from pathlib import Path
from typing import Optional

from models.commons.core.logging import get_logger
from models.commons.storage.download_helpers import r2_then_library
from models.commons.storage.downloads import get_model_dir_util, setup_hf_cache_env
from models.esmfold.schema import ESMFoldParams

logger = get_logger(__name__)

# fair-esm CDN object for the ESMFold v1 folding head. The runtime loader
# (esm.pretrained.esmfold_v1) fetches this same object via torch.hub into
# "<hub_dir>/checkpoints/". The head has no contact-regression companion.
ESMFOLD_HEAD_URL = "https://dl.fbaipublicfiles.com/fair-esm/models/esmfold_3B_v1.pt"
# ESMFold v1's cfg.esm_type == "esm2_3B" -> esm_registry["esm2_3B"] ==
# esm.pretrained.esm2_t36_3B_UR50D, which ESMFold.__init__ loads (with its
# contact-regression companion) at runtime. So the backbone files are
# esm2_t36_3B_UR50D.pt + esm2_t36_3B_UR50D-contact-regression.pt.
ESMFOLD_BACKBONE_NAME = "esm2_t36_3B_UR50D"


def get_model_dir() -> Path:
    """torch.hub directory for ESMFold weights.

    The runtime loader does ``torch.hub.set_dir(this)`` and fair-esm then reads
    ``<this>/checkpoints/esmfold_3B_v1.pt`` plus the ``esm2_t36_3B_UR50D`` backbone
    (and its contact-regression companion) — the exact on-disk layout the download
    writes and caches to R2 (R2 prefix ``model-store/esmfold/v1/``).
    """
    return get_model_dir_util(
        base_model_slug=ESMFoldParams.base_model_slug,
        weights_version=ESMFoldParams.weights_version,
    )


def _init_esmfold_weights(target_dir: Path) -> Path:
    """Fetch ESMFold weights into ``target_dir/checkpoints/`` via fair-esm's hub download.

    Source fallback for ``r2_then_library``: on an R2 cache miss this triggers
    fair-esm's own ``torch.hub`` downloads, then the acquisition layer caches
    ``target_dir`` back to R2 so later deploys self-populate.

    NOTE: this deliberately downloads the checkpoints WITHOUT constructing ESMFold.
    The full loader (``esm.pretrained.esmfold_v1``) imports ``openfold`` (plus
    einops / omegaconf / ml-collections / dm-tree) at construction time — none of
    which are installed in the Modal download layer (it carries fair-esm only), and
    openfold cannot be added there cleanly (it needs build tooling +
    ``--no-build-isolation``). So we fetch exactly the two artifacts ESMFold v1
    reads at runtime: the folding head (``esmfold_3B_v1.pt``) and the
    ``esm2_t36_3B_UR50D`` backbone + its contact-regression companion. The backbone
    download via ``_download_model_and_regression_data`` is openfold-free (plain
    ESM2 path), needing nothing beyond fair-esm + torch.
    """
    import torch

    torch.hub.set_dir(target_dir)
    setup_hf_cache_env(target_dir)

    import esm.pretrained

    logger.info("Downloading ESMFold folding head from fair-esm...")
    torch.hub.load_state_dict_from_url(
        ESMFOLD_HEAD_URL, progress=False, map_location="cpu"
    )
    logger.info(
        "Downloading ESMFold backbone (%s) + regression from fair-esm...",
        ESMFOLD_BACKBONE_NAME,
    )
    esm.pretrained._download_model_and_regression_data(ESMFOLD_BACKBONE_NAME)
    logger.info("ESMFold weights downloaded successfully")

    return target_dir


def download_model_assets(
    base_model_slug: str,
    weights_version: str,
    variant_config: Optional[dict] = None,
    sub_path: Optional[str] = None,
) -> Path:
    """Acquire ESMFold weights: R2 cache first, else fair-esm download, cached back to R2."""
    result = r2_then_library(
        base_model_slug=base_model_slug,
        weights_version=weights_version,
        sub_path=sub_path,
        library_name="esm",
        init_fn=_init_esmfold_weights,
    )

    if not result.success:
        raise RuntimeError(f"Model download failed: {result.error_message}")

    logger.info("Downloaded %s files using acquisition system", result.files_downloaded)
    return result.actual_model_path or result.target_dir
