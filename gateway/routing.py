"""Shared gateway routing core.

Both gateway variants — the bare ``gateway/gateway.py`` (no response cache) and
``gateway/gateway_with_cache.py`` (both cache tiers, off by default) — build their
FastAPI app from :func:`build_gateway_app`. The only difference is the
``use_cache`` flag.

This module is imported only inside the Modal container (from each gateway's
ASGI entrypoint), so it imports FastAPI at module scope.

Design notes:
- **No auth / billing / analytics.** The gateway routes a validated request to a
  deployed Modal model class and returns its response. That's it.
- **Config-driven discovery.** The Modal container class name comes from
  ``ModelFamily.modal_class_name`` via :class:`~gateway.model_discovery.ModelMapper`
  — no source-code scanning.
- **status_code → HTTP status.** Models return a structured ``ErrorResponse``
  (``{"detail", "errors", "status_code", "code"}``) on failure. The gateway
  promotes that body ``status_code`` to the real HTTP status so external/agent
  callers can rely on HTTP semantics (decision deferred from W7 to W8).
"""

import functools
import re
from collections.abc import Callable
from typing import Any, cast

import modal
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from gateway.config import get_cors_allowed_origins
from gateway.model_discovery import ModelMapper
from models.commons.core.logging import DebugLogger, get_logger
from models.commons.data.serializer import serialize_model

# NOTE: the response-cache stack (commons.core.caching → commons.storage.*) is
# imported lazily inside the cache code path only, so the bare gateway never
# pulls in the weight-acquisition deps (e.g. `requests`) it doesn't use.

logger = get_logger(__name__)


class _ModelErrorResponse(Exception):
    """Internal signal that a model returned a structured ErrorResponse.

    Lets an error surfaced inside the cached compute path short-circuit back to
    the request handler so the body ``status_code`` can be promoted to HTTP.
    """

    def __init__(self, payload: dict[str, Any]):
        super().__init__(payload.get("detail", "model error"))
        self.payload = payload


def _is_error_response(resp: Any) -> bool:
    """True if a model response is a structured ErrorResponse rather than success.

    Success responses carry a ``results`` list; the ``ErrorResponse`` model
    carries an integer ``status_code`` (and ``detail``) with no ``results``.
    """
    return (
        isinstance(resp, dict)
        and "results" not in resp
        and isinstance(resp.get("status_code"), int)
    )


def _sanitize_error_message(error_msg: str) -> str:
    """Strip filesystem paths and long tokens from a gateway-side error string."""
    sanitized = re.sub(r"/[^\s]+", "<path>", error_msg)
    sanitized = re.sub(r"[A-Za-z0-9_-]{20,}", "<token>", sanitized)
    if len(sanitized) > 200:
        sanitized = sanitized[:200] + "..."
    return sanitized


@functools.lru_cache(maxsize=256)
def _model_class(modal_app_name: str, class_name: str) -> modal.cls.Obj:
    """Resolve (and cache) a deployed Modal model class handle.

    Instantiated with no arguments — the container class supplies defaults for
    any constructor parameters (e.g. the legacy ``app_username``).
    """
    return modal.Cls.from_name(modal_app_name, class_name)()


async def _compute_remotely(
    payload: BaseModel,
    modal_app_name: str,
    class_name: str,
    model_action: str,
) -> dict[str, Any]:
    """Dispatch a single (possibly partial) request to the deployed Modal model.

    The model is told to skip its own validation (the gateway already validated
    via the FastAPI route's request schema) and its own response cache (the
    cached gateway caches at this layer instead).
    """
    try:
        instance = _model_class(modal_app_name, class_name)
        remote_function = getattr(instance, model_action)
        # The remote Modal function is resolved dynamically (getattr), so its
        # return type is unknown to mypy; cast to the documented contract
        # (a JSON-serializable response dict).
        return cast(
            dict[str, Any],
            await remote_function.remote.aio(
                payload=payload, _skip_validation=True, _skip_cache=True
            ),
        )
    except modal.exception.NotFoundError as e:
        raise HTTPException(
            status_code=404,
            detail=f"Model '{modal_app_name}' is not deployed.",
        ) from e
    except modal.exception.FunctionTimeoutError as e:
        raise HTTPException(status_code=504, detail="Model execution timed out.") from e
    except modal.exception.ConnectionError as e:
        raise HTTPException(
            status_code=503, detail="Could not reach the model backend."
        ) from e


