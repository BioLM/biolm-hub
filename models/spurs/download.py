from pathlib import Path
from typing import Optional

from models.commons.storage.download_helpers import r2_then_hf
from models.commons.storage.downloads import get_model_dir_util
from models.spurs.config import HF_REPO_ID, HF_REVISION
from models.spurs.schema import SpursParams


def get_model_dir(sub_path: Optional[str] = None) -> Path:
    """Resolve the local directory where SPURS weights should be stored."""
    return get_model_dir_util(
        base_model_slug=SpursParams.base_model_slug,
        params_version=SpursParams.params_version,
        model_variant=None,
        sub_path=sub_path,
    )


def download_model_assets(
    base_model_slug: str,
    params_version: str,
    variant_config: Optional[dict] = None,
    sub_path: Optional[str] = None,
) -> Path:
    """Download SPURS model assets."""
    print("🔧 SPURS: Downloading model assets")

    result = r2_then_hf(
        base_model_slug=base_model_slug,
        params_version=params_version,
        sub_path=sub_path,
        hf_repo_id=HF_REPO_ID,
        hf_revision=HF_REVISION,
        allow_patterns=[
            "spurs/.hydra/*",
            "spurs/checkpoints/*",
            "spurs_multi/.hydra/*",
            "spurs_multi/checkpoints/*",
        ],
    )

    if not result.success:
        raise RuntimeError(
            f"Failed to download SPURS model assets: {result.error_message}"
        )

    if result.cache_hit:
        print("✅ SPURS assets restored from cache")
    else:
        print(f"✅ SPURS assets downloaded: {result.files_downloaded} files")

    snapshot_root = result.actual_model_path or result.target_dir

    # ---- Validate required SPURS checkpoint files ----
    required_files = [
        snapshot_root / "spurs" / ".hydra" / "config.yaml",
        snapshot_root / "spurs" / "checkpoints" / "best.ckpt",
        snapshot_root / "spurs_multi" / ".hydra" / "config.yaml",
        snapshot_root / "spurs_multi" / "checkpoints" / "best.ckpt",
    ]
    missing = [path for path in required_files if not path.exists()]
    if missing:
        raise FileNotFoundError(
            "Missing expected SPURS assets: " + ", ".join(str(p) for p in missing)
        )

    return snapshot_root
