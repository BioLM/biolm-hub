from collections.abc import Iterator
from enum import Enum, EnumMeta
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


class EnhancedEnumMeta(EnumMeta):
    def __contains__(cls, item: object) -> bool:
        try:
            cls(item)
        except ValueError:
            return False
        return True


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


class EnhancedStringEnum(_CastableEnumMixin, str, Enum, metaclass=EnhancedEnumMeta):
    """
    EnhancedStringEnum class that allows for:
    - membership testing with `in` operator
    - iteration over the members
    - automatic string casting in Pydantic models
    """

    @classmethod
    def __iter__(cls) -> Iterator[str]:
        return (member.value for member in cls)

    def __str__(self) -> str:
        return str(self.value)
