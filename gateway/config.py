"""Gateway configuration — public, self-host-friendly defaults.

The gateway ships with **no authentication, billing, or analytics**. Every
setting here has a sensible default so a fresh clone deploys without any extra
configuration; each can be overridden with an environment variable for
operators who want a custom domain or tighter CORS.
"""

import os
from pathlib import Path

# --- Gateway package paths (copied into the Modal container) ---
local_gateway_path = Path(__file__).resolve().parent
remote_gateway_path = "/root/gateway"


def get_custom_domain() -> str | None:
    """Custom domain for the gateway ASGI app, or None for Modal's auto URL.

    Set ``BIOLM_GATEWAY_DOMAIN`` to bind the deployment to a custom domain
    (the domain must already be configured in the Modal workspace). When unset
    (the default), Modal serves the gateway at its generated ``*.modal.run`` URL.
    """
    domain = os.getenv("BIOLM_GATEWAY_DOMAIN", "").strip()
    return domain or None


def get_cors_allowed_origins() -> list[str]:
    """CORS allow-list for the gateway.

    Defaults to ``["*"]`` (allow any origin) so a self-hosted gateway is usable
    from local notebooks and web apps out of the box. Override with a
    comma-separated ``BIOLM_GATEWAY_CORS_ORIGINS`` to restrict it, e.g.
    ``BIOLM_GATEWAY_CORS_ORIGINS="https://example.com,http://localhost:3000"``.
    """
    raw = os.getenv("BIOLM_GATEWAY_CORS_ORIGINS", "").strip()
    if not raw:
        return ["*"]
    return [origin.strip() for origin in raw.split(",") if origin.strip()]
