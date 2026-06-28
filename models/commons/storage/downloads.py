"""
Low-Level Download Operations and Path Utilities
===============================================

Purpose:
Foundation layer for path resolution and primitive download operations. This module
is used by the acquisition engine; models typically call the higher-level helpers.

Role in Flow:
Layer 3 (Bottom) → acquisition.py → download_helpers.py → models/*/download.py

What this module provides:
- get_model_dir_util(): Standardized model directory construction. This path must
  be the exact directory where the model expects weights at runtime. R2 caching
  also uses this path to derive the R2 prefix, ensuring restores land in-place.
- download_model_from_r2(): Idempotent R2 sync with simple filtering and retry.
- download_from_hf(): Hugging Face snapshot download that returns the actual
  snapshot directory. Callers must use the returned path when loading models.
- verify_model_dir(): Lightweight post-download validation (presence + files).
- setup_hf_cache_env(): Configure HF cache env vars to point under model_dir
- build_hf_snapshot_path(): Build deterministic HuggingFace snapshot paths
- download_archive(): Stream download zip/archive files with progress reporting
- extract_archive_subtree(): Extract subset of archive files matching a prefix
  (used by some library-managed flows to place files correctly).

Notes:
- Models should prefer download_helpers or acquisition; importing this module
  directly is typically only for path utilities.
- HF downloads return a snapshot directory under model_dir; acquisition preserves
  that structure when caching/restoring via R2 so later restores match exactly.
"""

import os
import zipfile
from collections.abc import Callable
from pathlib import Path
from typing import NamedTuple, Optional

import requests

from models.commons.core.logging import get_logger
from models.commons.util.config import r2_bucket_name, r2_model_store_dir

logger = get_logger(__name__)

# Files at or below this size use put_object (single HTTP PUT, no thread pool).
# Raising this above ~50MB risks high memory usage since put_object loads the
# entire file into memory.  10MB is a safe, fast sweet spot.
UPLOAD_SMALL_FILE_THRESHOLD = 10 * 1024 * 1024  # 10MB

# Downloads above this size use TransferConfig with retries and optimized
# concurrency.  Matches the multipart threshold in get_r2_upload_transfer_config.
DOWNLOAD_LARGE_FILE_THRESHOLD = 100 * 1024 * 1024  # 100MB


def download_file_with_size_optimization(
    r2_client, bucket_name: str, key: str, local_path: str, file_size: int = 0
) -> None:
    """
    Download file with optimization for large files (>100MB).

    This function centralizes the logic for choosing between regular download
    and optimized TransferConfig download based on file size.

    Args:
        r2_client: Boto3 R2 client
        bucket_name: R2 bucket name
        key: R2 object key
        local_path: Local file path (as string)
        file_size: File size in bytes (used for optimization decision)
    """
    if file_size > DOWNLOAD_LARGE_FILE_THRESHOLD:
        from models.commons.storage.r2 import get_r2_transfer_config

        transfer_config = get_r2_transfer_config()
        r2_client.download_file(bucket_name, key, local_path, Config=transfer_config)
    else:
        r2_client.download_file(bucket_name, key, local_path)


def upload_file_with_size_optimization(
    r2_client,
    bucket_name: str,
    key: str,
    local_path: str,
    file_size: Optional[int] = None,
) -> None:
    """
    Upload file with size-based optimization, symmetric to download_file_with_size_optimization.

    Small files (<=10MB) use put_object for zero thread overhead.
    Large files use upload_file with TransferConfig for streaming multipart upload.

    Args:
        r2_client: Boto3 R2 client
        bucket_name: R2 bucket name
        key: R2 object key
        local_path: Local file path (as string)
        file_size: File size in bytes. None means "stat the file to find out".
    """
    if file_size is None:
        file_size = Path(local_path).stat().st_size

    if file_size <= UPLOAD_SMALL_FILE_THRESHOLD:
        with open(local_path, "rb") as f:
            r2_client.put_object(Bucket=bucket_name, Key=key, Body=f)
    else:
        from models.commons.storage.r2 import get_r2_upload_transfer_config

        r2_client.upload_file(
            local_path, bucket_name, key, Config=get_r2_upload_transfer_config()
        )


