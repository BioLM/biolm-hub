from functools import partial
from typing import Annotated, Optional, Union

from pydantic import Field, field_validator, model_validator

from models.commons.data.validator import validate_smiles
from models.commons.model.base import ModelParams
from models.commons.model.pydantic import (
    EnhancedStringEnum,
    RequestModel,
    ResponseModel,
)

### Boltz Params


# Boltz model versions
class BoltzModelVersion(EnhancedStringEnum):
    BOLTZ1 = "boltz1"
    BOLTZ2 = "boltz2"


# Boltz model parameters for app deployment
class BoltzModelParams(ModelParams):
    params_version = "v1"
    display_name = "Boltz"
    base_model_slug = "boltz"
    log_identifier = "Boltz"
    batch_size = 1
    max_sequence_len = 1024


### Boltz Requests


# MSA search mode for automatic MSA generation via MSA Search NIM
class MSASearchMode(EnhancedStringEnum):
    """Mode for automatic MSA generation via MSA Search NIM.

    - "fast": Uses UniRef30 + PDB70 databases only. Faster but less sensitive.
    - "standard": Uses all 5 databases (UniRef30, PDB70, UniRef90, MGnify, BFD).
      More sensitive but slower.

    When set on a predict request, protein entities without user-provided
    alignments will have MSA automatically generated before prediction.
    """

    FAST = "fast"
    STANDARD = "standard"


# Output parameters
class BoltzIncludeParams(EnhancedStringEnum):
    PAE = "pae"  # predicted aligned error
    PDE = "pde"  # predicted distance error
    PLDDT = "plddt"  # predicted lDDT
    EMBEDDINGS = "embeddings"  # single and pairwise embeddings


# Boltz predict parameters for input JSON
class BoltzAffinityProperty(RequestModel):
    """Affinity calculation property for Boltz YAML properties block."""

    binder: str  # Chain ID of the binder


# Base predict parameters (common to both Boltz1 and Boltz2)
class BoltzPredictParamsBase(RequestModel):
    recycling_steps: int = Field(default=3, ge=1, le=10)
    sampling_steps: int = Field(default=20, ge=1, le=200)
    diffusion_samples: int = Field(default=1, ge=1, le=10)
    step_scale: float = Field(default=1.638, ge=0.1, le=10.0)
    seed: Optional[int] = 42
    potentials: bool = True
    include: Optional[list[BoltzIncludeParams]] = Field(
        default_factory=partial(list, [])
    )

    # Automatic MSA generation via MSA Search NIM
    msa_search: Optional[MSASearchMode] = Field(
        default=None,
        description=(
            "Enable automatic MSA generation for protein entities that lack "
            "user-provided alignments. 'fast' uses UniRef30 + PDB70 (quicker), "
            "'standard' uses all 5 databases (more sensitive). Default is None (off)."
        ),
    )

    # MSA parameters (supported by both Boltz1 and Boltz2)
    max_msa_seqs: int = Field(
        default=8192,
        ge=1,
        le=32768,
        description="The maximum number of MSA sequences to use for prediction",
    )
    subsample_msa: bool = Field(
        default=False, description="Whether to subsample the MSA"
    )
    num_subsampled_msa: int = Field(
        default=1024,
        ge=1,
        le=8192,
        description="The number of MSA sequences to subsample",
    )


# Boltz1 predict parameters (no affinity support)
Boltz1PredictParams = BoltzPredictParamsBase


# Boltz2 predict parameters (with affinity support)
class Boltz2PredictParams(BoltzPredictParamsBase):
    # Affinity prediction parameters (Boltz2 only)
    affinity_mw_correction: bool = Field(
        default=False,
        description="Whether to add the Molecular Weight correction to the affinity value head",
    )
    sampling_steps_affinity: int = Field(
        default=200,
        ge=1,
        le=200,
        description="The number of sampling steps to use for affinity prediction",
    )
    diffusion_samples_affinity: int = Field(
        default=5,
        ge=1,
        le=50,
        description="The number of diffusion samples to use for affinity prediction",
    )
    affinity: Optional[BoltzAffinityProperty] = Field(
        default=None,
        description="Affinity calculation parameters, e.g. binder chain ID",
    )


# Backward compatibility - use Boltz2PredictParams as default
BoltzPredictParams = Boltz2PredictParams


# Modification model
class BoltzModification(RequestModel):
    position: int
    ccd: str


