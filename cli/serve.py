"""``bh serve`` — launch a local web app to browse and run your models.

This runs entirely on your machine. It does **not** require deploying the
gateway: it serves the catalog UI and, in-process, reuses the routing logic to
expose ``/api/v1/{slug}/{action}`` endpoints that call your **individual deployed
Modal models** directly (via the Modal SDK). Browse models, see which are
deployed, and run inference from the form — no extra Modal function needed.

(The deployed gateway in ``gateway/server.py`` is a separate, optional thing for
when you want a *hosted, shareable* HTTP endpoint.)
"""

import os
from typing import Optional

import typer


def serve_cmd(
    host: str = typer.Option("127.0.0.1", help="Host to bind the local server to."),
    port: int = typer.Option(8000, help="Port to bind the local server to."),
    env: Optional[str] = typer.Option(
        None,
        "--env",
        "-e",
        help="Modal environment to target for model calls + deployment status.",
    ),
    gateway_url: Optional[str] = typer.Option(
        None,
        "--gateway-url",
        help="Send inference to a remote deployed gateway URL instead of calling "
        "models in-process (UI-only mode).",
    ),
) -> None:
    """Launch the local catalog web app (browse + run your deployed models)."""
    try:
        import uvicorn

        from gateway.catalog.mount import mount_catalog
        from gateway.model_discovery import get_model_mapper
        from gateway.routing import build_gateway_app
    except ImportError as e:
        raise typer.BadParameter(
            f"`bh serve` needs the web extras ({e.name}). "
            'Install them with: pip install "biolm-hub[serve]"'
        ) from e

    # Target a specific Modal environment for both model calls and the
    # deployment-status check (model calls read MODAL_ENVIRONMENT at call time).
    if env:
        os.environ["MODAL_ENVIRONMENT"] = env

    mapper = get_model_mapper()
    fastapi_app = build_gateway_app(mapper, use_cache=False)
    mount_catalog(fastapi_app, mapper, environment=env, gateway_url=gateway_url or "")

    typer.echo(f"biolm-hub catalog → http://{host}:{port}/catalog")
    typer.echo(f"Swagger UI       → http://{host}:{port}/docs")
    typer.echo(f"OpenAPI spec     → http://{host}:{port}/openapi.json")
    uvicorn.run(fastapi_app, host=host, port=port)