def get_model_dir_util(
    base_model_slug: str,
    params_version: str,
    model_variant: Optional[str] = None,
    sub_path: Optional[str] = None,
) -> Path:
    """
    Constructs standardized local directory path for model assets.
    Single responsibility: Path resolution only.

    Args:
        base_model_slug: The base model identifier (e.g., "esm2", "ablang2")
        params_version: Version of the model parameters (e.g., "v1", "v2")
        model_variant: Optional model variant/size (e.g., "8b", "250m")
        sub_path: Optional subdirectory path (e.g., "checkpoints")

    Returns:
        Path object representing the model directory

    Examples:
        >>> get_model_dir_util("esm2", "v1")
        Path("/model-store/esm2/v1")

        >>> get_model_dir_util("esm_if1", "v1", sub_path="checkpoints")
        Path("/model-store/esm_if1/v1/checkpoints")
    """
    path_parts = [f"/{r2_model_store_dir}", base_model_slug, params_version]
    if model_variant:
        path_parts.append(model_variant)
    if sub_path:
        path_parts.append(sub_path)

    model_dir = Path("/".join(path_parts))
    logger.info("📂 [downloads.py] Resolved model directory: %s", model_dir)
    return model_dir


def verify_model_dir(
    model_dir: Path, required_files: Optional[list[str]] = None
) -> bool:
    """
    Simple verification that directory exists and has content.

    Args:
        model_dir: Directory to verify
        required_files: Optional list of files with relative paths from model_dir
                       (e.g., ["model.safetensors", "config.json"] or
                        ["snapshots/abc123/model.bin"])

    Returns:
        True if verification passes

    Raises:
        RuntimeError: If verification fails with detailed error message

    Examples:
        >>> verify_model_dir(Path("/models/esm2"))
        True

        >>> verify_model_dir(
        ...     Path("/models/esm2"),
        ...     required_files=["model.pt", "config.json"]
        ... )
        True
    """
    logger.info("🔎 [downloads.py] Verifying model directory: %s", model_dir)

    if not model_dir.exists():
        raise RuntimeError(f"❌ Model directory does not exist: {model_dir}")

    # Check if directory has any content (files or subdirectories)
    if not any(model_dir.iterdir()):
        raise RuntimeError(f"❌ Model directory is empty: {model_dir}")

    # Check for specific required files if provided
    # Caller is responsible for providing correct relative paths
    if required_files:
        missing_files = []
        for req_file in required_files:
            file_path = model_dir / req_file
            if not file_path.exists():
                missing_files.append(req_file)

        if missing_files:
            raise RuntimeError(f"❌ Required files missing: {', '.join(missing_files)}")

    logger.info("✅ [downloads.py] Verification successful for %s", model_dir)
    return True


def _should_skip_file(
    local_file_path: Path, remote_size: int, force_download: bool
) -> bool:
    """Check if file should be skipped based on idempotency rules."""
    if force_download or not local_file_path.exists():
        return False

    local_size = local_file_path.stat().st_size
    if local_size == remote_size:
        return True

    logger.warning(
        f"  - Size mismatch for {local_file_path.name}: "
        f"local={local_size/1024**3:.2f}GB, remote={remote_size/1024**3:.2f}GB"
    )
    return False


def _filter_r2_objects(
    r2_objects: list, filter_func: Optional[Callable[[str], bool]]
) -> list:
    """Filter R2 objects based on criteria."""
    # Lazy import avoids a module-load cycle (r2_utils imports downloads).
    from models.commons.storage.r2_utils import R2Utils

    cache_dotfiles = (R2Utils.COMPLETION_MARKER, R2Utils.MANIFEST_FILE)

    files_to_process = []
    for obj in r2_objects:
        full_key = obj["Key"]

        # Skip directories
        if full_key.endswith("/"):
            continue

        # Never materialize the atomic cache-control dotfiles
        # (.r2_cache_complete / .r2_manifest.json) into the model directory.
        if full_key.rsplit("/", 1)[-1] in cache_dotfiles:
            continue

        # Apply filter if provided
        if filter_func and not filter_func(full_key):
            continue

        files_to_process.append(obj)

    return files_to_process


def _download_single_file(
    r2_client,
    bucket_name: str,
    full_key: str,
    local_file_path: Path,
    remote_size: int,
    idx: int,
    total: int,
):
    """Download a single file from R2 with optimized configuration for large files."""
    local_file_path.parent.mkdir(parents=True, exist_ok=True)

    file_gb = remote_size / (1024**3)
    status = "📝 Updating" if local_file_path.exists() else "📥 Downloading"
    logger.info(f"  [{idx}/{total}] {status} {local_file_path.name} ({file_gb:.2f} GB)")

    # Use optimized download based on file size
    download_file_with_size_optimization(
        r2_client, bucket_name, full_key, str(local_file_path), remote_size
    )
    if (
        file_gb > 0.5 and remote_size > 100 * 1024 * 1024
    ):  # Only log for large files > 500MB
        logger.debug(
            f"    ✅ Used optimized transfer config for large file ({file_gb:.2f} GB)"
        )


