"""Download module for Boltz model weights from R2 storage."""

from pathlib import Path
from typing import Optional

from models.boltz.schema import BoltzModelParams, BoltzModelVersion
from models.commons.storage.download_helpers import (
    extract_model_variant,
    standard_r2_download,
)
from models.commons.storage.downloads import get_model_dir_util


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

    print(f"📥 Downloading Boltz {model_version} assets...")

    # Get expected files for validation
    if model_version == BoltzModelVersion.BOLTZ1:
        expected_files = ["boltz1_conf.ckpt", "ccd.pkl"]
    elif model_version == BoltzModelVersion.BOLTZ2:
        expected_files = ["boltz2_conf.ckpt", "boltz2_aff.ckpt", "mols.tar"]
    else:
        raise ValueError(f"Unknown Boltz model version: {model_version}")

    # Use standard R2 download helper (recommended for R2-only patterns)
    result = standard_r2_download(
        base_model_slug=base_model_slug,
        params_version=params_version,
        model_variant=model_version,
        sub_path=sub_path,
        required_files=expected_files,
    )

    if not result.success:
        raise RuntimeError(
            f"Failed to download Boltz {model_version} model assets: {result.error_message}"
        )

    print(f"✅ Downloaded {result.files_downloaded} files using acquisition system")
    return result.actual_model_path or result.target_dir
