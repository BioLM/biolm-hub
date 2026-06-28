from typing import Optional

from models.commons.core.logging import get_logger
from models.commons.storage import r2_then_urls
from models.commons.storage.downloads import get_model_dir_util
from models.mpnn.config import MPNNModelCheckpoints, MPNNModelTypes
from models.mpnn.schema import MPNNParams

logger = get_logger(__name__)

# The six LigandMPNN-family checkpoints are published on the IPD file server
# (the upstream ``get_model_params.sh`` pulls them from this host). The seventh,
# HyperMPNN, is a community retrain hosted on GitHub. Keys are the on-disk
# filenames the runtime loader reads flat at ``<model_dir>/<file>.pt``
# (app.py: ``model_dir / MPNNModelCheckpoints[model_type]`` and the side-chain
# checkpoint). All MPNN variants share one R2 prefix (``model_variant=None``),
# so the first variant deploy self-populates R2 for every variant.
IPD_LIGANDMPNN_BASE_URL = "https://files.ipd.uw.edu/pub/ligandmpnn/"
HYPERMPNN_GITHUB_BASE_URL = (
    "https://github.com/meilerlab/HyperMPNN/raw/main/retrained_models/"
)

MPNN_CHECKPOINT_URLS = {
    filename: (
        f"{HYPERMPNN_GITHUB_BASE_URL}{filename}"
        if model_type == MPNNModelTypes.HYPER
        else f"{IPD_LIGANDMPNN_BASE_URL}{filename}"
    )
    for model_type, filename in MPNNModelCheckpoints.items()
}


def get_model_dir():

    return get_model_dir_util(
        base_model_slug=MPNNParams.base_model_slug,
        params_version=MPNNParams.params_version,
    )


def download_model_assets(
    base_model_slug: str,
    params_version: str,
    variant_config: Optional[dict] = None,
    sub_path: Optional[str] = None,
):
    """Download all MPNN checkpoints: R2 cache first, else the source URLs.

    On an R2 miss the six LigandMPNN-family checkpoints are fetched from IPD and
    the HyperMPNN checkpoint from GitHub, then cached back to R2 in the same
    container path so ``git clone -> deploy`` self-populates R2. ``variant_config``
    is unused: every variant downloads the full set into one shared R2 prefix.
    """
    result = r2_then_urls(
        base_model_slug=base_model_slug,
        params_version=params_version,
        sub_path=sub_path,
        urls=MPNN_CHECKPOINT_URLS,
        required_files=list(MPNN_CHECKPOINT_URLS.keys()),
        # files.ipd.uw.edu serves these over an unreliable TLS chain (same host
        # as RF3, which also disables verification). HyperMPNN/GitHub is fine
        # either way; verify_ssl=False applies to the whole batch.
        verify_ssl=False,
        timeout=3600,
    )

    if not result.success:
        raise RuntimeError(f"Model download failed: {result.error_message}")

    if result.cache_hit:
        logger.info("MPNN checkpoints restored from R2 cache")
    else:
        logger.info("MPNN downloaded %s checkpoint files", result.files_downloaded)

    return result.actual_model_path or result.target_dir