class R2SyncResult(NamedTuple):
    """Result of an R2 sync operation.

    Attributes:
        downloaded: Number of files newly downloaded.
        skipped: Number of files skipped because they already exist locally
            with the correct size (idempotent hits).
        total: Total number of files considered after filtering.
    """

    downloaded: int
    skipped: int
    total: int


def download_model_from_r2(
    model_dir: Path,
    filter_func: Optional[Callable[[str], bool]] = None,
    force_download: bool = False,
) -> R2SyncResult:
    """
    Idempotent R2 download with pagination support for any number of files.
    Optimized for large files (up to 8GB) with size-based idempotency.

    Args:
        model_dir: Local directory to download files into
        filter_func: Optional function that takes R2 key and returns True to download
        force_download: If True, re-download even if file exists with same size

    Returns:
        R2SyncResult with downloaded, skipped, and total file counts.
        When all files are already present (idempotent re-run), downloaded=0
        but skipped>0 and total>0 -- this is a success, not a failure.

    Raises:
        Exception: If R2 download fails

    Examples:
        >>> # Download all files
        >>> result = download_model_from_r2(Path("/models/esm2"))
        >>> result.downloaded
        15

        >>> # Download only checkpoint files
        >>> result = download_model_from_r2(
        ...     Path("/models/mpnn"),
        ...     filter_func=lambda key: key.endswith(".ckpt")
        ... )
        >>> result.downloaded
        3
    """
    from models.commons.storage.r2 import get_r2_client

    logger.info("▶️ [downloads.py] Starting R2 sync for directory: %s", model_dir)
    model_dir.mkdir(parents=True, exist_ok=True)

    r2_client = get_r2_client()
    r2_dir_prefix = str(model_dir).lstrip("/")

    # Ensure prefix ends with / for directory listing
    if not r2_dir_prefix.endswith("/"):
        r2_dir_prefix += "/"

    try:
        # Use paginator for robustness - handles any number of files
        paginator = r2_client.get_paginator("list_objects_v2")
        pages = paginator.paginate(Bucket=r2_bucket_name, Prefix=r2_dir_prefix)

        # Collect all objects across pages
        r2_objects = []
        for page in pages:
            r2_objects.extend(page.get("Contents", []))

        if not r2_objects:
            logger.warning(
                "⚠️ [downloads.py] No files found in R2 at prefix: '%s'", r2_dir_prefix
            )
            return R2SyncResult(downloaded=0, skipped=0, total=0)

        logger.info("🔍 [downloads.py] Found %s objects in R2", len(r2_objects))

        # Pre-filter to get accurate counts
        files_to_process = _filter_r2_objects(r2_objects, filter_func)

        if not files_to_process:
            logger.info("✅ [downloads.py] No files to process after filtering")
            return R2SyncResult(downloaded=0, skipped=0, total=0)

        logger.info(
            "📋 [downloads.py] Processing %s files after filtering",
            len(files_to_process),
        )

        download_count = 0
        skip_count = 0

        # Process files with accurate progress counter
        for idx, obj in enumerate(files_to_process, 1):
            full_key = obj["Key"]
            remote_size = obj["Size"]
            local_file_path = Path("/") / full_key

            # Check if should skip
            if _should_skip_file(local_file_path, remote_size, force_download):
                skip_count += 1
                continue

            # Download the file
            _download_single_file(
                r2_client,
                r2_bucket_name,
                full_key,
                local_file_path,
                remote_size,
                idx,
                len(files_to_process),
            )
            download_count += 1

        # Summary
        logger.info("✅ [downloads.py] R2 sync complete:")
        logger.info("   • Downloaded: %s files", download_count)
        logger.info("   • Skipped (up-to-date): %s files", skip_count)
        logger.info("   • Total processed: %s files", len(files_to_process))

        return R2SyncResult(
            downloaded=download_count,
            skipped=skip_count,
            total=len(files_to_process),
        )

    except Exception as e:
        logger.error("❌ [downloads.py] R2 sync failed: %s", e, exc_info=True)
        raise


