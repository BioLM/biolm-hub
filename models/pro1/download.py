from pathlib import Path

from models.commons.storage.download_helpers import (
    acquire_library_managed_model,
)
from models.commons.storage.downloads import (
    get_model_dir_util,
    setup_hf_cache_env,
)
from models.pro1.config import (
    PRO1_ADAPTER_REVISION,
    PRO1_BASE_MODEL_REVISION,
    PRO1_HF_REPO,
    PRO1_VARIANT_TO_HF_CONFIG,
)
from models.pro1.schema import Pro1Params, Pro1Variant


def get_model_dir():
    return get_model_dir_util(
        base_model_slug=Pro1Params.base_model_slug,
        params_version=Pro1Params.params_version,
    )


def _init_pro1_weights(
    target_dir: Path, base_model: str, adapter_subfolder: str
) -> Path:
    """Download Pro-1 base model + LoRA adapter via HuggingFace hub."""
    from huggingface_hub import snapshot_download

    setup_hf_cache_env(target_dir)

    # Download base model directly via HF hub (no GPU needed at download time;
    # newer unsloth requires GPU even at download).
    print(f"📥 Downloading base model: {base_model}@{PRO1_BASE_MODEL_REVISION[:8]}")
    snapshot_download(repo_id=base_model, revision=PRO1_BASE_MODEL_REVISION)
    print(f"✅ Base model downloaded: {base_model}")

    adapter_dir = target_dir / "adapter"
    adapter_dir.mkdir(parents=True, exist_ok=True)
    print(
        f"📥 Downloading LoRA adapter: "
        f"{PRO1_HF_REPO}@{PRO1_ADAPTER_REVISION[:8]}/{adapter_subfolder}"
    )
    snapshot_download(
        repo_id=PRO1_HF_REPO,
        revision=PRO1_ADAPTER_REVISION,
        local_dir=str(adapter_dir),
        allow_patterns=f"{adapter_subfolder}/**",
    )
    adapter_path = adapter_dir / adapter_subfolder
    if not adapter_path.exists():
        raise FileNotFoundError(
            f"LoRA adapter not found at expected path: {adapter_path}\n"
            f"Searched under: {adapter_dir}"
        )
    print(f"✅ LoRA adapter downloaded: {adapter_path}")
    return target_dir


def download_model_assets(
    base_model_slug: str,
    params_version: str,
    variant_config: dict | None = None,
    sub_path: str | None = None,
) -> Path:
    """Download Pro-1 base model + LoRA adapter.

    Downloads to HuggingFace cache within the model directory.
    Uses acquire_library_managed_model since HF manages its own cache layout.
    """
    model_variant_str = (variant_config or {}).get("MODEL_VARIANT", Pro1Variant.SIZE_8B)
    model_variant = Pro1Variant(model_variant_str)
    base_model, adapter_subfolder = PRO1_VARIANT_TO_HF_CONFIG[model_variant]

    target_dir = Path(
        get_model_dir_util(
            base_model_slug=base_model_slug,
            params_version=params_version,
        )
    )

    def init_fn(td: Path) -> Path:
        return _init_pro1_weights(td, base_model, adapter_subfolder)

    result = acquire_library_managed_model(
        library_name="pro1",
        target_dir=target_dir,
        init_fn=init_fn,
        monitor_directories=["~/.cache/huggingface"],
        cache_to_r2=False,  # Weights too large for R2 caching
    )

    if not result.success:
        raise RuntimeError(f"Pro-1 model download failed: {result.error_message}")

    print(f"✅ Pro-1 ({model_variant}) download complete")
    return target_dir
