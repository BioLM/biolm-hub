import shutil
from pathlib import Path
from typing import Optional

from models.ablang2.schema import AbLang2Params
from models.commons.core.logging import get_logger
from models.commons.storage.download_helpers import r2_then_library
from models.commons.storage.downloads import get_model_dir_util

logger = get_logger(__name__)

# Constants
REQUIRED_FILES = ["model.pt", "hparams.json"]
ABLANG2_WEIGHTS_DIR_NAME = "model-weights-ablang2-paired"  # from ablang2 library


def get_model_dir():

    return get_model_dir_util(
        base_model_slug=AbLang2Params.base_model_slug,
        params_version=AbLang2Params.params_version,
    )


def _get_ablang2_paths() -> tuple[Path, Path]:
    """Get ablang2 module dir and expected weights location"""
    import ablang2

    module_dir = Path(ablang2.__file__).parent
    weights_location = module_dir / ABLANG2_WEIGHTS_DIR_NAME
    return module_dir, weights_location


def _find_weights_dir(model_dir: Path) -> Optional[Path]:
    """Find weights directory in model_dir"""
    # Check R2 structure first, then fallback
    for candidate in [model_dir / "ablang2_paired", model_dir]:
        if candidate.exists() and all((candidate / f).exists() for f in REQUIRED_FILES):
            return candidate
    return None


def _copy_files(src_dir: Path, dst_dir: Path, files: list[str]):
    """Copy files from src to dst directory"""
    dst_dir.mkdir(parents=True, exist_ok=True)
    for filename in files:
        src = src_dir / filename
        dst = dst_dir / filename
        if src.exists() and not dst.exists():
            logger.info("Copying %s", filename)
            shutil.copy2(src, dst)


def _setup_ablang2_symlink(model_dir: Path) -> bool:
    """
    Create symlink from ablang2's hardcoded location to our weights.

    The ablang2 library expects weights at a specific location. We create
    a symlink from that location to our managed weights directory to avoid
    duplicating the weights.

    Args:
        model_dir: Directory containing our managed weights

    Returns:
        True if symlink was created successfully, False otherwise
    """
    try:
        # Get ablang2's expected location for weights
        _, expected_location = _get_ablang2_paths()

        # Find where our weights actually are
        weights_dir = _find_weights_dir(model_dir)
        if not weights_dir:
            logger.error("Cannot find weights in %s", model_dir)
            return False

        # ---- Handle existing location ----
        if expected_location.exists() or expected_location.is_symlink():
            if expected_location.is_symlink():
                # Remove old symlink
                expected_location.unlink()
                logger.info("Removed existing symlink at %s", expected_location)

            elif expected_location.is_dir():
                # Check if directory already has valid weights
                if all((expected_location / f).exists() for f in REQUIRED_FILES):
                    logger.info("Valid weights already exist at %s", expected_location)
                    return True
                # Remove invalid/incomplete directory
                shutil.rmtree(expected_location)
                logger.info("Cleaned up incomplete weights at %s", expected_location)

            else:
                # Remove unexpected file
                expected_location.unlink()

        # ---- Create new symlink ----
        expected_location.symlink_to(weights_dir.absolute())
        logger.info(
            "Created symlink: %s -> %s", expected_location, weights_dir.absolute()
        )
        return True

    except Exception as e:
        logger.error("Failed to create symlink: %s", e, exc_info=True)
        return False


def _init_ablang2_weights(target_dir: Path) -> Path:
    """
    Initialize ablang2 weights using the library-managed download strategy.

    This function:
    1. Triggers ablang2's built-in download mechanism
    2. Reorganizes downloaded files to match our R2 structure

    Args:
        target_dir: Target directory for model weights

    Returns:
        Path to directory containing reorganized weights
    """
    logger.info("Initializing ablang2 library-managed download")
    target_dir.mkdir(parents=True, exist_ok=True)

    try:
        from ablang2.pretrained import pretrained

        # Get ablang2's expected weights location
        _, ablang2_weights_dir = _get_ablang2_paths()

        # Check if weights already exist in ablang2's location
        weights_existed = ablang2_weights_dir.exists() and all(
            (ablang2_weights_dir / f).exists() for f in REQUIRED_FILES
        )

        if not weights_existed:
            logger.info("Triggering ablang2 built-in download...")
        else:
            logger.info("Using existing ablang2 weights")

        # Initialize model - this triggers download if weights don't exist
        _ = pretrained(
            model_to_use="ablang2-paired",
            random_init=False,  # Use pretrained weights
            ncpu=1,  # Single CPU for initialization
            device="cpu",  # CPU device for download
        )
        logger.info("ablang2 model initialized successfully")

        # Reorganize files to match our R2 structure
        if ablang2_weights_dir.exists():
            # Create ablang2_paired subdirectory for R2 compatibility
            ablang2_paired_dir = target_dir / "ablang2_paired"

            # Copy required files plus the original tar.gz if present
            files_to_copy = REQUIRED_FILES + ["ablang2-weights.tar.gz"]
            _copy_files(ablang2_weights_dir, ablang2_paired_dir, files_to_copy)

            logger.info("Files reorganized for R2 structure")

        return target_dir

    except ImportError as e:
        raise RuntimeError(f"AbLang2 library not available: {e}") from e


def download_model_assets(
    base_model_slug: str,
    params_version: str,
    variant_config: Optional[dict] = None,
    sub_path: Optional[str] = None,
):
    """Download ablang2 model assets with R2 caching and library-managed fallback."""
    logger.info("AbLang2: Setting up model assets")

    # Build list of directories to monitor for library bypass detection
    monitor_dirs = ["~/.cache/ablang2", "~/.ablang2"]
    try:
        module_dir, _ = _get_ablang2_paths()
        monitor_dirs.append(str(module_dir))
    except ImportError:
        pass

    required_files = [
        "ablang2_paired/model.pt",
        "ablang2_paired/hparams.json",
    ]

    result = r2_then_library(
        base_model_slug=base_model_slug,
        params_version=params_version,
        sub_path=sub_path,
        library_name="ablang2",
        init_fn=_init_ablang2_weights,
        monitor_directories=monitor_dirs,
        required_files=required_files,
    )

    if not result.success:
        raise RuntimeError(f"AbLang2 download failed: {result.error_message}") from None

    actual_dir = result.actual_model_path or result.target_dir

    if result.bypass_detected:
        logger.warning(
            "Library bypass detected - weights downloaded to unexpected location"
        )
        if result.bypass_locations:
            logger.warning("Bypass locations: %s", result.bypass_locations)

    # ---- Setup symlink for library compatibility ----
    logger.info("Setting up ablang2 library symlink...")
    if not _setup_ablang2_symlink(Path(actual_dir)):
        logger.warning("Symlink setup failed - ablang2 may re-download weights")

    # ---- Final validation ----
    weights_dir = _find_weights_dir(Path(actual_dir))
    if not weights_dir:
        raise RuntimeError(
            f"AbLang2 weights validation failed - could not find required files in {actual_dir}"
        )

    logger.info("AbLang2 model ready at %s", actual_dir)
    logger.info("Weights location: %s", weights_dir)

    for required_file in REQUIRED_FILES:
        file_path = weights_dir / required_file
        if file_path.exists():
            file_size_mb = file_path.stat().st_size / (1024 * 1024)
            logger.info("  %s: %.1f MB", required_file, file_size_mb)

    return Path(actual_dir)
