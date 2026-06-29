from pathlib import Path
from typing import Optional, Union

from models.commons.core.logging import get_logger
from models.commons.storage.download_helpers import (
    extract_model_variant,
    r2_then_hf,
)
from models.commons.storage.downloads import build_hf_snapshot_path, get_model_dir_util
from models.esm1v.config import (
    ESM1V_HF_REPO_MAP,
    ESM1V_HF_REVISION_MAP,
    ESM1V_MEMBERS,
)
from models.esm1v.schema import ESM1vParams

logger = get_logger(__name__)


def get_model_id(model_number: str):
    """Generate ESM1v model ID from model number (e.g. 'n1' -> 'esm1v_t33_650M_UR90S_1')."""
    if model_number == "all":
        return None  # No specific variant for "all"
    model_name_template = "esm1v_t33_650M_UR90S_{model_num}"
    model_number_clean = model_number.removeprefix("n")
    return model_name_template.format(model_num=model_number_clean)


def get_member_model_dir(member: str) -> Path:
    """Return the HuggingFace snapshot path for a single ensemble member ('n1'..'n5')."""
    model_variant = get_model_id(member)
    base_dir = get_model_dir_util(
        base_model_slug=ESM1vParams.base_model_slug,
        weights_version=ESM1vParams.weights_version,
        model_variant=model_variant,
    )
    return build_hf_snapshot_path(
        base_dir, ESM1V_HF_REPO_MAP[member], ESM1V_HF_REVISION_MAP[member]
    )


def get_model_dir(model_number: str = "all") -> Path:
    """Resolve the local directory for a deploy.

    For a single member ('n1'..'n5') this is the member's HuggingFace snapshot
    path. The 'all' ensemble has no single snapshot — callers must iterate the
    members via ``get_member_model_dir`` — so the base directory is returned.
    """
    if model_number == "all":
        return get_model_dir_util(
            base_model_slug=ESM1vParams.base_model_slug,
            weights_version=ESM1vParams.weights_version,
        )
    return get_member_model_dir(model_number)


def download_model_assets(
    base_model_slug: str,
    weights_version: str,
    variant_config: Optional[dict] = None,
    sub_path: Optional[str] = None,
) -> Union[Path, str]:
    """Download model assets.

    Each ensemble member is fetched from its own HuggingFace repo (R2 cache
    first, HF on miss, then cached back to R2). The 'all' variant fetches all
    five members; n1..n5 fetch a single member.
    """

    model_number = extract_model_variant(variant_config, "MODEL_NUMBER")

    members = ESM1V_MEMBERS if model_number == "all" else [model_number]

    total_files = 0
    for member in members:
        model_variant = get_model_id(member)
        result = r2_then_hf(
            base_model_slug=base_model_slug,
            weights_version=weights_version,
            model_variant=model_variant,
            sub_path=sub_path,
            hf_repo_id=ESM1V_HF_REPO_MAP[member],
            hf_revision=ESM1V_HF_REVISION_MAP[member],
            ignore_patterns=[
                "tf_model.h5"
            ],  # PyTorch loader never reads the TF weights
            required_files=["config.json"],
        )

        if not result.success:
            raise RuntimeError(
                f"Model download failed for {member}: {result.error_message}"
            )

        total_files += result.files_downloaded or 0

    logger.info("Downloaded %s files using acquisition system", total_files)
    return get_model_dir(model_number)
