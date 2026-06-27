from typing import Annotated, Optional

from pydantic import BeforeValidator, Field

from models.commons.data.validator import validate_aa_extended
from models.commons.model.base import ModelParams
from models.commons.model.pydantic import (
    EnhancedStringEnum,
    RequestModel,
    ResponseModel,
)

### ProperMAB Params


class ProperMABParams(ModelParams):
    params_version = "v1"
    display_name = "ProperMAB"
    base_model_slug = "propermab"
    log_identifier = "ProperMAB"
    batch_size = 1  # Structure prediction is resource-intensive
    max_sequence_len = 200  # Antibody variable regions are ~100-150 AA
    min_sequence_len = 100  # Minimum for valid Fv domain


class ProperMABIsotype(EnhancedStringEnum):
    """Antibody heavy chain isotype for Fc charge feature calculations."""

    IgG1 = "igg1"
    IgG2 = "igg2"
    IgG4 = "igg4"


class ProperMABLightChainType(EnhancedStringEnum):
    """Light chain type (kappa or lambda)."""

    KAPPA = "kappa"
    LAMBDA = "lambda"


### ProperMAB Request


class ProperMABExtractFeaturesParams(RequestModel):
    """Parameters for ProperMAB feature extraction.

    Attributes:
        num_runs: Number of structure prediction runs for averaging (1-5).
            Multiple runs can improve robustness but increase computation time.
            Default: 1 (~60s), 5 runs: ~5-8 minutes.
        is_fv: Whether input sequences are Fv-only (True) or full-length (False).
            Affects charge calculations. Default: True (Fv domain only).
        isotype: Heavy chain isotype for Fc charge calculations.
            Default: igg1
        lc_type: Light chain type (kappa or lambda).
            Default: kappa
        seed: Random seed for reproducible structure prediction and feature extraction.
            Default: 42
    """

    num_runs: int = Field(default=1, ge=1, le=5)
    is_fv: bool = Field(default=True)
    isotype: ProperMABIsotype = Field(default=ProperMABIsotype.IgG1)
    lc_type: ProperMABLightChainType = Field(default=ProperMABLightChainType.KAPPA)
    seed: int = Field(default=42, ge=0)


class ProperMABExtractFeaturesRequestItem(RequestModel):
    """Request item for ProperMAB feature extraction.

    Attributes:
        heavy_seq: Heavy chain variable region sequence (VH domain).
            Should be 100-150 amino acids.
        light_seq: Light chain variable region sequence (VL domain).
            Should be 100-120 amino acids.
    """

    heavy_seq: Annotated[
        str,
        BeforeValidator(validate_aa_extended),
        Field(
            ...,
            min_length=ProperMABParams.min_sequence_len,
            max_length=ProperMABParams.max_sequence_len,
        ),
    ]
    light_seq: Annotated[
        str,
        BeforeValidator(validate_aa_extended),
        Field(
            ...,
            min_length=ProperMABParams.min_sequence_len,
            max_length=ProperMABParams.max_sequence_len,
        ),
    ]


class ProperMABExtractFeaturesRequest(RequestModel):
    """Request schema for ProperMAB feature extraction endpoint.

    ProperMAB extracts 34 biophysical features from antibody sequences that
    predict developability properties (HIC retention time, viscosity, aggregation).
    """

    items: Annotated[
        list[ProperMABExtractFeaturesRequestItem],
        Field(min_length=1, max_length=ProperMABParams.batch_size),
    ]
    params: Optional[ProperMABExtractFeaturesParams] = ProperMABExtractFeaturesParams()


### ProperMAB Response


class ProperMABSequenceFeatures(ResponseModel):
    """7 sequence-based features (computed instantly without structure).

    Charge Features:
        theoretical_pi: Isoelectric point (pH stability, formulation)
        n_charged_res: Total charged residues (D,E,K,R)
        n_charged_res_fv: Charged residues in Fv region
        fv_charge: Net charge of Fv domain (solubility)
        fv_csp: VH_charge × VL_charge (charge separation parameter)
        fc_charge: Net charge of Fc domain
        fab_fc_csp: FAB_charge × FC_charge (domain charge asymmetry)
    """

    theoretical_pi: float
    n_charged_res: int
    n_charged_res_fv: int
    fv_charge: float
    fv_csp: float
    fc_charge: float
    fab_fc_csp: float


