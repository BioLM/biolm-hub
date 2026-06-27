from pathlib import Path
from typing import Optional

from models.commons.storage.acquisition import (
    AcquisitionConfig,
    AcquisitionStrategy,
    CacheConfig,
    CustomSourceConfig,
    R2OnlyConfig,
)
from models.commons.storage.download_helpers import (
    download_with_fallback,
    extract_model_variant,
)
from models.commons.storage.downloads import download_archive, get_model_dir_util
from models.tempro.config import TEMPRO_GIT_COMMIT, TEMPRO_ZIP_URL, TemproESM2Sizes
from models.tempro.schema import TemproParams

# Mapping of model variants to their corresponding Keras files within the zip
KERAS_MODEL_MAPPING = {
    TemproESM2Sizes.SIZE_650M: "ESM_650M.keras",
    TemproESM2Sizes.SIZE_3B: "ESM_3B.keras",
    # TemproESM2Sizes.SIZE_15B: "ESM_15B.keras",
}

# Path within the zip file where models are stored
ZIP_MODEL_PATH = "user - Copy/saved_ANNmodels_1500epoch/"


def get_model_dir(esm2_size: str):

    return get_model_dir_util(
        base_model_slug=TemproParams.base_model_slug,
        params_version=TemproParams.params_version,
        model_variant=esm2_size,
    )


def _create_r2_config(
    base_model_slug: str,
    params_version: str,
    model_variant: str,
    sub_path: Optional[str],
    target_dir: Path,
) -> AcquisitionConfig:
    """
    Create acquisition config for R2 downloads.

    This is the primary download strategy that tries to fetch weights from R2 cache.
    """
    return AcquisitionConfig(
        strategy=AcquisitionStrategy.R2_ONLY,
        target_dir=target_dir,
        cache_config=CacheConfig(
            enable_r2_cache=True,
        ),
        r2_config=R2OnlyConfig(
            base_model_slug=base_model_slug,
            params_version=params_version,
            model_variant=model_variant,
            sub_path=sub_path,
        ),
    )


def _download_tempro_archive(target_dir: Path, **_kwargs) -> dict:
    """
    Download TEMPRO user.zip to target directory.

    This is the acquisition function for CustomSourceConfig.
    Downloads the entire user.zip file which contains all model variants.

    Args:
        target_dir: Directory where the zip should be downloaded
        **_kwargs: Additional arguments (unused, but kept for compatibility)

    Returns:
        Metadata dictionary with download information
    """
    zip_path = target_dir / "user.zip"

    print(
        f"📥 Downloading TEMPRO user.zip from GitHub (commit: {TEMPRO_GIT_COMMIT[:8]})..."
    )

    # Use the shared download_archive helper
    metadata = download_archive(TEMPRO_ZIP_URL, zip_path)
    metadata["source"] = "github_zip"
    return metadata


def _extract_keras_model(target_dir: Path, *, model_variant: str) -> None:
    """
    Extract specific Keras model from zip and cleanup.

    This is the post-processing function for CustomSourceConfig.
    Extracts the appropriate .keras file based on the model variant.

    Args:
        target_dir: Directory containing the downloaded zip
        model_variant: The model variant (e.g., "650m", "3b")
    """
    import zipfile

    zip_path = target_dir / "user.zip"

    if model_variant not in KERAS_MODEL_MAPPING:
        raise ValueError(f"Unknown model variant: {model_variant}")

    keras_filename = KERAS_MODEL_MAPPING[model_variant]
    zip_internal_path = ZIP_MODEL_PATH + keras_filename

    # Create saved_models directory
    saved_models_dir = target_dir / "saved_models"
    saved_models_dir.mkdir(parents=True, exist_ok=True)

    target_file = saved_models_dir / keras_filename

    # Skip if file already exists
    if target_file.exists():
        print(f"✅ Model file already exists: {target_file}")
        if zip_path.exists():
            zip_path.unlink()  # Clean up zip
        return

    print(f"📦 Extracting {keras_filename} from zip archive...")

    # For TEMPRO, we need specific file extraction rather than subtree
    # So we'll handle it directly here instead of using extract_archive_subtree
    try:
        with zipfile.ZipFile(zip_path, "r") as zip_ref:
            # Check if file exists in zip
            if zip_internal_path not in zip_ref.namelist():
                raise FileNotFoundError(
                    f"File {zip_internal_path} not found in zip archive"
                )

            # Extract the model file
            with zip_ref.open(zip_internal_path) as source:
                with open(target_file, "wb") as target:
                    target.write(source.read())

        print(f"✅ Successfully extracted {keras_filename} to {saved_models_dir}")

    finally:
        # Always clean up the zip file after extraction
        if zip_path.exists():
            zip_path.unlink()
            print("🧹 Cleaned up temporary zip file")