# Bond constraint model
class BoltzBondConstraint(RequestModel):
    """
    Specifies a covalent bond between two atoms (atom1 and atom2).
    - Only supported for CCD ligands and canonical residues (protein, DNA, RNA).
    - CHAIN_ID refers to the id of the residue set above.
    - RES_IDX is the index (starting from 1) of the residue (1 for ligands).
    - ATOM_NAME is the standardized atom name (see RCSB CIF file for the component).
    """

    atom1: list[Union[str, int]]
    atom2: list[Union[str, int]]


# Pocket constraint model
class BoltzPocketConstraint(RequestModel):
    """
    Specifies the residues associated with a ligand pocket.
    - binder: the chain binding to the pocket (can be a molecule, protein, DNA, or RNA).
    - contacts: list of [CHAIN_ID, RES_IDX/ATOM_NAME] associated with the pocket.
    - Only a single binder chain is supported.
    """

    binder: str
    contacts: list[list[Union[str, int]]]
    max_distance: Optional[float] = None

    @field_validator("binder")
    def validate_single_binder(cls, v):
        if isinstance(v, list):
            raise ValueError(
                "Only a single binder chain is supported in pocket constraints."
            )
        return v


# Contact constraint model
class BoltzContactConstraint(RequestModel):
    """
    Specifies a contact between two tokens (token1 and token2).
    - token1 and token2: [CHAIN_ID, RES_IDX/ATOM_NAME]
    - max_distance: maximum allowed distance in angstroms
    """

    token1: list[Union[str, int]]
    token2: list[Union[str, int]]
    max_distance: float


# Entity type for sequences
class BoltzEntityType(EnhancedStringEnum):
    PROTEIN = "protein"
    DNA = "dna"
    RNA = "rna"
    LIGAND = "ligand"


# Alignment database enum for Boltz
class BoltzAlignmentDatabase(EnhancedStringEnum):
    MGNIFY = "mgnify"
    SMALL_BFD = "small_bfd"
    UNIREF90 = "uniref90"


class BoltzEntity(RequestModel):
    id: Union[str, list[str]]
    type: BoltzEntityType
    sequence: Optional[str] = None
    smiles: Optional[str] = None
    ccd: Optional[str] = None
    alignment: Optional[dict[BoltzAlignmentDatabase, str]] = (
        None  # key: database enum, value: a3m file content
    )
    modifications: Optional[list[BoltzModification]] = None
    cyclic: bool = False

    @field_validator("sequence")
    def validate_sequence_for_type(cls, v, info):
        """Validate sequence is provided for appropriate entity types."""
        entity_type = info.data.get("type")
        if entity_type in [
            BoltzEntityType.PROTEIN,
            BoltzEntityType.DNA,
            BoltzEntityType.RNA,
        ]:
            if v is None:
                raise ValueError(
                    f"Sequence is required for {entity_type.value} entities"
                )
        elif entity_type == BoltzEntityType.LIGAND and v is not None:
            raise ValueError("Sequence should not be provided for ligand entities")
        return v

    @field_validator("smiles")
    def validate_smiles_for_type(cls, v, info):
        """Validate SMILES is only provided for ligands and has valid format."""
        entity_type = info.data.get("type")
        if entity_type != BoltzEntityType.LIGAND and v is not None:
            raise ValueError(
                f"SMILES should not be provided for {entity_type.value} entities"
            )
        if v is not None:
            v = validate_smiles(v)
        return v

    @field_validator("ccd")
    def validate_ccd_for_type(cls, v, info):
        """Validate CCD is only provided for ligands."""
        entity_type = info.data.get("type")
        if entity_type != BoltzEntityType.LIGAND and v is not None:
            raise ValueError(
                f"CCD should not be provided for {entity_type.value} entities"
            )
        return v

    @model_validator(mode="after")
    def validate_ligand_has_smiles_or_ccd(self):
        """Validate that ligand entities have either SMILES or CCD."""
        if self.type == BoltzEntityType.LIGAND:
            if self.smiles is None and self.ccd is None:
                raise ValueError(
                    "Either SMILES or CCD must be provided for ligand entities"
                )
        return self

    @field_validator("alignment")
    def validate_alignment_for_type(cls, v, info):
        """Validate alignment is only provided for proteins."""
        entity_type = info.data.get("type")
        if v is not None and entity_type != BoltzEntityType.PROTEIN:
            raise ValueError(
                f"Alignment can only be provided for protein entities, not {entity_type.value}"
            )
        return v

    @field_validator("modifications")
    def validate_modifications_for_type(cls, v, info):
        """Validate modifications are only provided for proteins."""
        entity_type = info.data.get("type")
        if v is not None and entity_type not in [
            BoltzEntityType.PROTEIN,
            BoltzEntityType.DNA,
            BoltzEntityType.RNA,
        ]:
            raise ValueError(
                f"Modifications can only be provided for protein, DNA or RNA entities, not {entity_type.value}"
            )
        return v


