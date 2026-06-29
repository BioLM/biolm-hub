from collections.abc import Callable
from pathlib import Path
from typing import Any, Optional

from models.commons.core.logging import get_logger
from models.commons.storage.acquisition import (
    AcquisitionConfig,
    AcquisitionResult,
    AcquisitionStrategy,
    CacheConfig,
    CustomSourceConfig,
    HfSourceConfig,
    LibrarySourceConfig,
    R2OnlyConfig,
    UrlSourceConfig,
    ValidationConfig,
    acquire_model_weights,
)

"""
High-Level Download Helpers (Preferred API)
==========================================

Purpose:
Thin, ergonomic wrappers around the acquisition engine. Most models use these
helpers to implement (a) legacy direct-from-R2 or (b) check-R2-then-fetch-and-
cache flows with minimal boilerplate.

Role in Flow:
Layer 1 (Top) → Uses acquisition.py (strategies) → downloads.py (low-level ops)

Common patterns:
- standard_r2_download(...): R2-only (legacy/compat)
- download_with_fallback(primary, fallback): try R2, then source (HF/library/URLs)
- acquire_library_managed_model(...): DEPRECATED — prefer r2_then_library
- extract_model_variant(...): fetch variant axes from variant_config

Notes:
- Prefer these helpers from models/*/download.py; acquire_model_weights is still
  available for advanced/custom scenarios.
"""

logger = get_logger(__name__)


def standard_r2_download(
    base_model_slug: Optional[str] = None,
    params_version: Optional[str] = None,
    model_variant: Optional[str] = None,
    sub_path: Optional[str] = None,
    target_dir: Optional[Path] = None,
    force_download: bool = False,
    filter_func: Optional[Callable[[str], bool]] = None,
    required_files: Optional[list[str]] = None,
) -> AcquisitionResult:
    """
    Simple wrapper for R2-only downloads with standard configuration.

    R2-only; cannot self-populate. Prefer a fallback wrapper
    (``r2_then_hf`` / ``r2_then_urls`` / ``r2_then_library`` / ``r2_then_archive``)
    so a missing R2 cache fetches from the original source. Use this only for a
    model with no fetchable upstream source (e.g. the self-trained ``esmstabp``).

    Args:
        base_model_slug: Model family identifier
        params_version: Parameter version
        model_variant: Model size/variant
        sub_path: Subdirectory path
        target_dir: Custom target directory (computed if None)
        force_download: Force re-download even if files exist
        filter_func: Optional function to filter which files to download
        required_files: Optional list of files to validate after download

    Returns:
        AcquisitionResult with download status and metadata

    Examples:
        >>> # Pass explicit kwargs (recommended)
        >>> result = standard_r2_download(
        ...     base_model_slug="esm2",
        ...     params_version="v1",
        ...     model_variant="8b",
        ...     required_files=["model.pt", "config.json"],
        ...     filter_func=lambda k: k.endswith(".pt"),
        ... )
    """
    # Validate required parameters
    if not base_model_slug:
        raise ValueError("base_model_slug is required for standard_r2_download")
    if not params_version:
        raise ValueError("params_version is required for standard_r2_download")

    # Create R2 configuration
    r2_config = R2OnlyConfig(
        base_model_slug=base_model_slug,
        params_version=params_version,
        model_variant=model_variant,
        sub_path=sub_path,
        filter_func=filter_func,
    )

    # Create cache configuration
    cache_config = CacheConfig(
        enable_r2_cache=True,
        force_download=force_download,
    )

    # Create validation configuration
    validation_config = ValidationConfig(
        required_files=required_files,
    )

    # Determine target directory (use default path resolution if not specified)
    if target_dir is None:
        from models.commons.storage.downloads import get_model_dir_util

        target_dir = get_model_dir_util(
            base_model_slug=base_model_slug,
            params_version=params_version,
            model_variant=model_variant,
            sub_path=sub_path,
        )

    # Create acquisition configuration
    config = AcquisitionConfig(
        strategy=AcquisitionStrategy.R2_ONLY,
        target_dir=target_dir,
        cache_config=cache_config,
        validation_config=validation_config,
        r2_config=r2_config,
    )

    # Execute acquisition
    return acquire_model_weights(config)


