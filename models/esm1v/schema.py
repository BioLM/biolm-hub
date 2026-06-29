from typing import Annotated, Union

from pydantic import BeforeValidator, Field

from models.commons.data.validator import (
    AAExtendedPlusExtra,
    SingleOccurrenceOf,
)
from models.commons.model.base import ModelParams
from models.commons.model.pydantic import (
    EnhancedStringEnum,
    RequestModel,
    ResponseModel,
)

### ESM1v Params


class ESM1vParams(ModelParams):
    params_version = "v1"
    display_name = "ESM1v"
    base_model_slug = "esm1v"
    log_identifier = "ESM-1v"
    batch_size = 5
    max_sequence_len = (
        1022  # 1024 tokens - 2 for BOS/EOS (ESM-1v shares ESM-1b's architecture)
    )


class ESM1vModelNumbers(EnhancedStringEnum):
    N1 = "n1"
    N2 = "n2"
    N3 = "n3"
    N4 = "n4"
    N5 = "n5"
    ALL = "all"


### ESM1v Request


class ESM1vPredictRequestItem(RequestModel):
    sequence: Annotated[
        str,
        BeforeValidator(AAExtendedPlusExtra(extra=["<mask>"])),
        BeforeValidator(SingleOccurrenceOf(single_token="<mask>")),
        Field(
            ...,
            min_length=1,
            max_length=ESM1vParams.max_sequence_len,
            description="A protein sequence in single-letter amino-acid codes with exactly one <mask> token marking the position to predict.",
        ),
    ]


class ESM1vPredictRequest(RequestModel):
    items: Annotated[
        list[ESM1vPredictRequestItem],
        Field(
            min_length=1,
            max_length=ESM1vParams.batch_size,
            description="Batch of inputs to process in a single request. Up to 5 sequences per request.",
        ),
    ]


### ESM1v Response


class ESM1vPredictResponseLabel(ResponseModel):
    token: int = Field(
        description="Tokenizer vocabulary ID for the predicted amino acid."
    )
    token_str: str = Field(
        description="Single-letter amino-acid code for the predicted residue."
    )
    score: float = Field(
        description="Model probability for this amino acid at the masked position."
    )
    sequence: str = Field(
        description="Full protein sequence with the masked position filled by this amino acid."
    )


ESM1vNPredictResponseResult = list[ESM1vPredictResponseLabel]

ESM1vAllPredictResponseResult = dict[
    Annotated[str, Field(pattern="^esm1v-n[1-5]$")],
    list[ESM1vPredictResponseLabel],
]


class ESM1vPredictResponse(ResponseModel):
    results: Union[
        list[ESM1vNPredictResponseResult], list[ESM1vAllPredictResponseResult]
    ] = Field(
        description="Per-input results, returned in the same order as the request items."
    )
