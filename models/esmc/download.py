from pathlib import Path
from typing import Optional

from models.commons.core.logging import get_logger
from models.commons.storage.download_helpers import (
    extract_model_variant,
    r2_then_hf,
)
from models.commons.storage.downloads import get_model_dir_util
from models.esmc.config import ESMC_HF_REPO_MAP, ESMC_HF_REVISION_MAP
from models.esmc.schema import ESMCParams

logger = get_logger(__name__)


def get_model_id(model_size: str):
    return f"esmc_{model_size}"


def get_model_dir(model_size: str):
    model_id = get_model_id(model_size)
    return get_model_dir_util(
        base_model_slug=ESMCParams.base_model_slug,
        params_version=ESMCParams.params_version,
        model_variant=model_id,
    )


def download_model_assets(
    base_model_slug: str,
    params_version: str,
    variant_config: Optional[dict] = None,
    sub_path: Optional[str] = None,
) -> Path:
    """Download ESMC model assets."""
    model_size = extract_model_variant(variant_config, "MODEL_SIZE")
    derived_variant = get_model_id(model_size)

    hf_repo_id = ESMC_HF_REPO_MAP.get(model_size)
    hf_revision = ESMC_HF_REVISION_MAP.get(model_size)

    if not hf_repo_id:
        raise ValueError(
            f"No HuggingFace repository mapped for model size: {model_size}"
        )

    logger.info("Downloading ESMC %s", model_size)

    result = r2_then_hf(
        base_model_slug=base_model_slug,
        params_version=params_version,
        model_variant=derived_variant,
        sub_path=sub_path,
        hf_repo_id=hf_repo_id,
        hf_revision=hf_revision,
        required_files=["config.json", "data/weights"],
    )

    if not result.success:
        raise RuntimeError(f"Failed to acquire ESMC model: {result.error_message}")

    snapshot_path = result.actual_model_path or result.target_dir

    if result.cache_hit:
        logger.info("ESMC %s restored from cache", model_size)
    else:
        logger.info("ESMC %s downloaded: %s files", model_size, result.files_downloaded)

    logger.info("Using deterministic HF snapshot path: %s", snapshot_path)
    return snapshot_path
