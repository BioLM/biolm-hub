"""Download module for RosettaFold3 (RF3) model weights.

Based on RosettaCommons/foundry implementation (BSD 3-Clause License).
"""

from pathlib import Path
from typing import Optional

from models.commons.core.logging import get_logger
from models.commons.storage.download_helpers import r2_then_urls
from models.commons.storage.downloads import get_model_dir_util
from models.rf3.schema import RF3Params

logger = get_logger(__name__)

# RF3 checkpoint URLs from IPD
# Multiple versions available - using latest by default
RF3_CHECKPOINT_URLS = {
    "latest": "http://files.ipd.uw.edu/pub/rf3/rf3_foundry_01_24_latest.ckpt",
    "preprint": "http://files.ipd.uw.edu/pub/rf3/rf3_foundry_01_24_preprint.ckpt",
    "benchmark": "http://files.ipd.uw.edu/pub/rf3/rf3_foundry_09_21_preprint.ckpt",
}

RF3_CHECKPOINT_FILENAMES = {
    "latest": "rf3_foundry_01_24_latest.ckpt",
    "preprint": "rf3_foundry_01_24_preprint.ckpt",
    "benchmark": "rf3_foundry_09_21_preprint.ckpt",
}


def get_model_dir() -> Path:
    """Get model directory for RosettaFold3."""
    return get_model_dir_util(
        base_model_slug=RF3Params.base_model_slug,
        weights_version=RF3Params.weights_version,
    )


def download_model_assets(
    base_model_slug: str,
    weights_version: str,
    variant_config: Optional[dict] = None,
    sub_path: Optional[str] = None,
    checkpoint_version: str = "latest",
) -> Path:
    """Download RosettaFold3 checkpoint with R2 caching and IPD URL fallback."""
    if checkpoint_version not in RF3_CHECKPOINT_URLS:
        raise ValueError(
            f"Unknown checkpoint version: {checkpoint_version}. "
            f"Must be one of: {list(RF3_CHECKPOINT_URLS.keys())}"
        )

    checkpoint_filename = RF3_CHECKPOINT_FILENAMES[checkpoint_version]
    checkpoint_url = RF3_CHECKPOINT_URLS[checkpoint_version]

    logger.info("Downloading RosettaFold3 (%s checkpoint)", checkpoint_version)

    result = r2_then_urls(
        base_model_slug=base_model_slug,
        weights_version=weights_version,
        sub_path=sub_path,
        urls={checkpoint_filename: checkpoint_url},
        required_files=[checkpoint_filename],
        verify_ssl=False,  # IPD server uses HTTP
        timeout=1800,
    )

    if not result.success:
        raise RuntimeError(
            f"Failed to download RosettaFold3 model assets: {result.error_message}"
        )

    if result.cache_hit:
        logger.info("RosettaFold3 restored from R2 cache")
    else:
        logger.info("RosettaFold3 downloaded: %s files", result.files_downloaded)

    return result.actual_model_path or result.target_dir
