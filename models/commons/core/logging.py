import io
import logging
import os
import sys
from typing import Any, Optional, cast

from pydantic import BaseModel

# Maximum length for string fields in debug logs (to prevent overwhelming output)
DEBUG_MAX_FIELD_LENGTH = 500

# Module-logger format. Mirrors DebugLogger's style minus the request-scoped
# model_slug/model_action context (which is injected per-request by DebugLogger).
_LOG_FORMAT = "[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s"

# Guard so the root logger is configured at most once per process.
_configured = False


def configure_logging(level: "str | int | None" = None) -> None:
    """Idempotently configure the root logger for runtime code.

    Installs a single ``StreamHandler(sys.stdout)`` with a simple formatter and
    sets the level from the ``LOG_LEVEL`` env var (default ``INFO``). Modal
    captures stdout, so there are deliberately no file handlers. Safe to call
    multiple times — only the first call installs the handler.
    """
    global _configured
    if _configured:
        return
    if level is None:
        level = os.environ.get("LOG_LEVEL", "INFO")
    root = logging.getLogger()
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter(_LOG_FORMAT))
    root.addHandler(handler)
    root.setLevel(level)
    _configured = True


def get_logger(name: str) -> logging.Logger:
    """Module logger. Usage: ``logger = get_logger(__name__)``.

    Lazily applies a safe default configuration (see ``configure_logging``) so
    callers get working stdout logging without an explicit setup step.
    """
    configure_logging()
    return logging.getLogger(name)


def truncate_for_debug(obj: Any, max_length: int = DEBUG_MAX_FIELD_LENGTH) -> Any:
    """
    Recursively truncate long string fields in objects for debug logging.

    Args:
        obj: The object to truncate (dict, list, Pydantic model, or primitive)
        max_length: Maximum length for string fields

    Returns:
        A copy of the object with long strings truncated
    """
    if isinstance(obj, str):
        if len(obj) > max_length:
            return f"{obj[:max_length]}... [truncated {len(obj) - max_length} chars]"
        return obj
    elif isinstance(obj, dict):
        return {k: truncate_for_debug(v, max_length) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [truncate_for_debug(item, max_length) for item in obj]
    elif isinstance(obj, BaseModel):
        # Convert Pydantic model to dict, truncate, then return as dict
        try:
            d = obj.model_dump() if hasattr(obj, "model_dump") else obj.dict()
            return truncate_for_debug(d, max_length)
        except Exception:
            # If serialization fails, just return string representation
            return (
                str(obj)[:max_length] + "..."
                if len(str(obj)) > max_length
                else str(obj)
            )
    else:
        # For other types (int, float, bool, None, etc.), return as-is
        return obj


class DebugLogger:
    def __init__(
        self,
        enabled: bool = True,
        print_to_console: bool = True,
        level: int = logging.DEBUG,
        extra_context: Optional[dict[str, Any]] = None,
    ) -> None:
        self.enabled = enabled
        self.log_stream: Optional[io.StringIO] = None
        self.handler: Optional[logging.StreamHandler[Any]] = None
        self.logger: Optional[logging.Logger] = None
        self.adapter: Optional[logging.LoggerAdapter[logging.Logger]] = None
        # This will hold the console handler so we can remove it later
        self._print_handler: Optional[logging.StreamHandler[Any]] = None
        if self.enabled:
            self.log_stream = io.StringIO()
            self.handler = logging.StreamHandler(self.log_stream)
            # Custom formatter that prints time, log level, and the provided context (e.g., model_slug and model_action)
            formatter = logging.Formatter(
                "[%(asctime)s] [%(levelname)s] [%(model_slug)s:%(model_action)s] %(message)s"
            )
            self.handler.setFormatter(formatter)

            self.logger = logging.getLogger(f"biolm_debug.{id(self)}")
            self.logger.setLevel(level)
            self.logger.addHandler(self.handler)

            if print_to_console:
                self._print_handler = logging.StreamHandler(sys.stdout)
                self._print_handler.setFormatter(formatter)
                self.logger.addHandler(self._print_handler)

            # Prevent logs from propagating to avoid duplicate output
            self.logger.propagate = False

            # Default extra context if none provided
            if extra_context is None:
                extra_context = {"model_slug": "", "model_action": ""}
            # Wrap the logger in a LoggerAdapter to inject the extra context into every log record.
            self.adapter = logging.LoggerAdapter(self.logger, extra_context)

    def debug(self, message: str) -> None:
        if not self.enabled:
            return
        assert self.adapter is not None
        self.adapter.debug(message)

    def info(self, message: str) -> None:
        if not self.enabled:
            return
        assert self.adapter is not None
        self.adapter.info(message)

    def warning(self, message: str) -> None:
        if not self.enabled:
            return
        assert self.adapter is not None
        self.adapter.warning(message)

    def error(self, message: str) -> None:
        if not self.enabled:
            return
        assert self.adapter is not None
        self.adapter.error(message)

    def get_logs(self) -> str:
        if not self.enabled:
            return ""
        assert self.handler is not None
        assert self.log_stream is not None
        self.handler.flush()
        return self.log_stream.getvalue()

    def clear(self) -> None:
        if not self.enabled:
            return
        assert self.log_stream is not None
        self.log_stream.truncate(0)
        self.log_stream.seek(0)

    def remove_handler(self) -> None:
        if not self.enabled:
            return
        assert self.logger is not None
        assert self.handler is not None
        self.logger.removeHandler(self.handler)
        # Also remove the print handler if it exists
        if self._print_handler:
            self.logger.removeHandler(self._print_handler)

    def update_context(self, extra_context: dict[str, Any]) -> None:
        if not self.enabled:
            return
        assert self.adapter is not None
        # Update the extra context; this will be added to all future log records.
        # LoggerAdapter.extra is typed by typeshed as an immutable Mapping, but
        # __init__ always constructs it from a plain dict, so mutation is safe.
        cast(dict[str, Any], self.adapter.extra).update(extra_context)
