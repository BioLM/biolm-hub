from pathlib import Path
from typing import Optional

from models.commons.core.logging import get_logger
from models.commons.storage.acquisition import (
    AcquisitionConfig,
    AcquisitionStrategy,
    CacheConfig,
    HfSourceConfig,
    R2OnlyConfig,
    ValidationConfig,
)
from models.commons.storage.download_helpers import (
    download_with_fallback,
    extract_model_variant,
)
from models.commons.storage.downloads import build_hf_snapshot_path, get_model_dir_util
from models.evo2.config import (
    EVO2_FILENAME_MAP,
    EVO2_HF_REPO_MAP,
    EVO2_HF_REVISION_MAP,
)
from models.evo2.schema import Evo2Params

logger = get_logger(__name__)


def get_model_dir(model_variant: str):

    return get_model_dir_util(
        base_model_slug=Evo2Params.base_model_slug,
        weights_version=Evo2Params.weights_version,
        model_variant=model_variant,
    )


def download_model_assets(
    base_model_slug: str,
    weights_version: str,
    variant_config: Optional[dict] = None,
    sub_path: Optional[str] = None,
):
    """
    Download Evo2 model assets with R2 caching and HuggingFace Hub fallback.

    Strategy:
    1. First attempt: Download from R2 cache (fastest)
    2. Fallback: Download from HuggingFace Hub and cache to R2 for future use

    The R2 structure preserves HF's cache directory layout (from original manual upload):
    biolm-hub/models/evo2/v1/{variant}/models--{repo}/snapshots/{hash}/{filename}.pt

    This nested structure comes from how HuggingFace Hub organizes its cache and was
    preserved when the weights were manually uploaded to R2 using get_params.py.

    Note: The complexity in this function exists because evo2 models were manually
    uploaded to R2 preserving HuggingFace's nested cache structure, requiring special
    handling that other models don't need.

    Returns:
        Path to downloaded model directory
    """
    # Extract model variant from variant_config using standardized helper
    model_variant = extract_model_variant(variant_config, "MODEL_VARIANT")

    # Get target model directory
    model_dir = get_model_dir_util(
        base_model_slug=base_model_slug,
        weights_version=weights_version,
        model_variant=model_variant,
        sub_path=sub_path,
    )

    # Cache all HF-related lookups at the start to avoid duplication
    hf_repo_id = EVO2_HF_REPO_MAP.get(model_variant)
    hf_revision = EVO2_HF_REVISION_MAP.get(model_variant, "main")
    expected_filename = EVO2_FILENAME_MAP.get(model_variant)

    logger.info("Evo2: Setting up model assets")
    logger.info("   Target directory: %s", model_dir)
    logger.info("   Model variant: %s", model_variant)

    # Create variant-specific filter to download only requested variant
    def evo2_filter_func(full_key: str) -> bool:
        """Filter to download only files for the specific variant"""
        if not model_variant:
            return True  # Download everything if no variant specified
        # Check if the R2 key contains our variant folder
        return f"/{model_variant}/" in full_key

    # ---- Primary strategy: R2 cache ----
    r2_config = R2OnlyConfig(
        base_model_slug=base_model_slug,
        weights_version=weights_version,
        model_variant=model_variant,
        sub_path=sub_path,
        filter_func=evo2_filter_func,  # Apply variant filtering
    )

    primary_config = AcquisitionConfig(
        strategy=AcquisitionStrategy.R2_ONLY,
        target_dir=model_dir,
        cache_config=CacheConfig(
            enable_r2_cache=False
        ),  # We're reading from R2, not writing
        validation_config=ValidationConfig(required_files=None),  # Files may be nested
        r2_config=r2_config,
    )

    # ---- Fallback strategy: Hugging Face Hub ----
    fallback_config = None
    if hf_repo_id and expected_filename:  # Use cached lookups
        hf_config = HfSourceConfig(
            repo_id=hf_repo_id,
            allow_patterns=[expected_filename],  # Download only the .pt file
        )

        fallback_config = AcquisitionConfig(
            strategy=AcquisitionStrategy.HUGGINGFACE_HUB,
            target_dir=model_dir,
            cache_config=CacheConfig(
                enable_r2_cache=True
            ),  # Cache to R2 for future use
            validation_config=ValidationConfig(required_files=[expected_filename]),
            hf_config=hf_config,
        )

    # ---- Execute download with fallback ----
    # Every deployable variant has an HF repo + filename mapping (see
    # EVO2_HF_REPO_MAP / EVO2_FILENAME_MAP in config.py), so a missing fallback
    # means a variant was enabled without its HF mapping — fail loudly rather
    # than silently attempting an R2-only read that cannot self-populate.
    if not fallback_config:
        raise RuntimeError(
            f"Evo2 variant '{model_variant}' has no HF repo/filename mapping; "
            "add it to EVO2_HF_REPO_MAP and EVO2_FILENAME_MAP in config.py."
        )
    result = download_with_fallback(primary_config, fallback_config)

    # ---- Final validation ----
    if not result.success:
        raise RuntimeError(f"Failed to acquire Evo2 model: {result.error_message}")

    # Build deterministic path from HF details
    actual_path = build_hf_snapshot_path(model_dir, hf_repo_id, hf_revision)
    logger.info("Using deterministic HF snapshot path: %s", actual_path)
    logger.info("Evo2 model ready at %s", actual_path)

    # Verify the expected model file exists
    # Handle the nested HF cache structure from R2
    if expected_filename:  # Use cached lookup
        # First check if file exists directly (new structure)
        direct_file = Path(actual_path) / expected_filename

        # Also check in HF cache structure (existing R2 structure)
        hf_repo_name = (hf_repo_id or "").replace("/", "--")  # Use cached lookup
        nested_pattern = f"models--{hf_repo_name}/snapshots/*/{expected_filename}"
        nested_files = list(Path(actual_path).glob(nested_pattern))

        found_file = None
        if direct_file.exists():
            found_file = direct_file
        elif nested_files:
            found_file = nested_files[0]  # Use first match
            # Update actual_path to point to snapshot directory for compatibility
            actual_path = str(found_file.parent)

        if found_file:
            file_size_gb = found_file.stat().st_size / (1024**3)
            logger.info(f"   - {expected_filename}: {file_size_gb:.2f} GB")
            logger.info("   - Located at: %s", found_file)
        else:
            logger.warning("Expected file not found: %s", expected_filename)
            logger.warning("   Searched in: %s", direct_file)
            logger.warning("   And pattern: %s", nested_pattern)

    return str(actual_path)
