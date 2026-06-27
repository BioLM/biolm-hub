import hashlib
import os
import time
from decimal import Decimal, InvalidOperation

from gateway.auth_mock import get_mock_introspection_response
from gateway.billing import calculate_execution_cost
from gateway.config import (
    BIOLM_WEB_INTROSPECT_URL,
    internal_django_modal_auth_token_env_key,
)
from gateway.model_discovery import get_model_mapper
from gateway.schemas.introspection import IntrospectionResponse
from gateway.shared_state import passport_cache, user_usage_manager


def _hash_token(token: str) -> str:
    """Hash token for secure storage using SHA-256."""
    return hashlib.sha256(token.encode()).hexdigest()


class PassportAuthenticationMiddleware:
    """
    Middleware for authenticating requests, managing local quota and billing state.

    This middleware performs real-time validation of a user's permissions, API
    request quotas, and monetary spending limits before executing a model. It
    calls the `/introspect` endpoint to fetch the user's state and caches it
    locally for a short TTL period to perform instant, subsequent checks.
    """

    def __init__(self, app):
        self.app = app
        self.auth_token = os.environ.get(internal_django_modal_auth_token_env_key)

    async def _fetch_and_cache_passport(
        self, token: str, hashed_token: str
    ) -> IntrospectionResponse | None:
        """Fetches passport from the introspect endpoint and updates the cache."""
        import httpx

        if BIOLM_WEB_INTROSPECT_URL == "MOCK":
            passport = get_mock_introspection_response(token)
        else:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    BIOLM_WEB_INTROSPECT_URL,
                    json={"token": token},
                    headers={"X-Internal-Auth": self.auth_token},
                )
            if response.status_code != 200:
                return None
            passport = IntrospectionResponse.model_validate(response.json())

        # Cache the fresh passport
        passport_cache[hashed_token] = {
            "passport": passport.model_dump(),
            "timestamp": time.time(),
        }
        return passport

    async def _validate_limit_with_recheck(
        self,
        token: str,
        hashed_token: str,
        passport: IntrospectionResponse,
        limit_name: str,
        current_usage: Decimal,
        original_limit: Decimal,
        cost_to_add: Decimal,
        get_fresh_limit_fn,
    ):
        """Generic helper to check a limit, re-fetch passport, and re-check."""
        from fastapi import HTTPException

        if (current_usage + cost_to_add) > original_limit:
            # First check failed, try with fresh data
            fresh_passport = await self._fetch_and_cache_passport(token, hashed_token)
            if fresh_passport:
                # Re-check with the new limit from fresh passport
                new_limit = get_fresh_limit_fn(fresh_passport)
                if (current_usage + cost_to_add) > new_limit:
                    raise HTTPException(
                        status_code=429, detail=f"{limit_name} limit reached."
                    )
                return fresh_passport  # Return updated passport for subsequent checks
            else:
                # Introspect failed, so rely on the original check
                raise HTTPException(
                    status_code=429, detail=f"{limit_name} limit reached."
                )
        return passport  # No limit exceeded, return original passport

    async def __call__(self, scope, receive, send):
        """ASGI callable that implements the middleware pattern."""
        from starlette.middleware.base import BaseHTTPMiddleware

        middleware = BaseHTTPMiddleware(self.app)
        middleware.dispatch = self._dispatch
        return await middleware(scope, receive, send)

    async def _dispatch(self, request, call_next):  # noqa: C901
        # FIXME(noqa: C901): Refactor to reduce complexity below the linter's threshold.
        """Main middleware logic for passport authentication and validation."""
        from fastapi import HTTPException

        # Skip authentication for public endpoints
        path = request.url.path
        public_endpoints = [
            "/",  # Health check
            "/resource-specs",  # Public resource info
            "/catalog",  # Public model catalog
            "/docs",  # API documentation
            "/openapi.json",  # OpenAPI spec
            "/redoc",  # Alternative docs
        ]

        # Check for exact matches and prefix matches for catalog sub-pages
        if path in public_endpoints or path.startswith("/catalog/"):
            # Set empty passport for public endpoints to prevent downstream errors
            request.state.passport = None
            request.state.token = None
            return await call_next(request)

        token = request.headers.get("Authorization")
        if not token:
            raise HTTPException(status_code=401, detail="Authorization header missing")

        # Hash token for secure storage and lookup
        hashed_token = _hash_token(token)

        # 1. Check Cache for non-expired passport
        cached_data = passport_cache.get(hashed_token)
        passport: IntrospectionResponse | None = None
        if cached_data:
            fetch_time = cached_data.get("timestamp", 0)
            ttl = cached_data.get("passport", {}).get("cache_ttl_seconds", 30)
            if time.time() - fetch_time < ttl:
                passport = IntrospectionResponse.model_validate(cached_data["passport"])

        # 2. If not cached or expired, call /introspect
        if not passport:
            passport = await self._fetch_and_cache_passport(token, hashed_token)
            if not passport:
                raise HTTPException(
                    status_code=401, detail="Failed to authenticate token"
                )

            # Reset usage state in StateManagedDict with fresh passport data
            if passport.user and passport.user.id:
                # Queue a force_set operation to reset usage counters based on fresh passport data
                try:
                    initial_state = {
                        "monthly_requests": passport.usage_state.monthly_api_requests.current,
                        "lifetime_requests": passport.usage_state.lifetime_api_requests.current,
                        "monthly_charges": str(
                            passport.billing_state.monthly_charges.current
                        ),
                        "lifetime_charges": str(
                            passport.billing_state.lifetime_charges.current
                        ),
                    }
                    user_usage_manager.force_set(hashed_token, initial_state)
                except (KeyError, TypeError) as e:
                    print(f"Warning: Could not reset usage state from passport: {e}")
                    # Use safe defaults if passport data is malformed
                    user_usage_manager.force_set(
                        hashed_token,
                        {
                            "monthly_requests": "0",
                            "lifetime_requests": "0",
                            "monthly_charges": "0.0",
                            "lifetime_charges": "0.0",
                        },
                    )

        # Attach passport and hashed token to request state for downstream use
        request.state.passport = passport
        request.state.token = (
            hashed_token  # Hashed token for StateManagedDict operations
        )

        # 3. Perform Pre-Flight Validation
        # A. Check for Hard Blocks
        if not passport.token_is_valid:
            raise HTTPException(status_code=401, detail="Invalid authentication token.")

        if passport.policy.bypass_billing:
            return await call_next(request)  # Skip all checks

        if not passport.authorization.can_access_api:
            raise HTTPException(
                status_code=403,
                detail=passport.authorization.reason,
            )

        if passport.policy.payment_past_due_or_canceled:
            raise HTTPException(status_code=403, detail="Payment is past due.")

        # TODO: Implement check for private/personal models in the future.
        # For now, all models are considered public.
        #
        # model_slug = request.path_params.get("model_slug")
        # allowed_models = passport.get("allowed_models", [])
        # if model_slug not in allowed_models:
        #     raise HTTPException(
        #         status_code=403,
        #         detail=f"Access to model '{model_slug}' is not permitted.",
        #     )

        # B. Estimate Request Cost
        model_slug = request.path_params.get("model_slug")
        model_mapper = get_model_mapper()
        if not model_mapper.get_variant_info(model_slug):
            raise HTTPException(
                status_code=404, detail=f"Unknown API model slug: {model_slug}"
            )

        # Generous low estimates to be lenient to users
        # These are optimistic estimates that allow more requests through pre-flight checks
        estimated_seconds = Decimal("5.0")  # Default conservative estimate

        try:
            estimated_cost = calculate_execution_cost(model_slug, estimated_seconds)
        except ValueError as e:
            raise HTTPException(
                status_code=500, detail=f"Cost estimation error: {e}"
            ) from e

        request.state.estimated_cost = estimated_cost

        # C. Check Limits against Shared Usage State

        # TODO: Test if Modal Dict/Queue supports Decimal directly to avoid conversion
        # Modal docs say dicts/queues support anything serializable by orjson
        # Convert string values from Modal Dict to Decimal for calculations
        user_counters = user_usage_manager.get(
            hashed_token,
            default={
                "monthly_requests": Decimal("0"),
                "lifetime_requests": Decimal("0"),
                "monthly_charges": Decimal("0.0"),
                "lifetime_charges": Decimal("0.0"),
            },
        )

        # Request Quotas
        passport = await self._validate_limit_with_recheck(
            token,
            hashed_token,
            passport,
            "Monthly request",
            user_counters["monthly_requests"],
            passport.usage_state.monthly_api_requests.limit,
            Decimal("1"),
            lambda p: p.usage_state.monthly_api_requests.limit,
        )
        passport = await self._validate_limit_with_recheck(
            token,
            hashed_token,
            passport,
            "Lifetime request",
            user_counters["lifetime_requests"],
            passport.usage_state.lifetime_api_requests.limit,
            Decimal("1"),
            lambda p: p.usage_state.lifetime_api_requests.limit,
        )

        # Billing Quotas
        try:
            monthly_charge_limit = Decimal(passport.billing_state.monthly_charges.limit)
            lifetime_charge_limit = Decimal(
                passport.billing_state.lifetime_charges.limit
            )

            passport = await self._validate_limit_with_recheck(
                token,
                hashed_token,
                passport,
                "Monthly spending",
                user_counters["monthly_charges"],
                monthly_charge_limit,
                estimated_cost,
                lambda p: Decimal(p.billing_state.monthly_charges.limit),
            )
            passport = await self._validate_limit_with_recheck(
                token,
                hashed_token,
                passport,
                "Lifetime spending",
                user_counters["lifetime_charges"],
                lifetime_charge_limit,
                estimated_cost,
                lambda p: Decimal(p.billing_state.lifetime_charges.limit),
            )
        except (InvalidOperation, KeyError) as e:
            raise HTTPException(
                status_code=500, detail=f"Invalid billing state format: {e}"
            ) from e

        # 4. Process the Request
        # The actual incrementing of local counters will happen in the main app
        # logic after the request is processed and we have the final cost.
        response = await call_next(request)

        # TODO: Move the local state update logic here from app.py
        # This would be a better place for it, but for now we do it in app.py
        # to have access to the final execution time.

        return response
