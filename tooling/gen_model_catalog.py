"""Generate the GitHub-viewable model + variant catalog in ``models/README.md``.

Unlike the mkdocs site (whose per-model pages are rendered at build time), the
repo's ``models/README.md`` is browsed directly on GitHub, so its catalog table
is committed. This module regenerates that table from every model's
``config.py`` ``MODEL_FAMILY`` and writes it back into the fenced region of
``models/README.md`` (idempotently: running it twice is a no-op).

    python -m tooling.gen_model_catalog            # rewrite models/README.md
    python -m tooling.gen_model_catalog --check     # fail (non-zero) if stale

The table lists every *deployable variant* — the "what's callable" reference:
its public endpoint slug (``POST /api/v1/{slug}/{action}`` under ``bh serve``),
its Modal app name (``modal.Cls.from_name(app_name, ...)``), the closed-set
actions its family supports, and the GPU it runs on. It is Modal-free (only
imports model configs, exactly like ``docs/gen_pages.py``), so it needs no
credentials. ``tooling/test_model_catalog.py`` enforces freshness in CI.
"""

from __future__ import annotations

import argparse
import importlib
import re
import sys
from pathlib import Path

from models.commons.model.config import ModelFamily
from models.commons.model.schema import ModalResourceSpec

REPO = Path(__file__).resolve().parent.parent
MODELS_DIR = REPO / "models"
README = MODELS_DIR / "README.md"

# Mirror ``docs/gen_pages.py`` discovery: ``dummy`` is the unresolved template
# and ``commons`` is the shared framework — neither is a deployable model.
SKIP = {"commons", "dummy", "__pycache__"}

BEGIN = (
    "<!-- BEGIN GENERATED CATALOG "
    "(tooling/gen_model_catalog.py — do not edit by hand) -->"
)
END = "<!-- END GENERATED CATALOG -->"
_BLOCK_RE = re.compile(re.escape(BEGIN) + r".*?" + re.escape(END), re.DOTALL)


def discover_models() -> list[str]:
    """Deployable model directory names, sorted (matches ``docs/gen_pages.py``)."""
    return sorted(
        p.name
        for p in MODELS_DIR.iterdir()
        if p.is_dir() and p.name not in SKIP and (p / "config.py").exists()
    )


def _family(name: str) -> ModelFamily:
    """Import a model's ``MODEL_FAMILY`` (auth-free — no Modal token needed)."""
    fam: ModelFamily = importlib.import_module(f"models.{name}.config").MODEL_FAMILY
    return fam


def _gpu_label(spec: ModalResourceSpec) -> str:
    """Human-readable accelerator for a variant (``"CPU"`` when none)."""
    gpu = spec.gpu
    if gpu is None:
        return "CPU"
    label = str(gpu.value).upper()
    count = spec.gpu_count
    if count and count > 1:
        return f"{label} ×{count}"
    return label


def _actions(fam: ModelFamily) -> str:
    """Family actions as sorted, code-spanned verbs (e.g. ``` `encode`, `predict` ```)."""
    return ", ".join(
        f"`{name}`" for name in sorted(str(a.name) for a in fam.action_schemas)
    )


def _variant_rows() -> list[str]:
    """One markdown table row per deployable variant, deterministically ordered.

    Models are ordered alphabetically by directory name; a model's variants keep
    their natural (config-declared) order, which is itself deterministic.
    """
    rows: list[str] = []
    for name in discover_models():
        fam = _family(name)
        actions = _actions(fam)
        base = fam.base_model_slug
        for v in fam.resolved_variants:
            rows.append(
                f"| [{v.public_display_name}]({name}/) "
                f"| `{base}` "
                f"| `{v.public_endpoint_slug}` "
                f"| `{v.modal_app_name}` "
                f"| {actions} "
                f"| {_gpu_label(v.modal_resource_spec)} |"
            )
    return rows


def build_catalog() -> str:
    """Render the catalog body (heading + intro + table) that lives in the fences."""
    models = discover_models()
    rows = _variant_rows()
    intro = (
        f"**{len(models)} models · {len(rows)} deployable variants.** Each row is one "
        "variant — everything you need to call it. When `bh serve` is running, invoke "
        "an action with `POST /api/v1/{endpoint-slug}/{action}`; to call the Modal "
        'class directly, use `modal.Cls.from_name("{modal-app}", ...)`. The **Actions** '
        "column lists the closed-set verbs the variant's family supports."
    )
    lines = [
        "## Models",
        "",
        intro,
        "",
        "| Model | Base slug | Endpoint slug | Modal app | Actions | GPU |",
        "|-------|-----------|---------------|-----------|---------|-----|",
        *rows,
    ]
    return "\n".join(lines)


def _block(body: str) -> str:
    return f"{BEGIN}\n{body}\n{END}"


def render_readme(current: str, body: str) -> str:
    """Return ``current`` with the fenced catalog replaced by ``body``.

    Only the region between the fences changes; all surrounding prose is
    preserved byte-for-byte. Raises if the fences are absent.
    """
    if not _BLOCK_RE.search(current):
        raise SystemExit(
            f"{README} is missing the generated-catalog fences.\n"
            f"Add these markers around the model table:\n  {BEGIN}\n  {END}"
        )
    return _BLOCK_RE.sub(lambda _m: _block(body), current)


def extract_block(text: str) -> str | None:
    """Return the catalog body currently between the fences (``None`` if absent)."""
    match = _BLOCK_RE.search(text)
    if not match:
        return None
    inner = match.group(0)[len(BEGIN) : -len(END)]
    return inner.strip("\n")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="fail (non-zero) if the README catalog is stale; do not write",
    )
    args = parser.parse_args(argv)

    body = build_catalog()
    current = README.read_text(encoding="utf-8")
    updated = render_readme(current, body)
    rel = README.relative_to(REPO)

    if args.check:
        if updated != current:
            print(
                f"✗ {rel} catalog is stale — "
                "run `python -m tooling.gen_model_catalog`"
            )
            return 1
        print(f"✓ {rel} catalog is up to date")
        return 0

    if updated != current:
        README.write_text(updated, encoding="utf-8")
        print(f"✓ wrote catalog to {rel}")
    else:
        print(f"✓ {rel} already up to date")
    return 0


if __name__ == "__main__":
    sys.exit(main())
