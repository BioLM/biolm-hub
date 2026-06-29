"""Schema-field documentation consistency checker.

Every request/response field in every model must carry a description that
*renders* in the OpenAPI/JSON schema (so it shows up in the docs site and the
live FastAPI docs), and shared fields must use the canonical wording from
``tooling/field_glossary.yaml``. This is enforced in CI by
``tooling/test_schema_docs.py`` and is a handy gate while authoring a model:

    python tooling/check_schema_docs.py            # check every model
    python tooling/check_schema_docs.py --model esm2

A description set via ``Field(description=...)`` *inside* ``Optional[Annotated[
...]]`` is silently dropped by Pydantic (the Field lands in a Union arm) — this
checker inspects the rendered ``model_json_schema()``, so it catches exactly that
class of mistake. Fix it by moving the ``Field`` to field level.
"""

from __future__ import annotations

import argparse
import importlib
import sys
from pathlib import Path
from typing import Any

import yaml

REPO = Path(__file__).resolve().parent.parent
MODELS_DIR = REPO / "models"
GLOSSARY = Path(__file__).resolve().parent / "field_glossary.yaml"
SKIP = {"commons", "__pycache__"}


def _discover() -> list[str]:
    return sorted(
        p.name
        for p in MODELS_DIR.iterdir()
        if p.is_dir() and p.name not in SKIP and (p / "config.py").exists()
    )


def _blocks(schema_cls: Any) -> list[tuple[str, dict[str, Any]]]:
    """The schema plus every nested ``$defs`` block, as (owner, block) pairs."""
    js = schema_cls.model_json_schema()
    out = [(schema_cls.__name__, js)]
    for name, block in js.get("$defs", {}).items():
        out.append((name, block))
    return out


def _load_verbatim() -> dict[str, list[str]]:
    data = yaml.safe_load(GLOSSARY.read_text(encoding="utf-8")) or {}
    return data.get("verbatim", {})


def check_model(name: str, verbatim: dict[str, list[str]]) -> list[str]:
    """Return a list of violation strings for one model (empty == clean)."""
    try:
        fam = importlib.import_module(f"models.{name}.config").MODEL_FAMILY
    except Exception as exc:  # noqa: BLE001
        return [f"{name}: cannot import config ({exc})"]

    violations: list[str] = []
    for action in fam.action_schemas:
        for schema_cls in (action.request_schema, action.response_schema):
            for owner, block in _blocks(schema_cls):
                for field, prop in block.get("properties", {}).items():
                    desc = (prop.get("description") or "").strip()
                    if not desc:
                        violations.append(
                            f"{name}: {owner}.{field} has no rendered description "
                            f"(if it's Optional[Annotated[..., Field(...)]], move the "
                            f"Field to field level)"
                        )
                        continue
                    allowed = verbatim.get(field)
                    if allowed and desc not in allowed:
                        violations.append(
                            f"{name}: {owner}.{field} drifts from the glossary.\n"
                            f"      found:    {desc!r}\n"
                            f"      expected: {allowed!r}"
                        )
    return violations


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", help="check a single model (default: all)")
    args = parser.parse_args(argv)

    verbatim = _load_verbatim()
    names = [args.model] if args.model else _discover()

    all_violations: list[str] = []
    for name in names:
        all_violations.extend(check_model(name, verbatim))

    if all_violations:
        print(f"✗ {len(all_violations)} schema-doc violation(s):\n")
        for v in all_violations:
            print(f"  - {v}")
        print(
            "\nEvery schema field needs a Field(description=...) that renders, and "
            "shared fields must match tooling/field_glossary.yaml."
        )
        return 1

    scope = args.model or f"{len(names)} models"
    print(f"✓ schema docs OK ({scope})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