async def _run_cached(
    payload: BaseModel,
    request_schema: type[BaseModel],
    response_schema: type[BaseModel],
    public_slug: str,
    modal_app_name: str,
    class_name: str,
    model_action: str,
) -> dict[str, Any]:
    """Cache-check → compute-misses → merge, then return the assembled dict.

    Caching tiers are gated inside ``process_with_cache`` by ``BIOLM_CACHE_ENABLED``
    (off by default), so this path is a no-op cache that computes every item
    unless an operator opts in.
    """
    # Lazy import: only the cache path needs the storage/acquisition stack.
    from models.commons.core.caching import process_with_cache

    items = getattr(payload, "items", [])
    params_obj = getattr(payload, "params", None)
    params_dict = serialize_model(params_obj) if params_obj else None

    # Full items (with None defaults) captured once outside the closure so the
    # partial-payload reconstruction preserves nested fields that
    # serialize_model(exclude_none=True) would otherwise strip.
    full_items = payload.model_dump().get("items", [])

    async def _compute(
        items_to_compute: list[BaseModel], indices_to_compute: list[int]
    ) -> BaseModel:
        partial_payload_dict = serialize_model(payload)
        partial_payload_dict["items"] = [full_items[i] for i in indices_to_compute]
        partial_payload = request_schema.model_validate(partial_payload_dict)
        result_dict = await _compute_remotely(
            partial_payload, modal_app_name, class_name, model_action
        )
        if _is_error_response(result_dict):
            raise _ModelErrorResponse(result_dict)
        # process_with_cache merges by index off the response's `.results`
        # attribute, so the closure must return a Pydantic model (not a dict);
        # returning a dict would silently drop the merge and return only the
        # freshly-computed items on a partial cache hit.
        return response_schema.model_validate(result_dict)

    debug_logger = DebugLogger(
        enabled=False,
        extra_context={"model_slug": public_slug, "model_action": model_action},
    )
    final_response_dict, _computed = await process_with_cache(
        items=items,
        params=params_dict,
        model_slug=public_slug,
        model_action=model_action,
        compute_fn=_compute,
        debug_logger=debug_logger,
    )
    return final_response_dict


async def _handle_request(
    *,
    use_cache: bool,
    public_slug: str,
    modal_app_name: str,
    class_name: str,
    model_action: str,
    request_schema: type[BaseModel],
    response_schema: type[BaseModel],
    payload: BaseModel,
) -> dict[str, Any] | JSONResponse:
    """Route one request to the model and promote any model error to HTTP status."""
    # Never cache stochastic actions (e.g. `generate`) — caching them would
    # return byte-identical samples for repeated identical inputs. Mirrors the
    # model-side guard in commons/core/decorator.py. (non_cacheable_actions is
    # imported lazily so the bare gateway doesn't pull in the cache stack.)
    route_through_cache = use_cache
    if use_cache:
        from models.commons.core.caching import non_cacheable_actions

        route_through_cache = model_action not in non_cacheable_actions

    if route_through_cache:
        try:
            response_dict = await _run_cached(
                payload,
                request_schema,
                response_schema,
                public_slug,
                modal_app_name,
                class_name,
                model_action,
            )
        except _ModelErrorResponse as err:
            return JSONResponse(
                status_code=err.payload["status_code"], content=err.payload
            )
    else:
        response_dict = await _compute_remotely(
            payload, modal_app_name, class_name, model_action
        )

    # Promote a structured model error to the real HTTP status.
    if _is_error_response(response_dict):
        return JSONResponse(
            status_code=response_dict["status_code"], content=response_dict
        )

    if not isinstance(response_dict, dict) or "results" not in response_dict:
        raise HTTPException(
            status_code=500,
            detail=f"Invalid result structure from {model_action}.",
        )
    return response_dict


