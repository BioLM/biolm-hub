from enum import StrEnum
from typing import Any

from pydantic import BaseModel

try:
    # Pydantic v2 (all models except sadie, whose container downgrades to v1)
    from pydantic import ConfigDict

    _REQUEST_CFG = ConfigDict(strict=True, extra="forbid")
    _RESPONSE_CFG = ConfigDict(strict=True, extra="ignore")

    class RequestModel(BaseModel):
        """Request / internal DTO – reject unknown keys."""

        model_config = _REQUEST_CFG

    class ResponseModel(BaseModel):
        """Response DTO – drop unknown keys silently."""

        model_config = _RESPONSE_CFG

except ImportError:
    # Pydantic v1 fallback (sadie-antibody==1.0.6 forces pydantic v1)

    class RequestModel(BaseModel):  # type: ignore[no-redef]
        """Request / internal DTO – reject unknown keys."""

        class Config:
            extra = "forbid"

    class ResponseModel(BaseModel):  # type: ignore[no-redef]
        """Response DTO – drop unknown keys silently."""

        class Config:
            extra = "ignore"


# -------- Enhanced Enum Utilities --------


try:
    from pydantic import GetCoreSchemaHandler as _Handler
    from pydantic_core import core_schema as _cs

    class _CastableEnumMixin:
        """Mix-in that lets strict models accept raw strings or the enum itself."""

        @classmethod
        def __get_pydantic_core_schema__(
            cls, source: Any, handler: _Handler
        ) -> _cs.CoreSchema:
            schema = handler(source)
            return _cs.no_info_before_validator_function(
                lambda v: cls(v) if isinstance(v, str) else v,
                schema,
            )

except ImportError:

    class _CastableEnumMixin:  # type: ignore[no-redef]
        """Fallback for pydantic v1 (sadie container)."""

        @classmethod
        def __get_validators__(cls):
            def _cast(v):
                if isinstance(v, str) and not isinstance(v, cls):
                    return cls(v)
                return v

            yield _cast


class EnhancedStringEnum(_CastableEnumMixin, StrEnum):
    """String enum with value-based membership, member iteration, and `str()` to value.

    On Python 3.12+, stdlib ``StrEnum`` already provides value-`in` membership
    (``"predict" in ModelActions``), iteration over members, and ``__str__``
    returning the member's value. The only feature layered on top is
    ``_CastableEnumMixin``, which lets *strict* Pydantic models accept a raw
    string (or the enum member) for fields typed as this enum.
    """
