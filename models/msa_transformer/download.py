from pathlib import Path
from typing import Optional

from models.commons.core.logging import get_logger
from models.commons.storage.download_helpers import r2_then_library
from models.commons.storage.downloads import get_model_dir_util, setup_hf_cache_env
from models.msa_transformer.schema import MSATransformerParams

logger = get_logger(__name__)


def get_model_dir() -> Path:
    """Get model directory for MSA Transformer weights."""
    return get_model_dir_util(
        base_model_slug=MSATransformerParams.base_model_slug,
        params_version=MSATransformerParams.params_version,
    )


def _init_msa_transformer_weights(target_dir: Path) -> Path:
    """Initialize MSA Transformer weights using the ESM library."""
    import torch

    torch.hub.set_dir(target_dir)
    setup_hf_cache_env(target_dir)

    import esm

    logger.info(
        "Loading MSA Transformer (esm_msa1b_t12_100M_UR50S) to download weights..."
    )
    model, alphabet = esm.pretrained.esm_msa1b_t12_100M_UR50S()
    logger.info("MSA Transformer weights downloaded successfully")

    del model
    del alphabet

    return target_dir


def download_model_assets(
    base_model_slug: str,
    params_version: str,
    variant_config: Optional[dict] = None,
    sub_path: Optional[str] = None,
) -> Path:
    """Download MSA Transformer model assets."""
    result = r2_then_library(
        base_model_slug=base_model_slug,
        params_version=params_version,
        sub_path=sub_path,
        library_name="esm",
        init_fn=_init_msa_transformer_weights,
        monitor_directories=["~/.cache/torch"],
    )

    if not result.success:
        raise RuntimeError(f"Model download failed: {result.error_message}")

    logger.info("Downloaded %s files using acquisition system", result.files_downloaded)
    return result.actual_model_path or result.target_dir
