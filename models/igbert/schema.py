from functools import partial
from typing import Annotated, Optional

from pydantic import (
    AliasChoices,
    BeforeValidator,
    ConfigDict,
    Field,
    PrivateAttr,
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

### IgBert Params


class IgBertParams(ModelParams):
    params_version = "v1"
    display_name = "IgBert"
    base_model_slug = "igbert"
    log_identifier = "IgBert"
    batch_size = 32
    max_sequence_len = 256
    max_unpaired_sequence_len = 512


class IgBertModelTypes(EnhancedStringEnum):
    PAIRED = "paired"
    UNPAIRED = "unpaired"


### IgBert Request


class IgBertEncodeIncludeOptions(EnhancedStringEnum):
    MEAN = "mean"  # mean embedding (default)
    RESIDUE = "residue"  # per-residue embeddings
    LOGITS = "logits"  # logits


class IgBertEncodeRequestParams(RequestModel):
    include: list[IgBertEncodeIncludeOptions] = Field(
        default_factory=partial(list, [IgBertEncodeIncludeOptions.MEAN]),
        description="Optional outputs to compute and include in the response.",
    )


class IgBertEncodeRequestItem(RequestModel):
    # Canonical antibody field names; old `heavy`/`light` accepted via alias.
    model_config = ConfigDict(populate_by_name=True)

    heavy_chain: Optional[Annotated[str, BeforeValidator(validate_aa_extended)]] = (
        Field(
            default=None,
            min_length=1,
            max_length=IgBertParams.max_sequence_len,
            validation_alias=AliasChoices("heavy_chain", "heavy"),
            description="Antibody heavy-chain amino-acid sequence.",
        )
    )

    light_chain: Optional[Annotated[str, BeforeValidator(validate_aa_extended)]] = (
        Field(
            default=None,
            min_length=1,
            max_length=IgBertParams.max_sequence_len,
            validation_alias=AliasChoices("light_chain", "light"),
            description="Antibody light-chain amino-acid sequence.",
        )
    )

    sequence: Optional[Annotated[str, BeforeValidator(validate_aa_extended)]] = Field(
        default=None,
        min_length=1,
        max_length=IgBertParams.max_unpaired_sequence_len,
        description="An antibody chain sequence in single-letter amino-acid codes, for unpaired mode.",
    )

    # Private attribute to store the inferred "kind"
    _kind: Optional[str] = PrivateAttr()

    @model_validator(mode="after")
    def validate_and_infer_type(cls, instance):
        """
        Infer request type and ensure valid field combos:
          - If `heavy` and `light` => "paired"
          - If `sequence` => "unpaired"
          - Otherwise => error.
        """
        heavy, light, sequence = (
            instance.heavy_chain,
            instance.light_chain,
            instance.sequence,
        )

        if sequence and (heavy or light):
            raise ValueError(
                "Cannot provide both `sequence` and (`heavy_chain`, `light_chain`). "
                "Pick one."
            )

        from models.igbert.config import IgBertModelTypes

        if heavy and light:
            instance._kind = IgBertModelTypes.PAIRED
        elif sequence:
            instance._kind = IgBertModelTypes.UNPAIRED
        else:
            raise ValueError(
                "Must provide either (`heavy_chain`, `light_chain`) OR `sequence`, "
                "but not both."
            )

        return instance


class IgBertEncodeRequest(RequestModel):
    params: IgBertEncodeRequestParams = Field(
        default_factory=IgBertEncodeRequestParams,
        description="Optional parameters controlling this action (defaults are used when omitted).",
    )
    items: list[IgBertEncodeRequestItem] = Field(
        min_length=1,
        max_length=IgBertParams.batch_size,
        description="Batch of inputs to process in a single request. Up to 32 sequences per request.",
    )


class IgBertGenerateRequestItem(RequestModel):
    """
    For generate(), we allow '*' placeholders inside the heavy/light sequences,
    which must still be valid length and contain at least 1 '*'.
    """

    # Canonical antibody field names; old `heavy`/`light` accepted via alias.
    model_config = ConfigDict(populate_by_name=True)

    heavy_chain: Optional[str] = Field(
        default=None,
        min_length=1,
        max_length=IgBertParams.max_sequence_len,
        validation_alias=AliasChoices("heavy_chain", "heavy"),
        description="Antibody heavy-chain sequence with * at masked positions to be restored.",
    )

    light_chain: Optional[str] = Field(
        default=None,
        min_length=1,
        max_length=IgBertParams.max_sequence_len,
        validation_alias=AliasChoices("light_chain", "light"),
        description="Antibody light-chain sequence with * at masked positions to be restored.",
    )

    sequence: Optional[str] = Field(
        default=None,
        min_length=1,
        max_length=IgBertParams.max_unpaired_sequence_len,
        description="An antibody chain sequence in single-letter amino-acid codes with * at masked positions, for unpaired mode.",
    )

    _kind: Optional[str] = PrivateAttr()

    @model_validator(mode="after")
    def validate_and_infer_type(cls, instance):
        # Still do the same logic to detect paired vs. unpaired
        heavy, light, sequence = (
            instance.heavy_chain,
            instance.light_chain,
            instance.sequence,
        )
        if sequence and (heavy or light):
            raise ValueError(
                "Cannot provide both `sequence` and (`heavy_chain`, `light_chain`)."
            )
        from models.igbert.config import IgBertModelTypes

        if heavy and light:
            instance._kind = IgBertModelTypes.PAIRED
            sequence_to_validate = heavy + light
        elif sequence:
            instance._kind = IgBertModelTypes.UNPAIRED
            sequence_to_validate = sequence
        else:
            raise ValueError(
                "Must provide either `heavy_chain`+`light_chain` OR `sequence`."
            )

        SingleOrMoreOccurrencesOf(token="*")(sequence_to_validate)
        AAUnambiguousPlusExtra(extra=["*"])(sequence_to_validate)

        return instance


class IgBertGenerateRequest(RequestModel):
    items: list[IgBertGenerateRequestItem] = Field(
        min_length=1,
        max_length=IgBertParams.batch_size,
        description="Batch of inputs to process in a single request. Up to 32 sequences per request.",
    )


class IgBertLogProbRequest(RequestModel):
    items: list[IgBertEncodeRequestItem] = Field(
        min_length=1,
        max_length=IgBertParams.batch_size,
        description="Batch of inputs to process in a single request. Up to 32 sequences per request.",
    )


### IgBert Response


class IgBertEncodeResponseResult(ResponseModel):
    model_config = ConfigDict(
        exclude_unset=True,
        exclude_none=True,
        extra="forbid",
    )

    embeddings: Optional[list[float]] = Field(
        default=None,
        description="Mean-pooled embedding vector for the sequence.",
    )
    residue_embeddings: Optional[list[list[float]]] = Field(
        default=None,
        description="Per-residue embedding vectors.",
    )
    logits: Optional[list[list[float]]] = Field(
        default=None,
        description="Per-position logits over the model vocabulary.",
    )


class IgBertEncodeResponse(ResponseModel):
    results: list[IgBertEncodeResponseResult] = Field(
        description="Per-input results, returned in the same order as the request items.",
    )


class IgBertGenerateResponseResult(ResponseModel):
    # Restore output mirrors the canonical antibody field names.
    heavy_chain: Optional[str] = Field(
        default=None,
        description="Restored antibody heavy-chain sequence with masked positions filled in.",
    )
    light_chain: Optional[str] = Field(
        default=None,
        description="Restored antibody light-chain sequence with masked positions filled in.",
    )
    sequence: Optional[str] = Field(
        default=None,
        description="Restored antibody chain sequence with masked positions filled in, populated in unpaired mode.",
    )


class IgBertGenerateResponse(ResponseModel):
    results: list[IgBertGenerateResponseResult] = Field(
        description="Per-input results, returned in the same order as the request items.",
    )


class IgBertLogProbResponseResult(ResponseModel):
    log_prob: float = Field(
        description="Pseudo-log-likelihood of the sequence under the model.",
    )


class IgBertLogProbResponse(ResponseModel):
    results: list[IgBertLogProbResponseResult] = Field(
        description="Per-input results, returned in the same order as the request items.",
    )
