from functools import partial
from typing import Annotated, Optional

from pydantic import BeforeValidator, Field

from models.commons.data.validator import (
    AAExtendedPlusExtra,
    validate_aa_unambiguous,
)
from models.commons.model.base import ModelParams
from models.commons.model.pydantic import (
    EnhancedStringEnum,
    RequestModel,
    ResponseModel,
)


def validate_dsm_sequence(value: str) -> str:
    """Validate DSM sequence that can contain mask tokens, eos tokens, or be empty."""
    if not value:  # Allow empty sequences
        return value

    # Remove special tokens and validate the remaining sequence
    remaining = value.replace("<mask>", "").replace("<eos>", "")
    # If there's something left after removing special tokens, validate it
    if remaining:
        validate_aa_unambiguous(remaining)

    return value


class DSMRemaskingStrategy(EnhancedStringEnum):
    """Remasking strategy for DSM generation."""

    LOW_CONFIDENCE = "low_confidence"
    RANDOM = "random"
    LOW_LOGIT = "low_logit"
    DUAL = "dual"


### DSM Model Parameters


class DSMParams(ModelParams):
    params_version = "v1"
    display_name = "DSM"
    base_model_slug = "dsm"
    log_identifier = "DSM"
    batch_size = 8
    max_sequence_len = 2048
    generate_batch_size = 1  # Generate limited to 1 due to diffusion cost
    encode_batch_size = 16  # Encode/score can handle larger batches


class DSMModelSizes(EnhancedStringEnum):
    SIZE_150M = "150m"
    SIZE_650M = "650m"
    SIZE_3B = "3b"


class DSMVariants(EnhancedStringEnum):
    BASE = "base"  # Standard protein generation
    PPI = "ppi"  # Protein-protein interaction focused


### DSM Generate Request


class DSMGenerateRequestParams(RequestModel):
    """Parameters for DSM generation."""

    num_sequences: int = Field(
        default=1, ge=1, le=32, description="Number of sequences to generate"
    )
    temperature: float = Field(
        default=1.0, ge=0.1, le=2.0, description="Sampling temperature"
    )
    top_k: Optional[int] = Field(
        default=None, ge=1, description="Top-k sampling (None = disabled)"
    )
    top_p: Optional[float] = Field(
        default=None, ge=0.0, le=1.0, description="Nucleus sampling (None = disabled)"
    )
    max_length: Optional[int] = Field(
        default=None,
        ge=10,
        le=2048,
        description="Max sequence length (None = from input)",
    )
    step_divisor: int = Field(
        default=100,
        ge=1,
        le=1000,
        description="Step divisor for diffusion (lower = slower but better quality)",
    )
    remasking: DSMRemaskingStrategy = Field(
        default=DSMRemaskingStrategy.RANDOM,
        description="Remasking strategy for diffusion",
    )
    seed: Optional[int] = Field(
        default=None,
        description="Random seed for reproducibility (None = time-based entropy)",
    )


class DSMGenerateRequestItem(RequestModel):
    """Single input for DSM generation - can be masked or empty for unconditional."""

    sequence: Annotated[
        str,
        BeforeValidator(validate_dsm_sequence),
        Field(default="", max_length=DSMParams.max_sequence_len),
    ]


class DSMGenerateRequest(RequestModel):
    """Request for DSM sequence generation."""

    params: DSMGenerateRequestParams = DSMGenerateRequestParams()
    items: Annotated[
        list[DSMGenerateRequestItem],
        Field(min_length=1, max_length=DSMParams.generate_batch_size),
    ]


### DSM Encode Request


class DSMEncodeIncludeOptions(EnhancedStringEnum):
    MEAN = "mean"  # Mean pooled embedding
    PER_RESIDUE = "per_residue"  # Per-residue embeddings
    CLS = "cls"  # CLS token embedding


class DSMEncodeRequestParams(RequestModel):
    include: list[DSMEncodeIncludeOptions] = Field(
        default_factory=partial(list, [DSMEncodeIncludeOptions.MEAN])
    )


class DSMEncodeRequestItem(RequestModel):
    sequence: Annotated[
        str,
        BeforeValidator(AAExtendedPlusExtra(extra=["-"])),
        Field(..., min_length=1, max_length=DSMParams.max_sequence_len),
    ]


class DSMEncodeRequest(RequestModel):
    params: DSMEncodeRequestParams = DSMEncodeRequestParams()
    items: Annotated[
        list[DSMEncodeRequestItem],
        Field(min_length=1, max_length=DSMParams.encode_batch_size),
    ]


### DSM Score Request


class DSMScoreRequestItem(RequestModel):
    sequence: Annotated[
        str,
        BeforeValidator(validate_aa_unambiguous),
        Field(..., min_length=1, max_length=DSMParams.max_sequence_len),
    ]


class DSMScoreRequest(RequestModel):
    items: Annotated[
        list[DSMScoreRequestItem],
        Field(min_length=1, max_length=DSMParams.encode_batch_size),
    ]


### DSM Responses


class DSMGenerateResponseResult(ResponseModel):
    """Result for a single generated sequence."""

    sequence: str
    log_prob: float  # Total log probability
    perplexity: float  # exp(-log_prob / length)
    sequence2: Optional[str] = None  # Second sequence for PPI models


class DSMGenerateResponse(ResponseModel):
    results: list[list[DSMGenerateResponseResult]]  # Nested: [batch][num_sequences]


class DSMEncodeResponseResult(ResponseModel):
    model_config = {
        "populate_by_name": True,  # Ensures alias names work as expected
        "json_schema_extra": {
            "exclude_unset": True,  # Excludes unset fields from JSON output
            "exclude_none": True,  # Ensures None fields do not appear in JSON
        },
    }

    sequence_index: int
    embeddings: Optional[list[float]] = None  # Mean pooled
    per_residue_embeddings: Optional[list[list[float]]] = None  # [seq_len, hidden_dim]
    cls_embeddings: Optional[list[float]] = None  # CLS token


class DSMEncodeResponse(ResponseModel):
    results: list[DSMEncodeResponseResult]


class DSMScoreResponseResult(ResponseModel):
    log_prob: float  # Total log probability
    perplexity: float  # exp(-log_prob / length)
    sequence_length: int


class DSMScoreResponse(ResponseModel):
    results: list[DSMScoreResponseResult]
