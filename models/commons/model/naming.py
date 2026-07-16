"""Canonical mapping between a model's public slug and its on-disk / import forms.

The **public identifier is the hyphenated ``base_model_slug``** (e.g. ``dna-chisel``, ``esm-if1``).
Python's import rules force the on-disk package directory and module path to use underscores
(``models/dna_chisel/``, ``models.dna_chisel``). This module is the **single place** that bridges the
two, so callers never hand-roll ``.replace("-", "_")`` at scattered boundaries.

Direction matters:

- **slug → dir / module is deterministic and safe:** no ``base_model_slug`` in the catalog contains an
  underscore, so ``-`` → ``_`` is unambiguous.
- **dir → slug is ambiguous in principle** (``_`` → ``-`` could be wrong if a slug ever legitimately
  contained ``_``), so :func:`dirname_to_slug` is a guarded convenience — never build a public slug
  from a directory name on a hot path; resolve through the config/registry instead.

Accepting *either* form is intentional: ``slug_to_dirname`` is idempotent on an already-underscored
directory name, so ``model_dir("dna-chisel")`` and ``model_dir("dna_chisel")`` both resolve.
"""

from importlib.resources import files
from pathlib import Path

# The repository ``models/`` directory — the ONE canonical definition; other modules import it from
# here rather than re-deriving their own. Resolved from the importable ``models`` package instead of
# a fragile ``Path(__file__).parents[N]`` walk, so there is no hard-coded directory depth to break if
# a file moves, and it resolves the same in the repo and inside a model container (where ``models``
# is on the path).
MODELS_DIR = Path(str(files("models")))

# The repository root (the parent of ``models/``). Derived from ``MODELS_DIR`` so there is still only
# one path derivation — modules that need the repo root import this instead of walking ``__file__``.
REPO_ROOT = MODELS_DIR.parent


def slug_to_dirname(slug: str) -> str:
    """Map a model slug to its package directory name (``dna-chisel`` → ``dna_chisel``).

    Idempotent on a directory name already, so callers may pass either form.
    """
    return slug.replace("-", "_")


def slug_to_module(slug: str) -> str:
    """Map a model slug to its importable module prefix (``dna-chisel`` → ``models.dna_chisel``)."""
    return f"models.{slug_to_dirname(slug)}"


def dirname_to_slug(dirname: str) -> str:
    """Map a package directory name back to its public slug (``dna_chisel`` → ``dna-chisel``).

    Guarded convenience: valid only because no ``base_model_slug`` contains an underscore. Prefer the
    config/registry as the source of truth rather than reconstructing a slug from a directory name.
    """
    return dirname.replace("_", "-")


def model_dir(slug: str) -> Path:
    """Absolute path to a model's package directory, from its slug (or directory name)."""
    return MODELS_DIR / slug_to_dirname(slug)


def model_app_path(slug: str) -> Path:
    """Absolute path to a model's ``app.py``."""
    return model_dir(slug) / "app.py"


def model_config_path(slug: str) -> Path:
    """Absolute path to a model's ``config.py``."""
    return model_dir(slug) / "config.py"
