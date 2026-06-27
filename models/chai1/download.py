import os
from pathlib import Path
from typing import Optional

from models.chai1.schema import Chai1Params
from models.commons.core.logging import get_logger
from models.commons.storage.download_helpers import r2_then_library
from models.commons.storage.downloads import get_model_dir_util

logger = get_logger(__name__)


def get_model_dir():

    return get_model_dir_util(
        base_model_slug=Chai1Params.base_model_slug,
        params_version=Chai1Params.params_version,
    )


def _create_chai1_lock_files(target_dir: Path):
    """
    Post-process Chai1 downloads to ensure .download_lock files exist.

    CRITICAL: Chai1 uses FileLock with .download_lock files to prevent concurrent downloads.
    See chai_lab/utils/paths.py::download_if_not_exists() for the actual implementation.

    How Chai1's download logic works:
    1. Before downloading 'model.pt', it acquires FileLock on 'model.download_lock'
    2. Inside the lock, it checks if 'model.pt' exists (double-check pattern)
    3. If file doesn't exist, downloads to a temp file, then renames
    4. The lock file remains after download completes

    Without these .download_lock files, Chai1's FileLock() call will create them anyway,
    but having them pre-created signals that our R2 cache contains complete downloads.
    """
    logger.info("Creating Chai1 .download_lock files...")

    # Create .download_lock files for all .pt and .apkl files
    for root, _, files in os.walk(target_dir):
        for file in files:
            if file.endswith((".pt", ".apkl")):
                lock_file = Path(root) / f"{file.rsplit('.', 1)[0]}.download_lock"
                if not lock_file.exists():
                    lock_file.touch()
                    logger.debug("Created: %s", lock_file.name)


def _init_chai1_weights(target_dir: Path) -> Path:
    """
    Initialize Chai1 weights download using library-managed approach.

    This function sets up the required environment and triggers Chai1's
    native download mechanism to ensure all files are properly downloaded.

    Args:
        target_dir: Target directory for model weights

    Returns:
        Path to directory containing downloaded weights
    """
    # Set CHAI_DOWNLOADS_DIR environment variable - critical for chai1 library
    os.environ["CHAI_DOWNLOADS_DIR"] = str(target_dir)
    logger.info("Set CHAI_DOWNLOADS_DIR to: %s", target_dir)

    try:
        import torch
        from chai_lab.chai1 import run_inference

        # Create a minimal dummy input to trigger download
        dummy_fasta = Path("/tmp/chai1_dummy.fasta")
        dummy_fasta.write_text(">protein|dummy\nAAAA\n")
        dummy_output = Path("/tmp/chai1_dummy_output")
        dummy_output.mkdir(exist_ok=True)

        # This should trigger the download
        logger.info("Triggering Chai1 download via minimal inference...")
        run_inference(
            fasta_file=dummy_fasta,
            output_dir=dummy_output,
            num_trunk_recycles=0,  # Minimal settings
            num_diffn_timesteps=1,
            seed=42,
            device=torch.device("cpu"),
            use_esm_embeddings=False,
        )

        # Clean up dummy files
        dummy_fasta.unlink(missing_ok=True)
        if dummy_output.exists():
            import shutil

            shutil.rmtree(dummy_output)

        logger.info("Chai1 library download completed")

        # Create necessary lock files after download
        _create_chai1_lock_files(target_dir)

        return target_dir

    except Exception as e:
        logger.error("Chai1 library download failed: %s", e, exc_info=True)
        raise


def _verify_chai1_structure(model_path: str):
    """Verify Chai1 model directory structure and files."""
    models_v2_dir = Path(model_path) / "models_v2"
    if not models_v2_dir.exists():
        logger.warning("Warning: models_v2 directory not found at %s", models_v2_dir)
        logger.warning("Chai1 may attempt its own download")
    else:
        pt_files = list(models_v2_dir.glob("*.pt"))
        lock_files = list(models_v2_dir.glob("*.download_lock"))
        logger.info(
            "Found %s .pt files and %s .download_lock files",
            len(pt_files),
            len(lock_files),
        )


def download_model_assets(
    base_model_slug: str,
    params_version: str,
    variant_config: Optional[dict] = None,
    sub_path: Optional[str] = None,
):
    """Download model assets."""
    logger.info("Chai1: Setting up model assets")

    expected_files = [
        "models_v2/bond_loss_input_proj.pt",
        "models_v2/confidence_head.pt",
        "models_v2/diffusion_module.pt",
        "conformers_v1.apkl",
    ]

    result = r2_then_library(
        base_model_slug=base_model_slug,
        params_version=params_version,
        sub_path=sub_path,
        library_name="chai1",
        init_fn=_init_chai1_weights,
        monitor_directories=["~/.cache/chai"],
        required_files=expected_files,
    )

    if not result.success:
        raise RuntimeError(f"Failed to acquire Chai1 model: {result.error_message}")

    if result.bypass_detected:
        logger.warning(
            "Chai1 bypass detected - model downloaded to: %s", result.bypass_locations
        )

    actual_path = result.actual_model_path or result.target_dir

    # Ensure lock files exist (in case downloaded from R2 without them)
    _create_chai1_lock_files(Path(actual_path))

    # Verify the structure
    _verify_chai1_structure(actual_path)

    logger.info("Chai1 download complete and verified at %s", actual_path)
    return actual_path
