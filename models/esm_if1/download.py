from pathlib import Path
from typing import Optional

from models.commons.core.logging import get_logger
from models.commons.storage.download_helpers import r2_then_library
from models.commons.storage.downloads import get_model_dir_util, setup_hf_cache_env
from models.esm_if1.schema import ESMIF1Params

logger = get_logger(__name__)

# fair-esm checkpoint name for ESM-IF1. The runtime loader
# (esm.pretrained.esm_if1_gvp4_t16_142M_UR50) fetches this same object via
# torch.hub into "<hub_dir>/checkpoints/". ESM-IF has no contact-regression
# companion (_has_regression_weights is False for "esm_if*").
ESM_IF1_MODEL_NAME = "esm_if1_gvp4_t16_142M_UR50"


def get_model_dir() -> Path:
    """torch.hub directory for ESM-IF1 weights.

    The runtime loader does ``torch.hub.set_dir(this)`` and fair-esm then reads
    ``<this>/checkpoints/esm_if1_gvp4_t16_142M_UR50.pt`` — the exact on-disk layout
    the download writes and caches to R2. There is NO ``checkpoints`` sub_path on
    this dir: fair-esm creates the ``checkpoints/`` subdir itself under the hub
    dir, so the cached/restored R2 prefix is ``model-store/esm-if1/v1/`` (which
    contains ``checkpoints/<id>.pt``).
    """
    return get_model_dir_util(
        base_model_slug=ESMIF1Params.base_model_slug,
        params_version=ESMIF1Params.params_version,
    )


def _init_esm_if1_weights(target_dir: Path) -> Path:
    """Fetch ESM-IF1 weights into ``target_dir/checkpoints/`` via fair-esm's hub download.

    Source fallback for ``r2_then_library``: on an R2 cache miss this triggers
    fair-esm's own ``torch.hub`` download of the checkpoint, then the acquisition
    layer caches ``target_dir`` back to R2 so later deploys self-populate.

    NOTE: this deliberately downloads the checkpoint WITHOUT constructing the
    model. The full loader (``esm.pretrained.esm_if1_gvp4_t16_142M_UR50``) imports
    ``esm.inverse_folding`` at construction time, which requires
    ``torch_geometric`` / ``biotite`` / ``scipy`` — none of which are installed in
    the Modal download layer (it carries fair-esm only). The plain-ESM2 templates
    (esm2 / msa_transformer) can call their full loader because plain ESM2 has no
    such extra deps; ESM-IF1 does, so we download-only here using fair-esm's own
    hub-download primitive (which needs nothing beyond fair-esm + torch).
    """
    import torch

    torch.hub.set_dir(target_dir)
    setup_hf_cache_env(target_dir)

    import esm.pretrained

    logger.info("Downloading ESM-IF1 (%s) weights from fair-esm...", ESM_IF1_MODEL_NAME)
    esm.pretrained._download_model_and_regression_data(ESM_IF1_MODEL_NAME)
    logger.info("ESM-IF1 weights downloaded successfully")

    return target_dir


def download_model_assets(
    base_model_slug: str,
    params_version: str,
    variant_config: Optional[dict] = None,
    sub_path: Optional[str] = None,
) -> Path:
    """Acquire ESM-IF1 weights: R2 cache first, else fair-esm download, cached back to R2."""
    result = r2_then_library(
        base_model_slug=base_model_slug,
        params_version=params_version,
        sub_path=sub_path,
        library_name="esm",
        init_fn=_init_esm_if1_weights,
        monitor_directories=["~/.cache/torch"],
    )

    if not result.success:
        raise RuntimeError(f"Model download failed: {result.error_message}")

    logger.info("Downloaded %s files using acquisition system", result.files_downloaded)
    return result.actual_model_path or result.target_dir
