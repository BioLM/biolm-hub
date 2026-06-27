from typing import Any, Union

from pydantic import BaseModel


class UserError(Exception):
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


class ErrorResponse(BaseModel):
    """
    Represents a structured error response with a consistent format.

    Attributes:
        detail (str): A top-level message describing the error.
        errors (list[Union[dict[str, Any], str]]): Additional error details,
            such as validation errors or debug logs.
        status_code (int): An HTTP-like status code (e.g., 400, 404, 500).

    Use this model when returning an error response from the decorator
    to ensure a consistent schema.
    """

    detail: str
    errors: list[Union[dict[str, Any], str]] = []
    status_code: int
