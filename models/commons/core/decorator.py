import asyncio
import functools
import inspect
import traceback
from collections.abc import Callable
from typing import Any, Optional

import modal
import orjson
from pydantic import BaseModel, ValidationError

from models.commons.core.caching import (
    non_cacheable_actions,
    process_with_cache,
)
from models.commons.core.error import (
    ErrorResponse,
    ModelExecutionError,
    ResourceNotFoundError,
    UnsupportedOptionError,
    UserError,
    ValidationError400,
)
from models.commons.core.logging import DebugLogger, truncate_for_debug
from models.commons.data.serializer import serialize_model
from models.commons.util.config import cache_enabled


def modal_endpoint(  # noqa: C901
    app_name: str,
    debug: bool = False,
):
    # FIXME(noqa: C901): Refactor to reduce complexity below the linter's threshold.

    """
    Creates a decorator that wraps a Modal function with additional features.

    This decorator:
        1. Marks the function as a public API action (BioLM action).
        2. Deserializes JSON or dict payloads into a Pydantic model.
        3. Provides structured error responses, including debug info if requested.
        4. Catches and handles common Modal-specific exceptions.
        5. Optionally caches results (both short-term and long-term) based on the payload items.
        6. Allows skipping caching for certain actions or by setting a special flag.
        7. Registers the method signature to the SCHEMA_REGISTRY for discovery.

    Args:
        app_name (str): The name of the Modal app, e.g., "esm1v-n1".
        debug (bool): If True, includes debug information and stack traces in error responses.

    Returns:
        Callable: The decorator that can be applied to a Modal function.

    Example:
        @modal_endpoint(app_name=app_name)
        def predict(payload: MyModelRequest):
            ...
            return MyModelResponse(results=[...])

    Example Error Response:
        {
            "detail": "Validation failed for payload",
            "errors": [...],
            "status_code": 400,
        }
    """

    def decorator(func):  # noqa: C901
        # FIXME(noqa: C901): Refactor to reduce complexity below the linter's threshold.

        # Mark the function as a BioLM action (public API action)
        func._is_biolm_action = True

        # Validate the method signature (no longer registers to SCHEMA_REGISTRY)
        signature = inspect.signature(func)
        payload_param = signature.parameters.get("payload")
        if not (
            payload_param and payload_param.annotation is not inspect.Parameter.empty
        ):
            # This is an internal error, so we raise a TypeError
            raise TypeError(
                f"Function '{func.__name__}' must have a `payload` parameter with a type hint."
            )

        request_model_type: type[BaseModel] = payload_param.annotation

        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):  # noqa: C901
            # FIXME(noqa: C901): Refactor to reduce complexity below the linter's threshold.

            ### ------- [Temporary] Return payload schema logic for Python SDK -------
            _return_payload_schema = kwargs.pop("_return_payload_schema", False)
            if _return_payload_schema:
                # hasattr guard: sadie's container downgrades to pydantic v1
                schema_dict = (
                    request_model_type.model_json_schema()
                    if hasattr(request_model_type, "model_json_schema")
                    else request_model_type.schema()
                )
                return {"schema_dict": schema_dict}

            ### ------- Initial setup -------
            model_slug = app_name
            model_action = func.__name__
            debug_logger = DebugLogger(
                enabled=debug,
                extra_context={"model_slug": model_slug, "model_action": model_action},
            )

            try:
                return await _run_main_decorator_flow_async(
                    func=func,
                    model_slug=model_slug,
                    model_action=model_action,
                    signature=signature,
                    request_model_type=request_model_type,
                    args=args,
                    kwargs=kwargs,
                    debug_logger=debug_logger,
                )

            except Exception as exc:
                return _handle_errors(
                    exc,
                    debug_logger=debug_logger,
                )

        if inspect.iscoroutinefunction(func):
            return async_wrapper  # Expose async wrapper directly
        else:
            # Create sync adapter that runs async_wrapper in a new event loop
            def _sync_proxy(*args, **kwargs):
                return asyncio.run(async_wrapper(*args, **kwargs))

            functools.update_wrapper(_sync_proxy, func)
            return _sync_proxy

    return decorator


