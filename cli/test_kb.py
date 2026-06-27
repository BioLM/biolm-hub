"""
Tests for cli/kb.py — Knowledge Base CLI commands.

Tests the underlying logic of helper functions and validate_cmd:
- _load_sources / _get_all_model_slugs
- _collect_missing_papers / _format_missing_report
- validate_cmd (schema, comparison.yaml, pending R2 checks)

Note: status_cmd, missing_cmd, sources_cmd, and matrix_cmd are not
unit-tested here (they primarily format Rich output).

We mock the filesystem and YAML parsing so tests run without the real
models/ tree.  Rich console output is captured via a patched Console
to verify warnings are actually printed.
"""

from io import StringIO
from pathlib import Path
from unittest.mock import patch

import click
import pytest
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
    _collect_missing_papers,
    _format_missing_report,
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
        with pytest.raises(click.exceptions.Exit) as exc:
            _load_sources("nonexistent")
        assert exc.value.exit_code == 1

    def test_malformed_yaml_exits(self, mock_models_dir: Path):
        """Raises typer.Exit(1) on invalid YAML."""
        model_dir = mock_models_dir / "bad-yaml"
        model_dir.mkdir()
        (model_dir / "sources.yaml").write_text("invalid: yaml: [unterminated")

        with pytest.raises(click.exceptions.Exit) as exc:
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
# _collect_missing_papers
# ---------------------------------------------------------------------------


