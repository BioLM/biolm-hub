from pathlib import Path
from typing import Optional

from models.commons.core.logging import get_logger
from models.commons.storage.download_helpers import (
    extract_model_variant,
    r2_then_library,
)
from models.commons.storage.downloads import get_model_dir_util, setup_hf_cache_env
from models.evo.config import EVO_VARIANT_TO_MODEL_NAME
from models.evo.schema import EvoModelVariants, EvoParams

logger = get_logger(__name__)


def get_model_dir(model_variant: str) -> Path:
    """Local/R2 directory for an Evo variant.

    The Evo library downloads via HuggingFace Hub; we redirect its cache here (at
    both build and runtime) so the weights live under this dir, get cached to R2,
    and are found on the next deploy.
    """
    return get_model_dir_util(
        base_model_slug=EvoParams.base_model_slug,
        weights_version=EvoParams.weights_version,
        model_variant=model_variant,
    )


def _init_evo_weights(model_name: str):
    """Build an init_fn that downloads ``model_name`` via the Evo library.

    Redirects the HF cache to ``target_dir`` first, so the Evo library's internal
    HuggingFace download lands under target_dir (which r2_then_library caches to R2).
    """

    def _init(target_dir: Path) -> Path:
        import torch

        setup_hf_cache_env(target_dir)

        from evo import Evo

        logger.info("Downloading Evo model %s to %s ...", model_name, target_dir)
        _ = Evo(model_name, device=torch.device("cpu"))
        logger.info("Evo download complete for %s", model_name)
        return target_dir

    return _init


def download_model_assets(
    base_model_slug: str,
    weights_version: str,
    variant_config: Optional[dict] = None,
    sub_path: Optional[str] = None,
) -> Path:
    """Acquire Evo weights: R2 cache first, else Evo/HF download, cached back to R2."""
    model_variant = extract_model_variant(variant_config, "MODEL_VARIANT")
    model_name = EVO_VARIANT_TO_MODEL_NAME[EvoModelVariants(model_variant)]

    result = r2_then_library(
        base_model_slug=base_model_slug,
        weights_version=weights_version,
        model_variant=model_variant,
        sub_path=sub_path,
        library_name="evo",
        init_fn=_init_evo_weights(model_name),
        monitor_directories=["~/.cache/huggingface", "~/.cache/torch"],
    )

    if not result.success:
        raise RuntimeError(f"Failed to acquire Evo model: {result.error_message}")

    logger.info("Evo %s ready (%s files)", model_variant, result.files_downloaded)
    return result.actual_model_path or result.target_dir