def _validate_and_bind_payload(
    signature: inspect.Signature,
    args: tuple,
    kwargs: dict,
    request_model_type: type[BaseModel],
    debug_logger: DebugLogger,
) -> tuple[inspect.BoundArguments, Any, dict, bool, Optional[dict]]:
    """
    Validates and binds the payload from function arguments.

    Returns:
        Tuple of (bound_args, payload, clean_kwargs, skip_cache, raw_payload_dict).
        raw_payload_dict is the original request as a dict, used to reconstruct partial
        payloads during cache hits without field loss from Pydantic's None defaults.
    """
    ### ------- Deserialize and validate the payload -------

    # Remove these from kwargs before binding:
    # Create a mutable copy to safely separate flags from function arguments.
    clean_kwargs = kwargs.copy()

    # Pop all known decorator flags from the copy.
    skip_validation = clean_kwargs.pop("_skip_validation", False)
    skip_cache = clean_kwargs.pop("_skip_cache", False)

    # Bind the arguments to the function signature
    bound_args = signature.bind(*args, **clean_kwargs)
    bound_args.apply_defaults()

    # Extract `payload` from bound arguments
    raw_payload = bound_args.arguments.get("payload", None)
    # Truncate long fields for debug logging to prevent overwhelming output
    truncated_payload = (
        truncate_for_debug(raw_payload) if debug_logger.enabled else raw_payload
    )
    debug_logger.debug(f"Initial payload: {truncated_payload}")

    # Capture original request dict for cache partial-payload reconstruction.
    # This preserves fields (e.g. smiles on ligands) that would be lost when
    # Pydantic validation adds None defaults and serialize_model strips them.
    raw_payload_dict: Optional[dict] = None
    if isinstance(raw_payload, dict):
        raw_payload_dict = raw_payload
    elif isinstance(raw_payload, str):
        try:
            raw_payload_dict = orjson.loads(raw_payload)
        except orjson.JSONDecodeError:
            raw_payload_dict = None  # validation will raise later
    elif isinstance(raw_payload, request_model_type):
        raw_payload_dict = (
            raw_payload.model_dump()
            if hasattr(raw_payload, "model_dump")
            else raw_payload.dict()
        )

    # Deserialize and validate payload if present
    if not skip_validation:
        if isinstance(raw_payload, str) and raw_payload_dict is not None:
            payload = _validate_payload(raw_payload_dict, request_model_type)
        else:
            payload = _validate_payload(raw_payload, request_model_type)
    else:
        payload = raw_payload  # Assumed to be a valid Pydantic object

    # Truncate long fields for debug logging to prevent overwhelming output
    truncated_payload = truncate_for_debug(payload) if debug_logger.enabled else payload
    debug_logger.debug(f"Deserialized payload: {truncated_payload}")

    # Update the payload in bound arguments
    bound_args.arguments["payload"] = payload
    return bound_args, payload, clean_kwargs, skip_cache, raw_payload_dict


async def _call_function_directly(
    func: Callable,
    bound_args: inspect.BoundArguments,
    debug_logger: DebugLogger,
) -> dict[str, list[Any]]:
    """Call the function directly without caching."""
    ### ------- Function call (skip cache) -------
    debug_logger.debug("Skipping cache logic; calling underlying function directly.")
    if inspect.iscoroutinefunction(func):
        response_obj = await func(*bound_args.args, **bound_args.kwargs)
    else:
        response_obj = func(*bound_args.args, **bound_args.kwargs)

    # Convert the Pydantic response to a dictionary immediately.
    return serialize_model(response_obj, debug_logger)


async def _call_function_with_cache(
    func: Callable,
    payload: Any,
    raw_payload_dict: Optional[dict],
    bound_args: inspect.BoundArguments,
    signature: inspect.Signature,
    request_model_type: type[BaseModel],
    model_slug: str,
    model_action: str,
    debug_logger: DebugLogger,
) -> dict[str, list[Any]]:
    """Call the function with caching enabled."""
    ### ------- Caching logic -------

    # Extract `params` and `items` from the payload
    items = getattr(payload, "items", [])
    params = getattr(payload, "params", None)

    if params:  # Convert params to a dict for hashing
        params = serialize_model(params, debug_logger)

    async def compute_function(items_to_compute: list, indices_to_compute: list[int]):
        """
        This closure correctly reconstructs the function call with a partial payload.
        When raw_payload_dict is available, items are taken from it to preserve
        original request fields (e.g. smiles) that may be missing after validation.
        """
        # Call the underlying function with only the incomplete items
        partial_payload_dict = serialize_model(payload, debug_logger)
        if raw_payload_dict is not None and "items" in raw_payload_dict:
            partial_payload_dict["items"] = [
                raw_payload_dict["items"][i] for i in indices_to_compute
            ]
        else:
            partial_payload_dict["items"] = items_to_compute
        # Validate with Pydantic (uses centralized _validate_payload for v1/v2 compatibility)
        partial_payload = _validate_payload(partial_payload_dict, request_model_type)

        # Make a copy of bound_args, then modify "payload" in place:
        partial_bound_args = signature.bind(*bound_args.args, **bound_args.kwargs)
        partial_bound_args.apply_defaults()
        partial_bound_args.arguments["payload"] = partial_payload

        # Now run the function
        if inspect.iscoroutinefunction(func):
            partial_response_obj = await func(
                *partial_bound_args.args, **partial_bound_args.kwargs
            )
        else:
            partial_response_obj = func(
                *partial_bound_args.args, **partial_bound_args.kwargs
            )
        return partial_response_obj

    complete_response_dict, _ = await process_with_cache(
        items=items,
        params=params,
        model_slug=model_slug,
        model_action=model_action,
        compute_fn=compute_function,
        debug_logger=debug_logger,
    )

    return complete_response_dict


