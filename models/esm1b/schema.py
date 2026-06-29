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
    weights_version = "v1"
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
    repr_layers: list[int] = Field(
        default_factory=partial(list, [-1]),
        description="Hidden layers whose representations to return (negative indexes count from the last layer).",
    )
    include: list[ESM1bEncodeIncludeOptions] = Field(
        default_factory=partial(list, [ESM1bEncodeIncludeOptions.MEAN]),
        description="Output types to include in the encode response; controls which embeddings, logits, or attention outputs are returned.",
    )


class ESM1bEncodeRequestItem(RequestModel):
    sequence: Annotated[
        str,
        BeforeValidator(AAExtendedPlusExtra(extra=["-"])),
        Field(
            ...,
            min_length=1,
            max_length=ESM1bParams.max_sequence_len,
            description="A protein sequence in single-letter amino-acid codes.",
        ),
    ]


class ESM1bEncodeRequest(RequestModel):
    params: ESM1bEncodeRequestParams = Field(
        default_factory=ESM1bEncodeRequestParams,
        description="Optional parameters controlling this action (defaults are used when omitted).",
    )
    items: Annotated[
        list[ESM1bEncodeRequestItem],
        Field(
            min_length=1,
            max_length=ESM1bParams.batch_size,
            description="Batch of inputs to process in a single request. Up to 8 sequences per request.",
        ),
    ]


### ESM-1b Predict Request


class ESM1bPredictRequestItem(RequestModel):
    sequence: Annotated[
        str,
        BeforeValidator(AAExtendedPlusExtra(extra=["<mask>"])),
        BeforeValidator(SingleOrMoreOccurrencesOf(token="<mask>")),
        Field(
            ...,
            min_length=1,
            max_length=ESM1bParams.max_sequence_len,
            description="A protein sequence in single-letter amino-acid codes, with one or more <mask> tokens for masked prediction.",
        ),
    ]


class ESM1bPredictRequest(RequestModel):
    items: Annotated[
        list[ESM1bPredictRequestItem],
        Field(
            min_length=1,
            max_length=ESM1bParams.batch_size,
            description="Batch of inputs to process in a single request. Up to 8 sequences per request.",
        ),
    ]


### ESM-1b Log Prob Request


class ESM1bLogProbRequest(RequestModel):
    items: Annotated[
        list[ESM1bEncodeRequestItem],
        Field(
            min_length=1,
            max_length=ESM1bParams.batch_size,
            description="Batch of inputs to process in a single request. Up to 8 sequences per request.",
        ),
    ]


### ESM-1b Encode Response


class LayerEmbedding(ResponseModel):
    layer: int = Field(description="Model layer this representation was taken from.")
    embedding: list[float] = Field(
        description="Embedding vector for the sequence at this layer.",
    )


class LayerPerTokenEmbeddings(ResponseModel):
    layer: int = Field(description="Model layer this representation was taken from.")
    embeddings: list[list[float]] = Field(
        description="Per-residue (per-token) embedding vectors for this layer.",
    )


class ESM1bEncodeResponseResult(ResponseModel):
    model_config = {
        "populate_by_name": True,
        "json_schema_extra": {
            "exclude_unset": True,
            "exclude_none": True,
        },
    }

    sequence_index: int = Field(
        description="Index of the corresponding input sequence within the request batch.",
    )
    embeddings: Optional[list["LayerEmbedding"]] = Field(
        default=None,
        description="Per-layer mean-pooled embedding vectors; present only when 'mean' is requested.",
    )
    bos_embeddings: Optional[list["LayerEmbedding"]] = Field(
        default=None,
        description="Per-layer beginning-of-sequence (BOS/CLS) token embedding vectors; present only when 'bos' is requested.",
    )
    per_token_embeddings: Optional[list["LayerPerTokenEmbeddings"]] = Field(
        default=None,
        description="Per-residue (per-token) embedding vectors.",
    )
    attentions: Optional[list[list[float]]] = Field(
        default=None,
        description="Averaged attention weights across all layers and heads; present only when 'attentions' is requested.",
    )
    logits: Optional[list[list[float]]] = Field(
        default=None,
        description="Per-position logits over the model vocabulary.",
    )
    vocab_tokens: Optional[list[str]] = Field(
        default=None,
        description="Vocabulary token order corresponding to the logits columns.",
    )


class ESM1bEncodeResponse(ResponseModel):
    results: list[ESM1bEncodeResponseResult] = Field(
        description="Per-input results, returned in the same order as the request items.",
    )


### ESM-1b Predict Response


class ESM1bPredictResponseResult(ResponseModel):
    logits: list[list[float]] = Field(
        description="Per-position logits over the model vocabulary.",
    )
    sequence_tokens: list[str] = Field(
        description="Per-position input tokens, aligned with the logits.",
    )
    vocab_tokens: list[str] = Field(
        description="Vocabulary token order corresponding to the logits columns.",
    )


class ESM1bPredictResponse(ResponseModel):
    results: list[ESM1bPredictResponseResult] = Field(
        description="Per-input results, returned in the same order as the request items.",
    )


### ESM-1b Log Prob Response


class ESM1bLogProbResponseResult(ResponseModel):
    log_prob: float = Field(
        description="Log-likelihood of the sequence under the model.",
    )


class ESM1bLogProbResponse(ResponseModel):
    results: list[ESM1bLogProbResponseResult] = Field(
        description="Per-input results, returned in the same order as the request items.",
    )
