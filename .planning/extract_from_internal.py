#!/usr/bin/env python3
"""TEMP porting tool (W2) — extract the in-scope subset from the internal repo.

Lives in .planning/ (deleted at launch) because it references the internal repo path.

Usage:
    python .planning/extract_from_internal.py            # full extraction
    python .planning/extract_from_internal.py --model esm2   # re-extract one model

Copies cli/, gateway/, and models/ (commons + included models) from the read-only
`main` worktree of the internal repo into this repo. Decoupling (billing/auth/
analytics), secret-scrubbing, and simplification happen in later workstreams
(W3a/W8/W-acq/W-sec) — NOT here. This step is a faithful snapshot.
"""
from __future__ import annotations

import argparse
import shutil
from pathlib import Path

SRC = Path("/Users/qamar/dev/biolm-modal-worktrees/oss-readonly-main")
DST = Path("/Users/qamar/dev/biolm-models")

# Excluded per .planning/02_MODEL_INCLUSION_MATRIX.md
# (NIM / non-commercial / proprietary / revocable-license / not-permissive).
EXCLUDED_MODELS = {
    "ablef", "af2_nim", "biolmtox2", "camsol", "diamond", "esm3", "gemme",
    "msa_search_nim", "nt", "poet", "pro4s", "proteina_complexa", "saprot", "soluprot",
}
NON_MODEL_DIRS = {"commons", "scripts"}
IGNORE = shutil.ignore_patterns(
    "__pycache__", "*.pyc", "*.pyo", ".git", ".pytest_cache",
    ".ruff_cache", ".mypy_cache", "*.egg-info",
)


def copytree(src: Path, dst: Path) -> None:
    shutil.copytree(src, dst, dirs_exist_ok=True, ignore=IGNORE)


def extract_model(name: str) -> None:
    s = SRC / "models" / name
    if not s.is_dir():
        raise SystemExit(f"model dir not found: {s}")
    copytree(s, DST / "models" / name)
    print(f"  models/{name}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", help="re-extract a single model and exit")
    args = ap.parse_args()

    (DST / "models").mkdir(exist_ok=True)

    if args.model:
        extract_model(args.model)
        return

    # Framework + package marker
    copytree(SRC / "models" / "commons", DST / "models" / "commons")
    print("  models/commons")
    shutil.copy2(SRC / "models" / "__init__.py", DST / "models" / "__init__.py")

    # Included models
    included = sorted(
        d.name
        for d in (SRC / "models").iterdir()
        if d.is_dir() and d.name not in EXCLUDED_MODELS | NON_MODEL_DIRS
    )
    for name in included:
        extract_model(name)

    # CLI + gateway (wholesale; auth/billing/analytics stripped later in W3a/W8)
    copytree(SRC / "cli", DST / "cli")
    print("  cli/")
    copytree(SRC / "gateway", DST / "gateway")
    print("  gateway/")

    print(f"\nExtracted {len(included)} models + commons + cli + gateway.")
    print(f"Excluded {len(EXCLUDED_MODELS)} models: {', '.join(sorted(EXCLUDED_MODELS))}")


if __name__ == "__main__":
    main()
