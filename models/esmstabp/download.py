from pathlib import Path
from typing import Any, Optional

from models.commons.storage.download_helpers import standard_r2_download
from models.commons.storage.downloads import get_model_dir_util
from models.esmstabp.schema import ESMStabPParams

# R2 paths: r2://biolm-modal/model-store/esmstabp/v1/{1,2,3,4}.joblib
# If missing, run: python models/esmstabp/_train.py


def get_model_dir() -> Path:
    """Get local model directory path."""
    return get_model_dir_util(
        base_model_slug=ESMStabPParams.base_model_slug,
        params_version=ESMStabPParams.params_version,
    )


def download_model_assets(
    base_model_slug: str,
    params_version: str,
    variant_config: Optional[dict[str, Any]] = None,
    sub_path: Optional[str] = None,
) -> Path:
    """Download RF model weights from R2."""
    result = standard_r2_download(
        base_model_slug=base_model_slug,
        params_version=params_version,
        model_variant=None,  # Single-variant model
        sub_path=sub_path,
    )

    if not result.success:
        raise RuntimeError(
            f"Download failed: {result.error_message}\n"
            f"Run: python models/esmstabp/_train.py"
        )

    return result.actual_model_path or result.target_dir
