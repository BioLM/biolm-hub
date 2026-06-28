"""Bare BioLM Models gateway — routing only, no response cache.

This is the minimal gateway: it discovers deployed models from their
``config.py`` files and exposes one ``POST /api/v3/{slug}/{action}`` route per
(variant, action), forwarding each validated request to the deployed Modal
model class. No auth, no billing, no analytics, no caching.

Deploy:
    modal deploy gateway/gateway.py

Override the served domain or CORS with ``BIOLM_GATEWAY_DOMAIN`` /
``BIOLM_GATEWAY_CORS_ORIGINS`` (see ``gateway/config.py``).
"""

import modal

from gateway.config import (
    get_custom_domain,
    local_gateway_path,
    remote_gateway_path,
)
from models.commons.util.config import (
    common_requirements,
    local_models_path,
    remote_models_path,
)

image = (
    modal.Image.debian_slim(python_version="3.12")
    .uv_pip_install(common_requirements)
    .uv_pip_install("fastapi[standard]==0.112.0")
    .add_local_dir(local_models_path, remote_models_path, copy=True)
    .add_local_dir(local_gateway_path, remote_gateway_path, copy=True)
)

app = modal.App("biolm-gateway", image=image)

# Bind a custom domain only if one is configured; otherwise Modal serves the
# app at its generated *.modal.run URL.
_custom_domains = [d] if (d := get_custom_domain()) else []


@app.function(
    cpu=0.125,
    memory=512,
    scaledown_window=15,
    max_containers=50,
    timeout=60 * 60,
)
@modal.concurrent(max_inputs=100)
@modal.asgi_app(custom_domains=_custom_domains)
def gateway():
    """ASGI entrypoint: build and return the bare (no-cache) gateway app."""
    from gateway.model_discovery import get_model_mapper
    from gateway.routing import build_gateway_app

    return build_gateway_app(get_model_mapper(), use_cache=False)