# Constraints for prediction
class BoltzPredictConstraints(RequestModel):
    """
    Optional field to specify additional information about the input structure.
    - bond: covalent bonds between atoms
    - pocket: residues associated with a ligand pocket
    - contact: contacts between tokens (residues/atoms)
    """

    bond: Optional[BoltzBondConstraint] = None
    pocket: Optional[BoltzPocketConstraint] = None
    contact: Optional[BoltzContactConstraint] = None

    @model_validator(mode="after")
    def validate_at_least_one_constraint(self):
        if not any([self.bond, self.pocket, self.contact]):
            raise ValueError(
                "At least one constraint (bond, pocket, or contact) must be provided"
            )
        return self


# Template model
class BoltzTemplate(RequestModel):
    cif: str
    chain_id: Optional[Union[str, list[str]]] = None
    template_id: Optional[Union[str, list[str]]] = None

    @field_validator("cif")
    def validate_cif_not_empty(cls, v):
        """Validate CIF content is not empty."""
        if not v or not v.strip():
            raise ValueError("CIF content cannot be empty")
        return v


# Predict request
# Base input class
class BoltzPredictRequestInputBase(RequestModel):
    # Both Boltz1 and Boltz2 use "molecules" convention
    molecules: list[BoltzEntity] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_molecules_provided(self):
        """Ensure molecules field is provided."""
        if not self.molecules:
            raise ValueError("Molecules must be provided")
        return self


# Boltz1 input (templates only, no constraints)
Boltz1PredictRequestInput = BoltzPredictRequestInputBase


# Boltz2 input (with constraints and templates)
class Boltz2PredictRequestInput(BoltzPredictRequestInputBase):
    constraints: Optional[list[BoltzPredictConstraints]] = None
    templates: Optional[list[BoltzTemplate]] = None

    @model_validator(mode="after")
    # TODO: Refactor to reduce complexity below 10
    def validate_template_and_constraint_chain_ids(self):  # noqa: C901
        def get_molecule_chain_ids(molecules):
            chain_ids = set()
            for mol in molecules:
                if isinstance(mol.id, str):
                    chain_ids.add(mol.id)
                elif isinstance(mol.id, list):
                    chain_ids.update(mol.id)
            return chain_ids

        # TODO: Refactor to reduce complexity below 10
        def check_constraints(constraints, molecule_chain_ids):  # noqa: C901
            for constraint in constraints or []:
                if constraint.bond:
                    if len(constraint.bond.atom1) > 0 and isinstance(
                        constraint.bond.atom1[0], str
                    ):
                        chain_id = constraint.bond.atom1[0]
                        if chain_id not in molecule_chain_ids:
                            raise ValueError(
                                f"Bond constraint atom1 chain_id '{chain_id}' not found in molecules"
                            )
                    if len(constraint.bond.atom2) > 0 and isinstance(
                        constraint.bond.atom2[0], str
                    ):
                        chain_id = constraint.bond.atom2[0]
                        if chain_id not in molecule_chain_ids:
                            raise ValueError(
                                f"Bond constraint atom2 chain_id '{chain_id}' not found in molecules"
                            )
                if constraint.pocket:
                    if constraint.pocket.binder not in molecule_chain_ids:
                        raise ValueError(
                            f"Pocket constraint binder '{constraint.pocket.binder}' not found in molecules"
                        )
                    for contact in constraint.pocket.contacts:
                        if len(contact) > 0 and isinstance(contact[0], str):
                            chain_id = contact[0]
                            if chain_id not in molecule_chain_ids:
                                raise ValueError(
                                    f"Pocket constraint contact chain_id '{chain_id}' not found in molecules"
                                )
                if constraint.contact:
                    if len(constraint.contact.token1) > 0 and isinstance(
                        constraint.contact.token1[0], str
                    ):
                        chain_id = constraint.contact.token1[0]
                        if chain_id not in molecule_chain_ids:
                            raise ValueError(
                                f"Contact constraint token1 chain_id '{chain_id}' not found in molecules"
                            )
                    if len(constraint.contact.token2) > 0 and isinstance(
                        constraint.contact.token2[0], str
                    ):
                        chain_id = constraint.contact.token2[0]
                        if chain_id not in molecule_chain_ids:
                            raise ValueError(
                                f"Contact constraint token2 chain_id '{chain_id}' not found in molecules"
                            )

        def check_templates(templates, molecule_chain_ids):
            for template in templates or []:
                if template.chain_id is not None:
                    if isinstance(template.chain_id, str):
                        if template.chain_id not in molecule_chain_ids:
                            raise ValueError(
                                f"Template chain_id '{template.chain_id}' not found in molecules"
                            )
                    elif isinstance(template.chain_id, list):
                        for chain_id in template.chain_id:
                            if chain_id not in molecule_chain_ids:
                                raise ValueError(
                                    f"Template chain_id '{chain_id}' not found in molecules"
                                )

        molecule_chain_ids = get_molecule_chain_ids(self.molecules)
        check_templates(self.templates, molecule_chain_ids)
        check_constraints(self.constraints, molecule_chain_ids)
        return self


