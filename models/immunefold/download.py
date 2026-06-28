from typing import Optional

from models.commons.core.logging import get_logger
from models.commons.storage.download_helpers import (
    extract_model_variant,
    r2_then_urls,
)
from models.commons.storage.downloads import get_model_dir_util
from models.immunefold.config import ImmuneFoldModelTypes, model_id_mapping
from models.immunefold.schema import ImmuneFoldParams

logger = get_logger(__name__)

# Upstream weight sources.
#  - Per-variant ImmuneFold checkpoints are hosted on the authors' Zenodo
#    record (CarbonMatrixLab, open / CC-BY-4.0). The Zenodo filenames already
#    match the names the loader expects (immunefold-ab.ckpt / immunefold-tcr.ckpt).
#  - The shared ESM-2 3B backbone (+ its contact-regression companion) comes
#    from the fair-esm CDN; carbonmatrix loads it from a flat ``.pt`` path, and
#    fair-esm's local loader expects the companion regression file alongside.
_ZENODO_BASE = "https://zenodo.org/api/records/14580322/files"
_FAIR_ESM_BASE = "https://dl.fbaipublicfiles.com/fair-esm"

ESM2_BACKBONE_URLS = {
    "esm2_t36_3B_UR50D.pt": f"{_FAIR_ESM_BASE}/models/esm2_t36_3B_UR50D.pt",
    "esm2_t36_3B_UR50D-contact-regression.pt": (
        f"{_FAIR_ESM_BASE}/regression/esm2_t36_3B_UR50D-contact-regression.pt"
    ),
}

# Both per model-type checkpoints (keyed by the loader's checkpoint filename).
# Both variants share ONE R2 prefix (model_variant=None) and the R2 completion
# marker is per-prefix, so any deploy must populate the FULL set — otherwise the
# second variant's marker-gated R2 read would "succeed" without its own
# checkpoint. We therefore always fetch both checkpoints + the backbone; the
# variant only selects which checkpoint the loader reads at runtime.
CHECKPOINT_URLS = {
    "immunefold-ab.ckpt": f"{_ZENODO_BASE}/immunefold-ab.ckpt/content",
    "immunefold-tcr.ckpt": f"{_ZENODO_BASE}/immunefold-tcr.ckpt/content",
}


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
    """Download model assets: R2 cache first, else Zenodo + fair-esm, cached to R2."""

    # Extract MODEL_TYPE from variant_config and validate it (the variant only
    # selects which checkpoint the loader reads; we always fetch the full set).
    model_type = extract_model_variant(variant_config, "MODEL_TYPE")
    try:
        ImmuneFoldModelTypes(model_type)
    except ValueError as exc:
        raise ValueError(
            f"Invalid ImmuneFold model type '{model_type}'. "
            f"Must be one of: {[t.value for t in ImmuneFoldModelTypes]}"
        ) from exc

    # Full asset set: both checkpoints + the shared ESM-2 3B backbone.
    urls = {**CHECKPOINT_URLS, **ESM2_BACKBONE_URLS}
    required_files = [
        *model_id_mapping.values(),
        "esm2_t36_3B_UR50D.pt",
    ]

    logger.info("Downloading ImmuneFold %s assets (full set)...", model_type)

    result = r2_then_urls(
        base_model_slug=base_model_slug,
        params_version=params_version,
        model_variant=None,  # immunefold doesn't use model_variant in the path
        sub_path=sub_path,
        urls=urls,
        required_files=required_files,
    )

    if not result.success:
        raise RuntimeError(f"Model download failed: {result.error_message}")

    logger.info("Downloaded %s files using acquisition system", result.files_downloaded)
    return result.actual_model_path or result.target_dir
