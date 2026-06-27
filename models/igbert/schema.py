from functools import partial
from typing import Annotated, Optional

from pydantic import (
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
        default_factory=partial(list, [IgBertEncodeIncludeOptions.MEAN])
    )


class IgBertEncodeRequestItem(RequestModel):
    heavy: Optional[
        Annotated[
            str,
            BeforeValidator(validate_aa_extended),
            Field(None, min_length=1, max_length=IgBertParams.max_sequence_len),
        ]
    ] = None

    light: Optional[
        Annotated[
            str,
            BeforeValidator(validate_aa_extended),
            Field(None, min_length=1, max_length=IgBertParams.max_sequence_len),
        ]
    ] = None

    sequence: Optional[
        Annotated[
            str,
            BeforeValidator(validate_aa_extended),
            Field(
                None, min_length=1, max_length=IgBertParams.max_unpaired_sequence_len
            ),
        ]
    ] = None

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
        heavy, light, sequence = instance.heavy, instance.light, instance.sequence

        if sequence and (heavy or light):
            raise ValueError(
                "Cannot provide both `sequence` and (`heavy`, `light`). Pick one."
            )

        from models.igbert.config import IgBertModelTypes

        if heavy and light:
            instance._kind = IgBertModelTypes.PAIRED
        elif sequence:
            instance._kind = IgBertModelTypes.UNPAIRED
        else:
            raise ValueError(
                "Must provide either (`heavy`, `light`) OR `sequence`, but not both."
            )

        return instance


class IgBertEncodeRequest(RequestModel):
    params: IgBertEncodeRequestParams = Field(default_factory=IgBertEncodeRequestParams)
    items: list[IgBertEncodeRequestItem] = Field(
        min_length=1, max_length=IgBertParams.batch_size
    )


class IgBertGenerateRequestItem(RequestModel):
    """
    For generate(), we allow '*' placeholders inside the heavy/light sequences,
    which must still be valid length and contain at least 1 '*'.
    """

    heavy: Optional[
        Annotated[
            str,
            Field(None, min_length=1, max_length=IgBertParams.max_sequence_len),
        ]
    ] = None

    light: Optional[
        Annotated[
            str,
            Field(None, min_length=1, max_length=IgBertParams.max_sequence_len),
        ]
    ] = None

    sequence: Optional[
        Annotated[
            str,
            Field(
                None, min_length=1, max_length=IgBertParams.max_unpaired_sequence_len
            ),
        ]
    ] = None

    _kind: Optional[str] = PrivateAttr()

    @model_validator(mode="after")
    def validate_and_infer_type(cls, instance):
        # Still do the same logic to detect paired vs. unpaired
        heavy, light, sequence = instance.heavy, instance.light, instance.sequence
        if sequence and (heavy or light):
            raise ValueError("Cannot provide both `sequence` and (`heavy`, `light`).")
        from models.igbert.config import IgBertModelTypes

        if heavy and light:
            instance._kind = IgBertModelTypes.PAIRED
            sequence_to_validate = heavy + light
        elif sequence:
            instance._kind = IgBertModelTypes.UNPAIRED
            sequence_to_validate = sequence
        else:
            raise ValueError("Must provide either `heavy`+`light` OR `sequence`.")

        SingleOrMoreOccurrencesOf(token="*")(sequence_to_validate)
        AAUnambiguousPlusExtra(extra=["*"])(sequence_to_validate)

        return instance


class IgBertGenerateRequest(RequestModel):
    items: list[IgBertGenerateRequestItem] = Field(
        min_length=1, max_length=IgBertParams.batch_size
    )


class IgBertLogProbRequest(RequestModel):
    items: list[IgBertEncodeRequestItem] = Field(
        min_length=1, max_length=IgBertParams.batch_size
    )


### IgBert Response


class IgBertEncodeResponseResult(ResponseModel):
    model_config = ConfigDict(
        exclude_unset=True,
        exclude_none=True,
        extra="forbid",
    )

    embeddings: Optional[list[float]] = None
    residue_embeddings: Optional[list[list[float]]] = None
    logits: Optional[list[list[float]]] = None


class IgBertEncodeResponse(ResponseModel):
    results: list[IgBertEncodeResponseResult]


class IgBertGenerateResponseResult(ResponseModel):
    heavy: Optional[str] = None
    light: Optional[str] = None
    sequence: Optional[str] = None


class IgBertGenerateResponse(ResponseModel):
    results: list[IgBertGenerateResponseResult]


class IgBertLogProbResponseResult(ResponseModel):
    log_prob: float


class IgBertLogProbResponse(ResponseModel):
    results: list[IgBertLogProbResponseResult]
