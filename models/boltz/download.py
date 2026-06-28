"""Download module for Boltz model weights (R2 cache first, HuggingFace fallback)."""

from pathlib import Path
from typing import Optional

from models.boltz.schema import BoltzModelParams, BoltzModelVersion
from models.commons.core.logging import get_logger
from models.commons.storage.download_helpers import (
    extract_model_variant,
    r2_then_urls,
)
from models.commons.storage.downloads import get_model_dir_util

logger = get_logger(__name__)

# Upstream weight sources. Boltz's own CLI normally self-downloads these exact
# files into its ``--cache`` dir from the ``boltz-community`` HuggingFace repos;
# we fetch them directly (flat) so the layout matches what app.py expects
# (``--cache <model_dir>`` + ``<model_dir>/mols.tar``) and so ``mols.tar`` stays
# a single archive (extracted to a Modal volume at runtime, not into the cache).
_BOLTZ1_BASE = "https://huggingface.co/boltz-community/boltz-1/resolve/main"
_BOLTZ2_BASE = "https://huggingface.co/boltz-community/boltz-2/resolve/main"

BOLTZ_SOURCE_URLS = {
    BoltzModelVersion.BOLTZ1: {
        "boltz1_conf.ckpt": f"{_BOLTZ1_BASE}/boltz1_conf.ckpt",
        "ccd.pkl": f"{_BOLTZ1_BASE}/ccd.pkl",
    },
    BoltzModelVersion.BOLTZ2: {
        "boltz2_conf.ckpt": f"{_BOLTZ2_BASE}/boltz2_conf.ckpt",
        "boltz2_aff.ckpt": f"{_BOLTZ2_BASE}/boltz2_aff.ckpt",
        "mols.tar": f"{_BOLTZ2_BASE}/mols.tar",
    },
}


def get_model_dir(model_version: str) -> Path:
    """Get model directory for the specified Boltz variant.

    This returns the same path structure as used in app.py.
    """
    return get_model_dir_util(
        base_model_slug=BoltzModelParams.base_model_slug,
        params_version=BoltzModelParams.params_version,
        model_variant=model_version,
    )


def download_model_assets(
    base_model_slug: str,
    params_version: str,
    variant_config: Optional[dict] = None,
    sub_path: Optional[str] = None,
) -> Path:
    """Download Boltz model assets from R2 storage.

    Uses the standard R2 download pattern recommended for models that
    only need R2 storage without fallback mechanisms.

    Args:
        base_model_slug: The base model identifier (e.g., "boltz")
        params_version: Version of the model parameters (e.g., "v1")
        variant_config: Dictionary containing MODEL_VERSION
        sub_path: Optional subdirectory path

    Returns:
        Path to the downloaded model directory

    Note:
        The mols.tar file for boltz2 is downloaded but NOT extracted here.
        Extraction is handled by app.py during container setup to ensure
        proper volume mounting and avoid duplication/conflicts.
    """
    # Extract MODEL_VERSION from variant_config
    model_version = extract_model_variant(variant_config, "MODEL_VERSION")

    logger.info("Downloading Boltz %s assets...", model_version)

    if model_version not in BOLTZ_SOURCE_URLS:
        raise ValueError(f"Unknown Boltz model version: {model_version}")

    urls = BOLTZ_SOURCE_URLS[model_version]
    expected_files = list(urls.keys())

    # R2 cache first; on a miss fetch the exact files from the boltz-community
    # HuggingFace repos and cache them back to R2 in the same flat layout.
    result = r2_then_urls(
        base_model_slug=base_model_slug,
        params_version=params_version,
        model_variant=model_version,
        sub_path=sub_path,
        urls=urls,
        required_files=expected_files,
    )

    if not result.success:
        raise RuntimeError(
            f"Failed to download Boltz {model_version} model assets: {result.error_message}"
        )

    logger.info("Downloaded %s files using acquisition system", result.files_downloaded)
    return result.actual_model_path or result.target_dir