def download_from_hf(
    model_dir: Path,
    hf_repo_id: str,
    hf_revision: Optional[str] = None,
    allow_patterns: Optional[list[str]] = None,
    ignore_patterns: Optional[list[str]] = None,
    repo_type: str = "model",
) -> Path:
    """
    Downloads model from HuggingFace Hub, caching to a subdirectory within model_dir.

    IMPORTANT: When hf_revision is provided as a full commit hash (40 chars), the
    snapshot path is deterministic and can be rebuilt without downloading.

    Args:
        model_dir: Base directory to use as the root for the HF cache
        hf_repo_id: HuggingFace repository ID (e.g., "facebook/esm2_t6_8M_UR50D")
        hf_revision: Git revision to download (tag, branch, or commit hash).
                    For deterministic paths, use full 40-char commit hash.
        allow_patterns: List of file patterns to include (e.g., ["*.bin", "*.json"])
        ignore_patterns: List of file patterns to exclude

    Returns:
        Path: The exact path to the downloaded snapshot directory.
              When revision is a full commit hash, this path is deterministic:
              {model_dir}/models--{org}--{repo}/snapshots/{revision}/

    Raises:
        Exception: If download fails

    Examples:
        >>> # Download with deterministic path (using commit hash)
        >>> snapshot_dir = download_from_hf(
        ...     Path("/models/nt"),
        ...     "InstaDeepAI/nucleotide-transformer-v2-250m",
        ...     hf_revision="4cc2b6eaa0cc45e3e3a7d7ea7e427286e931a1f3"  # Full hash
        ... )
        >>> # Path is deterministic: /models/nt/models--InstaDeepAI--nucleotide-transformer-v2-250m/snapshots/4cc2b6eaa0cc45e3e3a7d7ea7e427286e931a1f3/
    """
    from huggingface_hub import snapshot_download

    logger.info("▶️ [downloads.py] Downloading from HuggingFace: %s", hf_repo_id)
    if hf_revision:
        logger.info("   📌 [downloads.py] Revision: %s", hf_revision)
        # Check if revision looks like a full commit hash (40 hex chars)
        if len(hf_revision) == 40 and all(
            c in "0123456789abcdef" for c in hf_revision.lower()
        ):
            logger.info("   🔒 [downloads.py] Using deterministic commit hash")
    if allow_patterns:
        logger.info("   ✅ [downloads.py] Including patterns: %s", allow_patterns)
    if ignore_patterns:
        logger.info("   ❌ [downloads.py] Excluding patterns: %s", ignore_patterns)

    logger.info("   📁 [downloads.py] Cache root directory: %s", model_dir)
    logger.info("   ⏳ [downloads.py] HuggingFace Hub will show download progress...")

    try:
        # snapshot_download returns the actual snapshot path
        local_dir = snapshot_download(
            repo_id=hf_repo_id,
            revision=hf_revision,
            cache_dir=str(model_dir),
            allow_patterns=allow_patterns,
            ignore_patterns=ignore_patterns,
            local_files_only=False,
            resume_download=True,
            repo_type=repo_type,
        )

        snapshot_path = Path(local_dir)
        logger.info("✅ [downloads.py] Downloaded to snapshot: %s", snapshot_path)

        # If we have a deterministic revision, verify the path matches expected structure
        if hf_revision and len(hf_revision) == 40:
            expected_path = build_hf_snapshot_path(
                model_dir, hf_repo_id, hf_revision, repo_type=repo_type
            )
            if snapshot_path != expected_path:
                logger.warning(
                    "   ⚠️ [downloads.py] Warning: Snapshot path differs from expected"
                )
                logger.warning("      Expected: %s", expected_path)
                logger.warning("      Actual:   %s", snapshot_path)

        return snapshot_path

    except Exception as e:
        logger.error(
            "❌ [downloads.py] HuggingFace download failed: %s", e, exc_info=True
        )
        raise


