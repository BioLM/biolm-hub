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
    # TODO: test how long sequences can be, based on tokenization
    max_sequence_len = 2048


### DNABERT2 Requests


class DNABERT2EncodeRequestItem(RequestModel):
    sequence: Annotated[
        str,
        BeforeValidator(validate_dna_unambiguous),
        Field(..., min_length=1, max_length=DNABERT2Params.max_sequence_len),
    ]


class DNABERT2EncodeRequest(RequestModel):
    items: Annotated[
        list[DNABERT2EncodeRequestItem],
        Field(..., min_length=1, max_length=DNABERT2Params.batch_size),
    ]


class DNABERT2PredictLogProbRequestItem(RequestModel):
    sequence: Annotated[
        str,
        BeforeValidator(validate_dna_unambiguous),
        Field(..., min_length=1, max_length=DNABERT2Params.max_sequence_len),
    ]


class DNABERT2PredictLogProbRequest(RequestModel):
    items: Annotated[
        list[DNABERT2PredictLogProbRequestItem],
        Field(..., min_length=1, max_length=DNABERT2Params.batch_size),
    ]


### DNABERT2 Responses


class DNABERT2EncodeResponseResult(ResponseModel):
    embedding: list[float]


class DNABERT2EncodeResponse(ResponseModel):
    results: list[DNABERT2EncodeResponseResult]


class DNABERT2PredictLogProbResponseResult(ResponseModel):
    log_prob: float


class DNABERT2PredictLogProbResponse(ResponseModel):
    results: list[DNABERT2PredictLogProbResponseResult]
