import os
import sys
from pathlib import Path
from typing import Optional

import modal

from models.commons.core.logging import get_logger
from models.commons.util.config import (
    cloudflare_r2_secret,
    huggingface_api_token_secret,
    skip_modal_secrets,
)

logger = get_logger(__name__)

"""
Modal Download Layer
====================

Purpose:
Isolate model weight downloads during Modal image builds to maximize Docker layer
caching. Parameters are passed via kwargs to keep the layer stable.

Role in Flow:
This layer adds a minimal subset of commons and the model's `download.py`, then
executes `download_model_assets(...)` with explicit kwargs.

Why this exists:
- We want weights cached independently from frequent code changes in app.py.
- Copying only minimal files preserves build cache and avoids cache busting.

Primary APIs:
- setup_download_layer(): add minimal files, install deps, run download with kwargs
- _run_download_with_params(): executes with `base_model_slug`, `weights_version`,
  optional `variant_config` and `sub_path`.
"""

# Credential-less deploys. A user whose Modal workspace has no `cloudflare-r2` /
# `hf-api-token` secret cannot mount them: Modal 1.3.5's `Secret.from_name` has no
# `required=False`, and a missing named secret aborts the deploy before it starts. Set
# BIOLM_SKIP_MODAL_SECRETS=1 to mount NO download secrets — the deploy then starts and
# the build/runtime reads public weights anonymously over r2.dev (no self-population;
# that needs credentials). Maintainer deploys leave it unset and self-populate as before.
#
# We deliberately do NOT probe secret existence here: hydrating a secret requires Modal
# auth + a network round-trip, and this runs at import of every model's app.py (the
# download layer is built at module scope). Importing app.py must stay credential-free
# and network-free so unit-test collection, docs generation, and schema checks work with
# no Modal token. `Secret.from_name` is lazy, so mounting the references is import-safe;
# Modal resolves them at deploy/build time. The skip-flag check (`skip_modal_secrets`,
# same truthy vocabulary as BIOLM_CACHE_ENABLED) is centralized in
# models.commons.util.config so the build and runtime layers stay in lockstep.


def _available_download_secrets() -> list[modal.Secret]:
    """Download secrets to mount — resolution deferred to deploy time (no import-time I/O).

    - Default (maintainer / CI with the secrets provisioned): mount `cloudflare-r2` +
      `hf-api-token` as lazy `Secret.from_name` references; the build self-populates the
      public R2 bucket with credentials. Unchanged from prior behavior.
    - BIOLM_SKIP_MODAL_SECRETS truthy (credential-less user): mount nothing, so a deploy
      starts even with no secrets provisioned and the build/runtime reads public weights
      anonymously over r2.dev (`r2_credentials_present()` is False in-container).
    """
    if skip_modal_secrets():
        logger.info(
            "BIOLM_SKIP_MODAL_SECRETS set — mounting no download secrets; the build "
            "will read public weights anonymously over HTTP (no self-population)."
        )
        return []
    return [cloudflare_r2_secret, huggingface_api_token_secret]


def setup_download_layer(
    image: modal.Image,
    base_model_slug: str,
    weights_version: str,
    variant_config: Optional[dict[str, str]] = None,
    sub_path: Optional[str] = None,
    extra_pip_packages: Optional[list[str]] = None,
) -> modal.Image:
    """Add model download layer to Modal image using direct parameter passing.

    Args:
        image: Base Modal image to build upon
        base_model_slug: Model identifier (e.g., "esm2", "ablang2")
        weights_version: Version of model parameters to download
        variant_config: Dictionary containing all variant configuration
        sub_path: Optional subdirectory for model storage
        extra_pip_packages: Additional pip packages needed for download

    Returns:
        Modal image with download layer configured
    """
    model_folder_name = base_model_slug.replace("-", "_")

    # Step 1: Add minimal commons dependencies needed for download
    image = _add_minimal_commons(image, model_folder_name)

    # Step 2: Add model's download module
    downloader_file = Path(__file__).resolve()
    repo_root = downloader_file.parent.parent.parent.parent
    download_module = repo_root / "models" / model_folder_name / "download.py"

    if not download_module.exists():
        raise FileNotFoundError(
            f"Download module not found: {download_module}\n"
            f"Current working directory: {os.getcwd()}\n"
            f"Expected location: {download_module}"
        )
    image = image.add_local_file(download_module, "/root/download.py", copy=True)

    # Step 3: Install download dependencies
    base_packages = [
        "boto3==1.35.78",
        "pydantic>=2.0,<3.0",
        "requests>=2.28.0,<3.0",  # Updated to support urllib3>=2.0 for chai-lab compatibility
    ]

    all_packages = base_packages + (extra_pip_packages or [])

    image = image.uv_pip_install(*all_packages)

    # Step 4: Add unique identifiers to prevent Modal cache collisions
    # These ensure each model gets its own download layer cached separately
    envs_to_add = {
        "_BIOLM_BASE_MODEL_SLUG": base_model_slug,
        "_BIOLM_WEIGHTS_VERSION": weights_version,
    }

    # Add variant config if present (for both runtime and cache distinction)
    if variant_config:
        envs_to_add.update(variant_config)

    image = image.env(envs_to_add)

    # Step 5: Compute source hash to bust run_function cache when download
    # logic changes. Modal's run_function only hashes the function body and
    # kwargs — it does NOT detect changes to files the function imports at
    # runtime (e.g., download.py, acquisition.py). By including a content
    # hash of all mounted source files in the kwargs, we ensure the download
    # layer rebuilds whenever any download-related code changes.
    source_hash = _compute_download_source_hash(
        repo_root, model_folder_name, download_module
    )

    # Step 6: Execute download function.
    # Mount the download secrets unless BIOLM_SKIP_MODAL_SECRETS opts out, so a
    # credential-less deploy can still START (see _available_download_secrets).
    image = image.run_function(
        _run_download_with_params,
        secrets=_available_download_secrets(),
        kwargs={
            "base_model_slug": base_model_slug,
            "weights_version": weights_version,
            "variant_config": variant_config,
            "sub_path": sub_path,
            "_source_hash": source_hash,
        },
    )

    return image


