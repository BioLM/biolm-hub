from functools import partial
from typing import Annotated, Optional

from pydantic import BeforeValidator, Field, field_validator

from models.commons.data.validator import (
    AAExtendedPlusExtra,
    SingleOrMoreOccurrencesOf,
    validate_aa_extended,
    validate_aa_unambiguous,
)
from models.commons.model.base import ModelParams
from models.commons.model.pydantic import (
    EnhancedStringEnum,
    RequestModel,
    ResponseModel,
)

### E1 Model Parameters


class E1Params(ModelParams):
    params_version = "v1"
    display_name = "E1"
    base_model_slug = "e1"
    log_identifier = "E1"
    batch_size = 8
    max_sequence_len = 2048
    # Paper states E1 supports up to 512 context sequences; limited to 50 for practical use
    max_context_sequences = 50


class E1ModelSizes(EnhancedStringEnum):
    SIZE_150M = "150m"
    SIZE_300M = "300m"
    SIZE_600M = "600m"


### E1 Requests


class E1EncodeIncludeOptions(EnhancedStringEnum):
    MEAN = "mean"
    PER_TOKEN = "per_token"
    LOGITS = "logits"


class E1EncodeRequestParams(RequestModel):
    repr_layers: list[int] = Field(default_factory=partial(list, [-1]))
    include: list[E1EncodeIncludeOptions] = Field(
        default_factory=partial(list, [E1EncodeIncludeOptions.MEAN])
    )


class E1EncodeRequestItem(RequestModel):
    """Single item for encoding.

    E1 supports retrieval-augmented inference where context sequences (homologs)
    can be prepended to the query sequence to improve predictions.

    Args:
        sequence: The query sequence to encode (required). Accepts extended
            amino acid alphabet (ACDEFGHIKLMNPQRSTVWY + BXZUO).
        context_sequences: Optional list of homologous sequences for context.
            These are prepended to the query and the model uses block-causal
            attention to condition the query on the context. Each context
            sequence must also be a valid amino acid sequence.
    """

    sequence: Annotated[
        str,
        BeforeValidator(validate_aa_extended),
        Field(..., min_length=1, max_length=E1Params.max_sequence_len),
    ]
    context_sequences: Optional[list[str]] = Field(
        default=None, max_length=E1Params.max_context_sequences
    )

    @field_validator("context_sequences")
    @classmethod
    def validate_context_sequences(cls, v: list[str] | None) -> list[str] | None:
        """Validate each context sequence for AA content and length."""
        if v is None:
            return v
        for i, seq in enumerate(v):
            if len(seq) < 1:
                raise ValueError(f"Context sequence {i} is empty")
            if len(seq) > E1Params.max_sequence_len:
                raise ValueError(
                    f"Context sequence {i} exceeds max length {E1Params.max_sequence_len}"
                )
            validate_aa_extended(seq)
        return v


class E1EncodeRequest(RequestModel):
    params: E1EncodeRequestParams = E1EncodeRequestParams()
    items: Annotated[
        list[E1EncodeRequestItem],
        Field(min_length=1, max_length=E1Params.batch_size),
    ]


class E1PredictRequestItem(RequestModel):
    """Single item for masked prediction.

    Args:
        sequence: Sequence with '?' tokens marking positions to predict.
            Only the query sequence may contain mask tokens.
        context_sequences: Optional list of homologous sequences for context.
            Context sequences must NOT contain '?' mask tokens.
    """

    sequence: Annotated[
        str,
        BeforeValidator(AAExtendedPlusExtra(extra=["?"])),
        BeforeValidator(SingleOrMoreOccurrencesOf("?")),
        Field(..., min_length=1, max_length=E1Params.max_sequence_len),
    ]
    context_sequences: Optional[list[str]] = Field(
        default=None, max_length=E1Params.max_context_sequences
    )

    @field_validator("context_sequences")
    @classmethod
    def validate_context_sequences(cls, v: list[str] | None) -> list[str] | None:
        """Validate context sequences: AA content, length, and no mask tokens."""
        if v is None:
            return v
        for i, seq in enumerate(v):
            if len(seq) < 1:
                raise ValueError(f"Context sequence {i} is empty")
            if len(seq) > E1Params.max_sequence_len:
                raise ValueError(
                    f"Context sequence {i} exceeds max length {E1Params.max_sequence_len}"
                )
            if "?" in seq:
                raise ValueError(
                    f"Context sequence {i} contains '?' mask token; "
                    "only the query sequence may contain masks"
                )
            validate_aa_extended(seq)
        return v


class E1PredictRequest(RequestModel):
    items: Annotated[
        list[E1PredictRequestItem],
        Field(min_length=1, max_length=E1Params.batch_size),
    ]


class E1PredictLogProbRequestItem(RequestModel):
    """Single item for log probability prediction.

    Args:
        sequence: The query sequence to score. Must contain only the 20
            canonical amino acids (ACDEFGHIKLMNPQRSTVWY).
        context_sequences: Optional list of homologous sequences for context.
            When provided, the model conditions on these sequences using
            block-causal attention, typically improving fitness predictions.
            Context sequences must also use only canonical amino acids.
    """

    sequence: Annotated[
        str,
        BeforeValidator(validate_aa_unambiguous),
        Field(..., min_length=1, max_length=E1Params.max_sequence_len),
    ]
    context_sequences: Optional[list[str]] = Field(
        default=None, max_length=E1Params.max_context_sequences
    )

    @field_validator("context_sequences")
    @classmethod
    def validate_context_sequences(cls, v: list[str] | None) -> list[str] | None:
        """Validate context sequences: canonical AAs only, length constraints."""
        if v is None:
            return v
        for i, seq in enumerate(v):
            if len(seq) < 1:
                raise ValueError(f"Context sequence {i} is empty")
            if len(seq) > E1Params.max_sequence_len:
                raise ValueError(
                    f"Context sequence {i} exceeds max length {E1Params.max_sequence_len}"
                )
            validate_aa_unambiguous(seq)
        return v


class E1PredictLogProbRequest(RequestModel):
    items: Annotated[
        list[E1PredictLogProbRequestItem],
        Field(min_length=1, max_length=E1Params.batch_size),
    ]


### E1 Responses


class LayerEmbedding(ResponseModel):
    """Embedding vector for a single layer."""

    layer: int
    embedding: list[float]


class LayerPerTokenEmbeddings(ResponseModel):
    """Per-token embedding vectors for a single layer."""

    layer: int
    embeddings: list[list[float]]


class E1EncodeResponseResult(ResponseModel):
    """Response result for a single encoded sequence."""

    model_config = {
        "populate_by_name": True,
        "json_schema_extra": {
            "exclude_unset": True,
            "exclude_none": True,
        },
    }

    embeddings: Optional[list[LayerEmbedding]] = None
    per_token_embeddings: Optional[list[LayerPerTokenEmbeddings]] = None
    logits: Optional[list[list[float]]] = None
    vocab_tokens: Optional[list[str]] = None  # Included when logits requested
    context_sequence_count: Optional[int] = None  # Number of context sequences


class E1EncodeResponse(ResponseModel):
    results: list[E1EncodeResponseResult]


class E1PredictResponseResult(ResponseModel):
    logits: list[list[float]]
    sequence_tokens: list[str]
    vocab_tokens: list[str]


class E1PredictResponse(ResponseModel):
    results: list[E1PredictResponseResult]


class E1PredictLogProbResponseResult(ResponseModel):
    log_prob: float


class E1PredictLogProbResponse(ResponseModel):
    results: list[E1PredictLogProbResponseResult]