def _make_endpoint_handler(
    *,
    use_cache: bool,
    public_slug: str,
    modal_app_name: str,
    class_name: str,
    model_action: str,
    request_schema: type[BaseModel],
    response_schema: type[BaseModel],
) -> Callable[..., Any]:
    """Build a FastAPI endpoint that forwards to :func:`_handle_request`.

    The factory captures per-route values to dodge Python's late-binding gotcha,
    and annotates ``payload`` with the request schema so FastAPI validates it.

    Return type is deliberately ``Callable[..., Any]`` rather than a precise
    ``Coroutine[..., dict | JSONResponse]``: FastAPI's own ``add_api_route``
    stub declares ``endpoint: Callable[..., Coroutine[Any, Any, Response]]``,
    which doesn't admit a handler that (by design) sometimes returns a plain
    dict for ``response_model`` validation and sometimes a ``JSONResponse``
    to bypass it for structured model errors — both are supported at runtime.
    """

    async def endpoint_handler(
        payload: request_schema,  # type: ignore[valid-type]  # dynamic per-model Pydantic class; kept as a real runtime annotation so FastAPI validates the request body against it
        request: Request,
    ) -> dict[str, Any] | JSONResponse:
        return await _handle_request(
            use_cache=use_cache,
            public_slug=public_slug,
            modal_app_name=modal_app_name,
            class_name=class_name,
            model_action=model_action,
            request_schema=request_schema,
            response_schema=response_schema,
            payload=payload,
        )

    endpoint_handler.__name__ = f"handle_{public_slug.replace('-', '_')}_{model_action}"
    return endpoint_handler


def _register_model_routes(
    fastapi_app: FastAPI, model_mapper: ModelMapper, *, use_cache: bool
) -> int:
    """Register one ``POST /api/v3/{slug}/{action}`` route per (variant, action)."""
    route_count = 0
    for public_slug, variant_info in model_mapper.get_all_variant_mappings().items():
        base_slug = variant_info["base_model_slug"]
        modal_app_name = variant_info["modal_app_name"]
        class_name = model_mapper.get_class_name(base_slug)
        if not class_name:
            logger.warning(
                "Skipping routes for '%s': no modal_class_name configured.", base_slug
            )
            continue

        for action, req_schema, res_schema in model_mapper.get_all_actions_for_model(
            base_slug
        ):
            handler = _make_endpoint_handler(
                use_cache=use_cache,
                public_slug=public_slug,
                modal_app_name=modal_app_name,
                class_name=class_name,
                model_action=action,
                request_schema=req_schema,
                response_schema=res_schema,
            )
            fastapi_app.add_api_route(
                path=f"/api/v3/{public_slug}/{action}",
                endpoint=handler,
                methods=["POST"],
                response_model=res_schema,
                tags=[base_slug],
                summary=f"Run {action} on {variant_info.get('display_name', public_slug)}",
            )
            route_count += 1
    return route_count


def build_gateway_app(model_mapper: ModelMapper, *, use_cache: bool) -> FastAPI:
    """Build the gateway FastAPI app.

    Args:
        model_mapper: The (config-driven) model discovery map.
        use_cache: When True, route through the response-cache machinery
            (still inert unless ``BIOLM_CACHE_ENABLED`` is set). When False,
            every request goes straight to the model.
    """
    fastapi_app = FastAPI(
        title="BioLM Models Gateway",
        description=(
            "A unified, self-hostable gateway for the BioLM open biological "
            "ML model catalog. Routes requests to deployed Modal model apps."
        ),
        version="1.0.0",
        redirect_slashes=True,
    )

    # Middleware executes in reverse order of addition.
    fastapi_app.add_middleware(GZipMiddleware, minimum_size=1000)
    fastapi_app.add_middleware(
        CORSMiddleware,
        allow_origins=get_cors_allowed_origins(),
        allow_credentials=False,  # no auth → no cookies/credentials
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @fastapi_app.exception_handler(Exception)
    async def _unhandled_exception_handler(
        request: Request, exc: Exception
    ) -> JSONResponse:
        """Uniform, sanitized 500 for any error not already mapped to a status."""
        logger.error(
            "Unhandled gateway error for %s: %s", request.url, exc, exc_info=True
        )
        return JSONResponse(
            status_code=500,
            content={
                "detail": "An unexpected backend error occurred.",
                "errors": [_sanitize_error_message(str(exc))],
                "status_code": 500,
                "code": None,
            },
        )

    @fastapi_app.get("/", tags=["Health"])
    async def health_check() -> dict[str, Any]:
        """Confirm the gateway is running and list supported models."""
        return {
            "status": "ok",
            "message": "BioLM Models Gateway is running",
            "cache_enabled_at_build": use_cache,
            "supported_models": model_mapper.get_all_registered_models(),
        }

    @fastapi_app.get("/resource-specs", tags=["Gateway"])
    async def resource_specs() -> dict[str, dict[str, Any]]:
        """Return the resource specifications for all model variants."""
        return model_mapper.get_all_resource_specs()

    route_count = _register_model_routes(fastapi_app, model_mapper, use_cache=use_cache)
    logger.info("Registered %d gateway routes (use_cache=%s)", route_count, use_cache)
    return fastapi_app
