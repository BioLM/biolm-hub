from typing import Optional

from models.commons.core.logging import get_logger
from models.commons.storage.download_helpers import (
    build_model_type_filter,
    extract_model_variant,
    standard_r2_download,
)
from models.commons.storage.downloads import get_model_dir_util
from models.immunefold.config import ImmuneFoldModelTypes, model_id_mapping
from models.immunefold.schema import ImmuneFoldParams

logger = get_logger(__name__)


def get_model_dir():

    return get_model_dir_util(
        base_model_slug=ImmuneFoldParams.base_model_slug,
        params_version=ImmuneFoldParams.params_version,
    )


def download_model_assets(
    base_model_slug: str,
    params_version: str,
    variant_config: Optional[dict] = None,
    sub_path: Optional[str] = None,
):
    """Download model assets."""

    # Extract MODEL_TYPE from variant_config
    model_type = extract_model_variant(variant_config, "MODEL_TYPE")

    # Build filter using the helper
    filter_func = build_model_type_filter(
        checkpoint_mapping=model_id_mapping,
        model_type=model_type,
        allowed_values=ImmuneFoldModelTypes,
        include_files=[".pt"],  # Always include .pt files
    )

    result = standard_r2_download(
        base_model_slug=base_model_slug,
        params_version=params_version,
        model_variant=None,  # immunefold doesn't use model_variant parameter
        sub_path=sub_path,
        filter_func=filter_func,
    )

    if not result.success:
        raise RuntimeError(f"Model download failed: {result.error_message}")

    logger.info("Downloaded %s files using acquisition system", result.files_downloaded)
    return result.actual_model_path or result.target_dir