def setup_hf_cache_env(model_dir: Path) -> None:
    """
    Sets up ALL relevant environment variables for library-managed HF downloads.
    Must be called BEFORE importing model libraries (e.g., ESM3, ESMC).

    Args:
        model_dir: Directory to use as HuggingFace cache

    Examples:
        >>> # MUST set environment BEFORE importing
        >>> setup_hf_cache_env(Path("/models/esm3"))
        >>> # NOW safe to import
        >>> from esm.models.esm3 import ESM3
        >>> model = ESM3.from_pretrained("esm3-sm-open-v1")
    """
    cache_path = str(model_dir)

    # Set all HF-related environment variables for maximum compatibility
    env_vars = {
        # Latest paths used by HF
        "HF_HUB_CACHE": cache_path,
        "HF_HOME": cache_path,
        # Legacy paths, but some tools still check
        "TRANSFORMERS_CACHE": cache_path,  # deprecated
        "HUGGINGFACE_HUB_CACHE": cache_path,
    }

    for var, value in env_vars.items():
        os.environ[var] = value

    logger.info(
        "📌 [downloads.py] Set HuggingFace cache environment to: %s", cache_path
    )
    logger.info("   [downloads.py] Variables set: %s", ", ".join(env_vars.keys()))


def build_hf_snapshot_path(
    model_dir: Path,
    hf_repo_id: str,
    hf_revision: str,
    repo_type: str = "model",
) -> Path:
    """
    Build the deterministic HuggingFace snapshot path.

    This function constructs the path where HuggingFace will store a model snapshot
    when given a specific revision. This allows us to deterministically know where
    files will be without having to search for them.

    Args:
        model_dir: Base cache directory
        hf_repo_id: Repository ID (e.g., "facebook/esm2")
        hf_revision: Git revision (should be full 40-char commit hash for determinism)
        repo_type: HuggingFace repo type — ``"model"`` or ``"dataset"``

    Returns:
        Path to the snapshot directory

    Example:
        >>> build_hf_snapshot_path(
        ...     Path("/models/nt"),
        ...     "InstaDeepAI/nucleotide-transformer",
        ...     "abc123def456..."
        ... )
        Path("/models/nt/models--InstaDeepAI--nucleotide-transformer/snapshots/abc123def456...")
    """
    prefix = "datasets--" if repo_type == "dataset" else "models--"
    cache_name = f"{prefix}{hf_repo_id.replace('/', '--')}"
    snapshot_path = model_dir / cache_name / "snapshots" / hf_revision
    return snapshot_path


