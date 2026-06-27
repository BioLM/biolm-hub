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

### ESM2 Params


class ESM2Params(ModelParams):
    params_version = "v1"
    display_name = "ESM2"
    base_model_slug = "esm2"
    log_identifier = "ESM2"
    batch_size = 8
    max_sequence_len = 2048


class ESM2ModelSizes(EnhancedStringEnum):
    SIZE_8M = "8m"
    SIZE_35M = "35m"
    SIZE_150M = "150m"
    SIZE_650M = "650m"
    SIZE_3B = "3b"
    # SIZE_15B = "15b"  # Too big to support, unless really needed
    # See: https://github.com/facebookresearch/esm/blob/main/examples/esm2_infer_fairscale_fsdp_cpu_offloading.py


### ESM2 Requests


class ESM2EncodeIncludeOptions(EnhancedStringEnum):
    MEAN = "mean"  # mean embedding (default)
    PER_TOKEN = "per_token"  # per-token embeddings
    BOS = "bos"  # beginning-of-sequence embedding
    CONTACTS = "contacts"  # predicted inter-residue distances
    LOGITS = "logits"  # predicted per-token logits
    ATTENTIONS = "attentions"  # self-attention weights


class ESM2EncodeRequestParams(RequestModel):
    repr_layers: list[int] = Field(default_factory=partial(list, [-1]))
    include: list[ESM2EncodeIncludeOptions] = Field(
        default_factory=partial(list, [ESM2EncodeIncludeOptions.MEAN])
    )


class ESM2EncodeRequestItem(RequestModel):
    sequence: Annotated[
        str,
        BeforeValidator(AAExtendedPlusExtra(extra=["-"])),
        Field(..., min_length=1, max_length=ESM2Params.max_sequence_len),
    ]


class ESM2EncodeRequest(RequestModel):
    params: ESM2EncodeRequestParams = ESM2EncodeRequestParams()
    items: Annotated[
        list[ESM2EncodeRequestItem],
        Field(min_length=1, max_length=ESM2Params.batch_size),
    ]


class ESM2PredictRequestItem(RequestModel):
    sequence: Annotated[
        str,
        BeforeValidator(AAExtendedPlusExtra(extra=["<mask>"])),
        BeforeValidator(SingleOrMoreOccurrencesOf(token="<mask>")),
        Field(..., min_length=1, max_length=ESM2Params.max_sequence_len),
    ]


class ESM2PredictRequest(RequestModel):
    items: Annotated[
        list[ESM2PredictRequestItem],
        Field(min_length=1, max_length=ESM2Params.batch_size),
    ]


class ESM2LogProbRequest(RequestModel):
    items: Annotated[
        list[ESM2EncodeRequestItem],
        Field(min_length=1, max_length=ESM2Params.batch_size),
    ]


### ESM2 Responses


class LayerEmbedding(RequestModel):
    layer: int
    embedding: list[float]


class LayerPerTokenEmbeddings(RequestModel):
    layer: int
    embeddings: list[list[float]]


class ESM2EncodeResponseResult(ResponseModel):
    model_config = {
        "populate_by_name": True,  # Ensures alias names work
        "json_schema_extra": {
            "exclude_unset": True,  # Excludes unset (None) fields from the output
            "exclude_none": True,  # Ensures that None fields do not appear in JSON
        },
    }

    sequence_index: int
    embeddings: Optional[list["LayerEmbedding"]] = None
    bos_embeddings: Optional[list["LayerEmbedding"]] = None
    per_token_embeddings: Optional[list["LayerPerTokenEmbeddings"]] = None
    contacts: Optional[list[list[float]]] = None
    attentions: Optional[list[list[float]]] = None
    logits: Optional[list[list[float]]] = None
    vocab_tokens: Optional[list[str]] = None  # Include only when logits are requested


class ESM2EncodeResponse(ResponseModel):
    results: list[ESM2EncodeResponseResult]


class ESM2PredictResponseResult(ResponseModel):
    logits: list[list[float]]
    sequence_tokens: list[str]
    vocab_tokens: list[str]


class ESM2PredictResponse(ResponseModel):
    results: list[ESM2PredictResponseResult]


class ESM2LogProbResponseResult(ResponseModel):
    log_prob: float


class ESM2LogProbResponse(ResponseModel):
    results: list[ESM2LogProbResponseResult]
