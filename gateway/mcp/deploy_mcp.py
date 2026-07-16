"""Host the biolm-hub MCP server on Modal over stateless Streamable HTTP.

An **opt-in, unauthenticated hosted surface** for the MCP server — the same stance as the gateway
(``gateway/server.py``): anyone who can reach the URL can call it, and it bills the deployer's Modal
account, so don't expose it publicly without your own access control. It is **metadata-only by
default** — ``list_models`` / ``search_models`` / ``get_model_knowledge`` / ``get_model_schema`` /
``find_alternatives`` / ``find_complements`` / ``suggest_pipeline`` / ``get_openapi`` and every
``biolm://`` resource are static reads of the repo tree (no Modal, no billing). Only ``invoke_action``
runs a model, and only when a client calls it.

Deploy (from the repo root)::

    modal deploy gateway/mcp/deploy_mcp.py     # → https://<workspace>--biolm-mcp-web.modal.run/mcp

Bind a custom domain with ``BIOLM_MCP_DOMAIN`` (the domain must already be configured in the Modal
workspace); unset (the default) serves at Modal's generated ``*.modal.run`` URL.

Statelessness: MCP is served in **stateless** Streamable-HTTP mode — each request is fully
self-contained (no per-session state held on the server), which is what lets Modal fan requests
across containers and scale to zero safely.
"""

import os
from pathlib import Path
from typing import TYPE_CHECKING

import modal

from gateway.config import local_gateway_path, remote_gateway_path
from models.commons.util.config import common_requirements, remote_models_path

if TYPE_CHECKING:
    from starlette.applications import Starlette

# The MCP server imports every model's config.py (to enumerate the catalog) and the gateway package
# (gateway.mcp.* + gateway.routing, the latter for get_openapi), so mount BOTH the whole models/
# tree at /root/models and the gateway/ package at /root/gateway.
_local_models_dir = Path(__file__).resolve().parent.parent.parent / "models"
_pycache_ignore = modal.FilePatternMatcher("**/__pycache__", "**/*.pyc")

image = (
    modal.Image.debian_slim(python_version="3.12")
    .uv_pip_install(common_requirements)
    # The [mcp] extra: FastMCP + its Streamable-HTTP ASGI app. Pulls in starlette (which builds the
    # app) and uvicorn transitively, so no extra web-server pins are needed here. Pinned exact and
    # kept in lockstep with the [mcp] extra in pyproject.toml.
    .uv_pip_install("mcp==1.28.1")
    # get_openapi builds the gateway FastAPI app in-process to emit its OpenAPI document; without
    # FastAPI that tool degrades to a clean [serve]-extra error. Shipping it (same pin as
    # gateway/server.py) keeps the hosted MCP fully capable and at parity with the gateway.
    .uv_pip_install("fastapi[standard]==0.139.0")
    .add_local_dir(
        _local_models_dir, remote_models_path, ignore=_pycache_ignore, copy=True
    )
    .add_local_dir(
        local_gateway_path, remote_gateway_path, ignore=_pycache_ignore, copy=True
    )
)

app = modal.App("biolm-mcp", image=image)


def _custom_domains() -> list[str]:
    """Bind a custom domain only if one is configured; else Modal serves the ``*.modal.run`` URL."""
    domain = os.getenv("BIOLM_MCP_DOMAIN", "").strip()
    return [domain] if domain else []


@app.function(
    # Cold start imports every model's config + builds the catalog snapshot — give it a full CPU so
    # first-request latency stays low (idle still scales to $0).
    cpu=1.0,
    memory=512,
    scaledown_window=15,
    max_containers=50,
    timeout=60 * 60,
)
@modal.concurrent(max_inputs=100)
@modal.asgi_app(custom_domains=_custom_domains())
def web() -> "Starlette":
    """ASGI entrypoint: build the MCP server and return its stateless Streamable-HTTP app."""
    from gateway.mcp.server import build_mcp_server
    from gateway.model_discovery import get_model_mapper

    server = build_mcp_server(get_model_mapper())
    # Stateless mode: no per-client session is retained between requests, so requests can land on
    # any container and the app can scale to zero. streamable_http_app() reads this at build time.
    server.settings.stateless_http = True
    return server.streamable_http_app()
