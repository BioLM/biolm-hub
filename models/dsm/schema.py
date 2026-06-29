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
    weights_version = "v1"
    display_name = "DSM"
    base_model_slug = "dsm"
    log_identifier = "DSM"
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
        default=1, ge=1, le=32, description="Number of sequences to generate per input."
    )
    temperature: float = Field(
        default=1.0,
        ge=0.1,
        le=2.0,
        description="Sampling temperature; higher values increase diversity.",
    )
    max_length: Optional[int] = Field(
        default=None,
        ge=10,
        le=2048,
        description=(
            "Canvas size (number of mask tokens) for unconditional generation when "
            "sequence is empty. Defaults to 100 if not specified. "
            "Ignored for masked infilling and conditional modes, where generation "
            "length is determined by the number of <mask> tokens in the input."
        ),
    )
    step_divisor: int = Field(
        default=100,
        ge=1,
        le=1000,
        description="Diffusion step divisor; lower values yield more denoising steps and better quality at higher compute cost.",
    )
    remasking: DSMRemaskingStrategy = Field(
        default=DSMRemaskingStrategy.RANDOM,
        description="Remasking strategy controlling which positions are re-masked between diffusion steps.",
    )
    seed: Optional[int] = Field(
        default=None,
        description="Random seed for reproducible sampling.",
    )


class DSMGenerateRequestItem(RequestModel):
    """Single input for DSM generation - can be masked or empty for unconditional."""

    sequence: Annotated[
        str,
        BeforeValidator(validate_dsm_sequence),
        Field(
            default="",
            max_length=DSMParams.max_sequence_len,
            description=(
                "Input sequence. Three modes: "
                "(1) empty string — unconditional generation; the model creates a canvas of "
                "`max_length` mask tokens (default 100) and denoises them; "
                "(2) sequence containing `<mask>` tokens — masked infilling; the model fills "
                "only the masked positions; output length equals the number of tokens in the input; "
                "(3) plain amino-acid prefix — conditional generation from the prefix; "
                "the model denoises any remaining context."
            ),
        ),
    ]


class DSMGenerateRequest(RequestModel):
    """Request for DSM sequence generation."""

    params: DSMGenerateRequestParams = Field(
        default_factory=DSMGenerateRequestParams,
        description="Optional parameters controlling this action (defaults are used when omitted).",
    )
    items: Annotated[
        list[DSMGenerateRequestItem],
        Field(
            min_length=1,
            max_length=DSMParams.generate_batch_size,
            description="Batch of inputs to process in a single request. Up to 1 sequence per request.",
        ),
    ]


### DSM Encode Request


class DSMEncodeIncludeOptions(EnhancedStringEnum):
    MEAN = "mean"  # Mean pooled embedding
    PER_RESIDUE = "per_residue"  # Per-residue embeddings
    CLS = "cls"  # CLS token embedding


class DSMEncodeRequestParams(RequestModel):
    include: list[DSMEncodeIncludeOptions] = Field(
        default_factory=partial(list, [DSMEncodeIncludeOptions.MEAN]),
        description="Optional outputs to compute and include in the response.",
    )


class DSMEncodeRequestItem(RequestModel):
    sequence: Annotated[
        str,
        BeforeValidator(AAExtendedPlusExtra(extra=["-"])),
        Field(
            ...,
            min_length=1,
            max_length=DSMParams.max_sequence_len,
            description="A protein sequence in single-letter amino-acid codes.",
        ),
    ]


class DSMEncodeRequest(RequestModel):
    params: DSMEncodeRequestParams = Field(
        default_factory=DSMEncodeRequestParams,
        description="Optional parameters controlling this action (defaults are used when omitted).",
    )
    items: Annotated[
        list[DSMEncodeRequestItem],
        Field(
            min_length=1,
            max_length=DSMParams.encode_batch_size,
            description="Batch of inputs to process in a single request. Up to 16 sequences per request.",
        ),
    ]


### DSM Score Request


class DSMScoreRequestItem(RequestModel):
    sequence: Annotated[
        str,
        BeforeValidator(validate_aa_unambiguous),
        Field(
            ...,
            min_length=1,
            max_length=DSMParams.max_sequence_len,
            description="A protein sequence in single-letter amino-acid codes.",
        ),
    ]


class DSMScoreRequest(RequestModel):
    items: Annotated[
        list[DSMScoreRequestItem],
        Field(
            min_length=1,
            max_length=DSMParams.encode_batch_size,
            description="Batch of inputs to process in a single request. Up to 16 sequences per request.",
        ),
    ]


### DSM Responses


class DSMGenerateResponseResult(ResponseModel):
    """Result for a single generated sequence."""

    sequence: str = Field(
        description="Generated protein sequence in single-letter amino-acid codes."
    )
    log_prob: float = Field(
        description="Pseudo-log-likelihood of the sequence under the model."
    )
    perplexity: float = Field(
        description="Perplexity of the sequence under the model (lower means more likely)."
    )
    sequence2: Optional[str] = Field(
        default=None,
        description="Second generated sequence for PPI-variant outputs; None for base-model generations.",
    )


class DSMGenerateResponse(ResponseModel):
    results: list[list[DSMGenerateResponseResult]] = Field(
        description="Per-input results in request order. Each inner list contains num_sequences generated sequences.",
    )


class DSMEncodeResponseResult(ResponseModel):
    model_config = {
        "populate_by_name": True,  # Ensures alias names work as expected
    }

    sequence_index: int = Field(
        description="Index of the corresponding input sequence within the request batch."
    )
    embeddings: Optional[list[float]] = Field(
        default=None,
        description="Mean-pooled embedding vector for the sequence.",
    )
    per_residue_embeddings: Optional[list[list[float]]] = Field(
        default=None,
        description="Per-residue embedding vectors, shape [seq_len, hidden_dim].",
    )
    cls_embeddings: Optional[list[float]] = Field(
        default=None,
        description="CLS-token embedding vector for the sequence.",
    )


class DSMEncodeResponse(ResponseModel):
    results: list[DSMEncodeResponseResult] = Field(
        description="Per-input results, returned in the same order as the request items.",
    )


class DSMScoreResponseResult(ResponseModel):
    log_prob: float = Field(
        description="Pseudo-log-likelihood of the sequence under the model."
    )
    perplexity: float = Field(
        description="Perplexity of the sequence under the model (lower means more likely)."
    )
    sequence_length: int = Field(
        description="Length of the input sequence in amino acids."
    )


class DSMScoreResponse(ResponseModel):
    results: list[DSMScoreResponseResult] = Field(
        description="Per-input results, returned in the same order as the request items.",
    )
