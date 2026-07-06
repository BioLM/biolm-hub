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
    weights_version = "v1"
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


class ImmuneBuilderFoldParams(RequestModel):
    seed: int = Field(
        default=42, ge=0, description="Random seed for reproducible sampling."
    )


class ImmuneBuilderFoldRequestItem(RequestModel):
    # Canonical antibody/TCR field names; old single-letter chain keys
    # (`H`/`L`/`A`/`B`) are accepted via input alias for back-compat.
    model_config = ConfigDict(populate_by_name=True)

    heavy_chain: Optional[
        Annotated[
            str,
            BeforeValidator(validate_aa_extended),
        ]
    ] = Field(
        default=None,
        min_length=1,
        max_length=ImmuneBuilderParams.max_sequence_len,
        validation_alias=AliasChoices("heavy_chain", "H"),
        description="Antibody heavy-chain amino-acid sequence; provide alone for nanobody (VHH) prediction.",
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
        description="Antibody light-chain amino-acid sequence.",
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
        description="TCR alpha-chain amino-acid sequence; pair with tcr_beta for TCR structure prediction.",
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
        description="TCR beta-chain amino-acid sequence; pair with tcr_alpha for TCR structure prediction.",
    )

    # Private attribute to store the inferred "kind"
    _kind: Optional[str] = PrivateAttr()
    _kind2: Optional[str] = PrivateAttr()

    @model_validator(mode="after")
    def validate_and_infer_type(self) -> "ImmuneBuilderFoldRequestItem":
        """
        Infer request type and ensure valid field combos:
          - If `heavy_chain` and `light_chain` => "abody"
          - If `heavy_chain` only => "nanobody"
          - If `tcr_alpha` and `tcr_beta` => TCR
          - Otherwise => error.
        """
        H, L, A, B = (
            self.heavy_chain,
            self.light_chain,
            self.tcr_alpha,
            self.tcr_beta,
        )

        if (A or B) and (H or L):
            raise ValueError(
                "Cannot provide both ('tcr_alpha', 'tcr_beta') and "
                "('heavy_chain', 'light_chain'). Pick one."
            )

        if H and L:
            self._kind = ImmuneBuilderModelTypes.ABODYBUILDER2
        elif H and not L:
            self._kind = ImmuneBuilderModelTypes.NANOBODYBUILDER2
        elif A and B:
            self._kind = ImmuneBuilderModelTypes.TCRBUILDER2
            self._kind2 = ImmuneBuilderModelTypes.TCRBUILDER2PLUS
        else:
            raise ValueError(
                "Must provide either ('heavy_chain', 'light_chain') OR "
                "('heavy_chain' only) OR ('tcr_alpha', 'tcr_beta')."
            )

        return self


class ImmuneBuilderFoldRequest(RequestModel):
    items: list[ImmuneBuilderFoldRequestItem] = Field(
        min_length=1,
        max_length=ImmuneBuilderParams.batch_size,
        description="Batch of inputs to process in a single request. Up to 8 sequences per request.",
    )
    params: Optional[ImmuneBuilderFoldParams] = Field(
        default_factory=ImmuneBuilderFoldParams,
        description="Optional parameters controlling this action (defaults are used when omitted).",
    )


### ImmuneBuilder Response


class ImmuneBuilderFoldResponseResult(ResponseModel):
    pdb: str = Field(description="Predicted structure in PDB format.")


class ImmuneBuilderFoldResponse(ResponseModel):
    results: list[ImmuneBuilderFoldResponseResult] = Field(
        description="Per-input results, returned in the same order as the request items."
    )
