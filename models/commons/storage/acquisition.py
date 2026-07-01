import os
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Optional
from urllib.parse import urlparse

import requests

from models.commons.core.logging import get_logger
from models.commons.storage.downloads import (
    download_model_from_r2,
)
from models.commons.storage.r2_utils import R2Utils
from models.commons.util.config import r2_bucket_name

"""
Core Model Weight Acquisition Engine
====================================

Purpose:
Unified engine that implements the two supported download flows:
1) Direct-from-R2 (legacy/compatibility), and 2) Check-R2-then-fetch-from-source
   with caching back to R2. The engine ensures files are placed at the exact
   path models expect and uses atomic R2 cache markers/manifests.

Position in Architecture:
Layer 2 (Middle) – Called by download_helpers.py → used by models/*/download.py.
Uses downloads.py (low-level ops) and r2_utils.py (atomic R2 cache ops).

Key APIs:
- acquire_model_weights(): Strategy router and validator
- AcquisitionConfig (+ R2OnlyConfig, HfSourceConfig, LibrarySourceConfig, UrlSourceConfig)
- AcquisitionResult: reports actual path, cache hits, and validation details

Non-obvious details:
- For HF downloads, the returned path differs from target_dir (points to the
  snapshot subdir). Callers should use result.actual_model_path when loading.
- R2 cache prefixes are derived from the intended target_dir so restores land in
  the same directory structure the model expects.
- Library-managed flows can set env vars via LibrarySourceConfig.env_vars and/or
  call custom init functions; parameters for downloads are passed via kwargs,
  not environment variables.

Notes on current state:
- Library-managed strategies pass a small `custom_function` (the library init
  entry point) to trigger the third-party library downloads. It is required by
  the LIBRARY_MANAGED strategy and is NOT deprecated; CustomSourceConfig serves
  the separate CUSTOM strategy.
"""

logger = get_logger(__name__)


class AcquisitionStrategy(Enum):
    """Enumeration of supported acquisition strategies."""

    R2_ONLY = "r2_only"
    HUGGINGFACE_HUB = "huggingface_hub"
    LIBRARY_MANAGED = "library_managed"
    DIRECT_URLS = "direct_urls"
    CUSTOM = "custom"


@dataclass
class CacheConfig:
    """Configuration for R2 caching behavior."""

    enable_r2_cache: bool = True
    force_download: bool = False
    cache_timeout_hours: Optional[int] = None
    validate_checksums: bool = True


@dataclass
class ValidationConfig:
    """Configuration for validating acquired weights."""

    required_files: Optional[list[str]] = None
    custom_validator: Optional[Callable[[Path], bool]] = None
    min_size_bytes: Optional[int] = None
    max_size_bytes: Optional[int] = None


@dataclass
class R2OnlyConfig:
    """Configuration for R2-only acquisition strategy."""

    base_model_slug: str
    weights_version: str
    model_variant: Optional[str] = None
    sub_path: Optional[str] = None
    filter_func: Optional[Callable[[str], bool]] = None


@dataclass
class HfSourceConfig:
    """Configuration for HuggingFace Hub acquisition strategy."""

    repo_id: str
    revision: Optional[str] = None
    allow_patterns: Optional[list[str]] = None
    ignore_patterns: Optional[list[str]] = None
    repo_type: str = "model"  # "model" or "dataset"


@dataclass
class LibrarySourceConfig:
    """Configuration for library-managed acquisition strategy."""

    library_name: str
    env_vars: Optional[dict[str, str]] = None


@dataclass
class UrlSourceConfig:
    """Configuration for direct URL downloads"""

    urls: dict[str, str]  # Mapping of filename -> URL
    headers: Optional[dict[str, str]] = None  # Optional HTTP headers
    verify_ssl: bool = True  # Whether to verify SSL certificates
    timeout: int = 300  # Request timeout in seconds
    chunk_size: int = 8192  # Download chunk size


@dataclass
class CustomSourceConfig:
    """Configuration for custom acquisition strategy."""

    # Function that downloads to target_dir. Called as
    # acquisition_fn(target_dir=..., **acquisition_kwargs), so the signature must
    # accept a `target_dir` keyword argument (plus arbitrary extra kwargs).
    acquisition_fn: Callable[..., dict[str, Any]]
    acquisition_kwargs: dict[str, Any] = field(
        default_factory=dict
    )  # Additional kwargs for function
    name: Optional[str] = None  # Name for this custom strategy
    description: Optional[str] = None  # Description of what this does
    post_process_fn: Optional[Callable[..., None]] = None  # Optional post-processing
    post_process_kwargs: dict[str, Any] = field(
        default_factory=dict
    )  # Additional kwargs for post-processing


@dataclass
class AcquisitionConfig:
    """Main configuration for model weight acquisition."""

    strategy: AcquisitionStrategy
    target_dir: Path
    cache_config: CacheConfig = field(default_factory=CacheConfig)
    validation_config: ValidationConfig = field(default_factory=ValidationConfig)

    # Strategy-specific configs (only one should be set)
    r2_config: Optional[R2OnlyConfig] = None
    hf_config: Optional[HfSourceConfig] = None
    library_config: Optional[LibrarySourceConfig] = None
    url_config: Optional[UrlSourceConfig] = None
    custom_config: Optional[CustomSourceConfig] = None
    custom_function: Optional[Callable[[Path], Any]] = (
        None  # Library-managed init entry point (required by LIBRARY_MANAGED)
    )


