"""Invoke a model action from the MCP, with clean, actionable error handling.

The probe surface (catalog/knowledge/schemas) is static; this is the one place the MCP touches
Modal. Every failure mode an agent can hit — the model isn't deployed, Modal auth/token is missing,
a timeout, a dropped connection, or invalid input — is caught and turned into a short, actionable
message (surfaced by FastMCP as an ``isError`` tool result) instead of a stack trace.

By default it dispatches directly via the Modal SDK using the credentials of the process running
``bh mcp`` (exactly how ``bh serve`` calls models). Pass ``gateway_url`` to POST to a deployed
gateway instead (e.g. for a hosted MCP that holds no Modal credentials).
"""

from __future__ import annotations

from typing import Any, Optional, cast

from pydantic import BaseModel, ValidationError

from gateway.model_discovery import ModelMapper


class InvokeError(ValueError):
    """A clean, actionable error. Subclasses ValueError so FastMCP surfaces it as an isError result."""


def _variants_for(mapper: ModelMapper, base: str) -> list[str]:
    return sorted(
        slug
        for slug, info in mapper.get_all_variant_mappings().items()
        if info["base_model_slug"] == base
    )


def _resolve_variant(mapper: ModelMapper, slug: str) -> dict[str, Any]:
    """Resolve a deployable variant slug, with a helpful error for a family slug or a typo."""
    info = mapper.get_variant_info(slug)
    if info is not None:
        return info
    if slug in mapper.get_all_registered_models():
        variants = _variants_for(mapper, slug)
        raise InvokeError(
            f"'{slug}' is a model family, not a deployable variant. "
            f"Pick one: {', '.join(variants)}."
        )
    raise InvokeError(
        f"Unknown model '{slug}'. Use list_models to see available slugs."
    )


def _format_validation(error: ValidationError) -> str:
    parts = []
    for item in error.errors()[:5]:
        loc = ".".join(str(p) for p in item.get("loc", ()))
        parts.append(f"{loc}: {item.get('msg')}" if loc else str(item.get("msg")))
    return "; ".join(parts)


def _validate_input(
    mapper: ModelMapper,
    base: str,
    slug: str,
    action: str,
    items: list[dict[str, Any]],
    params: Optional[dict[str, Any]],
) -> BaseModel:
    req_schema, _res = mapper.get_action_schemas(base, action)
    if req_schema is None:
        available = sorted(
            name for name, _q, _s in mapper.get_all_actions_for_model(base)
        )
        raise InvokeError(
            f"Model '{base}' has no action '{action}'. Available: {', '.join(available)}."
        )
    payload: dict[str, Any] = {"items": items}
    if params is not None:
        payload["params"] = params
    try:
        return req_schema.model_validate(payload)
    except ValidationError as e:
        raise InvokeError(
            f"Invalid input for {slug}/{action}: {_format_validation(e)}"
        ) from e


def _check_model_result(result: Any, slug: str, action: str) -> dict[str, Any]:
    """Pass a success dict through; turn the model's own structured error into a clean message."""
    if not isinstance(result, dict):
        raise InvokeError(f"Unexpected response from {slug}/{action}.")
    if "results" not in result and isinstance(result.get("status_code"), int):
        detail = result.get("detail", "model error")
        code = result.get("code")
        suffix = f" (code={code})" if code else ""
        raise InvokeError(f"{slug}/{action} rejected the request: {detail}{suffix}")
    return result


async def _invoke_via_modal(
    modal_app_name: str,
    class_name: str,
    base: str,
    slug: str,
    action: str,
    payload: BaseModel,
) -> dict[str, Any]:
    import modal

    payload_dict = payload.model_dump(mode="json")
    try:
        instance = modal.Cls.from_name(modal_app_name, class_name)()
        remote = getattr(instance, action)
        result = await remote.remote.aio(payload=payload_dict, _skip_cache=True)
    except modal.exception.NotFoundError as e:
        raise InvokeError(
            f"Model '{slug}' isn't deployed to Modal. Deploy it with: bh deploy {base}"
        ) from e
    except modal.exception.AuthError as e:
        raise InvokeError(
            "Modal authentication failed. Set up credentials with: modal token new"
        ) from e
    except modal.exception.FunctionTimeoutError as e:
        raise InvokeError(f"'{slug}/{action}' timed out on Modal.") from e
    except modal.exception.ConnectionError as e:
        raise InvokeError(
            "Couldn't reach Modal. Check your connection and retry."
        ) from e
    except modal.exception.Error as e:
        raise InvokeError(f"Modal error invoking {slug}/{action}: {e}") from e
    return _check_model_result(result, slug, action)


async def _invoke_via_gateway(
    gateway_url: str, slug: str, action: str, payload: BaseModel
) -> dict[str, Any]:
    import httpx

    url = f"{gateway_url.rstrip('/')}/api/v1/{slug}/{action}"
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(300.0)) as client:
            resp = await client.post(url, json=payload.model_dump(mode="json"))
    except httpx.HTTPError as e:
        raise InvokeError(f"Couldn't reach the gateway at {gateway_url}: {e}") from e
    if resp.status_code >= 400:
        raise InvokeError(
            f"Gateway returned {resp.status_code} for {slug}/{action}: {_safe_detail(resp)}"
        )
    return cast(dict[str, Any], resp.json())


def _safe_detail(resp: Any) -> str:
    try:
        body = resp.json()
    except ValueError:
        return str(resp.text)[:200]
    return str(body.get("detail", body)) if isinstance(body, dict) else str(body)[:200]


async def invoke_action(
    mapper: ModelMapper,
    slug: str,
    action: str,
    items: list[dict[str, Any]],
    params: Optional[dict[str, Any]] = None,
    gateway_url: Optional[str] = None,
) -> dict[str, Any]:
    """Validate then dispatch one action call, raising :class:`InvokeError` on any failure."""
    variant = _resolve_variant(mapper, slug)
    base = str(variant["base_model_slug"])
    payload = _validate_input(mapper, base, slug, action, items, params)
    if gateway_url:
        return await _invoke_via_gateway(gateway_url, slug, action, payload)
    class_name = mapper.get_class_name(base)
    if not class_name:
        raise InvokeError(
            f"Model '{base}' has no Modal class configured; cannot invoke it."
        )
    return await _invoke_via_modal(
        str(variant["modal_app_name"]), class_name, base, slug, action, payload
    )
