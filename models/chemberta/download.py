from pathlib import Path
from typing import Any, Optional

from models.chemberta.config import hf_pin_revision, hf_repo_id
from models.chemberta.schema import ChemBERTaParams
from models.commons.core.logging import get_logger
from models.commons.storage.download_helpers import r2_then_hf
from models.commons.storage.downloads import get_model_dir_util

logger = get_logger(__name__)


def get_model_dir() -> Path:
    """Path helper used by app.py to locate the downloaded weights. No variant arg."""
    return get_model_dir_util(
        base_model_slug=ChemBERTaParams.base_model_slug,
        weights_version=ChemBERTaParams.weights_version,
    )


def download_model_assets(
    base_model_slug: str,
    weights_version: str,
    variant_config: Optional[dict[str, Any]] = None,
    sub_path: Optional[str] = None,
) -> Path:
    """Download model assets at image-build time.

    R2 is the fast primary cache; HuggingFace is the guaranteed fallback (which
    also caches back to R2). Returns the resolved snapshot directory.
    """
    logger.info("[Build phase] Snapshotting ChemBERTa model '%s'", hf_repo_id)

    result = r2_then_hf(
        base_model_slug=base_model_slug,
        weights_version=weights_version,
        sub_path=sub_path,
        hf_repo_id=hf_repo_id,
        hf_revision=hf_pin_revision,  # 40-char commit hash — never "main"
        required_files=["config.json"],
    )

    if not result.success:
        raise RuntimeError(
            f"Failed to download ChemBERTa model: {result.error_message}"
        )

    snapshot_path = result.actual_model_path or result.target_dir
    logger.info("[Build phase] ChemBERTa snapshot ready at: %s", snapshot_path)
    return snapshot_path
