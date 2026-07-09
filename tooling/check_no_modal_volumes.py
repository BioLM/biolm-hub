"""Scope guard: no model may mount a Modal Volume / NFS / cloud-bucket mount.

biolm-hub OSS models fetch **bounded** weights via ``download.py``'s ``r2_then_*``
wrappers (R2-cached) and operate on **caller-provided** request inputs. Persistent
Modal Volumes, network filesystems, cloud-bucket mounts, and server-side reference
databases (UniRef/BFD/MGnify/…) are deliberately out of scope — that volume
lifecycle, multi-TB data hosting, and per-caller cost attribution is intentionally
omitted from this catalog (see ``CONTRIBUTING.md`` → "Scope — bounded assets only").

Enforced in CI by ``tooling/test_no_modal_volumes.py``, and a handy gate while
authoring a model:

    python tooling/check_no_modal_volumes.py

It scans every model's Python for the Modal persistent-storage APIs. If a model
legitimately needs one, it belongs in the internal pipeline, not this catalog —
alignment-dependent models take the MSA as an ``msa``/``alignment`` request input.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
MODELS_DIR = REPO / "models"
SKIP = {"commons", "__pycache__"}

# Modal persistent-storage / mounted-filesystem APIs that put a model out of scope.
FORBIDDEN = (
    "modal.Volume",
    "Volume.from_name",
    "NetworkFileSystem",
    "CloudBucketMount",
)
_PATTERN = re.compile("|".join(re.escape(tok) for tok in FORBIDDEN))


def _model_dirs() -> list[Path]:
    return sorted(p for p in MODELS_DIR.iterdir() if p.is_dir() and p.name not in SKIP)


def scan() -> list[str]:
    """Return a list of violation strings (empty == clean)."""
    violations: list[str] = []
    for model_dir in _model_dirs():
        for py in sorted(model_dir.rglob("*.py")):
            if "__pycache__" in py.parts:
                continue
            lines = py.read_text(encoding="utf-8").splitlines()
            for lineno, line in enumerate(lines, start=1):
                match = _PATTERN.search(line)
                if match:
                    rel = py.relative_to(REPO)
                    violations.append(f"{rel}:{lineno}: uses {match.group(0)!r}")
    return violations


def main() -> int:
    violations = scan()
    if violations:
        print(f"✗ {len(violations)} out-of-scope Modal-storage usage(s):\n")
        for v in violations:
            print(f"  - {v}")
        print(
            "\nbiolm-hub models may not mount Modal Volumes / network filesystems /\n"
            "cloud-bucket mounts, or host a server-side reference database. Fetch\n"
            "bounded weights via download.py's r2_then_* wrappers and take large\n"
            'inputs (e.g. MSAs) as request fields. See CONTRIBUTING.md → "Scope —\n'
            'bounded assets only".'
        )
        return 1

    print(
        f"✓ scope OK: no Modal Volumes / NFS / bucket mounts "
        f"({len(_model_dirs())} models)"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
