from functools import partial
from typing import Annotated, Optional

from pydantic import BeforeValidator, Field

from models.commons.data.validator import (
    AAExtendedPlusExtra,
    SingleOrMoreOccurrencesOf,
    validate_aa_unambiguous,
)
from models.commons.model.base import ModelParams
from models.commons.model.pydantic import (
    EnhancedStringEnum,
    RequestModel,
    ResponseModel,
)

### ESM C Model Parameters


class ESMCParams(ModelParams):
    params_version = "v1"
    display_name = "ESM C"
    base_model_slug = "esmc"
    log_identifier = "ESM-C"
    batch_size = 8
    max_sequence_len = 2048


class ESMCModelSizes(EnhancedStringEnum):
    SIZE_300M = "300m"


### ESM C Requests


class ESMCEncodeIncludeOptions(EnhancedStringEnum):
    MEAN = "mean"
    PER_TOKEN = "per_token"
    LOGITS = "logits"


class ESMCEncodeRequestParams(RequestModel):
    repr_layers: list[int] = Field(default_factory=partial(list, [-1]))
    include: list[ESMCEncodeIncludeOptions] = Field(
        default_factory=partial(list, [ESMCEncodeIncludeOptions.MEAN])
    )


class ESMCEncodeRequestItem(RequestModel):
    sequence: Annotated[
        str,
        BeforeValidator(AAExtendedPlusExtra(extra=["-"])),
        Field(..., min_length=1, max_length=ESMCParams.max_sequence_len),
    ]


class ESMCEncodeRequest(RequestModel):
    params: ESMCEncodeRequestParams = ESMCEncodeRequestParams()
    items: Annotated[
        list[ESMCEncodeRequestItem],
        Field(min_length=1, max_length=ESMCParams.batch_size),
    ]


class ESMCPredictRequestItem(RequestModel):
    sequence: Annotated[
        str,
        BeforeValidator(AAExtendedPlusExtra(extra=["<mask>"])),
        BeforeValidator(SingleOrMoreOccurrencesOf("<mask>")),
        Field(..., min_length=1, max_length=ESMCParams.max_sequence_len),
    ]


class ESMCPredictRequest(RequestModel):
    items: Annotated[
        list[ESMCPredictRequestItem],
        Field(min_length=1, max_length=ESMCParams.batch_size),
    ]


class ESMCPredictLogProbRequestItem(RequestModel):
    sequence: Annotated[
        str,
        BeforeValidator(validate_aa_unambiguous),
        Field(..., min_length=1, max_length=ESMCParams.max_sequence_len),
    ]


class ESMCPredictLogProbRequest(RequestModel):
    items: Annotated[
        list[ESMCPredictLogProbRequestItem],
        Field(min_length=1, max_length=ESMCParams.batch_size),
    ]


### ESM C Responses


class LayerEmbedding(ResponseModel):
    layer: int
    embedding: list[float]


class LayerPerTokenEmbeddings(ResponseModel):
    layer: int
    embeddings: list[list[float]]


class ESMCEncodeResponseResult(ResponseModel):
    model_config = {
        "populate_by_name": True,  # Ensures alias names work as expected
        "json_schema_extra": {
            "exclude_unset": True,  # Excludes unset (None) fields from the output
            "exclude_none": True,  # Ensures that None fields do not appear in JSON
        },
    }

    embeddings: Optional[list[LayerEmbedding]] = None
    per_token_embeddings: Optional[list[LayerPerTokenEmbeddings]] = None
    logits: Optional[list[list[float]]] = None
    vocab_tokens: Optional[list[str]] = None  # Include only when logits are requested


class ESMCEncodeResponse(ResponseModel):
    results: list[ESMCEncodeResponseResult]


class ESMCPredictResponseResult(ResponseModel):
    logits: list[list[float]]
    sequence_tokens: list[str]
    vocab_tokens: list[str]


class ESMCPredictResponse(ResponseModel):
    results: list[ESMCPredictResponseResult]


class ESMCPredictLogProbResponseResult(ResponseModel):
    log_prob: float


class ESMCPredictLogProbResponse(ResponseModel):
    results: list[ESMCPredictLogProbResponseResult]
