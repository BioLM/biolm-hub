from pathlib import Path
from typing import Optional

from models.commons.core.logging import get_logger
from models.commons.storage.download_helpers import r2_then_hf
from models.commons.storage.downloads import build_hf_snapshot_path, get_model_dir_util
from models.prostt5.config import PROSTT5_HF_REPO_ID, PROSTT5_HF_REVISION
from models.prostt5.schema import ProstT5Params

logger = get_logger(__name__)


def get_model_dir() -> Path:
    """Helper for consistent paths. Used by app.py.

    Returns the HuggingFace snapshot path where model files are actually located,
    not the base directory.
    """
    base_dir = get_model_dir_util(
        base_model_slug=ProstT5Params.base_model_slug,
        weights_version=ProstT5Params.weights_version,
    )
    return build_hf_snapshot_path(base_dir, PROSTT5_HF_REPO_ID, PROSTT5_HF_REVISION)


def download_model_assets(
    base_model_slug: str,
    weights_version: str,
    variant_config: Optional[dict] = None,
    sub_path: Optional[str] = None,
):
    """Download ProstT5 model assets.

    All ProstT5 variants (encode/generate, both directions) share the same
    weights, so there is no per-variant subdirectory.
    """
    result = r2_then_hf(
        base_model_slug=base_model_slug,
        weights_version=weights_version,
        sub_path=sub_path,
        hf_repo_id=PROSTT5_HF_REPO_ID,
        hf_revision=PROSTT5_HF_REVISION,
        required_files=["config.json"],
    )

    if not result.success:
        raise RuntimeError(f"Model download failed: {result.error_message}")

    logger.info("Downloaded %s files using acquisition system", result.files_downloaded)
    return result.actual_model_path or result.target_dir
