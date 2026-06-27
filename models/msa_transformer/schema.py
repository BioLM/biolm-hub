import re
from functools import partial
from typing import Annotated, Optional

from pydantic import BeforeValidator, Field

from models.commons.data.validator import aa_extended
from models.commons.model.base import ModelParams
from models.commons.model.pydantic import (
    EnhancedStringEnum,
    RequestModel,
    ResponseModel,
)

# MSA alphabet: extended AA + gap (-) + alignment insert (.)
msa_alphabet = aa_extended + "-."
msa_regex = re.compile(f"^[{re.escape(msa_alphabet)}]+$")


def validate_msa_sequence(text: str) -> str:
    """Validate a single MSA sequence."""
    if not msa_regex.match(text):
        raise ValueError(
            f"MSA sequences can only contain characters from: '{msa_alphabet}'"
        )
    return text


class ValidateMSA:
    """Validator for MSA input: list of aligned sequences."""

    def __init__(self, max_seq_len: int):
        self.max_seq_len = max_seq_len

    def __call__(self, value: list[str]) -> list[str]:
        if not value:
            raise ValueError("MSA cannot be empty")

        # Check all sequences have same length
        first_len = len(value[0])
        for i, seq in enumerate(value):
            if len(seq) != first_len:
                raise ValueError(
                    f"All MSA sequences must have same length. "
                    f"Sequence 0 has length {first_len}, but sequence {i} has length {len(seq)}"
                )
            if len(seq) > self.max_seq_len:
                raise ValueError(
                    f"Sequence length {len(seq)} exceeds maximum of {self.max_seq_len}"
                )
            # Validate each sequence's characters
            validate_msa_sequence(seq)

        return value


class MSATransformerParams(ModelParams):
    """Parameters for MSA Transformer model."""

    params_version = "v1"
    display_name = "MSA Transformer"
    base_model_slug = "msa-transformer"
    log_identifier = "MSA-Transformer"
    batch_size = 4
    max_sequence_len = 1024
    max_msa_depth = 256


class MSATransformerEncodeIncludeOptions(EnhancedStringEnum):
    """Options for what to include in encode response."""

    MEAN = "mean"  # Mean embedding of query sequence
    PER_TOKEN = "per_token"  # Per-position embeddings of query sequence
    ROW_ATTENTION = "row_attention"  # Tied row attention maps
    CONTACTS = "contacts"  # Contact predictions from attention


class MSATransformerEncodeRequestParams(RequestModel):
    """Parameters for encode request."""

    repr_layers: list[int] = Field(default_factory=partial(list, [-1]))
    include: list[MSATransformerEncodeIncludeOptions] = Field(
        default_factory=partial(list, [MSATransformerEncodeIncludeOptions.MEAN])
    )


class MSATransformerEncodeRequestItem(RequestModel):
    """Single MSA input item."""

    msa: Annotated[
        list[str],
        BeforeValidator(ValidateMSA(max_seq_len=MSATransformerParams.max_sequence_len)),
        Field(
            ...,
            min_length=2,
            max_length=MSATransformerParams.max_msa_depth,
            description="List of aligned sequences. First sequence is the query.",
        ),
    ]


class MSATransformerEncodeRequest(RequestModel):
    """Request for MSA Transformer encode action."""

    params: MSATransformerEncodeRequestParams = MSATransformerEncodeRequestParams()
    items: Annotated[
        list[MSATransformerEncodeRequestItem],
        Field(min_length=1, max_length=MSATransformerParams.batch_size),
    ]


class LayerEmbedding(ResponseModel):
    """Embedding for a specific layer."""

    layer: int
    embedding: list[float]


class LayerPerTokenEmbeddings(ResponseModel):
    """Per-token embeddings for a specific layer."""

    layer: int
    embeddings: list[list[float]]


class MSATransformerEncodeResponseResult(ResponseModel):
    """Result for a single MSA encode."""

    model_config = {
        "populate_by_name": True,
        "json_schema_extra": {
            "exclude_unset": True,
            "exclude_none": True,
        },
    }

    sequence_index: int
    embeddings: Optional[list[LayerEmbedding]] = None
    per_token_embeddings: Optional[list[LayerPerTokenEmbeddings]] = None
    row_attentions: Optional[list[list[list[float]]]] = None  # [layers, L, L]
    contacts: Optional[list[list[float]]] = None  # [L, L]


class MSATransformerEncodeResponse(ResponseModel):
    """Response for MSA Transformer encode action."""

    results: list[MSATransformerEncodeResponseResult]