# Backward compatibility - use Boltz2PredictRequestInput as default
BoltzPredictRequestInput = Boltz2PredictRequestInput


# Boltz1 request (no affinity support)
class Boltz1PredictRequest(RequestModel):
    items: Annotated[
        list[Boltz1PredictRequestInput],
        Field(min_length=1, max_length=BoltzModelParams.batch_size),
    ]
    params: Boltz1PredictParams = Boltz1PredictParams()


# Boltz2 request (with affinity support)
class Boltz2PredictRequest(RequestModel):
    items: Annotated[
        list[Boltz2PredictRequestInput],
        Field(min_length=1, max_length=BoltzModelParams.batch_size),
    ]
    params: Boltz2PredictParams = Boltz2PredictParams()

    @model_validator(mode="after")
    def validate_affinity_binder_exists(self):
        v = self.params
        items = self.items
        if v.affinity is None:
            return self
        all_chain_ids = set()
        for item in items:
            for mol in item.molecules:
                if isinstance(mol.id, str):
                    all_chain_ids.add(mol.id)
                elif isinstance(mol.id, list):
                    all_chain_ids.update(mol.id)
        if v.affinity.binder not in all_chain_ids:
            raise ValueError(
                f"Affinity binder '{v.affinity.binder}' not found in molecules"
            )
        return self


# Backward compatibility - use Boltz2PredictRequest as default
BoltzPredictRequest = Boltz2PredictRequest


### Boltz Responses


# Confidence scores
class BoltzChainScores(ResponseModel):
    ptm: dict[str, float]
    pair_chains_iptm: dict[str, dict[str, float]]


# Affinity scores
class BoltzAffinityScores(ResponseModel):
    affinity_pred_value: float  # Predicted binding affinity from the ensemble model
    affinity_probability_binary: (
        float  # Predicted binding likelihood from the ensemble model
    )
    affinity_pred_value1: (
        float  # Predicted binding affinity from the first model of the ensemble
    )
    affinity_probability_binary1: (
        float  # Predicted binding likelihood from the first model in the ensemble
    )
    affinity_pred_value2: (
        float  # Predicted binding affinity from the second model of the ensemble
    )
    affinity_probability_binary2: (
        float  # Predicted binding likelihood from the second model in the ensemble
    )


class BoltzConfidenceScores(ResponseModel):
    confidence_score: float
    ptm: float
    iptm: float
    ligand_iptm: float
    protein_iptm: float
    complex_plddt: float
    complex_iplddt: float
    complex_pde: float
    complex_ipde: float
    chains_ptm: dict[str, float]
    pair_chains_iptm: dict[str, dict[str, float]]
    pair_chains_ipae: Optional[dict[str, dict[str, float]]] = None
    pair_chains_ipsae: Optional[dict[str, dict[str, dict[str, float]]]] = None


# Embeddings response
class BoltzEmbeddings(ResponseModel):
    s: list[list[float]]  # single embeddings
    z: list[list[list[float]]]  # pairwise embeddings


# Predict response
class BoltzPredictResponseOutput(ResponseModel):
    model_config = {
        "populate_by_name": True,
        "extra": "forbid",
        "json_schema_extra": {
            "exclude_unset": True,
            "exclude_none": True,
        },
    }
    cif: str
    plddt: Optional[list[float]] = None  # a lot of data takes a while to transfer
    pae: Optional[list[list[float]]] = None
    pde: Optional[list[list[float]]] = None
    embeddings: Optional[BoltzEmbeddings] = None  # Optional embeddings if requested
    confidence: BoltzConfidenceScores
    affinity: Optional[BoltzAffinityScores] = (
        None  # Optional affinity predictions if available
    )


class BoltzPredictResponse(ResponseModel):
    model_config = {
        "populate_by_name": True,
        "extra": "forbid",
        "json_schema_extra": {
            "exclude_unset": True,
            "exclude_none": True,
        },
    }
    results: list[BoltzPredictResponseOutput]
