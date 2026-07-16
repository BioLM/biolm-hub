"""CI guard: the generated model catalog and every model count are fresh.

Modal-free (only imports model configs), so it runs in the normal unit tier and thus in
``make check``. It re-derives the catalog table in ``models/README.md`` **and** the model counts in
``README.md`` (badge + pitch) and ``docs/media/architecture.md`` from each model's config, and fails
with an actionable message on any drift. See ``tooling/gen_model_catalog.py`` to fix a failure.
"""

from __future__ import annotations

from tooling.gen_model_catalog import README, build_catalog, extract_block, main


def test_readme_catalog_is_fresh() -> None:
    committed = extract_block(README.read_text(encoding="utf-8"))
    assert committed is not None, (
        "models/README.md is missing the generated-catalog fences — "
        "run `python -m tooling.gen_model_catalog`"
    )
    assert (
        committed == build_catalog()
    ), "models/README.md catalog is stale — run `python -m tooling.gen_model_catalog`"


def test_model_counts_are_fresh() -> None:
    # Covers the models/README catalog + the counts in README.md (badge/pitch) and architecture.md.
    assert main(["--check"]) == 0, (
        "A model count is stale (models/README.md, README.md badge/pitch, or "
        "docs/media/architecture.md) — run `python -m tooling.gen_model_catalog`"
    )
