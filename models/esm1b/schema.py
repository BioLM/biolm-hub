from functools import partial
from typing import Annotated, Optional

from pydantic import BeforeValidator, Field

from models.commons.data.validator import (
    AAExtendedPlusExtra,
    SingleOrMoreOccurrencesOf,
)
from models.commons.model.base import ModelParams
from models.commons.model.pydantic import (
    EnhancedStringEnum,
    RequestModel,
    ResponseModel,
)

### ESM-1b Params


class ESM1bParams(ModelParams):
    params_version = "v1"
    display_name = "ESM-1b"
    base_model_slug = "esm1b"
    log_identifier = "ESM-1b"
    batch_size = 8
    max_sequence_len = 1022  # 1024 tokens - 2 for BOS/EOS


### ESM-1b Encode Request


class ESM1bEncodeIncludeOptions(EnhancedStringEnum):
    MEAN = "mean"  # mean embedding (default)
    PER_TOKEN = "per_token"  # per-token embeddings
    BOS = "bos"  # beginning-of-sequence embedding
    LOGITS = "logits"  # predicted per-token logits
    ATTENTIONS = "attentions"  # self-attention weights


class ESM1bEncodeRequestParams(RequestModel):
    repr_layers: list[int] = Field(default_factory=partial(list, [-1]))
    include: list[ESM1bEncodeIncludeOptions] = Field(
        default_factory=partial(list, [ESM1bEncodeIncludeOptions.MEAN])
    )


class ESM1bEncodeRequestItem(RequestModel):
    sequence: Annotated[
        str,
        BeforeValidator(AAExtendedPlusExtra(extra=["-"])),
        Field(..., min_length=1, max_length=ESM1bParams.max_sequence_len),
    ]


class ESM1bEncodeRequest(RequestModel):
    params: ESM1bEncodeRequestParams = ESM1bEncodeRequestParams()
    items: Annotated[
        list[ESM1bEncodeRequestItem],
        Field(min_length=1, max_length=ESM1bParams.batch_size),
    ]


### ESM-1b Predict Request


class ESM1bPredictRequestItem(RequestModel):
    sequence: Annotated[
        str,
        BeforeValidator(AAExtendedPlusExtra(extra=["<mask>"])),
        BeforeValidator(SingleOrMoreOccurrencesOf(token="<mask>")),
        Field(..., min_length=1, max_length=ESM1bParams.max_sequence_len),
    ]


class ESM1bPredictRequest(RequestModel):
    items: Annotated[
        list[ESM1bPredictRequestItem],
        Field(min_length=1, max_length=ESM1bParams.batch_size),
    ]


### ESM-1b Log Prob Request


class ESM1bLogProbRequest(RequestModel):
    items: Annotated[
        list[ESM1bEncodeRequestItem],
        Field(min_length=1, max_length=ESM1bParams.batch_size),
    ]


### ESM-1b Encode Response


class LayerEmbedding(ResponseModel):
    layer: int
    embedding: list[float]


class LayerPerTokenEmbeddings(ResponseModel):
    layer: int
    embeddings: list[list[float]]


class ESM1bEncodeResponseResult(ResponseModel):
    model_config = {
        "populate_by_name": True,
        "json_schema_extra": {
            "exclude_unset": True,
            "exclude_none": True,
        },
    }

    sequence_index: int
    embeddings: Optional[list["LayerEmbedding"]] = None
    bos_embeddings: Optional[list["LayerEmbedding"]] = None
    per_token_embeddings: Optional[list["LayerPerTokenEmbeddings"]] = None
    attentions: Optional[list[list[float]]] = None
    logits: Optional[list[list[float]]] = None
    vocab_tokens: Optional[list[str]] = None


class ESM1bEncodeResponse(ResponseModel):
    results: list[ESM1bEncodeResponseResult]


### ESM-1b Predict Response


class ESM1bPredictResponseResult(ResponseModel):
    logits: list[list[float]]
    sequence_tokens: list[str]
    vocab_tokens: list[str]


class ESM1bPredictResponse(ResponseModel):
    results: list[ESM1bPredictResponseResult]


### ESM-1b Log Prob Response


class ESM1bLogProbResponseResult(ResponseModel):
    log_prob: float


class ESM1bLogProbResponse(ResponseModel):
    results: list[ESM1bLogProbResponseResult]
