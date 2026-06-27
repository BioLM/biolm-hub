from typing import Annotated, Optional

from pydantic import (
    BeforeValidator,
    Field,
    PrivateAttr,
    model_validator,
)

from models.commons.data.structure_validator import validate_pdb
from models.commons.data.validator import validate_aa_extended
from models.commons.model.base import ModelParams
from models.commons.model.pydantic import (
    EnhancedStringEnum,
    RequestModel,
    ResponseModel,
)
from models.commons.util.config import max_pdb_str_len

### ImmuneFold Params


class ImmuneFoldParams(ModelParams):
    params_version = "v1"
    display_name = "ImmuneFold"
    base_model_slug = "immunefold"
    log_identifier = "ImmuneFold"
    batch_size = 32
    max_sequence_len = 256
    max_unpaired_sequence_len = 512


class ImmuneFoldModelTypes(EnhancedStringEnum):
    ANTIBODY = "antibody"
    TCR = "tcr"


### ImmuneFold Request


class ImmuneFoldPredictRequestParams(RequestModel):
    contact_idx: Optional[int] = None


# Biological minimum lengths for antibody variable domains to support IMGT numbering
# VH framework: 91 AA (FR1:25 + FR2:17 + FR3:38 + FR4:11) + typical CDRs (~20-30 AA)
# VL framework: 89 AA (FR1:26 + FR2:17 + FR3:36 + FR4:10) + typical CDRs (~15-25 AA)
# These minimums ensure presence of conserved residues required for IMGT numbering:
# - Cys-23 (1st-CYS), Trp-41 (CONSERVED-TRP), Cys-104 (2nd-CYS), Phe/Trp-118 (J-PHE/J-TRP)
# Sequences below these thresholds will likely fail upstream IMGT renumbering in ImmuneFold
ANTIBODY_MIN_HEAVY_LEN = 90  # VH minimum for IMGT numbering success
ANTIBODY_MIN_LIGHT_LEN = 85  # VL minimum for IMGT numbering success


class ImmuneFoldPredictRequestItem(RequestModel):
    H: Optional[
        Annotated[
            str,
            BeforeValidator(validate_aa_extended),
            Field(None, min_length=1, max_length=ImmuneFoldParams.max_sequence_len),
        ]
    ] = None

    L: Optional[
        Annotated[
            str,
            BeforeValidator(validate_aa_extended),
            Field(None, min_length=1, max_length=ImmuneFoldParams.max_sequence_len),
        ]
    ] = None

    B: Optional[
        Annotated[
            str,
            BeforeValidator(validate_aa_extended),
            Field(None, min_length=1, max_length=ImmuneFoldParams.max_sequence_len),
        ]
    ] = None
    A: Optional[
        Annotated[
            str,
            BeforeValidator(validate_aa_extended),
            Field(None, min_length=1, max_length=ImmuneFoldParams.max_sequence_len),
        ]
    ] = None
    P: Optional[
        Annotated[
            str,
            BeforeValidator(validate_aa_extended),
            Field(None, min_length=1, max_length=ImmuneFoldParams.max_sequence_len),
        ]
    ] = None
    M: Optional[
        Annotated[
            str,
            BeforeValidator(validate_aa_extended),
            Field(None, min_length=1, max_length=ImmuneFoldParams.max_sequence_len),
        ]
    ] = None

    pdb: Optional[
        Annotated[
            str,
            BeforeValidator(validate_pdb),
            Field(min_length=1, max_length=max_pdb_str_len),
        ]
    ] = None

    # Private attribute to store the inferred "kind"
    _kind: Optional[str] = PrivateAttr()

    @model_validator(mode="after")
    def validate_and_infer_type(cls, instance):
        """
        Infer request type and ensure valid field combos:
          - If `H` and `L` => "antibody"
          - If `B' 'A', 'P' 'M'` => "tcr"
          - Otherwise => error.
        """
        H, L, A, B, M, P, pdb = (
            instance.H,
            instance.L,
            instance.A,
            instance.B,
            instance.M,
            instance.P,
            instance.pdb,
        )
        if pdb and any([A, B, P, M]):
            raise ValueError(
                "Cannot provide both `antigen pdb' with TCR inputs (`B`, `A`, 'P', 'M'). Pick one."
            )
        if pdb and not (H or L):
            raise ValueError(
                "Cannot provide `antigen pdb' without antibody inputs (`H' and 'L') . Pick one."
            )
        if L and not H:
            raise ValueError(
                "Cannot provide both 'L' without 'H' for single domain VHH antibodies use just 'H'."
            )
        if H:
            instance._kind = ImmuneFoldModelTypes.ANTIBODY
            # Validate antibody chain lengths (inline - no separate method needed)
            issues: list[str] = []
            if instance.H and len(instance.H) < ANTIBODY_MIN_HEAVY_LEN:
                issues.append(
                    f"H chain length {len(instance.H)} is below the minimum "
                    f"{ANTIBODY_MIN_HEAVY_LEN} residues required for antibody variable domains."
                )
            if instance.L and len(instance.L) < ANTIBODY_MIN_LIGHT_LEN:
                issues.append(
                    f"L chain length {len(instance.L)} is below the minimum "
                    f"{ANTIBODY_MIN_LIGHT_LEN} residues required for antibody variable domains."
                )
            if issues:
                raise ValueError(
                    f"Invalid antibody input: {' '.join(issues)} "
                    "Use the TCR endpoint if you intended TCR chains."
                )
        elif all([A, B, P, M]):
            instance._kind = ImmuneFoldModelTypes.TCR
        else:
            raise ValueError(
                "Must provide either (`H` or `L`) OR (`B`, `A`, 'P' and 'M'), but not both."
            )

        return instance


class ImmuneFoldPredictRequest(RequestModel):
    params: Optional[ImmuneFoldPredictRequestParams] = Field(
        default_factory=ImmuneFoldPredictRequestParams
    )
    items: list[ImmuneFoldPredictRequestItem] = Field(
        min_length=1, max_length=ImmuneFoldParams.batch_size
    )


### ImmuneFold Response


class ImmuneFoldPredictResponseResult(ResponseModel):
    ptm: float
    full_plddt: float
    plddt: list[list[float]]
    pdb: str


class ImmuneFoldPredictResponse(ResponseModel):
    results: list[ImmuneFoldPredictResponseResult]
