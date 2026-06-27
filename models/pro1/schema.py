from typing import Annotated

from pydantic import BeforeValidator, Field

from models.commons.data.validator import validate_aa_unambiguous
from models.commons.model.base import ModelParams
from models.commons.model.pydantic import (
    EnhancedStringEnum,
    RequestModel,
    ResponseModel,
)

### Pro-1 Params


class Pro1Params(ModelParams):
    params_version = "v1"
    display_name = "Pro-1"
    base_model_slug = "pro1"
    log_identifier = "Pro-1"
    batch_size = 1
    max_sequence_len = 2000


class Pro1Variant(EnhancedStringEnum):  # noqa: UP042
    SIZE_8B = "8b"  # Default: all-lm-grpo-mega-run (creativity+specificity)
    SIZE_8B_GRPO = "8b-grpo"  # GRPO only checkpoint


### Pro-1 Request Models


class Pro1Reaction(RequestModel):
    """A single reaction: substrates + products."""

    substrates: list[str] = Field(default_factory=list)
    products: list[str] = Field(default_factory=list)


class Pro1KnownMutation(RequestModel):
    """A prior mutagenesis result for iterative design."""

    mutation: str = Field(
        ...,
        max_length=16,
        description="Mutation in standard notation e.g. K116E",
    )
    effect: str = Field(
        ...,
        max_length=500,
        description="Observed effect e.g. 'increases Tm by 24°C'",
    )


class Pro1ProteinData(RequestModel):
    """Per-protein input data for Pro-1."""

    sequence: Annotated[
        str,
        Field(
            ...,
            min_length=10,
            max_length=Pro1Params.max_sequence_len,
            description=(
                "Amino acid sequence (standard 1-letter codes). "
                "Performance is best on globular sequences in the 50-500 AA range; "
                "outputs degrade for sequences shorter than 20 AA or longer than 500 AA "
                "(see BIOLOGY.md)."
            ),
        ),
        BeforeValidator(validate_aa_unambiguous),
    ]
    name: str = Field(
        default="",
        max_length=200,
        description="Protein name used in prompt context",
    )
    ec_number: str = Field(
        default="",
        max_length=32,
        description="EC number for enzymes (e.g. '4.2.1.1')",
    )
    reaction: list[Pro1Reaction] = Field(
        default_factory=list,
        max_length=8,
        description="List of reaction substrates/products (only the first entry is used in the prompt)",
    )
    general_information: str = Field(
        default="",
        max_length=4000,
        description="Freeform biological context: literature notes, structural features, engineering goals",
    )
    metal_ions: list[str] = Field(
        default_factory=list,
        max_length=20,
        description="Metal ions or cofactors present (e.g. ['Zn2+', 'Mg2+'])",
    )
    active_site_residues: list[str] = Field(
        default_factory=list,
        max_length=200,
        description="Active site residues that must not be modified (e.g. ['H64', 'H119'])",
    )
    known_mutations: list[Pro1KnownMutation] = Field(
        default_factory=list,
        max_length=50,
        description="Prior experimental results for iterative design",
    )


class Pro1GenerateParams(RequestModel):
    """Generation parameters for Pro-1.

    Variant selection is performed by gateway routing (each variant is a
    separate Modal deployment), not by a body field — see ESM2 / ProGen2.
    """

    max_iterations: int = Field(
        default=3,
        ge=1,
        le=10,
        description="Maximum number of generation attempts (each produces one proposal)",
    )
    max_new_tokens: int = Field(
        default=8192,
        ge=128,
        le=16384,
        description="Maximum new tokens to generate per iteration",
    )
    temperature: float = Field(
        default=0.95,
        gt=0.0,
        le=2.0,
        description="Sampling temperature",
    )
    top_p: float = Field(
        default=0.95,
        gt=0.0,
        le=1.0,
        description="Top-p (nucleus) sampling cutoff",
    )
    seed: int | None = Field(
        default=None,
        description="Random seed for reproducibility",
    )


class Pro1GenerateRequest(RequestModel):
    """Request for Pro-1 generate action."""

    params: Pro1GenerateParams
    items: Annotated[
        list[Pro1ProteinData],
        Field(
            min_length=1,
            max_length=1,
            description="Single protein to engineer (Pro-1 processes one protein at a time)",
        ),
    ]


### Pro-1 Response Models


class Pro1MutationProposal(ResponseModel):
    """A single proposed mutation with rationale."""

    mutation: str = Field(
        ...,
        description="Mutation in standard notation e.g. K116E (Lys→Glu at position 116)",
    )
    rationale: str = Field(
        ...,
        description="Biochemical rationale extracted from reasoning trace",
    )


class Pro1GenerateResult(ResponseModel):
    """One generation result from a single iteration."""

    reasoning: str = Field(
        ...,
        description="Full chain-of-thought reasoning trace (may include <think> tags). NOTE: citations may be hallucinated.",
    )
    mutations: list[Pro1MutationProposal] = Field(
        default_factory=list,
        description="Parsed list of proposed mutations with rationale. May be empty if none could be parsed.",
    )
    modified_sequence: str | None = Field(
        default=None,
        description="Modified protein sequence with proposed mutations applied. None if sequence could not be extracted.",
    )


class Pro1GenerateResponse(ResponseModel):
    """Response from Pro-1 generate action."""

    results: list[Pro1GenerateResult] = Field(
        ...,
        description="One result per successful generation iteration",
    )
