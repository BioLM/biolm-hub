"""Public storage API for model weight acquisition.

The blessed surface for ``models/<model>/download.py`` is the small set of
declarative, R2-cache-first wrappers re-exported here. Each tries the R2 cache
first (marker-gated) and, on a miss, fetches from the original source and caches
back to R2 in the same container path so ``git clone -> deploy`` self-populates.

Prefer these over importing the lower-level ``acquisition`` engine directly.
"""

from models.commons.storage.acquisition import CustomSourceConfig
from models.commons.storage.download_helpers import (
    download_with_fallback,
    extract_model_variant,
    r2_then_archive,
    r2_then_hf,
    r2_then_library,
    r2_then_urls,
)
from models.commons.storage.downloads import (
    build_hf_snapshot_path,
    get_model_dir_util,
)

__all__ = [
    # R2-cache-first wrappers (the canonical model entry points)
    "r2_then_hf",
    "r2_then_urls",
    "r2_then_library",
    "r2_then_archive",
    "download_with_fallback",
    # Escape hatch + variant helper
    "CustomSourceConfig",
    "extract_model_variant",
    # Path utilities
    "get_model_dir_util",
    "build_hf_snapshot_path",
]
