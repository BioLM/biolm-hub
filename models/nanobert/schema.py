from functools import partial
from typing import Annotated, Optional

from pydantic import (
    BeforeValidator,
    ConfigDict,
    Field,
)

from models.commons.data.validator import (
    AAUnambiguousPlusExtra,
    validate_aa_unambiguous,
)
from models.commons.model.base import ModelParams
from models.commons.model.pydantic import (
    EnhancedStringEnum,
    RequestModel,
    ResponseModel,
)

### NanoBERT Params


class NanoBERTParams(ModelParams):
    params_version = "v1"
    display_name = "NanoBERT"
    base_model_slug = "nanobert"
    log_identifier = "NanoBERT"
    batch_size = 32
    max_sequence_len = 154


### NanoBERT Request


class NanoBERTEncodeIncludeOptions(EnhancedStringEnum):
    MEAN = "mean"  # mean embedding (default)
    RESIDUE = "residue"  # per-residue embeddings
    LOGITS = "logits"  # logits


class NanoBERTEncodeRequestParams(RequestModel):
    include: list[NanoBERTEncodeIncludeOptions] = Field(
        default_factory=partial(list, [NanoBERTEncodeIncludeOptions.MEAN])
    )


class NanoBERTEncodeRequestItem(RequestModel):
    sequence: Annotated[
        str,
        BeforeValidator(validate_aa_unambiguous),
        Field(..., min_length=1, max_length=NanoBERTParams.max_sequence_len),
    ]


class NanoBERTEncodeRequest(RequestModel):
    params: NanoBERTEncodeRequestParams = Field(
        default_factory=NanoBERTEncodeRequestParams
    )
    items: list[NanoBERTEncodeRequestItem] = Field(
        min_length=1, max_length=NanoBERTParams.batch_size
    )


class NanoBERTGenerateRequestItem(RequestModel):
    """
    For generate(), we allow '*' placeholders inside the heavy/light sequences,
    which must still be valid length and contain at least 1 '*'.
    """

    sequence: Annotated[
        str,
        BeforeValidator(AAUnambiguousPlusExtra(extra=["*"])),
        Field(..., min_length=1, max_length=NanoBERTParams.max_sequence_len),
    ]


class NanoBERTGenerateRequest(RequestModel):
    items: list[NanoBERTGenerateRequestItem] = Field(
        min_length=1, max_length=NanoBERTParams.batch_size
    )


class NanoBERTLogProbRequest(RequestModel):
    items: list[NanoBERTEncodeRequestItem] = Field(
        min_length=1, max_length=NanoBERTParams.batch_size
    )


### NanoBERT Response


class NanoBERTEncodeResponseResult(ResponseModel):
    model_config = ConfigDict(
        exclude_unset=True,
        exclude_none=True,
        extra="forbid",
    )

    embeddings: Optional[list[float]] = None
    residue_embeddings: Optional[list[list[float]]] = None
    logits: Optional[list[list[float]]] = None


class NanoBERTEncodeResponse(ResponseModel):
    results: list[NanoBERTEncodeResponseResult]


class NanoBERTGenerateResponseResult(ResponseModel):
    sequence: str


class NanoBERTGenerateResponse(ResponseModel):
    results: list[NanoBERTGenerateResponseResult]


class NanoBERTLogProbResponseResult(ResponseModel):
    log_prob: float


class NanoBERTLogProbResponse(ResponseModel):
    results: list[NanoBERTLogProbResponseResult]
