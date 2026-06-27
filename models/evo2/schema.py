from functools import partial
from typing import Annotated, Optional

from pydantic import BeforeValidator, Field

from models.commons.data.validator import validate_dna_unambiguous
from models.commons.model.base import ModelParams
from models.commons.model.pydantic import (
    EnhancedStringEnum,
    RequestModel,
    ResponseModel,
)

### Evo2 Model Parameters


class Evo2Params(ModelParams):
    params_version = "v1"
    display_name = "Evo2"
    base_model_slug = "evo2"
    log_identifier = "Evo2"
    batch_size = 1
    max_sequence_len = 4096


class Evo2ModelVariants(EnhancedStringEnum):
    """
    List of all 5 Evo2 variants published on HF:
      - 1b_base (8k context)
      - 7b_base (8k context)
      - 7b (1M context)
      - 40b_base (8k context)
      - 40b (1M context)

    We only *actively* use 1b_base & 7b_base in our codebase. The others are commented out below.
    """

    EVO2_1B_BASE = "1b-base"  # evo2_1b_base
    EVO2_7B_BASE = "7b-base"  # evo2_7b_base
    # EVO2_7B = "7b"  # evo2_7b
    # EVO2_40B_BASE = "40b-base"  # evo2_40b_base
    # EVO2_40B = "40b"  # evo2_40b


### Evo2 Requests


class Evo2EncodeIncludeOptions(EnhancedStringEnum):
    MEAN = "mean"
    LAST = "last"


class Evo2EncodeRequestParams(RequestModel):
    embedding_layers: list[int] = Field(default_factory=partial(list, [-2]))
    mlp_layer: int = 3  # Fixed to 3, but can be adjusted
    include: list[Evo2EncodeIncludeOptions] = Field(
        default_factory=partial(list, [Evo2EncodeIncludeOptions.MEAN])
    )


class Evo2EncodeRequestItem(RequestModel):
    sequence: Annotated[
        str,
        BeforeValidator(validate_dna_unambiguous),
        Field(..., min_length=1, max_length=Evo2Params.max_sequence_len),
    ]


class Evo2EncodeRequest(RequestModel):
    params: Evo2EncodeRequestParams = Evo2EncodeRequestParams()
    items: Annotated[
        list[Evo2EncodeRequestItem],
        Field(..., min_length=1, max_length=Evo2Params.batch_size),
    ]


class Evo2PredictLogProbRequestItem(RequestModel):
    sequence: Annotated[
        str,
        BeforeValidator(validate_dna_unambiguous),
        Field(..., min_length=1, max_length=Evo2Params.max_sequence_len),
    ]


class Evo2PredictLogProbRequest(RequestModel):
    items: Annotated[
        list[Evo2PredictLogProbRequestItem],
        Field(..., min_length=1, max_length=Evo2Params.batch_size),
    ]


class Evo2GenerateRequestParams(RequestModel):
    max_new_tokens: int = Field(100, ge=1, le=Evo2Params.max_sequence_len)
    temperature: float = Field(1.0, ge=0.0)
    top_k: int = Field(4, ge=1)
    top_p: float = Field(1.0, ge=0.0, le=1.0)
    seed: Optional[int] = None  # For reproducibility control


class Evo2GenerateRequestItem(RequestModel):
    prompt: Annotated[
        str,
        BeforeValidator(validate_dna_unambiguous),
        Field(..., min_length=1, max_length=Evo2Params.max_sequence_len),
    ]


class Evo2GenerateRequest(RequestModel):
    params: Evo2GenerateRequestParams = Evo2GenerateRequestParams()
    items: Annotated[
        list[Evo2GenerateRequestItem],
        Field(..., min_length=1, max_length=Evo2Params.batch_size),
    ]


### Evo2 Responses


class Evo2EncodeResponseEmbedding(RequestModel):
    model_config = {
        "populate_by_name": True,  # Ensures alias names work as expected
        "json_schema_extra": {
            "exclude_unset": True,  # Excludes unset (None) fields from the output
            "exclude_none": True,  # Ensures that None fields do not appear in JSON
        },
    }

    layer: int
    mean: Optional[list[float]] = None
    last: Optional[list[float]] = None


class Evo2EncodeResponseResult(ResponseModel):
    embeddings: list[Evo2EncodeResponseEmbedding]


class Evo2EncodeResponse(ResponseModel):
    results: list[Evo2EncodeResponseResult]


class Evo2PredictLogProbResponseResult(ResponseModel):
    log_prob: float


class Evo2PredictLogProbResponse(ResponseModel):
    results: list[Evo2PredictLogProbResponseResult]


class Evo2GenerateResponseResult(ResponseModel):
    generated: str


class Evo2GenerateResponse(ResponseModel):
    results: list[Evo2GenerateResponseResult]
