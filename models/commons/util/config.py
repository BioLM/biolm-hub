import os

import modal

# R2
# The bucket defaults to the public OSS bucket and may be overridden via the
# BIOLM_R2_BUCKET environment variable. All artifacts are namespaced under a
# `biolm-hub/` prefix (the bucket is shared with other BioLM public assets) and
# mirror the repo layout under uniform top-level dirs: weights at
# biolm-hub/model-weights/models/<slug>/<weights_version>/, golden fixtures at
# biolm-hub/test-data/models/<slug>/, response cache at biolm-hub/model-cache/models/<slug>/.
r2_bucket_name = os.getenv("BIOLM_R2_BUCKET", "biolm-public")
r2_model_store_dir = "biolm-hub/model-weights/models"
r2_model_cache_dir = "biolm-hub/model-cache/models"
r2_test_data_dir = "biolm-hub/test-data"

# Public read URL for the OSS bucket — Cloudflare R2's "Public Development URL".
# When NO R2 (S3) credentials are present, cached model weights are read
# anonymously over HTTPS GET from this base URL instead of the signed S3 API
# (see models/commons/storage/r2_http.py). This is what makes the "no credentials
# beyond Modal" happy path real. It is rate-limited and not recommended for
# production — put a custom domain on the bucket and override BIOLM_R2_PUBLIC_URL
# for that. Reads only; writes/self-population always require S3 credentials.
r2_public_url = os.getenv(
    "BIOLM_R2_PUBLIC_URL", "https://pub-c56611cf24404740b0ff53b356a6b48d.r2.dev"
)


# Modal paths
remote_models_path = "/root/models"


# Common Python requirements
# Image Builder Version: 2025.06 (workspace setting changed 2026-03-31)
common_requirements = [
    "biopython==1.84",
    "boto3==1.35.78",
    "cbor2==5.6.5",  # Required for Modal SDK >= 1.2 serialization protocol
    "modal==1.3.5",
    "orjson==3.10.12",
    "pydantic==2.11.7",
    # `requests` is a cold-start runtime dep: storage/__init__.py eagerly imports
    # the acquisition engine (the curated public storage API), which `import
    # requests` at module top. Models bundling transformers/hf get it transitively,
    # but minimal algorithmic images (prody/biotite/dna_chisel) would crash-loop on
    # ModuleNotFoundError without it — so it belongs in the base image.
    "requests==2.32.3",
]


# Modal container scaledown window in seconds
default_scaledown_window = 2  # seconds


# Modal dicts
def get_model_cache_name(model_slug: str) -> str:
    """Generate a per-model cache name for Modal Dict.

    Each model gets its own cache to prevent large models (e.g., ESM2-3B)
    from filling a shared cache and affecting other models.

    Args:
        model_slug: The model's slug identifier (e.g., "esm2-3b", "esmfold").

    Returns:
        Cache name in format "model-cache-{model_slug}".
    """
    return f"model-cache-{model_slug}"


# Response cache feature flag.
# Both response-cache tiers (modal.Dict short-term + R2 long-term) are OFF by
# default. Enable them by setting BIOLM_CACHE_ENABLED to a truthy value.
_CACHE_TRUTHY_VALUES = {"1", "true", "yes"}


def cache_enabled() -> bool:
    """Return True if response caching is enabled via BIOLM_CACHE_ENABLED.

    Both cache tiers (modal.Dict + R2 gzip) are disabled unless the environment
    variable is set to one of "1", "true", "yes" (case-insensitive). Default off.
    """
    return os.getenv("BIOLM_CACHE_ENABLED", "").strip().lower() in _CACHE_TRUTHY_VALUES


# Modal secrets
cloudflare_r2_secret_name = "cloudflare-r2"
cloudflare_r2_secret = modal.Secret.from_name(cloudflare_r2_secret_name)

huggingface_api_token_secret_name = "hf-api-token"
huggingface_api_token_secret = modal.Secret.from_name(huggingface_api_token_secret_name)


# Credential-less deploys. A user whose Modal workspace has no `cloudflare-r2`
# secret cannot mount it: Modal's `Secret.from_name` has no `required=False`, and a
# missing named secret aborts the deploy before it starts. Set BIOLM_SKIP_MODAL_SECRETS=1
# to mount NO secrets (build download layer AND runtime container) so a genuinely
# credential-less deploy can start. Same truthy vocabulary as BIOLM_CACHE_ENABLED.
_SKIP_SECRETS_TRUTHY = {"1", "true", "yes"}


def skip_modal_secrets() -> bool:
    """Return True if BIOLM_SKIP_MODAL_SECRETS opts out of mounting Modal secrets.

    Shared by the build/download layer (models/commons/modal/downloader.py) and the
    runtime container secret (`runtime_secrets`). Import-safe: a plain env check with
    no Modal auth or network I/O. Truthy vocabulary matches BIOLM_CACHE_ENABLED
    ("1", "true", "yes", case-insensitive); default off.
    """
    return (
        os.getenv("BIOLM_SKIP_MODAL_SECRETS", "").strip().lower()
        in _SKIP_SECRETS_TRUTHY
    )


def runtime_secrets() -> list[modal.Secret]:
    """Secrets to mount on the runtime model container (`@app.cls(secrets=...)`).

    Gates the runtime model-container secret so a credential-less deploy (no
    `cloudflare-r2` secret provisioned) can start — weights are baked into the image
    at build time, so runtime R2 access isn't needed on that path. Maintainer deploys
    leave the flag unset and mount the secret.

    Import-safe: only an env check (via `skip_modal_secrets`) plus the lazy
    `cloudflare_r2_secret` object, which is already a lazy `Secret.from_name` resolved
    by Modal at deploy time — no Modal network/auth call happens here.
    """
    return [] if skip_modal_secrets() else [cloudflare_r2_secret]


# Modal environments
# The deploy targets used by CI. The non-prod ("dev") environment runs PR
# smoke/comprehensive checks; the prod environment serves the public catalog.
# Override-free defaults match the names CI deploys to.
dev_environment_name = "biolm-hub-dev"
prod_environment_name = "biolm-hub"
deployed_environment_names = [dev_environment_name, prod_environment_name]


# Validation parameters
# Max length of PDB string characters
max_pdb_str_len = 2_500_000  # About 2.5MB
# Max length of FASTA string characters
max_fasta_str_len = 50000  # About 50KB
