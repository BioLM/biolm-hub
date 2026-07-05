import os
import sys
from pathlib import Path
from typing import Optional

import modal
from modal.exception import NotFoundError

from models.commons.core.logging import get_logger
from models.commons.util.config import (
    cloudflare_r2_secret,
    cloudflare_r2_secret_name,
    huggingface_api_token_secret,
    huggingface_api_token_secret_name,
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

# Escape hatch: force a fully credential-less build even on a workspace that DOES have
# the secrets. When truthy, skip the Modal existence probe entirely and mount no
# secrets, so the build reads public weights anonymously over r2.dev. Useful for
# exercising the credential-less happy path (and Milestone-B verification) from a
# maintainer workspace. Same truthy vocabulary as BIOLM_CACHE_ENABLED.
_SKIP_SECRETS_TRUTHY = {"1", "true", "yes"}


def _skip_modal_secrets() -> bool:
    """True if BIOLM_SKIP_MODAL_SECRETS opts out of mounting download secrets."""
    return (
        os.getenv("BIOLM_SKIP_MODAL_SECRETS", "").strip().lower()
        in _SKIP_SECRETS_TRUTHY
    )


def _secret_exists(secret_name: str) -> bool:
    """Return True if a named Modal secret is provisioned in the target workspace.

    Modal 1.3.5's ``Secret.from_name`` has no ``required=False`` (verified against the
    installed version — its only relevant kwarg is ``required_keys``), and Modal
    resolves *every* mounted secret by name at deploy/build time, so a missing named
    secret aborts the entire deploy before it starts. That would make the
    credential-less happy path impossible: a user whose Modal workspace has no
    ``cloudflare-r2`` / ``hf-api-token`` secret could not even begin a deploy.

    So we probe existence ourselves with a throwaway reference. The deploy runs in the
    same process and ambient ``MODAL_ENVIRONMENT`` as this graph construction (``bh
    deploy`` shells out to ``app.py`` inheriting ``os.environ``), so the probe resolves
    against the exact environment the real mount would use. A ``NotFoundError`` means
    the secret is genuinely absent -> return False so the caller omits it. Any other
    error (network/auth) propagates: the deploy needs Modal reachable regardless, and
    we must not silently drop a maintainer's secret over a transient blip.
    """
    try:
        modal.Secret.from_name(secret_name).hydrate()
        return True
    except NotFoundError:
        return False


def _available_download_secrets() -> list[modal.Secret]:
    """Return only the download secrets that exist in the workspace (see _secret_exists).

    Behavior by workspace, mirroring the credential-gated read path in
    ``storage.acquisition``/``storage.r2_utils`` (``r2_credentials_present()``):

    - Both present (maintainer / CI): both mounted -> the build reads and *self-populates*
      the public R2 bucket with credentials. Unchanged from prior behavior.
    - Neither present (credential-less user): none mounted -> the deploy still STARTS, and
      inside the build container ``r2_credentials_present()`` is False, so weight
      acquisition takes the anonymous public-HTTP path (r2.dev). Self-population is
      skipped; reads work.
    - Exactly one present: only that one is mounted.

    We mount the shared module-level secret objects (not the throwaway probe references)
    so Modal re-resolves them fresh against the deploy's environment during the build.
    """
    if _skip_modal_secrets():
        logger.info(
            "BIOLM_SKIP_MODAL_SECRETS set — mounting no download secrets; the build "
            "will read public weights anonymously over HTTP (no self-population)."
        )
        return []

    candidates = [
        (cloudflare_r2_secret, cloudflare_r2_secret_name),
        (huggingface_api_token_secret, huggingface_api_token_secret_name),
    ]
    available: list[modal.Secret] = []
    mounted_names: list[str] = []
    for secret, name in candidates:
        if _secret_exists(name):
            available.append(secret)
            mounted_names.append(name)

    if mounted_names:
        logger.info("Download layer: mounting Modal secrets %s", mounted_names)
    else:
        logger.info(
            "Download layer: no download secrets found in this Modal workspace — "
            "proceeding credential-less. Public weights are read anonymously over "
            "HTTP; self-population is skipped (needs credentials)."
        )
    return available


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
    # Mount ONLY the secrets that actually exist in the target Modal workspace so a
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


def _compute_download_source_hash(
    repo_root: Path, model_folder_name: str, download_module: Path
) -> str:
    """Compute a content hash of all source files used during download.

    Modal's run_function caches based on function source code and kwargs only.
    It does NOT detect changes to files imported at runtime inside the container.
    This hash ensures the download layer rebuilds when any download-related
    source file changes (commons storage modules, model download.py, schema, etc.).
    """
    import hashlib

    h = hashlib.sha256()

    # Hash the model's download.py
    if download_module.exists():
        h.update(download_module.read_bytes())

    # Hash essential commons files that are mounted into the download container
    commons_files = [
        "models/commons/storage/downloads.py",
        "models/commons/storage/acquisition.py",
        "models/commons/storage/download_helpers.py",
        "models/commons/storage/r2.py",
        "models/commons/storage/r2_utils.py",
        "models/commons/util/config.py",
        f"models/{model_folder_name}/schema.py",
        f"models/{model_folder_name}/config.py",
    ]

    for rel_path in sorted(commons_files):
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

    essential_files = [
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
    ]

    # Add model-specific files that may be imported during download
    model_specific_files = [
        f"models/{model_folder_name}/__init__.py",
        f"models/{model_folder_name}/schema.py",
        f"models/{model_folder_name}/config.py",
    ]

    all_files = essential_files + model_specific_files

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
