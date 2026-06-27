from typing import Annotated, Any, Optional

from pydantic import BeforeValidator, Field

from models.commons.data.validator import validate_aa_extended
from models.commons.model.base import ModelParams
from models.commons.model.pydantic import (
    EnhancedStringEnum,
    RequestModel,
    ResponseModel,
)

### Peptides Params


class PeptidesParams(ModelParams):
    params_version = "v1"
    display_name = "peptides"
    base_model_slug = "peptides"
    log_identifier = "peptides"
    batch_size = 10
    max_sequence_len = 2048


### Peptides Requests


class PeptidesEncodeIncludeOptions(EnhancedStringEnum):
    VECTOR = "vector"  # if present, also compute vector-based features


class PeptidesEncodeRequestParams(RequestModel):
    include: list[PeptidesEncodeIncludeOptions] = Field(
        default_factory=list,
    )


class PeptidesEncodeRequestItem(RequestModel):
    sequence: Annotated[
        str,
        BeforeValidator(validate_aa_extended),
        Field(..., min_length=1, max_length=PeptidesParams.max_sequence_len),
    ]


class PeptidesEncodeRequest(RequestModel):
    params: Optional[PeptidesEncodeRequestParams] = None
    items: list[PeptidesEncodeRequestItem] = Field(
        ..., min_length=1, max_length=PeptidesParams.batch_size
    )


### Peptides Response


class PeptidesEncodeResponseResult(ResponseModel):
    """
    We collect all features (numeric, vector, dictionaries, etc.)
    into one large dictionary called 'features'.
    """

    features: dict[str, Any] = Field(default_factory=dict)


class PeptidesEncodeResponse(ResponseModel):
    results: list[PeptidesEncodeResponseResult]
