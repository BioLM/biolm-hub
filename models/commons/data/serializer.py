import datetime
import decimal
import pathlib
import uuid
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel

from models.commons.core.logging import DebugLogger, get_logger

_logger = get_logger(__name__)

# Sentinel returned by _coerce_pandas_numpy when the object is not a
# pandas/numpy type so callers can distinguish None (valid coercion) from
# "not handled".
_SENTINEL = object()


def _coerce_pandas_numpy(obj: Any) -> Any:
    """Coerce pandas/numpy temporal and NA types to JSON-native values.

    Returns ``_SENTINEL`` if *obj* is not a recognised pandas/numpy type so
    that the caller can fall through to further handling.  Returns ``None``
    when the object is a pandas NA/NaT value.

    Lazy-imports pandas and numpy so CPU-only callers don't pay the import
    cost when these types are never encountered.
    """
    try:
        import pandas as pd  # noqa: PLC0415

        # pd.NA / pd.NaT / NAType → None  (avoids truthy "<NA>" string)
        if obj is pd.NA or obj is pd.NaT:
            return None
        # pandas Timestamp → isoformat
        if isinstance(obj, pd.Timestamp):
            return obj.isoformat()
    except ImportError:
        pass

    try:
        import numpy as np  # noqa: PLC0415

        if isinstance(obj, np.datetime64):
            # Convert via pandas for robust isoformat output
            try:
                import pandas as pd  # noqa: PLC0415

                return pd.Timestamp(obj).isoformat()
            except Exception:
                return str(obj)
    except ImportError:
        pass

    return _SENTINEL


def _coerce_stdlib(obj: Any) -> Any:
    """Coerce stdlib types (bytes, sets, datetime, Decimal, UUID, Path).

    Returns ``_SENTINEL`` when the object is not a recognised stdlib type.
    """
    # Bytes → decoded string (best-effort)
    if isinstance(obj, bytes | bytearray):
        try:
            return obj.decode("utf-8")
        except UnicodeDecodeError:
            return obj.hex()

    # Sets/frozensets → lists
    if isinstance(obj, set | frozenset):
        return [_coerce_to_json_native(x) for x in obj]

    # datetime.datetime must be checked before datetime.date (it's a subclass)
    if isinstance(obj, datetime.datetime):
        return obj.isoformat()
    if isinstance(obj, datetime.date):
        return obj.isoformat()

    # Decimal → float for metric consistency (avoids silent "3.14" string)
    if isinstance(obj, decimal.Decimal):
        return float(obj)

    # UUID → canonical string representation
    if isinstance(obj, uuid.UUID):
        return str(obj)

    # Path → POSIX string
    if isinstance(obj, pathlib.PurePath):
        return str(obj)

    return _SENTINEL


def _coerce_array_protocol(obj: Any) -> Any:
    """Coerce numpy-like scalars/arrays using the array protocol methods.

    Returns ``_SENTINEL`` when neither ``tolist`` nor ``item`` is available.
    """
    if hasattr(obj, "tolist") and callable(obj.tolist):
        try:
            return _coerce_to_json_native(obj.tolist())
        except Exception:
            pass
    if hasattr(obj, "item") and callable(obj.item):
        try:
            return _coerce_to_json_native(obj.item())
        except Exception:
            pass
    return _SENTINEL


def _coerce_to_json_native(obj: Any) -> Any:
    """Coerce a single value to a JSON-native type.

    Handles the "Any"-typed leaks that serialize_model's recursion can't
    catch: numpy scalars/arrays, enums, sets, bytes, and anything else
    with a module reference that can't round-trip through cloudpickle on
    the other side of a Modal call.
    """
    # IMPORTANT: Enums must be checked BEFORE the str/int/float/bool fast
    # path. String-valued enums (e.g. EnhancedStringEnum) subclass `str`,
    # so `isinstance(obj, str)` is True for them — but they still pickle
    # by their class module path (e.g. `my_app.enums.SomeEnum`) which breaks
    # Modal's cloudpickle round-trip when the receiver does not have the
    # module installed. Extracting `.value` returns a plain str/int with no
    # module reference.
    if isinstance(obj, Enum):
        return _coerce_to_json_native(obj.value)

    # Fast path for already-native primitives
    if obj is None or isinstance(obj, bool | int | float | str):
        return obj

    # pandas/numpy checked before stdlib: pd.NaT inherits datetime.datetime,
    # so it must be intercepted before the isoformat() branch fires.
    result = _coerce_pandas_numpy(obj)
    if result is not _SENTINEL:
        return result

    result = _coerce_stdlib(obj)
    if result is not _SENTINEL:
        return result

    result = _coerce_array_protocol(obj)
    if result is not _SENTINEL:
        return result

    # Last resort: stringify — but log a warning so unknown types are audible.
    _logger.warning(
        "serializer.fallback: unknown type coerced to str",
        extra={
            "obj_type": type(obj).__name__,
            "obj_module": type(obj).__module__,
        },
    )
    return str(obj)


def serialize_model(obj: Any, debug_logger: Optional[DebugLogger] = None) -> Any:
    """
    Recursively converts a Pydantic model (or collection of Pydantic models)
    into plain Python objects suitable for JSON serialization.

    IMPORTANT: the top-level return crosses the Modal function boundary, which
    cloudpickles everything. Any object whose class lives in a module not
    available on the caller side (e.g. a class defined only in the calling
    application's own modules) will raise ``DeserializationError`` on the
    receiver. This function therefore
    enforces a strict JSON-native contract: every leaf is coerced to
    bool/int/float/str/None via :func:`_coerce_to_json_native`.

    Args:
        obj (Any): A Pydantic model, list, dict, or primitive.

    Returns:
        Any: A structure of only dicts, lists, and JSON-native primitives.
    """

    if debug_logger:
        debug_logger.debug(f"[serialize_model] Converting object type: {type(obj)}")

    # If it's a Pydantic model, convert to dict and recurse
    if isinstance(obj, BaseModel):
        data = (
            obj.model_dump(exclude_none=True)
            if hasattr(obj, "model_dump")
            else obj.dict()
        )
        return serialize_model(data, debug_logger)

    # If it's a list or tuple, recurse on each element
    if isinstance(obj, list | tuple):
        return [serialize_model(item, debug_logger) for item in obj]

    # If it's a dict, recurse on each value
    if isinstance(obj, dict):
        return {str(k): serialize_model(v, debug_logger) for k, v in obj.items()}

    # Leaf: coerce to a JSON-native primitive so nothing with a user-module
    # class reference can leak across the Modal boundary.
    return _coerce_to_json_native(obj)
