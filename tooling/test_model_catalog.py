"""CI guard: the generated catalog in ``models/README.md`` is fresh.

Modal-free (only imports model configs), so it runs in the normal unit tier and
thus in ``make check``. It regenerates the catalog block in memory and asserts it
matches what is currently committed between the fences in ``models/README.md``.
On mismatch it fails with an actionable message. See
``tooling/gen_model_catalog.py`` for the generator (and to fix a failure).
"""

from __future__ import annotations

from tooling.gen_model_catalog import README, build_catalog, extract_block


def test_readme_catalog_is_fresh() -> None:
    committed = extract_block(README.read_text(encoding="utf-8"))
    assert committed is not None, (
        "models/README.md is missing the generated-catalog fences — "
        "run `python -m tooling.gen_model_catalog`"
    )
    assert committed == build_catalog(), (
        "models/README.md catalog is stale — "
        "run `python -m tooling.gen_model_catalog`"
    )
