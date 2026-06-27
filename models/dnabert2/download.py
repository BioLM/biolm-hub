from typing import Optional

from models.commons.storage.download_helpers import r2_then_hf
from models.commons.storage.downloads import get_model_dir_util
from models.dnabert2.config import hf_pin_revision, hf_repo_id
from models.dnabert2.schema import DNABERT2Params


def get_model_dir():

    return get_model_dir_util(
        base_model_slug=DNABERT2Params.base_model_slug,
        params_version=DNABERT2Params.params_version,
    )


def download_model_assets(
    base_model_slug: str,
    params_version: str,
    variant_config: Optional[dict] = None,
    sub_path: Optional[str] = None,
):
    """Download model assets."""

    from transformers import AutoModelForMaskedLM, AutoTokenizer

    print(f"⏳ [Build phase] Snapshotting DNABERT-2 model '{hf_repo_id}'")

    result = r2_then_hf(
        base_model_slug=base_model_slug,
        params_version=params_version,
        sub_path=sub_path,
        hf_repo_id=hf_repo_id,
        hf_revision=hf_pin_revision,
        required_files=["config.json"],
    )

    if not result.success:
        raise RuntimeError(
            f"Failed to download DNABERT-2 model: {result.error_message}"
        )

    snapshot_path = result.actual_model_path or result.target_dir
    print(f"📍 Using HF snapshot path: {snapshot_path}")

    # ---- Final validation ----
    print(f"🔍 [Build phase] Testing model loading from {snapshot_path}...")

    _ = AutoModelForMaskedLM.from_pretrained(snapshot_path, trust_remote_code=True)
    print("✅ [Build phase] Model loaded successfully")

    _ = AutoTokenizer.from_pretrained(
        snapshot_path, trust_remote_code=True, use_fast=True
    )
    print("✅ [Build phase] Tokenizer loaded successfully")

    print(f"✅ [Build phase] Model snapshot ready at: {snapshot_path}")
    return snapshot_path