@dataclass
class AcquisitionResult:
    """Result of model weight acquisition."""

    success: bool
    target_dir: Path
    actual_model_path: Optional[Path] = (
        None  # May differ from target_dir for HF snapshots
    )
    files_downloaded: int = 0
    cache_hit: bool = False
    acquisition_time_seconds: float = 0.0
    error_message: Optional[str] = None
    metadata: dict[str, Any] = field(default_factory=dict)


def _calculate_directory_size(directory: Path) -> int:
    """
    Calculate total size of all files in directory recursively.

    Args:
        directory: Directory to calculate size for

    Returns:
        Total size in bytes
    """
    total_size = 0
    try:
        for file_path in directory.rglob("*"):
            if file_path.is_file():
                total_size += file_path.stat().st_size
    except Exception as e:
        logger.warning("Error calculating directory size: %s", e)
    return total_size


def _try_r2_restore(
    config: AcquisitionConfig,
    target_dir: Path,
    start_time: float,
    strategy_name: str,
    *,
    extra_metadata: Optional[dict[str, Any]] = None,
    resolve_model_path: Optional[Callable[[Path], Path]] = None,
) -> Optional[AcquisitionResult]:
    """
    Unified R2 cache check and restore for all acquisition strategies.

    Checks if the target directory is already cached in R2 and restores it.
    Returns an AcquisitionResult on cache hit, or None on miss/skip.

    Args:
        config: Acquisition configuration (checks cache_config.enable_r2_cache)
        target_dir: Local directory to restore to
        start_time: Acquisition start timestamp for timing
        strategy_name: Name of the strategy for metadata (e.g. "huggingface_hub")
        extra_metadata: Additional metadata to include in the result
        resolve_model_path: Optional callback to resolve actual_model_path from
            target_dir after restore (e.g. HF snapshot path resolution).
            If None, actual_model_path = target_dir.

    Returns:
        AcquisitionResult with cache_hit=True on success, None otherwise
    """
    if not config.cache_config.enable_r2_cache or config.cache_config.force_download:
        return None

    r2_prefix = R2Utils.get_r2_prefix_from_target_dir(target_dir)
    logger.info("Checking R2 cache at %s", r2_prefix)

    # Extract cache config parameters
    timeout_hours = None
    if config.cache_config.cache_timeout_hours:
        timeout_hours = config.cache_config.cache_timeout_hours
    validate_manifest = config.cache_config.validate_checksums

    logger.info("[acquisition.py] Starting atomic restore from R2: %s", r2_prefix)
    restored = R2Utils.restore_from_r2_atomic(
        target_dir=target_dir,
        r2_prefix=r2_prefix,
        bucket_name=r2_bucket_name,
        validate_manifest=validate_manifest,
        timeout_hours=timeout_hours,
    )

    if not restored:
        return None

    logger.info("Found in R2 cache, restored successfully")

    # Resolve actual model path (e.g. HF snapshot subdirectory)
    actual_model_path = target_dir
    if resolve_model_path is not None:
        actual_model_path = resolve_model_path(target_dir)

    metadata: dict[str, Any] = {
        "strategy": strategy_name,
        "cache_source": "r2",
        "r2_prefix": r2_prefix,
    }
    if extra_metadata:
        metadata.update(extra_metadata)

    return AcquisitionResult(
        success=True,
        target_dir=target_dir,
        actual_model_path=actual_model_path,
        files_downloaded=0,
        cache_hit=True,
        acquisition_time_seconds=time.time() - start_time,
        metadata=metadata,
    )


def _download_file_with_progress(
    session: requests.Session, url: str, file_path: Path, url_conf: UrlSourceConfig
) -> int:
    """Download a single file with progress reporting."""
    response = session.get(
        url, stream=True, verify=url_conf.verify_ssl, timeout=url_conf.timeout
    )
    response.raise_for_status()

    file_size = int(response.headers.get("content-length", 0))
    downloaded = 0
    last_percent_printed = -1  # Track last printed percentage to avoid spam

    with open(file_path, "wb") as f:
        for chunk in response.iter_content(chunk_size=url_conf.chunk_size):
            if chunk:
                f.write(chunk)
                downloaded += len(chunk)
                if file_size > 0:
                    progress = int((downloaded / file_size) * 100)
                    # Only print at 0%, 25%, 50%, 75%, 100% milestones
                    if progress >= 0 and progress != last_percent_printed:
                        if progress in [0, 25, 50, 75, 100]:
                            logger.info(
                                f"   Progress: {progress}% ({downloaded/(1024**2):.1f}MB/{file_size/(1024**2):.1f}MB)"
                            )
                            last_percent_printed = progress

    if file_size > 0:
        logger.info(f"   Downloaded {file_path.name} ({file_size/(1024**2):.1f}MB)")
    else:
        logger.info(f"   Downloaded {file_path.name} ({downloaded/(1024**2):.1f}MB)")

    return max(file_size, downloaded)


