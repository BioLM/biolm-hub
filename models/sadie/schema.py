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
    params_version = "v1"
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
    region_assign: Optional[SADIERegion] = SADIERegion.IMGT
    scheme: Optional[SADIENumbering] = SADIENumbering.CHOTHIA
    scfv: StrictBool = False
    allowed_chain: list[StrictStr] = Field(
        default_factory=lambda: ["H", "K", "L"],  # default chains in SADIE library
        description="Which chains to include (default H, K, L)",
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
        ..., min_length=1, max_length=SADIEParams.max_sequence_len
    )

    @validator("sequence", pre=True)
    def validate_sequence(cls, value):
        return validate_aa_extended(value)


class SADIEPredictRequest(RequestModel):
    """Batch prediction request for SADIE."""

    params: Optional[SADIEPredictRequestParams] = SADIEPredictRequestParams()
    items: list[SADIEPredictRequestItem] = Field(...)

    @validator("items")
    def validate_items(cls, value):
        if not (1 <= len(value) <= SADIEParams.batch_size):
            raise ValueError(f"Must have 1 to {SADIEParams.batch_size} items.")
        return value


### SADIE Response


class SADIEPredictResponseResult(ResponseModel):
    domain_no: int
    hmm_species: str
    chain_type: str
    e_value: float
    score: float
    identity_species: str
    v_gene: str
    v_identity: float
    j_gene: str
    j_identity: float
    Chain: str
    Numbering: list[int]
    Insertion: list[str]
    scheme: str
    region_definition: str
    fwr1_aa_gaps: str
    fwr1_aa_no_gaps: str
    cdr1_aa_gaps: str
    cdr1_aa_no_gaps: str
    fwr2_aa_gaps: str
    fwr2_aa_no_gaps: str
    cdr2_aa_gaps: str
    cdr2_aa_no_gaps: str
    fwr3_aa_gaps: str
    fwr3_aa_no_gaps: str
    cdr3_aa_gaps: str
    cdr3_aa_no_gaps: str
    fwr4_aa_gaps: str
    fwr4_aa_no_gaps: str
    leader: str
    follow: str


class SADIEPredictResponse(ResponseModel):
    results: list[SADIEPredictResponseResult]
