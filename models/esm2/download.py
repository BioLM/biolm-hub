from pathlib import Path
from typing import Optional

from models.commons.core.logging import get_logger
from models.commons.storage.download_helpers import (
    extract_model_variant,
    r2_then_library,
)
from models.commons.storage.downloads import get_model_dir_util, setup_hf_cache_env
from models.esm2.config import model_id_mapping
from models.esm2.schema import ESM2Params

logger = get_logger(__name__)


def get_model_id(model_size: str) -> str:
    """Generate ESM2 model ID from model size."""
    return model_id_mapping[model_size]


def get_model_dir(model_size: str) -> Path:
    """Local/R2 directory for a given ESM2 size, keyed by the fair-esm model id.

    The runtime loader does ``torch.hub.set_dir(this)`` and fair-esm then reads
    ``<this>/checkpoints/<model_id>.pt`` — the same layout the download caches to R2.
    """
    model_id = get_model_id(model_size)
    return get_model_dir_util(
        base_model_slug=ESM2Params.base_model_slug,
        weights_version=ESM2Params.weights_version,
        model_variant=model_id,
    )


def _init_esm2_weights(model_id: str):
    """Build a fair-esm init_fn that downloads ``model_id`` into ``target_dir/checkpoints/``.

    Used as the source fallback for ``r2_then_library``: on an R2 cache miss the ESM
    library fetches the checkpoint (+ contact-regression companion) from the fair-esm
    CDN, and the acquisition layer then caches the whole ``target_dir`` back to R2.
    """

    def _init(target_dir: Path) -> Path:
        import torch

        torch.hub.set_dir(target_dir)
        setup_hf_cache_env(target_dir)

        import esm

        logger.info("Loading ESM2 (%s) to download weights from fair-esm...", model_id)
        model, alphabet = esm.pretrained.load_model_and_alphabet_hub(model_id)
        logger.info("ESM2 weights downloaded successfully (%s)", model_id)

        del model
        del alphabet

        return target_dir

    return _init


def download_model_assets(
    base_model_slug: str,
    weights_version: str,
    variant_config: Optional[dict] = None,
    sub_path: Optional[str] = None,
) -> Path:
    """Acquire ESM2 weights: R2 cache first, else fair-esm download, cached back to R2."""
    model_size = extract_model_variant(variant_config, "MODEL_SIZE")
    model_id = get_model_id(model_size)

    result = r2_then_library(
        base_model_slug=base_model_slug,
        weights_version=weights_version,
        model_variant=model_id,
        sub_path=sub_path,
        library_name="esm",
        init_fn=_init_esm2_weights(model_id),
        monitor_directories=["~/.cache/torch"],
    )

    if not result.success:
        raise RuntimeError(f"Model download failed: {result.error_message}")

    logger.info("Downloaded %s files using acquisition system", result.files_downloaded)
    return result.actual_model_path or result.target_dir
