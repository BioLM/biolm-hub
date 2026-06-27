import logging
import time
from decimal import Decimal
from functools import lru_cache

import modal
from pydantic import BaseModel

from gateway.analytics import AnalyticsPublisher, get_moesif_options
from gateway.auth import PassportAuthenticationMiddleware
from gateway.billing import calculate_execution_cost, get_hardware_spec_name
from gateway.config import (
    django_modal_secret,
    get_cors_allowed_origins,
    get_custom_domain,
    local_gateway_path,
    remote_gateway_path,
    validate_required_config,
)
from gateway.middleware import generic_exception_handler
from gateway.model_discovery import get_model_mapper
from gateway.shared_state import user_usage_manager
from models.commons.core.caching import non_cacheable_actions, process_with_cache
from models.commons.core.logging import DebugLogger
from models.commons.data.serializer import serialize_model
from models.commons.util.config import (
    cloudflare_r2_secret,
    common_requirements,
    local_models_path,
    remote_models_path,
)

logger = logging.getLogger(__name__)

image = (
    modal.Image.debian_slim(python_version="3.12")
    .uv_pip_install(common_requirements)
    .uv_pip_install(
        "fastapi[standard]==0.112.0",
        "moesifasgi",
        "httpx",
        "decimal",
    )
    .add_local_dir(local_models_path, remote_models_path, copy=True)
    .add_local_dir(local_gateway_path, remote_gateway_path, copy=True)
)

app = modal.App("biolm-gateway", image=image)


# --- Background Worker for State Management ---
@app.function(
    cpu=0.125,  # Smallest fractional CPU for cost efficiency
    memory=256,  # Minimal memory for simple queue processing
    concurrency_limit=1,  # Critical: ensures no race conditions
    keep_warm=1,  # Always keep one container warm
    timeout=60 * 60,  # 1 hour timeout, but should run indefinitely
)
def persistent_usage_state_updater():
    """
    Persistent background worker that continuously processes the usage update queue.
    This ensures atomic updates to the shared usage state dictionary.

    The function runs in an infinite loop, processing queue events as they arrive.
    With concurrency_limit=1, only one instance runs globally, preventing race conditions.
    """
    print("Starting persistent usage state updater...")

    while True:
        try:
            # Process any available events from the queue
            processed_count = user_usage_manager.run_processor_once(timeout=5.0)

            if processed_count > 0:
                print(f"Processed {processed_count} usage update events")

            # Brief pause to prevent excessive CPU usage when queue is empty
            time.sleep(0.1)

        except Exception as e:
            print(f"ERROR in usage state updater: {e}")
            time.sleep(1.0)  # Back off more on errors


@lru_cache(maxsize=256)
def get_user_modal_class(model_slug, app_username):
    """Get cached user-specific modal class instance"""
    model_mapper = get_model_mapper()

    class_name = model_mapper.get_class_name(model_slug)
    if not class_name:
        raise ValueError(f"No class found for model_slug: {model_slug}")

    try:
        return modal.Cls.from_name(model_slug, class_name)(app_username=app_username)
    except Exception as e:
        error_msg = str(e).lower()

        if "not found" in error_msg or "does not exist" in error_msg:
            raise ValueError(
                f"Modal app '{model_slug}' not found. Please ensure the model is deployed."
            ) from e
        elif (
            "unreachable" in error_msg
            or "connection" in error_msg
            or "timeout" in error_msg
        ):
            raise ValueError(
                f"Modal app '{model_slug}' is temporarily unreachable. Please try again later."
            ) from e
        else:
            raise ValueError(
                f"Failed to instantiate Modal class for '{model_slug}': {e}"
            ) from e


