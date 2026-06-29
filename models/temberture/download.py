from pathlib import Path
from typing import Optional

from models.commons.core.logging import get_logger
from models.commons.storage.acquisition import (
    AcquisitionConfig,
    AcquisitionStrategy,
    CacheConfig,
    CustomSourceConfig,
    HfSourceConfig,
    R2OnlyConfig,
    ValidationConfig,
)
from models.commons.storage.download_helpers import (
    download_with_fallback,
    extract_model_variant,
)
from models.commons.storage.downloads import (
    build_hf_snapshot_path,
    download_archive,
    extract_archive_subtree,
    get_model_dir_util,
)
from models.temberture.config import (
    TemBERTureModelTypes,
    hf_pinned_revision,
    hf_repo_id,
    temberture_github_commit,
    temberture_github_repo,
)
from models.temberture.schema import TemBERTureParams

logger = get_logger(__name__)


def get_shared_base_model_dir() -> Path:
    """Get the directory path for the shared ProtBERT base model."""
    return get_model_dir_util(
        base_model_slug=TemBERTureParams.base_model_slug,
        weights_version=TemBERTureParams.weights_version,
        model_variant="shared",
        sub_path="base_model",
    )


def get_model_dir() -> Path:

    return get_model_dir_util(
        base_model_slug=TemBERTureParams.base_model_slug,
        weights_version=TemBERTureParams.weights_version,
        model_variant=None,
        sub_path="adapters",
    )


def _download_shared_base_model(
    base_model_slug: str, weights_version: str, base_model_dir: Path
):
    """Download shared ProtBERT base model."""

    # Build the deterministic snapshot path for validation
    snapshot_dir = build_hf_snapshot_path(
        base_model_dir, hf_repo_id, hf_pinned_revision
    )

    # ---- Primary strategy: R2 cache (validate it has the full model in snapshot structure) ----
    primary_config = AcquisitionConfig(
        strategy=AcquisitionStrategy.R2_ONLY,
        target_dir=base_model_dir,
        cache_config=CacheConfig(enable_r2_cache=False),  # Reading from R2
        validation_config=ValidationConfig(
            required_files=[
                # Use relative paths from snapshot dir
                str(snapshot_dir.relative_to(base_model_dir) / "pytorch_model.bin"),
                str(snapshot_dir.relative_to(base_model_dir) / "config.json"),
                str(snapshot_dir.relative_to(base_model_dir) / "vocab.txt"),
            ]
        ),
        r2_config=R2OnlyConfig(
            base_model_slug=base_model_slug,
            weights_version=weights_version,
            model_variant="shared",
            sub_path="base_model",
        ),
    )

    # ---- Fallback strategy: Download from HuggingFace with pinned revision ----
    fallback_config = AcquisitionConfig(
        strategy=AcquisitionStrategy.HUGGINGFACE_HUB,
        target_dir=base_model_dir,
        cache_config=CacheConfig(enable_r2_cache=True),  # Cache back to R2
        validation_config=ValidationConfig(
            required_files=["config.json", "pytorch_model.bin", "vocab.txt"]
        ),
        hf_config=HfSourceConfig(
            repo_id=hf_repo_id,
            revision=hf_pinned_revision,  # Pinned for determinism
            allow_patterns=["*.json", "*.txt", "pytorch_model.bin"],
            ignore_patterns=[
                "tf_model.h5",
                "*.msgpack",
                "*.h5",
            ],  # Skip TF weights (1.85GB)
        ),
    )

    result = download_with_fallback(primary_config, fallback_config)

    if not result.success:
        raise RuntimeError(
            f"Failed to download shared base model: {result.error_message}"
        )

    # Verify the snapshot directory exists
    if not snapshot_dir.exists():
        raise RuntimeError(
            f"Expected snapshot directory not found at {snapshot_dir}. "
            f"Download succeeded but files are in unexpected location."
        )

    logger.info("Shared ProtBERT model ready at snapshot: %s", snapshot_dir)

    # Return the result with snapshot path
    result.actual_model_path = snapshot_dir
    return result


