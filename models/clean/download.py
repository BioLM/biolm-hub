import shutil
import zipfile
from pathlib import Path
from typing import Optional

from models.clean.schema import CLEANParams
from models.commons.storage.acquisition import (
    AcquisitionConfig,
    AcquisitionStrategy,
    CacheConfig,
    CustomSourceConfig,
    R2OnlyConfig,
)
from models.commons.storage.download_helpers import download_with_fallback
from models.commons.storage.downloads import get_model_dir_util

# Google Drive file ID for pretrained weights
# Source: https://drive.google.com/file/d/1kwYd4VtzYuMvJMWXy6Vks91DSUAOcKpZ/view
GDRIVE_FILE_ID = "1kwYd4VtzYuMvJMWXy6Vks91DSUAOcKpZ"

# GitHub raw URL for split100.csv (training data with EC-ID mappings)
# This file is ~89MB and contains Entry, EC number, Sequence columns
GITHUB_SPLIT100_CSV_URL = (
    "https://raw.githubusercontent.com/tttianhao/CLEAN/main/app/data/split100.csv"
)

# Files extracted from pretrained.zip
PRETRAINED_FILES = [
    "split100.pth",  # CLEAN LayerNormNet weights
    "100.pt",  # Precomputed EC cluster center embeddings
    "gmm_ensumble.pkl",  # GMM ensemble for confidence estimation
]

# All required files for CLEAN
REQUIRED_FILES = PRETRAINED_FILES + ["split100.csv"]


def get_model_dir() -> Path:
    """
    Get the model directory for CLEAN assets.

    Used by app.py to locate downloaded weights.

    Returns:
        Path to model directory
    """
    return get_model_dir_util(
        base_model_slug=CLEANParams.base_model_slug,
        params_version=CLEANParams.params_version,
    )


def _download_from_gdrive(file_id: str, output_path: Path) -> None:
    """
    Download a file from Google Drive.

    Uses gdown library which handles large file confirmation.

    Args:
        file_id: Google Drive file ID
        output_path: Path to save the downloaded file
    """
    import gdown

    url = f"https://drive.google.com/uc?id={file_id}"
    print(f"Downloading from Google Drive: {url}")
    gdown.download(url, str(output_path), quiet=False)


def _download_from_url(url: str, output_path: Path) -> None:
    """
    Download a file from a URL.

    Args:
        url: URL to download from
        output_path: Path to save the downloaded file
    """
    import urllib.request

    print(f"Downloading from URL: {url}")
    urllib.request.urlretrieve(url, output_path)


def _download_clean_assets(target_dir: Path, **_kwargs) -> dict:
    """
    Download CLEAN assets from original sources.

    This is the acquisition function for CustomSourceConfig.
    Downloads:
    1. pretrained.zip from Google Drive (contains model weights)
    2. split100.csv from GitHub (training data)

    Args:
        target_dir: Directory where files should be downloaded
        **_kwargs: Additional arguments (unused)

    Returns:
        Metadata dictionary with download information
    """
    target_dir.mkdir(parents=True, exist_ok=True)

    # Download pretrained.zip from Google Drive
    zip_path = target_dir / "pretrained.zip"
    _download_from_gdrive(GDRIVE_FILE_ID, zip_path)

    # Download split100.csv from GitHub
    csv_path = target_dir / "split100.csv"
    _download_from_url(GITHUB_SPLIT100_CSV_URL, csv_path)

    return {
        "source": "google_drive_and_github",
        "gdrive_file_id": GDRIVE_FILE_ID,
        "github_csv_url": GITHUB_SPLIT100_CSV_URL,
    }


def _extract_clean_files(target_dir: Path) -> None:
    """
    Extract CLEAN files from downloaded zip and clean up.

    This is the post-processing function for CustomSourceConfig.
    Extracts pretrained weights from the ZIP file.

    Args:
        target_dir: Directory containing the downloaded files

    Raises:
        RuntimeError: If extraction fails or files are missing
    """
    zip_path = target_dir / "pretrained.zip"

    print("Extracting CLEAN pretrained weights from zip archive...")

    try:
        with zipfile.ZipFile(zip_path, "r") as zip_ref:
            # Verify ZIP integrity
            bad_file = zip_ref.testzip()
            if bad_file:
                raise zipfile.BadZipFile(f"Corrupted file in archive: {bad_file}")

            namelist = zip_ref.namelist()
            print(f"ZIP contains {len(namelist)} files")

            # Extract each required pretrained file
            for filename in PRETRAINED_FILES:
                # Find the file in the ZIP (may be in a subdirectory)
                matching_files = [n for n in namelist if n.endswith(filename)]
                if not matching_files:
                    raise FileNotFoundError(
                        f"Required file {filename} not found in zip archive"
                    )

                zip_internal_path = matching_files[0]
                target_file = target_dir / filename

                # Extract using streaming copy
                with zip_ref.open(zip_internal_path) as source:
                    with open(target_file, "wb") as target:
                        shutil.copyfileobj(source, target)

                print(f"  Extracted {filename}")

        # Validate all files exist and are non-empty
        for filename in REQUIRED_FILES:
            filepath = target_dir / filename
            if not filepath.exists():
                raise RuntimeError(f"Missing required file: {filename}")
            if filepath.stat().st_size == 0:
                raise RuntimeError(f"File is empty: {filename}")

        print(f"Successfully extracted and validated {len(REQUIRED_FILES)} files")

    except zipfile.BadZipFile as e:
        raise RuntimeError(f"Downloaded ZIP file is corrupted: {e}") from e
    except Exception as e:
        raise RuntimeError(f"Failed to extract CLEAN files: {e}") from e
    finally:
        # Clean up zip file
        if zip_path.exists():
            zip_path.unlink()
            print("Cleaned up temporary zip file")


