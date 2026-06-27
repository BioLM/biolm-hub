from typing import Optional

from models.commons.storage.download_helpers import (
    extract_model_variant,
    r2_then_urls,
)
from models.commons.storage.downloads import get_model_dir_util
from models.immunebuilder.schema import ImmuneBuilderParams

# Define Zenodo URLs for each model type
ZENODO_URLS = {
    "nanobodybuilder2": {
        "nanobody_model_1": "https://zenodo.org/record/7258553/files/nanobody_model_1?download=1",
        "nanobody_model_2": "https://zenodo.org/record/7258553/files/nanobody_model_2?download=1",
        "nanobody_model_3": "https://zenodo.org/record/7258553/files/nanobody_model_3?download=1",
        "nanobody_model_4": "https://zenodo.org/record/7258553/files/nanobody_model_4?download=1",
    },
    "abodybuilder2": {
        "antibody_model_1": "https://zenodo.org/record/7258553/files/antibody_model_1?download=1",
        "antibody_model_2": "https://zenodo.org/record/7258553/files/antibody_model_2?download=1",
        "antibody_model_3": "https://zenodo.org/record/7258553/files/antibody_model_3?download=1",
        "antibody_model_4": "https://zenodo.org/record/7258553/files/antibody_model_4?download=1",
    },
    "tcrbuilder2": {
        "tcr2_model_1": "https://zenodo.org/record/7258553/files/tcr_model_1?download=1",
        "tcr2_model_2": "https://zenodo.org/record/7258553/files/tcr_model_2?download=1",
        "tcr2_model_3": "https://zenodo.org/record/7258553/files/tcr_model_3?download=1",
        "tcr2_model_4": "https://zenodo.org/record/7258553/files/tcr_model_4?download=1",
    },
    "tcrbuilder2plus": {
        "tcr_model_1": "https://zenodo.org/records/10892159/files/tcr_model_1?download=1",
        "tcr_model_2": "https://zenodo.org/record/10892159/files/tcr_model_2?download=1",
        "tcr_model_3": "https://zenodo.org/record/10892159/files/tcr_model_3?download=1",
        "tcr_model_4": "https://zenodo.org/record/10892159/files/tcr_model_4?download=1",
    },
}


def get_model_dir(model_type: str):

    return get_model_dir_util(
        base_model_slug=ImmuneBuilderParams.base_model_slug,
        params_version=ImmuneBuilderParams.params_version,
        model_variant=model_type,
    )


def download_model_assets(
    base_model_slug: str,
    params_version: str,
    variant_config: Optional[dict] = None,
    sub_path: Optional[str] = None,
):
    """Download ImmuneBuilder model assets with R2 primary and Zenodo fallback."""
    model_variant = extract_model_variant(variant_config, "MODEL_TYPE")

    if model_variant not in ZENODO_URLS:
        raise ValueError(f"Unknown model variant: {model_variant}")

    print(f"📥 Downloading ImmuneBuilder {model_variant}")

    result = r2_then_urls(
        base_model_slug=base_model_slug,
        params_version=params_version,
        model_variant=model_variant,
        sub_path=sub_path,
        urls=ZENODO_URLS[model_variant],
    )

    if not result.success:
        raise RuntimeError(
            f"Failed to download ImmuneBuilder models: {result.error_message}"
        )

    if result.cache_hit:
        print("✅ Downloaded from R2 cache")
    else:
        print(f"✅ Downloaded {result.files_downloaded} files")

    return result.actual_model_path or result.target_dir
