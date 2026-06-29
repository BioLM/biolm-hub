from pathlib import Path
from typing import Optional

from models.commons.core.logging import get_logger
from models.commons.storage.download_helpers import (
    extract_model_variant,
    r2_then_hf,
)
from models.commons.storage.downloads import build_hf_snapshot_path, get_model_dir_util
from models.igt5.config import (
    IGT5_HF_REPO_MAP,
    IGT5_HF_REVISION_MAP,
    model_id_mapping,
)
from models.igt5.schema import IgT5Params

logger = get_logger(__name__)


def get_model_dir(model_type: str) -> Path:
    """Return the HuggingFace snapshot path for the given variant (used by app.py)."""
    model_id = model_id_mapping[model_type]
    base_dir = get_model_dir_util(
        base_model_slug=IgT5Params.base_model_slug,
        weights_version=IgT5Params.weights_version,
        model_variant=model_id,
    )
    return build_hf_snapshot_path(
        base_dir, IGT5_HF_REPO_MAP[model_id], IGT5_HF_REVISION_MAP[model_id]
    )


def download_model_assets(
    base_model_slug: str,
    weights_version: str,
    variant_config: Optional[dict] = None,
    sub_path: Optional[str] = None,
):
    """Download model assets."""

    # Extract MODEL_TYPE from variant_config using standardized helper
    model_type = extract_model_variant(variant_config, "MODEL_TYPE")

    model_id = model_id_mapping[model_type]

    result = r2_then_hf(
        base_model_slug=base_model_slug,
        weights_version=weights_version,
        model_variant=model_id,
        sub_path=sub_path,
        hf_repo_id=IGT5_HF_REPO_MAP[model_id],
        hf_revision=IGT5_HF_REVISION_MAP[model_id],
        required_files=["config.json"],
    )

    if not result.success:
        raise RuntimeError(f"Model download failed: {result.error_message}")

    logger.info("Downloaded %s files using acquisition system", result.files_downloaded)
    return result.actual_model_path or result.target_dir
