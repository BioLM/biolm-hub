"""Bare BioLM Models gateway — routing only, no response cache.

This is the minimal gateway: it discovers deployed models from their
``config.py`` files and exposes one ``POST /api/v3/{slug}/{action}`` route per
(variant, action), forwarding each validated request to the deployed Modal
model class. No auth, no billing, no analytics, no caching.

Deploy (from the repo root):
    python -m gateway.deploy_gateway      # or: modal deploy gateway/server.py

Override the served domain or CORS with ``BIOLM_GATEWAY_DOMAIN`` /
``BIOLM_GATEWAY_CORS_ORIGINS`` (see ``gateway/config.py``).
"""

from pathlib import Path

import modal

from gateway.config import (
    get_custom_domain,
    local_gateway_path,
    remote_gateway_path,
)
from models.commons.util.config import common_requirements, remote_models_path

# The gateway imports every model's config.py at startup, so it needs the WHOLE
# models/ tree (models/__init__.py + models/commons/ + every models/<slug>/)
# mounted at /root/models. (commons' `local_models_path` resolves to
# models/commons, not models/, so we compute the real source dir here.)
_local_models_dir = Path(__file__).resolve().parent.parent / "models"
_pycache_ignore = modal.FilePatternMatcher("**/__pycache__", "**/*.pyc")

image = (
    modal.Image.debian_slim(python_version="3.12")
    .uv_pip_install(common_requirements)
    .uv_pip_install("fastapi[standard]==0.112.0")
    .add_local_dir(
        _local_models_dir, remote_models_path, ignore=_pycache_ignore, copy=True
    )
    .add_local_dir(
        local_gateway_path, remote_gateway_path, ignore=_pycache_ignore, copy=True
    )
)

app = modal.App("biolm-gateway", image=image)

# Bind a custom domain only if one is configured; otherwise Modal serves the
# app at its generated *.modal.run URL.
_custom_domains = [d] if (d := get_custom_domain()) else []


@app.function(
    # Cold start imports every model's config + builds all routes — give it a
    # full CPU so first-request latency stays low (idle still scales to $0).
    cpu=1.0,
    memory=512,
    scaledown_window=15,
    max_containers=50,
    timeout=60 * 60,
)
@modal.concurrent(max_inputs=100)
@modal.asgi_app(custom_domains=_custom_domains)
def web():
    """ASGI entrypoint: build and return the bare (no-cache) gateway app."""
    from gateway.model_discovery import get_model_mapper
    from gateway.routing import build_gateway_app

    return build_gateway_app(get_model_mapper(), use_cache=False)
