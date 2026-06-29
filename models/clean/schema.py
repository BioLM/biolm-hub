from typing import Annotated, Optional

from pydantic import BeforeValidator, Field

from models.commons.data.validator import validate_aa_extended
from models.commons.model.base import ModelParams
from models.commons.model.pydantic import RequestModel, ResponseModel

### CLEAN Model Parameters


class CLEANParams(ModelParams):
    """CLEAN model parameters."""

    params_version = "v1"
    display_name = "CLEAN"
    base_model_slug = "clean"
    log_identifier = "CLEAN"
    batch_size = 10
    # ESM-1b has a hard limit of 1022 amino acids (1024 tokens with BOS/EOS)
    max_sequence_len = 1022


### CLEAN Requests


class CLEANPredictRequestParams(RequestModel):
    """Optional parameters for CLEAN prediction request."""

    max_predictions: int = Field(
        default=10,
        ge=1,
        le=20,
        description="Maximum number of EC predictions to return per sequence.",
    )
    min_confidence: float = Field(
        default=0.05,
        ge=0.0,
        le=1.0,
        description="Minimum confidence threshold to include a prediction.",
    )


class CLEANPredictRequestItem(RequestModel):
    """Single sequence item for CLEAN prediction."""

    sequence: Annotated[
        str,
        BeforeValidator(validate_aa_extended),
        Field(
            ...,
            min_length=1,
            max_length=CLEANParams.max_sequence_len,
            description="A protein sequence in single-letter amino-acid codes.",
        ),
    ]


class CLEANPredictRequest(RequestModel):
    """CLEAN prediction request."""

    params: Optional[CLEANPredictRequestParams] = Field(
        default=None,
        description="Optional parameters controlling this action (defaults are used when omitted).",
    )
    items: Annotated[
        list[CLEANPredictRequestItem],
        Field(
            min_length=1,
            max_length=CLEANParams.batch_size,
            description="Batch of inputs to process in a single request. Up to 10 sequences per request.",
        ),
    ]


class CLEANEncodeRequestItem(RequestModel):
    """Single sequence item for CLEAN encoding."""

    sequence: Annotated[
        str,
        BeforeValidator(validate_aa_extended),
        Field(
            ...,
            min_length=1,
            max_length=CLEANParams.max_sequence_len,
            description="A protein sequence in single-letter amino-acid codes.",
        ),
    ]


class CLEANEncodeRequest(RequestModel):
    """CLEAN encoding request."""

    items: Annotated[
        list[CLEANEncodeRequestItem],
        Field(
            min_length=1,
            max_length=CLEANParams.batch_size,
            description="Batch of inputs to process in a single request. Up to 10 sequences per request.",
        ),
    ]


### CLEAN Responses


class ECPrediction(ResponseModel):
    """Single EC number prediction with confidence."""

    ec_number: str = Field(
        ...,
        description="Predicted Enzyme Commission (EC) number.",
    )
    distance: float = Field(
        ...,
        description="Euclidean distance to the predicted EC cluster center (lower means more similar to known enzymes of that class).",
    )
    confidence: float = Field(
        ...,
        description="GMM-based confidence score (0–1; higher means more confident in the EC prediction).",
    )


class CLEANPredictResult(ResponseModel):
    """Prediction results for a single sequence."""

    predictions: list[ECPrediction] = Field(
        ...,
        description="List of predicted EC numbers, ordered by distance (closest first).",
    )


class CLEANPredictResponse(ResponseModel):
    """CLEAN prediction response."""

    results: list[CLEANPredictResult] = Field(
        description="Per-input results, returned in the same order as the request items.",
    )


class CLEANEncodeResult(ResponseModel):
    """Encoding result for a single sequence."""

    embedding: list[float] = Field(
        ...,
        description="128-dimensional CLEAN functional embedding, projected from ESM-1b mean-pooled features.",
    )


class CLEANEncodeResponse(ResponseModel):
    """CLEAN encoding response."""

    results: list[CLEANEncodeResult] = Field(
        description="Per-input results, returned in the same order as the request items.",
    )