def _create_r2_config(
    base_model_slug: str,
    params_version: str,
    sub_path: Optional[str],
    target_dir: Path,
) -> AcquisitionConfig:
    """
    Create acquisition config for R2 downloads (primary/cache).

    Args:
        base_model_slug: Model slug
        params_version: Model version
        sub_path: Optional sub-path
        target_dir: Target directory

    Returns:
        AcquisitionConfig for R2 strategy
    """
    return AcquisitionConfig(
        strategy=AcquisitionStrategy.R2_ONLY,
        target_dir=target_dir,
        cache_config=CacheConfig(
            enable_r2_cache=True,
        ),
        r2_config=R2OnlyConfig(
            base_model_slug=base_model_slug,
            params_version=params_version,
            model_variant=None,  # CLEAN has no variants
            sub_path=sub_path,
        ),
    )


def _create_custom_fallback_config(target_dir: Path) -> AcquisitionConfig:
    """
    Create custom acquisition config for downloading from original sources.

    Uses CustomSourceConfig to handle Google Drive + GitHub downloads.

    Args:
        target_dir: Directory where files should be saved

    Returns:
        AcquisitionConfig with custom strategy
    """
    custom_config = CustomSourceConfig(
        acquisition_fn=_download_clean_assets,
        acquisition_kwargs={},
        post_process_fn=_extract_clean_files,
        post_process_kwargs={},
        name="clean_gdrive_github",
        description="Download CLEAN weights from Google Drive and split100.csv from GitHub",
    )

    return AcquisitionConfig(
        strategy=AcquisitionStrategy.CUSTOM,
        target_dir=target_dir,
        custom_config=custom_config,
        cache_config=CacheConfig(
            enable_r2_cache=True,  # Cache to R2 for future builds
        ),
    )


def download_model_assets(
    base_model_slug: str,
    params_version: str,
    variant_config: Optional[dict] = None,
    sub_path: Optional[str] = None,
) -> Path:
    """
    Download CLEAN model assets with R2 primary and Google Drive/GitHub fallback.

    This function implements a two-stage download strategy:
    1. Primary: Try to fetch from R2 cache (fast, if previously cached)
    2. Fallback: Download from original sources (Google Drive + GitHub)
       - pretrained.zip from Google Drive (model weights, cluster centers, GMM)
       - split100.csv from GitHub (EC-ID training mappings)

    The fallback uses CustomSourceConfig to handle downloads and extraction,
    with automatic R2 caching of the extracted files for future use.

    Args:
        base_model_slug: Base model identifier ("clean")
        params_version: Model version ("v1")
        variant_config: Unused (CLEAN has no variants)
        sub_path: Optional subdirectory path

    Returns:
        Path to downloaded model assets directory

    Raises:
        RuntimeError: If both R2 and fallback download strategies fail
    """
    print("Downloading CLEAN model assets...")

    # Get target directory (no variant for CLEAN - single variant model)
    model_dir = get_model_dir_util(
        base_model_slug=base_model_slug,
        params_version=params_version,
        sub_path=sub_path,
    )

    print(f"Target directory: {model_dir}")

    # Stage 1: Try R2 cache (fast path)
    print("Checking R2 cache...")
    primary_config = _create_r2_config(
        base_model_slug=base_model_slug,
        params_version=params_version,
        sub_path=sub_path,
        target_dir=model_dir,
    )

    # Stage 2: Fallback to Google Drive + GitHub
    fallback_config = _create_custom_fallback_config(target_dir=model_dir)

    # Execute download with fallback
    result = download_with_fallback(
        primary_config=primary_config,
        fallback_config=fallback_config,
    )

    if not result.success:
        raise RuntimeError(f"Failed to download CLEAN model: {result.error_message}")

    if result.cache_hit:
        print("Downloaded from R2 cache")
    else:
        print("Downloaded from Google Drive + GitHub (files cached to R2)")

    return result.actual_model_path or result.target_dir
