from typing import Annotated

from pydantic import BeforeValidator, Field

from models.commons.data.validator import validate_aa_extended
from models.commons.model.base import ModelParams
from models.commons.model.pydantic import (
    EnhancedStringEnum,
    RequestModel,
    ResponseModel,
)

### TEMPRO Model Parameters


class TemproParams(ModelParams):
    params_version = "v1"
    display_name = "TEMPRO"
    base_model_slug = "tempro"
    log_identifier = "TEMPRO"
    batch_size = 8
    min_sequence_len = 100
    max_sequence_len = 160


class TemproESM2Sizes(EnhancedStringEnum):
    SIZE_650M = "650m"
    SIZE_3B = "3b"
    # SIZE_15B = "15b"


### TEMPRO Request


class TemproPredictRequestItem(RequestModel):
    sequence: Annotated[
        str,
        BeforeValidator(validate_aa_extended),
        Field(
            ...,
            min_length=TemproParams.min_sequence_len,
            max_length=TemproParams.max_sequence_len,
            description="Protein sequence (100-160 amino acids, typical nanobody length with some generalization)",
        ),
    ]


class TemproPredictRequest(RequestModel):
    items: Annotated[
        list[TemproPredictRequestItem],
        Field(
            min_length=1,
            max_length=TemproParams.batch_size,
            description="List of protein sequences to predict melting temperatures for",
        ),
    ]


### TEMPRO Response


class TemproPredictResponseResult(ResponseModel):
    tm: float = Field(..., description="Predicted melting temperature in Celsius")


class TemproPredictResponse(ResponseModel):
    results: list[TemproPredictResponseResult] = Field(
        ..., description="List of melting temperature predictions"
    )