class TestCollectMissingPapers:
    """Tests for paper categorization by acquisition difficulty."""

    def _setup_model(self, mock_models_dir: Path, slug: str, sources: dict) -> None:
        _make_model_dir(mock_models_dir, slug, sources=sources)

    def test_paper_already_in_r2_is_skipped(self, mock_models_dir: Path):
        """Papers with a valid knowledge-base/ R2 path are not missing."""
        self._setup_model(
            mock_models_dir,
            "m1",
            {
                "primary_papers": [
                    {
                        "title": "Good Paper",
                        "doi": "10.1234/good",
                        "pdf_r2": "knowledge-base/m1/papers/good.pdf",
                    }
                ]
            },
        )
        oa, pw, nop = _collect_missing_papers(["m1"])
        assert oa == [] and pw == [] and nop == []

    def test_pending_paper_is_counted(self, mock_models_dir: Path):
        """pdf_r2='pending' is treated as missing."""
        self._setup_model(
            mock_models_dir,
            "m1",
            {
                "primary_papers": [
                    {
                        "title": "Pending Paper",
                        "doi": "10.1234/pending",
                        "pdf_r2": "pending",
                    }
                ]
            },
        )
        oa, pw, nop = _collect_missing_papers(["m1"])
        # Has DOI but not arxiv/biorxiv -> paywall
        assert len(pw) == 1
        assert pw[0][0] == "m1"

    def test_empty_pdf_r2_is_counted(self, mock_models_dir: Path):
        """Empty pdf_r2 string is treated as missing."""
        self._setup_model(
            mock_models_dir,
            "m1",
            {
                "primary_papers": [
                    {"title": "No R2", "doi": "10.1234/test", "pdf_r2": ""}
                ]
            },
        )
        oa, pw, nop = _collect_missing_papers(["m1"])
        assert len(pw) == 1

    def test_missing_pdf_r2_key_is_counted(self, mock_models_dir: Path):
        """No pdf_r2 key at all is treated as missing."""
        self._setup_model(
            mock_models_dir,
            "m1",
            {"primary_papers": [{"title": "No Key", "doi": "10.1234/test"}]},
        )
        oa, pw, nop = _collect_missing_papers(["m1"])
        assert len(pw) == 1

    def test_null_pdf_r2_is_counted(self, mock_models_dir: Path):
        """pdf_r2 explicitly set to None (YAML null) is treated as missing."""
        self._setup_model(
            mock_models_dir,
            "m1",
            {
                "primary_papers": [
                    {"title": "Null R2", "doi": "10.1234/test", "pdf_r2": None}
                ]
            },
        )
        oa, pw, nop = _collect_missing_papers(["m1"])
        assert len(pw) == 1

    def test_arxiv_is_open_access(self, mock_models_dir: Path):
        """Paper with arxiv identifier is categorized as open access."""
        self._setup_model(
            mock_models_dir,
            "m1",
            {
                "primary_papers": [
                    {
                        "title": "ArXiv Paper",
                        "arxiv": "2401.12345",
                        "pdf_r2": "",
                    }
                ]
            },
        )
        oa, pw, nop = _collect_missing_papers(["m1"])
        assert len(oa) == 1
        assert oa[0][2] == "primary"

    def test_biorxiv_doi_prefix_is_open_access(self, mock_models_dir: Path):
        """bioRxiv papers identified by 10.1101/ DOI prefix -> open access.

        Regression test: bioRxiv DOIs use the 10.1101/ prefix (e.g.
        10.1101/2024.11.19.624167). An earlier version failed to
        categorize these as open access.
        """
        self._setup_model(
            mock_models_dir,
            "m1",
            {
                "primary_papers": [
                    {
                        "title": "bioRxiv Paper",
                        "doi": "10.1101/2024.11.19.624167",
                        "pdf_r2": "",
                    }
                ]
            },
        )
        oa, pw, nop = _collect_missing_papers(["m1"])
        assert len(oa) == 1
        assert len(pw) == 0, "bioRxiv DOI should NOT be categorized as paywall"

    def test_biorxiv_in_doi_string_is_open_access(self, mock_models_dir: Path):
        """DOI containing 'biorxiv' (case-insensitive) -> open access."""
        self._setup_model(
            mock_models_dir,
            "m1",
            {
                "primary_papers": [
                    {
                        "title": "bioRxiv Paper 2",
                        "doi": "https://doi.org/10.1101/biorxiv.something",
                        "pdf_r2": "",
                    }
                ]
            },
        )
        oa, pw, nop = _collect_missing_papers(["m1"])
        assert len(oa) == 1

    def test_regular_doi_is_paywall(self, mock_models_dir: Path):
        """A normal journal DOI without arxiv/biorxiv -> paywall."""
        self._setup_model(
            mock_models_dir,
            "m1",
            {
                "primary_papers": [
                    {
                        "title": "Nature Paper",
                        "doi": "10.1038/s41586-024",
                        "pdf_r2": "",
                    }
                ]
            },
        )
        oa, pw, nop = _collect_missing_papers(["m1"])
        assert len(pw) == 1

    def test_no_identifiers_is_no_paper(self, mock_models_dir: Path):
        """Paper with neither DOI nor arXiv -> no_paper bucket."""
        self._setup_model(
            mock_models_dir,
            "m1",
            {"primary_papers": [{"title": "Mystery Paper", "pdf_r2": ""}]},
        )
        oa, pw, nop = _collect_missing_papers(["m1"])
        assert len(nop) == 1

    def test_applied_literature_also_collected(self, mock_models_dir: Path):
        """Papers in applied_literature section are collected with kind='applied'."""
        self._setup_model(
            mock_models_dir,
            "m1",
            {
                "applied_literature": [
                    {
                        "title": "Applied Paper",
                        "arxiv": "2401.99999",
                        "pdf_r2": "",
                    }
                ]
            },
        )
        oa, pw, nop = _collect_missing_papers(["m1"])
        assert len(oa) == 1
        assert oa[0][2] == "applied"

    def test_model_without_sources_yaml_skipped(self, mock_models_dir: Path):
        """Model directories without sources.yaml are silently skipped."""
        _make_model_dir(mock_models_dir, "no-sources")  # No sources.yaml
        oa, pw, nop = _collect_missing_papers(["no-sources"])
        assert oa == [] and pw == [] and nop == []

    def test_multiple_models_aggregated(self, mock_models_dir: Path):
        """Papers from multiple models are aggregated correctly."""
        self._setup_model(
            mock_models_dir,
            "m1",
            {"primary_papers": [{"title": "P1", "arxiv": "2401.00001", "pdf_r2": ""}]},
        )
        self._setup_model(
            mock_models_dir,
            "m2",
            {"primary_papers": [{"title": "P2", "doi": "10.1038/test", "pdf_r2": ""}]},
        )
        oa, pw, nop = _collect_missing_papers(["m1", "m2"])
        assert len(oa) == 1  # arxiv paper
        assert len(pw) == 1  # journal paper


