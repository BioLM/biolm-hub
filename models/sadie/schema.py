from typing import Optional

from pydantic import Field, StrictBool, StrictStr, validator

from models.commons.data.validator import validate_aa_extended
from models.commons.model.base import ModelParams
from models.commons.model.pydantic import (
    EnhancedStringEnum,
    RequestModel,
    ResponseModel,
)

### SADIE Params


class SADIEParams(ModelParams):
    weights_version = "v1"
    display_name = "SADIE"
    base_model_slug = "sadie"
    log_identifier = "SADIE"
    batch_size = 8
    max_sequence_len = 2048


### SADIE Request


class SADIENumbering(EnhancedStringEnum):
    IMGT = "imgt"
    KABAT = "kabat"
    CHOTHIA = "chothia"


class SADIERegion(EnhancedStringEnum):
    IMGT = "imgt"
    KABAT = "kabat"
    CHOTHIA = "chothia"
    ABM = "abm"
    CONTACT = "contact"
    SCDR = "scdr"


class SADIEPredictRequestParams(RequestModel):
    region_assign: Optional[SADIERegion] = Field(
        default=SADIERegion.IMGT,
        description="Region definition used to assign CDR and framework boundaries (imgt, kabat, chothia, abm, contact, or scdr).",
    )
    scheme: Optional[SADIENumbering] = Field(
        default=SADIENumbering.CHOTHIA,
        description="Residue numbering scheme applied to the annotated sequence (imgt, kabat, or chothia).",
    )
    scfv: StrictBool = Field(
        default=False,
        description="When true, parse the input as a single-chain variable fragment (scFv) containing two linked domains.",
    )
    allowed_chain: list[StrictStr] = Field(
        default_factory=lambda: ["H", "K", "L"],  # default chains in SADIE library
        description="Chain types to consider during annotation (H=heavy, K=kappa, L=lambda, A/B/G/D=TCR chains).",
    )

    @validator("allowed_chain", pre=True, each_item=True)
    def _check_allowed_chain(cls, v):
        allowed = ["L", "H", "K", "A", "B", "G", "D"]
        v = v.upper()
        if v not in allowed:
            raise ValueError(
                f"Invalid chain '{v}'. allowed_chain must be subset of {allowed}"
            )
        return v


class SADIEPredictRequestItem(RequestModel):
    """Single sequence item for SADIE prediction."""

    sequence: StrictStr = Field(
        ...,
        min_length=1,
        max_length=SADIEParams.max_sequence_len,
        description="An antibody or TCR sequence in single-letter amino-acid codes.",
    )

    @validator("sequence", pre=True)
    def validate_sequence(cls, value):
        return validate_aa_extended(value)


class SADIEPredictRequest(RequestModel):
    """Batch prediction request for SADIE."""

    params: Optional[SADIEPredictRequestParams] = Field(
        default_factory=SADIEPredictRequestParams,
        description="Optional parameters controlling this action (defaults are used when omitted).",
    )
    items: list[SADIEPredictRequestItem] = Field(
        ...,
        description="Batch of inputs to process in a single request. Up to 8 sequences per request.",
    )

    @validator("items")
    def validate_items(cls, value):
        if not (1 <= len(value) <= SADIEParams.batch_size):
            raise ValueError(f"Must have 1 to {SADIEParams.batch_size} items.")
        return value


### SADIE Response


class SADIEPredictResponseResult(ResponseModel):
    domain_no: int = Field(
        description="Zero-based index of this domain within the input sequence (scFv inputs yield multiple domains).",
    )
    hmm_species: str = Field(
        description="Species identified by HMM profile matching against the reference database.",
    )
    chain_type: str = Field(
        description="Detected chain type: H (heavy), K (kappa), L (lambda), or A/B/G/D (TCR chains).",
    )
    e_value: float = Field(
        description="HMM alignment E-value; lower values indicate a more confident domain identification.",
    )
    score: float = Field(
        description="HMM alignment bit score; higher values indicate a better match to the reference HMM.",
    )
    identity_species: str = Field(
        description="Species assigned by sequence identity comparison against the germline reference database.",
    )
    v_gene: str = Field(
        description="Closest germline V-gene assignment (e.g. IGHV3-23*01).",
    )
    v_identity: float = Field(
        description="Percent identity of the input sequence to the assigned V-gene.",
    )
    j_gene: str = Field(
        description="Closest germline J-gene assignment (e.g. IGHJ4*02).",
    )
    j_identity: float = Field(
        description="Percent identity of the input sequence to the assigned J-gene.",
    )
    Chain: str = Field(
        description="Chain identifier used for this domain (H, K, L, A, B, G, or D).",
    )
    Numbering: list[int] = Field(
        description="Per-residue position numbers assigned according to the selected numbering scheme.",
    )
    Insertion: list[str] = Field(
        description="Per-residue insertion codes paired with the numbering (empty string when no insertion).",
    )
    scheme: str = Field(
        description="Numbering scheme applied to this domain (imgt, kabat, or chothia).",
    )
    region_definition: str = Field(
        description="Region definition used to assign CDR and framework boundaries.",
    )
    fwr1_aa_gaps: str = Field(
        description="Framework 1 (FWR1) amino-acid sequence including alignment gap characters.",
    )
    fwr1_aa_no_gaps: str = Field(
        description="Framework 1 (FWR1) amino-acid sequence with alignment gaps removed.",
    )
    cdr1_aa_gaps: str = Field(
        description="CDR1 amino-acid sequence including alignment gap characters.",
    )
    cdr1_aa_no_gaps: str = Field(
        description="CDR1 amino-acid sequence with alignment gaps removed.",
    )
    fwr2_aa_gaps: str = Field(
        description="Framework 2 (FWR2) amino-acid sequence including alignment gap characters.",
    )
    fwr2_aa_no_gaps: str = Field(
        description="Framework 2 (FWR2) amino-acid sequence with alignment gaps removed.",
    )
    cdr2_aa_gaps: str = Field(
        description="CDR2 amino-acid sequence including alignment gap characters.",
    )
    cdr2_aa_no_gaps: str = Field(
        description="CDR2 amino-acid sequence with alignment gaps removed.",
    )
    fwr3_aa_gaps: str = Field(
        description="Framework 3 (FWR3) amino-acid sequence including alignment gap characters.",
    )
    fwr3_aa_no_gaps: str = Field(
        description="Framework 3 (FWR3) amino-acid sequence with alignment gaps removed.",
    )
    cdr3_aa_gaps: str = Field(
        description="CDR3 amino-acid sequence including alignment gap characters.",
    )
    cdr3_aa_no_gaps: str = Field(
        description="CDR3 amino-acid sequence with alignment gaps removed.",
    )
    fwr4_aa_gaps: str = Field(
        description="Framework 4 (FWR4) amino-acid sequence including alignment gap characters.",
    )
    fwr4_aa_no_gaps: str = Field(
        description="Framework 4 (FWR4) amino-acid sequence with alignment gaps removed.",
    )
    leader: str = Field(
        description="Residues N-terminal to FWR1 that fall outside the annotated variable domain.",
    )
    follow: str = Field(
        description="Residues C-terminal to FWR4 that fall outside the annotated variable domain.",
    )


class SADIEPredictResponse(ResponseModel):
    results: list[SADIEPredictResponseResult] = Field(
        description="Per-input results, returned in the same order as the request items.",
    )
