from typing import Optional

from models.abodybuilder3.schema import AbodyBuilder3Params
from models.commons.storage.download_helpers import (
    standard_r2_download,
)
from models.commons.storage.downloads import get_model_dir_util


def get_model_dir():

    return get_model_dir_util(
        base_model_slug=AbodyBuilder3Params.base_model_slug,
        params_version=AbodyBuilder3Params.params_version,
    )


def download_model_assets(
    base_model_slug: str,
    params_version: str,
    variant_config: Optional[dict] = None,
    sub_path: Optional[str] = None,
):
    """Download model assets."""

    model_variant = None  # this model does not have variants

    # AbodyBuilder3 downloads all necessary files regardless of variant
    # The filter remains the same for all model types
    def _should_download_file(full_key: str) -> bool:
        return (
            "prott5/" in full_key or "-loss/" in full_key or full_key.endswith(".ckpt")
        )

    result = standard_r2_download(
        base_model_slug=base_model_slug,
        params_version=params_version,
        model_variant=model_variant,
        sub_path=sub_path,
        filter_func=_should_download_file,
    )

    if not result.success:
        raise RuntimeError(f"Model download failed: {result.error_message}")

    print(f"✅ Downloaded {result.files_downloaded} files using acquisition system")
    return result.actual_model_path or result.target_dir
