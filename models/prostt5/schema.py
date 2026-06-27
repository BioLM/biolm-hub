import re
from typing import Annotated

from pydantic import BeforeValidator, Field

from models.commons.data.validator import validate_aa_extended
from models.commons.model.base import ModelParams
from models.commons.model.pydantic import (
    EnhancedStringEnum,
    RequestModel,
    ResponseModel,
)

### ProstT5 Params


class ProstT5Params(ModelParams):
    params_version = "v1"
    half_precision = True
    display_name = "ProstT5"
    base_model_slug = "prostt5"
    log_identifier = "ProstT5"


class ProstT5EncodeParams(ProstT5Params):
    batch_size = 16
    max_sequence_len = 1000


class ProstT5GenerateParams(ProstT5Params):
    batch_size = 2
    max_sequence_len = 512  # <= 1000
    max_beam_width = 3


# ProstT5 Model Types


class ProstT5Directions(EnhancedStringEnum):
    FOLD = "fold2AA"
    AA = "AA2fold"


class ProstT5Types(EnhancedStringEnum):
    ENCODE = "encode"
    GENERATE = "generate"


### ProstT5 Validator

prostt5_3di = "acdefghiklmnpqrstvwy"
prostt5_3di_regex = re.compile(f"^[{prostt5_3di}]+$")


def validate_prostt5_3di(text: str) -> str:
    if not prostt5_3di_regex.match(text):
        raise ValueError(
            f"Nucleotides can only be represented with '{prostt5_3di}' characters"
        )
    return text


### ProstT5 Encode Request


class ProstT5EncodeRequestItemAA(RequestModel):  # AA2fold
    sequence: Annotated[
        str,
        BeforeValidator(validate_aa_extended),
        Field(..., min_length=1, max_length=ProstT5EncodeParams.max_sequence_len),
    ]


class ProstT5EncodeRequestItemFold(RequestModel):  # fold2AA
    sequence: Annotated[
        str,
        BeforeValidator(validate_prostt5_3di),
        Field(..., min_length=1, max_length=ProstT5EncodeParams.max_sequence_len),
    ]


class ProstT5EncodeRequestAA(RequestModel):
    items: Annotated[
        list[ProstT5EncodeRequestItemAA],
        Field(min_length=1, max_length=ProstT5EncodeParams.batch_size),
    ]


class ProstT5EncodeRequestFold(RequestModel):
    items: Annotated[
        list[ProstT5EncodeRequestItemFold],
        Field(min_length=1, max_length=ProstT5EncodeParams.batch_size),
    ]


### ProstT5 Encode Response


class ProstT5EncodeResponseLabel(RequestModel):
    token: int
    token_str: str
    score: float
    sequence: str


ProstT5NEncodeResponseResult = list[ProstT5EncodeResponseLabel]


class ProstT5EncodeResponseResult(ResponseModel):
    mean_representation: list[float]


class ProstT5EncodeResponse(ResponseModel):
    results: list[ProstT5EncodeResponseResult]


### ProstT5 Generate Request


class ProstT5GenerateParamsAA(RequestModel):  # AA2Fold
    temperature: float = Field(default=1.2, ge=0.0, le=8.0)
    top_p: float = Field(default=0.95, ge=0.0, le=1.0)
    top_k: int = Field(default=6, ge=1, le=20)
    repetition_penalty: float = Field(
        default=1.2, ge=0.0, le=3.0
    )  # No specific cap was in model repo
    num_samples: int = Field(default=1, ge=1, le=3)
    num_beams: int = Field(default=3, ge=1, le=ProstT5GenerateParams.max_beam_width)
    seed: int | None = None  # For reproducibility control


class ProstT5GenerateRequestItemAA(RequestModel):
    sequence: Annotated[
        str,
        BeforeValidator(validate_aa_extended),
        Field(..., min_length=1, max_length=ProstT5GenerateParams.max_sequence_len),
    ]


class ProstT5GenerateRequestAA(RequestModel):
    params: ProstT5GenerateParamsAA = ProstT5GenerateParamsAA()
    items: Annotated[
        list[ProstT5GenerateRequestItemAA],
        Field(min_length=1, max_length=ProstT5GenerateParams.batch_size),
    ]


class ProstT5GenerateParamsFold(RequestModel):  # fold2AA
    temperature: float = Field(default=1.0, ge=0.0, le=8.0)
    top_p: float = Field(default=0.85, ge=0.0, le=1.0)
    top_k: int = Field(default=3, ge=1, le=20)
    repetition_penalty: float = Field(default=1.2, ge=0.0, le=3.0)
    num_samples: int = Field(default=1, ge=1, le=3)
    seed: int | None = None  # For reproducibility control


class ProstT5GenerateRequestItemFold(RequestModel):
    sequence: Annotated[
        str,
        BeforeValidator(validate_prostt5_3di),
        Field(..., min_length=1, max_length=ProstT5GenerateParams.max_sequence_len),
    ]


class ProstT5GenerateRequestFold(RequestModel):
    params: ProstT5GenerateParamsFold = ProstT5GenerateParamsFold()
    items: Annotated[
        list[ProstT5GenerateRequestItemFold],
        Field(min_length=1, max_length=ProstT5GenerateParams.batch_size),
    ]


### ProstT5 Generate Response


class ProstT5GenerateResponseGenerated(RequestModel):
    sequence: str


ProstT5GenerateResponseResult = list[ProstT5GenerateResponseGenerated]


class ProstT5GenerateResponse(ResponseModel):
    results: list[ProstT5GenerateResponseResult]
