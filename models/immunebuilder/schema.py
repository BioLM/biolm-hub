from typing import Annotated, Optional

from pydantic import (
    AliasChoices,
    BeforeValidator,
    ConfigDict,
    Field,
    PrivateAttr,
    model_validator,
)

from models.commons.data.validator import validate_aa_extended
from models.commons.model.base import ModelParams
from models.commons.model.pydantic import (
    EnhancedStringEnum,
    RequestModel,
    ResponseModel,
)

### ImmuneBuilder Params


class ImmuneBuilderParams(ModelParams):
    params_version = "v1"
    display_name = "ImmuneBuilder"
    base_model_slug = "immunebuilder"
    log_identifier = "ImmuneBuilder"
    batch_size = 8
    max_sequence_len = 2048


class ImmuneBuilderModelTypes(EnhancedStringEnum):
    TCRBUILDER2 = "tcrbuilder2"
    TCRBUILDER2PLUS = "tcrbuilder2plus"
    ABODYBUILDER2 = "abodybuilder2"
    NANOBODYBUILDER2 = "nanobodybuilder2"


### ImmuneBuilder Request


class ImmuneBuilderPredictParams(RequestModel):
    seed: int = Field(default=42, ge=0)


class ImmuneBuilderPredictRequestItem(RequestModel):
    # Canonical antibody/TCR field names; old single-letter chain keys
    # (`H`/`L`/`A`/`B`) are accepted via input alias for back-compat.
    model_config = ConfigDict(populate_by_name=True)

    heavy_chain: Optional[
        Annotated[
            str,
            BeforeValidator(
                validate_aa_extended
            ),  # TODO: check if extended or unambiguous should be validated
        ]
    ] = Field(
        default=None,
        min_length=1,
        max_length=ImmuneBuilderParams.max_sequence_len,
        validation_alias=AliasChoices("heavy_chain", "H"),
    )

    light_chain: Optional[
        Annotated[
            str,
            BeforeValidator(validate_aa_extended),
        ]
    ] = Field(
        default=None,
        min_length=1,
        max_length=ImmuneBuilderParams.max_sequence_len,
        validation_alias=AliasChoices("light_chain", "L"),
    )
    tcr_alpha: Optional[
        Annotated[
            str,
            BeforeValidator(validate_aa_extended),
        ]
    ] = Field(
        default=None,
        min_length=1,
        max_length=ImmuneBuilderParams.max_sequence_len,
        validation_alias=AliasChoices("tcr_alpha", "A"),
    )

    tcr_beta: Optional[
        Annotated[
            str,
            BeforeValidator(validate_aa_extended),
        ]
    ] = Field(
        default=None,
        min_length=1,
        max_length=ImmuneBuilderParams.max_sequence_len,
        validation_alias=AliasChoices("tcr_beta", "B"),
    )

    # Private attribute to store the inferred "kind"
    _kind: Optional[str] = PrivateAttr()
    _kind2: Optional[str] = PrivateAttr()

    @model_validator(mode="after")
    def validate_and_infer_type(cls, instance):
        """
        Infer request type and ensure valid field combos:
          - If `heavy_chain` and `light_chain` => "abody"
          - If `heavy_chain` only => "nanobody"
          - If `tcr_alpha` and `tcr_beta` => TCR
          - Otherwise => error.
        """
        H, L, A, B = (
            instance.heavy_chain,
            instance.light_chain,
            instance.tcr_alpha,
            instance.tcr_beta,
        )

        if (A or B) and (H or L):
            raise ValueError(
                "Cannot provide both ('tcr_alpha', 'tcr_beta') and "
                "('heavy_chain', 'light_chain'). Pick one."
            )

        if H and L:
            instance._kind = ImmuneBuilderModelTypes.ABODYBUILDER2
        elif H and not L:
            instance._kind = ImmuneBuilderModelTypes.NANOBODYBUILDER2
        elif A and B:
            instance._kind = ImmuneBuilderModelTypes.TCRBUILDER2
            instance._kind2 = ImmuneBuilderModelTypes.TCRBUILDER2PLUS
        else:
            raise ValueError(
                "Must provide either ('heavy_chain', 'light_chain') OR "
                "('heavy_chain' only) OR ('tcr_alpha', 'tcr_beta')."
            )

        return instance


class ImmuneBuilderPredictRequest(RequestModel):
    items: Annotated[
        list[ImmuneBuilderPredictRequestItem],
        Field(min_length=1, max_length=ImmuneBuilderParams.batch_size),
    ]
    params: Optional[ImmuneBuilderPredictParams] = ImmuneBuilderPredictParams()


### ImmuneBuilder Response


class ImmuneBuilderPredictResponseResult(ResponseModel):
    pdb: str


class ImmuneBuilderPredictResponse(ResponseModel):
    results: list[ImmuneBuilderPredictResponseResult]
