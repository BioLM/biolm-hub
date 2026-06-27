import re

from fastapi import Request, status
from fastapi.responses import JSONResponse


def sanitize_error_message(error_msg: str) -> str:
    """Sanitize error messages to remove sensitive information."""
    # Replace sensitive terms
    sanitized = error_msg.replace("modal", "backend").replace("Modal", "Backend")

    # Remove file paths (anything that looks like /path/to/file)
    sanitized = re.sub(r"/[^\s]+", "<path>", sanitized)

    # Remove stack trace lines
    sanitized = re.sub(r'File "[^"]+", line \d+, in [^\n]+', "<internal>", sanitized)

    # Remove UUIDs and tokens
    sanitized = re.sub(
        r"[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}",
        "<uuid>",
        sanitized,
        flags=re.IGNORECASE,
    )
    sanitized = re.sub(r"[A-Za-z0-9_-]{20,}", "<token>", sanitized)

    # Limit message length
    if len(sanitized) > 200:
        sanitized = sanitized[:200] + "..."

    return sanitized


async def generic_exception_handler(request: Request, exc: Exception):
    """
    Handles all unhandled exceptions and ensures responses are uniform and secure.
    """
    # Log the full exception for internal review (keep sensitive info for debugging)
    print(f"Unhandled exception for request {request.url}: {exc}")

    # Sanitize the error message for end users
    scrubbed_detail = sanitize_error_message(str(exc))

    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": "An unexpected backend error occurred.",
            "detail": scrubbed_detail,
        },
    )
