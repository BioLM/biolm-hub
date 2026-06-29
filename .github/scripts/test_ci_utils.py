"""Tests for ci_utils.py shared utilities."""

import json
from pathlib import Path
from typing import Any

from ci_utils import (
    EXCLUDED_MODEL_DIRS,
    NON_CODE_EXTENSIONS,
    is_docs_only,
    is_non_code,
    json_dumps,
    list_subdirectories,
    write_github_outputs,
)


class TestIsNonCode:
    """Test the is_non_code helper (and its is_docs_only alias)."""

    def test_markdown_is_non_code(self) -> None:
        assert is_non_code("models/esm2/README.md") is True

    def test_txt_is_non_code(self) -> None:
        assert is_non_code("CHANGELOG.txt") is True

    def test_rst_is_non_code(self) -> None:
        assert is_non_code("docs/index.rst") is True

    def test_adoc_is_non_code(self) -> None:
        assert is_non_code("guide.adoc") is True

    def test_python_is_code(self) -> None:
        assert is_non_code("models/esm2/app.py") is False

    def test_yaml_is_non_code(self) -> None:
        assert is_non_code("models/esm2/sources.yaml") is True

    def test_yml_is_non_code(self) -> None:
        assert is_non_code("config.yml") is True

    def test_json_is_non_code(self) -> None:
        assert is_non_code("manifest.json") is True

    def test_no_extension_is_code(self) -> None:
        assert is_non_code("Makefile") is False

    def test_substring_not_matched(self) -> None:
        """Ensure .md only matches at the end, not as substring."""
        assert is_non_code("models/esm2/mdfile.py") is False

    def test_all_non_code_extensions_covered(self) -> None:
        """Every extension in NON_CODE_EXTENSIONS should return True."""
        for ext in NON_CODE_EXTENSIONS:
            assert is_non_code(f"file{ext}") is True

    def test_backwards_compat_alias(self) -> None:
        """is_docs_only is kept as an alias for is_non_code."""
        assert is_docs_only is is_non_code


class TestListSubdirectories:
    """Test the list_subdirectories helper."""

    # Resolve models/ relative to the repo root, not the CWD.
    _repo_root = Path(__file__).resolve().parent.parent.parent
    _models_dir = str(_repo_root / "models")

    def test_models_dir_returns_models(self) -> None:
        result = list_subdirectories(self._models_dir, EXCLUDED_MODEL_DIRS)
        assert len(result) > 0, "Should find at least one model"
        assert "commons" not in result
        assert "scripts" not in result
        assert "__pycache__" not in result

    def test_nonexistent_dir_returns_empty(self) -> None:
        result = list_subdirectories("/nonexistent/path/xyz", set())
        assert result == set()

    def test_no_exclusions(self) -> None:
        result_no_exclude = list_subdirectories(self._models_dir, set())
        result_with_exclude = list_subdirectories(self._models_dir, EXCLUDED_MODEL_DIRS)
        assert len(result_no_exclude) >= len(result_with_exclude)

    def test_exclude_none_defaults_empty(self) -> None:
        result = list_subdirectories(self._models_dir)
        assert "commons" in result, "Without exclusions, commons should be present"


class TestWriteGithubOutputs:
    """Test the generic write_github_outputs function."""

    # pytest fixture params (tmp_path, monkeypatch, capsys) are typed as Any
    # here because importing from _pytest or pytest transitively loads numpy stubs,
    # which crash mypy 1.5.1 on Python 3.12 (ASTConverter.visit_TypeAlias missing).
    # pathlib.Path is safe to use directly for tmp_path.

    def test_writes_to_file(self, tmp_path: Path, monkeypatch: Any) -> None:
        output_file = tmp_path / "github_output"
        output_file.touch()
        monkeypatch.setenv("GITHUB_OUTPUT", str(output_file))

        write_github_outputs({"key1": "value1", "key2": "value2"})

        content = output_file.read_text()
        assert "key1=value1\n" in content
        assert "key2=value2\n" in content

    def test_prints_to_stdout_without_env(self, capsys: Any, monkeypatch: Any) -> None:
        monkeypatch.delenv("GITHUB_OUTPUT", raising=False)

        write_github_outputs({"mykey": "myval"})

        captured = capsys.readouterr()
        assert "mykey=myval" in captured.out
        assert "GITHUB_OUTPUT not set" in captured.out

    def test_appends_to_existing_file(self, tmp_path: Path, monkeypatch: Any) -> None:
        output_file = tmp_path / "github_output"
        output_file.write_text("existing=data\n")
        monkeypatch.setenv("GITHUB_OUTPUT", str(output_file))

        write_github_outputs({"new": "value"})

        content = output_file.read_text()
        assert "existing=data\n" in content
        assert "new=value\n" in content

    def test_empty_outputs_dict(self, tmp_path: Path, monkeypatch: Any) -> None:
        output_file = tmp_path / "github_output"
        output_file.touch()
        monkeypatch.setenv("GITHUB_OUTPUT", str(output_file))

        write_github_outputs({})

        content = output_file.read_text()
        assert content == ""


class TestJsonDumps:
    """Test the json_dumps convenience wrapper."""

    def test_list(self) -> None:
        assert json_dumps(["a", "b"]) == '["a", "b"]'

    def test_empty_list(self) -> None:
        assert json_dumps([]) == "[]"

    def test_dict(self) -> None:
        result = json.loads(json_dumps({"key": "val"}))
        assert result == {"key": "val"}


class TestConstants:
    """Verify shared constants are correct."""

    def test_excluded_model_dirs(self) -> None:
        assert EXCLUDED_MODEL_DIRS == {"commons", "scripts", "__pycache__"}

    def test_non_code_extensions(self) -> None:
        assert ".md" in NON_CODE_EXTENSIONS
        assert ".yaml" in NON_CODE_EXTENSIONS
        assert ".py" not in NON_CODE_EXTENSIONS
