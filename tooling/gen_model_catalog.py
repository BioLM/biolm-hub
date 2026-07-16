"""Generate the GitHub-viewable model + variant catalog and keep model counts in sync.

Unlike the mkdocs site (whose per-model pages are rendered at build time), the repo's
``models/README.md`` is browsed directly on GitHub, so its catalog table is committed. This module
regenerates that table from every model's ``config.py`` ``MODEL_FAMILY`` — and, from the same two
numbers (deployable variants + model families), keeps the model counts in ``README.md`` (the shields
badge + the one-line pitch) and ``docs/media/architecture.md`` in sync. Everything is idempotent
(running it twice is a no-op) and Modal-free (only imports model configs, like ``docs/gen_pages.py``),
so it needs no credentials.

    python -m tooling.gen_model_catalog            # rewrite the catalog + counts
    python -m tooling.gen_model_catalog --check     # fail (non-zero) if anything is stale

Counting convention (used everywhere): lead with the **deployable variants** (the flattened
"what's callable" total — the bigger number) and call the unique base models **model families**.
``tooling/test_model_catalog.py`` enforces freshness in CI.
"""

from __future__ import annotations

import argparse
import importlib
import re
import sys
from pathlib import Path
from urllib.parse import quote

from models.commons.model.config import ModelFamily
from models.commons.model.schema import ModalResourceSpec

REPO = Path(__file__).resolve().parent.parent
MODELS_DIR = REPO / "models"
README = MODELS_DIR / "README.md"
MAIN_README = REPO / "README.md"
ARCHITECTURE = REPO / "docs" / "media" / "architecture.md"

# Mirror ``docs/gen_pages.py`` discovery: ``dummy`` is the unresolved template
# and ``commons`` is the shared framework — neither is a deployable model.
SKIP = {"commons", "dummy", "__pycache__"}

BEGIN = (
    "<!-- BEGIN GENERATED CATALOG "
    "(tooling/gen_model_catalog.py — do not edit by hand) -->"
)
END = "<!-- END GENERATED CATALOG -->"
_BLOCK_RE = re.compile(re.escape(BEGIN) + r".*?" + re.escape(END), re.DOTALL)

# Count spots this tool owns outside the fenced catalog. Each regex matches both the old and the
# newly-generated form so the rewrite is idempotent.
_BADGE_COLOR = "6d28d9"
_BADGE_RE = re.compile(
    r'<img alt="[^"]*" src="https://img\.shields\.io/badge/models-[^"]*\.svg">'
)
_PITCH_RE = re.compile(r"\*\*\d[^*]*?\btoday\*\*")
_ARCH_RE = re.compile(r"any of \d+ (?:deployable )?models")


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


def counts() -> tuple[int, int]:
    """Return ``(deployable_variants, model_families)`` — the two numbers everything renders from."""
    return len(_variant_rows()), len(discover_models())


def build_catalog() -> str:
    """Render the catalog body (heading + intro + table) that lives in the fences."""
    variants, families = counts()
    intro = (
        f"**{variants} deployable models across {families} model families.** Each row is one "
        "deployable variant — everything you need to call it. When `bh serve` is running, invoke "
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
        *_variant_rows(),
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


def _badge(variants: int, families: int) -> str:
    """The shields.io model-count badge — variants first, families second."""
    message = f"{variants} deployable · {families} families"
    src = f"https://img.shields.io/badge/models-{quote(message, safe='')}-{_BADGE_COLOR}.svg"
    alt = f"{variants} deployable models across {families} model families"
    return f'<img alt="{alt}" src="{src}">'


def render_main_readme(current: str, variants: int, families: int) -> str:
    """Sync the model-count badge and the one-line pitch in the top-level ``README.md``."""
    badge = _badge(variants, families)
    pitch = f"**{variants} deployable models across {families} families today**"
    current = _BADGE_RE.sub(lambda _m: badge, current)
    current = _PITCH_RE.sub(lambda _m: pitch, current)
    return current


def render_architecture(current: str, variants: int) -> str:
    """Sync the model count in the architecture diagram."""
    return _ARCH_RE.sub(lambda _m: f"any of {variants} deployable models", current)


def _targets() -> list[tuple[Path, str, str]]:
    """Every (path, current, updated) this tool owns — the single source for counts."""
    variants, families = counts()
    readme_cur = README.read_text(encoding="utf-8")
    main_cur = MAIN_README.read_text(encoding="utf-8")
    arch_cur = ARCHITECTURE.read_text(encoding="utf-8")
    return [
        (README, readme_cur, render_readme(readme_cur, build_catalog())),
        (MAIN_README, main_cur, render_main_readme(main_cur, variants, families)),
        (ARCHITECTURE, arch_cur, render_architecture(arch_cur, variants)),
    ]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="fail (non-zero) if the catalog or any model count is stale; do not write",
    )
    args = parser.parse_args(argv)

    stale = [(p, cur, new) for p, cur, new in _targets() if cur != new]

    if args.check:
        if stale:
            for path, _cur, _new in stale:
                print(
                    f"✗ {path.relative_to(REPO)} is stale — "
                    "run `python -m tooling.gen_model_catalog`"
                )
            return 1
        print("✓ model catalog + counts are up to date")
        return 0

    if not stale:
        print("✓ model catalog + counts already up to date")
        return 0
    for path, _cur, new in stale:
        path.write_text(new, encoding="utf-8")
        print(f"✓ wrote {path.relative_to(REPO)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
