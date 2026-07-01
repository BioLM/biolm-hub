# Model Weight Download Architecture & Implementation Guide

## Overview

This document explains the complete model weight download architecture for Modal deployments, including the modern acquisition system with primary/fallback strategies, atomic R2 caching, and robust error handling.

## Table of Contents

1. [Architecture Overview](#architecture-overview)
2. [Modern Download Pattern](#modern-download-pattern)
3. [Modal Container Build Process](#modal-container-build-process)
4. [Layer Architecture](#layer-architecture)
5. [Acquisition Strategies](#acquisition-strategies)
6. [R2 Caching System](#r2-caching-system)
7. [Implementation Patterns](#implementation-patterns)
8. [Model-Specific Implementations](#model-specific-implementations)
9. [Migration Guide](#migration-guide)
10. [Troubleshooting](#troubleshooting)

## Architecture Overview

The download system uses a **4-layer architecture** with clear separation of concerns:

```
┌───────────────────────────────────────────────────────────────┐
│                      Modal Container Build                    │
│  ┌─────────────────────────────────────────────────────────┐  │
│  │         setup_download_layer() [downloader.py]          │  │ ← Modal Integration
│  │  • Copies minimal files to container                    │  │
│  │  • Executes download_model_assets() with kwargs         │  │
│  │  • Manages Docker layer caching                         │  │
│  └──────────────────────┬──────────────────────────────────┘  │
│                         ↓                                     │
│  ┌─────────────────────────────────────────────────────────┐  │
│  │     download_model_assets() [models/*/download.py]      │  │ ← Model Entry Point
│  │  • Receives explicit parameters (not env vars!)         │  │
│  │  • Configures primary + fallback strategies             │  │
│  │  • Returns actual model path                            │  │
│  └──────────────────────┬──────────────────────────────────┘  │
│                         ↓                                     │
│  ┌─────────────────────────────────────────────────────────┐  │
│  │      download_helpers.py [Layer 1 - High-Level API]     │  │ ← Helper Functions
│  │  • download_with_fallback()                             │  │
│  │  • standard_r2_download()                               │  │
│  │  • acquire_library_managed_model()                      │  │
│  │  • extract_model_variant()                              │  │
│  └──────────────────────┬──────────────────────────────────┘  │
│                         ↓                                     │
│  ┌─────────────────────────────────────────────────────────┐  │
│  │       acquisition.py [Layer 2 - Strategy Engine]        │  │ ← Core Engine
│  │  • acquire_model_weights() - main entry point           │  │
│  │  • Strategy implementations:                            │  │
│  │    - R2_ONLY, HUGGINGFACE_HUB, LIBRARY_MANAGED          │  │
│  │    - DIRECT_URLS, CUSTOM                                │  │
│  │  • Bypass detection, validation, retry logic            │  │
│  └──────────────────────┬──────────────────────────────────┘  │
│                         ↓                                     │
│  ┌─────────────────────────────────────────────────────────┐  │
│  │       downloads.py [Layer 3 - Low-Level Ops]            │  │ ← Core Operations
│  │  • download_model_from_r2() - paginated R2 download     │  │
│  │  • download_from_hf() - HuggingFace snapshot download   │  │
│  │  • get_model_dir_util() - path resolution               │  │
│  │  • verify_model_dir() - validation                      │  │
│  └──────────────────────┬──────────────────────────────────┘  │
│                         ↓                                     │
│  ┌─────────────────────────────────────────────────────────┐  │
│  │      r2_utils.py [Layer 4 - Infrastructure]             │  │ ← R2 Operations
│  │  • upload_to_r2_atomic() - atomic upload with manifest  │  │
│  │  • restore_from_r2_atomic() - validated restore         │  │
│  │  • Completion markers, manifest validation              │  │
│  │  • Checksum calculation, progress reporting             │  │
│  └──────────────────────┬──────────────────────────────────┘  │
│                         ↓                                     │
│  ┌─────────────────────────────────────────────────────────┐  │
│  │         Cloudflare R2 Storage [Primary Cache]           │  │ ← Storage Backend
│  └─────────────────────────────────────────────────────────┘  │
└───────────────────────────────────────────────────────────────┘
```

## Modern Download Pattern

### Primary + Fallback Strategy

The modern pattern uses **download_with_fallback()** to implement a two-stage download strategy:

```python
# In models/{model}/download.py
def download_model_assets(
    base_model_slug: str,
    weights_version: str,
    variant_config: Optional[dict] = None,
    sub_path: Optional[str] = None,
) -> Path:
    # Extract variant from config
    model_size = extract_model_variant(variant_config, "MODEL_SIZE")

    # Configure primary strategy (R2_ONLY)
    primary_config = AcquisitionConfig(
        strategy=AcquisitionStrategy.R2_ONLY,
        target_dir=model_dir,
        cache_config=CacheConfig(enable_r2_cache=False),  # Reading, not writing
        r2_config=R2OnlyConfig(...)
    )

    # Configure fallback strategy (HUGGINGFACE_HUB or LIBRARY_MANAGED)
    fallback_config = AcquisitionConfig(
        strategy=AcquisitionStrategy.HUGGINGFACE_HUB,
        target_dir=model_dir,
        cache_config=CacheConfig(enable_r2_cache=True),  # Cache to R2
        hf_config=HfSourceConfig(...)
    )

    # Execute with fallback
    result = download_with_fallback(primary_config, fallback_config)
    return result.actual_model_path
```

### Models Using Modern Pattern

As of now, **9 models** implement the modern pattern:

| Model | Primary | Fallback | Fallback Type |
|------|---------|----------|---------------|
| esm3 | R2_ONLY | LIBRARY_MANAGED | ESM3 library |
| chai1 | R2_ONLY | LIBRARY_MANAGED | Chai1 library |
| ablang2 | R2_ONLY | LIBRARY_MANAGED | ablang2 library |
| nt | R2_ONLY | HUGGINGFACE_HUB | InstaDeep repo |
| dnabert2 | R2_ONLY | HUGGINGFACE_HUB | zhihan1996 repo |
| evo2 | R2_ONLY | HUGGINGFACE_HUB | Arc Institute repo |
| omni_dna | R2_ONLY | HUGGINGFACE_HUB | zehui127 repo |
| immunebuilder | R2_ONLY | DIRECT_URLS | Zenodo URLs |
| esmc | R2_ONLY | HUGGINGFACE_HUB | EvolutionaryScale repo |

## Modal Container Build Process

### 1. Parameter-Based Downloads (Modern)

The modern approach uses **explicit parameters** passed through kwargs:

```python
# In Modal app.py
image = setup_download_layer(
    image,
    base_model_slug="esmc",
    weights_version="v1",
    variant_config={"MODEL_SIZE": "300m"},  # Explicit variant config
    sub_path=None,
)
```

### 2. Build-Time Execution Flow

1. **setup_download_layer()** copies minimal files to container
2. **Executes download_model_assets()** with explicit kwargs
3. **Downloads weights** to `/biolm-hub/model-weights/models/` during build
4. **Creates immutable container** with weights included

### 3. Directory Structure

Standard path structure:
```
/biolm-hub/model-weights/models/
├── {base_model_slug}/
│   ├── {weights_version}/
│   │   ├── {model_variant}/        # e.g., esmc_300m
│   │   │   ├── model files...
│   │   │   └── for HuggingFace models:
│   │   │       └── models--{org}--{repo}/
│   │   │           └── snapshots/
│   │   │               └── {commit_hash}/
│   │   │                   └── actual model files...
```

## Layer Architecture

### Layer 1: download_helpers.py (High-Level API)

**Primary Functions:**
- `download_with_fallback()` - Execute primary + fallback strategies
- `standard_r2_download()` - Simple R2-only wrapper
- `acquire_library_managed_model()` - Library download with bypass detection
- `extract_model_variant()` - Extract variant from config dict
- `build_model_type_filter()` - Create filter functions

### Layer 2: acquisition.py (Strategy Engine)

**Core Components:**
- `AcquisitionConfig` - Main configuration dataclass
- `AcquisitionResult` - Result with metadata and paths
- `acquire_model_weights()` - Main entry point

**Strategy Classes:**
- `R2OnlyConfig` - R2 download configuration
- `HfSourceConfig` - HuggingFace Hub configuration
- `LibrarySourceConfig` - Library-managed configuration
- `UrlSourceConfig` - Direct URL configuration
- `CustomSourceConfig` - Custom function configuration

### Layer 3: downloads.py (Low-Level Operations)

**Key Functions:**
- `get_model_dir_util()` - Construct model directory paths
- `download_model_from_r2()` - Paginated R2 download with retry
- `download_from_hf()` - HuggingFace snapshot download
- `verify_model_dir()` - Validate downloaded files
- `setup_hf_cache_env()` - Configure HF environment

### Layer 4: r2_utils.py (Infrastructure)

**Atomic Operations:**
- `upload_to_r2_atomic()` - Upload with manifest and completion marker
- `restore_from_r2_atomic()` - Restore with validation
- `check_completion_marker()` - Verify cache completeness
- `create_manifest()` - Generate file manifest with checksums
- `validate_manifest()` - Verify files against manifest

## Acquisition Strategies

### 1. R2_ONLY Strategy
```python
AcquisitionConfig(
    strategy=AcquisitionStrategy.R2_ONLY,
    r2_config=R2OnlyConfig(
        base_model_slug="esm2",
        weights_version="v1",
        model_variant="8b",
        filter_func=lambda k: k.endswith(".pt")
    )
)
```

### 2. HUGGINGFACE_HUB Strategy
```python
AcquisitionConfig(
    strategy=AcquisitionStrategy.HUGGINGFACE_HUB,
    hf_config=HfSourceConfig(
        repo_id="EvolutionaryScale/esmc-300m-2024-12",
        revision="a19d363f07313a10a64d08a2d6b41376a73df5c8",
    )
)
```

### 3. LIBRARY_MANAGED Strategy
```python
AcquisitionConfig(
    strategy=AcquisitionStrategy.LIBRARY_MANAGED,
    library_config=LibrarySourceConfig(
        library_name="esm3",
        env_vars={"HF_HUB_CACHE": str(target_dir)}
    ),
    custom_function=init_library_weights
)
```

### 4. DIRECT_URLS Strategy
```python
AcquisitionConfig(
    strategy=AcquisitionStrategy.DIRECT_URLS,
    url_config=UrlSourceConfig(
        urls={
            "model.pt": "https://zenodo.org/record/123/files/model.pt",
            "config.json": "https://zenodo.org/record/123/files/config.json"
        },
        timeout=3600
    )
)
```

### 5. CUSTOM Strategy
```python
AcquisitionConfig(
    strategy=AcquisitionStrategy.CUSTOM,
    custom_config=CustomSourceConfig(
        acquisition_fn=custom_download_function,
        acquisition_kwargs={'model_variant': '650m'},
        post_process_fn=extract_and_cleanup_function,
        name="custom_source",
        description="Download and extract model from custom source"
    ),
    cache_config=CacheConfig(enable_r2_cache=True)  # Cache to R2
)
```

## R2 Caching System

### Atomic Operations

The R2 cache uses **atomic operations** to ensure consistency:

1. **Upload Phase:**
   - Upload all files to R2
   - Create manifest with SHA256 checksums
   - Upload completion marker (atomic commit)

2. **Restore Phase:**
   - Check completion marker exists
   - Download all files
   - Validate against manifest
   - Return success only if valid

### Cache Structure
```
r2://bucket/biolm-hub/model-weights/models/
├── esmc/v1/esmc_300m/
│   ├── models--EvolutionaryScale--esmc-300m-2024-12/
│   │   └── snapshots/{hash}/
│   │       ├── config.json
│   │       └── data/weights/esmc_300m_2024_12_v0.pth
│   ├── .r2_manifest.json          # File checksums
│   └── .r2_cache_complete         # Completion marker
```

### Completion Marker Format
```json
{
    "completed_at": 1699123456.789,
    "r2_prefix": "biolm-hub/model-weights/models/esmc/v1/esmc_300m",
    "file_count": 15,
    "manifest_uploaded": true,
    "manifest_key": "biolm-hub/model-weights/models/esmc/v1/esmc_300m/.r2_manifest.json"
}
```

### Manifest Format
```json
{
    "config.json": {
        "size": 1234,
        "sha256": "abc123...",
        "mtime": 1699123456.789
    },
    "data/weights/model.pth": {
        "size": 8589934592,
        "sha256": "def456...",
        "mtime": 1699123456.789
    }
}
```

## Implementation Patterns

### Pattern 1: Simple R2-Only (Legacy)
```python
def download_model_assets(
    base_model_slug: str,
    weights_version: str,
    variant_config: Optional[dict] = None,
    sub_path: Optional[str] = None,
):
    result = standard_r2_download(
        base_model_slug=base_model_slug,
        weights_version=weights_version,
        model_variant=extract_model_variant(variant_config, "MODEL_SIZE"),
        sub_path=sub_path,
    )
    if not result.success:
        raise RuntimeError(f"Download failed: {result.error_message}")
    return result.actual_model_path
```

### Pattern 2: Modern Primary + Fallback
```python
def download_model_assets(...) -> Path:
    # Configure primary (R2)
    primary_config = AcquisitionConfig(
        strategy=AcquisitionStrategy.R2_ONLY,
        target_dir=model_dir,
        cache_config=CacheConfig(enable_r2_cache=False),
        r2_config=R2OnlyConfig(...)
    )

    # Configure fallback (HuggingFace)
    fallback_config = AcquisitionConfig(
        strategy=AcquisitionStrategy.HUGGINGFACE_HUB,
        target_dir=model_dir,
        cache_config=CacheConfig(enable_r2_cache=True),  # Cache to R2!
        hf_config=HfSourceConfig(...)
    )

    # Execute with automatic fallback
    result = download_with_fallback(primary_config, fallback_config)
    return Path(result.actual_model_path)
```

### Pattern 3: Library-Managed with Bypass Detection
```python
def _init_library_weights(target_dir: Path) -> Path:
    # Set environment to control library
    setup_hf_cache_env(target_dir)

    # Import and trigger library download
    from some_library import Model
    Model.from_pretrained("model-name", device="cpu")

    return target_dir

def download_model_assets(...) -> Path:
    # Primary: R2
    primary_config = AcquisitionConfig(...)

    # Fallback: Library-managed
    fallback_config = AcquisitionConfig(
        strategy=AcquisitionStrategy.LIBRARY_MANAGED,
        target_dir=model_dir,
        cache_config=CacheConfig(enable_r2_cache=True),
        library_config=LibrarySourceConfig(
            library_name="some_library",
        ),
        custom_function=_init_library_weights,
    )

    result = download_with_fallback(primary_config, fallback_config)
    return Path(result.actual_model_path)
```

## Model-Specific Implementations

### HuggingFace Models (nt, dnabert2, evo2, omni_dna, esmc)
```python
# Repository and revision mappings
HF_REPO_MAP = {
    "300m": "EvolutionaryScale/esmc-300m-2024-12",
    "600m": "EvolutionaryScale/esmc-600m-2024-12",
}
HF_REVISION_MAP = {
    "300m": "a19d363f07313a10a64d08a2d6b41376a73df5c8",
    "600m": "d11cc14d44078eaecbc6a843d5eb20f4eecc1e7e",
}
```

### Library-Managed Models (esm3, chai1, ablang2)
```python
# ESM3: Uses HF cache redirection
def _init_esm3_weights(target_dir: Path) -> Path:
    setup_hf_cache_env(target_dir)
    from esm.models.esm3 import ESM3
    ESM3.from_pretrained("esm3-sm-open-v1", device="cpu")
    return target_dir

# Chai1: Uses CHAI_DOWNLOADS_DIR
def _init_chai1_weights(target_dir: Path) -> Path:
    os.environ["CHAI_DOWNLOADS_DIR"] = str(target_dir)
    from chai1 import run_inference
    # Trigger download with dummy input
    run_inference(...)
    return target_dir
```

### Direct URL Models (immunebuilder)
```python
ZENODO_URLS = {
    "nanobodybuilder2": {
        "model_1": "https://zenodo.org/record/7258553/files/model_1",
        "model_2": "https://zenodo.org/record/7258553/files/model_2",
    }
}
```

## Migration Guide

### Migrating from Legacy to Modern Pattern

**Old Pattern (Environment Variables):**
```python
def download_model_assets_from_env():
    params = extract_download_params_from_env()
    return standard_r2_download(**params)
```

**New Pattern (Explicit Parameters):**
```python
def download_model_assets(
    base_model_slug: str,
    weights_version: str,
    variant_config: Optional[dict] = None,
    sub_path: Optional[str] = None,
) -> Path:
    # Modern implementation with fallback
    primary_config = ...
    fallback_config = ...
    result = download_with_fallback(primary_config, fallback_config)
    return Path(result.actual_model_path)
```

### Adding a New Model

1. **Create download.py:**
```python
from pathlib import Path
from typing import Optional

from models.commons.storage.acquisition import (
    AcquisitionConfig,
    AcquisitionStrategy,
    CacheConfig,
    HfSourceConfig,
    R2OnlyConfig,
)
from models.commons.storage.download_helpers import (
    download_with_fallback,
    extract_model_variant,
)
from models.commons.storage.downloads import get_model_dir_util

def download_model_assets(...) -> Path:
    # Implement modern pattern
    ...
```

2. **Configure Modal app.py:**
```python
image = setup_download_layer(
    image,
    base_model_slug="new_model",
    weights_version="v1",
    variant_config={"MODEL_SIZE": "base"},
)
```

3. **Upload initial weights to R2:**
```bash
# Use R2Utils for atomic upload
python -c "
from pathlib import Path
from models.commons.storage.r2_utils import R2Utils

R2Utils.upload_to_r2_atomic(
    source_dir=Path('./weights'),
    r2_prefix='biolm-hub/model-weights/models/new_model/v1/base'
)
"
```

## Troubleshooting

### Common Issues

#### 1. R2 Cache Miss
**Error:** `No files found in R2 at prefix`
**Solution:**
- Check if fallback is configured
- Verify R2 prefix matches expected structure
- Ensure initial weights were uploaded

#### 2. HuggingFace Snapshot Path
**Issue:** Model loads from wrong directory
**Solution:**
- Use `result.actual_model_path` (not `target_dir`)
- HF models return snapshot directory, not base directory

#### 3. Library Bypass Detection
**Warning:** `BYPASS DETECTED! Library downloaded to unexpected location`
**Solution:**
- Add appropriate environment variables
- Monitor additional directories
- Check library's cache configuration

#### 4. Manifest Validation Failures
**Error:** `Checksum mismatch for file`
**Solution:**
- Force re-upload with `create_manifest=True`
- Check for corrupted files
- Verify upload completed atomically

### Debugging Commands

```bash
# Check R2 contents
bh r2 ls | grep "biolm-hub/model-weights/models/esmc"

# Test download locally
python -c "
from models.esmc.download import download_model_assets
result = download_model_assets(
    'esmc', 'v1', {'MODEL_SIZE': '300m'}
)
print(f'Downloaded to: {result}')
"

# Verify completion marker
python -c "
from models.commons.storage.r2_utils import R2Utils
exists = R2Utils.check_r2_cache_exists('biolm-hub/model-weights/models/esmc/v1/esmc_300m')
print(f'Cache exists: {exists}')
"

# Upload to R2 atomically
python -c "
from pathlib import Path
from models.commons.storage.r2_utils import R2Utils
success = R2Utils.upload_to_r2_atomic(
    Path('./local_weights'),
    'biolm-hub/model-weights/models/new_model/v1'
)
"
```

## Best Practices

1. **Always implement fallback** - Ensures availability when R2 is down
2. **Use modern pattern** - Primary + fallback with download_with_fallback()
3. **Pin HuggingFace revisions** - Ensures reproducible downloads
4. **Enable R2 caching on fallback** - Cache successful downloads for future
5. **Return actual_model_path** - Handles HF snapshot directories correctly
6. **Validate required files** - Ensure downloads are complete
7. **Use atomic operations** - Prevents partial downloads
8. **Add progress reporting** - Helps debug slow downloads
9. **Document special requirements** - Note any model-specific quirks
10. **Test both strategies** - Verify primary and fallback work

## Summary

The modern download architecture provides:

- **Resilience** through primary + fallback strategies
- **Performance** via R2 caching and atomic operations
- **Consistency** through manifest validation and checksums
- **Flexibility** with multiple acquisition strategies
- **Maintainability** through layered architecture
- **Self-healing** by caching successful fallback downloads

This system enables reliable, efficient model deployment in Modal's serverless environment while minimizing download times and maximizing availability.
