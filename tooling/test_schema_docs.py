"""CI guard: every model's schema fields are documented + glossary-consistent.

Modal-free (only imports model configs), so it runs in the unit tier. See
``tooling/check_schema_docs.py`` for the rules and a CLI to run it yourself.
"""

from __future__ import annotations

from tooling.check_schema_docs import _discover, _load_verbatim, check_model


def test_all_schema_fields_documented_and_consistent() -> None:
    verbatim = _load_verbatim()
    violations: list[str] = []
    for name in _discover():
        violations.extend(check_model(name, verbatim))
    assert not violations, "schema-doc violations:\n" + "\n".join(violations)
