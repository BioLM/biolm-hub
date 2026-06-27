from typing import Annotated

from pydantic import BeforeValidator, Field

from models.commons.data.validator import validate_aa_unambiguous
from models.commons.model.base import ModelParams
from models.commons.model.pydantic import (
    EnhancedStringEnum,
    RequestModel,
    ResponseModel,
)

### ProGen2 Params


class ProGen2Params(ModelParams):
    display_name = "ProGen2"
    base_model_slug = "progen2"
    log_identifier = "ProGen2"
    params_version = "v1"
    batch_size = 1
    max_sequence_len = 512


class ProGen2ModelTypes(EnhancedStringEnum):
    OAS = "oas"
    MEDIUM = "medium"
    LARGE = "large"
    BFD90 = "bfd90"


### ProGen2 Request


class ProGen2GenerateParams(RequestModel):
    temperature: float = Field(default=0.8, ge=0.0, le=8.0)
    top_p: float = Field(default=0.9, ge=0.0, le=1.0)
    num_samples: int = Field(default=1, ge=1, le=3)
    max_length: int = Field(default=128, ge=12, le=ProGen2Params.max_sequence_len)
    seed: int | None = Field(
        default=None, description="Random seed for reproducibility"
    )


class ProGen2GenerateRequestItem(RequestModel):
    context: Annotated[
        str,
        BeforeValidator(validate_aa_unambiguous),
        Field(..., min_length=1, max_length=ProGen2Params.max_sequence_len),
    ]


class ProGen2GenerateRequest(RequestModel):
    params: ProGen2GenerateParams
    items: Annotated[
        list[ProGen2GenerateRequestItem],
        Field(min_length=1, max_length=ProGen2Params.batch_size),
    ]


### ProGen2 Response


class ProGen2GenerateResponseGenerated(RequestModel):
    sequence: str
    ll_sum: float
    ll_mean: float


ProGen2GenerateResponseResult = list[ProGen2GenerateResponseGenerated]


class ProGen2GenerateResponse(ResponseModel):
    results: list[ProGen2GenerateResponseResult]
