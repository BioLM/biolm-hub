from collections.abc import Callable
from pathlib import Path
from typing import Any, Optional

from models.commons.storage.acquisition import (
    AcquisitionConfig,
    AcquisitionResult,
    AcquisitionStrategy,
    CacheConfig,
    HfSourceConfig,
    LibrarySourceConfig,
    R2OnlyConfig,
    UrlSourceConfig,
    ValidationConfig,
    acquire_model_weights,
)
from models.commons.storage.r2_utils import (
    R2Utils,
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
- acquire_library_managed_model(...): wrap library-managed flows with bypass detection
- extract_model_variant(...): fetch variant axes from variant_config

Notes:
- Prefer these helpers from models/*/download.py; acquire_model_weights is still
  available for advanced/custom scenarios.
"""


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
    setup_function: Optional[Callable[[Path], None]] = None,
    import_modules: Optional[list[str]] = None,
    monitor_directories: Optional[list[str]] = None,
    env_vars: Optional[dict] = None,
    cache_to_r2: bool = True,
    required_files: Optional[list[str]] = None,
) -> AcquisitionResult:
    """
    Library-managed acquisition with bypass detection and optional R2 caching.

    This function allows libraries to manage their own downloads while providing
    bypass detection and caching capabilities.

    Args:
        library_name: Name of the library managing the download
        target_dir: Directory where the model should be downloaded
        init_fn: Function that triggers the library's download (returns model path)
        setup_function: Optional function to set up environment before download
        import_modules: Optional list of modules to import for the download
        monitor_directories: Optional list of directories to monitor for bypass
        env_vars: Optional dictionary of environment variables to set
        cache_to_r2: Whether to cache downloaded model to R2
        required_files: Optional list of files to validate after download

    Returns:
        AcquisitionResult with download status and bypass detection info

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
        ...     monitor_directories=["~/.cache/huggingface"]
        ... )
    """
    # Create library configuration
    library_config = LibrarySourceConfig(
        library_name=library_name,
        setup_function=setup_function,
        import_modules=import_modules,
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


def quick_r2_check(
    base_model_slug: str,
    params_version: str,
    model_variant: Optional[str] = None,
    sub_path: Optional[str] = None,
) -> bool:
    """
    Quick check if model exists in R2 without downloading.

    Args:
        base_model_slug: Model family identifier
        params_version: Parameter version
        model_variant: Model size/variant (optional)
        sub_path: Subdirectory path (optional)

    Returns:
        True if model appears to be available in R2

    Examples:
        >>> if quick_r2_check("esm2", "v1", "8b"):
        ...     print("Model available in R2")
    """
    try:
        from models.commons.storage.downloads import get_model_dir_util
        from models.commons.storage.r2 import get_r2_client
        from models.commons.util.config import r2_bucket_name

        # Get the expected R2 path
        model_dir = get_model_dir_util(
            base_model_slug=base_model_slug,
            params_version=params_version,
            model_variant=model_variant,
            sub_path=sub_path,
        )

        r2_prefix = str(model_dir).lstrip("/")

        # Check for completion marker using R2Utils
        if R2Utils.check_r2_cache_exists(r2_prefix):
            return True

        # Fallback: check if any files exist for partial caches
        try:
            r2_client = get_r2_client()
            response = r2_client.list_objects_v2(
                Bucket=r2_bucket_name, Prefix=r2_prefix + "/", MaxKeys=1
            )
            return response.get("KeyCount", 0) > 0
        except Exception:
            return False

    except Exception:
        return False


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
    print("🔄 [download_helpers.py] Attempting primary acquisition strategy...")
    primary_result = acquire_model_weights(primary_config)

    if primary_result.success:
        print("✅ [download_helpers.py] Primary strategy succeeded")
        return primary_result

    print(
        f"⚠️ [download_helpers.py] Primary strategy failed: {primary_result.error_message}"
    )
    print("🔄 [download_helpers.py] Attempting fallback strategy...")

    fallback_result = acquire_model_weights(fallback_config)

    if fallback_result.success:
        print("✅ [download_helpers.py] Fallback strategy succeeded")
    else:
        print(
            f"❌ [download_helpers.py] Fallback strategy also failed: {fallback_result.error_message}"
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
    enable_diagnostics: bool = True,
) -> AcquisitionResult:
    """Try R2 first, fall back to library-managed download with R2 caching.

    The ``init_fn`` is called with ``target_dir`` and should trigger the
    library's own download mechanism (e.g. ``ESM3.from_pretrained``).
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
        cache_config=CacheConfig(enable_r2_cache=True),
        validation_config=ValidationConfig(required_files=required_files),
        library_config=LibrarySourceConfig(
            library_name=library_name,
            monitor_directories=monitor_directories,
            env_vars=env_vars,
            enable_diagnostics=enable_diagnostics,
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