def _download_temberture_archive(target_dir: Path, **_kwargs) -> dict:
    """
    Download TemBERTure GitHub archive to target directory.

    This is the acquisition function for CustomSourceConfig.
    Downloads the repository archive which contains adapter weights.

    Args:
        target_dir: Directory where the zip should be downloaded
        **_kwargs: Additional arguments (unused, but kept for compatibility)

    Returns:
        Metadata dictionary with download information
    """
    zip_url = f"https://github.com/{temberture_github_repo}/archive/{temberture_github_commit}.zip"
    zip_path = target_dir / "temberture.zip"

    logger.info(
        "Downloading TemBERTure adapters from GitHub (commit: %s)...",
        temberture_github_commit[:8],
    )

    # Use the shared download_archive helper
    metadata = download_archive(zip_url, zip_path)
    metadata["source"] = "github_archive"
    return metadata


def _extract_temberture_adapters(
    target_dir: Path, *, model_type: str, adapter_subdir: str
) -> None:
    """
    Extract TemBERTure adapters from zip and cleanup.

    This is the post-processing function for CustomSourceConfig.
    Extracts the temBERTure/ subdirectory from the GitHub archive.

    Args:
        target_dir: Directory containing the downloaded zip
        model_type: Type of model (classifier or regression)
        adapter_subdir: The expected adapter subdirectory name
    """
    zip_path = target_dir / "temberture.zip"
    prefix = f"TemBERTure-{temberture_github_commit}/temBERTure/"
    dest_dir = target_dir

    # Use the shared extract_archive_subtree helper
    extract_archive_subtree(zip_path, prefix, dest_dir, overwrite=False)

    # Clean up the zip file
    zip_path.unlink(missing_ok=True)
    logger.info("Cleaned up temporary archive file")

    # Verify expected directories exist
    expected_dir = dest_dir / adapter_subdir
    if not expected_dir.exists():
        raise RuntimeError(
            f"Expected adapter directory not found after extraction: {expected_dir}"
        )


def _download_variant_adapters(
    base_model_slug: str, weights_version: str, model_type: str
):
    """Download variant-specific TemBERTure adapters to shared location with filtering."""

    shared_adapter_dir = get_model_dir()
    if model_type == TemBERTureModelTypes.CLASSIFIER:
        adapter_subdir = "temBERTure_CLS"
    elif model_type == TemBERTureModelTypes.REGRESSION:
        adapter_subdir = "temBERTure_TM"

    def filter_func(key: str) -> bool:
        return adapter_subdir in key

    # ---- Primary strategy: R2 cache with filter ----
    primary_config = AcquisitionConfig(
        strategy=AcquisitionStrategy.R2_ONLY,
        target_dir=shared_adapter_dir,
        cache_config=CacheConfig(enable_r2_cache=False),
        validation_config=ValidationConfig(required_files=[adapter_subdir]),
        r2_config=R2OnlyConfig(
            base_model_slug=base_model_slug,
            weights_version=weights_version,
            model_variant=None,
            sub_path="adapters",
            filter_func=filter_func,
        ),
    )

    # ---- Fallback strategy: CUSTOM with GitHub archive download ----
    custom_config = CustomSourceConfig(
        acquisition_fn=_download_temberture_archive,
        acquisition_kwargs={},
        post_process_fn=_extract_temberture_adapters,
        post_process_kwargs={
            "model_type": model_type,
            "adapter_subdir": adapter_subdir,
        },
        name="temberture_github_archive",
        description=f"Download TemBERTure {model_type} adapters from GitHub",
    )

    fallback_config = AcquisitionConfig(
        strategy=AcquisitionStrategy.CUSTOM,
        target_dir=shared_adapter_dir,
        custom_config=custom_config,
        cache_config=CacheConfig(enable_r2_cache=True),
    )

    return download_with_fallback(primary_config, fallback_config)


def download_model_assets(
    base_model_slug: str,
    weights_version: str,
    variant_config: Optional[dict] = None,
    sub_path: Optional[str] = None,
):
    """Download model assets with shared base model and variant-specific adapters."""

    # Extract MODEL_TYPE from variant_config
    model_type = extract_model_variant(variant_config, "MODEL_TYPE")

    # Get directory for shared base model
    base_model_dir = get_shared_base_model_dir()
    logger.info("TemBERTure: Setting up shared base model at %s", base_model_dir)

    # ---- Download shared base model ----
    _download_shared_base_model(base_model_slug, weights_version, base_model_dir)

    # ---- Download adapters to shared location with filtering ----
    adapter_result = _download_variant_adapters(
        base_model_slug, weights_version, model_type
    )

    if not adapter_result.success:
        raise RuntimeError(
            f"Failed to download adapters: {adapter_result.error_message}"
        )

    # Return adapter path (the model loading code uses this)
    return adapter_result.actual_model_path or get_model_dir()
