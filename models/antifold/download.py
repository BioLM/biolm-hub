from pathlib import Path
from typing import Any, Optional

from models.antifold.schema import AntiFoldParams
from models.commons.core.logging import get_logger
from models.commons.storage import r2_then_urls
from models.commons.storage.downloads import get_model_dir_util

logger = get_logger(__name__)

# AntiFold publishes a single inverse-folding checkpoint from the Oxford OPIG
# group. The runtime loader reads it flat at ``<model_dir>/model.pt``
# (see app.py: ``load_model_modified(checkpoint_path=model_dir / "model.pt")``).
ANTIFOLD_CHECKPOINT_FILENAME = "model.pt"
ANTIFOLD_WEIGHTS_URL = (
    "https://opig.stats.ox.ac.uk/data/downloads/AntiFold/models/model.pt"
)


def get_model_dir() -> Path:

    return get_model_dir_util(
        base_model_slug=AntiFoldParams.base_model_slug,
        weights_version=AntiFoldParams.weights_version,
    )


def download_model_assets(
    base_model_slug: str,
    weights_version: str,
    variant_config: Optional[dict[str, Any]] = None,
    sub_path: Optional[str] = None,
) -> Path:
    """Download AntiFold weights: R2 cache first, else the OPIG source URL.

    On an R2 miss the checkpoint is fetched from OPIG and cached back to R2 in
    the same container path, so ``git clone -> deploy`` self-populates R2.
    """
    result = r2_then_urls(
        base_model_slug=base_model_slug,
        weights_version=weights_version,
        sub_path=sub_path,
        urls={ANTIFOLD_CHECKPOINT_FILENAME: ANTIFOLD_WEIGHTS_URL},
        required_files=[ANTIFOLD_CHECKPOINT_FILENAME],
    )

    if not result.success:
        raise RuntimeError(f"Model download failed: {result.error_message}")

    if result.cache_hit:
        logger.info("AntiFold restored from R2 cache")
    else:
        logger.info("AntiFold downloaded: %s files", result.files_downloaded)

    return result.actual_model_path or result.target_dir
