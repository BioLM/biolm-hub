from pathlib import Path
from typing import Optional

from models.commons.storage.download_helpers import r2_then_hf
from models.commons.storage.downloads import build_hf_snapshot_path, get_model_dir_util
from models.esm1b.config import ESM1B_HF_REPO_ID, ESM1B_HF_REVISION
from models.esm1b.schema import ESM1bParams


def get_model_dir() -> Path:
    """Helper for consistent paths. Used by app.py.

    Returns the HuggingFace snapshot path where model files are actually located,
    not the base directory.
    """
    base_dir = get_model_dir_util(
        base_model_slug=ESM1bParams.base_model_slug,
        params_version=ESM1bParams.params_version,
    )
    return build_hf_snapshot_path(base_dir, ESM1B_HF_REPO_ID, ESM1B_HF_REVISION)


def download_model_assets(
    base_model_slug: str,
    params_version: str,
    variant_config: Optional[dict] = None,
    sub_path: Optional[str] = None,
) -> Path:
    """Download ESM-1b model assets."""
    result = r2_then_hf(
        base_model_slug=base_model_slug,
        params_version=params_version,
        sub_path=sub_path,
        hf_repo_id=ESM1B_HF_REPO_ID,
        hf_revision=ESM1B_HF_REVISION,
    )

    if not result.success:
        raise RuntimeError(f"Download failed: {result.error_message}")

    return result.actual_model_path or result.target_dir
