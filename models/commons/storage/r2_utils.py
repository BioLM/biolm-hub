import hashlib
import json
import time
from collections.abc import Callable
from pathlib import Path
from typing import Optional

from models.commons.core.logging import get_logger
from models.commons.storage.r2 import get_r2_client
from models.commons.util.config import r2_bucket_name, r2_model_store_dir

"""
R2 Storage Utilities (Infrastructure)
====================================

Purpose:
Infrastructure for atomic R2 cache operations used by the acquisition engine and
low-level download code. Models do not import this directly.

Role in Flow:
Layer 4 (Infrastructure) – called by acquisition.py / downloads.py for:
- Atomic upload/restore with completion markers and manifests
- Manifest creation/validation and quick cache checks
- Prefix derivation from target_dir to guarantee in-place restores

Notes:
- Methods here are intentionally generic and side-effect free (besides I/O).
- Use download_helpers/acquisition from models; this module serves those layers.
"""

logger = get_logger(__name__)


class R2Utils:
    """
    Centralized utilities for R2 storage operations.

    This class consolidates common R2 patterns to eliminate code duplication
    and provide consistent behavior across the storage system.
    """

    # Constants for atomic operations
    COMPLETION_MARKER = ".r2_cache_complete"
    MANIFEST_FILE = ".r2_manifest.json"

    # Default chunk size for file operations
    DEFAULT_CHUNK_SIZE = 4096

    @staticmethod
    def calculate_file_checksum(
        file_path: Path, algorithm: str = "sha256", chunk_size: int = DEFAULT_CHUNK_SIZE
    ) -> str:
        """
        Calculate file checksum with chunked reading.

        Args:
            file_path: Path to file to checksum
            algorithm: Hash algorithm ('sha256', 'md5', etc.)
            chunk_size: Size of chunks to read (default 4096 bytes)

        Returns:
            Hexadecimal checksum string

        Examples:
            >>> R2Utils.calculate_file_checksum(Path("/models/config.json"))
            "a1b2c3d4e5f67890abcdef1234567890abcdef1234567890abcdef1234567890"
        """
        if not file_path.exists():
            raise FileNotFoundError(f"File does not exist: {file_path}")

        # Get hash function
        if algorithm == "sha256":
            file_hash = hashlib.sha256()
        elif algorithm == "md5":
            file_hash = hashlib.md5()
        else:
            raise ValueError(f"Unsupported algorithm: {algorithm}")

        # Read file in chunks to handle large files efficiently
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(chunk_size), b""):
                file_hash.update(chunk)

        return file_hash.hexdigest()

    @staticmethod
    def download_from_r2_prefix(
        r2_client,
        target_dir: Path,
        r2_prefix: str,
        bucket_name: str = r2_bucket_name,
        skip_patterns: Optional[list[str]] = None,
    ) -> int:
        """
        Download all files from R2 under a specific prefix using pagination.

        Args:
            r2_client: Initialized R2 client
            target_dir: Local directory to download to
            r2_prefix: R2 prefix to download from (without trailing slash)
            bucket_name: R2 bucket name
            skip_patterns: List of file patterns to skip (e.g., [".r2_cache_complete"])

        Returns:
            Number of files downloaded

        Examples:
            >>> client = get_r2_client()
            >>> count = R2Utils.download_from_r2_prefix(
            ...     client, Path("/models/esm2"), "esm2/v1"
            ... )
            >>> print(f"Downloaded {count} files")
        """
        files_downloaded = 0
        skip_patterns = skip_patterns or [
            R2Utils.COMPLETION_MARKER,
            R2Utils.MANIFEST_FILE,
        ]

        try:
            target_dir.mkdir(parents=True, exist_ok=True)

            # Use paginator for robust handling of any number of files
            paginator = r2_client.get_paginator("list_objects_v2")
            pages = paginator.paginate(Bucket=bucket_name, Prefix=f"{r2_prefix}/")

            for page in pages:
                if "Contents" not in page:
                    continue

                for obj in page["Contents"]:
                    key = obj["Key"]

                    # Skip patterns (completion markers, manifests, etc.)
                    if any(key.endswith(pattern) for pattern in skip_patterns):
                        continue

                    # Extract relative path from the key
                    relative_path = key[len(r2_prefix) + 1 :]  # +1 for the slash
                    if not relative_path:
                        continue

                    local_path = target_dir / relative_path
                    local_path.parent.mkdir(parents=True, exist_ok=True)

                    # Download the file with size-based optimization
                    file_size = obj.get("Size", 0)
                    from models.commons.storage.downloads import (
                        download_file_with_size_optimization,
                    )

                    download_file_with_size_optimization(
                        r2_client, bucket_name, key, str(local_path), file_size
                    )
                    files_downloaded += 1

                    if files_downloaded % 10 == 0:
                        logger.info("   📥 Downloaded %s files...", files_downloaded)

        except Exception as e:
            logger.error(
                "❌ Failed to download from R2 prefix %s: %s",
                r2_prefix,
                e,
                exc_info=True,
            )

        return files_downloaded

    @staticmethod
    def upload_completion_marker(
        r2_client,
        r2_prefix: str,
        bucket_name: str = r2_bucket_name,
        metadata: Optional[dict] = None,
    ) -> bool:
        """
        Upload atomic completion marker to signal successful cache operation.

        Args:
            r2_client: Initialized R2 client
            r2_prefix: R2 prefix (without trailing slash)
            bucket_name: R2 bucket name
            metadata: Optional metadata to include in marker

        Returns:
            True if upload succeeded

        Examples:
            >>> client = get_r2_client()
            >>> success = R2Utils.upload_completion_marker(
            ...     client, "esm2/v1", metadata={"files": 15}
            ... )
        """
        try:
            completion_key = f"{r2_prefix}/{R2Utils.COMPLETION_MARKER}"

            # Create completion data with timestamp
            completion_data = {
                "completed_at": time.time(),
                "r2_prefix": r2_prefix,
            }

            # Add any additional metadata
            if metadata:
                completion_data.update(metadata)

            # Upload completion marker atomically
            r2_client.put_object(
                Bucket=bucket_name,
                Key=completion_key,
                Body=json.dumps(completion_data, indent=2).encode("utf-8"),
                ContentType="application/json",
            )

            return True

        except Exception as e:
            logger.error("❌ Failed to upload completion marker: %s", e, exc_info=True)
            return False

    @staticmethod
    def check_completion_marker(
        r2_client,
        r2_prefix: str,
        bucket_name: str = r2_bucket_name,
        timeout_hours: Optional[int] = None,
    ) -> bool:
        """
        Check if completion marker exists and is valid.

        Args:
            r2_client: Initialized R2 client
            r2_prefix: R2 prefix (without trailing slash)
            bucket_name: R2 bucket name
            timeout_hours: Optional timeout in hours to consider marker valid

        Returns:
            True if completion marker exists and is valid

        Examples:
            >>> client = get_r2_client()
            >>> exists = R2Utils.check_completion_marker(client, "esm2/v1")
            >>> if exists:
            ...     print("Cache is complete and ready")
        """
        try:
            completion_key = f"{r2_prefix}/{R2Utils.COMPLETION_MARKER}"

            # Try to get the completion marker
            completion_obj = r2_client.get_object(
                Bucket=bucket_name, Key=completion_key
            )
            completion_data = json.loads(completion_obj["Body"].read().decode("utf-8"))

            # Check timeout if specified
            if timeout_hours:
                completed_at = completion_data.get("completed_at", 0)
                current_time = time.time()
                age_hours = (current_time - completed_at) / 3600

                if age_hours > timeout_hours:
                    logger.warning(
                        f"⚠️ Cache expired: {age_hours:.1f} hours old (timeout: {timeout_hours}h)"
                    )
                    return False

            return True

        except r2_client.exceptions.NoSuchKey:
            return False
        except Exception as e:
            logger.warning("⚠️ Error checking completion marker: %s", e)
            return False

    @staticmethod
    def create_manifest(source_dir: Path, include_checksums: bool = True) -> dict:
        """
        Create manifest with file metadata and optional checksums.

        Args:
            source_dir: Directory to create manifest for
            include_checksums: Whether to calculate SHA256 checksums

        Returns:
            Dictionary containing file manifest

        Examples:
            >>> manifest = R2Utils.create_manifest(Path("/models/esm2"))
            >>> print(f"Manifest contains {len(manifest)} files")
        """
        manifest = {}

        if not source_dir.exists():
            return manifest

        try:
            for file_path in source_dir.rglob("*"):
                if file_path.is_file():
                    relative_path = file_path.relative_to(source_dir)

                    file_info = {
                        "size": file_path.stat().st_size,
                        "mtime": file_path.stat().st_mtime,
                    }

                    # Add checksum if requested
                    if include_checksums:
                        file_info["sha256"] = R2Utils.calculate_file_checksum(file_path)

                    manifest[str(relative_path)] = file_info

        except Exception as e:
            logger.warning("⚠️ Error creating manifest: %s", e)

        return manifest

    @staticmethod
    def validate_manifest(
        target_dir: Path, manifest: dict, check_checksums: bool = True
    ) -> bool:
        """
        Validate files against manifest metadata.

        Args:
            target_dir: Directory containing files to validate
            manifest: Manifest dictionary with file metadata
            check_checksums: Whether to validate SHA256 checksums

        Returns:
            True if all files validate successfully

        Examples:
            >>> manifest = R2Utils.create_manifest(source_dir)
            >>> valid = R2Utils.validate_manifest(target_dir, manifest)
            >>> if not valid:
            ...     print("Validation failed!")
        """
        try:
            for relative_path, file_metadata in manifest.items():
                file_path = target_dir / relative_path

                # Check if file exists
                if not file_path.exists():
                    logger.error("❌ Missing file: %s", relative_path)
                    return False

                # Check file size
                actual_size = file_path.stat().st_size
                expected_size = file_metadata.get("size", 0)
                if actual_size != expected_size:
                    logger.error(
                        "❌ Size mismatch for %s: expected %s, got %s",
                        relative_path,
                        expected_size,
                        actual_size,
                    )
                    return False

                # Check SHA256 hash if present and requested
                if check_checksums and "sha256" in file_metadata:
                    expected_sha256 = file_metadata["sha256"]
                    actual_sha256 = R2Utils.calculate_file_checksum(file_path)

                    if actual_sha256 != expected_sha256:
                        logger.error("❌ Checksum mismatch for %s", relative_path)
                        logger.error("   Expected: %s", expected_sha256)
                        logger.error("   Actual:   %s", actual_sha256)
                        return False

            return True

        except Exception as e:
            logger.error("❌ Manifest validation error: %s", e, exc_info=True)
            return False

    @staticmethod
    def _upload_file_to_r2(
        r2_client, file_path: Path, r2_key: str, bucket_name: str
    ) -> None:
        """Upload a single file to R2 with size-based optimization."""
        from models.commons.storage.downloads import upload_file_with_size_optimization

        file_size = file_path.stat().st_size
        upload_file_with_size_optimization(
            r2_client, bucket_name, r2_key, str(file_path), file_size
        )

    @staticmethod
    def _create_file_manifest_entry(file_path: Path) -> dict:
        """Create manifest entry for a file."""
        return {
            "size": file_path.stat().st_size,
            "sha256": R2Utils.calculate_file_checksum(file_path),
            "mtime": file_path.stat().st_mtime,
        }

    @staticmethod
    def _upload_manifest_to_r2(
        r2_client, manifest: dict, r2_prefix: str, bucket_name: str
    ) -> bool:
        """Upload manifest to R2."""
        if not manifest:
            return False

        manifest_key = f"{r2_prefix}/{R2Utils.MANIFEST_FILE}"
        manifest_content = json.dumps(manifest, indent=2)
        r2_client.put_object(
            Bucket=bucket_name,
            Key=manifest_key,
            Body=manifest_content.encode("utf-8"),
            ContentType="application/json",
        )
        return True

    @staticmethod
    def _report_upload_progress(
        file_name: str,
        file_num: int,
        total_files: int,
        bytes_uploaded: int,
        total_bytes: int,
        progress_callback: Optional[Callable[[dict], None]] = None,
    ) -> None:
        """Report detailed upload progress with size and file information."""
        percent = (bytes_uploaded / total_bytes * 100) if total_bytes > 0 else 0
        size_mb = bytes_uploaded / (1024 * 1024)
        total_mb = total_bytes / (1024 * 1024)

        # Always report for small file counts, or every 10 for large counts
        if total_files <= 10 or file_num % 10 == 0:
            logger.info(
                f"   📤 [{file_num}/{total_files}] Uploaded {file_name} "
                f"({size_mb:.1f}/{total_mb:.1f} MB, {percent:.0f}%)"
            )

        if progress_callback:
            progress_callback(
                {
                    "file_name": file_name,
                    "file_num": file_num,
                    "total_files": total_files,
                    "bytes_uploaded": bytes_uploaded,
                    "total_bytes": total_bytes,
                    "percent": percent,
                }
            )

    @staticmethod
    def upload_to_r2_atomic(
        source_dir: Path,
        r2_prefix: str,
        bucket_name: str = r2_bucket_name,
        create_manifest: bool = True,
        progress_callback: Optional[Callable[[dict], None]] = None,
    ) -> bool:
        """
        Atomically upload directory to R2 with completion marker.

        Args:
            source_dir: Local directory to upload
            r2_prefix: R2 prefix (without trailing slash)
            bucket_name: R2 bucket name
            create_manifest: Whether to create and upload manifest
            progress_callback: Optional callback for upload progress

        Returns:
            True if upload succeeded

        Examples:
            >>> success = R2Utils.upload_to_r2_atomic(
            ...     Path("/models/esm2"), "esm2/v1/8b"
            ... )
            >>> if success:
            ...     print("Upload completed successfully")
        """
        if not source_dir.exists():
            logger.error("❌ Source directory does not exist: %s", source_dir)
            return False

        try:
            r2_client = get_r2_client()
            logger.info("🔄 Starting atomic upload to R2: %s", r2_prefix)

            # Pre-scan to count files and calculate total size
            files_to_upload = []
            total_bytes = 0
            for file_path in source_dir.rglob("*"):
                if file_path.is_file():
                    file_size = file_path.stat().st_size
                    files_to_upload.append((file_path, file_size))
                    total_bytes += file_size

            total_files = len(files_to_upload)
            if total_files == 0:
                logger.warning("⚠️ No files to upload in %s", source_dir)
                return False

            # Report what we're about to upload
            total_mb = total_bytes / (1024 * 1024)
            logger.info(
                f"📊 Preparing to upload {total_files} files ({total_mb:.1f} MB total)..."
            )

            manifest = {}
            bytes_uploaded = 0

            # Upload all files with progress tracking
            for file_num, (file_path, file_size) in enumerate(files_to_upload, 1):
                relative_path = file_path.relative_to(source_dir)
                r2_key = f"{r2_prefix}/{relative_path}"

                # Add to manifest if needed
                if create_manifest:
                    manifest[str(relative_path)] = R2Utils._create_file_manifest_entry(
                        file_path
                    )

                # Upload file
                R2Utils._upload_file_to_r2(r2_client, file_path, r2_key, bucket_name)

                # Update progress
                bytes_uploaded += file_size
                R2Utils._report_upload_progress(
                    file_name=str(relative_path),
                    file_num=file_num,
                    total_files=total_files,
                    bytes_uploaded=bytes_uploaded,
                    total_bytes=total_bytes,
                    progress_callback=progress_callback,
                )

            # Upload manifest
            manifest_uploaded = (
                R2Utils._upload_manifest_to_r2(
                    r2_client, manifest, r2_prefix, bucket_name
                )
                if create_manifest
                else False
            )

            # Upload completion marker (atomic commit)
            completion_metadata = {
                "file_count": total_files,
                "manifest_uploaded": manifest_uploaded,
            }
            if manifest_uploaded:
                completion_metadata["manifest_key"] = (
                    f"{r2_prefix}/{R2Utils.MANIFEST_FILE}"
                )

            success = R2Utils.upload_completion_marker(
                r2_client, r2_prefix, bucket_name, completion_metadata
            )

            if success:
                logger.info(
                    "✅ Atomic upload complete: %s files to %s", total_files, r2_prefix
                )

            return success

        except Exception as e:
            logger.error("❌ Atomic upload failed: %s", e, exc_info=True)
            return False

    @staticmethod
    def restore_from_r2_atomic(
        target_dir: Path,
        r2_prefix: str,
        bucket_name: str = r2_bucket_name,
        validate_manifest: bool = True,
        timeout_hours: Optional[int] = None,
    ) -> bool:
        """
        Atomically restore directory from R2 with validation.

        Args:
            target_dir: Local directory to restore to
            r2_prefix: R2 prefix (without trailing slash)
            bucket_name: R2 bucket name
            validate_manifest: Whether to validate using manifest checksums
            timeout_hours: Optional cache timeout in hours

        Returns:
            True if restore succeeded

        Examples:
            >>> success = R2Utils.restore_from_r2_atomic(
            ...     Path("/models/esm2"), "esm2/v1/8b"
            ... )
            >>> if success:
            ...     print("Restore completed successfully")
        """
        try:
            # Credential-less public read: with no S3 creds present, restore the
            # cached weights anonymously over HTTPS from the bucket's public URL.
            # r2.dev has no LIST, so the manifest drives the fetch. Writes still
            # need creds, so this branch only ever reads.
            from models.commons.storage.r2 import r2_credentials_present
            from models.commons.util.config import r2_public_url

            if not r2_credentials_present() and r2_public_url:
                from models.commons.storage.r2_http import restore_weights_via_http

                return restore_weights_via_http(target_dir, r2_prefix, r2_public_url)

            r2_client = get_r2_client()

            # Check for completion marker first
            if not R2Utils.check_completion_marker(
                r2_client, r2_prefix, bucket_name, timeout_hours
            ):
                logger.warning("⚠️ No valid completion marker found at %s", r2_prefix)
                return False

            logger.info("🔄 Starting atomic restore from R2: %s", r2_prefix)

            # Download files from R2
            target_dir.mkdir(parents=True, exist_ok=True)
            files_downloaded = R2Utils.download_from_r2_prefix(
                r2_client, target_dir, r2_prefix, bucket_name
            )

            if files_downloaded == 0:
                logger.warning("⚠️ No files found under prefix %s", r2_prefix)
                return False

            # Validate manifest if requested and available
            if validate_manifest:
                manifest_key = f"{r2_prefix}/{R2Utils.MANIFEST_FILE}"
                try:
                    manifest_obj = r2_client.get_object(
                        Bucket=bucket_name, Key=manifest_key
                    )
                    manifest_data = json.loads(
                        manifest_obj["Body"].read().decode("utf-8")
                    )

                    logger.info(
                        "🔍 Validating %s files using manifest checksums...",
                        len(manifest_data),
                    )
                    if not R2Utils.validate_manifest(target_dir, manifest_data):
                        logger.error("❌ Manifest validation failed")
                        return False
                    logger.info("✅ Manifest validation successful")

                except r2_client.exceptions.NoSuchKey:
                    logger.warning("⚠️ No manifest found, skipping checksum validation")
                except Exception as e:
                    logger.warning("⚠️ Manifest validation failed: %s", e)
                    return False

            logger.info(
                "✅ Atomic restore complete: %s files to %s",
                files_downloaded,
                target_dir,
            )
            return True

        except Exception as e:
            logger.error("❌ Atomic restore failed: %s", e, exc_info=True)
            return False

    @staticmethod
    def get_r2_prefix_from_target_dir(target_dir: Path) -> str:
        """
        Extract the R2 prefix from the target directory path.

        This ensures all strategies use the same biolm-hub/model-weights/models structure for R2 caching.

        Args:
            target_dir: Target directory path

        Returns:
            R2 prefix string (without leading slash)

        Examples:
            >>> R2Utils.get_r2_prefix_from_target_dir(Path("/biolm-hub/model-weights/models/esm2/v1"))
            "biolm-hub/model-weights/models/esm2/v1"
        """
        # The local model dir is rooted at the configured store prefix (e.g.
        # "biolm-hub/model-weights/models"), so the R2 prefix mirrors it. Extract from the prefix.
        target_str = str(target_dir).replace("\\", "/")
        if r2_model_store_dir in target_str:
            idx = target_str.index(r2_model_store_dir)
            return target_str[idx:].lstrip("/")
        # Fallback: relative path from root (already correct for store-rooted dirs).
        return target_str.lstrip("/")

    @staticmethod
    def check_r2_cache_exists(
        r2_prefix: str, bucket_name: str = r2_bucket_name
    ) -> bool:
        """
        Quick check if R2 cache exists by looking for completion marker.

        Args:
            r2_prefix: R2 prefix to check
            bucket_name: R2 bucket name

        Returns:
            True if cache exists (completion marker found)

        Examples:
            >>> if R2Utils.check_r2_cache_exists("biolm-hub/model-weights/models/esm2/v1"):
            ...     print("Cache exists")
        """
        try:
            r2_client = get_r2_client()
            completion_marker = f"{r2_prefix}/{R2Utils.COMPLETION_MARKER}"
            r2_client.head_object(Bucket=bucket_name, Key=completion_marker)
            return True
        except r2_client.exceptions.NoSuchKey:
            return False
        except Exception:
            return False