def acquire_library_managed_model(
    library_name: str,
    target_dir: Path,
    init_fn: Optional[Callable[[Path], Any]] = None,
    monitor_directories: Optional[list[str]] = None,
    env_vars: Optional[dict] = None,
    cache_to_r2: bool = True,
    required_files: Optional[list[str]] = None,
) -> AcquisitionResult:
    """
    Library-managed acquisition with optional R2 caching.

    .. deprecated::
        Prefer :func:`r2_then_library`, which adds the marker-gated R2-primary
        read in front of the library download. This wrapper is retained only
        until the remaining callers migrate, after which it is removed.

    This function lets libraries manage their own downloads while providing
    R2 caching.

    Args:
        library_name: Name of the library managing the download
        target_dir: Directory where the model should be downloaded
        init_fn: Function that triggers the library's download (returns model path)
        monitor_directories: Retained for caller compatibility; no longer read
            (the bypass detector that consumed it was removed).
        env_vars: Optional dictionary of environment variables to set
        cache_to_r2: Whether to cache downloaded model to R2
        required_files: Optional list of files to validate after download

    Returns:
        AcquisitionResult with download status

    Examples:
        >>> def init_esm3(target_dir):
        ...     from models.commons.storage.downloads import setup_hf_cache_env
        ...     setup_hf_cache_env(target_dir)
        ...     from esm.models.esm3 import ESM3
        ...     ESM3.from_pretrained("esm3-sm-open-v1", device="cpu")
        ...     return target_dir

        >>> result = acquire_library_managed_model(
        ...     library_name="esm3",
        ...     target_dir=Path("/models/esm3"),
        ...     init_fn=init_esm3,
        ... )
    """
    # Create library configuration
    library_config = LibrarySourceConfig(
        library_name=library_name,
        monitor_directories=monitor_directories,
        env_vars=env_vars,
    )

    # Create cache configuration
    cache_config = CacheConfig(
        enable_r2_cache=cache_to_r2,
    )

    # Create validation configuration
    validation_config = ValidationConfig(
        required_files=required_files,
    )

    # Create acquisition configuration
    config = AcquisitionConfig(
        strategy=AcquisitionStrategy.LIBRARY_MANAGED,
        target_dir=target_dir,
        cache_config=cache_config,
        validation_config=validation_config,
        library_config=library_config,
        custom_function=init_fn,
    )

    # Execute acquisition
    return acquire_model_weights(config)


def download_with_fallback(
    primary_config: AcquisitionConfig,
    fallback_config: AcquisitionConfig,
) -> AcquisitionResult:
    """
    Attempt primary acquisition strategy, fallback to secondary if it fails.

    Args:
        primary_config: Primary acquisition configuration to try first
        fallback_config: Fallback configuration if primary fails

    Returns:
        AcquisitionResult from whichever strategy succeeded

    Examples:
        >>> # Try R2 first, fallback to HuggingFace
        >>> primary = AcquisitionConfig(strategy=AcquisitionStrategy.R2_ONLY, ...)
        >>> fallback = AcquisitionConfig(strategy=AcquisitionStrategy.HUGGINGFACE_HUB, ...)
        >>> result = download_with_fallback(primary, fallback)
    """
    logger.info("🔄 [download_helpers.py] Attempting primary acquisition strategy...")
    primary_result = acquire_model_weights(primary_config)

    if primary_result.success:
        logger.info("✅ [download_helpers.py] Primary strategy succeeded")
        return primary_result

    logger.warning(
        "⚠️ [download_helpers.py] Primary strategy failed: %s",
        primary_result.error_message,
    )
    logger.info("🔄 [download_helpers.py] Attempting fallback strategy...")

    fallback_result = acquire_model_weights(fallback_config)

    if fallback_result.success:
        logger.info("✅ [download_helpers.py] Fallback strategy succeeded")
    else:
        logger.error(
            "❌ [download_helpers.py] Fallback strategy also failed: %s",
            fallback_result.error_message,
        )

    return fallback_result


def build_model_type_filter(
    checkpoint_mapping: dict,
    model_type: str,
    allowed_values: Optional[type] = None,
    include_files: Optional[list[str]] = None,
) -> Callable[[str], bool]:
    """
    Build filter functions based on model type from variant_config.

    Args:
        checkpoint_mapping: Dict mapping model types to checkpoint filenames
        model_type: The model type (e.g., from variant_config["MODEL_TYPE"])
        allowed_values: Enum class for validation (optional)
        include_files: Additional files to always include

    Returns:
        Filter function for use with standard_r2_download

    Example:
        # For ImmuneFold:
        from models.immunefold.config import model_id_mapping, ImmuneFoldModelTypes

        model_type = extract_model_variant(variant_config, "MODEL_TYPE")
        filter_func = build_model_type_filter(
            checkpoint_mapping=model_id_mapping,
            model_type=model_type,
            allowed_values=ImmuneFoldModelTypes,
            include_files=[".pt"]
        )
        return standard_r2_download(filter_func=filter_func)
    """
    # Validate against allowed values if provided
    if allowed_values and hasattr(allowed_values, "__members__"):
        valid_values = [e.value for e in allowed_values]
        if model_type not in valid_values:
            raise ValueError(
                f"Invalid model type '{model_type}'. " f"Must be one of: {valid_values}"
            )

    checkpoints_to_include = []

    if model_type and model_type in checkpoint_mapping:
        checkpoints_to_include.append(checkpoint_mapping[model_type])

    if include_files:
        checkpoints_to_include.extend(include_files)

    def filter_func(full_key: str) -> bool:
        return any(
            full_key.endswith(checkpoint) for checkpoint in checkpoints_to_include
        )

    return filter_func


