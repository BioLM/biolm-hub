"""Schema definitions for RosettaFold3 (RF3) API.

RosettaFold3 is an all-atom biomolecular structure prediction network.
Based on RosettaCommons/foundry implementation (BSD 3-Clause License).
"""

from typing import Annotated, Optional

from pydantic import Field, model_validator

from models.commons.model.base import ModelParams
from models.commons.model.pydantic import (
    EnhancedStringEnum,
    RequestModel,
    ResponseModel,
)

### RF3 Params


class RF3Params(ModelParams):
    weights_version = "v1"
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

    name: str = Field(
        ...,
        description="Human-readable label for this component; used as an identifier within the prediction job.",
    )
    type: RF3EntityType = Field(
        ...,
        description="Component entity type: protein, DNA, RNA, or ligand.",
    )
    sequence: Optional[str] = Field(
        default=None,
        max_length=RF3Params.max_sequence_len,
        description="A protein, DNA, or RNA sequence in single-letter codes (maximum 2048 characters).",
    )
    smiles: Optional[str] = Field(
        default=None, description="Ligand structure as a SMILES string."
    )
    ccd_code: Optional[str] = Field(
        default=None, description="Chemical Component Dictionary code for a ligand."
    )
    structure_path: Optional[str] = Field(
        default=None,
        description=(
            "Container-local path to a template structure file (CIF/PDB/SDF). "
            "Not usable by external callers; prefer structure_cif instead."
        ),
    )
    structure_cif: Optional[str] = Field(
        default=None,
        description="Template structure in mmCIF format (inline text). Use this to supply a structure template.",
    )
    chain_id: Optional[str] = Field(
        default=None, description='Chain identifier to operate on (e.g. "A").'
    )
    msa_path: Optional[str] = Field(
        default=None,
        description=(
            "Container-local path to an MSA file (.a3m). "
            "Not usable by external callers; prefer msa_content or alignment instead."
        ),
    )
    msa_content: Optional[str] = Field(
        default=None,
        description="Multiple-sequence alignment for the query sequence, in A3M format.",
    )
    alignment: Optional[dict[RF3AlignmentDatabase, str]] = Field(
        default=None, description="MSA alignments keyed by sequence database."
    )

    @model_validator(mode="after")
    def check_at_least_one_payload_field(self) -> "RF3Component":
        """Require at least one of sequence, smiles, or ccd_code."""
        if self.sequence is None and self.smiles is None and self.ccd_code is None:
            raise ValueError(
                "Each component must provide at least one of: sequence, smiles, or ccd_code."
            )
        return self


class RF3PredictParams(RequestModel):
    """Parameters for RF3 structure prediction."""

    # Recycling and sampling parameters
    n_recycles: int = Field(
        default=10, ge=2, le=20, description="Number of trunk recycling iterations."
    )
    num_steps: int = Field(
        default=200,
        ge=50,
        le=500,
        description="Number of diffusion sampling steps.",
    )
    diffusion_batch_size: int = Field(
        default=5,
        ge=1,
        le=RF3Params.max_num_samples,
        description="Number of diffusion samples to generate in parallel.",
    )
    seed: Optional[int] = Field(
        default=42, description="Random seed for reproducible sampling."
    )

    # Template parameters
    template_selection: Optional[list[str]] = Field(
        default=None,
        description="Atom selections for token-level templates (e.g. ['A', 'B/*/1-10']).",
    )
    ground_truth_conformer_selection: Optional[list[str]] = Field(
        default=None,
        description="Atom selections fixed to their ground-truth conformers (e.g. ['C', 'D']).",
    )
    cyclic_chains: Optional[list[str]] = Field(
        default=None,
        description="Chain identifiers to model as cyclic (e.g. cyclic peptides).",
    )

    # Early stopping
    early_stopping_plddt_threshold: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description=(
            "Early-stopping threshold as a fraction in [0, 1] (note: output pLDDT scores use a "
            "0–100 scale). Sampling stops early when the pLDDT fraction falls below this value."
        ),
    )

    # Output control
    one_model_per_file: bool = Field(
        default=False,
        description="Whether to write each predicted model to its own file.",
    )
    annotate_b_factor_with_plddt: bool = Field(
        default=False,
        description="Whether to store per-residue pLDDT in the B-factor column.",
    )

    # Confidence scores to include
    include_pae: bool = Field(
        default=False,
        description="Whether to include the predicted aligned error matrix in the response.",
    )
    include_plddt: bool = Field(
        default=True,
        description="Whether to include per-residue pLDDT scores in the response.",
    )


class RF3PredictRequestInput(RequestModel):
    """Input specification for a structure prediction task."""

    name: str = Field(
        ...,
        description="Human-readable label for this prediction job; used as the output directory name.",
    )
    components: list[RF3Component] = Field(
        ...,
        min_length=1,
        description="Biomolecular components that make up the complex to predict.",
    )
    bonds: Optional[list[tuple[str, str]]] = Field(
        default=None,
        description="Custom covalent bonds as pairs of atom specifications.",
    )


class RF3PredictRequest(RequestModel):
    """Request for RF3 structure prediction."""

    params: RF3PredictParams = Field(
        default_factory=RF3PredictParams,
        description="Optional parameters controlling this action (defaults are used when omitted).",
    )
    items: Annotated[
        list[RF3PredictRequestInput],
        Field(
            min_length=1,
            max_length=RF3Params.batch_size,
            description="Batch of inputs to process in a single request. Up to 1 input per request.",
        ),
    ]


### RF3 Response


class RF3ConfidenceScores(ResponseModel):
    """Confidence metrics for a prediction."""

    ptm: Optional[float] = Field(
        default=None,
        description="Predicted TM-score (pTM) for the overall structure (0–1).",
    )
    iptm: Optional[float] = Field(
        default=None,
        description="Interface predicted TM-score (ipTM) for multi-chain complexes (0–1).",
    )
    ranking_score: Optional[float] = Field(
        default=None, description="Composite score used to rank diffusion samples."
    )
    has_clash: Optional[bool] = Field(
        default=None,
        description="Whether the predicted structure contains steric clashes.",
    )
    plddt: Optional[list[float]] = Field(
        default=None,
        description="Per-residue pLDDT confidence score (0–100; higher is more confident).",
    )
    pae: Optional[list[list[float]]] = Field(
        default=None, description="Predicted aligned error (PAE) matrix, in Ångströms."
    )


class RF3PredictResponseResult(ResponseModel):
    """Single prediction output from RF3."""

    structure_cif: str = Field(..., description="Predicted structure in mmCIF format.")
    confidence: RF3ConfidenceScores = Field(
        ...,
        description="Confidence scores for the prediction (pTM, ipTM, pLDDT, PAE, ranking).",
    )
    early_stopped: bool = Field(
        default=False,
        description="Whether this sample was stopped early on low confidence.",
    )
    sample_idx: int = Field(
        ..., description="Index of this sample within the diffusion batch."
    )


class RF3PredictResponse(ResponseModel):
    """Response from RF3 structure prediction."""

    results: list[list[RF3PredictResponseResult]] = Field(
        ...,
        description="Per-input results, returned in the same order as the request items.",
    )
