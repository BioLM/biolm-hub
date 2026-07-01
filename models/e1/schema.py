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
    weights_version = "v1"
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


def _validate_context_list(
    v: list[str] | None,
    *,
    residue_validator,
    forbid_mask: bool = False,
) -> list[str] | None:
    """Shared validation logic for all context_sequences field_validators.

    Args:
        v: The list of context sequences (or None).
        residue_validator: Callable that validates a single sequence string.
        forbid_mask: If True, raise if any sequence contains a '?' mask token.
    """
    if v is None:
        return v
    for i, seq in enumerate(v):
        if len(seq) < 1:
            raise ValueError(f"Context sequence {i} is empty")
        if len(seq) > E1Params.max_sequence_len:
            raise ValueError(
                f"Context sequence {i} exceeds max length {E1Params.max_sequence_len}"
            )
        if forbid_mask and "?" in seq:
            raise ValueError(
                f"Context sequence {i} contains '?' mask token; "
                "only the query sequence may contain masks"
            )
        residue_validator(seq)
    return v


### E1 Requests


class E1EncodeIncludeOptions(EnhancedStringEnum):
    MEAN = "mean"
    PER_TOKEN = "per_token"
    LOGITS = "logits"


class E1EncodeRequestParams(RequestModel):
    repr_layers: list[int] = Field(
        default_factory=partial(list, [-1]),
        description="Hidden layers whose representations to return (negative indexes count from the last layer).",
    )
    include: list[E1EncodeIncludeOptions] = Field(
        default_factory=partial(list, [E1EncodeIncludeOptions.MEAN]),
        description="Optional outputs to compute and include in the response.",
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
        Field(
            ...,
            min_length=1,
            max_length=E1Params.max_sequence_len,
            description="A protein sequence in single-letter amino-acid codes (extended alphabet: standard 20 + B/X/Z/U/O).",
        ),
    ]
    context_sequences: Optional[list[str]] = Field(
        default=None,
        max_length=E1Params.max_context_sequences,
        description="Optional homologous sequences to condition inference via block-causal attention; up to 50 sequences allowed.",
    )

    @field_validator("context_sequences")
    @classmethod
    def validate_context_sequences(cls, v: list[str] | None) -> list[str] | None:
        """Validate each context sequence for AA content and length."""
        return _validate_context_list(v, residue_validator=validate_aa_extended)


class E1EncodeRequest(RequestModel):
    params: E1EncodeRequestParams = Field(
        default_factory=E1EncodeRequestParams,
        description="Optional parameters controlling this action (defaults are used when omitted).",
    )
    items: Annotated[
        list[E1EncodeRequestItem],
        Field(
            min_length=1,
            max_length=E1Params.batch_size,
            description="Batch of inputs to process in a single request. Up to 8 sequences per request.",
        ),
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
        Field(
            ...,
            min_length=1,
            max_length=E1Params.max_sequence_len,
            description="A protein sequence with one or more '?' mask tokens marking positions to predict.",
        ),
    ]
    context_sequences: Optional[list[str]] = Field(
        default=None,
        max_length=E1Params.max_context_sequences,
        description="Optional homologous sequences for context; no '?' mask tokens allowed in context sequences.",
    )

    @field_validator("context_sequences")
    @classmethod
    def validate_context_sequences(cls, v: list[str] | None) -> list[str] | None:
        """Validate context sequences: AA content, length, and no mask tokens."""
        return _validate_context_list(
            v, residue_validator=validate_aa_extended, forbid_mask=True
        )


class E1PredictRequest(RequestModel):
    items: Annotated[
        list[E1PredictRequestItem],
        Field(
            min_length=1,
            max_length=E1Params.batch_size,
            description="Batch of inputs to process in a single request. Up to 8 sequences per request.",
        ),
    ]


class E1LogProbRequestItem(RequestModel):
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
        Field(
            ...,
            min_length=1,
            max_length=E1Params.max_sequence_len,
            description="A protein sequence in the 20 canonical amino-acid codes to score.",
        ),
    ]
    context_sequences: Optional[list[str]] = Field(
        default=None,
        max_length=E1Params.max_context_sequences,
        description="Optional homologous sequences to condition scoring via block-causal attention; up to 50 sequences allowed.",
    )

    @field_validator("context_sequences")
    @classmethod
    def validate_context_sequences(cls, v: list[str] | None) -> list[str] | None:
        """Validate context sequences: canonical AAs only, length constraints."""
        return _validate_context_list(v, residue_validator=validate_aa_unambiguous)


class E1LogProbRequest(RequestModel):
    items: Annotated[
        list[E1LogProbRequestItem],
        Field(
            min_length=1,
            max_length=E1Params.batch_size,
            description="Batch of inputs to process in a single request. Up to 8 sequences per request.",
        ),
    ]


### E1 Responses


class LayerEmbedding(ResponseModel):
    """Embedding vector for a single layer."""

    layer: int = Field(description="Model layer this representation was taken from.")
    embedding: list[float] = Field(
        description="Mean-pooled embedding vector for the sequence."
    )


class LayerPerTokenEmbeddings(ResponseModel):
    """Per-token embedding vectors for a single layer."""

    layer: int = Field(description="Model layer this representation was taken from.")
    embeddings: list[list[float]] = Field(
        description="Per-token embedding vectors for the sequence at this layer."
    )


class E1EncodeResponseResult(ResponseModel):
    """Response result for a single encoded sequence."""

    model_config = {
        "populate_by_name": True,
        "json_schema_extra": {
            "exclude_unset": True,
            "exclude_none": True,
        },
    }

    embeddings: Optional[list[LayerEmbedding]] = Field(
        default=None,
        description="Per-layer mean-pooled embedding vectors for the query sequence.",
    )
    per_token_embeddings: Optional[list[LayerPerTokenEmbeddings]] = Field(
        default=None,
        description="Per-residue (per-token) embedding vectors.",
    )
    logits: Optional[list[list[float]]] = Field(
        default=None,
        description="Per-position logits over the model vocabulary.",
    )
    vocab_tokens: Optional[list[str]] = Field(
        default=None,
        description="Vocabulary token order corresponding to the logits columns.",
    )
    context_sequence_count: Optional[int] = Field(
        default=None,
        description="Number of context sequences used to condition this prediction.",
    )


class E1EncodeResponse(ResponseModel):
    results: list[E1EncodeResponseResult] = Field(
        description="Per-input results, returned in the same order as the request items.",
    )


class E1PredictResponseResult(ResponseModel):
    logits: list[list[float]] = Field(
        description="Per-position logits over the model vocabulary.",
    )
    sequence_tokens: list[str] = Field(
        description="Per-position input tokens, aligned with the logits.",
    )
    vocab_tokens: list[str] = Field(
        description="Vocabulary token order corresponding to the logits columns.",
    )


class E1PredictResponse(ResponseModel):
    results: list[E1PredictResponseResult] = Field(
        description="Per-input results, returned in the same order as the request items.",
    )


class E1LogProbResponseResult(ResponseModel):
    log_prob: float = Field(
        description="Pseudo-log-likelihood of the sequence under the model.",
    )


class E1LogProbResponse(ResponseModel):
    results: list[E1LogProbResponseResult] = Field(
        description="Per-input results, returned in the same order as the request items.",
    )