def extract_model_variant(variant_config: Optional[dict[str, Any]], key: str) -> str:
    """
    Extract model variant value from variant_config dictionary.

    Args:
        variant_config: Dictionary containing variant configuration
        key: Key to extract (e.g., "MODEL_SIZE", "MODEL_TYPE")

    Returns:
        Extracted variant value as string

    Raises:
        ValueError: If variant_config is None/empty or key is not found
    """
    if not variant_config:
        raise ValueError(
            f"variant_config is required but was {variant_config}. "
            f"Expected a dictionary with key '{key}'."
        )

    if key not in variant_config:
        available_keys = list(variant_config.keys())
        raise ValueError(
            f"Required key '{key}' not found in variant_config. "
            f"Available keys: {available_keys}. "
            f"This likely means the model's app.py is not passing the correct variant_config."
        )

    value = variant_config[key]
    if value is None:
        raise ValueError(
            f"Key '{key}' exists in variant_config but has value None. "
            f"This likely means the variant was not properly set in app.py."
        )

    return value


# ---------------------------------------------------------------------------
# Declarative fallback wrappers
# ---------------------------------------------------------------------------
# These wrappers build both R2-primary and source-fallback configs internally,
# eliminating the 40-60 lines of boilerplate that models previously wrote by
# hand.  Each returns an AcquisitionResult; callers only need to check
# result.success and use result.actual_model_path.
# ---------------------------------------------------------------------------


def _build_r2_primary(
    *,
    base_model_slug: str,
    params_version: str,
    model_variant: Optional[str],
    sub_path: Optional[str],
    target_dir: "Path",
    filter_func: Optional[Callable[[str], bool]] = None,
    required_files: Optional[list[str]] = None,
) -> AcquisitionConfig:
    """Internal helper: build the R2-only primary config used by all fallback wrappers."""
    return AcquisitionConfig(
        strategy=AcquisitionStrategy.R2_ONLY,
        target_dir=target_dir,
        cache_config=CacheConfig(enable_r2_cache=False),  # reading, not writing
        validation_config=ValidationConfig(required_files=required_files),
        r2_config=R2OnlyConfig(
            base_model_slug=base_model_slug,
            params_version=params_version,
            model_variant=model_variant,
            sub_path=sub_path,
            filter_func=filter_func,
        ),
    )


def r2_then_hf(
    *,
    base_model_slug: str,
    params_version: str,
    model_variant: Optional[str] = None,
    sub_path: Optional[str] = None,
    hf_repo_id: str,
    hf_revision: Optional[str] = None,
    allow_patterns: Optional[list[str]] = None,
    ignore_patterns: Optional[list[str]] = None,
    required_files: Optional[list[str]] = None,
    repo_type: str = "model",
) -> AcquisitionResult:
    """Try R2 first, fall back to HuggingFace Hub download with R2 caching.

    Builds both configs internally — models only need to supply the source
    parameters.  On success, ``result.actual_model_path`` points to the HF
    snapshot directory (which may differ from target_dir).

    When the R2 primary succeeds, the snapshot path is resolved automatically
    so callers never need to call ``build_hf_snapshot_path`` themselves.
    """
    from models.commons.storage.downloads import (
        build_hf_snapshot_path,
        get_model_dir_util,
    )

    target_dir = get_model_dir_util(
        base_model_slug=base_model_slug,
        params_version=params_version,
        model_variant=model_variant,
        sub_path=sub_path,
    )

    # R2 primary: skip required_files validation — R2 may store HF models in a
    # flat layout that differs from the HF snapshot structure (e.g. safetensors
    # vs pytorch_model.bin, no nested snapshot dirs).
    primary = _build_r2_primary(
        base_model_slug=base_model_slug,
        params_version=params_version,
        model_variant=model_variant,
        sub_path=sub_path,
        target_dir=target_dir,
    )

    fallback = AcquisitionConfig(
        strategy=AcquisitionStrategy.HUGGINGFACE_HUB,
        target_dir=target_dir,
        cache_config=CacheConfig(enable_r2_cache=True),
        validation_config=ValidationConfig(required_files=required_files),
        hf_config=HfSourceConfig(
            repo_id=hf_repo_id,
            revision=hf_revision,
            allow_patterns=allow_patterns,
            ignore_patterns=ignore_patterns,
            repo_type=repo_type,
        ),
    )

    result = download_with_fallback(primary, fallback)

    # Ensure actual_model_path always points to the HF snapshot directory.
    # When the HF fallback runs, _acquire_huggingface_hub already sets this.
    # When the R2 primary succeeds, we need to resolve it ourselves.
    if result.success and result.actual_model_path == target_dir:
        snapshot_path = build_hf_snapshot_path(
            target_dir, hf_repo_id, hf_revision, repo_type=repo_type
        )
        result.actual_model_path = snapshot_path

    return result


