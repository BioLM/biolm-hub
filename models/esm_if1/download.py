from typing import Optional

from models.commons.core.logging import get_logger
from models.commons.storage.download_helpers import (
    standard_r2_download,
)
from models.commons.storage.downloads import get_model_dir_util
from models.esm_if1.schema import ESMIF1Params

logger = get_logger(__name__)


def get_model_dir():

    return get_model_dir_util(
        base_model_slug=ESMIF1Params.base_model_slug,
        params_version=ESMIF1Params.params_version,
        sub_path="checkpoints",
    )


def download_model_assets(
    base_model_slug: str,
    params_version: str,
    variant_config: Optional[dict] = None,
    sub_path: Optional[str] = None,
):
    """Download model assets."""

    model_variant = None  # this model does not have variants

    result = standard_r2_download(
        base_model_slug=base_model_slug,
        params_version=params_version,
        model_variant=model_variant,
        sub_path=sub_path,  # Use the sub_path parameter passed to this function
    )

    if not result.success:
        raise RuntimeError(f"Model download failed: {result.error_message}")

    logger.info("Downloaded %s files using acquisition system", result.files_downloaded)
    return result.actual_model_path or result.target_dir