def _cache_to_r2(
    config: AcquisitionConfig,
    source_dir: Path,
    *,
    r2_prefix_dir: Optional[Path] = None,
    skip_if_no_files: bool = False,
    files_downloaded: int = 0,
) -> bool:
    """
    Unified R2 cache write for all acquisition strategies.

    Uploads the source directory to R2 if caching is enabled.

    Args:
        config: Acquisition configuration (checks cache_config.enable_r2_cache)
        source_dir: Directory to upload to R2
        r2_prefix_dir: Directory used to derive R2 prefix (defaults to source_dir).
            Use this when source_dir differs from the canonical target_dir
            (e.g. library bypass) so the R2 key matches _try_r2_restore.
        skip_if_no_files: If True, skip upload when files_downloaded <= 0
        files_downloaded: Number of files downloaded (used with skip_if_no_files)

    Returns:
        True if upload succeeded or was skipped (not enabled)
    """
    if not config.cache_config.enable_r2_cache:
        return True

    if skip_if_no_files and files_downloaded <= 0:
        return True

    r2_prefix = R2Utils.get_r2_prefix_from_target_dir(r2_prefix_dir or source_dir)
    logger.info("Caching to R2 at %s", r2_prefix)
    logger.info("[acquisition.py] Starting atomic upload to R2: %s", r2_prefix)

    success = R2Utils.upload_to_r2_atomic(
        source_dir=source_dir,
        r2_prefix=r2_prefix,
        bucket_name=r2_bucket_name,
        create_manifest=True,
    )
    if not success:
        logger.warning("R2 upload failed, but download succeeded")
    return success


def _acquire_direct_urls(config: AcquisitionConfig) -> AcquisitionResult:
    """
    Acquire model weights from direct URLs.

    This strategy downloads files from a list of direct URLs (HTTP/HTTPS).
    Useful for models hosted on custom servers, GitHub releases, or any
    non-HuggingFace/R2 locations.

    Args:
        config: Complete acquisition configuration

    Returns:
        AcquisitionResult with download status and metadata

    Example usage:
        from models.commons.storage.acquisition import (
            acquire_model_weights,
            AcquisitionStrategy,
            AcquisitionConfig,
            UrlSourceConfig
        )

        config = AcquisitionConfig(
            strategy=AcquisitionStrategy.DIRECT_URLS,
            target_dir=Path("/models/mymodel"),
            url_config=UrlSourceConfig(
                urls={
                    "model.bin": "https://example.com/models/mymodel/model.bin",
                    "config.json": "https://github.com/org/repo/releases/download/v1/config.json",
                    "tokenizer.json": "https://storage.googleapis.com/mybucket/tokenizer.json"
                },
                headers={"Authorization": "Bearer token"},  # Optional auth headers
                verify_ssl=True,
                chunk_size=8192
            )
        )

        result = acquire_model_weights(config)
    """
    start_time = time.time()

    if not config.url_config:
        return AcquisitionResult(
            success=False,
            target_dir=config.target_dir,
            error_message="UrlSourceConfig required for DIRECT_URLS strategy",
            acquisition_time_seconds=time.time() - start_time,
        )

    url_conf = config.url_config
    target_dir = config.target_dir
    target_dir.mkdir(parents=True, exist_ok=True)

    logger.info("Acquiring model weights from direct URLs to %s", target_dir)

    # Check R2 cache first
    cache_result = _try_r2_restore(config, target_dir, start_time, "direct_urls")
    if cache_result:
        return cache_result

    # Download from URLs
    downloaded_files = []
    total_bytes = 0

    try:
        session = requests.Session()
        if url_conf.headers:
            session.headers.update(url_conf.headers)

        for filename, url in url_conf.urls.items():
            file_path = target_dir / filename
            file_path.parent.mkdir(parents=True, exist_ok=True)

            logger.info("Downloading %s from %s", filename, urlparse(url).netloc)

            bytes_downloaded = _download_file_with_progress(
                session, url, file_path, url_conf
            )
            downloaded_files.append(filename)
            total_bytes += bytes_downloaded

        logger.info(
            f"Downloaded {len(downloaded_files)} files ({total_bytes/(1024**3):.2f}GB total)"
        )

        # Cache to R2
        upload_success = _cache_to_r2(config, target_dir)

        return AcquisitionResult(
            success=True,
            target_dir=target_dir,
            actual_model_path=target_dir,
            files_downloaded=len(downloaded_files),
            cache_hit=False,
            acquisition_time_seconds=time.time() - start_time,
            metadata={
                "strategy": "direct_urls",
                "files": downloaded_files,
                "urls": list(url_conf.urls.keys()),
                "total_size_bytes": total_bytes,
                "r2_upload_success": upload_success,
            },
        )

    except Exception as e:
        error_msg = f"Failed to download from URLs: {str(e)}"
        logger.error("%s", error_msg, exc_info=True)
        return AcquisitionResult(
            success=False,
            target_dir=target_dir,
            error_message=error_msg,
            acquisition_time_seconds=time.time() - start_time,
        )


