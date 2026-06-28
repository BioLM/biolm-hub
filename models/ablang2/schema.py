from typing import Annotated, Optional, Union

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
    params_version = "v1"
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
        ),
    ]


### AbLang2 Seqcoding Request


class AbLang2SeqcodingOptions(EnhancedStringEnum):
    SEQCODING = "seqcoding"


class AbLang2SeqcodingParams(RequestModel):
    include: AbLang2SeqcodingOptions = AbLang2SeqcodingOptions.SEQCODING


class AbLang2SeqcodingRequest(RequestModel):
    params: AbLang2SeqcodingParams = Field(default_factory=AbLang2SeqcodingParams)
    items: Annotated[
        list[AbLang2SequenceItem],
        Field(min_length=1, max_length=AbLang2Params.batch_size),
    ]


### AbLang2 Rescoding Request


class AbLang2RescodingOptions(EnhancedStringEnum):
    RESCODING = "rescoding"


class AbLang2RescodingParams(RequestModel):
    include: AbLang2RescodingOptions = AbLang2RescodingOptions.RESCODING
    align: bool = False


class AbLang2RescodingRequest(RequestModel):
    params: AbLang2RescodingParams = Field(default_factory=AbLang2RescodingParams)
    items: Annotated[
        list[AbLang2SequenceItem],
        Field(min_length=1, max_length=AbLang2Params.batch_size),
    ]


### AbLang2 Encode Request (specialized for handling seqcoding and rescoding)


class AbLang2EncodeOptions(EnhancedStringEnum):
    SEQCODING = "seqcoding"
    RESCODING = "rescoding"


class AbLang2EncodeParams(RequestModel):
    include: Optional[AbLang2EncodeOptions] = AbLang2EncodeOptions.SEQCODING
    align: Optional[bool] = Field(default=False, description="Specific to rescoding.")


class AbLang2EncodeRequest(RequestModel):
    params: AbLang2EncodeParams = Field(
        default_factory=AbLang2EncodeParams
    )  # Default to seqcoding
    items: Annotated[
        list[AbLang2SequenceItem],
        Field(min_length=1, max_length=AbLang2Params.batch_size),
    ]


### AbLang2 Likelihood Request


class AbLang2LikelihoodOptions(EnhancedStringEnum):
    LIKELIHOOD = "likelihood"


class AbLang2LikelihoodParams(RequestModel):
    include: AbLang2LikelihoodOptions = AbLang2LikelihoodOptions.LIKELIHOOD


class _AbLang2LikelihoodRequest(RequestModel):
    params: AbLang2LikelihoodParams = Field(default_factory=AbLang2LikelihoodParams)
    items: Annotated[
        list[AbLang2SequenceItem],
        Field(min_length=1, max_length=AbLang2Params.batch_size),
    ]


AbLang2PredictRequest = _AbLang2LikelihoodRequest  # Alias to conform to ModelActions

### AbLang2 Restore Request


class AbLang2RestoreOptions(EnhancedStringEnum):
    RESTORE = "restore"


class AbLang2RestoreParams(RequestModel):
    include: AbLang2RestoreOptions = AbLang2RestoreOptions.RESTORE
    align: bool = False


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
        ),
    ]
    light_chain: Annotated[
        str,
        Field(
            ...,
            min_length=1,
            max_length=AbLang2Params.max_sequence_len,
            validation_alias=AliasChoices("light_chain", "light"),
        ),
    ]

    @model_validator(mode="after")
    def validate_combined_sequence(cls, values):
        combined = values.heavy_chain + values.light_chain
        SingleOrMoreOccurrencesOf(token="*")(combined)
        AAUnambiguousPlusExtra(extra=["*"])(combined)
        return values


class _AbLang2RestoreRequest(RequestModel):
    params: AbLang2RestoreParams = Field(default_factory=AbLang2RestoreParams)
    items: Annotated[
        list[AbLang2MissingSequenceItem],
        Field(min_length=1, max_length=AbLang2Params.batch_size),
    ]


AbLang2GenerateRequest = _AbLang2RestoreRequest  # Alias to conform to ModelActions

### AbLang2 Log Prob Request


class AbLang2LogProbRequest(RequestModel):
    items: Annotated[
        list[AbLang2SequenceItem],
        Field(min_length=1, max_length=AbLang2Params.batch_size),
    ]


######### Response Models

### AbLang2 Rescoding Response


class AbLang2RescodingResult(ResponseModel):
    rescoding: list[
        list[Union[float, str]]
    ]  # e.g. shape [num_positions, embed-dims or tokens]


class AbLang2RescodingResponse(ResponseModel):
    results: list[AbLang2RescodingResult]
    number_alignment: Optional[list[str]] = None


### AbLang2 Seqcoding Response


class AbLang2SeqcodingResult(ResponseModel):
    seqcoding: list[float]


class AbLang2SeqcodingResponse(ResponseModel):
    results: list[AbLang2SeqcodingResult]


### AbLang2 Likelihood Response


class AbLang2LikelihoodResult(ResponseModel):
    likelihood: list[list[float]]
    sequence_tokens: list[str]
    vocab_tokens: list[str]


class _AbLang2LikelihoodResponse(ResponseModel):
    results: list[AbLang2LikelihoodResult]


AbLang2PredictResponse = _AbLang2LikelihoodResponse  # Alias to conform to ModelActions

### AbLang2 Restore Response


class AbLang2RestoreItem(RequestModel):
    # Restore output mirrors the canonical antibody field names.
    heavy_chain: str
    light_chain: str


class _AbLang2RestoreResponse(ResponseModel):
    results: list[AbLang2RestoreItem]


AbLang2GenerateResponse = _AbLang2RestoreResponse  # Alias to conform to ModelActions

### AbLang2 Log Prob Response


class AbLang2LogProbResponseResult(ResponseModel):
    log_prob: float


class AbLang2LogProbResponse(ResponseModel):
    results: list[AbLang2LogProbResponseResult]
