"""Mount the interactive catalog UI onto a gateway FastAPI app.

The catalog is the *human face* of the gateway: a browsable list of models (with
deployed/undeployed status) and a schema-driven form to run inference. Its forms
POST to the gateway's own ``/api/v3/{slug}/{action}`` routes, so every run goes
through the same routing logic that programmatic callers use.

:func:`mount_catalog` adds ``/static``, ``/catalog`` and ``/catalog/{slug}`` to an
app already built by :func:`gateway.routing.build_gateway_app`. It's used by
``bh serve`` (local web app) and can be opted into on a deployed gateway via
``BIOLM_GATEWAY_CATALOG`` (see ``gateway/server.py``).
"""

from pathlib import Path
from typing import Optional

from fastapi import FastAPI

from gateway.catalog.deployment_status import get_deployment_status
from gateway.catalog.generator import generate_catalog_data, group_models_by_base
from gateway.model_discovery import ModelMapper
from models.commons.core.logging import get_logger

logger = get_logger(__name__)

_CATALOG_DIR = Path(__file__).resolve().parent


def mount_catalog(
    fastapi_app: FastAPI,
    model_mapper: ModelMapper,
    *,
    environment: Optional[str] = None,
    gateway_url: str = "",
    check_deployment_status: bool = True,
) -> None:
    """Mount the catalog UI (``/catalog``, ``/catalog/{slug}``, ``/static``).

    Must be called AFTER the model routes are registered (the catalog is built by
    scanning the app's ``/api/v3`` routes).

    Args:
        fastapi_app: The app returned by ``build_gateway_app``.
        model_mapper: The discovery map (used to resolve deployment status).
        environment: Modal environment to check deployment status against.
        gateway_url: Optional absolute base URL to send inference requests to
            (e.g. a remote deployed gateway). Empty = same-origin (the default),
            so the forms POST back to this app.
        check_deployment_status: Query Modal for deployed/undeployed status.
            True for ``bh serve`` (works locally). False on a deployed gateway,
            where the container has no Modal CLI credentials (the query would
            always fail) and per-request subprocess spawns are a needless risk —
            the catalog then renders without deployment badges.
    """
    from fastapi import HTTPException, Request, Response
    from fastapi.concurrency import run_in_threadpool
    from fastapi.staticfiles import StaticFiles
    from fastapi.templating import Jinja2Templates

    fastapi_app.mount(
        "/static",
        StaticFiles(directory=str(_CATALOG_DIR / "static")),
        name="static",
    )
    templates = Jinja2Templates(directory=str(_CATALOG_DIR / "templates"))

    # Static structure (routes don't change after startup); deployment status is
    # queried per request so the catalog reflects newly deployed models.
    catalog_data = generate_catalog_data(fastapi_app)
    grouped_catalog = group_models_by_base(catalog_data)
    logger.info("Catalog mounted for %d model variants", len(catalog_data))

    async def _status() -> dict[str, Optional[bool]]:
        # Off the event loop: the Modal query is a blocking subprocess.
        if not check_deployment_status:
            return {}
        return await run_in_threadpool(get_deployment_status, model_mapper, environment)

    @fastapi_app.get("/catalog", include_in_schema=False)
    async def get_catalog(request: Request) -> Response:
        return templates.TemplateResponse(
            request,
            "catalog.html",
            {"grouped_catalog": grouped_catalog, "status": await _status()},
        )

    @fastapi_app.get("/catalog/{model_slug}", include_in_schema=False)
    async def get_model_catalog(request: Request, model_slug: str) -> Response:
        if model_slug not in catalog_data:
            raise HTTPException(status_code=404, detail="Model not found")
        return templates.TemplateResponse(
            request,
            "model.html",
            {
                "model_info": catalog_data[model_slug],
                "deployed": (await _status()).get(model_slug),
                "gateway_url": gateway_url,
            },
        )
