from typing import Optional

from models.commons.core.logging import get_logger
from models.commons.storage.download_helpers import (
    extract_model_variant,
    standard_r2_download,
)
from models.commons.storage.downloads import get_model_dir_util
from models.igbert.config import model_id_mapping
from models.igbert.schema import IgBertParams

logger = get_logger(__name__)


def get_model_id(model_type: str) -> str:
    return model_id_mapping[model_type]


def get_model_dir(model_type: str):

    model_id = model_id_mapping[model_type]
    return get_model_dir_util(
        base_model_slug=IgBertParams.base_model_slug,
        params_version=IgBertParams.params_version,
        model_variant=model_id,
    )


def download_model_assets(
    base_model_slug: str,
    params_version: str,
    variant_config: Optional[dict] = None,
    sub_path: Optional[str] = None,
):
    """Download model assets."""

    # Extract MODEL_TYPE from variant_config using standardized helper
    model_type = extract_model_variant(variant_config, "MODEL_TYPE")

    derived_variant = get_model_id(model_type)

    result = standard_r2_download(
        base_model_slug=base_model_slug,
        params_version=params_version,
        model_variant=derived_variant,
        sub_path=sub_path,
    )

    if not result.success:
        raise RuntimeError(f"Model download failed: {result.error_message}")

    logger.info("Downloaded %s files using acquisition system", result.files_downloaded)
    return result.actual_model_path or result.target_dir
