from functools import partial
from typing import Annotated, Optional

from pydantic import BeforeValidator, Field

from models.commons.data.validator import (
    AAExtendedPlusExtra,
)
from models.commons.model.base import ModelParams
from models.commons.model.pydantic import (
    EnhancedStringEnum,
    RequestModel,
    ResponseModel,
)

### TemBERTure Model Parameters


class TemBERTureParams(ModelParams):
    params_version = "v1"
    display_name = "TemBERTure"
    base_model_slug = "temberture"
    log_identifier = "TEMBERTURE"
    batch_size = 8
    max_sequence_len = 512


class TemBERTureModelTypes(EnhancedStringEnum):
    CLASSIFIER = "classifier"
    REGRESSION = "regression"


### TemBERTure Request


class TemBERTureEncodeIncludeOptions(EnhancedStringEnum):
    MEAN = "mean"  # mean embedding (default)
    PER_RESIDUE = "per_residue"  # per-residue embeddings
    CLS = "cls"  # CLS token embedding


class TemBERTureEncodeRequestParams(RequestModel):
    include: list[TemBERTureEncodeIncludeOptions] = Field(
        default_factory=partial(list, [TemBERTureEncodeIncludeOptions.MEAN])
    )


class TemBERTureEncodeRequestItem(RequestModel):
    sequence: Annotated[
        str,
        BeforeValidator(AAExtendedPlusExtra(extra=["-"])),
        Field(..., min_length=1, max_length=TemBERTureParams.max_sequence_len),
    ]


class TemBERTureEncodeRequest(RequestModel):
    params: TemBERTureEncodeRequestParams = TemBERTureEncodeRequestParams()
    items: Annotated[
        list[TemBERTureEncodeRequestItem],
        Field(min_length=1, max_length=TemBERTureParams.batch_size),
    ]


class TemBERTurePredictRequestItem(RequestModel):
    sequence: Annotated[
        str,
        BeforeValidator(AAExtendedPlusExtra(extra=["-"])),
        Field(..., min_length=1, max_length=TemBERTureParams.max_sequence_len),
    ]


class TemBERTurePredictRequest(RequestModel):
    items: Annotated[
        list[TemBERTurePredictRequestItem],
        Field(min_length=1, max_length=TemBERTureParams.batch_size),
    ]


### TemBERTure Response


class TemBERTureEncodeResponseResult(ResponseModel):
    model_config = {
        "populate_by_name": True,  # Ensures alias names work
        "json_schema_extra": {
            "exclude_unset": True,  # Excludes unset (None) fields from the output
            "exclude_none": True,  # Ensures that None fields do not appear in JSON
        },
    }

    sequence_index: int
    embeddings: Optional[list[float]] = None
    per_residue_embeddings: Optional[list[list[float]]] = None
    cls_embeddings: Optional[list[float]] = None


class TemBERTureEncodeResponse(ResponseModel):
    results: list[TemBERTureEncodeResponseResult]


class TemBERTurePredictResponseResult(ResponseModel):
    prediction: float
    classification: Optional[str] = None


class TemBERTurePredictResponse(ResponseModel):
    results: list[TemBERTurePredictResponseResult]