# ---------------------------------------------------------------------------
# _format_missing_report
# ---------------------------------------------------------------------------


class TestFormatMissingReport:
    def test_all_empty_shows_completion_message(self):
        """When all lists are empty, report says everything is in R2."""
        report = _format_missing_report([], [], [])
        assert "All papers are in R2!" in report
        assert "Total missing: 0 papers" in report

    def test_open_access_section_rendered(self):
        """Open access papers appear in the Open Access section."""
        oa = [("esm2", {"title": "ESM2 Paper", "doi": "10.1101/xxx"}, "primary")]
        report = _format_missing_report(oa, [], [])
        assert "Open Access" in report
        assert "1 papers" in report
        assert "esm2" in report
        assert "ESM2 Paper" in report

    def test_paywall_section_rendered(self):
        """Paywall papers appear in the Paywall section."""
        pw = [("boltz", {"title": "Boltz Paper", "doi": "10.1038/xxx"}, "applied")]
        report = _format_missing_report([], pw, [])
        assert "Paywall" in report
        assert "boltz" in report

    def test_no_paper_section_rendered(self):
        """No-paper entries appear in the Non-Academic section."""
        nop = [("nims", {"title": "NIM Tool"}, "primary")]
        report = _format_missing_report([], [], nop)
        assert "No Paper" in report
        assert "nims" in report

    def test_total_count_correct(self):
        """Total missing count sums all three categories."""
        oa = [("m1", {"title": "A"}, "primary")]
        pw = [("m2", {"title": "B"}, "applied"), ("m3", {"title": "C"}, "primary")]
        nop = [("m4", {"title": "D"}, "primary")]
        report = _format_missing_report(oa, pw, nop)
        assert "Total missing: 4 papers" in report

    def test_long_title_truncated_in_table(self):
        """Titles longer than 60 chars are truncated in the table rows."""
        long_title = "A" * 100
        oa = [("m1", {"title": long_title, "doi": "10.1101/xxx"}, "primary")]
        report = _format_missing_report(oa, [], [])
        # The table row should have the truncated title (60 chars)
        assert "A" * 60 in report
        assert "A" * 100 not in report

    def test_report_starts_with_header(self):
        """Report starts with markdown header."""
        report = _format_missing_report([], [], [])
        assert report.startswith("# Missing R2 Papers Report")

    def test_report_has_date(self):
        """Report includes generation date."""
        import datetime

        report = _format_missing_report([], [], [])
        assert datetime.date.today().isoformat() in report


# ---------------------------------------------------------------------------
# validate_cmd — schema and comparison.yaml validation
# ---------------------------------------------------------------------------


