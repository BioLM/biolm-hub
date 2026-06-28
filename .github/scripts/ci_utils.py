"""Shared utilities for CI/CD detection scripts.

Provides common functions used by detect_models.py to avoid duplication.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

# Directories under models/ that are not model implementations.
EXCLUDED_MODEL_DIRS = {"commons", "scripts", "__pycache__"}

# File extensions that are documentation/data-only and should not trigger deployments.
# These are non-code files: docs (.md, .txt, .rst, .adoc) and data/metadata (.yaml, .yml, .json).
NON_CODE_EXTENSIONS = {".md", ".txt", ".rst", ".adoc", ".yaml", ".yml", ".json"}


def is_non_code(file_path: str) -> bool:
    """Return True if the file is a documentation or data file (not code).

    Used by model detection to skip non-code changes (README.md, sources.yaml, etc.)
    that should not trigger model deployments.
    """
    return any(file_path.endswith(ext) for ext in NON_CODE_EXTENSIONS)


# Backwards-compatible alias.
is_docs_only = is_non_code


def run_git_command(args: list[str]) -> str:
    """Run a git command and return stripped stdout. Exits on failure."""
    try:
        result = subprocess.run(
            ["git"] + args,
            capture_output=True,
            text=True,
            check=True,
            timeout=30,
        )
        return result.stdout.strip()
    except subprocess.CalledProcessError as e:
        print(f"::error::Git command failed: git {' '.join(args)}")
        print(f"::error::Exit code: {e.returncode}")
        print(f"::error::Stderr: {e.stderr}")
        sys.exit(1)
    except subprocess.TimeoutExpired:
        print(f"::error::Git command timed out: git {' '.join(args)}")
        sys.exit(1)


def get_changed_files(base_ref: str = "HEAD") -> list[str]:
    """Get list of changed files compared to base reference."""
    changed_files = run_git_command(["diff", "--name-only", base_ref])
    if changed_files:
        return changed_files.split("\n")
    return []


def list_subdirectories(base_dir: str, exclude: set[str] | None = None) -> set[str]:
    """List subdirectory names under base_dir, excluding specified names."""
    base = Path(base_dir)
    if not base.exists():
        return set()
    exclude = exclude or set()
    return {
        item.name
        for item in base.iterdir()
        if item.is_dir() and item.name not in exclude
    }


def write_github_outputs(outputs: dict[str, str]) -> None:
    """Write key-value outputs for GitHub Actions consumption.

    Writes to GITHUB_OUTPUT file if available, otherwise prints to stdout
    with a warning.
    """
    github_output = os.environ.get("GITHUB_OUTPUT")

    if github_output:
        try:
            with open(github_output, "a") as f:
                for key, value in outputs.items():
                    f.write(f"{key}={value}\n")
        except OSError as e:
            print(f"::error::Failed to write to GITHUB_OUTPUT: {e}")
            sys.exit(1)
    else:
        print(
            "::warning::GITHUB_OUTPUT not set, "
            "outputs will not be available to workflow"
        )
        for key, value in outputs.items():
            print(f"{key}={value}")


def json_dumps(value) -> str:
    """Serialize value to JSON string (convenience wrapper)."""
    return json.dumps(value)
