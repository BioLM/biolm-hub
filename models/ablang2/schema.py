from typing import Annotated, Optional

from pydantic import (
    AliasChoices,
    BeforeValidator,
    ConfigDict,
    Field,
    model_validator,
)

from models.commons.data.validator import (
    AAUnambiguousPlusExtra,
    SingleOrMoreOccurrencesOf,
    validate_aa_extended,
)
from models.commons.model.base import ModelParams
from models.commons.model.pydantic import (
    EnhancedStringEnum,
    RequestModel,
    ResponseModel,
)

### AbLang2 Params


class AbLang2Params(ModelParams):
    weights_version = "v1"
    display_name = "AbLang2"
    base_model_slug = "ablang2"
    log_identifier = "AbLang2"
    batch_size = 32
    max_sequence_len = 1024


class AbLang2SequenceItem(RequestModel):
    """
    A single item in an AbLang2 request, which must have heavy + light sequences.
    """

    # Canonical antibody field names; old `heavy`/`light` accepted via alias.
    model_config = ConfigDict(populate_by_name=True)

    heavy_chain: Annotated[
        str,
        BeforeValidator(validate_aa_extended),
        Field(
            ...,
            min_length=1,
            max_length=AbLang2Params.max_sequence_len,
            validation_alias=AliasChoices("heavy_chain", "heavy"),
            description="Antibody heavy-chain amino-acid sequence.",
        ),
    ]
    light_chain: Annotated[
        str,
        BeforeValidator(validate_aa_extended),
        Field(
            ...,
            min_length=1,
            max_length=AbLang2Params.max_sequence_len,
            validation_alias=AliasChoices("light_chain", "light"),
            description="Antibody light-chain amino-acid sequence.",
        ),
    ]


### AbLang2 Encode Request (specialized for handling seqcoding and rescoding)


class AbLang2EncodeOptions(EnhancedStringEnum):
    SEQCODING = "seqcoding"
    RESCODING = "rescoding"


class AbLang2EncodeParams(RequestModel):
    include: Optional[AbLang2EncodeOptions] = Field(
        default=AbLang2EncodeOptions.SEQCODING,
        description='Embedding mode; "seqcoding" returns a single pooled vector per pair, "rescoding" returns per-residue vectors.',
    )
    align: Optional[bool] = Field(
        default=False,
        description="Align residue embeddings to a standard antibody numbering scheme (rescoding only; not yet supported, must remain false).",
    )


class AbLang2EncodeRequest(RequestModel):
    params: AbLang2EncodeParams = Field(
        default_factory=AbLang2EncodeParams,
        description="Optional parameters controlling this action (defaults are used when omitted).",
    )  # Default to seqcoding
    items: Annotated[
        list[AbLang2SequenceItem],
        Field(
            min_length=1,
            max_length=AbLang2Params.batch_size,
            description="Batch of inputs to process in a single request. Up to 32 sequences per request.",
        ),
    ]


### AbLang2 Likelihood Request


class _AbLang2LikelihoodRequest(RequestModel):
    items: Annotated[
        list[AbLang2SequenceItem],
        Field(
            min_length=1,
            max_length=AbLang2Params.batch_size,
            description="Batch of inputs to process in a single request. Up to 32 sequences per request.",
        ),
    ]


AbLang2PredictRequest = _AbLang2LikelihoodRequest  # Alias to conform to ModelActions

### AbLang2 Restore Request


class AbLang2RestoreParams(RequestModel):
    align: bool = Field(
        default=False,
        description="If true, return restored sequences using a standard antibody numbering scheme (not yet supported; must remain false).",
    )


