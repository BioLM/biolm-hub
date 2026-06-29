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
    weights_version = "v1"
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
            f"3Di structural tokens can only use the lowercase characters '{prostt5_3di}'"
        )
    return text


### ProstT5 Encode Request


class ProstT5EncodeRequestItemAA(RequestModel):  # AA2fold
    sequence: Annotated[
        str,
        BeforeValidator(validate_aa_extended),
        Field(
            ...,
            min_length=1,
            max_length=ProstT5EncodeParams.max_sequence_len,
            description="A protein sequence in single-letter amino-acid codes.",
        ),
    ]


class ProstT5EncodeRequestItemFold(RequestModel):  # fold2AA
    sequence: Annotated[
        str,
        BeforeValidator(validate_prostt5_3di),
        Field(
            ...,
            min_length=1,
            max_length=ProstT5EncodeParams.max_sequence_len,
            description="A 3Di structural token sequence in Foldseek's lowercase 20-letter alphabet.",
        ),
    ]


class ProstT5EncodeRequestAA(RequestModel):
    items: Annotated[
        list[ProstT5EncodeRequestItemAA],
        Field(
            min_length=1,
            max_length=ProstT5EncodeParams.batch_size,
            description="Batch of inputs to process in a single request. Up to 16 sequences per request.",
        ),
    ]


class ProstT5EncodeRequestFold(RequestModel):
    items: Annotated[
        list[ProstT5EncodeRequestItemFold],
        Field(
            min_length=1,
            max_length=ProstT5EncodeParams.batch_size,
            description="Batch of inputs to process in a single request. Up to 16 sequences per request.",
        ),
    ]


### ProstT5 Encode Response


class ProstT5EncodeResponseResult(ResponseModel):
    mean_representation: list[float] = Field(
        description="Mean-pooled 1024-dimensional embedding vector for the input sequence."
    )


class ProstT5EncodeResponse(ResponseModel):
    results: list[ProstT5EncodeResponseResult] = Field(
        description="Per-input results, returned in the same order as the request items."
    )


### ProstT5 Generate Request


class ProstT5GenerateParamsAA(RequestModel):  # AA2Fold
    temperature: float = Field(
        default=1.2,
        ge=0.0,
        le=8.0,
        description="Sampling temperature; higher values increase diversity.",
    )
    top_p: float = Field(
        default=0.95,
        ge=0.0,
        le=1.0,
        description="Nucleus (top-p) sampling threshold.",
    )
    top_k: int = Field(
        default=6,
        ge=1,
        le=20,
        description="Top-k sampling cutoff; only the k most likely tokens are sampled.",
    )
    repetition_penalty: float = Field(
        default=1.2,
        ge=0.0,
        le=3.0,
        description="Repetition penalty applied during generation; values > 1.0 discourage repeated tokens.",
    )  # No specific cap was in model repo
    num_samples: int = Field(
        default=1,
        ge=1,
        le=3,
        description="Number of sequences to generate per input.",
    )
    num_beams: int = Field(
        default=3,
        ge=1,
        le=ProstT5GenerateParams.max_beam_width,
        description="Beam search width for AA2fold translation; wider beams improve quality at higher compute cost.",
    )
    seed: int | None = Field(
        default=None,
        description="Random seed for reproducible sampling.",
    )  # For reproducibility control


class ProstT5GenerateRequestItemAA(RequestModel):
    sequence: Annotated[
        str,
        BeforeValidator(validate_aa_extended),
        Field(
            ...,
            min_length=1,
            max_length=ProstT5GenerateParams.max_sequence_len,
            description="A protein sequence in single-letter amino-acid codes.",
        ),
    ]


class ProstT5GenerateRequestAA(RequestModel):
    params: ProstT5GenerateParamsAA = Field(
        default_factory=ProstT5GenerateParamsAA,
        description="Optional parameters controlling this action (defaults are used when omitted).",
    )
    items: Annotated[
        list[ProstT5GenerateRequestItemAA],
        Field(
            min_length=1,
            max_length=ProstT5GenerateParams.batch_size,
            description="Batch of inputs to process in a single request. Up to 2 sequences per request.",
        ),
    ]


class ProstT5GenerateParamsFold(RequestModel):  # fold2AA
    temperature: float = Field(
        default=1.0,
        ge=0.0,
        le=8.0,
        description="Sampling temperature; higher values increase diversity.",
    )
    top_p: float = Field(
        default=0.85,
        ge=0.0,
        le=1.0,
        description="Nucleus (top-p) sampling threshold.",
    )
    top_k: int = Field(
        default=3,
        ge=1,
        le=20,
        description="Top-k sampling cutoff; only the k most likely tokens are sampled.",
    )
    repetition_penalty: float = Field(
        default=1.2,
        ge=0.0,
        le=3.0,
        description="Repetition penalty applied during generation; values > 1.0 discourage repeated tokens.",
    )
    num_samples: int = Field(
        default=1,
        ge=1,
        le=3,
        description="Number of sequences to generate per input.",
    )
    seed: int | None = Field(
        default=None,
        description="Random seed for reproducible sampling.",
    )  # For reproducibility control


class ProstT5GenerateRequestItemFold(RequestModel):
    sequence: Annotated[
        str,
        BeforeValidator(validate_prostt5_3di),
        Field(
            ...,
            min_length=1,
            max_length=ProstT5GenerateParams.max_sequence_len,
            description="A 3Di structural token sequence in Foldseek's lowercase 20-letter alphabet.",
        ),
    ]


class ProstT5GenerateRequestFold(RequestModel):
    params: ProstT5GenerateParamsFold = Field(
        default_factory=ProstT5GenerateParamsFold,
        description="Optional parameters controlling this action (defaults are used when omitted).",
    )
    items: Annotated[
        list[ProstT5GenerateRequestItemFold],
        Field(
            min_length=1,
            max_length=ProstT5GenerateParams.batch_size,
            description="Batch of inputs to process in a single request. Up to 2 sequences per request.",
        ),
    ]


### ProstT5 Generate Response


class ProstT5GenerateResponseGenerated(RequestModel):
    sequence: str = Field(
        description="A generated sequence in the target alphabet (uppercase amino acids for fold2AA; lowercase 3Di tokens for AA2fold).",
    )


ProstT5GenerateResponseResult = list[ProstT5GenerateResponseGenerated]


class ProstT5GenerateResponse(ResponseModel):
    results: list[ProstT5GenerateResponseResult] = Field(
        description="Per-input results, returned in the same order as the request items."
    )