def _acquire_r2_only_via_http(
    r2_config: "R2OnlyConfig",
    target_dir: Path,
    r2_prefix: str,
    public_url: str,
    start_time: float,
) -> AcquisitionResult:
    """Credential-less R2_ONLY restore over anonymous public HTTPS (r2.dev).

    Mirrors the marker-gate miss/hit semantics of the signed S3 read, returning a
    success result on a complete manifest-driven restore and a miss result
    otherwise so the caller's source fallback runs.
    """
    from models.commons.storage.r2_http import restore_weights_via_http

    base_metadata = {
        "strategy": "r2_only",
        "model_slug": r2_config.base_model_slug,
        "weights_version": r2_config.weights_version,
        "read_via": "public_http",
    }
    if restore_weights_via_http(target_dir, r2_prefix, public_url):
        return AcquisitionResult(
            success=True,
            target_dir=target_dir,
            actual_model_path=target_dir,
            cache_hit=False,  # R2 is the primary source, not a cache hit
            acquisition_time_seconds=time.time() - start_time,
            metadata={
                **base_metadata,
                "model_variant": r2_config.model_variant,
                "sub_path": r2_config.sub_path,
            },
        )
    return AcquisitionResult(
        success=False,
        target_dir=target_dir,
        error_message=(
            "Public R2 read: no completion marker/manifest at the expected prefix "
            "(anonymous HTTP cache miss)"
        ),
        acquisition_time_seconds=time.time() - start_time,
        metadata={**base_metadata, "cache_miss_reason": "no_public_marker_or_manifest"},
    )


def _acquire_r2_only(config: AcquisitionConfig) -> AcquisitionResult:
    """
    Acquire model weights directly from R2 storage.

    This strategy downloads files directly from R2 using the standardized
    directory structure and optional filtering.

    Args:
        config: Complete acquisition configuration with r2_config

    Returns:
        AcquisitionResult with download status and metadata
    """
    start_time = time.time()

    if not config.r2_config:
        return AcquisitionResult(
            success=False,
            target_dir=config.target_dir,
            error_message="R2OnlyConfig required for R2_ONLY strategy",
            acquisition_time_seconds=time.time() - start_time,
        )

    r2_config = config.r2_config
    target_dir = config.target_dir
    target_dir.mkdir(parents=True, exist_ok=True)

    logger.info("Acquiring model weights from R2 storage to %s", target_dir)
    logger.info("   Model: %s/%s", r2_config.base_model_slug, r2_config.weights_version)
    if r2_config.model_variant:
        logger.info("   Variant: %s", r2_config.model_variant)
    if r2_config.sub_path:
        logger.info("   Sub-path: %s", r2_config.sub_path)
    if r2_config.filter_func:
        logger.info("   Using custom filter function")

    try:
        # Marker gate (B1/B2): an R2 prefix without a valid completion marker is
        # an incomplete/interrupted cache. Treat it as a MISS so the caller's
        # source fallback runs, instead of silently restoring a partial weight
        # set as a false "success". This unifies the R2-primary read semantics
        # with R2Utils.restore_from_r2_atomic, which already requires the marker.
        from models.commons.storage.r2 import get_r2_client, r2_credentials_present
        from models.commons.util.config import r2_public_url

        r2_prefix = R2Utils.get_r2_prefix_from_target_dir(target_dir)

        # Credential-less public read: with no S3 creds present, restore the cached
        # weights anonymously over HTTPS from the bucket's public URL (r2.dev has no
        # LIST, so it drives off the manifest). Writes still require credentials.
        if not r2_credentials_present() and r2_public_url:
            return _acquire_r2_only_via_http(
                r2_config, target_dir, r2_prefix, r2_public_url, start_time
            )

        if not R2Utils.check_completion_marker(
            get_r2_client(),
            r2_prefix,
            r2_bucket_name,
            config.cache_config.cache_timeout_hours,
        ):
            logger.info(
                "No valid R2 completion marker at %s — treating as cache miss",
                r2_prefix,
            )
            return AcquisitionResult(
                success=False,
                target_dir=target_dir,
                error_message=(
                    f"R2 cache incomplete: no completion marker at '{r2_prefix}' "
                    "(interrupted or absent upload)"
                ),
                acquisition_time_seconds=time.time() - start_time,
                metadata={
                    "strategy": "r2_only",
                    "model_slug": r2_config.base_model_slug,
                    "weights_version": r2_config.weights_version,
                    "cache_miss_reason": "no_completion_marker",
                },
            )

        # Use the existing download_model_from_r2 function
        sync_result = download_model_from_r2(
            model_dir=target_dir,
            filter_func=r2_config.filter_func,
            force_download=config.cache_config.force_download,
        )

        # Distinguish "no files exist in R2" (genuine failure) from
        # "all files already present locally" (idempotent success).
        if sync_result.total == 0:
            return AcquisitionResult(
                success=False,
                target_dir=target_dir,
                error_message="No files found in R2 at the expected prefix",
                acquisition_time_seconds=time.time() - start_time,
                metadata={
                    "strategy": "r2_only",
                    "model_slug": r2_config.base_model_slug,
                    "weights_version": r2_config.weights_version,
                    "model_variant": r2_config.model_variant,
                    "sub_path": r2_config.sub_path,
                },
            )

        files_downloaded = sync_result.downloaded
        if sync_result.skipped > 0:
            logger.info(
                "R2 sync complete: %s downloaded, %s already up-to-date",
                files_downloaded,
                sync_result.skipped,
            )
        else:
            logger.info("R2 download complete: %s files", files_downloaded)

        return AcquisitionResult(
            success=True,
            target_dir=target_dir,
            actual_model_path=target_dir,
            files_downloaded=files_downloaded,
            cache_hit=False,  # R2 is the primary source, not a cache hit
            acquisition_time_seconds=time.time() - start_time,
            metadata={
                "strategy": "r2_only",
                "model_slug": r2_config.base_model_slug,
                "weights_version": r2_config.weights_version,
                "model_variant": r2_config.model_variant,
                "sub_path": r2_config.sub_path,
                "filter_applied": r2_config.filter_func is not None,
            },
        )

    except Exception as e:
        error_msg = f"Failed to download from R2: {str(e)}"
        logger.error("%s", error_msg, exc_info=True)
        return AcquisitionResult(
            success=False,
            target_dir=target_dir,
            error_message=error_msg,
            acquisition_time_seconds=time.time() - start_time,
            metadata={
                "strategy": "r2_only",
                "model_slug": r2_config.base_model_slug,
                "weights_version": r2_config.weights_version,
            },
        )


