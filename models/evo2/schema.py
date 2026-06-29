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
    embedding_layers: list[int] = Field(
        default_factory=partial(list, [-2]),
        description="Transformer layers whose embeddings to extract; supports negative indexing from the last layer.",
    )
    mlp_layer: int = Field(
        default=3,
        description="Index of the MLP sublayer within each transformer block used for embedding extraction.",
    )
    include: list[Evo2EncodeIncludeOptions] = Field(
        default_factory=partial(list, [Evo2EncodeIncludeOptions.MEAN]),
        description="Optional outputs to compute and include in the response.",
    )


class Evo2EncodeRequestItem(RequestModel):
    sequence: Annotated[
        str,
        BeforeValidator(validate_dna_unambiguous),
        Field(
            ...,
            min_length=1,
            max_length=Evo2Params.max_sequence_len,
            description="A DNA sequence (A/C/G/T).",
        ),
    ]


class Evo2EncodeRequest(RequestModel):
    params: Evo2EncodeRequestParams = Field(
        default_factory=Evo2EncodeRequestParams,
        description="Optional parameters controlling this action (defaults are used when omitted).",
    )
    items: Annotated[
        list[Evo2EncodeRequestItem],
        Field(
            ...,
            min_length=1,
            max_length=Evo2Params.batch_size,
            description="Batch of inputs to process in a single request. Up to 1 sequence per request.",
        ),
    ]


class Evo2PredictLogProbRequestItem(RequestModel):
    sequence: Annotated[
        str,
        BeforeValidator(validate_dna_unambiguous),
        Field(
            ...,
            min_length=1,
            max_length=Evo2Params.max_sequence_len,
            description="A DNA sequence (A/C/G/T).",
        ),
    ]


class Evo2PredictLogProbRequest(RequestModel):
    items: Annotated[
        list[Evo2PredictLogProbRequestItem],
        Field(
            ...,
            min_length=1,
            max_length=Evo2Params.batch_size,
            description="Batch of inputs to process in a single request. Up to 1 sequence per request.",
        ),
    ]


class Evo2GenerateRequestParams(RequestModel):
    max_new_tokens: int = Field(
        100,
        ge=1,
        le=Evo2Params.max_sequence_len,
        description="Maximum number of new tokens to generate.",
    )
    temperature: float = Field(
        1.0,
        ge=0.0,
        description="Sampling temperature; higher values increase diversity.",
    )
    top_k: int = Field(
        4,
        ge=1,
        description="Top-k sampling cutoff; only the k most likely tokens are sampled.",
    )
    top_p: float = Field(
        1.0, ge=0.0, le=1.0, description="Nucleus (top-p) sampling threshold."
    )
    seed: Optional[int] = Field(
        default=None, description="Random seed for reproducible sampling."
    )  # For reproducibility control


class Evo2GenerateRequestItem(RequestModel):
    prompt: Annotated[
        str,
        BeforeValidator(validate_dna_unambiguous),
        Field(
            ...,
            min_length=1,
            max_length=Evo2Params.max_sequence_len,
            description="DNA seed sequence (A/C/G/T only) from which to continue autoregressive generation.",
        ),
    ]


class Evo2GenerateRequest(RequestModel):
    params: Evo2GenerateRequestParams = Field(
        default_factory=Evo2GenerateRequestParams,
        description="Optional parameters controlling this action (defaults are used when omitted).",
    )
    items: Annotated[
        list[Evo2GenerateRequestItem],
        Field(
            ...,
            min_length=1,
            max_length=Evo2Params.batch_size,
            description="Batch of inputs to process in a single request. Up to 1 sequence per request.",
        ),
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

    layer: int = Field(description="Model layer this representation was taken from.")
    mean: Optional[list[float]] = Field(
        default=None,
        description="Mean-pooled embedding vector over all non-padded sequence positions for this layer.",
    )
    last: Optional[list[float]] = Field(
        default=None,
        description="Last-token embedding vector for this layer; null if not requested.",
    )


class Evo2EncodeResponseResult(ResponseModel):
    embeddings: list[Evo2EncodeResponseEmbedding] = Field(
        description="Per-layer embedding vectors for the sequence."
    )


class Evo2EncodeResponse(ResponseModel):
    results: list[Evo2EncodeResponseResult] = Field(
        description="Per-input results, returned in the same order as the request items."
    )


class Evo2PredictLogProbResponseResult(ResponseModel):
    log_prob: float = Field(
        description="Pseudo-log-likelihood of the sequence under the model."
    )


class Evo2PredictLogProbResponse(ResponseModel):
    results: list[Evo2PredictLogProbResponseResult] = Field(
        description="Per-input results, returned in the same order as the request items."
    )


class Evo2GenerateResponseResult(ResponseModel):
    generated: str = Field(
        description="Autoregressive continuation of the input prompt as a DNA sequence (A/C/G/T)."
    )


class Evo2GenerateResponse(ResponseModel):
    results: list[Evo2GenerateResponseResult] = Field(
        description="Per-input results, returned in the same order as the request items."
    )
