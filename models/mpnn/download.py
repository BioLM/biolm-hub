from typing import Optional

from models.commons.storage.acquisition import (
    AcquisitionConfig,
    AcquisitionStrategy,
    CacheConfig,
    UrlSourceConfig,
    acquire_model_weights,
)
from models.commons.storage.download_helpers import (
    build_model_type_filter,
    extract_model_variant,
    standard_r2_download,
)
from models.commons.storage.downloads import get_model_dir_util
from models.mpnn.config import MPNNModelCheckpoints, MPNNModelTypes
from models.mpnn.schema import MPNNParams


def get_model_dir():

    return get_model_dir_util(
        base_model_slug=MPNNParams.base_model_slug,
        params_version=MPNNParams.params_version,
    )


def download_model_assets(
    base_model_slug: str,
    params_version: str,
    variant_config: Optional[dict] = None,
    sub_path: Optional[str] = None,
):
    """
    Download model assets with R2 primary and GitHub fallback for HyperMPNN.

    For most MPNN variants, downloads from R2 only.
    For HyperMPNN, if not in R2, falls back to downloading from GitHub.
    """
    # Extract MODEL_TYPE from variant_config using standardized helper
    model_type = extract_model_variant(variant_config, "MODEL_TYPE")

    # Build filter using the helper
    filter_func = build_model_type_filter(
        checkpoint_mapping=MPNNModelCheckpoints,
        model_type=model_type,
        allowed_values=MPNNModelTypes,
        include_files=[
            MPNNModelCheckpoints[MPNNModelTypes.SIDE_CHAIN]
        ],  # Always include side chain
    )

    # Get target directory
    target_dir = get_model_dir_util(
        base_model_slug=base_model_slug,
        params_version=params_version,
        model_variant=None,  # MPNN doesn't use model_variant in R2 paths
        sub_path=sub_path,
    )

    # For HyperMPNN, add GitHub fallback
    if model_type == MPNNModelTypes.HYPER:
        checkpoint_filename = MPNNModelCheckpoints[MPNNModelTypes.HYPER]
        checkpoint_path = target_dir / checkpoint_filename

        # GitHub raw URL for HyperMPNN weights
        github_url = (
            "https://github.com/meilerlab/HyperMPNN/raw/main/"
            f"retrained_models/{checkpoint_filename}"
        )

        # Try R2 first
        result = standard_r2_download(
            base_model_slug=base_model_slug,
            params_version=params_version,
            model_variant=None,
            sub_path=sub_path,
            filter_func=filter_func,
            target_dir=target_dir,
        )

        # Check if the hyper checkpoint was actually downloaded
        # If not, use fallback to download from GitHub
        if not checkpoint_path.exists():
            print(f"⚠️ HyperMPNN checkpoint not found in R2: {checkpoint_path}")
            print("📥 Falling back to GitHub download...")

            # Note: Side chain model should already be in R2 from other MPNN variants.
            # We only download the HyperMPNN checkpoint from GitHub if not in R2.
            fallback_config = AcquisitionConfig(
                strategy=AcquisitionStrategy.DIRECT_URLS,
                target_dir=target_dir,
                cache_config=CacheConfig(
                    enable_r2_cache=True,  # Cache to R2 after download
                ),
                url_config=UrlSourceConfig(
                    urls={
                        checkpoint_filename: github_url,
                    },
                    verify_ssl=True,
                    timeout=60 * 60,  # 1 hour timeout for large files
                    chunk_size=8192,
                ),
            )

            # Download from GitHub
            fallback_result = acquire_model_weights(fallback_config)

            if not fallback_result.success:
                raise RuntimeError(
                    f"Failed to download HyperMPNN from GitHub: {fallback_result.error_message}"
                )

            # Merge results - combine file counts from both downloads
            total_files = (result.files_downloaded or 0) + (
                fallback_result.files_downloaded or 0
            )
            result = fallback_result
            result.files_downloaded = total_files
    else:
        # For other variants, use standard R2 download only
        result = standard_r2_download(
            base_model_slug=base_model_slug,
            params_version=params_version,
            model_variant=None,
            sub_path=sub_path,
            filter_func=filter_func,
            target_dir=target_dir,
        )

    if not result.success:
        raise RuntimeError(f"Model download failed: {result.error_message}")

    print(f"✅ Downloaded {result.files_downloaded} files using acquisition system")
    if result.metadata.get("r2_upload_success"):
        print("✅ Successfully cached to R2 for future use")
    elif result.cache_hit:
        print("✅ Downloaded from R2 cache")

    return result.actual_model_path or result.target_dir
