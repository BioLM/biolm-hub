"""Guard tests for the slug ↔ directory / module naming convention.

Ensures every registered model resolves from its (hyphen) ``base_model_slug`` to a real package
directory, ``app.py`` and ``config.py`` — and that the slug↔dir round-trip is lossless — so the
hyphen/underscore boundary can never silently drift (the bug class that broke ``bh deploy dna-chisel``).
"""

from __future__ import annotations

import pytest

from gateway.model_discovery import get_model_mapper
from models.commons.model.naming import (
    dirname_to_slug,
    model_app_path,
    model_config_path,
    model_dir,
    slug_to_dirname,
    slug_to_module,
)

REGISTERED_SLUGS = sorted(get_model_mapper().get_all_registered_models())


def test_slug_to_dirname_accepts_either_form() -> None:
    assert slug_to_dirname("dna-chisel") == "dna_chisel"
    assert slug_to_dirname("dna_chisel") == "dna_chisel"  # idempotent on a dir name
    assert slug_to_dirname("esm2") == "esm2"


def test_slug_to_module() -> None:
    assert slug_to_module("dna-chisel") == "models.dna_chisel"
    assert slug_to_module("esm2") == "models.esm2"


@pytest.mark.parametrize("slug", REGISTERED_SLUGS)
def test_every_slug_resolves_to_real_files(slug: str) -> None:
    assert model_dir(slug).is_dir(), f"{slug}: package dir does not resolve"
    assert model_app_path(slug).exists(), f"{slug}: app.py does not resolve"
    assert model_config_path(slug).exists(), f"{slug}: config.py does not resolve"


@pytest.mark.parametrize("slug", REGISTERED_SLUGS)
def test_slug_dirname_roundtrip_is_lossless(slug: str) -> None:
    # dir→slug is lossless only because no base_model_slug contains an underscore. This guard fails
    # loudly if a future slug ever does (which would make dirname_to_slug ambiguous).
    assert "_" not in slug, f"{slug}: base slugs must not contain '_' (breaks dir→slug)"
    assert dirname_to_slug(slug_to_dirname(slug)) == slug
