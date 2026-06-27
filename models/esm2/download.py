from typing import Optional

from models.commons.core.logging import get_logger
from models.commons.storage.download_helpers import (
    extract_model_variant,
    standard_r2_download,
)
from models.commons.storage.downloads import get_model_dir_util
from models.esm2.config import model_id_mapping
from models.esm2.schema import ESM2Params

logger = get_logger(__name__)


def get_model_id(model_size: str):
    """Generate ESM2 model ID from model size."""
    return model_id_mapping[model_size]


def get_model_dir(model_size: str):

    model_id = get_model_id(model_size)
    return get_model_dir_util(
        base_model_slug=ESM2Params.base_model_slug,
        params_version=ESM2Params.params_version,
        model_variant=model_id,
    )


def download_model_assets(
    base_model_slug: str,
    params_version: str,
    variant_config: Optional[dict] = None,
    sub_path: Optional[str] = None,
):
    """Download model assets."""

    # Extract MODEL_SIZE from variant_config
    model_size = extract_model_variant(variant_config, "MODEL_SIZE")

    # Compute the model variant from MODEL_SIZE
    derived_variant = get_model_id(model_size)

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
