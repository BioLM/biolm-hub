"""Schema definitions for RosettaFold3 (RF3) API.

RosettaFold3 is an all-atom biomolecular structure prediction network.
Based on RosettaCommons/foundry implementation (BSD 3-Clause License).
"""

from typing import Annotated, Optional

from pydantic import Field

from models.commons.model.base import ModelParams
from models.commons.model.pydantic import (
    EnhancedStringEnum,
    RequestModel,
    ResponseModel,
)

### RF3 Params


class RF3Params(ModelParams):
    params_version = "v1"
    display_name = "RosettaFold3"
    base_model_slug = "rf3"
    log_identifier = "RF3"
    batch_size = 1
    max_sequence_len = 2048
    max_num_samples = 10


### RF3 Enums


class RF3AlignmentDatabase(EnhancedStringEnum):
    """MSA alignment database options."""

    MGNIFY = "mgnify"
    SMALL_BFD = "small_bfd"
    UNIREF90 = "uniref90"


class RF3EntityType(EnhancedStringEnum):
    """Entity types for RF3 input."""

    PROTEIN = "protein"
    DNA = "DNA"
    RNA = "RNA"
    LIGAND = "ligand"


### RF3 Request


class RF3Component(RequestModel):
    """A biomolecular component for structure prediction."""

    name: str = Field(..., description="Component name")
    type: RF3EntityType = Field(..., description="Entity type")
    sequence: Optional[str] = Field(None, description="Sequence string")
    smiles: Optional[str] = Field(None, description="SMILES string for small molecule")
    ccd_code: Optional[str] = Field(
        None, description="Chemical Component Dictionary code"
    )
    structure_path: Optional[str] = Field(
        None, description="Path to structure file (CIF/PDB/SDF)"
    )
    structure_cif: Optional[str] = Field(None, description="Structure in mmCIF format")
    chain_id: Optional[str] = Field(None, description="Chain identifier")
    msa_path: Optional[str] = Field(None, description="Path to MSA file (.a3m)")
    msa_content: Optional[str] = Field(None, description="MSA content in A3M format")
    alignment: Optional[dict[RF3AlignmentDatabase, str]] = Field(
        None, description="MSA alignments by database"
    )


class RF3PredictParams(RequestModel):
    """Parameters for RF3 structure prediction."""

    # Recycling and sampling parameters
    n_recycles: int = Field(
        default=10, ge=0, le=20, description="Number of trunk recycles"
    )
    num_steps: int = Field(
        default=200, ge=50, le=500, description="Number of diffusion sampling steps"
    )
    diffusion_batch_size: int = Field(
        default=5,
        ge=1,
        le=RF3Params.max_num_samples,
        description="Number of output structures to generate",
    )
    seed: Optional[int] = Field(
        default=42, description="Random seed for reproducibility"
    )

    # Template parameters
    template_selection: Optional[list[str]] = Field(
        None,
        description="Atom selections for token-level templates (e.g., ['A', 'B/*/1-10'])",
    )
    ground_truth_conformer_selection: Optional[list[str]] = Field(
        None,
        description="Atom selections for ground truth conformers (e.g., ['C', 'D'])",
    )
    cyclic_chains: Optional[list[str]] = Field(
        None, description="List of chain IDs to cyclize"
    )

    # Early stopping
    early_stopping_plddt_threshold: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description="pLDDT threshold for early stopping",
    )

    # Output control
    one_model_per_file: bool = Field(
        default=False, description="Save each model to separate file"
    )
    annotate_b_factor_with_plddt: bool = Field(
        default=False, description="Annotate B-factor column with pLDDT"
    )

    # Confidence scores to include
    include_pae: bool = Field(
        default=False, description="Include Predicted Aligned Error matrix"
    )
    include_plddt: bool = Field(
        default=True, description="Include per-residue pLDDT scores"
    )


class RF3PredictRequestInput(RequestModel):
    """Input specification for a structure prediction task."""

    name: str = Field(..., description="Name for this prediction task")
    components: list[RF3Component] = Field(
        ..., min_length=1, description="List of components for prediction"
    )
    bonds: Optional[list[tuple[str, str]]] = Field(
        None, description="Custom bonds as pairs of atom specifications"
    )


class RF3PredictRequest(RequestModel):
    """Request for RF3 structure prediction."""

    params: RF3PredictParams = RF3PredictParams()
    items: Annotated[
        list[RF3PredictRequestInput],
        Field(min_length=1, max_length=RF3Params.batch_size),
    ]


### RF3 Response


class RF3ConfidenceScores(ResponseModel):
    """Confidence metrics for a prediction."""

    ptm: Optional[float] = Field(None, description="Predicted TM-score")
    iptm: Optional[float] = Field(
        None, description="Interface predicted TM-score (multi-chain)"
    )
    ranking_score: Optional[float] = Field(None, description="Overall ranking score")
    has_clash: Optional[bool] = Field(None, description="Whether structure has clashes")
    plddt: Optional[list[float]] = Field(None, description="Per-residue pLDDT scores")
    pae: Optional[list[list[float]]] = Field(
        None, description="Predicted Aligned Error matrix"
    )


class RF3PredictResponseResult(ResponseModel):
    """Single prediction output from RF3."""

    structure_cif: str = Field(..., description="Predicted structure in mmCIF format")
    confidence: RF3ConfidenceScores = Field(..., description="Confidence metrics")
    early_stopped: bool = Field(
        default=False, description="Whether prediction was early-stopped"
    )
    sample_idx: int = Field(..., description="Sample index within diffusion batch")


class RF3PredictResponse(ResponseModel):
    """Response from RF3 structure prediction."""

    results: list[list[RF3PredictResponseResult]] = Field(
        ..., description="Prediction results corresponding to input items"
    )