async def _run_main_decorator_flow_async(
    func: Callable,
    model_slug: str,
    model_action: str,
    signature: inspect.Signature,
    request_model_type: type[BaseModel],
    args: tuple,
    kwargs: dict,
    debug_logger: DebugLogger,
) -> dict[str, list[Any]]:
    """
    Executes the main flow for a wrapped Modal function, including:

    1. Parsing the payload and applying Pydantic validation.
    2. Determining model_slug and model_action from the bound class (if any).
    3. Optionally performing cache checks (short-term, fallback R2).
    4. Partially calling the underlying function for cache misses.
    5. Merging cached and newly computed items into a final response.

    Args:
        func: The original function being decorated.
        model_slug: The model slug (e.g., "esm1v-n1").
        model_action: The action name (e.g., "predict").
        signature: The inspected signature of `func`.
        request_model_type: The Pydantic type inferred for the function's `payload` parameter.
        args: Positional arguments passed to `func`.
        kwargs: Keyword arguments passed to `func`.
        debug_logger: A DebugLogCollector instance for capturing debug logs.

    Returns:
        Any: A final response object, typically a dict or Pydantic model.
    """

    bound_args, payload, _clean_kwargs, skip_cache, raw_payload_dict = (
        _validate_and_bind_payload(
            signature, args, kwargs, request_model_type, debug_logger
        )
    )

    # Response caching is OFF unless explicitly enabled (BIOLM_CACHE_ENABLED).
    # When disabled, every request is computed directly — no modal.Dict or R2 access.
    if not cache_enabled():
        skip_cache = True
        debug_logger.debug(
            "Caching disabled (BIOLM_CACHE_ENABLED unset); computing directly."
        )

    # Determine if caching should be skipped
    if model_action in non_cacheable_actions:
        skip_cache = True

    # Auto-skip cache if there are zero items in the payload
    items = getattr(payload, "items", [])
    if items is not None and len(items) == 0:
        skip_cache = True
        debug_logger.debug("Skipping cache: payload has zero items.")

    if skip_cache or not model_slug:
        return await _call_function_directly(func, bound_args, debug_logger)
    else:
        return await _call_function_with_cache(
            func,
            payload,
            raw_payload_dict,
            bound_args,
            signature,
            request_model_type,
            model_slug,
            model_action,
            debug_logger,
        )


def _validate_payload(
    raw_payload: Any, request_model_type: type[BaseModel]
) -> BaseModel:
    """
    Validates and converts an input payload into a Pydantic model instance.
    The payload may be a Pydantic model, a dict, or a JSON string.

    Args:
        raw_payload (Any): The incoming payload to deserialize.
        request_model_type (Type[BaseModel]): The Pydantic model class to validate against.

    Returns:
        BaseModel: An instance of `request_model_type` with the validated data.

    Raises:
        ValidationError: If the payload fails Pydantic validation.
        ValueError: If the payload is an invalid type or a malformed JSON string.
    """
    if isinstance(raw_payload, request_model_type):
        return raw_payload

    if isinstance(raw_payload, str):
        try:
            payload_dict = orjson.loads(raw_payload)
        except orjson.JSONDecodeError as e:
            raise ValueError(f"Failed to deserialize JSON string: {e}") from e
    elif isinstance(raw_payload, dict):
        payload_dict = raw_payload
    else:
        raise ValueError(
            f"Payload must be a JSON string, dictionary, or Pydantic model, got {type(raw_payload)}"
        )

    # Let ValidationError propagate up if it fails
    if hasattr(request_model_type, "model_validate"):
        # Pydantic v2
        return request_model_type.model_validate(payload_dict)
    else:
        # Pydantic v1 fallback
        return request_model_type(**payload_dict)