def _resolve_hf_snapshot_path(hf_config: HfSourceConfig) -> Callable[[Path], Path]:
    """Build a resolve_model_path callback for HF snapshot path resolution."""
    from models.commons.storage.downloads import build_hf_snapshot_path

    def _resolve(target_dir: Path) -> Path:
        if hf_config.revision and len(hf_config.revision) == 40:
            # Full commit hash - use deterministic path
            snapshot_dir = build_hf_snapshot_path(
                target_dir,
                hf_config.repo_id,
                hf_config.revision,
                repo_type=hf_config.repo_type,
            )
            logger.info("   Using deterministic snapshot path: %s", snapshot_dir)
        else:
            # Branch name like "main" - find the actual snapshot directory
            prefix = "datasets--" if hf_config.repo_type == "dataset" else "models--"
            cache_name = f"{prefix}{hf_config.repo_id.replace('/', '--')}"
            cache_dir = target_dir / cache_name / "snapshots"
            if cache_dir.exists():
                snapshots = list(cache_dir.iterdir())
                if len(snapshots) == 1 and snapshots[0].is_dir():
                    snapshot_dir = snapshots[0]
                    logger.info("   Found snapshot path: %s", snapshot_dir)
                else:
                    raise ValueError(
                        f"Cannot determine snapshot path for {hf_config.repo_id} "
                        f"with revision '{hf_config.revision}'. "
                        f"Found {len(snapshots)} snapshots in {cache_dir}"
                    )
            else:
                raise FileNotFoundError(
                    f"Cache directory not found: {cache_dir}. "
                    f"Download may not have completed successfully."
                )
        return snapshot_dir

    return _resolve


def _acquire_huggingface_hub(config: AcquisitionConfig) -> AcquisitionResult:
    """
    Acquire model weights from HuggingFace Hub with R2 caching support.

    This strategy downloads files from HuggingFace Hub and handles the snapshot
    directory structure. It supports R2 caching, revision pinning, and file patterns.

    Args:
        config: Complete acquisition configuration with hf_config

    Returns:
        AcquisitionResult with download status and metadata
    """
    start_time = time.time()

    if not config.hf_config:
        return AcquisitionResult(
            success=False,
            target_dir=config.target_dir,
            error_message="HfSourceConfig required for HUGGINGFACE_HUB strategy",
            acquisition_time_seconds=time.time() - start_time,
        )

    hf_config = config.hf_config
    target_dir = config.target_dir
    target_dir.mkdir(parents=True, exist_ok=True)

    logger.info("Acquiring model weights from HuggingFace Hub")
    logger.info("   Repository: %s", hf_config.repo_id)
    if hf_config.revision:
        logger.info("   Revision: %s", hf_config.revision)
    if hf_config.allow_patterns:
        logger.info("   Include patterns: %s", hf_config.allow_patterns)
    if hf_config.ignore_patterns:
        logger.info("   Exclude patterns: %s", hf_config.ignore_patterns)

    # Check R2 cache first
    cache_result = _try_r2_restore(
        config,
        target_dir,
        start_time,
        "huggingface_hub",
        extra_metadata={
            "repo_id": hf_config.repo_id,
            "revision": hf_config.revision,
        },
        resolve_model_path=_resolve_hf_snapshot_path(hf_config),
    )
    if cache_result:
        return cache_result

    # Download from HuggingFace Hub
    try:
        from models.commons.storage.downloads import download_from_hf

        logger.info("Downloading from HuggingFace Hub...")
        snapshot_dir = download_from_hf(
            model_dir=target_dir,
            hf_repo_id=hf_config.repo_id,
            hf_revision=hf_config.revision,
            allow_patterns=hf_config.allow_patterns,
            ignore_patterns=hf_config.ignore_patterns,
            repo_type=hf_config.repo_type,
        )

        # Count downloaded files
        downloaded_files = list(snapshot_dir.rglob("*"))
        file_count = len([f for f in downloaded_files if f.is_file()])
        total_size = sum(f.stat().st_size for f in downloaded_files if f.is_file())

        logger.info(
            f"HuggingFace download complete: {file_count} files ({total_size/(1024**3):.2f}GB)"
        )
        logger.info("   Snapshot directory: %s", snapshot_dir)

        # Cache to R2
        upload_success = _cache_to_r2(config, target_dir)

        return AcquisitionResult(
            success=True,
            target_dir=target_dir,
            actual_model_path=snapshot_dir,
            files_downloaded=file_count,
            cache_hit=False,
            acquisition_time_seconds=time.time() - start_time,
            metadata={
                "strategy": "huggingface_hub",
                "repo_id": hf_config.repo_id,
                "revision": hf_config.revision,
                "snapshot_path": str(snapshot_dir),
                "is_deterministic": (
                    hf_config.revision and len(hf_config.revision) == 40
                ),
                "allow_patterns": hf_config.allow_patterns,
                "ignore_patterns": hf_config.ignore_patterns,
                "total_size_bytes": total_size,
                "r2_upload_success": upload_success,
            },
        )

    except Exception as e:
        error_msg = f"Failed to download from HuggingFace Hub: {str(e)}"
        logger.error("%s", error_msg, exc_info=True)
        return AcquisitionResult(
            success=False,
            target_dir=target_dir,
            error_message=error_msg,
            acquisition_time_seconds=time.time() - start_time,
            metadata={
                "strategy": "huggingface_hub",
                "repo_id": hf_config.repo_id,
                "revision": hf_config.revision,
            },
        )