class TestValidateCmd:
    """Test the validate command's error/warning detection logic.

    We invoke validate_cmd directly, mocking the filesystem as needed.
    The function raises typer.Exit(1) when errors are found, which we
    capture with pytest.raises(click.exceptions.Exit).
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

        with pytest.raises(click.exceptions.Exit) as exc:
            validate_cmd(model="no-sources")
        assert exc.value.exit_code == 1

    def test_missing_required_fields_are_errors(self, mock_models_dir: Path):
        """Each missing required top-level field in sources.yaml is an error."""
        # Sources with no required fields at all
        empty_sources: dict = {}
        self._make_complete_model(mock_models_dir, sources=empty_sources)

        with pytest.raises(click.exceptions.Exit) as exc:
            validate_cmd(model="test-model")
        assert exc.value.exit_code == 1

    def test_missing_license_type_is_error(self, mock_models_dir: Path):
        """license dict without 'type' key triggers error."""
        sources = {**MINIMAL_SOURCES, "license": {"url": "http://example.com"}}
        self._make_complete_model(mock_models_dir, sources=sources)

        with pytest.raises(click.exceptions.Exit) as exc:
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

        with pytest.raises(click.exceptions.Exit) as exc:
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

        with pytest.raises(click.exceptions.Exit) as exc:
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

        with pytest.raises(click.exceptions.Exit) as exc:
            validate_cmd(model="test-model")
        assert exc.value.exit_code == 1

    def test_source_repo_missing_url_is_error(self, mock_models_dir: Path):
        """source_repos entry without 'url' triggers error."""
        sources = {
            **MINIMAL_SOURCES,
            "source_repos": [{"type": "github"}],
        }
        self._make_complete_model(mock_models_dir, sources=sources)

        with pytest.raises(click.exceptions.Exit) as exc:
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

        with pytest.raises(click.exceptions.Exit) as exc:
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

        with pytest.raises(click.exceptions.Exit) as exc:
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

        with pytest.raises(click.exceptions.Exit) as exc:
            validate_cmd(model="test-model")
        assert exc.value.exit_code == 1

    def test_comparison_invalid_complement_slug_is_error(self, mock_models_dir: Path):
        """Complement with a model slug not in models/ triggers error."""
        comparison = {
            **MINIMAL_COMPARISON,
            "complements": [{"model": "ghost-model", "reason": "test"}],
        }
        self._make_complete_model(mock_models_dir, comparison=comparison)

        with pytest.raises(click.exceptions.Exit) as exc:
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

        with pytest.raises(click.exceptions.Exit) as exc:
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


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


class TestEdgeCases:
    """Edge cases and regression tests."""

    def test_biorxiv_doi_with_date_prefix_open_access(self, mock_models_dir: Path):
        """Regression: bioRxiv DOIs like 10.1101/2024.01.01.000000 must be open access.

        This is the canonical format for bioRxiv DOIs and must not fall through
        to the paywall bucket.
        """
        _make_model_dir(
            mock_models_dir,
            "m1",
            sources={
                "primary_papers": [
                    {
                        "title": "bioRxiv Test",
                        "doi": "10.1101/2024.01.01.000000",
                        "pdf_r2": "",
                    }
                ]
            },
        )
        oa, pw, nop = _collect_missing_papers(["m1"])
        assert len(oa) == 1
        assert len(pw) == 0

    def test_medrxiv_doi_is_open_access(self, mock_models_dir: Path):
        """medRxiv also uses 10.1101/ prefix and should be open access."""
        _make_model_dir(
            mock_models_dir,
            "m1",
            sources={
                "primary_papers": [
                    {
                        "title": "medRxiv Test",
                        "doi": "10.1101/2024.05.15.123456",
                        "pdf_r2": "",
                    }
                ]
            },
        )
        oa, pw, nop = _collect_missing_papers(["m1"])
        assert len(oa) == 1

    def test_both_arxiv_and_doi_prefers_open_access(self, mock_models_dir: Path):
        """Paper with both arxiv and a journal DOI -> open access (arxiv check first)."""
        _make_model_dir(
            mock_models_dir,
            "m1",
            sources={
                "primary_papers": [
                    {
                        "title": "Dual Identifier",
                        "arxiv": "2401.12345",
                        "doi": "10.1038/s41586-024",
                        "pdf_r2": "",
                    }
                ]
            },
        )
        oa, pw, nop = _collect_missing_papers(["m1"])
        assert len(oa) == 1
        assert len(pw) == 0

    def test_empty_slug_list_produces_no_results(self, mock_models_dir: Path):
        """Passing an empty list of slugs returns empty results."""
        oa, pw, nop = _collect_missing_papers([])
        assert oa == [] and pw == [] and nop == []

    def test_sources_with_no_papers_sections(self, mock_models_dir: Path):
        """sources.yaml with no primary_papers or applied_literature -> no missing."""
        _make_model_dir(
            mock_models_dir,
            "m1",
            sources={"model_slug": "m1", "display_name": "M1"},
        )
        oa, pw, nop = _collect_missing_papers(["m1"])
        assert oa == [] and pw == [] and nop == []
