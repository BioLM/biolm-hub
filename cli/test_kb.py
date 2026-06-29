"""
Tests for cli/kb.py — Knowledge Base CLI commands.

Tests the underlying logic of helper functions and validate_cmd:
- _load_sources / _get_all_model_slugs
- validate_cmd (schema, comparison.yaml, pending R2 checks)

Note: status_cmd and sources_cmd are not unit-tested here (they
primarily format Rich output).

We mock the filesystem and YAML parsing so tests run without the real
models/ tree.  Rich console output is captured via a patched Console
to verify warnings are actually printed.
"""

from io import StringIO
from pathlib import Path
from unittest.mock import patch

import pytest
import typer
import yaml
from rich.console import Console

from cli.kb import (
    REQUIRED_DOCS,
    REQUIRED_FIELDS,
    REQUIRED_PAPER_FIELDS,
    SKIP_DIRS,
    VALID_MOLECULE_TYPES,
    VALID_REPO_TYPES,
    VALID_TASKS,
    _get_all_model_slugs,
    _load_sources,
    validate_cmd,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

MINIMAL_SOURCES = {
    "model_slug": "test-model",
    "display_name": "Test Model",
    "license": {"type": "MIT"},
    "molecule_types": ["protein"],
    "tasks": ["embedding"],
    "primary_papers": [
        {
            "title": "Test Paper",
            "year": 2024,
            "doi": "10.1234/test",
            "pdf_r2": "knowledge-base/test-model/papers/test.pdf",
        }
    ],
}

MINIMAL_COMPARISON = {
    "strengths": ["a", "b", "c", "d", "e"],
    "weaknesses": ["a", "b", "c", "d", "e"],
    "use_when": ["a", "b", "c", "d", "e"],
    "dont_use_when": ["a", "b", "c", "d", "e"],
    "alternatives": [],
    "complements": [],
}


@pytest.fixture()
def mock_models_dir(tmp_path: Path):
    """Patch cli.kb.MODELS_DIR to a temporary directory for isolation."""
    with patch("cli.kb.MODELS_DIR", tmp_path):
        yield tmp_path


def _make_model_dir(tmp_path: Path, slug: str, sources: dict | None = None) -> Path:
    """Create a model directory with optional sources.yaml."""
    model_dir = tmp_path / slug
    model_dir.mkdir(parents=True, exist_ok=True)
    if sources is not None:
        (model_dir / "sources.yaml").write_text(yaml.dump(sources))
    return model_dir


def _capture_console():
    """Return (console, buf) for capturing Rich output."""
    buf = StringIO()
    test_console = Console(file=buf, force_terminal=False)
    return test_console, buf


# ---------------------------------------------------------------------------
# _get_all_model_slugs
# ---------------------------------------------------------------------------


class TestGetAllModelSlugs:
    def test_returns_sorted_slugs_with_sources(self, mock_models_dir: Path):
        """Only directories that contain sources.yaml are returned."""
        _make_model_dir(mock_models_dir, "zebra", sources={"model_slug": "zebra"})
        _make_model_dir(mock_models_dir, "alpha", sources={"model_slug": "alpha"})
        # No sources.yaml — should be excluded
        _make_model_dir(mock_models_dir, "no-sources")
        # A file, not a directory — should be excluded
        (mock_models_dir / "not-a-dir.txt").write_text("hi")

        result = _get_all_model_slugs()
        assert result == ["alpha", "zebra"]

    def test_skips_special_directories(self, mock_models_dir: Path):
        """Directories in SKIP_DIRS are excluded even if they have sources.yaml."""
        for skip in SKIP_DIRS:
            _make_model_dir(mock_models_dir, skip, sources={"model_slug": skip})
        _make_model_dir(
            mock_models_dir, "real-model", sources={"model_slug": "real-model"}
        )

        result = _get_all_model_slugs()
        assert result == ["real-model"]

    def test_empty_models_dir(self, mock_models_dir: Path):
        """Empty directory returns empty list."""
        assert _get_all_model_slugs() == []


# ---------------------------------------------------------------------------
# _load_sources
# ---------------------------------------------------------------------------


class TestLoadSources:
    def test_loads_valid_yaml(self, mock_models_dir: Path):
        """Valid sources.yaml is loaded and returned as dict."""
        _make_model_dir(mock_models_dir, "good-model", sources=MINIMAL_SOURCES)

        result = _load_sources("good-model")
        assert result["model_slug"] == "test-model"
        assert result["display_name"] == "Test Model"

    def test_missing_model_exits(self, mock_models_dir: Path):
        """Raises typer.Exit(1) when sources.yaml does not exist."""
        with pytest.raises(typer.Exit) as exc:
            _load_sources("nonexistent")
        assert exc.value.exit_code == 1

    def test_malformed_yaml_exits(self, mock_models_dir: Path):
        """Raises typer.Exit(1) on invalid YAML."""
        model_dir = mock_models_dir / "bad-yaml"
        model_dir.mkdir()
        (model_dir / "sources.yaml").write_text("invalid: yaml: [unterminated")

        with pytest.raises(typer.Exit) as exc:
            _load_sources("bad-yaml")
        assert exc.value.exit_code == 1

    def test_empty_yaml_returns_empty_dict(self, mock_models_dir: Path):
        """An empty YAML file returns {} (not None)."""
        model_dir = mock_models_dir / "empty-model"
        model_dir.mkdir()
        (model_dir / "sources.yaml").write_text("")

        result = _load_sources("empty-model")
        assert result == {}


# ---------------------------------------------------------------------------
# validate_cmd — schema and comparison.yaml validation
# ---------------------------------------------------------------------------


class TestValidateCmd:
    """Test the validate command's error/warning detection logic.

    We invoke validate_cmd directly, mocking the filesystem as needed.
    The function raises typer.Exit(1) when errors are found, which we
    capture with pytest.raises(typer.Exit).
    """

    def _make_complete_model(
        self,
        tmp_path: Path,
        slug: str = "test-model",
        sources: dict | None = None,
        comparison: dict | None = None,
        docs: set[str] | None = None,
    ) -> Path:
        """Create a fully valid model directory.

        Returns the model directory path. All required docs, sources.yaml,
        and comparison.yaml are created by default.
        """
        model_dir = tmp_path / slug
        model_dir.mkdir(parents=True, exist_ok=True)

        # Write sources.yaml
        src = sources if sources is not None else MINIMAL_SOURCES
        (model_dir / "sources.yaml").write_text(yaml.dump(src))

        # Write comparison.yaml
        comp = comparison if comparison is not None else MINIMAL_COMPARISON
        (model_dir / "comparison.yaml").write_text(yaml.dump(comp))

        # Write required docs
        doc_names = docs if docs is not None else REQUIRED_DOCS
        for doc in doc_names:
            (model_dir / doc).write_text(f"# {doc}")

        return model_dir

    def test_fully_valid_model_no_errors(self, mock_models_dir: Path):
        """A fully valid model should produce no errors or warnings."""
        self._make_complete_model(mock_models_dir)
        # Should NOT raise
        validate_cmd(model="test-model")

    def test_missing_sources_yaml_is_error(self, mock_models_dir: Path):
        """Missing sources.yaml triggers an error and typer.Exit(1)."""
        model_dir = mock_models_dir / "no-sources"
        model_dir.mkdir()
        for doc in REQUIRED_DOCS:
            (model_dir / doc).write_text(f"# {doc}")

        with pytest.raises(typer.Exit) as exc:
            validate_cmd(model="no-sources")
        assert exc.value.exit_code == 1

    def test_missing_required_fields_are_errors(self, mock_models_dir: Path):
        """Each missing required top-level field in sources.yaml is an error."""
        # Sources with no required fields at all
        empty_sources: dict = {}
        self._make_complete_model(mock_models_dir, sources=empty_sources)

        with pytest.raises(typer.Exit) as exc:
            validate_cmd(model="test-model")
        assert exc.value.exit_code == 1

    def test_missing_license_type_is_error(self, mock_models_dir: Path):
        """license dict without 'type' key triggers error."""
        sources = {**MINIMAL_SOURCES, "license": {"url": "http://example.com"}}
        self._make_complete_model(mock_models_dir, sources=sources)

        with pytest.raises(typer.Exit) as exc:
            validate_cmd(model="test-model")
        assert exc.value.exit_code == 1

    def test_unrecognized_molecule_type_is_warning(self, mock_models_dir: Path):
        """Unknown molecule_type triggers a warning (not an error)."""
        sources = {**MINIMAL_SOURCES, "molecule_types": ["protein", "alien_molecule"]}
        self._make_complete_model(mock_models_dir, sources=sources)

        test_console, buf = _capture_console()
        with patch("cli.kb.console", test_console):
            # Should NOT raise (warnings only)
            validate_cmd(model="test-model")
        output = buf.getvalue()
        assert "WARN" in output
        assert "alien_molecule" in output

    def test_unrecognized_task_is_warning(self, mock_models_dir: Path):
        """Unknown task triggers a warning (not an error)."""
        sources = {**MINIMAL_SOURCES, "tasks": ["embedding", "teleportation"]}
        self._make_complete_model(mock_models_dir, sources=sources)

        test_console, buf = _capture_console()
        with patch("cli.kb.console", test_console):
            validate_cmd(model="test-model")
        output = buf.getvalue()
        assert "WARN" in output
        assert "teleportation" in output

    def test_paper_missing_title_is_error(self, mock_models_dir: Path):
        """Primary paper without 'title' triggers error."""
        sources = {
            **MINIMAL_SOURCES,
            "primary_papers": [
                {
                    "year": 2024,
                    "pdf_r2": "knowledge-base/test/paper.pdf",
                }
            ],
        }
        self._make_complete_model(mock_models_dir, sources=sources)

        with pytest.raises(typer.Exit) as exc:
            validate_cmd(model="test-model")
        assert exc.value.exit_code == 1

    def test_paper_missing_year_is_error(self, mock_models_dir: Path):
        """Primary paper without 'year' triggers error."""
        sources = {
            **MINIMAL_SOURCES,
            "primary_papers": [
                {
                    "title": "Good Title",
                    "pdf_r2": "knowledge-base/test/paper.pdf",
                }
            ],
        }
        self._make_complete_model(mock_models_dir, sources=sources)

        with pytest.raises(typer.Exit) as exc:
            validate_cmd(model="test-model")
        assert exc.value.exit_code == 1

    def test_molecule_focus_as_list_is_warning(self, mock_models_dir: Path):
        """molecule_focus as a list (instead of string) triggers warning."""
        sources = {
            **MINIMAL_SOURCES,
            "primary_papers": [
                {
                    "title": "Paper",
                    "year": 2024,
                    "molecule_focus": ["protein", "rna"],
                    "pdf_r2": "knowledge-base/test/paper.pdf",
                }
            ],
        }
        self._make_complete_model(mock_models_dir, sources=sources)

        test_console, buf = _capture_console()
        with patch("cli.kb.console", test_console):
            # Should NOT raise (only warnings)
            validate_cmd(model="test-model")
        output = buf.getvalue()
        assert "WARN" in output
        assert "molecule_focus" in output

    def test_applied_lit_missing_title_is_error(self, mock_models_dir: Path):
        """Applied literature entry without 'title' triggers error."""
        sources = {
            **MINIMAL_SOURCES,
            "applied_literature": [{"year": 2024}],
        }
        self._make_complete_model(mock_models_dir, sources=sources)

        with pytest.raises(typer.Exit) as exc:
            validate_cmd(model="test-model")
        assert exc.value.exit_code == 1

    def test_source_repo_missing_url_is_error(self, mock_models_dir: Path):
        """source_repos entry without 'url' triggers error."""
        sources = {
            **MINIMAL_SOURCES,
            "source_repos": [{"type": "github"}],
        }
        self._make_complete_model(mock_models_dir, sources=sources)

        with pytest.raises(typer.Exit) as exc:
            validate_cmd(model="test-model")
        assert exc.value.exit_code == 1

    def test_unrecognized_repo_type_is_warning(self, mock_models_dir: Path):
        """Unrecognized source_repos type triggers warning."""
        sources = {
            **MINIMAL_SOURCES,
            "source_repos": [{"type": "magic_repo", "url": "http://example.com"}],
        }
        self._make_complete_model(mock_models_dir, sources=sources)

        test_console, buf = _capture_console()
        with patch("cli.kb.console", test_console):
            validate_cmd(model="test-model")
        output = buf.getvalue()
        assert "WARN" in output
        assert "magic_repo" in output

    def test_missing_docs_are_errors(self, mock_models_dir: Path):
        """Each missing required doc (README.md, MODEL.md, BIOLOGY.md) is an error."""
        # Create model with sources and comparison but NO doc files
        self._make_complete_model(mock_models_dir, docs=set())

        with pytest.raises(typer.Exit) as exc:
            validate_cmd(model="test-model")
        assert exc.value.exit_code == 1

    # --- comparison.yaml validation ---

    def test_comparison_missing_is_warning(self, mock_models_dir: Path):
        """Missing comparison.yaml triggers a warning (not error)."""
        model_dir = mock_models_dir / "test-model"
        model_dir.mkdir(parents=True)
        (model_dir / "sources.yaml").write_text(yaml.dump(MINIMAL_SOURCES))
        for doc in REQUIRED_DOCS:
            (model_dir / doc).write_text(f"# {doc}")
        # Do NOT create comparison.yaml

        test_console, buf = _capture_console()
        with patch("cli.kb.console", test_console):
            # Should NOT raise (missing comparison is only a warning)
            validate_cmd(model="test-model")
        output = buf.getvalue()
        assert "WARN" in output
        assert "comparison.yaml" in output

    def test_comparison_section_below_min_is_error(self, mock_models_dir: Path):
        """comparison.yaml with <3 entries in a section triggers error."""
        comparison = {
            "strengths": ["a", "b"],  # Only 2, needs 3
            "weaknesses": ["a", "b", "c", "d", "e"],
            "use_when": ["a", "b", "c", "d", "e"],
            "dont_use_when": ["a", "b", "c", "d", "e"],
            "alternatives": [],
            "complements": [],
        }
        self._make_complete_model(mock_models_dir, comparison=comparison)

        with pytest.raises(typer.Exit) as exc:
            validate_cmd(model="test-model")
        assert exc.value.exit_code == 1

    def test_comparison_section_below_target_is_warning(self, mock_models_dir: Path):
        """comparison.yaml with 3-4 entries triggers warning (target 5+)."""
        comparison = {
            "strengths": ["a", "b", "c"],  # 3 entries -> warning (target 5+)
            "weaknesses": ["a", "b", "c", "d", "e"],
            "use_when": ["a", "b", "c", "d", "e"],
            "dont_use_when": ["a", "b", "c", "d", "e"],
            "alternatives": [],
            "complements": [],
        }
        self._make_complete_model(mock_models_dir, comparison=comparison)

        test_console, buf = _capture_console()
        with patch("cli.kb.console", test_console):
            # Should NOT raise (only warnings)
            validate_cmd(model="test-model")
        output = buf.getvalue()
        assert "WARN" in output
        assert "strengths" in output
        assert "target 5+" in output

    def test_comparison_invalid_alternative_slug_is_error(self, mock_models_dir: Path):
        """Alternative with a model slug not in models/ triggers error."""
        comparison = {
            **MINIMAL_COMPARISON,
            "alternatives": [{"model": "nonexistent-model", "reason": "test"}],
        }
        self._make_complete_model(mock_models_dir, comparison=comparison)

        with pytest.raises(typer.Exit) as exc:
            validate_cmd(model="test-model")
        assert exc.value.exit_code == 1

    def test_comparison_invalid_complement_slug_is_error(self, mock_models_dir: Path):
        """Complement with a model slug not in models/ triggers error."""
        comparison = {
            **MINIMAL_COMPARISON,
            "complements": [{"model": "ghost-model", "reason": "test"}],
        }
        self._make_complete_model(mock_models_dir, comparison=comparison)

        with pytest.raises(typer.Exit) as exc:
            validate_cmd(model="test-model")
        assert exc.value.exit_code == 1

    def test_comparison_valid_alternative_slug_no_error(self, mock_models_dir: Path):
        """Alternative referencing an existing model directory is valid."""
        # Create the referenced model directory
        (mock_models_dir / "other-model").mkdir()

        comparison = {
            **MINIMAL_COMPARISON,
            "alternatives": [{"model": "other-model", "reason": "similar"}],
        }
        self._make_complete_model(mock_models_dir, comparison=comparison)

        validate_cmd(model="test-model")

    def test_comparison_malformed_yaml_is_error(self, mock_models_dir: Path):
        """Malformed comparison.yaml triggers error."""
        model_dir = self._make_complete_model(mock_models_dir)
        # Overwrite with bad YAML
        (model_dir / "comparison.yaml").write_text("invalid: yaml: [unterminated")

        with pytest.raises(typer.Exit) as exc:
            validate_cmd(model="test-model")
        assert exc.value.exit_code == 1

    def test_pending_r2_uploads_are_warnings(self, mock_models_dir: Path):
        """Papers without R2 paths trigger warnings about pending uploads."""
        sources = {
            **MINIMAL_SOURCES,
            "primary_papers": [
                {"title": "P1", "year": 2024, "pdf_r2": ""},
                {"title": "P2", "year": 2024, "pdf_r2": ""},
            ],
        }
        self._make_complete_model(mock_models_dir, sources=sources)

        test_console, buf = _capture_console()
        with patch("cli.kb.console", test_console):
            # Warnings only (missing R2 is a warning, not error)
            validate_cmd(model="test-model")
        output = buf.getvalue()
        assert "WARN" in output
        assert "primary paper(s) missing from R2" in output


# ---------------------------------------------------------------------------
# Constants sanity checks
# ---------------------------------------------------------------------------


class TestConstants:
    """Verify that the enum sets and required fields are reasonable."""

    def test_valid_molecule_types_not_empty(self):
        assert len(VALID_MOLECULE_TYPES) >= 5

    def test_valid_tasks_not_empty(self):
        assert len(VALID_TASKS) >= 5

    def test_valid_repo_types_includes_github(self):
        assert "github" in VALID_REPO_TYPES

    def test_required_fields_include_model_slug(self):
        assert "model_slug" in REQUIRED_FIELDS

    def test_required_paper_fields_include_title_and_year(self):
        assert REQUIRED_PAPER_FIELDS == {"title", "year"}

    def test_required_docs_include_core_files(self):
        assert "README.md" in REQUIRED_DOCS
        assert "MODEL.md" in REQUIRED_DOCS
        assert "BIOLOGY.md" in REQUIRED_DOCS

    def test_skip_dirs_includes_commons(self):
        assert "commons" in SKIP_DIRS