def _setup_library_environment(
    library_config: LibrarySourceConfig,
) -> dict[str, Optional[str]]:
    """Set environment variables for library and return original values."""
    original_env: dict[str, Optional[str]] = {}
    if library_config.env_vars:
        logger.info("Setting %s environment variables", len(library_config.env_vars))
        for var, value in library_config.env_vars.items():
            original_env[var] = os.environ.get(var)
            os.environ[var] = value
            logger.debug("   Set env var: %s", var)
    return original_env


def _restore_environment(original_env: dict[str, Optional[str]]) -> None:
    """Restore original environment variables."""
    for var, value in original_env.items():
        if value is None:
            os.environ.pop(var, None)
        else:
            os.environ[var] = value


def _acquire_library_managed(config: AcquisitionConfig) -> AcquisitionResult:
    """Implement library-managed acquisition strategy."""
    start_time = time.time()

    if not config.library_config or not config.custom_function:
        return AcquisitionResult(
            success=False,
            target_dir=config.target_dir,
            error_message="LibrarySourceConfig and custom_function required for LIBRARY_MANAGED strategy",
            acquisition_time_seconds=time.time() - start_time,
        )

    library_config = config.library_config
    target_dir = config.target_dir
    target_dir.mkdir(parents=True, exist_ok=True)

    logger.info("Acquiring model weights using %s library", library_config.library_name)

    # Check R2 cache first
    cache_result = _try_r2_restore(
        config,
        target_dir,
        start_time,
        "library_managed",
        extra_metadata={"library_name": library_config.library_name},
    )
    if cache_result:
        return cache_result

    # Setup environment
    original_env = _setup_library_environment(library_config)

    try:
        logger.info(
            "Calling library initialization function for %s",
            library_config.library_name,
        )

        # Record initial state
        initial_files = list(target_dir.rglob("*"))
        initial_file_count = len([f for f in initial_files if f.is_file()])

        # Call the custom function
        result = config.custom_function(target_dir)
        actual_model_dir = (
            Path(result) if isinstance(result, str | Path) else target_dir
        )

        # Calculate files downloaded
        final_files = list(actual_model_dir.rglob("*"))
        final_file_count = len([f for f in final_files if f.is_file()])
        files_downloaded = final_file_count - initial_file_count

        logger.info(
            "Library function completed, %s files added to target directory",
            files_downloaded,
        )

        # Ensure the library actually wrote files to the target directory.
        # Required-file validation is handled centrally by
        # _perform_comprehensive_validation after this handler returns.
        if not any(actual_model_dir.rglob("*")):
            raise RuntimeError("library-managed download wrote no files")

        # Cache to R2 (use target_dir for prefix so _try_r2_restore can find it)
        upload_success = _cache_to_r2(
            config,
            actual_model_dir,
            r2_prefix_dir=target_dir,
            skip_if_no_files=True,
            files_downloaded=files_downloaded,
        )

        return AcquisitionResult(
            success=True,
            target_dir=target_dir,
            actual_model_path=actual_model_dir,
            files_downloaded=files_downloaded,
            cache_hit=False,
            acquisition_time_seconds=time.time() - start_time,
            metadata={
                "strategy": "library_managed",
                "library_name": library_config.library_name,
                "r2_upload_success": upload_success,
                "initial_file_count": initial_file_count,
                "final_file_count": final_file_count,
            },
        )

    except Exception as e:
        error_msg = f"Library-managed download failed: {str(e)}"
        logger.error("%s", error_msg, exc_info=True)

        return AcquisitionResult(
            success=False,
            target_dir=target_dir,
            error_message=error_msg,
            acquisition_time_seconds=time.time() - start_time,
            metadata={
                "strategy": "library_managed",
                "library_name": library_config.library_name,
            },
        )

    finally:
        _restore_environment(original_env)


def _validate_required_files_custom(
    target_dir: Path, required_files: list[str]
) -> None:
    """Validate that required files exist."""
    missing_files = []
    for required_file in required_files:
        file_path = target_dir / required_file
        if not file_path.exists():
            missing_files.append(required_file)

    if missing_files:
        raise FileNotFoundError(f"Required files missing: {missing_files}")


