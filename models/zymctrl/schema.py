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
    seed: Optional[int] = Field(
        default=None,
        description="Random seed for reproducible sampling.",
    )
    temperature: float = Field(
        default=0.8,
        gt=0.0,
        le=2.0,
        description="Sampling temperature; higher values increase diversity.",
    )
    top_k: int = Field(
        default=9,
        ge=1,
        le=50,
        description="Top-k sampling cutoff; only the k most likely tokens are sampled.",
    )
    repetition_penalty: float = Field(
        default=1.2,
        ge=1.0,
        le=2.0,
        description="Penalty applied to previously generated tokens to discourage repetitive sequences; higher values reduce repetition.",
    )
    num_samples: int = Field(
        default=5,
        ge=1,
        le=20,
        description="Number of sequences to generate per input.",
    )
    max_length: int = Field(
        default=256,
        ge=50,
        le=ZymCTRLParams.max_sequence_len,
        description="Maximum length of the generated sequence.",
    )


class ZymCTRLGenerateRequestItem(RequestModel):
    ec_number: str = Field(
        description="Enzyme Commission (EC) number conditioning generation (e.g. '1.1.1.1').",
    )

    @field_validator("ec_number", mode="before")
    @classmethod
    def validate_ec(cls, v: str) -> str:
        return validate_ec_number(v)


class ZymCTRLGenerateRequest(RequestModel):
    params: ZymCTRLGenerateParams = Field(
        default_factory=ZymCTRLGenerateParams,
        description="Optional parameters controlling this action (defaults are used when omitted).",
    )
    items: Annotated[
        list[ZymCTRLGenerateRequestItem],
        Field(
            min_length=1,
            max_length=ZymCTRLParams.batch_size,
            description="Batch of inputs to process in a single request. Up to 1 EC number per request.",
        ),
    ]


class ZymCTRLGenerateResponseGenerated(ResponseModel):
    sequence: str = Field(
        description="A protein sequence in single-letter amino-acid codes.",
    )
    perplexity: float = Field(
        description="Perplexity of the sequence under the model (lower means more likely).",
    )


ZymCTRLGenerateResponseResult = list[ZymCTRLGenerateResponseGenerated]


class ZymCTRLGenerateResponse(ResponseModel):
    results: list[ZymCTRLGenerateResponseResult] = Field(
        description="Per-input results, returned in the same order as the request items.",
    )


### Encode Request/Response


class ZymCTRLEncodeParams(RequestModel):
    pooling: ZymCTRLPoolingType = Field(
        default=ZymCTRLPoolingType.MEAN,
        description="Embedding pooling strategy: mean (average over residues), last (final token), or per_token (one embedding per residue).",
    )
    layer: int = Field(
        default=-1,
        ge=-36,
        le=36,
        description="Model layer this representation was taken from.",
    )


class ZymCTRLEncodeRequestItem(RequestModel):
    sequence: Annotated[
        str,
        BeforeValidator(validate_aa_unambiguous),
        Field(
            ...,
            min_length=1,
            max_length=ZymCTRLParams.max_sequence_len,
            description="A protein sequence in single-letter amino-acid codes.",
        ),
    ]
    ec_number: Optional[str] = Field(
        default=None,
        description="Optional EC number providing functional context for the embedding (e.g. '3.5.5.1').",
    )

    @field_validator("ec_number", mode="before")
    @classmethod
    def validate_ec(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        return validate_ec_number(v)


class ZymCTRLEncodeRequest(RequestModel):
    params: ZymCTRLEncodeParams = Field(
        default_factory=ZymCTRLEncodeParams,
        description="Optional parameters controlling this action (defaults are used when omitted).",
    )
    items: Annotated[
        list[ZymCTRLEncodeRequestItem],
        Field(
            min_length=1,
            max_length=ZymCTRLParams.batch_size_encode,
            description="Batch of inputs to process in a single request. Up to 8 sequences per request.",
        ),
    ]


class ZymCTRLEncodeResponseResult(ResponseModel):
    model_config = {
        "populate_by_name": True,
        "json_schema_extra": {
            "exclude_unset": True,
            "exclude_none": True,
        },
    }

    sequence_index: int = Field(
        description="Index of the corresponding input sequence within the request batch.",
    )
    embedding: Optional[list[float]] = Field(
        default=None,
        description="Embedding vector for the sequence; returned when pooling is 'mean' or 'last'.",
    )
    per_token_embeddings: Optional[list[list[float]]] = Field(
        default=None,
        description="Per-residue (per-token) embedding vectors.",
    )


class ZymCTRLEncodeResponse(ResponseModel):
    results: list[ZymCTRLEncodeResponseResult] = Field(
        description="Per-input results, returned in the same order as the request items.",
    )
