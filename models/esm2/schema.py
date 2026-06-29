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
    repr_layers: list[int] = Field(
        default_factory=partial(list, [-1]),
        description="Hidden layers whose representations to return (negative indexes count from the last layer).",
    )
    include: list[ESM2EncodeIncludeOptions] = Field(
        default_factory=partial(list, [ESM2EncodeIncludeOptions.MEAN]),
        description="Optional outputs to compute and include in the response.",
    )


class ESM2EncodeRequestItem(RequestModel):
    sequence: Annotated[
        str,
        BeforeValidator(AAExtendedPlusExtra(extra=["-"])),
        Field(
            ...,
            min_length=1,
            max_length=ESM2Params.max_sequence_len,
            description="A protein sequence in single-letter amino-acid codes.",
        ),
    ]


class ESM2EncodeRequest(RequestModel):
    params: ESM2EncodeRequestParams = Field(
        default_factory=ESM2EncodeRequestParams,
        description="Optional parameters controlling this action (defaults are used when omitted).",
    )
    items: Annotated[
        list[ESM2EncodeRequestItem],
        Field(
            min_length=1,
            max_length=ESM2Params.batch_size,
            description="Batch of inputs to process in a single request. Up to 8 sequences per request.",
        ),
    ]


class ESM2PredictRequestItem(RequestModel):
    sequence: Annotated[
        str,
        BeforeValidator(AAExtendedPlusExtra(extra=["<mask>"])),
        BeforeValidator(SingleOrMoreOccurrencesOf(token="<mask>")),
        Field(
            ...,
            min_length=1,
            max_length=ESM2Params.max_sequence_len,
            description="A protein sequence in single-letter amino-acid codes containing one or more <mask> tokens for masked prediction.",
        ),
    ]


class ESM2PredictRequest(RequestModel):
    items: Annotated[
        list[ESM2PredictRequestItem],
        Field(
            min_length=1,
            max_length=ESM2Params.batch_size,
            description="Batch of inputs to process in a single request. Up to 8 sequences per request.",
        ),
    ]


class ESM2LogProbRequest(RequestModel):
    items: Annotated[
        list[ESM2EncodeRequestItem],
        Field(
            min_length=1,
            max_length=ESM2Params.batch_size,
            description="Batch of inputs to process in a single request. Up to 8 sequences per request.",
        ),
    ]


### ESM2 Responses


class LayerEmbedding(RequestModel):
    layer: int = Field(description="Model layer this representation was taken from.")
    embedding: list[float] = Field(
        description="Embedding vector for the sequence at this layer."
    )


class LayerPerTokenEmbeddings(RequestModel):
    layer: int = Field(description="Model layer this representation was taken from.")
    embeddings: list[list[float]] = Field(
        description="Per-residue embedding matrix for this layer, shape [sequence_length, hidden_dim]."
    )


class ESM2EncodeResponseResult(ResponseModel):
    model_config = {
        "populate_by_name": True,  # Ensures alias names work
        "json_schema_extra": {
            "exclude_unset": True,  # Excludes unset (None) fields from the output
            "exclude_none": True,  # Ensures that None fields do not appear in JSON
        },
    }

    sequence_index: int = Field(
        description="Index of the corresponding input sequence within the request batch."
    )
    embeddings: Optional[list["LayerEmbedding"]] = Field(
        default=None,
        description="Mean-pooled embedding vectors, one entry per requested layer.",
    )
    bos_embeddings: Optional[list["LayerEmbedding"]] = Field(
        default=None,
        description="Beginning-of-sequence (CLS) token embedding vectors, one per requested layer.",
    )
    per_token_embeddings: Optional[list["LayerPerTokenEmbeddings"]] = Field(
        default=None,
        description="Per-residue (per-token) embedding vectors.",
    )
    contacts: Optional[list[list[float]]] = Field(
        default=None,
        description="Predicted residue–residue contact probability map.",
    )
    attentions: Optional[list[list[float]]] = Field(
        default=None,
        description="Self-attention weights from the model, averaged over attention heads.",
    )
    logits: Optional[list[list[float]]] = Field(
        default=None,
        description="Per-position logits over the model vocabulary.",
    )
    vocab_tokens: Optional[list[str]] = Field(
        default=None,
        description="Vocabulary token order corresponding to the logits columns.",
    )


class ESM2EncodeResponse(ResponseModel):
    results: list[ESM2EncodeResponseResult] = Field(
        description="Per-input results, returned in the same order as the request items."
    )


class ESM2PredictResponseResult(ResponseModel):
    logits: list[list[float]] = Field(
        description="Per-position logits over the model vocabulary."
    )
    sequence_tokens: list[str] = Field(
        description="Per-position input tokens, aligned with the logits."
    )
    vocab_tokens: list[str] = Field(
        description="Vocabulary token order corresponding to the logits columns."
    )


class ESM2PredictResponse(ResponseModel):
    results: list[ESM2PredictResponseResult] = Field(
        description="Per-input results, returned in the same order as the request items."
    )


class ESM2LogProbResponseResult(ResponseModel):
    log_prob: float = Field(
        description="Pseudo-log-likelihood of the sequence under the model."
    )


class ESM2LogProbResponse(ResponseModel):
    results: list[ESM2LogProbResponseResult] = Field(
        description="Per-input results, returned in the same order as the request items."
    )
