from pathlib import Path
from typing import Optional

from models.commons.core.logging import get_logger
from models.commons.storage.acquisition import (
    AcquisitionConfig,
    AcquisitionStrategy,
    CacheConfig,
    CustomSourceConfig,
    R2OnlyConfig,
)
from models.commons.storage.download_helpers import download_with_fallback
from models.commons.storage.downloads import download_archive, get_model_dir_util
from models.deepviscosity.schema import DeepViscosityParams

logger = get_logger(__name__)

# GitHub repository - pinned to specific commit for reproducibility
# To update: change PINNED_COMMIT and bump DeepViscosityParams.params_version
PINNED_COMMIT = "2d22a5bfd3905ca508fe675fd212d2d431876517"
DEEPVISCOSITY_ZIP_URL = (
    f"https://github.com/Lailabcode/DeepViscosity/archive/{PINNED_COMMIT}.zip"
)

# Directories to extract from the ZIP
# Note: StandardScaler is NOT downloaded - it's embedded directly in app.py
# to avoid sklearn version compatibility issues between serialization formats
REQUIRED_DIRS = [
    "DeepViscosity_ANN_ensemble_models",  # 102 ANN models (JSON + H5)
    "DeepSP_CNN_model",  # 3 CNN models for feature generation
]


def get_model_dir() -> Path:
    """Get the model directory for DeepViscosity assets."""
    return get_model_dir_util(
        base_model_slug=DeepViscosityParams.base_model_slug,
        params_version=DeepViscosityParams.params_version,
    )


def _create_r2_config(
    base_model_slug: str,
    params_version: str,
    sub_path: Optional[str],
    target_dir: Path,
) -> AcquisitionConfig:
    """Create acquisition config for R2 downloads (reading only)."""
    return AcquisitionConfig(
        strategy=AcquisitionStrategy.R2_ONLY,
        target_dir=target_dir,
        cache_config=CacheConfig(enable_r2_cache=False),  # Reading only from R2
        r2_config=R2OnlyConfig(
            base_model_slug=base_model_slug,
            params_version=params_version,
            model_variant=None,
            sub_path=sub_path,
        ),
    )


def _download_deepviscosity_archive(target_dir: Path, **_kwargs) -> dict:
    """Download DeepViscosity repo ZIP to target directory."""
    zip_path = target_dir / "deepviscosity.zip"

    logger.info("📥 Downloading DeepViscosity from %s...", DEEPVISCOSITY_ZIP_URL)

    metadata = download_archive(DEEPVISCOSITY_ZIP_URL, zip_path)
    metadata["source"] = "github_lailabcode"
    return metadata


def _find_repo_prefix(namelist: list) -> str:
    """Find the repository root directory prefix in the ZIP archive."""
    # GitHub ZIPs have structure: RepoName-{branch|commit}/files...
    for name in namelist:
        if "DeepViscosity_ANN_ensemble_models/" in name:
            # Extract the prefix before the directory name
            idx = name.find("DeepViscosity_ANN_ensemble_models/")
            return name[:idx]
    # Fallback to expected pattern (commit-based archive)
    return f"DeepViscosity-{PINNED_COMMIT}/"


def _extract_single_directory(
    zip_ref, namelist: list, source_prefix: str, target_subdir: Path
) -> int:
    """Extract files from a single directory within the ZIP archive."""
    import shutil

    target_subdir.mkdir(parents=True, exist_ok=True)
    files_extracted = 0

    for name in namelist:
        if not name.startswith(source_prefix) or name.endswith("/"):
            continue
        rel_name = name[len(source_prefix) :]
        if not rel_name:
            continue
        target_file = target_subdir / rel_name
        target_file.parent.mkdir(parents=True, exist_ok=True)

        # Extract file from ZIP to disk
        with zip_ref.open(name) as source:
            with open(target_file, "wb") as target:
                shutil.copyfileobj(source, target)

        files_extracted += 1

    return files_extracted


