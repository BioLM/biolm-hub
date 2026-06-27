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
        description="Maximum number of EC predictions to return per sequence",
    )
    min_confidence: float = Field(
        default=0.05,
        ge=0.0,
        le=1.0,
        description="Minimum confidence threshold to include a prediction",
    )


class CLEANPredictRequestItem(RequestModel):
    """Single sequence item for CLEAN prediction."""

    sequence: Annotated[
        str,
        BeforeValidator(validate_aa_extended),
        Field(..., min_length=1, max_length=CLEANParams.max_sequence_len),
    ]


class CLEANPredictRequest(RequestModel):
    """CLEAN prediction request."""

    params: Optional[CLEANPredictRequestParams] = None
    items: Annotated[
        list[CLEANPredictRequestItem],
        Field(min_length=1, max_length=CLEANParams.batch_size),
    ]


class CLEANEncodeRequestItem(RequestModel):
    """Single sequence item for CLEAN encoding."""

    sequence: Annotated[
        str,
        BeforeValidator(validate_aa_extended),
        Field(..., min_length=1, max_length=CLEANParams.max_sequence_len),
    ]


class CLEANEncodeRequest(RequestModel):
    """CLEAN encoding request."""

    items: Annotated[
        list[CLEANEncodeRequestItem],
        Field(min_length=1, max_length=CLEANParams.batch_size),
    ]


### CLEAN Responses


class ECPrediction(ResponseModel):
    """Single EC number prediction with confidence."""

    ec_number: str = Field(
        ...,
        description="Predicted EC number (e.g., '3.5.2.6')",
    )
    distance: float = Field(
        ...,
        description="Euclidean distance to EC cluster center (lower = more similar)",
    )
    confidence: float = Field(
        ...,
        description="GMM-based confidence score (0-1, higher = more confident)",
    )


class CLEANPredictResult(ResponseModel):
    """Prediction results for a single sequence."""

    predictions: list[ECPrediction] = Field(
        ...,
        description="List of predicted EC numbers, ordered by distance (closest first)",
    )


class CLEANPredictResponse(ResponseModel):
    """CLEAN prediction response."""

    results: list[CLEANPredictResult]


class CLEANEncodeResult(ResponseModel):
    """Encoding result for a single sequence."""

    embedding: list[float] = Field(
        ...,
        description="128-dimensional CLEAN embedding",
    )


class CLEANEncodeResponse(ResponseModel):
    """CLEAN encoding response."""

    results: list[CLEANEncodeResult]
