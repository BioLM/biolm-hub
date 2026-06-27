from typing import Optional

from models.commons.core.logging import get_logger
from models.commons.storage.download_helpers import (
    extract_model_variant,
    standard_r2_download,
)
from models.commons.storage.downloads import get_model_dir_util
from models.esm1v.schema import ESM1vParams

logger = get_logger(__name__)


def get_model_id(model_number: str):
    """Generate ESM1v model ID from model number."""
    if model_number == "all":
        return None  # No specific variant for "all"
    model_name_template = "esm1v_t33_650M_UR90S_{model_num}"
    model_number_clean = model_number.strip("n")
    return model_name_template.format(model_num=model_number_clean)


def get_model_dir(model_number: str = "all"):

    if model_number == "all":
        return get_model_dir_util(
            base_model_slug=ESM1vParams.base_model_slug,
            params_version=ESM1vParams.params_version,
        )
    else:
        model_variant = get_model_id(model_number)
        return get_model_dir_util(
            base_model_slug=ESM1vParams.base_model_slug,
            params_version=ESM1vParams.params_version,
            model_variant=model_variant,
        )


def download_model_assets(
    base_model_slug: str,
    params_version: str,
    variant_config: Optional[dict] = None,
    sub_path: Optional[str] = None,
):
    """Download model assets."""

    model_number = extract_model_variant(variant_config, "MODEL_NUMBER")

    if model_number == "all":
        # No model_variant downloads entire directory (all 5 models)
        derived_variant = None
        filter_func = None
    else:
        derived_variant = get_model_id(model_number)

        def esm1v_variant_filter(full_key: str) -> bool:
            return derived_variant in full_key

        filter_func = esm1v_variant_filter

    result = standard_r2_download(
        base_model_slug=base_model_slug,
        params_version=params_version,
        model_variant=derived_variant,
        sub_path=sub_path,
        filter_func=filter_func,
    )

    if not result.success:
        raise RuntimeError(f"Model download failed: {result.error_message}")

    logger.info("Downloaded %s files using acquisition system", result.files_downloaded)
    return result.actual_model_path or result.target_dir
