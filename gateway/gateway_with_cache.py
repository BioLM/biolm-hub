"""Cached BioLM Models gateway — routing + optional response cache.

Identical to the bare ``gateway/gateway.py`` except it routes requests through
the response-cache machinery. **Both cache tiers (modal.Dict short-term + R2
long-term) are OFF by default** and only activate when ``BIOLM_CACHE_ENABLED``
is set to a truthy value (``1``/``true``/``yes``). With caching off this gateway
behaves exactly like the bare one, just with the cache code path present.

Caching at the gateway layer (rather than inside each model) lets a cache hit
skip the Modal round-trip to the model entirely.

Deploy:
    modal deploy gateway/gateway_with_cache.py

    # ...and to actually serve from cache, deploy with the flag set, e.g.:
    BIOLM_CACHE_ENABLED=1 modal deploy gateway/gateway_with_cache.py
"""

import modal

from gateway.config import (
    get_custom_domain,
    local_gateway_path,
    remote_gateway_path,
)
from models.commons.util.config import (
    cloudflare_r2_secret,
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

app = modal.App("biolm-gateway-cache", image=image)

_custom_domains = [d] if (d := get_custom_domain()) else []


@app.function(
    # R2 secret powers the long-term (R2) cache tier when BIOLM_CACHE_ENABLED is set.
    secrets=[cloudflare_r2_secret],
    cpu=0.125,
    memory=512,
    scaledown_window=15,
    max_containers=50,
    timeout=60 * 60,
)
@modal.concurrent(max_inputs=100)
@modal.asgi_app(custom_domains=_custom_domains)
def gateway():
    """ASGI entrypoint: build and return the cache-enabled gateway app."""
    from gateway.model_discovery import get_model_mapper
    from gateway.routing import build_gateway_app

    return build_gateway_app(get_model_mapper(), use_cache=True)
