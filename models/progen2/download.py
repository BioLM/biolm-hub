from typing import Optional

from models.commons.storage.download_helpers import (
    extract_model_variant,
    standard_r2_download,
)
from models.commons.storage.downloads import get_model_dir_util
from models.progen2.schema import ProGen2Params


def get_model_dir():

    return get_model_dir_util(
        base_model_slug=ProGen2Params.base_model_slug,
        params_version=ProGen2Params.params_version,
        sub_path="checkpoints",
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

    # ProGen2 R2 structure: v1/checkpoints/progen2_{model_type}/
    # Use the sub_path parameter for correct path structure and filter for the specific model
    derived_variant = f"progen2_{model_type}"

    # We download from checkpoints/ directory and filter for specific model variant
    # Also include shared tokenizer.json file from checkpoints/ directory
    def progen2_filter_func(full_key: str) -> bool:
        # Include files from the specific model directory
        # The full_key will be like "model-store/progen2/v1/checkpoints/progen2_medium/config.json"
        if derived_variant in str(full_key):
            return True
        # Include shared tokenizer.json from checkpoints/ directory
        if full_key.endswith("tokenizer.json"):
            return True
        return False

    result = standard_r2_download(
        base_model_slug=base_model_slug,
        params_version=params_version,
        model_variant=None,  # Don't use model_variant for path construction
        sub_path=sub_path,  # Use the sub_path parameter passed to this function
        filter_func=progen2_filter_func,
        required_files=[
            f"{derived_variant}/config.json",
            f"{derived_variant}/pytorch_model.bin",
            "tokenizer.json",
        ],
    )

    if not result.success:
        raise RuntimeError(f"Model download failed: {result.error_message}")

    print(f"✅ Downloaded {result.files_downloaded} files using acquisition system")
    return result.actual_model_path or result.target_dir
