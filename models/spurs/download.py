from pathlib import Path

from models.commons.core.logging import get_logger
from models.commons.storage.download_helpers import r2_then_hf
from models.commons.storage.downloads import get_model_dir_util
from models.spurs.config import HF_REPO_ID, HF_REVISION
from models.spurs.schema import SpursParams

logger = get_logger(__name__)


def get_model_dir(sub_path: str | None = None) -> Path:
    """Resolve the local directory where SPURS weights should be stored."""
    return get_model_dir_util(
        base_model_slug=SpursParams.base_model_slug,
        weights_version=SpursParams.weights_version,
        model_variant=None,
        sub_path=sub_path,
    )


def download_model_assets(
    base_model_slug: str,
    weights_version: str,
    variant_config: dict | None = None,
    sub_path: str | None = None,
) -> Path:
    """Download SPURS model assets."""
    logger.info("SPURS: Downloading model assets")

    result = r2_then_hf(
        base_model_slug=base_model_slug,
        weights_version=weights_version,
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
        logger.info("SPURS assets restored from cache")
    else:
        logger.info("SPURS assets downloaded: %s files", result.files_downloaded)

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
