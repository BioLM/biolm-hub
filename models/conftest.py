"""Pytest configuration shared across every model test suite.

Registers the custom markers used by the generated test functions so that
running a single model's tests (``pytest models/<model>/test.py``) works even
when the root ``pyproject.toml`` ``[tool.pytest.ini_options]`` config is not in
scope. The marker definitions mirror that config; ``addinivalue_line`` is
idempotent, so registering them here as well is harmless when both apply.
"""

import pytest

MARKERS = {
    "integration": "full local app run against Modal (slower; needs a Modal env + R2)",
    "deployment": "runs against a live deployed endpoint",
    "slow": "full end-to-end correctness (minutes; run before releases)",
    "e2e": "end-to-end system validation",
    "live_modal": "invokes a live Modal app runner",
    "no_parallel": "cannot run in parallel (timing-sensitive or shared state)",
}


def pytest_configure(config: pytest.Config) -> None:
    """Register the BioLM model-test markers for single-file pytest runs."""
    for name, description in MARKERS.items():
        config.addinivalue_line("markers", f"{name}: {description}")
