from pathlib import Path
from typing import Optional

from models.commons.core.logging import get_logger
from models.commons.storage.download_helpers import (
    extract_model_variant,
    r2_then_hf,
)
from models.commons.storage.downloads import get_model_dir_util
from models.dsm.config import DSM_HF_REPO_MAP, DSM_HF_REVISION_MAP
from models.dsm.schema import DSMParams

logger = get_logger(__name__)


def get_model_id(model_size: str, variant: str) -> str:
    """Get model ID from size and variant."""
    return f"dsm_{model_size}_{variant}"


def get_model_dir(model_size: str, variant: str) -> Path:
    """Get model directory path."""
    model_id = get_model_id(model_size, variant)
    return get_model_dir_util(
        base_model_slug=DSMParams.base_model_slug,
        weights_version=DSMParams.weights_version,
        model_variant=model_id,
    )


def download_model_assets(
    base_model_slug: str,
    weights_version: str,
    variant_config: Optional[dict] = None,
    sub_path: Optional[str] = None,
) -> Path:
    """Download DSM model assets."""
    model_size = extract_model_variant(variant_config, "MODEL_SIZE")
    variant = extract_model_variant(variant_config, "VARIANT")
    derived_variant = get_model_id(model_size, variant)

    # Get HF repo ID based on size and variant
    repo_key = (model_size, variant)
    hf_repo_id = DSM_HF_REPO_MAP.get(repo_key)
    hf_revision = DSM_HF_REVISION_MAP.get(repo_key)

    if not hf_repo_id:
        raise ValueError(
            f"No HuggingFace repository mapped for model size: {model_size}, variant: {variant}"
        )

    logger.info("Downloading DSM %s %s", model_size, variant)

    result = r2_then_hf(
        base_model_slug=base_model_slug,
        weights_version=weights_version,
        model_variant=derived_variant,
        sub_path=sub_path,
        hf_repo_id=hf_repo_id,
        hf_revision=hf_revision,
        required_files=["config.json"],
    )

    if not result.success:
        raise RuntimeError(f"Failed to acquire DSM model: {result.error_message}")

    snapshot_path = result.actual_model_path or result.target_dir

    # Validate that the snapshot path exists and has required files
    if not snapshot_path.exists():
        raise RuntimeError(
            f"Snapshot path does not exist after download: {snapshot_path}. "
            f"Download may have failed or path is incorrect."
        )

    config_file = snapshot_path / "config.json"
    if not config_file.exists():
        raise RuntimeError(
            f"Model config.json not found at: {config_file}. "
            f"Model download may be incomplete. "
            f"Expected files in: {snapshot_path}"
        )

    model_weights = snapshot_path / "model.safetensors"
    pytorch_weights = snapshot_path / "pytorch_model.bin"
    if not model_weights.exists() and not pytorch_weights.exists():
        raise RuntimeError(
            f"Model weights not found. Expected either {model_weights} or {pytorch_weights}. "
            f"Model download may be incomplete."
        )

    if result.cache_hit:
        logger.info("DSM %s %s restored from cache", model_size, variant)
    else:
        logger.info(
            "DSM %s %s downloaded: %s files",
            model_size,
            variant,
            result.files_downloaded,
        )

    logger.info("Using deterministic HF snapshot path: %s", snapshot_path)
    logger.info(
        "Verified snapshot path exists with required files (config.json, model weights)"
    )

    return snapshot_path
