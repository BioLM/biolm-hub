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
    repr_layers: list[int] = Field(
        default_factory=partial(list, [-1]),
        description="Hidden layers whose representations to return (negative indexes count from the last layer).",
    )
    include: list[ESMCEncodeIncludeOptions] = Field(
        default_factory=partial(list, [ESMCEncodeIncludeOptions.MEAN]),
        description="Optional outputs to compute and include in the response.",
    )


class ESMCEncodeRequestItem(RequestModel):
    sequence: Annotated[
        str,
        BeforeValidator(AAExtendedPlusExtra(extra=["-"])),
        Field(
            ...,
            min_length=1,
            max_length=ESMCParams.max_sequence_len,
            description="A protein sequence in single-letter amino-acid codes; gap characters (-) are accepted.",
        ),
    ]


class ESMCEncodeRequest(RequestModel):
    params: ESMCEncodeRequestParams = Field(
        default_factory=ESMCEncodeRequestParams,
        description="Optional parameters controlling this action (defaults are used when omitted).",
    )
    items: Annotated[
        list[ESMCEncodeRequestItem],
        Field(
            min_length=1,
            max_length=ESMCParams.batch_size,
            description="Batch of inputs to process in a single request. Up to 8 sequences per request.",
        ),
    ]


class ESMCPredictRequestItem(RequestModel):
    sequence: Annotated[
        str,
        BeforeValidator(AAExtendedPlusExtra(extra=["<mask>"])),
        BeforeValidator(SingleOrMoreOccurrencesOf("<mask>")),
        Field(
            ...,
            min_length=1,
            max_length=ESMCParams.max_sequence_len,
            description="A protein sequence in single-letter amino-acid codes with one or more <mask> tokens indicating positions to predict.",
        ),
    ]


class ESMCPredictRequest(RequestModel):
    items: Annotated[
        list[ESMCPredictRequestItem],
        Field(
            min_length=1,
            max_length=ESMCParams.batch_size,
            description="Batch of inputs to process in a single request. Up to 8 sequences per request.",
        ),
    ]


class ESMCPredictLogProbRequestItem(RequestModel):
    sequence: Annotated[
        str,
        BeforeValidator(validate_aa_unambiguous),
        Field(
            ...,
            min_length=1,
            max_length=ESMCParams.max_sequence_len,
            description="A protein sequence in single-letter amino-acid codes; only the 20 unambiguous amino acids are accepted.",
        ),
    ]


class ESMCPredictLogProbRequest(RequestModel):
    items: Annotated[
        list[ESMCPredictLogProbRequestItem],
        Field(
            min_length=1,
            max_length=ESMCParams.batch_size,
            description="Batch of inputs to process in a single request. Up to 8 sequences per request.",
        ),
    ]


### ESM C Responses


class LayerEmbedding(ResponseModel):
    layer: int = Field(description="Model layer this representation was taken from.")
    embedding: list[float] = Field(
        description="Mean-pooled embedding vector for the sequence."
    )


class LayerPerTokenEmbeddings(ResponseModel):
    layer: int = Field(description="Model layer this representation was taken from.")
    embeddings: list[list[float]] = Field(
        description="Per-residue embedding vectors for this layer, one vector per sequence position (BOS/EOS excluded).",
    )


class ESMCEncodeResponseResult(ResponseModel):
    model_config = {
        "populate_by_name": True,  # Ensures alias names work as expected
        "json_schema_extra": {
            "exclude_unset": True,  # Excludes unset (None) fields from the output
            "exclude_none": True,  # Ensures that None fields do not appear in JSON
        },
    }

    embeddings: Optional[list[LayerEmbedding]] = Field(
        default=None,
        description="Mean-pooled embedding vectors for each requested layer.",
    )
    per_token_embeddings: Optional[list[LayerPerTokenEmbeddings]] = Field(
        default=None,
        description="Per-residue (per-token) embedding vectors.",
    )
    logits: Optional[list[list[float]]] = Field(
        default=None,
        description="Per-position logits over the model vocabulary.",
    )
    vocab_tokens: Optional[list[str]] = Field(
        default=None,
        description="Vocabulary token order corresponding to the logits columns.",
    )


class ESMCEncodeResponse(ResponseModel):
    results: list[ESMCEncodeResponseResult] = Field(
        description="Per-input results, returned in the same order as the request items.",
    )


class ESMCPredictResponseResult(ResponseModel):
    logits: list[list[float]] = Field(
        description="Per-position logits over the model vocabulary.",
    )
    sequence_tokens: list[str] = Field(
        description="Per-position input tokens, aligned with the logits.",
    )
    vocab_tokens: list[str] = Field(
        description="Vocabulary token order corresponding to the logits columns.",
    )


class ESMCPredictResponse(ResponseModel):
    results: list[ESMCPredictResponseResult] = Field(
        description="Per-input results, returned in the same order as the request items.",
    )


class ESMCPredictLogProbResponseResult(ResponseModel):
    log_prob: float = Field(
        description="Pseudo-log-likelihood of the sequence under the model.",
    )


class ESMCPredictLogProbResponse(ResponseModel):
    results: list[ESMCPredictLogProbResponseResult] = Field(
        description="Per-input results, returned in the same order as the request items.",
    )
