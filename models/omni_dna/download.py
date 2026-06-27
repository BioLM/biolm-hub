from typing import Optional

from models.commons.storage.download_helpers import (
    extract_model_variant,
    r2_then_hf,
)
from models.commons.storage.downloads import get_model_dir_util
from models.omni_dna.config import hf_model_name_mapping, hf_pin_revision_mapping
from models.omni_dna.schema import OmniDNAParams


def get_model_dir(model_size: str):

    return get_model_dir_util(
        base_model_slug=OmniDNAParams.base_model_slug,
        params_version=OmniDNAParams.params_version,
        model_variant=model_size,
    )


def download_model_assets(
    base_model_slug: str,
    params_version: str,
    variant_config: Optional[dict] = None,
    sub_path: Optional[str] = None,
):
    """Download model assets."""
    model_variant = extract_model_variant(variant_config, "MODEL_SIZE")

    hf_repo_id = hf_model_name_mapping[model_variant]
    hf_pinned_revision = hf_pin_revision_mapping[model_variant]

    print(f"⏳ [Build phase] Downloading Omni-DNA '{hf_repo_id}'")

    result = r2_then_hf(
        base_model_slug=base_model_slug,
        params_version=params_version,
        model_variant=model_variant,
        sub_path=sub_path,
        hf_repo_id=hf_repo_id,
        hf_revision=hf_pinned_revision,
        required_files=["config.json", "model.safetensors"],
    )

    if not result.success:
        raise RuntimeError(f"Failed to acquire Omni-DNA model: {result.error_message}")

    snapshot_dir = result.actual_model_path or result.target_dir
    print(f"📁 Using deterministic HF snapshot path: {snapshot_dir}")

    # Verify key files with size reporting
    safetensors_path = snapshot_dir / "model.safetensors"
    config_path = snapshot_dir / "config.json"

    if not safetensors_path.is_file():
        print(f"❌ Could not find model.safetensors at {safetensors_path}")
        return

    if not config_path.is_file():
        print(f"❌ Could not find config.json at {config_path}")
        return

    print(f"✅ [Build phase] Model files verified at {snapshot_dir}")
    print(
        f"   - model.safetensors: {safetensors_path.stat().st_size / (1024**3):.2f} GB"
    )
    print("   - config.json: found")
    print("✅ [Build phase] Download complete, model will be loaded at runtime")

    return snapshot_dir
