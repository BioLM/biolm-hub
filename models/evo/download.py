from pathlib import Path
from typing import Optional

from models.commons.storage.download_helpers import (
    acquire_library_managed_model,
    extract_model_variant,
)
from models.evo.config import EVO_VARIANT_TO_MODEL_NAME


def _init_evo_weights(target_dir: Path, model_name: str) -> Path:
    """Initialize Evo weights download using library-managed approach.

    Evo manages its own cache paths via HuggingFace Hub, so target_dir
    is not used directly by the library.
    """
    print(f"📥 Downloading Evo model {model_name}")

    import torch
    from evo import Evo

    device = torch.device("cpu")
    _ = Evo(model_name, device=device)

    print(f"✅ Evo download complete for {model_name}")
    return target_dir


def download_model_assets(
    base_model_slug: str,
    params_version: str,
    variant_config: Optional[dict] = None,
    sub_path: Optional[str] = None,
) -> Path:
    """Download Evo model assets.

    Evo manages its own HuggingFace cache paths. R2 caching is not yet
    supported — enabling it requires redirecting HF cache to our target_dir
    at both build and runtime.
    """
    model_variant = extract_model_variant(variant_config, "MODEL_VARIANT")
    model_name = EVO_VARIANT_TO_MODEL_NAME[model_variant]

    # Evo downloads to HF's default cache, not our target directory.
    # A dummy target is used until R2 caching support is added.
    dummy_target = Path("/tmp/evo-download-placeholder")

    def init_fn(target_dir: Path) -> Path:
        return _init_evo_weights(target_dir, model_name)

    result = acquire_library_managed_model(
        library_name="evo",
        target_dir=dummy_target,
        init_fn=init_fn,
        monitor_directories=["~/.cache/huggingface", "~/.cache/torch"],
        cache_to_r2=False,
    )

    if not result.success:
        raise RuntimeError(f"Failed to acquire Evo model: {result.error_message}")

    if result.bypass_detected:
        print("✅ Evo bypass detected as expected")
        print(
            f"   📁 Model cached to library-managed locations: {result.bypass_locations}"
        )
        print("   💡 This is expected behavior - Evo library manages its own cache")

    print(f"✅ Download complete for {model_name}")
    return dummy_target