@app.function(
    secrets=[django_modal_secret, cloudflare_r2_secret],
    enable_memory_snapshot=True,
    cpu=0.125,
    memory=512,
    # keep_warm=1,
    scaledown_window=15,  # Keep containers warm for 15 sec
    max_containers=50,
    timeout=60 * 60,  # 1 hour
)
@modal.concurrent(max_inputs=100)
@modal.asgi_app(custom_domains=[get_custom_domain()])
def gateway():  # noqa: C901
    # FIXME(noqa: C901): Refactor to reduce complexity below the linter's threshold.
    """
    Initializes and configures the FastAPI application.

    This function serves as the ASGI entrypoint for the Modal web service, running
    once when a new container starts.
    """
    # FastAPI imports (Modal container scope)
    from fastapi import BackgroundTasks, FastAPI, HTTPException, Request
    from fastapi.middleware.cors import CORSMiddleware
    from fastapi.middleware.gzip import GZipMiddleware
    from moesifasgi.middleware import MoesifMiddleware

    # Rate limiting imports (Modal container scope)
    from slowapi import Limiter, _rate_limit_exceeded_handler
    from slowapi.errors import RateLimitExceeded
    from slowapi.util import get_remote_address

    # Validate environment variable configs on import
    validate_required_config()

    # Rate limiting setup (Modal container scope)
    def get_rate_limit_key(request):
        """Extract user ID from passport for rate limiting, fallback to IP address."""
        try:
            # Try to get user ID from passport (set by auth middleware)
            if hasattr(request.state, "passport") and request.state.passport:
                return request.state.passport["user"]["id"]
            else:
                # Public endpoints or missing passport - use IP address
                return get_remote_address(request)
        except (AttributeError, KeyError, TypeError):
            # Fallback to IP address for any errors
            return get_remote_address(request)

    limiter = Limiter(key_func=get_rate_limit_key)

    # Initialize model mapper system
    model_mapper = get_model_mapper()

    # Create the FastAPI application instance
    fastapi_app = FastAPI(
        title="BioLM v3 API",
        description="A unified gateway for the BioLM biological machine learning models suite.",
        version="3.0.0",
        redirect_slashes=True,
        # swagger_ui_parameters={"defaultModelsExpandDepth": -1},
        contact={
            "name": "BioLM Support",
            "email": "support@biolm.ai",
        },
    )

    # --- Rate Limiter ---
    fastapi_app.state.limiter = limiter
    fastapi_app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

    # --- Middleware Configuration ---
    # CRITICAL: Order matters! Middleware executes in REVERSE order of addition
    # Last added = First executed
    fastapi_app.add_middleware(GZipMiddleware, minimum_size=1000)
    fastapi_app.add_middleware(
        CORSMiddleware,
        allow_origins=get_cors_allowed_origins(),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    # Moesif AFTER Auth so it can access request.state.passport
    fastapi_app.add_middleware(MoesifMiddleware, get_moesif_options())
    # Auth middleware populates request.state.passport
    fastapi_app.add_middleware(PassportAuthenticationMiddleware)

    # --- Exception Handlers ---
    fastapi_app.exception_handler(Exception)(generic_exception_handler)

    # --- Billing Publisher ---
    analytics_publisher = AnalyticsPublisher()

    @fastapi_app.get("/", tags=["Health"])
    async def health_check():
        """Confirms that the gateway is running."""
        response = {
            "status": "ok",
            "message": "BioLM Gateway is running",
            "supported_models": model_mapper.get_all_registered_models(),
        }
        return response

    @fastapi_app.get("/resource-specs", tags=["Gateway"])
    async def resource_specs(force: bool = False):
        """Returns the resource specifications for all models."""
        return model_mapper.get_all_resource_specs()

    # --- Generic Request Handling Logic ---

    def _finalize_request_and_report_usage(
        start_time: float,
        was_successful: bool,
        execution_started: bool,
        model_slug: str,
        token: str,
        items: list,
        cached_items: int,
        user_id: str,
        model_action: str,
        hardware_spec_name: str,
        background_tasks,
        analytics_publisher,
    ):
        """Finalize request costs and report usage analytics."""
        execution_seconds = time.time() - start_time

        # Calculate cost based on failure type:
        # - Pre-flight failures (before execution_started): zero cost
        # - Execution failures (after execution_started): actual cost for time elapsed
        # - Successful requests: actual cost for time elapsed
        if not execution_started:
            # Pre-flight failure (validation, permissions, etc.) - zero cost
            final_cost = Decimal("0")
        else:
            # Execution started - charge for time elapsed regardless of success/failure
            try:
                final_cost = calculate_execution_cost(
                    model_slug, Decimal(str(execution_seconds))
                )
            except ValueError as e:
                logger.warning("Cost calculation failed for %s: %s", model_slug, e)
                final_cost = Decimal("0")  # Fallback to zero cost on calculation errors

        # Queue usage updates to shared state management
        # Only count successful requests, but always track charges
        usage_update = {
            "monthly_requests": 1 if was_successful else 0,
            "lifetime_requests": 1 if was_successful else 0,
            "monthly_charges": str(final_cost),
            "lifetime_charges": str(final_cost),
        }
        user_usage_manager.update(token, usage_update)

        # Report usage to backend
        backend_items = len(items) - cached_items
        background_tasks.add_task(
            analytics_publisher.publish_usage_event,
            user_id=user_id,
            model_slug=model_slug,
            model_action=model_action,
            execution_seconds=execution_seconds,
            cached_items=cached_items,
            backend_items=backend_items,
            hardware_spec_name=hardware_spec_name,
        )

    def _prepare_request_context(request, model_slug: str, model_action: str):
        """Prepare initial request context and validate model/action."""
        from fastapi import HTTPException

        start_time = time.time()
        user_id = request.state.passport["user"]["id"]
        token = request.state.token  # Hashed token for StateManagedDict operations

        # Initialize variables that finally block needs (in case of early exceptions)
        items = []
        cached_items = 0
        was_successful = False  # Track if request completed successfully
        execution_started = False  # Track if we reached actual model execution
        final_response_dict = (
            None  # Initialize final_response_dict to prevent NameError in error paths
        )

        # 1. Resolve API model_slug using model mapper
        variant_info = model_mapper.get_variant_info(model_slug)
        if not variant_info:
            raise HTTPException(
                status_code=404, detail=f"Unknown API model slug: {model_slug}"
            )

        base_model_slug = variant_info["base_model_slug"]

        # Get hardware spec name for usage events (matches MODAL_RESOURCE_BASE_COSTS keys)
        hardware_spec_name = get_hardware_spec_name(model_slug)

        # 2. Look up the schema and class name from model mapper
        RequestSchema, ResponseSchema = model_mapper.get_action_schemas(
            base_model_slug, model_action
        )
        ModelClassName = model_mapper.get_class_name(base_model_slug)

        # Validate that discovery lookup was successful
        if not RequestSchema or not ResponseSchema or not ModelClassName:
            # Check what's available for debugging
            available_models = model_mapper.get_all_registered_models()
            available_actions = [
                action
                for action, _, _ in model_mapper.get_all_actions_for_model(
                    base_model_slug
                )
            ]

            if base_model_slug not in available_models:
                raise HTTPException(
                    status_code=404,
                    detail=f"Model '{base_model_slug}' not found. Available models: {sorted(available_models)}",
                )
            else:
                raise HTTPException(
                    status_code=404,
                    detail=f"Action '{model_action}' not found for model '{base_model_slug}'. Available actions: {sorted(available_actions)}",
                )

        return (
            start_time,
            user_id,
            token,
            items,
            cached_items,
            was_successful,
            execution_started,
            final_response_dict,
            base_model_slug,
            hardware_spec_name,
            RequestSchema,
            ResponseSchema,
            ModelClassName,
        )

    async def generic_request_handler(  # noqa: C901
        model_slug: str,
        model_action: str,
        payload: BaseModel,  # Payload is now a validated Pydantic model
        request: Request,
        background_tasks: BackgroundTasks,
    ):
        # FIXME(noqa: C901): Refactor to reduce complexity below the linter's threshold.
        """
        This is the core logic that handles a validated and parsed request.
        It is called by the dynamically generated endpoints.

        NOTE ON TIMEOUTS: This endpoint uses a direct request-response model.
        While the Modal function timeout can be set high, upstream services
        (e.g., Cloudflare, AWS load balancers) typically have short timeouts
        (1-2 minutes). For models that run longer than this, the connection
        may be dropped. The robust, long-term solution for such jobs is an
        asynchronous pattern using `.spawn()` and a separate results
        endpoint, which can be implemented in a future iteration. Consider
        implementing this as a separate endpoint /api/v3/{model}/{action}/async
        """
        (
            start_time,
            user_id,
            token,
            items,
            cached_items,
            was_successful,
            execution_started,
            final_response_dict,
            base_model_slug,
            hardware_spec_name,
            RequestSchema,
            ResponseSchema,
            ModelClassName,
        ) = _prepare_request_context(request, model_slug, model_action)

        # 3. Process request (with caching)
        try:
            # Mark that we've started execution (past validation/pre-flight checks)
            execution_started = True

            # Extract username for billing purposes
            # biolm_web provides app_username in composite format: user_id:company_id:environment_id
            user_data = request.state.passport["user"]
            username = user_data.get("username")

            # If username is not in composite format, construct it from available data
            # Composite format: user_id:company_id:environment_id (e.g., "1:2:3")
            if not username or ":" not in str(username):
                user_id = user_data.get("id")
                # Use company_id (fallback to institute_id for backwards compat, then 0)
                company_id = (
                    user_data.get("company_id") or user_data.get("institute_id") or 0
                )
                environment_id = user_data.get("environment_id", 0)

                # Construct composite username if not already provided
                if user_id:
                    username = f"{user_id}:{company_id}:{environment_id}"
                else:
                    # Fallback to simple username if no user_id available
                    username = user_data.get("username", "default_user")
                    logger.warning(
                        "Could not construct composite username, using: %s",
                        username,
                    )

            if model_action in non_cacheable_actions:
                final_response_dict = await compute_remotely(
                    payload, model_slug, ModelClassName, model_action, username
                )
                items = getattr(payload, "items", [])
                cached_items = 0
            else:
                items = getattr(payload, "items", [])
                params = getattr(payload, "params", None)
                params_dict = serialize_model(params) if params else None

                # Capture full items (with None defaults) outside closure to avoid
                # re-calling model_dump() on every partial-cache invocation.
                full_items = payload.model_dump().get("items", [])

                async def compute_function(
                    items_to_compute: list, indices_to_compute: list[int]
                ):
                    partial_payload_dict = serialize_model(payload)
                    # Use full_items indexed by original position to preserve
                    # field structure (e.g. smiles on ligands) that serialize_model's
                    # exclude_none=True would strip after Pydantic populates None defaults.
                    partial_payload_dict["items"] = [
                        full_items[i] for i in indices_to_compute
                    ]
                    partial_payload = RequestSchema.model_validate(partial_payload_dict)
                    result_dict = await compute_remotely(
                        partial_payload,
                        model_slug,
                        ModelClassName,
                        model_action,
                        username,
                    )
                    return ResponseSchema.model_validate(result_dict)

                debug_logger = DebugLogger(
                    enabled=False,
                    extra_context={
                        "model_slug": model_slug,
                        "model_action": model_action,
                    },
                )
                final_response_dict, computed_item_count = await process_with_cache(
                    items=items,
                    params=params_dict,
                    model_slug=model_slug,
                    model_action=model_action,
                    compute_fn=compute_function,
                    debug_logger=debug_logger,
                )

                cached_items = len(items) - computed_item_count

            # Validate result structure
            if (
                not isinstance(final_response_dict, dict)
                or "results" not in final_response_dict
            ):
                raise ValueError(f"Invalid result structure from {model_action}")

            # Mark success only if we reach the end of the try block
            was_successful = True

        finally:
            # 4. Post-flight: Update local state and report usage
            _finalize_request_and_report_usage(
                start_time,
                was_successful,
                execution_started,
                model_slug,
                token,
                items,
                cached_items,
                user_id,
                model_action,
                hardware_spec_name,
                background_tasks,
                analytics_publisher,
            )

        # Ensure we always return a valid final_response_dict
        if final_response_dict is None:
            # This should only happen if there was an exception before final_response_dict was set
            raise HTTPException(
                status_code=500, detail="Request processing failed before completion"
            )
        return final_response_dict

    async def compute_remotely(
        payload: BaseModel,
        model_slug: str,
        model_class_name: str,
        model_action: str,
        username: str,
    ) -> dict:
        """Helper function to dispatch the call to the remote Modal app."""
        try:
            model_instance = get_user_modal_class(model_slug, username)
            remote_function = getattr(model_instance, model_action)

            # Call the remote model, telling it to skip both validation and caching
            return await remote_function.remote.aio(
                payload=payload, _skip_validation=True, _skip_cache=True
            )
        except modal.exception.NotFoundError as e:
            raise HTTPException(
                status_code=404,
                detail=f"Deployed Modal App '{model_slug}' not found.",
            ) from e
        except Exception as e:
            raise RuntimeError(f"Error during model execution: {e}") from e

    # --- Generate routes dynamically based on model mapper ---
    print("Generating API routes...")

    variant_map = model_mapper.get_all_variant_mappings()
    for model_slug, variant_info in variant_map.items():
        base_model_slug = variant_info["base_model_slug"]

        for _action, _req_schema, _res_schema in model_mapper.get_all_actions_for_model(
            base_model_slug
        ):
            # Create endpoint handler with proper closure to capture variables
            # Note: We use a factory function to avoid Python's late binding gotcha
            def make_endpoint_handler(
                captured_slug: str, captured_action: str, captured_schema
            ):
                @limiter.limit(
                    "100/minute"
                )  # Default rate limit for all authenticated endpoints
                async def endpoint_handler(
                    payload: captured_schema,
                    request: Request,
                    background_tasks: BackgroundTasks,
                ):
                    return await generic_request_handler(
                        captured_slug,
                        captured_action,
                        payload,
                        request,
                        background_tasks,
                    )

                # Set a unique name to avoid FastAPI conflicts
                endpoint_handler.__name__ = (
                    f"handle_{captured_slug.replace('-', '_')}_{captured_action}"
                )
                return endpoint_handler

            # Create the actual endpoint handler
            handler = make_endpoint_handler(model_slug, _action, _req_schema)

            # Register the route with FastAPI
            fastapi_app.add_api_route(
                path=f"/api/v3/{model_slug}/{_action}",
                endpoint=handler,
                methods=["POST"],
                response_model=_res_schema,
                tags=[base_model_slug],
                summary=f"Run {_action} on {variant_info.get('display_name', model_slug)}",
            )
            print(f"  -> Created endpoint for: /api/v3/{model_slug}/{_action}")

    # --- Add interactive catalog ---
    from fastapi.staticfiles import StaticFiles
    from starlette.requests import Request
    from starlette.templating import Jinja2Templates

    from gateway.catalog.generator import generate_catalog_data, group_models_by_base

    fastapi_app.mount(
        "/static", StaticFiles(directory="gateway/catalog/static"), name="static"
    )
    templates = Jinja2Templates(directory="gateway/catalog/templates")
    catalog_data = generate_catalog_data(fastapi_app)

    @fastapi_app.get("/catalog", include_in_schema=False)
    async def get_catalog(request: Request):
        grouped_catalog = group_models_by_base(catalog_data)
        return templates.TemplateResponse(
            "catalog.html",
            {
                "request": request,
                "catalog": catalog_data,
                "grouped_catalog": grouped_catalog,
            },
        )

    @fastapi_app.get("/catalog/{model_slug}", include_in_schema=False)
    async def get_model_catalog(request: Request, model_slug: str):
        if model_slug not in catalog_data:
            raise HTTPException(status_code=404, detail="Model not found")
        return templates.TemplateResponse(
            "model.html", {"request": request, "model_info": catalog_data[model_slug]}
        )

    return fastapi_app
