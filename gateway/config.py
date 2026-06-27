import os
from pathlib import Path

import modal

from models.commons.util.environment import get_environment_name

# Model Python package dirs
local_gateway_path = Path(__file__).resolve().parent
remote_gateway_path = "/root/gateway"


# Modal secrets
django_modal_secret_name = "django-modal"
django_modal_secret = modal.Secret.from_name(django_modal_secret_name)


# --- Security & Authentication ---
# Tokens for inter-service communication, managed by Modal Secrets.
internal_django_modal_auth_token_env_key = "INTERNAL_DJANGO_MODAL_AUTH_TOKEN"


# --- Analytics & Monitoring ---
moesif_applicatio_id_env_key = "MOESIF_APPLICATION_ID"


# --- Core Infrastructure ---
# URLs and connection strings for external services.
# TODO: add these as modal.Secret in production.
BIOLM_WEB_INTROSPECT_URL = "MOCK"
BIOLM_WEB_USAGE_EVENT_URL = "MOCK"


# --- Environment Variable Validation ---
def validate_required_config():
    """Validate that required environment variables are set."""
    missing_vars = []

    # Critical variables required for operation
    internal_django_modal_auth_token = os.environ.get(
        internal_django_modal_auth_token_env_key
    )
    if not internal_django_modal_auth_token:
        missing_vars.append(internal_django_modal_auth_token_env_key)

    if missing_vars:
        error_msg = f"Missing required environment variables: {', '.join(missing_vars)}"
        print(f"ERROR: {error_msg}")
        raise OSError(error_msg)

    # Warnings for optional but recommended variables
    moesif_applicatio_id = os.environ.get(moesif_applicatio_id_env_key)
    warnings = []
    if not moesif_applicatio_id:
        warnings.append(f"{moesif_applicatio_id_env_key} (analytics will be disabled)")
    if BIOLM_WEB_INTROSPECT_URL == "MOCK":
        warnings.append(
            "BIOLM_WEB_INTROSPECT_URL is set to MOCK (introspection events will be mocked)"
        )
    if BIOLM_WEB_USAGE_EVENT_URL == "MOCK":
        warnings.append(
            "BIOLM_WEB_USAGE_EVENT_URL is set to MOCK (usage events will be mocked)"
        )

    if warnings:
        print(f"WARNING: Missing optional environment variables: {', '.join(warnings)}")


def get_custom_domain():
    modal_environment = get_environment_name()
    return {
        "dev-qamar": "dev-aq.biolm.ai",
        "qa": "modbackend-qa.biolm.ai",
        "main": "modbackend-prod.biolm.ai",
    }[modal_environment]


# --- CORS Configuration ---
# Define allowed origins for cross-origin requests
def get_cors_allowed_origins():
    modal_environment = get_environment_name()
    cors_allowed_dev = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:8888",
        "http://127.0.0.1:8000",
        "https://jupyter.biolm.ai",
    ]
    return {
        "dev-qamar": cors_allowed_dev,
        "qa": cors_allowed_dev,
        "main": [
            "http://localhost:3000",  # Local development
            "https://biolm.ai",  # Production frontend
            "https//jupyter.biolm.ai",  # Biolm Jupyter
        ],
    }[modal_environment]


# MODEL_VARIANT_MAP has been replaced by the dynamic discovery system in gateway/model_discovery.py
# The discovery system automatically builds the variant map from models/*/config.py files
# This provides better maintainability and single source of truth for model metadata