def r2_then_library(
    *,
    base_model_slug: str,
    params_version: str,
    model_variant: Optional[str] = None,
    sub_path: Optional[str] = None,
    library_name: str,
    init_fn: Callable[[Path], Any],
    monitor_directories: Optional[list[str]] = None,
    env_vars: Optional[dict[str, str]] = None,
    required_files: Optional[list[str]] = None,
    cache_to_r2: bool = True,
) -> AcquisitionResult:
    """Try R2 first, fall back to library-managed download with R2 caching.

    The ``init_fn`` is called with ``target_dir`` and should trigger the
    library's own download mechanism (e.g. ``ESM3.from_pretrained``).

    Args:
        cache_to_r2: When True (default) the library output is uploaded to R2
            after a source fetch so future deploys self-populate. Set False for
            libraries that manage their own out-of-tree cache and cannot be
            redirected into ``target_dir`` (e.g. ``evo``/``pro1``).
        monitor_directories: Retained for caller compatibility; no longer read
            (the bypass detector that consumed it was removed).
    """
    from models.commons.storage.downloads import get_model_dir_util

    target_dir = get_model_dir_util(
        base_model_slug=base_model_slug,
        params_version=params_version,
        model_variant=model_variant,
        sub_path=sub_path,
    )

    # R2 primary: skip required_files validation — R2 caches the raw
    # library output which may use different file names/paths than
    # what required_files specifies for the library download.
    primary = _build_r2_primary(
        base_model_slug=base_model_slug,
        params_version=params_version,
        model_variant=model_variant,
        sub_path=sub_path,
        target_dir=target_dir,
    )

    fallback = AcquisitionConfig(
        strategy=AcquisitionStrategy.LIBRARY_MANAGED,
        target_dir=target_dir,
        cache_config=CacheConfig(enable_r2_cache=cache_to_r2),
        validation_config=ValidationConfig(required_files=required_files),
        library_config=LibrarySourceConfig(
            library_name=library_name,
            monitor_directories=monitor_directories,
            env_vars=env_vars,
        ),
        custom_function=init_fn,
    )

    return download_with_fallback(primary, fallback)


def r2_then_urls(
    *,
    base_model_slug: str,
    params_version: str,
    model_variant: Optional[str] = None,
    sub_path: Optional[str] = None,
    urls: dict[str, str],
    required_files: Optional[list[str]] = None,
    headers: Optional[dict[str, str]] = None,
    verify_ssl: bool = True,
    timeout: int = 3600,
    chunk_size: int = 8192,
) -> AcquisitionResult:
    """Try R2 first, fall back to direct URL downloads with R2 caching."""
    from models.commons.storage.downloads import get_model_dir_util

    target_dir = get_model_dir_util(
        base_model_slug=base_model_slug,
        params_version=params_version,
        model_variant=model_variant,
        sub_path=sub_path,
    )

    primary = _build_r2_primary(
        base_model_slug=base_model_slug,
        params_version=params_version,
        model_variant=model_variant,
        sub_path=sub_path,
        target_dir=target_dir,
        required_files=required_files,
    )

    fallback = AcquisitionConfig(
        strategy=AcquisitionStrategy.DIRECT_URLS,
        target_dir=target_dir,
        cache_config=CacheConfig(enable_r2_cache=True),
        validation_config=ValidationConfig(required_files=required_files),
        url_config=UrlSourceConfig(
            urls=urls,
            headers=headers,
            verify_ssl=verify_ssl,
            timeout=timeout,
            chunk_size=chunk_size,
        ),
    )

    return download_with_fallback(primary, fallback)


