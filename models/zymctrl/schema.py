import re
from typing import Annotated, Optional

from pydantic import BeforeValidator, Field, field_validator

from models.commons.data.validator import validate_aa_unambiguous
from models.commons.model.base import ModelParams
from models.commons.model.pydantic import (
    EnhancedStringEnum,
    RequestModel,
    ResponseModel,
)

### ZymCTRL Params


class ZymCTRLParams(ModelParams):
    display_name = "ZymCTRL"
    base_model_slug = "zymctrl"
    log_identifier = "ZymCTRL"
    params_version = "v1"
    batch_size = 1  # For generate (sequential, resource-intensive)
    batch_size_encode = 8  # For encode
    # 1024 matches the paper's block size and training window
    max_sequence_len = 1024


### EC Number Validation


EC_NUMBER_PATTERN = re.compile(r"^\d+(\.\d+){1,3}$")


def validate_ec_number(value: str) -> str:
    """Validate EC number format (e.g., '3.5.5.1' or partial like '3.5.5')."""
    value = value.strip()
    if not EC_NUMBER_PATTERN.match(value):
        raise ValueError(
            f"Invalid EC number format: '{value}'. "
            "Expected format: X.X.X.X (e.g., '3.5.5.1') or partial (e.g., '3.5')"
        )
    return value


### Pooling Options


class ZymCTRLPoolingType(EnhancedStringEnum):
    MEAN = "mean"
    LAST = "last"
    PER_TOKEN = "per_token"


### Generate Request/Response


class ZymCTRLGenerateParams(RequestModel):
    seed: Optional[int] = None  # For reproducibility control
    temperature: float = Field(default=0.8, ge=0.0, le=2.0)
    top_k: int = Field(default=9, ge=1, le=50)
    repetition_penalty: float = Field(default=1.2, ge=1.0, le=2.0)
    num_samples: int = Field(default=5, ge=1, le=20)
    max_length: int = Field(default=256, ge=50, le=ZymCTRLParams.max_sequence_len)


class ZymCTRLGenerateRequestItem(RequestModel):
    ec_number: str

    @field_validator("ec_number", mode="before")
    @classmethod
    def validate_ec(cls, v: str) -> str:
        return validate_ec_number(v)


class ZymCTRLGenerateRequest(RequestModel):
    params: ZymCTRLGenerateParams = ZymCTRLGenerateParams()
    items: Annotated[
        list[ZymCTRLGenerateRequestItem],
        Field(min_length=1, max_length=ZymCTRLParams.batch_size),
    ]


class ZymCTRLGenerateResponseGenerated(ResponseModel):
    sequence: str
    perplexity: float


ZymCTRLGenerateResponseResult = list[ZymCTRLGenerateResponseGenerated]


class ZymCTRLGenerateResponse(ResponseModel):
    results: list[ZymCTRLGenerateResponseResult]


### Encode Request/Response


class ZymCTRLEncodeParams(RequestModel):
    pooling: ZymCTRLPoolingType = Field(default=ZymCTRLPoolingType.MEAN)
    layer: int = Field(default=-1, ge=-36, le=36)


class ZymCTRLEncodeRequestItem(RequestModel):
    sequence: Annotated[
        str,
        BeforeValidator(validate_aa_unambiguous),
        Field(..., min_length=1, max_length=ZymCTRLParams.max_sequence_len),
    ]
    ec_number: Optional[str] = Field(default=None)

    @field_validator("ec_number", mode="before")
    @classmethod
    def validate_ec(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        return validate_ec_number(v)


class ZymCTRLEncodeRequest(RequestModel):
    params: ZymCTRLEncodeParams = ZymCTRLEncodeParams()
    items: Annotated[
        list[ZymCTRLEncodeRequestItem],
        Field(min_length=1, max_length=ZymCTRLParams.batch_size_encode),
    ]


class ZymCTRLEncodeResponseResult(ResponseModel):
    model_config = {
        "populate_by_name": True,
        "json_schema_extra": {
            "exclude_unset": True,
            "exclude_none": True,
        },
    }

    sequence_index: int
    embedding: Optional[list[float]] = None  # For mean/last pooling
    per_token_embeddings: Optional[list[list[float]]] = None  # For per_token


class ZymCTRLEncodeResponse(ResponseModel):
    results: list[ZymCTRLEncodeResponseResult]
