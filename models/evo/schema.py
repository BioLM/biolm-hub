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
    weights_version = "v1"
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
        Field(
            ...,
            min_length=1,
            max_length=EvoParams.max_sequence_len,
            description="A DNA sequence (A/C/G/T).",
        ),
    ]


class EvoPredictLogProbRequest(RequestModel):
    items: Annotated[
        list[EvoPredictLogProbRequestItem],
        Field(
            min_length=1,
            max_length=EvoParams.batch_size,
            description="Batch of inputs to process in a single request. Up to 2 sequences per request.",
        ),
    ]


class EvoGenerateRequestParams(RequestModel):
    max_new_tokens: int = Field(
        100,
        ge=1,
        le=EvoParams.max_sequence_len,
        description="Maximum number of new tokens to generate.",
    )
    temperature: float = Field(
        0.0,
        ge=0.0,
        description="Sampling temperature; higher values increase diversity.",
    )
    top_k: int = Field(
        1,
        ge=1,
        description="Top-k sampling cutoff; only the k most likely tokens are sampled.",
    )
    top_p: float = Field(
        1.0,
        ge=0.0,
        le=1.0,
        description="Nucleus (top-p) sampling threshold.",
    )
    prepend_bos: bool = Field(
        False,
        description="Whether to prepend a BOS token before the prompt during generation.",
    )
    seed: Optional[int] = Field(
        default=None,
        description="Random seed for reproducible sampling.",
    )


class EvoGenerateRequestItem(RequestModel):
    prompt: Annotated[
        str,
        BeforeValidator(validate_dna_unambiguous),
        Field(
            ...,
            min_length=1,
            max_length=EvoParams.max_sequence_len,
            description="Seed DNA sequence (A/C/G/T) from which generation continues autoregressively.",
        ),
    ]


class EvoGenerateRequest(RequestModel):
    params: EvoGenerateRequestParams = Field(
        default_factory=EvoGenerateRequestParams,
        description="Optional parameters controlling this action (defaults are used when omitted).",
    )
    items: Annotated[
        list[EvoGenerateRequestItem],
        Field(
            min_length=1,
            max_length=EvoParams.batch_size,
            description="Batch of inputs to process in a single request. Up to 2 sequences per request.",
        ),
    ]


### Evo Responses


class EvoPredictLogProbResponseResult(ResponseModel):
    log_prob: float = Field(
        description="Log-likelihood of the sequence under the model.",
    )


class EvoPredictLogProbResponse(ResponseModel):
    results: list[EvoPredictLogProbResponseResult] = Field(
        description="Per-input results, returned in the same order as the request items.",
    )


class EvoGenerateResponseResult(ResponseModel):
    generated: str = Field(
        description="Newly generated DNA continuation (does NOT include the prompt), in A/C/G/T.",
    )
    score: float = Field(
        description="Average log-probability per token of the generated sequence, reflecting model confidence.",
    )


class EvoGenerateResponse(ResponseModel):
    results: list[EvoGenerateResponseResult] = Field(
        description="Per-input results, returned in the same order as the request items.",
    )
