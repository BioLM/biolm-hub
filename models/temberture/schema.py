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
        default_factory=partial(list, [TemBERTureEncodeIncludeOptions.MEAN]),
        description="Optional outputs to compute and include in the response.",
    )


class TemBERTureEncodeRequestItem(RequestModel):
    sequence: Annotated[
        str,
        BeforeValidator(AAExtendedPlusExtra(extra=["-"])),
        Field(
            ...,
            min_length=1,
            max_length=TemBERTureParams.max_sequence_len,
            description="A protein sequence in single-letter amino-acid codes.",
        ),
    ]


class TemBERTureEncodeRequest(RequestModel):
    params: TemBERTureEncodeRequestParams = Field(
        default_factory=TemBERTureEncodeRequestParams,
        description="Optional parameters controlling this action (defaults are used when omitted).",
    )
    items: Annotated[
        list[TemBERTureEncodeRequestItem],
        Field(
            min_length=1,
            max_length=TemBERTureParams.batch_size,
            description="Batch of inputs to process in a single request. Up to 8 sequences per request.",
        ),
    ]


class TemBERTurePredictRequestItem(RequestModel):
    sequence: Annotated[
        str,
        BeforeValidator(AAExtendedPlusExtra(extra=["-"])),
        Field(
            ...,
            min_length=1,
            max_length=TemBERTureParams.max_sequence_len,
            description="A protein sequence in single-letter amino-acid codes.",
        ),
    ]


class TemBERTurePredictRequest(RequestModel):
    items: Annotated[
        list[TemBERTurePredictRequestItem],
        Field(
            min_length=1,
            max_length=TemBERTureParams.batch_size,
            description="Batch of inputs to process in a single request. Up to 8 sequences per request.",
        ),
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

    sequence_index: int = Field(
        description="Index of the corresponding input sequence within the request batch.",
    )
    embeddings: Optional[list[float]] = Field(
        default=None,
        description="Mean-pooled embedding vector for the sequence (present when 'mean' is requested).",
    )
    per_residue_embeddings: Optional[list[list[float]]] = Field(
        default=None,
        description="Per-residue embedding vectors (present when 'per_residue' is requested).",
    )
    cls_embeddings: Optional[list[float]] = Field(
        default=None,
        description="CLS token embedding vector from the ProtBERT encoder (present when 'cls' is requested).",
    )


class TemBERTureEncodeResponse(ResponseModel):
    results: list[TemBERTureEncodeResponseResult] = Field(
        description="Per-input results, returned in the same order as the request items.",
    )


class TemBERTurePredictResponseResult(ResponseModel):
    prediction: float = Field(
        description="Thermophilicity probability (0-1) in classifier mode, or melting temperature in degrees C in regression mode.",
    )
    classification: Optional[str] = Field(
        default=None,
        description="Thermophilicity label ('Thermophilic' or 'Non-thermophilic'); present only for the classifier variant.",
    )


class TemBERTurePredictResponse(ResponseModel):
    results: list[TemBERTurePredictResponseResult] = Field(
        description="Per-input results, returned in the same order as the request items.",
    )