def _create_custom_fallback_config(
    model_variant: str,
    target_dir: Path,
) -> AcquisitionConfig:
    """
    Create a custom acquisition config for downloading and extracting from GitHub zip.

    Uses CustomSourceConfig to handle the zip download and extraction process.

    Args:
        model_variant: The model variant (650m, 3b, or 15b)
        target_dir: Directory where the model should be saved

    Returns:
        AcquisitionConfig with custom strategy for zip handling
    """
    custom_config = CustomSourceConfig(
        acquisition_fn=_download_tempro_archive,
        acquisition_kwargs={},  # No longer needed
        post_process_fn=_extract_keras_model,
        post_process_kwargs={"model_variant": model_variant},  # Pass via kwargs
        name="tempro_github_zip",
        description=f"Download and extract TEMPRO {model_variant} model from GitHub zip",
    )

    return AcquisitionConfig(
        strategy=AcquisitionStrategy.CUSTOM,
        target_dir=target_dir,
        custom_config=custom_config,
        cache_config=CacheConfig(
            enable_r2_cache=True,  # Will cache the extracted files to R2
        ),
    )


def download_model_assets(
    base_model_slug: str,
    params_version: str,
    variant_config: Optional[dict] = None,
    sub_path: Optional[str] = None,
):
    """
    Download TEMPRO model assets with R2 primary and GitHub zip fallback.

    This function implements a two-stage download strategy:
    1. Primary: Try to fetch from R2 cache (fast, if previously cached)
    2. Fallback: Download user.zip from GitHub and extract the specific model

    The fallback uses CustomSourceConfig to cleanly handle zip download and extraction,
    with automatic R2 caching of the extracted files for future use.

    Directory structure after download:
    - model-store/tempro/v1/{esm2_size}/saved_models/
        - ESM_650M.keras (for 650m variant)
        - ESM_3B.keras (for 3b variant)
        - ESM_15B.keras (for 15b variant)

    Args:
        base_model_slug: Base model identifier ("tempro")
        params_version: Model version ("v1")
        variant_config: Dict with ESM2_SIZE key specifying variant
        sub_path: Optional subdirectory path

    Returns:
        Path to downloaded model assets directory

    Raises:
        RuntimeError: If both R2 and GitHub download strategies fail
    """
    # Extract ESM2_SIZE from variant_config
    model_variant = extract_model_variant(variant_config, "ESM2_SIZE")

    print(f"🔧 TEMPRO: Downloading {model_variant} model variant")

    # Get target directory
    model_dir = get_model_dir_util(
        base_model_slug=base_model_slug,
        params_version=params_version,
        model_variant=model_variant,
        sub_path=sub_path,
    )

    print(f"📂 Target directory: {model_dir}")
    if sub_path:
        print(f"📁 Sub-path: {sub_path}")

    # ---- Stage 1: Try R2 cache (fast path) ----
    print("🔍 Checking R2 cache...")

    primary_config = _create_r2_config(
        base_model_slug=base_model_slug,
        params_version=params_version,
        model_variant=model_variant,
        sub_path=sub_path,
        target_dir=model_dir,
    )

    # ---- Stage 2: Fallback to GitHub zip with custom strategy ----
    fallback_config = _create_custom_fallback_config(
        model_variant=model_variant,
        target_dir=model_dir,
    )

    # Use the standard download_with_fallback which handles both strategies
    result = download_with_fallback(
        primary_config=primary_config,
        fallback_config=fallback_config,
    )

    if not result.success:
        raise RuntimeError(
            f"Failed to download TEMPRO model for variant {model_variant}: "
            f"{result.error_message}"
        )

    if result.cache_hit:
        print("✅ Downloaded from R2 cache")
    else:
        print("✅ Downloaded and extracted from GitHub (files cached to R2)")

    return result.actual_model_path or result.target_dir