class AbLang2MissingSequenceItem(RequestModel):
    """
    For restore, we allow '*' placeholders inside the heavy/light sequences,
    which must still be valid length and contain at least 1 '*'.
    """

    # Canonical antibody field names; old `heavy`/`light` accepted via alias.
    model_config = ConfigDict(populate_by_name=True)

    heavy_chain: Annotated[
        str,
        Field(
            ...,
            min_length=1,
            max_length=AbLang2Params.max_sequence_len,
            validation_alias=AliasChoices("heavy_chain", "heavy"),
            description='Antibody heavy-chain amino-acid sequence; use "*" to mark positions for restoration.',
        ),
    ]
    light_chain: Annotated[
        str,
        Field(
            ...,
            min_length=1,
            max_length=AbLang2Params.max_sequence_len,
            validation_alias=AliasChoices("light_chain", "light"),
            description='Antibody light-chain amino-acid sequence; use "*" to mark positions for restoration.',
        ),
    ]

    @model_validator(mode="after")
    def validate_combined_sequence(cls, values):
        combined = values.heavy_chain + values.light_chain
        SingleOrMoreOccurrencesOf(token="*")(combined)
        AAUnambiguousPlusExtra(extra=["*"])(combined)
        return values


class _AbLang2RestoreRequest(RequestModel):
    params: AbLang2RestoreParams = Field(
        default_factory=AbLang2RestoreParams,
        description="Optional parameters controlling this action (defaults are used when omitted).",
    )
    items: Annotated[
        list[AbLang2MissingSequenceItem],
        Field(
            min_length=1,
            max_length=AbLang2Params.batch_size,
            description="Batch of inputs to process in a single request. Up to 32 sequences per request.",
        ),
    ]


AbLang2GenerateRequest = _AbLang2RestoreRequest  # Alias to conform to ModelActions

### AbLang2 Log Prob Request


class AbLang2LogProbRequest(RequestModel):
    items: Annotated[
        list[AbLang2SequenceItem],
        Field(
            min_length=1,
            max_length=AbLang2Params.batch_size,
            description="Batch of inputs to process in a single request. Up to 32 sequences per request.",
        ),
    ]


######### Response Models

### AbLang2 Rescoding Response


class AbLang2RescodingResult(ResponseModel):
    residue_embeddings: list[list[float]] = Field(
        description="Per-residue embedding vectors."
    )


class AbLang2RescodingResponse(ResponseModel):
    results: list[AbLang2RescodingResult] = Field(
        description="Per-input results, returned in the same order as the request items."
    )
    number_alignment: Optional[list[str]] = Field(
        default=None,
        description="Per-residue antibody numbering labels, populated when alignment is requested; null otherwise.",
    )


### AbLang2 Seqcoding Response


class AbLang2SeqcodingResult(ResponseModel):
    embeddings: list[float] = Field(
        description="Germline-debiased sequence-level embedding vector for the antibody pair."
    )


class AbLang2SeqcodingResponse(ResponseModel):
    results: list[AbLang2SeqcodingResult] = Field(
        description="Per-input results, returned in the same order as the request items."
    )


### AbLang2 Likelihood Response


class AbLang2LikelihoodResult(ResponseModel):
    logits: list[list[float]] = Field(
        description="Per-position logits over the model vocabulary."
    )
    sequence_tokens: list[str] = Field(
        description="Per-position input tokens, aligned with the logits."
    )
    vocab_tokens: list[str] = Field(
        description="Vocabulary token order corresponding to the logits columns."
    )


class _AbLang2LikelihoodResponse(ResponseModel):
    results: list[AbLang2LikelihoodResult] = Field(
        description="Per-input results, returned in the same order as the request items."
    )


AbLang2PredictResponse = _AbLang2LikelihoodResponse  # Alias to conform to ModelActions

### AbLang2 Generate Response


class AbLang2GenerateResponseResult(RequestModel):
    # Generate output mirrors the canonical antibody field names.
    heavy_chain: str = Field(
        description="Restored heavy-chain amino-acid sequence with all masked positions filled."
    )
    light_chain: str = Field(
        description="Restored light-chain amino-acid sequence with all masked positions filled."
    )


class AbLang2GenerateResponse(ResponseModel):
    results: list[AbLang2GenerateResponseResult] = Field(
        description="Per-input results, returned in the same order as the request items."
    )

### AbLang2 Log Prob Response


class AbLang2LogProbResponseResult(ResponseModel):
    log_prob: float = Field(
        description="Pseudo-log-likelihood of the sequence under the model."
    )


class AbLang2LogProbResponse(ResponseModel):
    results: list[AbLang2LogProbResponseResult] = Field(
        description="Per-input results, returned in the same order as the request items."
    )