def _execute_custom_function(
    custom_config: CustomSourceConfig,
    target_dir: Path,
    validation_config: ValidationConfig,
    cache_config: CacheConfig,
    custom_name: str,
    start_time: float,
) -> AcquisitionResult:
    """Execute the custom acquisition function and handle results."""
    try:
        logger.info(
            "[acquisition.py] Executing custom acquisition function: %s...",
            custom_name,
        )

        # Call the custom function with target_dir and any additional kwargs
        result_metadata = custom_config.acquisition_fn(
            target_dir=target_dir, **custom_config.acquisition_kwargs
        )

        # Validate that files were actually downloaded
        downloaded_files = list(target_dir.rglob("*"))
        if not downloaded_files:
            raise RuntimeError("Custom function did not download any files")

        file_count = len([f for f in downloaded_files if f.is_file()])
        total_size = sum(f.stat().st_size for f in downloaded_files if f.is_file())

        logger.info(
            f"Custom acquisition complete: {file_count} files ({total_size/(1024**3):.2f}GB)"
        )

        # Validate required files if specified
        if validation_config and validation_config.required_files:
            _validate_required_files_custom(
                target_dir, validation_config.required_files
            )

        # Run post-processing if provided
        if custom_config.post_process_fn:
            logger.info("[acquisition.py] Running post-processing...")
            custom_config.post_process_fn(
                target_dir, **custom_config.post_process_kwargs
            )

        # Cache to R2 if requested
        if cache_config and cache_config.enable_r2_cache:
            # Build a minimal config for the unified helper
            cache_only_config = AcquisitionConfig(
                strategy=AcquisitionStrategy.CUSTOM,
                target_dir=target_dir,
                cache_config=cache_config,
            )
            _cache_to_r2(cache_only_config, target_dir)

        # Merge custom metadata with standard metadata
        metadata = {
            "strategy": "custom",
            "custom_strategy": custom_name,
            "files_downloaded": file_count,
            "total_size_bytes": total_size,
        }
        if isinstance(result_metadata, dict):
            metadata.update(result_metadata)

        return AcquisitionResult(
            success=True,
            target_dir=target_dir,
            actual_model_path=target_dir,
            files_downloaded=file_count,
            cache_hit=False,
            acquisition_time_seconds=time.time() - start_time,
            metadata=metadata,
        )

    except Exception as e:
        error_msg = f"Custom acquisition failed: {str(e)}"
        logger.error("%s", error_msg, exc_info=True)

        # Try to provide helpful debugging info
        if hasattr(e, "__traceback__"):
            import traceback

            logger.debug("   Traceback:")
            for line in traceback.format_tb(e.__traceback__):
                logger.debug("   %s", line.strip())

        return AcquisitionResult(
            success=False,
            target_dir=target_dir,
            error_message=error_msg,
            acquisition_time_seconds=time.time() - start_time,
            metadata={"custom_strategy": custom_name},
        )


def _acquire_custom(config: AcquisitionConfig) -> AcquisitionResult:
    """
    Acquire model weights using a custom user-provided function.

    This strategy allows complete flexibility by letting users provide
    their own acquisition logic while still benefiting from the acquisition
    system's caching, validation, and monitoring capabilities.

    Args:
        config: Complete acquisition configuration with custom_config

    Returns:
        AcquisitionResult with download status and metadata

    Example usage:
        from models.commons.storage.acquisition import (
            acquire_model_weights,
            AcquisitionStrategy,
            AcquisitionConfig,
            CustomSourceConfig
        )

        def my_custom_download(target_dir: Path, **kwargs) -> dict:
            '''
            Custom download logic that returns metadata dict.
            Must download files to target_dir and return info about what was downloaded.
            '''
            # Custom download logic here
            import subprocess

            # Example: Use rsync to copy from remote server
            remote_path = kwargs.get('remote_path', 'server:/models/mymodel/')
            subprocess.run(['rsync', '-av', remote_path, str(target_dir)], check=True)

            # Return metadata about download
            return {
                'files_downloaded': len(list(target_dir.glob('*'))),
                'source': remote_path,
                'method': 'rsync'
            }

        custom = CustomSourceConfig(
            acquisition_fn=my_custom_download,
            acquisition_kwargs={'remote_path': 'gpu-server:/data/models/mymodel/'},
            name="rsync_download",
            description="Download via rsync from GPU server"
        )

        config = AcquisitionConfig(
            strategy=AcquisitionStrategy.CUSTOM,
            target_dir=Path("/models/mymodel"),
            custom_config=custom
        )

        result = acquire_model_weights(config)
    """
    start_time = time.time()

    if not config.custom_config:
        return AcquisitionResult(
            success=False,
            target_dir=config.target_dir,
            error_message="CustomSourceConfig required for CUSTOM strategy",
            acquisition_time_seconds=time.time() - start_time,
        )

    custom_config = config.custom_config
    cache_config = config.cache_config
    validation_config = config.validation_config

    target_dir = config.target_dir
    target_dir.mkdir(parents=True, exist_ok=True)

    custom_name = custom_config.name or "custom_function"
    logger.info("Acquiring model weights using custom strategy: %s", custom_name)
    if custom_config.description:
        logger.info("   Description: %s", custom_config.description)

    # Check R2 cache first
    cache_result = _try_r2_restore(
        config,
        target_dir,
        start_time,
        "custom",
        extra_metadata={"custom_strategy": custom_name},
    )
    if cache_result:
        return cache_result

    # Execute custom acquisition function
    return _execute_custom_function(
        custom_config=custom_config,
        target_dir=target_dir,
        validation_config=validation_config,
        cache_config=cache_config,
        custom_name=custom_name,
        start_time=start_time,
    )


