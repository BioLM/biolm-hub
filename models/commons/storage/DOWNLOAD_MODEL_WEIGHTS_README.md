# Model weight acquisition & R2 caching

How a model's weights get into a Modal container at build time, and how the
public R2 bucket self-populates. This is the trickiest part of the framework;
the goal is that a new model's `download.py` is a handful of declarative lines.

## The one thing to know

Model `download.py` files call a **`r2_then_*` wrapper**. Each one does the same
thing: **try the public R2 cache first; on a miss, fetch from the original source
and cache the result back to R2** so the next deploy is a fast R2 restore. Pick the
wrapper by where the original weights live:

| Wrapper | Original source | Example models |
|---------|-----------------|----------------|
| `r2_then_hf` | a HuggingFace repo | `esmc`, `dnabert2`, `omni_dna`, `prostt5` |
| `r2_then_library` | the model's own library (`from_pretrained`) | `chai1`, `ablang2`, `esm2`, `esmfold` |
| `r2_then_urls` | direct file URLs (e.g. Zenodo) | `immunebuilder`, `antifold`, `mpnn` |
| `r2_then_archive` | a tarball/zip you extract a subtree from | `deepviscosity` |

```python
# models/<name>/download.py
from models.commons.storage.download_helpers import extract_model_variant, r2_then_hf

def download_model_assets(base_model_slug, weights_version, variant_config=None, sub_path=None):
    size = extract_model_variant(variant_config, "MODEL_SIZE")
    result = r2_then_hf(
        base_model_slug=base_model_slug,
        weights_version=weights_version,
        model_variant=size,
        hf_repo_id=HF_REPO_MAP[size],
        hf_revision=HF_REVISION_MAP[size],   # pin the commit for reproducibility
    )
    return result.actual_model_path          # HF snapshot dir, resolved for you
```

Return `result.actual_model_path`, not `target_dir` — for HF models the two differ
(the snapshot lives under `models--{org}--{repo}/snapshots/{hash}/`), and the wrapper
resolves it for you.

## Layered architecture

Each layer has one job; models only ever touch Layer 1.

```
setup_download_layer()          modal/downloader.py   Build-time Modal integration:
  │                                                   mounts minimal source, runs the
  │                                                   model's download.py in-container
  ▼
download_model_assets()         models/*/download.py  Model entry point (declarative)
  │
  ▼
r2_then_* / download_with_fallback   download_helpers.py   Layer 1 — preferred API
  │
  ▼
acquire_model_weights()         acquisition.py        Layer 2 — strategy engine:
  │                                                   R2_ONLY, HUGGINGFACE_HUB,
  │                                                   LIBRARY_MANAGED, DIRECT_URLS,
  │                                                   ARCHIVE, CUSTOM; retry/validation
  ▼
downloads.py / R2Utils          downloads.py, r2_utils.py   Layers 3–4 — low-level HF
  │                                                   snapshot + atomic R2 ops
  ▼
Cloudflare R2 (biolm-public)                          Primary cache
```

**Layer 1 — `download_helpers.py` (preferred API):** `r2_then_hf`, `r2_then_library`,
`r2_then_urls`, `r2_then_archive`, plus `download_with_fallback(primary, fallback)` and
`extract_model_variant(...)`. `acquire_model_weights` remains available for advanced
custom flows.

**Layer 2 — `acquisition.py`:** `acquire_model_weights()` dispatches an
`AcquisitionConfig` to a strategy (`AcquisitionStrategy.{R2_ONLY, HUGGINGFACE_HUB,
LIBRARY_MANAGED, DIRECT_URLS, ARCHIVE, CUSTOM}`) and returns an `AcquisitionResult`.

**Layer 3 — `downloads.py`:** `download_from_hf()`, `get_model_dir_util()`,
`build_hf_snapshot_path()`, `verify_model_dir()`, `download_file_with_size_optimization()`,
`download_archive()` / `extract_archive_subtree()`.

**Layer 4 — `r2_utils.py` (`R2Utils`):** `upload_to_r2_atomic()`,
`restore_from_r2_atomic()`, `download_from_r2_prefix()`, `check_completion_marker()`,
`validate_manifest()`. Every R2 read/write for weights and test data goes through here.

## R2 atomic caching

R2 is the primary cache. An upload is only "visible" once a completion marker lands,
so a half-finished upload can never be mistaken for a full one.

1. **Upload** (`upload_to_r2_atomic`): push all files → write `.r2_manifest.json`
   (per-file size + SHA256) → write `.r2_cache_complete` (the atomic commit).
2. **Restore** (`restore_from_r2_atomic`): require the completion marker → download the
   prefix (`download_from_r2_prefix`, with an optional per-key `filter_func` for
   single-variant subsets) → optionally validate against the manifest → success only if
   complete. No marker / no files ⇒ `success=False` ⇒ the wrapper falls back to source.

```
r2://biolm-public/biolm-hub/model-weights/models/esmc/v1/esmc_300m/
├── models--EvolutionaryScale--esmc-300m-2024-12/snapshots/{hash}/...
├── .r2_manifest.json      # {file: {size, sha256, mtime}}
└── .r2_cache_complete     # {completed_at, r2_prefix, file_count, manifest_key}
```

All five acquisition strategies share this one restore primitive
(`_acquire_r2_only → restore_from_r2_atomic → download_from_r2_prefix`), so there is a
single R2-read code path — not a per-strategy copy.

## Credential-less deploys

A user whose Modal workspace has no `cloudflare-r2` / `hf-api-token` secret sets
`BIOLM_SKIP_MODAL_SECRETS=1`. The build then mounts no download secrets and
`restore_from_r2_atomic` reads the **public bucket anonymously over `r2.dev` HTTP**
(manifest-driven, full set — the per-key `filter_func` is a signed-read optimization and
is not applied to the public path). No credentials ⇒ no self-population back to R2, which
is correct for a read-only consumer. Maintainer deploys leave the flag unset and
self-populate. The flag gates the build **and** is baked into the image
(`setup_source_layer`) so the runtime container resolves secrets identically to deploy
time — see `models/commons/modal/source.py` for why that lockstep matters.

## Troubleshooting

- **`No files found in R2 at prefix`** — expected on first deploy of a model; the wrapper
  falls back to source and (with credentials) caches the result. Persistent misses mean
  the R2 prefix doesn't match `get_model_dir_util(...)`'s layout.
- **Model loads from the wrong directory** — use `result.actual_model_path`, not
  `target_dir`; HF models return the nested snapshot directory.
- **Library downloaded to an unexpected location** — the library ignores its cache-redir
  env var; set the right `env_vars` on `r2_then_library` (or `cache_to_r2=False` to
  skip R2 caching for libraries that keep an out-of-tree cache).
- **Manifest checksum mismatch on restore** — the R2 copy is corrupt or partial;
  re-run a maintainer deploy to re-upload atomically.

```bash
bh r2 ls | grep biolm-hub/model-weights/models/esmc      # inspect the cache
python -c "from models.esmc.download import download_model_assets; \
  print(download_model_assets('esmc','v1',{'MODEL_SIZE':'300m'}))"   # local dry-run
```