def r2_then_archive(
    *,
    base_model_slug: str,
    params_version: str,
    model_variant: Optional[str] = None,
    sub_path: Optional[str] = None,
    archive_url: str,
    extract_subtrees: dict[str, str],
    strip_repo_root: bool = True,
    required_files: Optional[list[str]] = None,
    headers: Optional[dict[str, str]] = None,
    verify_ssl: bool = True,
    timeout: int = 1800,
) -> AcquisitionResult:
    """Try R2 first, fall back to a source ``.zip`` archive with R2 caching.

    On an R2 cache miss the archive at ``archive_url`` is downloaded once, then
    each ``(src_prefix -> dest)`` entry in ``extract_subtrees`` is extracted into
    ``target_dir / dest``. The extracted tree is then cached back to R2 (with the
    completion marker) so future deploys self-populate from R2.

    This replaces the hand-rolled "download zip → unzip subtree" logic that
    several models (tempro/deepviscosity/temberture/clean) carry inline.

    Args:
        archive_url: URL of the source ``.zip`` (e.g. a GitHub archive link).
        extract_subtrees: Mapping of archive subtree prefix (relative to the
            repo root, e.g. ``"tempro/models/"``) to a destination directory
            relative to ``target_dir`` (use ``""`` to extract into the root).
        strip_repo_root: When True (default) the single ``<Repo>-<ref>/`` root
            directory that GitHub archives wrap everything in is auto-detected
            and prepended to each ``src_prefix``. Set False to provide prefixes
            that already include the archive root.
        required_files: Files validated (relative to ``target_dir``) after
            extraction; also enforced on the R2-primary read.
        headers / verify_ssl / timeout: Forwarded to the archive download.

    Returns:
        AcquisitionResult; on success ``actual_model_path`` is ``target_dir``.
    """
    from models.commons.storage.downloads import (
        detect_archive_root_prefix,
        download_archive,
        extract_archive_subtree,
        get_model_dir_util,
    )

    target_dir = get_model_dir_util(
        base_model_slug=base_model_slug,
        params_version=params_version,
        model_variant=model_variant,
        sub_path=sub_path,
    )

    primary = _build_r2_primary(
        base_model_slug=base_model_slug,
        params_version=params_version,
        model_variant=model_variant,
        sub_path=sub_path,
        target_dir=target_dir,
        required_files=required_files,
    )

    def _acquire_archive(target_dir: Path, **_: Any) -> dict[str, Any]:
        import tempfile

        with tempfile.TemporaryDirectory(prefix="r2_then_archive_") as tmp:
            zip_path = Path(tmp) / "source_archive.zip"
            meta = download_archive(
                archive_url,
                zip_path,
                headers=headers,
                verify_ssl=verify_ssl,
                timeout=timeout,
            )

            root_prefix = (
                detect_archive_root_prefix(zip_path) if strip_repo_root else ""
            )

            cleared: set[Path] = set()
            for src_prefix, dest_rel in extract_subtrees.items():
                full_prefix = f"{root_prefix}{src_prefix}"
                dest_dir = target_dir / dest_rel if dest_rel else target_dir
                # Only clear (rmtree) a destination the first time we write to
                # it, so multiple subtrees mapped into one dir don't clobber.
                extract_archive_subtree(
                    zip_path,
                    full_prefix,
                    dest_dir,
                    overwrite=dest_dir not in cleared,
                )
                cleared.add(dest_dir)

        return {
            "archive_url": archive_url,
            "subtrees_extracted": len(extract_subtrees),
            "bytes_downloaded": meta.get("bytes_downloaded", 0),
            "stripped_root": root_prefix,
        }

    fallback = AcquisitionConfig(
        strategy=AcquisitionStrategy.CUSTOM,
        target_dir=target_dir,
        cache_config=CacheConfig(enable_r2_cache=True),
        validation_config=ValidationConfig(required_files=required_files),
        custom_config=CustomSourceConfig(
            acquisition_fn=_acquire_archive,
            name=f"{base_model_slug}_archive",
            description=f"Download + extract source archive from {archive_url}",
        ),
    )

    return download_with_fallback(primary, fallback)


def build_variant_filter(
    model_variant: str,
    *,
    include_files: Optional[list[str]] = None,
) -> Callable[[str], bool]:
    """Build a filter function that selects files matching a variant name.

    The returned callable accepts an R2 key and returns ``True`` when the key
    contains ``model_variant`` or matches any entry in ``include_files``.

    This standardises the one-off closures that many models hand-roll for
    variant-based filtering.
    """
    extras = include_files or []

    def _filter(full_key: str) -> bool:
        if model_variant in full_key:
            return True
        return any(f in full_key for f in extras)

    return _filter