def _download_layer_source_files(model_folder_name: str) -> list[str]:
    """Repo-relative source files the download layer mounts into the container.

    Single source of truth shared by ``_add_minimal_commons`` (which copies these
    into the image) and ``_compute_download_source_hash`` (which hashes them to
    bust Modal's run_function cache). Keeping ONE list guarantees the cache-busting
    hash covers exactly the files that are mounted: a new import added to the mount
    can never be silently left out of the hash (which would leave a stale weights
    layer), and a hashed file can never be missing from the mount (which would be
    an ImportError at build time). The model's ``download.py`` is mounted and
    hashed separately (see ``setup_download_layer`` / ``_compute_download_source_hash``).
    """
    return [
        # Package structure
        "models/__init__.py",
        "models/commons/__init__.py",
        # Storage modules
        "models/commons/storage/__init__.py",
        "models/commons/storage/downloads.py",
        "models/commons/storage/r2.py",
        "models/commons/storage/acquisition.py",
        "models/commons/storage/download_helpers.py",
        "models/commons/storage/r2_utils.py",
        # Configuration utilities
        "models/commons/util/__init__.py",
        "models/commons/util/config.py",
        "models/commons/util/environment.py",
        # Model-related modules
        "models/commons/model/__init__.py",
        "models/commons/model/pydantic.py",
        "models/commons/model/schema.py",
        # Model-specific files that may be imported during download
        f"models/{model_folder_name}/__init__.py",
        f"models/{model_folder_name}/schema.py",
        f"models/{model_folder_name}/config.py",
    ]


def _compute_download_source_hash(
    repo_root: Path, model_folder_name: str, download_module: Path
) -> str:
    """Compute a content hash of all source files used during download.

    Modal's run_function caches based on function source code and kwargs only.
    It does NOT detect changes to files imported at runtime inside the container.
    This hash ensures the download layer rebuilds when any download-related
    source file changes. It hashes EXACTLY the set mounted by
    ``_add_minimal_commons`` (plus the model's ``download.py``) via the shared
    ``_download_layer_source_files`` list, so the mounted closure and the hashed
    closure can never drift apart.
    """
    import hashlib

    h = hashlib.sha256()

    # Hash the model's download.py (mounted separately as /root/download.py)
    if download_module.exists():
        h.update(download_module.read_bytes())

    # Hash exactly the files mounted into the download container.
    for rel_path in sorted(_download_layer_source_files(model_folder_name)):
        full_path = repo_root / rel_path
        if full_path.exists():
            h.update(full_path.read_bytes())

    return h.hexdigest()[:16]


def _add_minimal_commons(image: modal.Image, model_folder_name: str) -> modal.Image:
    """Add minimal commons files required for download operations.

    Only includes essential modules to minimize image layer size.
    Optimized to use a single add_local_dir operation for better layer caching.

    Args:
        image: Modal image to add files to
        model_folder_name: Model folder name (e.g., "esm2", "ablang2")
    """
    # Find repo root relative to this file
    downloader_file = Path(__file__).resolve()
    repo_root = downloader_file.parent.parent.parent.parent

    # Shared with _compute_download_source_hash so the mounted set and the
    # cache-busting hash always cover exactly the same files.
    all_files = _download_layer_source_files(model_folder_name)

    # Optimized approach: collect all files and use a temporary directory
    # This results in a single layer operation instead of multiple individual file adds
    import atexit
    import shutil
    import tempfile

    # Create temp directory manually without context manager to control lifecycle
    tmpdir = tempfile.mkdtemp(prefix="modal_build_")
    tmp_path = Path(tmpdir)

    # Register cleanup for process exit (as a safety net)
    # This ensures the directory is cleaned up when the process exits
    def cleanup_tmpdir() -> None:
        try:
            shutil.rmtree(tmpdir, ignore_errors=True)
        except Exception:
            pass

    # The atexit handler will clean up temp files when the process exits
    atexit.register(cleanup_tmpdir)

    # Copy all required files to temp directory, preserving structure
    for file_path in all_files:
        local_file = repo_root / file_path
        if local_file.exists():
            # Create the destination path in temp directory
            dest_path = tmp_path / file_path
            dest_path.parent.mkdir(parents=True, exist_ok=True)
            # Copy the file preserving metadata
            shutil.copy2(local_file, dest_path)

    # Single add_local_dir call - most efficient for Modal layer caching
    # This creates a single layer with all files instead of multiple layers
    image = image.add_local_dir(
        tmp_path, "/root", copy=True  # Include in image layer for proper caching
    )

    return image


def _run_download_with_params(
    base_model_slug: str,
    weights_version: str,
    sub_path: Optional[str] = None,
    variant_config: Optional[dict[str, str]] = None,
    _source_hash: Optional[str] = None,
) -> None:
    """Execute download function with explicit parameters.

    The _source_hash kwarg is not used at runtime — it exists solely to bust
    Modal's run_function cache when download-related source files change.
    """
    sys.path.insert(0, "/root")

    from download import download_model_assets

    # Call with explicit parameters
    download_model_assets(
        base_model_slug=base_model_slug,
        weights_version=weights_version,
        variant_config=variant_config,
        sub_path=sub_path,
    )
