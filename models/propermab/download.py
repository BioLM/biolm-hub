"""Download utilities for ProperMAB model weights and data files.

ProperMAB uses ABodyBuilder2 for antibody structure prediction, which requires
pre-trained EGNN model weights. It also requires the amber.siz atomic radii file
for NanoShaper/APBS electrostatics calculations.

This module handles downloading and caching with R2-first strategy and URL fallback:
- ABodyBuilder2 weights (from Zenodo)
- amber.siz atomic radii file (from biskit repository)
"""

from pathlib import Path
from typing import Optional

from models.commons.core.logging import get_logger
from models.commons.storage.acquisition import (
    AcquisitionConfig,
    AcquisitionStrategy,
    CacheConfig,
    R2OnlyConfig,
)
from models.commons.storage.download_helpers import r2_then_urls
from models.commons.storage.downloads import get_model_dir_util
from models.propermab.schema import ProperMABParams

logger = get_logger(__name__)

# ABodyBuilder2 weights from Zenodo (same as immunebuilder/abodybuilder2)
# These are EGNN model checkpoints for antibody Fv structure prediction
ABODYBUILDER2_URLS = {
    "antibody_model_1": "https://zenodo.org/record/7258553/files/antibody_model_1?download=1",
    "antibody_model_2": "https://zenodo.org/record/7258553/files/antibody_model_2?download=1",
    "antibody_model_3": "https://zenodo.org/record/7258553/files/antibody_model_3?download=1",
    "antibody_model_4": "https://zenodo.org/record/7258553/files/antibody_model_4?download=1",
}

# amber.siz atomic radii file for NanoShaper/DelPhi
# Contains AMBER98 force field van der Waals radii derived from TINKER package
# Source: Clemson University DelPhi parameter files
# Scientific reference: AMBER98 force field parameters
# URL: http://compbio.clemson.edu/downloadDir/delphi/parameters.tar.gz
AMBER_SIZ_ARCHIVE_URL = (
    "http://compbio.clemson.edu/downloadDir/delphi/parameters.tar.gz"
)


def get_model_dir() -> Path:
    """Get the directory path for ABodyBuilder2 weights used by ProperMAB.

    Returns:
        Path to the model weights directory
    """
    return get_model_dir_util(
        base_model_slug=ProperMABParams.base_model_slug,
        params_version=ProperMABParams.params_version,
        sub_path="abodybuilder2",  # Stored in sub_path, not model_variant
    )


def get_data_dir() -> Path:
    """Get the directory path for static data files (e.g., amber.siz).

    Returns:
        Path to the data directory
    """
    return get_model_dir_util(
        base_model_slug=ProperMABParams.base_model_slug,
        params_version=ProperMABParams.params_version,
        # No model_variant or sub_path - stored at base level
    )


def download_model_assets(
    base_model_slug: str,
    params_version: str,
    variant_config: Optional[dict] = None,
    sub_path: Optional[str] = None,
) -> Path:
    """Download ABodyBuilder2 model weights with R2 primary and Zenodo fallback."""
    logger.info("ProperMAB: Downloading ABodyBuilder2 weights")

    result = r2_then_urls(
        base_model_slug=base_model_slug,
        params_version=params_version,
        sub_path="abodybuilder2",
        urls=ABODYBUILDER2_URLS,
    )

    if not result.success:
        raise RuntimeError(
            f"Failed to download ABodyBuilder2 models: {result.error_message}"
        )

    if result.cache_hit:
        logger.info("Downloaded from R2 cache")
    else:
        logger.info("Downloaded %s files", result.files_downloaded)

    return result.actual_model_path or result.target_dir


def download_amber_siz() -> Path:
    """Download amber.siz atomic radii file with R2 primary and Clemson fallback.

    The amber.siz file contains AMBER98 force field van der Waals radii,
    used by NanoShaper for molecular surface mesh generation.

    Scientific References:
    - AMBER98 force field parameters (derived from TINKER package)
    - Source: Clemson University DelPhi parameter files
    - URL: http://compbio.clemson.edu/downloadDir/delphi/parameters.tar.gz

    Returns:
        Path to the downloaded amber.siz file

    Raises:
        RuntimeError: If download fails from both R2 and Clemson
    """
    import shutil
    import tarfile
    import tempfile

    import requests

    # Store at base level: /model-store/propermab/v1/amber.siz
    data_dir = get_data_dir()
    amber_siz_path = data_dir / "amber.siz"

    logger.info("ProperMAB: Downloading amber.siz atomic radii file")
    logger.info("Target directory: %s", data_dir)

    # ---- Primary strategy: Check if already cached locally ----
    if amber_siz_path.exists():
        logger.info("amber.siz already exists at: %s", amber_siz_path)
        return amber_siz_path

    # ---- Try R2 cache first ----
    try:
        primary_config = AcquisitionConfig(
            strategy=AcquisitionStrategy.R2_ONLY,
            target_dir=data_dir,
            cache_config=CacheConfig(enable_r2_cache=True),
            r2_config=R2OnlyConfig(
                base_model_slug=ProperMABParams.base_model_slug,
                params_version=ProperMABParams.params_version,
            ),
        )
        from models.commons.storage.acquisition import acquire_model_weights

        result = acquire_model_weights(primary_config)
        if result.success and amber_siz_path.exists():
            logger.info("Downloaded from R2 cache: %s", amber_siz_path)
            return amber_siz_path
    except Exception as e:
        logger.warning("R2 cache miss or error: %s", e)

    # ---- Fallback: Download from Clemson and extract ----
    logger.info("Downloading from Clemson University DelPhi parameters...")
    data_dir.mkdir(parents=True, exist_ok=True)

    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            archive_path = Path(tmpdir) / "parameters.tar.gz"

            # Download the archive
            response = requests.get(AMBER_SIZ_ARCHIVE_URL, timeout=120, stream=True)
            response.raise_for_status()

            with open(archive_path, "wb") as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)

            logger.info("Extracting amber.siz from archive...")

            # Extract amber.siz from the archive
            with tarfile.open(archive_path, "r:gz") as tar:
                # Find and extract only amber.siz
                for member in tar.getmembers():
                    if member.name.endswith("amber.siz"):
                        # Extract to temp location
                        tar.extract(member, tmpdir)
                        extracted_path = Path(tmpdir) / member.name
                        # Copy to final location
                        shutil.copy2(extracted_path, amber_siz_path)
                        break
                else:
                    raise RuntimeError("amber.siz not found in archive")

        logger.info("amber.siz available at: %s", amber_siz_path)

        # ---- Cache to R2 for future use ----
        try:
            from models.commons.storage.r2_utils import R2Utils
            from models.commons.util.config import r2_bucket_name

            r2_prefix = f"model-store/{ProperMABParams.base_model_slug}/{ProperMABParams.params_version}"
            logger.info("Caching to R2 at %s", r2_prefix)
            R2Utils.upload_to_r2_atomic(
                source_dir=data_dir,
                r2_prefix=r2_prefix,
                bucket_name=r2_bucket_name,
                create_manifest=True,
            )
            logger.info("Successfully cached to R2 for future use")
        except Exception as e:
            logger.warning("Failed to cache to R2: %s", e)

        return amber_siz_path

    except Exception as e:
        raise RuntimeError(f"Failed to download amber.siz: {e}") from e