def download_archive(
    zip_url: str,
    destination: Path,
    *,
    show_progress: bool = True,
    headers: Optional[dict[str, str]] = None,
    verify_ssl: bool = True,
    timeout: int = 600,
) -> dict:
    """
    Stream a .zip archive to `destination` with progress and error cleanup.

    Downloads a zip file from the given URL to the specified destination path,
    with optional progress reporting and automatic cleanup on failure.

    Args:
        zip_url: URL of the zip file to download
        destination: Path where the zip file should be saved
        show_progress: Whether to show download progress (default True)
        headers: Optional HTTP headers (e.g. auth) to send with the request
        verify_ssl: Whether to verify SSL certificates (default True)
        timeout: Per-request timeout in seconds (default 600)

    Returns:
        Dictionary with download metadata:
            - files_downloaded: Number of files (always 1 for archive)
            - bytes_downloaded: Total bytes downloaded

    Raises:
        RuntimeError: If download fails

    Example:
        >>> metadata = download_archive(
        ...     "https://github.com/org/repo/archive/abc123.zip",
        ...     Path("/tmp/repo.zip")
        ... )
        >>> print(f"Downloaded {metadata['bytes_downloaded']} bytes")
    """
    # Ensure parent directory exists
    destination.parent.mkdir(parents=True, exist_ok=True)

    logger.info(f"📥 Downloading archive from {zip_url.split('/')[-1]}...")

    try:
        response = requests.get(
            zip_url,
            stream=True,
            timeout=timeout,
            headers=headers,
            verify=verify_ssl,
        )
        response.raise_for_status()

        # Get total size for progress reporting
        total_size = int(response.headers.get("content-length", 0))
        downloaded = 0
        chunk_size = 32768  # 32KB chunks for efficiency

        # Progress tracking variables
        last_reported_progress = -1
        progress_threshold = 10  # Report every 10%

        # Only show progress for files > 5MB
        should_show_progress = show_progress and total_size > 5 * 1024 * 1024

        if should_show_progress and total_size > 0:
            logger.info(f"📊 Total size: {total_size / (1024*1024):.1f} MB")

        with open(destination, "wb") as f:
            for chunk in response.iter_content(chunk_size=chunk_size):
                if chunk:
                    f.write(chunk)
                    downloaded += len(chunk)

                    # Update progress at meaningful intervals
                    if should_show_progress and total_size > 0:
                        progress = (downloaded / total_size) * 100
                        progress_interval = (
                            int(progress // progress_threshold) * progress_threshold
                        )

                        # Only print when crossing a threshold
                        if progress_interval > last_reported_progress:
                            last_reported_progress = progress_interval
                            if progress_interval < 100:
                                logger.info(
                                    f"⬇️  Download progress: {progress_interval}%"
                                )
                            else:
                                logger.info("⬇️  Download progress: 100%")

        logger.info(
            f"✅ Downloaded {destination.name} ({downloaded / (1024*1024):.1f} MB)"
        )

        return {
            "files_downloaded": 1,
            "bytes_downloaded": downloaded,
        }

    except Exception as e:
        # Clean up partial download if it exists
        if destination.exists():
            destination.unlink()
        raise RuntimeError(f"Failed to download archive: {e}") from e


def extract_archive_subtree(
    zip_path: Path, prefix: str, dest_dir: Path, *, overwrite: bool = True
) -> None:
    """
    Extract the subset of files whose names start with `prefix` into `dest_dir`.

    Extracts only files from the archive that match the given prefix,
    stripping the prefix from their paths when writing to the destination.

    Args:
        zip_path: Path to the zip file to extract from
        prefix: Prefix to match files against (e.g., "repo-abc123/src/")
        dest_dir: Destination directory for extracted files
        overwrite: Whether to overwrite existing files (default True)

    Raises:
        RuntimeError: If archive is not found or extraction fails

    Example:
        >>> extract_archive_subtree(
        ...     Path("/tmp/repo.zip"),
        ...     "repo-abc123/src/",
        ...     Path("/output/src")
        ... )
        # Extracts repo-abc123/src/file.py to /output/src/file.py
    """
    import shutil

    if not zip_path.exists():
        raise RuntimeError(f"Archive file not found: {zip_path}")

    logger.info("📦 Extracting archive subtree with prefix: %s", prefix)

    # Remove existing destination directory if overwrite is True
    if overwrite and dest_dir.exists():
        logger.info("🗑️  Removing existing directory: %s", dest_dir)
        shutil.rmtree(dest_dir)

    # Create destination directory
    dest_dir.mkdir(parents=True, exist_ok=True)

    extracted_count = 0

    try:
        with zipfile.ZipFile(zip_path, "r") as zip_ref:
            # Find all files with the specified prefix
            members_to_extract = [m for m in zip_ref.namelist() if m.startswith(prefix)]

            if not members_to_extract:
                raise RuntimeError(f"No files found with prefix '{prefix}' in archive")

            # Extract files with adjusted paths
            for member in members_to_extract:
                # Remove the prefix to get the relative path
                relative_path = member[len(prefix) :]

                if relative_path:  # Skip empty paths
                    target_path = dest_dir / relative_path

                    # Create parent directories if needed
                    if member.endswith("/"):
                        target_path.mkdir(parents=True, exist_ok=True)
                    else:
                        target_path.parent.mkdir(parents=True, exist_ok=True)
                        # Extract file
                        with zip_ref.open(member) as source:
                            with open(target_path, "wb") as target:
                                target.write(source.read())
                        extracted_count += 1

        logger.info("✅ Extracted %s files to %s", extracted_count, dest_dir)

    except Exception as e:
        raise RuntimeError(f"Failed to extract archive: {e}") from e


def detect_archive_root_prefix(zip_path: Path) -> str:
    """
    Detect the single top-level directory of a source archive.

    Source archives produced by GitHub (and most ``git archive`` tooling) wrap
    all files under one ``<Repo>-<ref>/`` root directory. This returns that root
    (with a trailing slash) so callers can strip it when extracting subtrees.

    Args:
        zip_path: Path to the .zip archive to inspect

    Returns:
        The shared top-level prefix including the trailing slash
        (e.g. ``"TEMPRO-main/"``), or ``""`` if the archive has no single
        common root directory.

    Raises:
        RuntimeError: If the archive file does not exist.

    Example:
        >>> detect_archive_root_prefix(Path("/tmp/TEMPRO-main.zip"))
        'TEMPRO-main/'
    """
    if not zip_path.exists():
        raise RuntimeError(f"Archive file not found: {zip_path}")

    with zipfile.ZipFile(zip_path, "r") as zip_ref:
        names = [n for n in zip_ref.namelist() if n]

    if not names:
        return ""

    top = names[0].split("/", 1)[0]
    if top and all(n.split("/", 1)[0] == top for n in names):
        return f"{top}/"
    return ""
