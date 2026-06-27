from typing import Any, Optional, Union

from pydantic import BaseModel


class BioLMError(Exception):
    """
    Base class for every BioLM-raised exception.

    Carries a stable, machine-readable ``code`` (dotted ``"<domain>.<reason>"``
    string) that the ``modal_endpoint()`` decorator surfaces on the structured
    ``ErrorResponse``. Subclasses split into a user-facing branch (caller
    mistakes, surfaced verbatim) and a system branch (internal failures,
    sanitized to 5xx by the gateway).
    """

    code: Optional[str] = None


class UserError(BioLMError):
    """
    A custom exception for user-facing errors in model-related workflows.

    Raised to communicate predictable or user-related failures, such as invalid
    input data or disallowed operations. Handled in the decorator to return a
    structured error response with a clear message.

    This exception is handled explicitly in the `modal_endpoint()` decorator
    to ensure that the error message is returned to the user in a structured format.

    Example:
        raise UserError("No valid input sequences found in the payload.")
    """

    code = "user.error"


class ValidationError400(UserError):
    """Invalid payload values that pass type checks but fail business rules."""

    code = "user.validation"


class UnsupportedOptionError(UserError):
    """The caller requested an option/variant/parameter the model doesn't support."""

    code = "user.unsupported_option"


class ResourceNotFoundError(UserError):
    """A user-referenced resource (e.g. a named input/asset) does not exist."""

    code = "user.resource_not_found"


class ServerError(BioLMError):
    """
    Base class for internal failures (not the caller's fault).

    Server-side errors propagate and are sanitized to 5xx by the gateway.
    """

    code = "system.error"


class ModelExecutionError(ServerError):
    """The underlying model/inference call failed during execution."""

    code = "system.model_execution"


class ErrorResponse(BaseModel):
    """
    Represents a structured error response with a consistent format.

    Attributes:
        detail (str): A top-level message describing the error.
        errors (list[Union[dict[str, Any], str]]): Additional error details,
            such as validation errors or debug logs.
        status_code (int): An HTTP-like status code (e.g., 400, 404, 500).
        code (Optional[str]): A stable, machine-readable error code (dotted
            ``"<domain>.<reason>"`` string) taken from the raised
            ``BioLMError.code``; ``None`` for non-BioLM exceptions.

    Use this model when returning an error response from the decorator
    to ensure a consistent schema.
    """

    detail: str
    errors: list[Union[dict[str, Any], str]] = []
    status_code: int
    code: Optional[str] = None
