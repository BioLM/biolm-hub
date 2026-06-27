import os
from pathlib import Path

import modal

# R2
# The bucket defaults to the public OSS bucket and may be overridden via the
# BIOLM_R2_BUCKET environment variable. The logical prefixes below are stable.
r2_bucket_name = os.getenv("BIOLM_R2_BUCKET", "biolm-public")
r2_model_store_dir = "model-store"
r2_model_cache_dir = "model-cache"
r2_test_data_dir = "test-data"


# Modal paths
local_models_path = Path(__file__).resolve().parent.parent
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

protocols_r2_bucket_secret_name = "protocols-r2-bkt"
protocols_r2_bucket_secret = modal.Secret.from_name(protocols_r2_bucket_secret_name)

huggingface_api_token_secret_name = "hf-api-token"
huggingface_api_token_secret = modal.Secret.from_name(huggingface_api_token_secret_name)

nvidia_ngc_secret_name = "ngc-cli-api-key"
nvidia_ngc_secret = modal.Secret.from_name(nvidia_ngc_secret_name)


# Modal environments
qa_environment_name = "qa"
prod_environment_name = "main"
deployed_environment_names = [qa_environment_name, prod_environment_name]


# Validation parameters
# Max length of PDB string characters
max_pdb_str_len = 2_500_000  # About 2.5MB
# Max length of FASTA string characters
max_fasta_str_len = 50000  # About 50KB
