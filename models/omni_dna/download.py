from pathlib import Path
from typing import Any, Optional

from models.commons.core.logging import get_logger
from models.commons.storage.download_helpers import (
    extract_model_variant,
    r2_then_hf,
)
from models.commons.storage.downloads import get_model_dir_util
from models.omni_dna.config import hf_model_name_mapping, hf_pin_revision_mapping
from models.omni_dna.schema import OmniDNAModelSizes, OmniDNAParams

logger = get_logger(__name__)


def get_model_dir(model_size: str) -> Path:

    return get_model_dir_util(
        base_model_slug=OmniDNAParams.base_model_slug,
        weights_version=OmniDNAParams.weights_version,
        model_variant=model_size,
    )


def download_model_assets(
    base_model_slug: str,
    weights_version: str,
    variant_config: Optional[dict[str, Any]] = None,
    sub_path: Optional[str] = None,
) -> Optional[Path]:
    """Download model assets."""
    model_variant = extract_model_variant(variant_config, "MODEL_SIZE")

    hf_repo_id = hf_model_name_mapping[OmniDNAModelSizes(model_variant)]
    hf_pinned_revision = hf_pin_revision_mapping[OmniDNAModelSizes(model_variant)]

    logger.info("[Build phase] Downloading Omni-DNA '%s'", hf_repo_id)

    result = r2_then_hf(
        base_model_slug=base_model_slug,
        weights_version=weights_version,
        model_variant=model_variant,
        sub_path=sub_path,
        hf_repo_id=hf_repo_id,
        hf_revision=hf_pinned_revision,
        required_files=["config.json", "model.safetensors"],
    )

    if not result.success:
        raise RuntimeError(f"Failed to acquire Omni-DNA model: {result.error_message}")

    snapshot_dir = result.actual_model_path or result.target_dir
    logger.info("Using deterministic HF snapshot path: %s", snapshot_dir)

    # Verify key files with size reporting
    safetensors_path = snapshot_dir / "model.safetensors"
    config_path = snapshot_dir / "config.json"

    if not safetensors_path.is_file():
        logger.error("Could not find model.safetensors at %s", safetensors_path)
        return None

    if not config_path.is_file():
        logger.error("Could not find config.json at %s", config_path)
        return None

    logger.info("[Build phase] Model files verified at %s", snapshot_dir)
    logger.info(
        f"   - model.safetensors: {safetensors_path.stat().st_size / (1024**3):.2f} GB"
    )
    logger.info("   - config.json: found")
    logger.info("[Build phase] Download complete, model will be loaded at runtime")

    return snapshot_dir
