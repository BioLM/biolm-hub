from pathlib import Path
from typing import Optional

from models.commons.core.logging import get_logger
from models.commons.storage.download_helpers import r2_then_archive
from models.commons.storage.downloads import get_model_dir_util
from models.deepviscosity.schema import DeepViscosityParams

logger = get_logger(__name__)

# GitHub repository - pinned to specific commit for reproducibility
# IMPORTANT: When bumping PINNED_COMMIT (e.g. after an upstream retrain), the embedded
# SCALER_PARAMS in util.py must also be re-extracted from DeepViscosity_scaler.joblib
# at the new commit.  Keep both in sync.
PINNED_COMMIT = "2d22a5bfd3905ca508fe675fd212d2d431876517"
DEEPVISCOSITY_ZIP_URL = (
    f"https://github.com/Lailabcode/DeepViscosity/archive/{PINNED_COMMIT}.zip"
)


def get_model_dir() -> Path:
    """Get the model directory for DeepViscosity assets."""
    return get_model_dir_util(
        base_model_slug=DeepViscosityParams.base_model_slug,
        weights_version=DeepViscosityParams.weights_version,
    )


def download_model_assets(
    base_model_slug: str,
    weights_version: str,
    variant_config: Optional[dict[str, str]] = None,
    sub_path: Optional[str] = None,
) -> Path:
    """
    Download DeepViscosity model assets with R2 primary and GitHub fallback.

    Assets downloaded:
    - DeepViscosity_ANN_ensemble_models/: 102 ensemble ANN models (JSON + H5)
    - DeepSP_CNN_model/: 3 CNN models for DeepSP feature extraction

    Note: StandardScaler parameters are NOT downloaded — they are embedded directly
    in util.py (SCALER_PARAMS) to avoid sklearn pickle-version compatibility issues.
    See PINNED_COMMIT above for the upstream commit from which they were extracted.
    """
    result = r2_then_archive(
        base_model_slug=base_model_slug,
        weights_version=weights_version,
        sub_path=sub_path,
        archive_url=DEEPVISCOSITY_ZIP_URL,
        extract_subtrees={
            "DeepViscosity_ANN_ensemble_models/": "DeepViscosity_ANN_ensemble_models",
            "DeepSP_CNN_model/": "DeepSP_CNN_model",
        },
        # Validate a representative file from each extracted subtree (also enforced
        # on the R2-primary read) so a partial/corrupt acquisition fails fast.
        required_files=[
            "DeepViscosity_ANN_ensemble_models/ANN_logo_0.json",
            "DeepViscosity_ANN_ensemble_models/ANN_logo_0.h5",
            "DeepSP_CNN_model/Conv1D_regressionSAPpos.json",
        ],
    )

    if not result.success:
        raise RuntimeError(
            f"Failed to download DeepViscosity model: {result.error_message}"
        )

    logger.info(
        "DeepViscosity model assets acquired (%s)",
        "R2 cache" if result.cache_hit else "GitHub archive",
    )
    return result.actual_model_path or result.target_dir
