from pathlib import Path
from typing import Optional

from models.commons.core.logging import get_logger
from models.commons.storage.download_helpers import r2_then_hf
from models.commons.storage.downloads import get_model_dir_util
from models.zymctrl.config import HF_REPO_ID, HF_REVISION
from models.zymctrl.schema import ZymCTRLParams

logger = get_logger(__name__)


def get_model_dir() -> Path:
    """Get the model directory path. Used by app.py for loading."""
    return get_model_dir_util(
        base_model_slug=ZymCTRLParams.base_model_slug,
        weights_version=ZymCTRLParams.weights_version,
    )


def download_model_assets(
    base_model_slug: str,
    weights_version: str,
    variant_config: Optional[dict] = None,
    sub_path: Optional[str] = None,
) -> Path:
    """Download ZymCTRL model assets."""
    logger.info("Downloading ZymCTRL")

    result = r2_then_hf(
        base_model_slug=base_model_slug,
        weights_version=weights_version,
        sub_path=sub_path,
        hf_repo_id=HF_REPO_ID,
        hf_revision=HF_REVISION,
        required_files=["config.json", "pytorch_model.bin"],
    )

    if not result.success:
        raise RuntimeError(f"Failed to acquire ZymCTRL model: {result.error_message}")

    snapshot_path = result.actual_model_path or result.target_dir

    if result.cache_hit:
        logger.info("ZymCTRL restored from R2 cache")
    else:
        logger.info("ZymCTRL downloaded: %s files", result.files_downloaded)

    logger.info("Using HF snapshot path: %s", snapshot_path)
    return snapshot_path
