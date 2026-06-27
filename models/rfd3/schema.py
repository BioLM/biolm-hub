"""Schema definitions for RFdiffusion3 API.

RFdiffusion3 is an all-atom generative diffusion model for biomolecular structure design.
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

### RFD3 Params


class RFD3Params(ModelParams):
    params_version = "v1"
    display_name = "RFdiffusion3"
    base_model_slug = "rfd3"
    log_identifier = "RFD3"
    batch_size = 1
    max_sequence_len = 2048
    max_num_designs = 16


### RFD3 Enums


class RFD3ConditioningMode(EnhancedStringEnum):
    """Conditioning modes for design."""

    UNCONDITIONAL = "unconditional"
    MOTIF_SCAFFOLDING = "motif_scaffolding"
    BINDER_DESIGN = "binder_design"
    PARTIAL_DIFFUSION = "partial_diffusion"
    SYMMETRIC_DESIGN = "symmetric_design"


### RFD3 Request


class RFD3Component(RequestModel):
    """A biomolecular component for design input."""

    name: str = Field(..., description="Component name")
    sequence: Optional[str] = Field(
        None,
        description="Sequence (if providing structure or for length determination)",
    )
    smiles: Optional[str] = Field(None, description="SMILES string for small molecule")
    ccd_code: Optional[str] = Field(
        None, description="Chemical Component Dictionary code"
    )
    structure_cif: Optional[str] = Field(
        None, description="Structure in mmCIF format (for fixed regions)"
    )
    chain_id: Optional[str] = Field(None, description="Chain identifier")
    fixed_atoms: Optional[list[str]] = Field(
        None, description="List of atom specifications to fix (e.g., ['A/ALA/10/CA'])"
    )
    fixed_residues: Optional[list[str]] = Field(
        None, description="List of residue specifications to fix (e.g., ['A/10-20'])"
    )


class RFD3DesignParams(RequestModel):
    """Parameters for RFdiffusion3 design."""

    # Diffusion sampling parameters
    num_diffusion_steps: int = Field(
        default=200, ge=50, le=500, description="Number of diffusion sampling steps"
    )
    diffusion_batch_size: int = Field(
        default=1,
        ge=1,
        le=RFD3Params.max_num_designs,
        description="Number of designs to generate",
    )
    seed: Optional[int] = Field(
        default=None, description="Random seed for reproducibility"
    )

    # Temperature/sampling controls
    temperature: float = Field(
        default=1.0, ge=0.1, le=2.0, description="Sampling temperature"
    )

    # Conditioning parameters
    conditioning_mode: RFD3ConditioningMode = Field(
        default=RFD3ConditioningMode.UNCONDITIONAL,
        description="Type of conditioning to apply",
    )

    # Symmetry parameters
    symmetry: Optional[str] = Field(
        None, description="Symmetry specification (e.g., 'C3', 'D2')"
    )
    cyclic_chains: Optional[list[str]] = Field(
        None, description="List of chain IDs to cyclize"
    )

    # Advanced sampling parameters
    step_scale: Optional[float] = Field(
        default=None,
        ge=1.0,
        le=2.0,
        description="Scales diffusion step size; higher → less diverse, more designable (default: 1.5)",
    )
    noise_scale: Optional[float] = Field(
        default=None,
        ge=1.0,
        le=2.0,
        description="Noise scale for diffusion (default: 1.003)",
    )
    center_option: Optional[str] = Field(
        default=None,
        description="Center option: 'all', 'motif', or 'diffuse' (default: 'all')",
    )

    # Output control
    output_format: str = Field(
        default="cif", description="Output format: 'cif' or 'pdb'"
    )
    include_trajectories: bool = Field(
        default=False, description="Include denoising trajectories in output"
    )


class RFD3DesignRequestInput(RequestModel):
    """Input specification for a design task."""

    name: str = Field(..., description="Name for this design task")
    components: list[RFD3Component] = Field(
        ..., min_length=1, description="List of components for design"
    )
    bonds: Optional[list[tuple[str, str]]] = Field(
        None, description="Custom bonds as pairs of atom specifications"
    )
    motif_selection: Optional[list[str]] = Field(
        None, description="Motif residue selections to scaffold around"
    )
    target_chain: Optional[str] = Field(
        None, description="Target chain ID for binder design"
    )
    # Input structure file (PDB or CIF)
    input_structure_path: Optional[str] = Field(
        None,
        description="Path to input PDB/CIF file (for motif scaffolding or partial diffusion)",
    )
    # Contig specification for motif scaffolding
    contig: Optional[str] = Field(
        None,
        description="Contig string specifying fixed/diffused regions (e.g., 'A1-100,50-80,/0')",
    )
    # Unindexed motifs (unknown sequence placement)
    unindex: Optional[list[str]] = Field(
        None,
        description="List of unindexed residue components (e.g., ['A107', 'A109', 'A126'])",
    )
    # Ligands to include
    ligands: Optional[list[str]] = Field(
        None,
        description="List of ligand residue names to include (e.g., ['ZN', 'NAI'])",
    )
    # Partial diffusion
    partial_t: Optional[float] = Field(
        None, ge=0.0, description="Noise level in Angstroms for partial diffusion"
    )
    # Length constraint
    length: Optional[str] = Field(
        None,
        description="Length constraint: integer or 'min-max' range (e.g., '200' or '180-200')",
    )


class RFD3DesignRequest(RequestModel):
    """Request for RFdiffusion3 design."""

    params: RFD3DesignParams = RFD3DesignParams()
    items: Annotated[
        list[RFD3DesignRequestInput],
        Field(min_length=1, max_length=RFD3Params.batch_size),
    ]


### RFD3 Response


class RFD3DesignResponseResult(ResponseModel):
    """Single design output from RFdiffusion3."""

    structure_cif: str = Field(..., description="Designed structure in mmCIF format")
    trajectory_cif: Optional[str] = Field(
        None, description="Denoising trajectory if requested"
    )


class RFD3DesignResponse(ResponseModel):
    """Response from RFdiffusion3 design."""

    results: list[list[RFD3DesignResponseResult]] = Field(
        ..., description="Design results corresponding to input items"
    )