# Maps an exception type -> (http_status_code, detail_template). The string
# `code` on the structured ErrorResponse is read from the exception's own
# `.code` attribute (BioLMError subclasses), not from this map. Order matters:
# `isinstance` is checked in insertion order, so the specific BioLM user-error
# subclasses MUST precede their `UserError` base.
ERROR_MAP = {
    modal.exception.FunctionTimeoutError: (504, "Modal function timed out"),
    modal.exception.ConnectionError: (503, "Failed to connect to Modal servers"),
    modal.exception.RemoteError: (500, "Remote server error: {exc}"),
    modal.exception.NotFoundError: (404, "Requested resource not found in Modal"),
    ValidationError: (422, "Validation failed for payload"),
    # BioLM user-error hierarchy (specific subclasses before the UserError base).
    ValidationError400: (400, "{exc}"),
    UnsupportedOptionError: (400, "{exc}"),
    ResourceNotFoundError: (404, "{exc}"),
    UserError: (400, "{exc}"),
    # BioLM system-error hierarchy.
    ModelExecutionError: (500, "{exc}"),
}


def _handle_errors(exc, *, debug_logger):
    """
    Concise error handler for the biolm_modal_function decorator.
    """
    for etype, (status_code, tmpl) in ERROR_MAP.items():
        if isinstance(exc, etype):
            # Build base kwargs
            kwargs = {
                "detail_msg": tmpl.format(exc=str(exc)),
                "status_code": status_code,
                # Machine-readable code from BioLMError.code (None otherwise).
                "code": getattr(exc, "code", None),
                "debug_logger": debug_logger,
            }

            # Only ValidationError gets the errors= field
            if isinstance(exc, ValidationError) and hasattr(exc, "errors"):
                kwargs["errors"] = exc.errors()

            return _error_response(**kwargs)

    # Fall-through -> unknown error
    return _error_response(
        detail_msg=f"Uncaught exception: {exc}",
        status_code=500,
        code=getattr(exc, "code", None),
        debug_logger=debug_logger,
        traceback_info=True,
        print_exc=True,
    )


def _error_response(
    detail_msg: str,
    status_code: int,
    debug_logger: DebugLogger,
    code: Optional[str] = None,
    errors: Optional[Any] = None,
    traceback_info: bool = False,
    print_exc: bool = False,
) -> ErrorResponse:
    """
    Builds a structured ErrorResponse and appends optional debug logs/traceback.

    Args:
        detail_msg (str): A top-level detail message describing the error.
        status_code (int): An HTTP-like status code (e.g., 400, 500).
        debug_logger (DebugLogCollector): A logger for capturing debug messages.
        code (Optional[str]): Stable machine-readable error code from the raised
            BioLMError (``None`` for non-BioLM exceptions).
        errors (Optional[Any]): Additional error details, e.g. Pydantic .errors().
        traceback_info (bool): If True, captures traceback.format_exc().
        print_exc (bool): If True and `traceback_info` is True, prints the traceback to logs.

    Returns:
        ErrorResponse: A Pydantic model containing error details, and status code.
    """

    # We'll collect everything in `collected_errors`, which becomes `ErrorResponse.errors`.
    collected_errors = []

    # If the caller has something in `errors` (e.g. pydantic loc/msg info),
    # we incorporate that.
    if errors:
        if isinstance(errors, list):
            collected_errors.extend(errors)
        else:
            # If it's a single dict or string, wrap it
            collected_errors.append(errors)

    if debug_logger.enabled:
        # If we're in debug mode, add debug logs
        collected_errors.extend(debug_logger.get_logs().splitlines())

        # Possibly capture the traceback
        if traceback_info:
            traceback_str = traceback.format_exc()
            collected_errors.append(traceback_str)

            # If we also want the full stack trace in logs for easier debugging
            if print_exc:
                traceback.print_exc()

    error_response = ErrorResponse(
        detail=str(detail_msg),
        errors=collected_errors,
        status_code=status_code,
        code=code,
    )

    return serialize_model(error_response)
