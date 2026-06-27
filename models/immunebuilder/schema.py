from typing import Annotated, Optional

from pydantic import (
    BeforeValidator,
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
    H: Optional[
        Annotated[
            str,
            BeforeValidator(
                validate_aa_extended
            ),  # TODO: check if extended or unambiguous should be validated
            Field(None, min_length=1, max_length=ImmuneBuilderParams.max_sequence_len),
        ]
    ] = None

    L: Optional[
        Annotated[
            str,
            BeforeValidator(validate_aa_extended),
            Field(None, min_length=1, max_length=ImmuneBuilderParams.max_sequence_len),
        ]
    ] = None
    A: Optional[
        Annotated[
            str,
            BeforeValidator(validate_aa_extended),
            Field(None, min_length=1, max_length=ImmuneBuilderParams.max_sequence_len),
        ]
    ] = None

    B: Optional[
        Annotated[
            str,
            BeforeValidator(validate_aa_extended),
            Field(None, min_length=1, max_length=ImmuneBuilderParams.max_sequence_len),
        ]
    ] = None

    # Private attribute to store the inferred "kind"
    _kind: Optional[str] = PrivateAttr()
    _kind2: Optional[str] = PrivateAttr()

    @model_validator(mode="after")
    def validate_and_infer_type(cls, instance):
        """
        Infer request type and ensure valid field combos:
          - If `H` and `L` => "abody"
          - If `H` => "nanobody"
          - If 'A' and 'B' = TCR
          - Otherwise => error.
        """
        H, L, A, B = instance.H, instance.L, instance.A, instance.B

        if (A or B) and (H or L):
            raise ValueError("Cannot provide both ('A', 'B') and (`H`, `L`). Pick one.")

        if H and L:
            instance._kind = ImmuneBuilderModelTypes.ABODYBUILDER2
        elif H and not L:
            instance._kind = ImmuneBuilderModelTypes.NANOBODYBUILDER2
        elif A and B:
            instance._kind = ImmuneBuilderModelTypes.TCRBUILDER2
            instance._kind2 = ImmuneBuilderModelTypes.TCRBUILDER2PLUS
        else:
            raise ValueError("Must provide either (`H`, `L`) OR ('H') OR `(A, B)`.")

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
