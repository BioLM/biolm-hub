from typing import Optional

from models.commons.core.logging import get_logger
from models.commons.storage.download_helpers import (
    extract_model_variant,
    standard_r2_download,
)
from models.commons.storage.downloads import get_model_dir_util
from models.igt5.config import model_id_mapping
from models.igt5.schema import IgT5Params

logger = get_logger(__name__)


def get_model_dir(model_type: str):

    model_id = model_id_mapping[model_type]
    return get_model_dir_util(
        base_model_slug=IgT5Params.base_model_slug,
        params_version=IgT5Params.params_version,
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

    derived_variant = model_id_mapping[model_type]

    # Apply variant filtering from original logic
    def igt5_filter_func(full_key: str) -> bool:
        if not derived_variant:
            return True
        return f"/{derived_variant}/" in full_key

    result = standard_r2_download(
        base_model_slug=base_model_slug,
        params_version=params_version,
        model_variant=derived_variant,
        sub_path=sub_path,
        filter_func=igt5_filter_func,
    )

    if not result.success:
        raise RuntimeError(f"Model download failed: {result.error_message}")

    logger.info("Downloaded %s files using acquisition system", result.files_downloaded)
    return result.actual_model_path or result.target_dir
