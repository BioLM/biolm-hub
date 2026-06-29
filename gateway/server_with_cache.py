"""Cached BioLM Models gateway — routing + optional response cache.

Identical to the bare ``gateway/server.py`` except it routes requests through
the response-cache machinery. **Both cache tiers (modal.Dict short-term + R2
long-term) are OFF by default** and only activate when ``BIOLM_CACHE_ENABLED``
is set to a truthy value (``1``/``true``/``yes``). With caching off this gateway
behaves exactly like the bare one, just with the cache code path present.

Caching at the gateway layer (rather than inside each model) lets a cache hit
skip the Modal round-trip to the model entirely.

Deploy (from the repo root):
    python -m gateway.deploy_gateway --cache   # or: modal deploy gateway/server_with_cache.py

    # ...and to actually serve from cache, deploy with the flag set, e.g.:
    BIOLM_CACHE_ENABLED=1 python -m gateway.deploy_gateway --cache
"""

from pathlib import Path

import modal

from gateway.config import (
    get_custom_domain,
    local_gateway_path,
    remote_gateway_path,
)
from models.commons.util.config import (
    cloudflare_r2_secret,
    common_requirements,
    remote_models_path,
)

# The gateway imports every model's config.py at startup, so it needs the WHOLE
# models/ tree (models/__init__.py + models/commons/ + every models/<slug>/)
# mounted at /root/models, so we compute the real source dir here.
_local_models_dir = Path(__file__).resolve().parent.parent / "models"
_pycache_ignore = modal.FilePatternMatcher("**/__pycache__", "**/*.pyc")

image = (
    modal.Image.debian_slim(python_version="3.12")
    .uv_pip_install(common_requirements)
    # `requests` is needed because the cache path lazily imports the storage/
    # acquisition stack (commons.storage.acquisition imports requests); the bare
    # gateway never imports it, so it doesn't carry this dependency.
    .uv_pip_install("fastapi[standard]==0.112.0", "requests==2.32.3")
    .add_local_dir(
        _local_models_dir, remote_models_path, ignore=_pycache_ignore, copy=True
    )
    .add_local_dir(
        local_gateway_path, remote_gateway_path, ignore=_pycache_ignore, copy=True
    )
)

app = modal.App("biolm-gateway-cache", image=image)

_custom_domains = [d] if (d := get_custom_domain()) else []


@app.function(
    # R2 secret powers the long-term (R2) cache tier when BIOLM_CACHE_ENABLED is set.
    secrets=[cloudflare_r2_secret],
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
    """ASGI entrypoint: build and return the cache-enabled gateway app."""
    from gateway.model_discovery import get_model_mapper
    from gateway.routing import build_gateway_app

    return build_gateway_app(get_model_mapper(), use_cache=True)
