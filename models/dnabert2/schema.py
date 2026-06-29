from typing import Annotated

from pydantic import BeforeValidator, Field

from models.commons.data.validator import validate_dna_unambiguous
from models.commons.model.base import ModelParams
from models.commons.model.pydantic import RequestModel, ResponseModel

### DNABERT2 Model Parameters


class DNABERT2Params(ModelParams):
    display_name = "DNABERT-2"
    base_model_slug = "dnabert2"
    log_identifier = "DNABERT2"
    params_version = "v1"
    batch_size = 10
    # Character (nucleotide) cap enforced by the request schema — 2,048 nt ≈ 2 kbp
    max_sequence_len = 2048
    # Token truncation limit passed to the HuggingFace tokenizer; BPE always yields
    # fewer tokens than characters so this bound never binds in practice.
    max_token_len = 2048


### DNABERT2 Requests


class DNABERT2EncodeRequestItem(RequestModel):
    sequence: Annotated[
        str,
        BeforeValidator(validate_dna_unambiguous),
        Field(
            ...,
            min_length=1,
            max_length=DNABERT2Params.max_sequence_len,
            description="A DNA sequence (A/C/G/T).",
        ),
    ]


class DNABERT2EncodeRequest(RequestModel):
    items: Annotated[
        list[DNABERT2EncodeRequestItem],
        Field(
            ...,
            min_length=1,
            max_length=DNABERT2Params.batch_size,
            description="Batch of inputs to process in a single request. Up to 10 sequences per request.",
        ),
    ]


class DNABERT2PredictLogProbRequestItem(RequestModel):
    sequence: Annotated[
        str,
        BeforeValidator(validate_dna_unambiguous),
        Field(
            ...,
            min_length=1,
            max_length=DNABERT2Params.max_sequence_len,
            description="A DNA sequence (A/C/G/T).",
        ),
    ]


class DNABERT2PredictLogProbRequest(RequestModel):
    items: Annotated[
        list[DNABERT2PredictLogProbRequestItem],
        Field(
            ...,
            min_length=1,
            max_length=DNABERT2Params.batch_size,
            description="Batch of inputs to process in a single request. Up to 10 sequences per request.",
        ),
    ]


### DNABERT2 Responses


class DNABERT2EncodeResponseResult(ResponseModel):
    embedding: list[float] = Field(
        description="Mean-pooled embedding vector for the sequence."
    )


class DNABERT2EncodeResponse(ResponseModel):
    results: list[DNABERT2EncodeResponseResult] = Field(
        description="Per-input results, returned in the same order as the request items."
    )


class DNABERT2PredictLogProbResponseResult(ResponseModel):
    log_prob: float = Field(
        description="Pseudo-log-likelihood of the sequence under the model."
    )


class DNABERT2PredictLogProbResponse(ResponseModel):
    results: list[DNABERT2PredictLogProbResponseResult] = Field(
        description="Per-input results, returned in the same order as the request items."
    )
