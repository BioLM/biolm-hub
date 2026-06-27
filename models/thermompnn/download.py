import shutil
from pathlib import Path
from typing import Optional

from models.commons.storage.download_helpers import r2_then_urls
from models.commons.storage.downloads import get_model_dir_util
from models.thermompnn.config import (
    PROTEIN_MPNN_CHECKPOINT,
    THERMOMPNN_MODEL_CHECKPOINT,
)
from models.thermompnn.schema import ThermoMPNNParams

GITHUB_BASE_URL = "https://github.com/Kuhlman-Lab/ThermoMPNN/raw/main/"


def get_model_dir():
    return get_model_dir_util(
        base_model_slug=ThermoMPNNParams.base_model_slug,
        params_version=ThermoMPNNParams.params_version,
    )


def download_model_assets(  # noqa: C901
    base_model_slug: str,
    params_version: str,
    variant_config: Optional[dict] = None,
    sub_path: Optional[str] = None,
):
    """Download ThermoMPNN + ProteinMPNN checkpoints."""
    result = r2_then_urls(
        base_model_slug=base_model_slug,
        params_version=params_version,
        sub_path=sub_path,
        urls={
            THERMOMPNN_MODEL_CHECKPOINT: f"{GITHUB_BASE_URL}models/{THERMOMPNN_MODEL_CHECKPOINT}",
            f"vanilla_model_weights/{PROTEIN_MPNN_CHECKPOINT}": f"{GITHUB_BASE_URL}vanilla_model_weights/{PROTEIN_MPNN_CHECKPOINT}",
        },
    )

    if not result.success:
        raise RuntimeError(f"Model download failed: {result.error_message}")

    target_dir = Path(result.target_dir)

    # Ensure ProteinMPNN checkpoint is in vanilla_model_weights/ subdirectory
    # This is required by ThermoMPNN's transfer_model.py
    vanilla_dir = target_dir / "vanilla_model_weights"
    vanilla_dir.mkdir(parents=True, exist_ok=True)

    protein_mpnn_path = vanilla_dir / PROTEIN_MPNN_CHECKPOINT
    protein_mpnn_root = target_dir / PROTEIN_MPNN_CHECKPOINT

    # Check if file exists in root or subdirectory
    if protein_mpnn_path.exists():
        print(
            f"✅ ProteinMPNN checkpoint already in correct location: {protein_mpnn_path}"
        )
    elif protein_mpnn_root.exists():
        # Move from root to subdirectory
        print(
            f"📦 Moving {PROTEIN_MPNN_CHECKPOINT} from root to vanilla_model_weights/ subdirectory"
        )
        shutil.move(str(protein_mpnn_root), str(protein_mpnn_path))
        print(f"✅ Moved to: {protein_mpnn_path}")
    else:
        # Search recursively for the file
        found_files = list(target_dir.rglob(PROTEIN_MPNN_CHECKPOINT))
        if found_files:
            found_file = found_files[0]
            if found_file != protein_mpnn_path:
                print(
                    f"📦 Found {PROTEIN_MPNN_CHECKPOINT} at {found_file}, moving to vanilla_model_weights/"
                )
                shutil.move(str(found_file), str(protein_mpnn_path))
                print(f"✅ Moved to: {protein_mpnn_path}")
        else:
            raise FileNotFoundError(
                f"ProteinMPNN checkpoint not found. Searched in:\n"
                f"  - {protein_mpnn_path}\n"
                f"  - {protein_mpnn_root}\n"
                f"  - Recursively in {target_dir}"
            )

    # Verify final location for ProteinMPNN
    if not protein_mpnn_path.exists():
        raise FileNotFoundError(
            f"Failed to place ProteinMPNN checkpoint at {protein_mpnn_path}"
        )
    print(f"Verified ProteinMPNN checkpoint at: {protein_mpnn_path}")

    # Verify ThermoMPNN checkpoint was downloaded
    thermompnn_path = target_dir / THERMOMPNN_MODEL_CHECKPOINT
    if not thermompnn_path.exists():
        # Search recursively
        found_files = list(target_dir.rglob(THERMOMPNN_MODEL_CHECKPOINT))
        if found_files:
            thermompnn_path = found_files[0]
        else:
            raise FileNotFoundError(
                f"ThermoMPNN checkpoint not found after download. "
                f"Expected: {thermompnn_path}"
            )
    print(f"Verified ThermoMPNN checkpoint at: {thermompnn_path}")

    if result.cache_hit:
        print("✅ Downloaded from R2 cache")
    else:
        print(f"✅ Downloaded {result.files_downloaded} files")

    return result.actual_model_path or result.target_dir