def _validate_extracted_dirs(target_dir: Path) -> None:
    """Validate that all required directories exist and are not empty."""
    for required_dir in REQUIRED_DIRS:
        dir_path = target_dir / required_dir
        if not dir_path.exists():
            raise RuntimeError(
                f"Required directory not found after extraction: {required_dir}"
            )
        if not any(dir_path.iterdir()):
            raise RuntimeError(
                f"Required directory is empty after extraction: {required_dir}"
            )


def _extract_deepviscosity_files(target_dir: Path) -> None:
    """Extract required DeepViscosity files from zip and cleanup."""
    import zipfile

    zip_path = target_dir / "deepviscosity.zip"
    logger.info("📦 Extracting DeepViscosity model files from zip archive...")

    try:
        with zipfile.ZipFile(zip_path, "r") as zip_ref:
            bad_file = zip_ref.testzip()
            if bad_file:
                raise zipfile.BadZipFile(f"Corrupted file in archive: {bad_file}")

            namelist = zip_ref.namelist()
            repo_prefix = _find_repo_prefix(namelist)
            logger.debug("Found repository prefix: %s", repo_prefix)

            for required_dir in REQUIRED_DIRS:
                source_prefix = repo_prefix + required_dir + "/"
                target_subdir = target_dir / required_dir
                files_extracted = _extract_single_directory(
                    zip_ref, namelist, source_prefix, target_subdir
                )
                logger.debug(
                    "  Extracted %s files to %s/", files_extracted, required_dir
                )

        _validate_extracted_dirs(target_dir)
        logger.info("✅ Successfully extracted model files in %s", target_dir)

    except zipfile.BadZipFile as e:
        raise RuntimeError(f"Downloaded ZIP file is corrupted: {e}") from e
    except RuntimeError:
        raise
    except Exception as e:
        raise RuntimeError(f"Failed to extract DeepViscosity files: {e}") from e
    finally:
        if zip_path.exists():
            zip_path.unlink()
            logger.info("Cleaned up temporary zip file")


def _create_custom_fallback_config(target_dir: Path) -> AcquisitionConfig:
    """Create custom acquisition config for downloading from GitHub."""
    custom_config = CustomSourceConfig(
        acquisition_fn=_download_deepviscosity_archive,
        acquisition_kwargs={},
        post_process_fn=_extract_deepviscosity_files,
        post_process_kwargs={},
        name="deepviscosity_github",
        description="Download and extract DeepViscosity from GitHub",
    )

    return AcquisitionConfig(
        strategy=AcquisitionStrategy.CUSTOM,
        target_dir=target_dir,
        custom_config=custom_config,
        cache_config=CacheConfig(enable_r2_cache=True),  # Cache to R2 after download
    )


def download_model_assets(
    base_model_slug: str,
    params_version: str,
    variant_config: Optional[dict] = None,
    sub_path: Optional[str] = None,
) -> Path:
    """
    Download DeepViscosity model assets with R2 primary and GitHub fallback.

    Assets downloaded:
    - DeepViscosity_ANN_ensemble_models/: 102 ensemble ANN models
    - DeepSP_CNN_model/: 3 CNN models for feature extraction

    Note: StandardScaler is NOT downloaded - it's embedded directly in app.py
    to avoid sklearn version compatibility issues.
    """
    logger.info("📥 DeepViscosity: Downloading model assets")

    model_dir = get_model_dir_util(
        base_model_slug=base_model_slug,
        params_version=params_version,
        sub_path=sub_path,
    )

    logger.info("📂 Target directory: %s", model_dir)

    # Primary: Try R2 cache
    logger.info("Checking R2 cache...")
    primary_config = _create_r2_config(
        base_model_slug=base_model_slug,
        params_version=params_version,
        sub_path=sub_path,
        target_dir=model_dir,
    )

    # Fallback: Download from GitHub
    fallback_config = _create_custom_fallback_config(target_dir=model_dir)

    result = download_with_fallback(
        primary_config=primary_config,
        fallback_config=fallback_config,
    )

    if not result.success:
        raise RuntimeError(
            f"Failed to download DeepViscosity model: {result.error_message}"
        )

    actual_path = result.actual_model_path or result.target_dir

    if result.cache_hit:
        logger.info("✅ Downloaded from R2 cache")
    else:
        logger.info("✅ Downloaded from GitHub (files cached to R2)")

    return actual_path