class ProperMABStructureFeatures(ResponseModel):
    """27 structure-based features (requires 3D structure prediction).

    Charge Distribution (6 features):
        net_charge: Total Fv charge from structure
        exposed_net_charge: Solvent-exposed charge only
        net_charge_cdr: Charge in CDR regions
        exposed_net_charge_cdr: Surface CDR charge
        scm: Spatial Charge Map score (negative electrostatic magnitude)
        dipole_moment: Electric dipole in Debyes (charge asymmetry)

    Hydrophobicity (6 features):
        hyd_asa: Hydrophobic surface area (Ų) - HIC retention predictor
        hph_asa: Hydrophilic surface area (Ų)
        hyd_moment: Hydrophobic moment (amphiphilicity)
        heiden_score: Surface hydrophobic potential
        hyd_patch_area: Total hydrophobic patch area
        hyd_patch_area_cdr: Hydrophobic patches near CDRs (strongest HIC RT predictor)

    Charge Patches (4 features):
        pos_patch_area: Positive charge patch area
        pos_patch_area_cdr: Positive patches near CDRs
        neg_patch_area: Negative charge patch area
        neg_patch_area_cdr: Negative patches near CDRs

    Aromatic Features (3 features):
        aromatic_asa: Surface area of F,W,Y (Ų)
        aromatic_cdr: Count of F,W,Y in CDRs
        exposed_aromatic: Solvent-exposed F,W,Y count

    Spatial Statistics (6 features - Novel PROPERMAB contribution):
        pos_ann_index: Positive charge clustering index (>1=dispersed, <1=clustered)
        neg_ann_index: Negative charge clustering index
        aromatic_ann_index: Aromatic residue clustering
        pos_ripley_k: Positive charge Ripley's K ratio (spatial correlation at 6Å)
        neg_ripley_k: Negative charge Ripley's K ratio
        aromatic_ripley_k: Aromatic Ripley's K ratio

    Domain Asymmetry (2 features):
        Fv_chml: VH_charge - VL_charge (heavy-light asymmetry)
        exposed_Fv_chml: Surface VH-VL charge difference

    Structural CDR Length (1 feature):
        cdr_h3_length: CDR-H3 loop length from IMGT numbering (flexibility, immunogenicity)
    """

    # Charge distribution (6)
    net_charge: float
    exposed_net_charge: float
    net_charge_cdr: float
    exposed_net_charge_cdr: float
    scm: float
    dipole_moment: float

    # Hydrophobicity (6)
    hyd_asa: float
    hph_asa: float
    hyd_moment: float
    heiden_score: float
    hyd_patch_area: float
    hyd_patch_area_cdr: float

    # Charge patches (4)
    pos_patch_area: float
    pos_patch_area_cdr: float
    neg_patch_area: float
    neg_patch_area_cdr: float

    # Aromatic features (3)
    aromatic_asa: float
    aromatic_cdr: int
    exposed_aromatic: int

    # Spatial statistics (6)
    pos_ann_index: float
    neg_ann_index: float
    aromatic_ann_index: float
    pos_ripley_k: float
    neg_ripley_k: float
    aromatic_ripley_k: float

    # Domain asymmetry (2)
    Fv_chml: float
    exposed_Fv_chml: float

    # CDR length (1) - calculated from predicted structure
    cdr_h3_length: int


class ProperMABExtractFeaturesMetadata(ResponseModel):
    """Metadata about the feature extraction computation."""

    num_runs: int
    isotype: str
    lc_type: str
    structure_prediction_method: str = "ABodyBuilder2"
    feature_calculation_version: str = "propermab-0.1.0"


class ProperMABExtractFeaturesResponseResult(ResponseModel):
    """Result containing all 34 ProperMAB features and metadata.

    The features are separated into:
    - sequence_features: 7 features computed instantly from sequence
    - structure_features: 27 features requiring 3D structure prediction
    """

    sequence_features: ProperMABSequenceFeatures
    structure_features: ProperMABStructureFeatures
    metadata: ProperMABExtractFeaturesMetadata


class ProperMABExtractFeaturesResponse(ResponseModel):
    """Response schema for ProperMAB feature extraction."""

    results: list[ProperMABExtractFeaturesResponseResult]
