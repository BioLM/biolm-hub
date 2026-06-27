"""Download module for RFdiffusion3 model weights.

Based on RosettaCommons/foundry implementation (BSD 3-Clause License).
Uses foundry CLI tool to download checkpoints from their registry.
"""

import subprocess
from pathlib import Path
from typing import Optional

from models.commons.core.logging import get_logger
from models.commons.storage.acquisition import (
    AcquisitionConfig,
    AcquisitionStrategy,
    CacheConfig,
    R2OnlyConfig,
    ValidationConfig,
)
from models.commons.storage.downloads import get_model_dir_util
from models.rfd3.schema import RFD3Params

logger = get_logger(__name__)

# RFD3 uses foundry's checkpoint registry
# Install with: foundry install rfd3 --checkpoint-dir <path>
# Default location: ~/.foundry/checkpoints
# Registry: foundry list-available


def get_model_dir() -> Path:
    """Get model directory for RFdiffusion3.

    Returns:
        Path to model directory
    """
    return get_model_dir_util(
        base_model_slug=RFD3Params.base_model_slug,
        params_version=RFD3Params.params_version,
    )


def _install_via_foundry_cli(checkpoint_dir: Path) -> bool:
    """Install RFD3 checkpoint using foundry CLI tool.

    Args:
        checkpoint_dir: Directory where checkpoint should be installed

    Returns:
        True if successful, False otherwise
    """
    try:
        logger.info("Installing RFD3 checkpoint via foundry CLI...")
        checkpoint_dir.mkdir(parents=True, exist_ok=True)

        # Run: foundry install rfd3 --checkpoint-dir <path>
        result = subprocess.run(
            ["foundry", "install", "rfd3", "--checkpoint-dir", str(checkpoint_dir)],
            capture_output=True,
            text=True,
            timeout=1800,  # 30 minutes timeout
        )

        if result.returncode == 0:
            logger.info("Foundry CLI installation successful")
            logger.debug("stdout: %s", result.stdout)
            logger.debug("stderr: %s", result.stderr)

            # List what was actually downloaded
            import os

            logger.debug("Contents of %s:", checkpoint_dir)
            for root, _dirs, files in os.walk(checkpoint_dir):
                level = root.replace(str(checkpoint_dir), "").count(os.sep)
                indent = " " * 2 * level
                logger.debug("%s%s/", indent, os.path.basename(root))
                subindent = " " * 2 * (level + 1)
                for file in files:
                    logger.debug("%s%s", subindent, file)

            return True
        else:
            logger.error("Foundry CLI installation failed: %s", result.stderr)
            return False

    except subprocess.TimeoutExpired:
        logger.error("Foundry CLI installation timed out", exc_info=True)
        return False
    except FileNotFoundError:
        logger.error("Foundry CLI not found - is rc-foundry installed?", exc_info=True)
        return False
    except Exception as e:
        logger.error("Foundry CLI installation error: %s", e, exc_info=True)
        return False


def download_model_assets(
    base_model_slug: str,
    params_version: str,
    variant_config: Optional[dict] = None,
    sub_path: Optional[str] = None,
) -> Path:
    """Download RFdiffusion3 model assets with R2 caching and foundry CLI fallback.

    Strategy:
    1. First attempt: Download from R2 cache (fastest)
    2. Fallback: Use foundry CLI to download from checkpoint registry
    3. Cache successful foundry downloads to R2 for future use

    Args:
        base_model_slug: The base model identifier ("rfd3")
        params_version: Version of the model parameters
        variant_config: Not used for RFD3 (no variants)
        sub_path: Optional subdirectory path

    Returns:
        Path to the downloaded model directory

    Raises:
        RuntimeError: If download fails

    Note:
        Uses foundry's checkpoint registry via `foundry install rfd3`.
        Run `foundry list-available` to see available checkpoints.
    """
    model_variant = None  # RFD3 has no variants

    # Get target model directory
    model_dir = get_model_dir_util(
        base_model_slug=base_model_slug,
        params_version=params_version,
        model_variant=model_variant,
        sub_path=sub_path,
    )

    logger.info("RFdiffusion3: Setting up model assets")
    logger.info("   Target directory: %s", model_dir)

    # Expected checkpoint file (foundry installs as rfd3_latest.ckpt)
    checkpoint_filename = "rfd3_latest.ckpt"
    checkpoint_path = model_dir / checkpoint_filename

    # ---- Primary strategy: R2 cache ----
    primary_config = AcquisitionConfig(
        strategy=AcquisitionStrategy.R2_ONLY,
        target_dir=model_dir,
        cache_config=CacheConfig(
            enable_r2_cache=False
        ),  # We're reading from R2, not writing
        validation_config=ValidationConfig(required_files=[checkpoint_filename]),
        r2_config=R2OnlyConfig(
            base_model_slug=base_model_slug,
            params_version=params_version,
            model_variant=model_variant,
            sub_path=sub_path,
        ),
    )

    # Try R2 first
    logger.info("[download_helpers.py] Attempting primary acquisition strategy...")
    from models.commons.storage.acquisition import acquire_model_weights

    primary_result = acquire_model_weights(primary_config)

    if primary_result.success:
        logger.info("Downloaded %s files from R2", primary_result.files_downloaded)
        return primary_result.actual_model_path or primary_result.target_dir

    logger.warning("R2 cache miss, trying foundry CLI...")

    # ---- Fallback: Use foundry CLI (only once) ----
    logger.warning("R2 cache miss, trying foundry CLI fallback...")
    if _install_via_foundry_cli(model_dir):
        # Verify checkpoint exists
        if checkpoint_path.exists():
            logger.info("RFD3 checkpoint installed at: %s", checkpoint_path)

            # Skip R2 upload during image build (too slow, causes timeouts)
            # R2 caching will happen at runtime in setup_model() when model is first used
            # This ensures future builds can use R2 cache without blocking current build
            import os

            is_image_build = os.environ.get("MODAL_IMAGE_BUILD", "0") == "1"

            if not is_image_build:
                # Only cache to R2 at runtime, not during image build
                try:
                    from models.commons.storage.r2_utils import R2Utils
                    from models.commons.util.config import r2_bucket_name

                    r2_prefix = f"model-store/{base_model_slug}/{params_version}"
                    logger.info("Caching checkpoint to R2 at %s...", r2_prefix)
                    success = R2Utils.upload_to_r2_atomic(
                        source_dir=model_dir,
                        r2_prefix=r2_prefix,
                        bucket_name=r2_bucket_name,
                        create_manifest=True,
                    )
                    if success:
                        logger.info(
                            "Cached to R2 successfully - future downloads will use R2 cache"
                        )
                    else:
                        logger.warning(
                            "Failed to cache to R2 (non-fatal) - will fallback again next time"
                        )
                except Exception as e:
                    logger.warning("Failed to cache to R2 (non-fatal): %s", e)
            else:
                logger.info(
                    "Skipping R2 upload during image build (will cache at runtime)"
                )

            return model_dir
        else:
            raise RuntimeError(
                f"Foundry CLI succeeded but checkpoint not found at {checkpoint_path}"
            )

    raise RuntimeError(
        "Failed to download RFdiffusion3 model assets: "
        "Both R2 cache and foundry CLI download failed. "
        "Ensure rc-foundry[rfd3] is installed in the Modal image."
    )