def _validate_required_files(
    actual_path: Path, required_files: list[str]
) -> Optional[str]:
    """Validate required files exist in the directory."""
    from models.commons.storage.downloads import verify_model_dir

    try:
        verify_model_dir(actual_path, required_files)
        logger.info("Required files validation successful")
        return None
    except Exception as e:
        return f"Required files check failed: {e}"


def _validate_size_constraints(
    actual_path: Path, validation_config: ValidationConfig
) -> list[str]:
    """Validate directory size against min/max constraints."""
    errors: list[str] = []
    if not (validation_config.min_size_bytes or validation_config.max_size_bytes):
        return errors

    total_size = _calculate_directory_size(actual_path)
    logger.info(f"Directory size: {total_size/(1024**3):.2f}GB")

    if (
        validation_config.min_size_bytes
        and total_size < validation_config.min_size_bytes
    ):
        errors.append(
            f"Directory too small: {total_size} bytes < {validation_config.min_size_bytes} bytes"
        )

    if (
        validation_config.max_size_bytes
        and total_size > validation_config.max_size_bytes
    ):
        errors.append(
            f"Directory too large: {total_size} bytes > {validation_config.max_size_bytes} bytes"
        )

    if not errors:
        logger.info("Size constraints validation successful")
    return errors


def _run_custom_validator(
    actual_path: Path, custom_validator: Callable[[Path], bool]
) -> Optional[str]:
    """Run custom validation function."""
    logger.info("Running custom validator...")
    try:
        custom_result = custom_validator(actual_path)
        if not custom_result:
            return "Custom validator returned False"
        logger.info("Custom validation successful")
        return None
    except Exception as e:
        return f"Custom validator failed: {e}"


def _perform_comprehensive_validation(
    result: AcquisitionResult, config: AcquisitionConfig
) -> list[str]:
    """Perform all configured validations on successful acquisition."""
    if not result.success:
        return []

    actual_path = result.actual_model_path or result.target_dir
    validation_errors = []

    # Required files validation
    if config.validation_config.required_files:
        error = _validate_required_files(
            actual_path, config.validation_config.required_files
        )
        if error:
            validation_errors.append(error)

    # Size constraints validation
    size_errors = _validate_size_constraints(actual_path, config.validation_config)
    validation_errors.extend(size_errors)

    # Custom validator
    if config.validation_config.custom_validator:
        error = _run_custom_validator(
            actual_path, config.validation_config.custom_validator
        )
        if error:
            validation_errors.append(error)

    return validation_errors


def acquire_model_weights(config: AcquisitionConfig) -> AcquisitionResult:
    """
    Main entry point for model weight acquisition.

    This function coordinates the entire acquisition process including:
    - Strategy-specific acquisition
    - Validation
    - R2 caching (when applicable)

    Args:
        config: Complete acquisition configuration

    Returns:
        AcquisitionResult with detailed information about the acquisition
    """
    logger.info("Starting model weight acquisition: %s", config.strategy.value)
    logger.info("   Target directory: %s", config.target_dir)

    # Route to strategy-specific implementation
    strategy_handlers = {
        AcquisitionStrategy.R2_ONLY: _acquire_r2_only,
        AcquisitionStrategy.HUGGINGFACE_HUB: _acquire_huggingface_hub,
        AcquisitionStrategy.LIBRARY_MANAGED: _acquire_library_managed,
        AcquisitionStrategy.DIRECT_URLS: _acquire_direct_urls,
        AcquisitionStrategy.CUSTOM: _acquire_custom,
    }

    handler = strategy_handlers.get(config.strategy)
    if not handler:
        return AcquisitionResult(
            success=False,
            target_dir=config.target_dir,
            error_message=f"Unknown acquisition strategy: {config.strategy}",
        )

    # Execute strategy
    result = handler(config)

    # Perform comprehensive validation if successful
    if result.success:
        validation_errors = _perform_comprehensive_validation(result, config)

        if validation_errors:
            result.success = False
            result.error_message = f"Validation failed: {'; '.join(validation_errors)}"
            logger.error("Validation failed: %s", result.error_message)
        elif any(
            [
                config.validation_config.required_files,
                config.validation_config.min_size_bytes,
                config.validation_config.max_size_bytes,
                config.validation_config.custom_validator,
            ]
        ):
            actual_path = result.actual_model_path or result.target_dir
            logger.info("All validations passed for %s", actual_path)

    # Log final result
    if result.success:
        logger.info(
            f"Acquisition complete: {result.files_downloaded} files in {result.acquisition_time_seconds:.1f}s"
        )
    else:
        logger.error("Acquisition failed: %s", result.error_message)

    return result
