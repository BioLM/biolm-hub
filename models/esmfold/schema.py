from typing import Annotated

from pydantic import BeforeValidator, Field

from models.commons.data.validator import (
    AAExtendedPlusExtra,
    UpToNNonConsecutiveOccurrencesOf,
)
from models.commons.model.base import ModelParams
from models.commons.model.pydantic import RequestModel, ResponseModel

### ESMFold Params


class ESMFoldParams(ModelParams):
    params_version = "v1"
    display_name = "ESMFold"
    base_model_slug = "esmfold"
    log_identifier = "ESMFold"
    batch_size = 2
    max_sequence_len = 768
    max_n_multimers = 4  # Maximum number of chains in a sequence


### ESMFold Request


class ESMFoldPredictRequestItem(RequestModel):
    sequence: Annotated[
        str,
        BeforeValidator(
            UpToNNonConsecutiveOccurrencesOf(
                token=":",
                max_count=ESMFoldParams.max_n_multimers - 1,
            )
        ),
        BeforeValidator(AAExtendedPlusExtra(extra=[":"])),
        Field(
            min_length=1,
            max_length=ESMFoldParams.max_sequence_len
            + ESMFoldParams.max_n_multimers
            - 1,
        ),
    ]


class ESMFoldPredictRequest(RequestModel):
    items: Annotated[
        list[ESMFoldPredictRequestItem],
        Field(min_length=1, max_length=ESMFoldParams.batch_size),
    ]


### ESMFold Response


class ESMFoldPredictResponseResult(ResponseModel):
    pdb: str
    mean_plddt: float
    ptm: float


class ESMFoldPredictResponse(ResponseModel):
    results: list[ESMFoldPredictResponseResult]
