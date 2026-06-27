from typing import Annotated, Optional

from pydantic import BeforeValidator, Field

from models.commons.data.validator import AAExtendedPlusExtra
from models.commons.model.base import ModelParams
from models.commons.model.pydantic import (
    EnhancedStringEnum,
    RequestModel,
    ResponseModel,
)

### ESMStabP Model Parameters


class ESMStabPParams(ModelParams):
    params_version = "v1"
    display_name = "ESMStabP"
    base_model_slug = "esmstabp"
    log_identifier = "ESMSTABP"
    batch_size = 8
    max_sequence_len = 1022  # ESM2 model limit


class ESMStabPExperimentalCondition(EnhancedStringEnum):
    CELL = "cell"
    LYSATE = "lysate"


### ESMStabP Requests


class ESMStabPPredictRequestItem(RequestModel):
    sequence: Annotated[
        str,
        BeforeValidator(AAExtendedPlusExtra(extra=["-"])),
        Field(..., min_length=1, max_length=ESMStabPParams.max_sequence_len),
    ]
    growth_temp: Optional[int] = Field(
        default=None,
        ge=-20,
        le=150,
        description="Optimal growth temperature in Celsius",
    )
    experimental_condition: Optional[ESMStabPExperimentalCondition] = Field(
        default=None,
        description="Experimental condition: cell or lysate",
    )


class ESMStabPPredictRequest(RequestModel):
    items: Annotated[
        list[ESMStabPPredictRequestItem],
        Field(min_length=1, max_length=ESMStabPParams.batch_size),
    ]


### ESMStabP Responses


class ESMStabPPredictResponseResult(ResponseModel):
    melting_temperature: float = Field(
        ...,
        description="Predicted melting temperature (Tm) in Celsius",
    )
    is_thermophilic: Optional[bool] = Field(
        default=None,
        description="Derived classification: True if predicted melting temperature > 60C",
    )


class ESMStabPPredictResponse(ResponseModel):
    results: list[ESMStabPPredictResponseResult]
