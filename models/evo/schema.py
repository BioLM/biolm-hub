from typing import Annotated, Optional

from pydantic import BeforeValidator, Field

from models.commons.data.validator import validate_dna_unambiguous
from models.commons.model.base import ModelParams
from models.commons.model.pydantic import (
    EnhancedStringEnum,
    RequestModel,
    ResponseModel,
)


class EvoParams(ModelParams):
    params_version = "v1"
    display_name = "Evo"
    base_model_slug = "evo"
    log_identifier = "Evo"
    batch_size = 2
    max_sequence_len = (
        4096  # Evo can handle longer contexts, but let's keep a cap in place
    )


class EvoModelVariants(EnhancedStringEnum):
    EVO_1_5_8K_BASE = "v1.5-8k"  # "1.5-8k-base" (Default)
    # EVO_1_8K_BASE = "v1-8k"  # "1-8k-base"
    # EVO_1_131K_BASE = "v1-131k"  # "1-131k-base"
    # EVO_1_8K_CRISPR = "v1-8k-crispr"  # "1-8k-crispr"
    # EVO_1_8K_TRANSPOSON = "v1-8k-transposon"  # "1-8k-transposon"


### Evo Requests


class EvoPredictLogProbRequestItem(RequestModel):
    sequence: Annotated[
        str,
        BeforeValidator(validate_dna_unambiguous),
        Field(..., min_length=1, max_length=EvoParams.max_sequence_len),
    ]


class EvoPredictLogProbRequest(RequestModel):
    items: Annotated[
        list[EvoPredictLogProbRequestItem],
        Field(min_length=1, max_length=EvoParams.batch_size),
    ]


class EvoGenerateRequestParams(RequestModel):
    max_new_tokens: int = Field(100, ge=1, le=EvoParams.max_sequence_len)
    temperature: float = Field(0.0, ge=0.0)
    top_k: int = Field(1, ge=1)
    top_p: float = Field(1.0, ge=0.0, le=1.0)
    prepend_bos: bool = Field(False)
    seed: Optional[int] = None  # NEW: For reproducibility control


class EvoGenerateRequestItem(RequestModel):
    prompt: Annotated[
        str,
        BeforeValidator(validate_dna_unambiguous),
        Field(..., min_length=1, max_length=EvoParams.max_sequence_len),
    ]


class EvoGenerateRequest(RequestModel):
    params: EvoGenerateRequestParams = EvoGenerateRequestParams()
    items: Annotated[
        list[EvoGenerateRequestItem],
        Field(min_length=1, max_length=EvoParams.batch_size),
    ]


### Evo Responses


class EvoPredictLogProbResponseResult(ResponseModel):
    log_prob: float


class EvoPredictLogProbResponse(ResponseModel):
    results: list[EvoPredictLogProbResponseResult]


class EvoGenerateResponseResult(ResponseModel):
    generated: str
    score: float


class EvoGenerateResponse(ResponseModel):
    results: list[EvoGenerateResponseResult]
