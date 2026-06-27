import os
import uuid

from gateway.config import (
    BIOLM_WEB_USAGE_EVENT_URL,
    internal_django_modal_auth_token_env_key,
    moesif_applicatio_id_env_key,
)


class AnalyticsPublisher:
    """Publisher for sending analytics events to Django HTTP endpoint.

    This class handles publishing usage analytics events to the Django service's
    /api/internal/v1/usage-event endpoint for tracking user activity, model performance
    metrics, billing data, and operational insights.
    """

    def __init__(self):
        self.usage_event_url = BIOLM_WEB_USAGE_EVENT_URL
        self.auth_token = os.environ.get(internal_django_modal_auth_token_env_key)

    async def publish_usage_event(
        self,
        user_id: str,
        model_slug: str,
        model_action: str,
        execution_seconds: float,
        cached_items: int,
        backend_items: int,
        hardware_spec_name: str,
    ):
        """Publish a usage analytics event to the Django HTTP endpoint.

        Args:
            user_id: ID of the user making the request.
            model_slug: The model being used.
            model_action: The action being performed.
            execution_seconds: Time spent executing the request.
            cached_items: Number of items served from cache.
            backend_items: Number of items computed by the backend.
            hardware_spec_name: Hardware specification used.
        """
        if self.usage_event_url == "MOCK":
            print(
                f"MOCK: Would send usage event for user {user_id}, model {model_slug}, action {model_action}"
            )
            return

        if not self.auth_token:
            print(
                f"WARNING: {internal_django_modal_auth_token_env_key} not set. Analytics event not sent."
            )
            return

        try:
            # Import httpx within Modal container scope
            import httpx

            payload = {
                "user_id": user_id,
                "hardware_spec_name": hardware_spec_name,
                "execution_seconds": execution_seconds,
                "model_slug": model_slug,
                "model_action": model_action,
                "transaction_id": str(uuid.uuid4()),
                "cached_items": cached_items,
                "backend_items": backend_items,
            }

            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    self.usage_event_url,
                    json=payload,
                    headers={"X-Internal-Auth": self.auth_token},
                )

            if response.status_code == 202:
                print(f"Usage event sent successfully for user {user_id}")
            else:
                print(
                    f"Failed to send usage event. Status: {response.status_code}, Response: {response.text}"
                )

        except Exception as e:
            print(f"Failed to publish analytics event: {e}")


# MOESIF ANALYTICS CONFIGURATION


def get_user_id(req, res):
    """Extract user ID from request passport for Moesif analytics."""
    try:
        return req.state.passport["user"]["username"]
    except (AttributeError, KeyError):
        return None


def get_company_id(req, res):
    """Extract company ID from request passport for Moesif analytics."""
    try:
        return req.state.passport["user"]["company_id"]
    except (AttributeError, KeyError):
        return None


def get_metadata(req, res):
    """Extract available metadata from request passport for Moesif analytics."""
    try:
        metadata = {
            "username": req.state.passport["user"]["username"],
        }
        # Only add the policy if it exists in the passport
        if "policy" in req.state.passport:
            metadata["policy"] = req.state.passport["policy"]
        return metadata
    except (AttributeError, KeyError):
        return None


def skip_moesif_event(req, res):
    """Determine whether to skip logging this event to Moesif.

    Adapted from the external service logic to match our gateway paths.
    """
    try:
        path = req.url.path

        # Skip superuser requests (if we implement superuser functionality)
        try:
            if req.state.passport.get("user", {}).get("is_superuser", False):
                return True
        except (AttributeError, KeyError):
            pass

        # Path-based filtering adapted for our gateway
        if "/console/" in path:
            return True
        elif (
            path.startswith("/api/v1/")
            or path.startswith("/api/v2/")
            or path.startswith("/api/v3/")
        ):
            return False  # Don't skip API calls - we want to log these
        elif path.startswith("/wss") or path.startswith("/ws"):
            return True  # Skip websocket connections
        elif path == "/" or path == "":
            return True  # Skip root path health checks
        elif "favicon.ico" in path:
            return True
        elif (
            path.startswith("/health")
            or path.startswith("/docs")
            or path.startswith("/openapi")
        ):
            return True  # Skip FastAPI built-in endpoints
        else:
            return False  # Log everything else by default

    except Exception as e:
        print(f"Error in skip_moesif_event: {e}")
        return False  # Default to logging if there's an error


def mask_sensitive_info(data, keys_to_mask):
    """Helper function to mask sensitive data in nested dictionaries."""
    if not isinstance(data, dict):
        return

    for key in keys_to_mask:
        if key in data:
            data[key] = "****"
        try:
            # Handle items array (common in our API requests)
            for i, item in enumerate(data.get("items", [])):
                if isinstance(item, dict) and key in item:
                    data["items"][i][key] = "****"
        except Exception as e:
            print(f"Error masking items for Moesif: {str(e)}")


def _mask_request_body_special_cases(request_body):
    """Handle special nested structure masking in request bodies."""
    # Handle instances array (legacy structure)
    if "instances" in request_body:
        for item in request_body["instances"]:
            if "data" in item and "text" in item["data"]:
                item["data"]["text"] = "****"


def _mask_headers(headers, headers_to_mask):
    """Mask sensitive headers in different case formats."""
    for header in headers_to_mask:
        for case_variant in [header, header.lower(), header.upper()]:
            if case_variant in headers:
                headers[case_variant] = "****"


def mask_moesif_event(eventmodel):
    """Mask sensitive data in Moesif events before sending.

    Adapted from the external service to match our API structure.
    """
    # Define sensitive fields to mask
    request_keys_to_mask = [
        "password",
        "content_str",
        "context",
        "prompt",
        "prompt_str",
        "fasta",
        "fasta_str",
        "fasta_string",
        "sequence",
        "pdb",
        "pdbs",
        "pdb_str",
        "pdb_string",
        "text",
        "input",
        "query",
    ]
    response_keys_to_mask = [
        "access",
        "refresh",
        "predictions",
        "results",
        "sequence",
        "embeddings",
        "output",
        "generated_text",
    ]
    headers_to_mask = ["Authorization", "Cookie", "Bearer", "X-Internal-Auth"]

    # Mask request body
    if eventmodel.request.body:
        mask_sensitive_info(eventmodel.request.body, request_keys_to_mask)
        _mask_request_body_special_cases(eventmodel.request.body)

    # Mask response body
    if eventmodel.response.body:
        mask_sensitive_info(eventmodel.response.body, response_keys_to_mask)

    # Mask sensitive headers
    _mask_headers(eventmodel.request.headers, headers_to_mask)

    return eventmodel


def get_moesif_options():
    MOESIF_APPLICATION_ID = os.environ.get(moesif_applicatio_id_env_key)

    # Moesif configuration for analytics middleware
    moesif_options = {
        "APPLICATION_ID": MOESIF_APPLICATION_ID,
        "CAPTURE_OUTGOING_REQUESTS": False,
        # Using modern recommended keys (cleaner than legacy GET_* keys)
        "IDENTIFY_USER": get_user_id,
        "IDENTIFY_COMPANY": get_company_id,
        "GET_METADATA": get_metadata,  # This key is still current
        "SKIP": skip_moesif_event,
        "MASK_EVENT_MODEL": mask_moesif_event,
        "LOCAL_DEBUG": False,
        # Disable logging entirely if Application ID is missing
        "DISABLE_TRANSACTION_LOGGING": not MOESIF_APPLICATION_ID,
    }

    return moesif_options
