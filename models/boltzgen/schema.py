import re
from typing import Annotated, Any, Optional, Union

from pydantic import BeforeValidator, Field, field_validator, model_validator

from models.commons.data.structure_validator import validate_cif, validate_pdb
from models.commons.model.base import ModelParams
from models.commons.model.pydantic import (
    EnhancedStringEnum,
    RequestModel,
    ResponseModel,
)
from models.commons.util.config import max_pdb_str_len

# Regex for a single res_index token: an integer, a range (N..M, ..M, N..), or "all".
# Tokens can be comma-separated, e.g. "1..5,10,20..30".
_RES_INDEX_TOKEN = r"(?:\d+\.\.\d+|\.\.\d+|\d+\.\.|\d+)"
_RES_INDEX_RE = re.compile(rf"^(?:all|{_RES_INDEX_TOKEN}(?:,{_RES_INDEX_TOKEN})*)$")

# Regex for additional_filters entries: metric_name followed by comparison operator and
# numeric threshold (optionally negative).  E.g. "plddt>70", "affinity>-5.0".
_FILTER_RE = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_]*[><]=?-?\d+(\.\d+)?$")

# Type alias used by multiple schema classes for residue index fields.
# Accepts a single int, a range/list string like "10..16" or "1,5,10",
# or a list mixing ints and range strings.
ResIndex = Optional[Union[str, int, list[Union[str, int]]]]

# Chain ID field: a single chain letter like "A" or a list ["A", "B"].
ChainId = Union[str, list[str]]


def _validate_res_index_str(value: str) -> None:
    """Raise ValueError if *value* is not a valid boltzgen res_index string."""
    if not _RES_INDEX_RE.match(value.replace(" ", "")):
        raise ValueError(
            f"Invalid res_index format: {value!r}. "
            "Expected an integer, a range (N..M, ..M, N..), "
            "comma-separated combinations (e.g. '1..5,10,20..30'), or 'all'."
        )


### BoltzGen Model Parameters


class BoltzGenParams(ModelParams):
    weights_version = "v1"
    display_name = "BoltzGen"
    base_model_slug = "boltzgen"
    log_identifier = "BOLTZGEN"
    batch_size = 1
    max_sequence_len = 2048


### BoltzGen Request


class BoltzGenProtocol(EnhancedStringEnum):
    PROTEIN_ANYTHING = "protein-anything"
    PEPTIDE_ANYTHING = "peptide-anything"
    PROTEIN_SMALL_MOLECULE = "protein-small_molecule"
    NANOBODY_ANYTHING = "nanobody-anything"


class _ResIndexValidatorMixin:
    """Shared validator for models that have a ``res_index`` field."""

    @field_validator("res_index", mode="after", check_fields=False)
    @classmethod
    def _check_res_index(cls, v: ResIndex) -> ResIndex:
        if v is None:
            return v
        if isinstance(v, int):
            if v < 1:
                raise ValueError(f"res_index must be >= 1, got {v}")
            return v
        if isinstance(v, str):
            _validate_res_index_str(v)
            return v
        if isinstance(v, list):
            for item in v:
                if isinstance(item, int):
                    if item < 1:
                        raise ValueError(f"res_index values must be >= 1, got {item}")
                elif isinstance(item, str):
                    _validate_res_index_str(item)
            return v
        return v


class BoltzGenChainSelector(_ResIndexValidatorMixin, RequestModel):
    """Selects a chain (or subset of residues) for include/exclude/reset operations.

    Used by ``include``, ``exclude``, and ``reset_res_index`` fields on file entities
    and at the top level of a design request item.
    """

    id: ChainId = Field(
        description="Chain ID or list of chain IDs to select (e.g. 'A' or ['A', 'B'])."
    )
    res_index: ResIndex = Field(
        default=None,
        description=(
            "Residue positions within the chain. Uses 1-based indexing. "
            "Accepts an integer (5), a range ('10..16'), open ranges ('..10', '20..'), "
            "or comma-separated combinations ('1..5,10,20..30'). "
            "If omitted, the entire chain is selected."
        ),
    )


class BoltzGenBindingType(RequestModel):
    """Specifies binding-site residues for a chain, used to bias diffusion toward interface contacts."""

    chain: ChainId = Field(
        description="Chain ID or list of chain IDs this binding constraint applies to."
    )
    binding: ResIndex = Field(
        default=None,
        description=(
            "Residue positions that should be at the binding interface. "
            "Accepts the same formats as res_index, or 'all'."
        ),
    )
    not_binding: ResIndex = Field(
        default=None,
        description=(
            "Residue positions that should NOT be at the binding interface. "
            "Accepts the same formats as res_index, or 'all'."
        ),
    )


class BoltzGenStructureGroup(RequestModel):
    """Groups chains together to control their structural visibility during design."""

    group: dict[str, Union[str, int, list[Union[str, int]]]] = Field(
        description=(
            "Mapping of chain IDs to residue indices defining the group membership. "
            "Use 'all' as the id to target all residues."
        )
    )
    visibility: int = Field(
        default=1,
        ge=0,
        le=2,
        description=(
            "Structural visibility level for this group. "
            "0 = fully masked, 1 = partial visibility (default), 2 = fully visible (fixed)."
        ),
    )


class BoltzGenSecondaryStructureSpec(RequestModel):
    """Constrains secondary structure assignments for residues in a chain during design."""

    chain: ChainId = Field(
        description="Chain ID or list of chain IDs to apply secondary structure constraints to."
    )
    loop: ResIndex = Field(
        default=None,
        description="Residue positions that should adopt loop (coil) secondary structure.",
    )
    helix: ResIndex = Field(
        default=None,
        description="Residue positions that should adopt alpha-helix secondary structure.",
    )
    sheet: ResIndex = Field(
        default=None,
        description="Residue positions that should adopt beta-sheet secondary structure.",
    )


class BoltzGenDesignSpec(_ResIndexValidatorMixin, RequestModel):
    """Marks residues in a chain as designable (sequence will be optimised by the model).

    Structurally identical to ``BoltzGenChainSelector`` but uses ``chain`` instead
    of ``id`` to match the boltzgen YAML format for ``design`` / ``not_design`` fields.
    """

    chain: ChainId = Field(
        description="Chain ID or list of chain IDs whose residues are designable."
    )
    res_index: ResIndex = Field(
        default=None,
        description=(
            "Residue positions to make designable. Uses 1-based indexing. "
            "Accepts an integer, a range ('10..16'), or comma-separated combinations ('26..34,52..59'). "
            "If omitted, the entire chain is treated as designable."
        ),
    )


class BoltzGenDesignInsertion(RequestModel):
    """Defines an insertion site where new residues may be inserted during design."""

    insertion: dict[str, Union[str, int]] = Field(
        description=(
            "Insertion site specification with keys: "
            "'id' (chain ID, e.g. 'B'), "
            "'res_index' (position to insert after, e.g. 26), "
            "'num_residues' (count or range, e.g. '1..5')."
        )
    )

    @field_validator("insertion", mode="after")
    @classmethod
    def _check_insertion_keys(
        cls, v: dict[str, Union[str, int]]
    ) -> dict[str, Union[str, int]]:
        if "id" not in v:
            raise ValueError("insertion must contain an 'id' key (chain ID)")
        if "res_index" not in v:
            raise ValueError("insertion must contain a 'res_index' key")
        return v


class BoltzGenFileEntity(RequestModel):
    """File entity for loading structures from CIF/PDB files.

    The file content should be provided as either `cif` or `pdb` string.
    The file will be written to a temporary location when processing.
    """

    cif: Optional[Annotated[str, BeforeValidator(validate_cif)]] = Field(
        default=None,
        min_length=1,
        max_length=max_pdb_str_len,
        description="Structure content in mmCIF format. Exactly one of 'cif' or 'pdb' must be provided.",
    )
    pdb: Optional[Annotated[str, BeforeValidator(validate_pdb)]] = Field(
        default=None,
        min_length=1,
        max_length=max_pdb_str_len,
        description="Structure content in PDB format. Exactly one of 'cif' or 'pdb' must be provided.",
    )
    include: Optional[list[BoltzGenChainSelector]] = Field(
        default=None,
        description=(
            "Chains (and optionally residues) from the file to include in the design system. "
            "If omitted, all chains are included."
        ),
    )
    exclude: Optional[list[BoltzGenChainSelector]] = Field(
        default=None,
        description=(
            "Chains (and optionally residues) from the file to exclude from the design system. "
            "Useful for removing non-essential chains like crystallographic partners."
        ),
    )
    include_proximity: Optional[list[dict[str, Any]]] = Field(
        default=None,
        description=(
            "Include residues that are spatially proximate to specified reference residues. "
            "Each entry is a dict matching the boltzgen YAML proximity format."
        ),
    )
    binding_types: Optional[Union[str, list[BoltzGenBindingType]]] = Field(
        default=None,
        description=(
            "Binding-site constraints for chains in this file entity. "
            "Pass 'auto' to infer binding sites automatically, or provide explicit per-chain specs."
        ),
    )
    structure_groups: Optional[list[BoltzGenStructureGroup]] = Field(
        default=None,
        description=(
            "Groups of chains with a shared visibility level during diffusion. "
            "Controls how much structural context each group provides to the model."
        ),
    )
    design: Optional[list[BoltzGenDesignSpec]] = Field(
        default=None,
        description=(
            "Chains and residues that are designable (sequence will be optimised). "
            "If omitted alongside not_design, the protocol default applies."
        ),
    )
    not_design: Optional[list[BoltzGenDesignSpec]] = Field(
        default=None,
        description=(
            "Residues to explicitly lock (exclude from design), even if they fall within a 'design' spec. "
            "Takes precedence over entries in 'design'."
        ),
    )
    secondary_structure: Optional[list[BoltzGenSecondaryStructureSpec]] = Field(
        default=None,
        description="Secondary structure constraints (helix, sheet, loop) for residues in this entity.",
    )
    design_insertions: Optional[list[BoltzGenDesignInsertion]] = Field(
        default=None,
        description="Insertion sites where the model may insert additional residues during design.",
    )
    fuse: Optional[str] = Field(
        default=None,
        description=(
            "Chain ID to fuse this entity's chain into. When set, the two chains are treated as "
            "a single contiguous chain by the model."
        ),
    )
    use_assembly: Optional[bool] = Field(
        default=None,
        description=(
            "Whether to load the biological assembly from the structure file rather than the asymmetric unit. "
            "Defaults to False. Useful when the functional form is a homo-oligomer."
        ),
    )
    reset_res_index: Optional[list[BoltzGenChainSelector]] = Field(
        default=None,
        description=(
            "Reset residue numbering to start from 1 for the specified chains. "
            "Commonly needed in scaffold redesign workflows where the input structure has non-standard numbering."
        ),
    )
    add_cyclization: Optional[list[dict[str, Any]]] = Field(
        default=None,
        description=(
            "Add covalent cyclization bonds (e.g. head-to-tail) to specified chains. "
            "Each entry is a dict matching the boltzgen YAML cyclization format. "
            "Use for cyclic peptide or cyclic protein design."
        ),
    )
    msa: Optional[Union[int, str]] = Field(
        default=None,
        description=(
            "Multiple sequence alignment (MSA) mode for this entity. "
            "0 = auto-generate MSA (default behaviour), -1 = no MSA (single-sequence mode), "
            "or provide a path to a pre-computed MSA file."
        ),
    )

    @model_validator(mode="after")
    def validate_file_provided(self) -> "BoltzGenFileEntity":
        """Validate that either CIF or PDB content is provided."""
        if not self.cif and not self.pdb:
            raise ValueError("Either 'cif' or 'pdb' must be provided for file entities")
        if self.cif and self.pdb:
            raise ValueError(
                "Cannot provide both 'cif' and 'pdb' for the same file entity"
            )
        return self


class BoltzGenProteinEntity(RequestModel):
    """A protein chain defined by sequence or length, to be placed in the design system."""

    id: Union[str, list[str]] = Field(
        description="Chain ID or list of chain IDs for this protein entity (e.g. 'A' or ['A', 'B'])."
    )
    sequence: Union[str, int, dict[str, Union[str, int]]] = Field(
        description=(
            "Defines the protein chain length and any fixed residues. "
            "Pass an integer (e.g. 50) to design a chain of that exact length with all residues free. "
            "Pass a range string (e.g. '30..50') to allow variable length. "
            "Pass an amino-acid sequence string (e.g. 'MKVL...') to fix the entire sequence. "
            "Pass a dict of {residue_index: amino_acid} to fix only specific positions."
        )
    )
    cyclic: bool = Field(
        default=False,
        description=(
            "Whether this protein chain is cyclic (head-to-tail peptide bond). "
            "When True, boltzgen adds the appropriate cyclization bond during design."
        ),
    )
    secondary_structure: Optional[list[BoltzGenSecondaryStructureSpec]] = Field(
        default=None,
        description="Secondary structure constraints (helix, sheet, loop) for residues in this chain.",
    )
    binding_types: Optional[Union[str, list[BoltzGenBindingType]]] = Field(
        default=None,
        description=(
            "Binding-site constraints for this chain. "
            "Pass 'auto' to infer binding sites automatically, or provide explicit per-chain specs."
        ),
    )
    msa: Optional[Union[int, str]] = Field(
        default=None,
        description=(
            "Multiple sequence alignment (MSA) mode for this entity. "
            "0 = auto-generate MSA (default behaviour), -1 = no MSA (single-sequence mode), "
            "or provide a path to a pre-computed MSA file."
        ),
    )


class BoltzGenLigandEntity(RequestModel):
    """A small-molecule ligand entity defined by CCD code or SMILES string."""

    id: Union[str, list[str]] = Field(
        description="Chain ID or list of chain IDs for this ligand entity (e.g. 'L' or ['L1', 'L2'])."
    )
    ccd: Optional[str] = Field(
        default=None,
        description=(
            "Chemical Component Dictionary (CCD) code identifying the ligand (e.g. 'ATP', 'HEM'). "
            "Use this for standard ligands with a PDB CCD entry. "
            "Exactly one of 'ccd' or 'smiles' must be provided."
        ),
    )
    smiles: Optional[str] = Field(
        default=None,
        description=(
            "SMILES string defining the ligand chemistry. "
            "Use this for non-standard or novel small molecules. "
            "Exactly one of 'ccd' or 'smiles' must be provided."
        ),
    )
    binding_types: Optional[Union[str, list[BoltzGenBindingType]]] = Field(
        default=None,
        description=(
            "Binding-site constraints for this ligand. "
            "Pass 'auto' to infer binding sites automatically, or provide explicit per-chain specs."
        ),
    )

    @model_validator(mode="after")
    def validate_ligand_has_ccd_or_smiles(self) -> "BoltzGenLigandEntity":
        """Validate that ligand entities have either SMILES or CCD."""
        if self.ccd is None and self.smiles is None:
            raise ValueError(
                "Either SMILES or CCD must be provided for ligand entities"
            )
        return self


# Union type for entity - using discriminated union pattern
class BoltzGenEntity(RequestModel):
    """Entity specification - can be protein, ligand, or file.

    This uses a discriminated union pattern where exactly one of
    protein, ligand, or file must be provided.
    """

    protein: Optional[BoltzGenProteinEntity] = Field(
        default=None,
        description="A protein chain defined by sequence or length. Use for chains that will be designed or held fixed.",
    )
    ligand: Optional[BoltzGenLigandEntity] = Field(
        default=None,
        description="A small-molecule ligand defined by CCD code or SMILES. Use for protein-small_molecule protocols.",
    )
    file: Optional[BoltzGenFileEntity] = Field(
        default=None,
        description="A structure loaded from a CIF or PDB file. Use when the scaffold or reference structure is pre-determined.",
    )
    dna: Optional[dict[str, Any]] = Field(
        default=None,
        description="A DNA chain entity. Follows the same structure as protein entities (id, sequence, etc.).",
    )
    rna: Optional[dict[str, Any]] = Field(
        default=None,
        description="An RNA chain entity. Follows the same structure as protein entities (id, sequence, etc.).",
    )

    @model_validator(mode="after")
    def validate_exactly_one_entity_type(self) -> "BoltzGenEntity":
        """Validate that exactly one entity type is specified."""
        entity_types = [
            self.protein,
            self.ligand,
            self.file,
            self.dna,
            self.rna,
        ]
        if sum(1 for et in entity_types if et is not None) != 1:
            raise ValueError(
                "Exactly one entity type (protein, ligand, file, dna, rna) must be specified"
            )
        return self


class BoltzGenBondConstraint(RequestModel):
    """Forces a covalent bond between two specific atoms across any two chains."""

    atom1: list[Union[str, int]] = Field(
        description="Atom identifier for the first atom, as [chain_id, res_index, atom_name] (e.g. ['A', 1, 'CA'])."
    )
    atom2: list[Union[str, int]] = Field(
        description="Atom identifier for the second atom, as [chain_id, res_index, atom_name]."
    )


class BoltzGenContactConstraint(RequestModel):
    """Requires two residue tokens to be within a maximum Cα–Cα distance of each other."""

    token1: list[Union[str, int]] = Field(
        description="Token identifier for the first residue, as [chain_id, res_index] (e.g. ['A', 5])."
    )
    token2: list[Union[str, int]] = Field(
        description="Token identifier for the second residue, as [chain_id, res_index]."
    )
    max_distance: float = Field(
        description="Maximum allowed Cα–Cα distance in Ångströms between the two tokens."
    )


class BoltzGenPocketConstraint(RequestModel):
    """Constrains a binder chain to be in contact with specified pocket residues on a target chain."""

    binder: str = Field(
        description="Chain ID of the binder (the chain being designed to engage the pocket)."
    )
    contacts: list[list[Union[str, int]]] = Field(
        description=(
            "List of pocket residue tokens on the target chain that the binder must contact. "
            "Each entry is [chain_id, res_index] (e.g. [['B', 42], ['B', 56]])."
        )
    )
    max_distance: Optional[float] = Field(
        default=None,
        description=(
            "Maximum Cα–Cα distance (Å) used to define 'contact'. "
            "If omitted, the boltzgen default threshold is used."
        ),
    )


class BoltzGenTotalLengthConstraint(RequestModel):
    """Constrains the total number of designable residues across all chains."""

    min: Optional[int] = Field(
        default=None,
        description="Minimum total residue count across all designable chains.",
    )
    max: Optional[int] = Field(
        default=None,
        description="Maximum total residue count across all designable chains.",
    )


class BoltzGenConstraint(RequestModel):
    """A single structural constraint applied during diffusion. Exactly one constraint type must be set."""

    bond: Optional[BoltzGenBondConstraint] = Field(
        default=None,
        description="Force a covalent bond between two atoms (e.g. for disulfide bonds or linker attachment).",
    )
    contact: Optional[BoltzGenContactConstraint] = Field(
        default=None,
        description="Require two residues to be within a maximum Cα–Cα distance.",
    )
    pocket: Optional[BoltzGenPocketConstraint] = Field(
        default=None,
        description="Constrain a binder chain to contact a set of pocket residues on a target chain.",
    )
    total_len: Optional[BoltzGenTotalLengthConstraint] = Field(
        default=None,
        description="Bound the total number of designable residues across all chains.",
    )

    @model_validator(mode="after")
    def validate_at_least_one_constraint(self) -> "BoltzGenConstraint":
        """Validate that at least one constraint type is specified."""
        constraint_types = [
            self.bond,
            self.contact,
            self.pocket,
            self.total_len,
        ]
        if sum(1 for ct in constraint_types if ct is not None) != 1:
            raise ValueError(
                "Exactly one constraint type (bond, contact, pocket, total_len) must be specified"
            )
        return self


class BoltzGenPipelineStep(EnhancedStringEnum):
    """Available pipeline steps."""

    DESIGN = "design"
    INVERSE_FOLDING = "inverse_folding"
    FOLDING = "folding"
    DESIGN_FOLDING = "design_folding"
    AFFINITY = "affinity"
    ANALYSIS = "analysis"
    FILTERING = "filtering"


class BoltzGenDesignParams(RequestModel):
    """Pipeline-level parameters controlling how BoltzGen generates and ranks designs."""

    protocol: BoltzGenProtocol = Field(
        default=BoltzGenProtocol.PROTEIN_ANYTHING,
        description=(
            "Design protocol that determines what is being designed and how. "
            "'protein-anything' designs a protein binder against any target chain. "
            "'peptide-anything' designs a short peptide binder. "
            "'protein-small_molecule' designs a protein that binds a specified small-molecule ligand. "
            "'nanobody-anything' designs a nanobody-format binder."
        ),
    )
    steps: Optional[list[BoltzGenPipelineStep]] = Field(
        default=None,
        description=(
            "Ordered list of pipeline steps to execute. If omitted, all steps run in the default order: "
            "design → inverse_folding → folding → design_folding → affinity → analysis → filtering. "
            "Provide an explicit list to run a subset (e.g. ['design'] for backbone-only runs). "
            "Steps are always executed in pipeline order regardless of the order listed here."
        ),
    )
    num_designs: int = Field(
        default=100,
        ge=1,
        le=500,
        description=(
            "Total number of backbone structures to generate in the 'design' step. "
            "This is the size of the candidate pool that all subsequent steps (inverse folding, "
            "folding, affinity, analysis) will process. "
            "A larger pool gives the filtering step more diversity to select from, "
            "but increases compute time proportionally. "
            "Default is 100. Maximum is 500. "
            "See also: 'budget', which controls how many designs are returned after filtering."
        ),
    )
    budget: int = Field(
        default=100,
        ge=1,
        le=500,
        description=(
            "Number of final designs to return after the 'filtering' step applies "
            "diversity-optimised ranking. The filtering step scores all 'num_designs' candidates, "
            "then selects this many using a quality-vs-diversity trade-off (controlled by 'alpha'). "
            "Must be ≤ num_designs. Has no effect if the 'filtering' step is not included in 'steps'. "
            "See also: 'num_designs' (the full candidate pool size) and 'alpha' (diversity weight)."
        ),
    )
    diffusion_batch_size: Optional[int] = Field(
        default=None,
        ge=1,
        le=100,
        description="Number of diffusion samples to generate in parallel.",
    )
    step_scale: Optional[float] = Field(
        default=None,
        ge=0.1,
        le=10.0,
        description=(
            "Fixed step scale (noise schedule multiplier) for the diffusion sampler. "
            "Lower values produce more conservative, less diverse structures. "
            "Higher values produce more diverse but potentially lower-quality structures. "
            "If omitted, boltzgen uses its adaptive default."
        ),
    )
    noise_scale: Optional[float] = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description=(
            "Noise injection scale applied during diffusion sampling (0.0–1.0). "
            "0.0 = fully deterministic sampling, 1.0 = maximum stochasticity. "
            "If omitted, boltzgen uses its default noise schedule."
        ),
    )
    inverse_fold_num_sequences: int = Field(
        default=1,
        ge=1,
        le=10,
        description=(
            "Number of amino-acid sequences to generate per backbone in the 'inverse_folding' step. "
            "Each backbone from 'num_designs' gets this many sequence candidates, so the total "
            "sequences entering the folding step is num_designs × inverse_fold_num_sequences. "
            "Increasing this improves sequence diversity at the cost of proportionally more compute "
            "in the folding and affinity steps."
        ),
    )
    inverse_fold_avoid: Optional[str] = Field(
        default=None,
        description=(
            "Amino acids to exclude from inverse-folding predictions, as a string of one-letter codes "
            "(e.g. 'KEC' to disallow lysine, glutamate, and cysteine). "
            "Useful for removing cysteines (disulfide risk) or charged residues for specific formulations."
        ),
    )
    refolding_rmsd_threshold: Optional[float] = Field(
        default=None,
        ge=0.0,
        description=(
            "Maximum Cα RMSD (Å) between the designed backbone and its refolded structure, "
            "used as a self-consistency filter in the 'folding' step. "
            "Designs where the folded structure deviates beyond this threshold are discarded. "
            "Lower values enforce stricter self-consistency. If omitted, no RMSD filter is applied."
        ),
    )
    alpha: Optional[float] = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description=(
            "Diversity weight for the final selection in the 'filtering' step (0.0–1.0). "
            "0.0 = pure quality ranking (top-scoring designs regardless of similarity). "
            "1.0 = pure diversity selection (maximise sequence/structure spread). "
            "Intermediate values blend quality and diversity. "
            "If omitted, boltzgen uses its default balance."
        ),
    )
    filter_biased: Optional[bool] = Field(
        default=None,
        description=(
            "Whether to remove designs with biased amino-acid compositions during filtering. "
            "When True, designs that are statistical outliers in their residue frequencies "
            "(e.g. unusually hydrophobic or charged) are discarded before the final selection."
        ),
    )
    additional_filters: Optional[list[str]] = Field(
        default=None,
        description=(
            "Hard filters applied to the scored designs before final selection. "
            "Each entry is an expression of the form 'metric>threshold' or 'metric<threshold' "
            "(e.g. ['plddt>70', 'ptm>0.5']). Designs that fail any filter are excluded. "
            "Available metrics depend on which analysis steps have run."
        ),
    )
    metrics_override: Optional[dict[str, Union[float, str]]] = Field(
        default=None,
        description=(
            "Override the per-metric importance weights used during ranking. "
            "Keys are metric names (e.g. 'plddt', 'ptm', 'affinity') and values are floats "
            "representing inverse importance (higher = less important in ranking). "
            "Use this to up-weight or down-weight specific metrics relative to the protocol default."
        ),
    )

    @field_validator("additional_filters", mode="after")
    @classmethod
    def _check_additional_filters(cls, v: Optional[list[str]]) -> Optional[list[str]]:
        if v is None:
            return v
        normalized = []
        for entry in v:
            stripped = entry.replace(" ", "")
            if not _FILTER_RE.match(stripped):
                raise ValueError(
                    f"Invalid additional_filters entry: {entry!r}. "
                    "Expected format: 'metric<op>threshold' where <op> is "
                    ">, <, >=, or <= (e.g. 'plddt>70', 'ptm>=0.5', 'affinity>-5.0')."
                )
            normalized.append(stripped)
        return normalized


class BoltzGenDesignRequestItem(RequestModel):
    """Defines a single design target: the set of chains and constraints that describe the system to design."""

    entities: list[BoltzGenEntity] = Field(
        min_length=1,
        description=(
            "List of entities (protein, ligand, file, DNA, RNA) that make up the design system. "
            "At least one entity is required. Typically this includes one designable chain and one "
            "or more fixed target chains, but the exact composition depends on the protocol."
        ),
    )
    constraints: Optional[list[BoltzGenConstraint]] = Field(
        default=None,
        description=(
            "Structural constraints enforced during diffusion sampling. "
            "Use bond, contact, or pocket constraints to bias the design toward specific geometries. "
            "If omitted, no structural constraints are applied beyond those implied by the protocol."
        ),
    )
    reset_res_index: Optional[list[BoltzGenChainSelector]] = Field(
        default=None,
        description=(
            "Reset residue numbering to start from 1 for the specified chains. "
            "This top-level field applies the reset globally across all entities. "
            "Can also be set per-entity inside a file entity. "
            "Commonly needed in scaffold redesign when input structures have non-sequential numbering."
        ),
    )


class BoltzGenDesignRequest(RequestModel):
    """Design request for BoltzGen."""

    items: Annotated[
        list[BoltzGenDesignRequestItem],
        Field(
            min_length=1,
            max_length=BoltzGenParams.batch_size,
            description="Batch of inputs to process in a single request. Up to 1 design system per request.",
        ),
    ]
    params: BoltzGenDesignParams = Field(
        default_factory=BoltzGenDesignParams,
        description="Optional parameters controlling this action (defaults are used when omitted).",
    )


### BoltzGen Response


class BoltzGenDesignResult(ResponseModel):
    """Result for a single design."""

    cif: str = Field(
        description=(
            "mmCIF format structure of the designed molecule. "
            "Contains the full atomic model produced by boltzgen for this design."
        )
    )
    metrics: Optional[dict[str, float]] = Field(
        default=None,
        description=(
            "Per-design quality metrics computed by the analysis step. "
            "Common keys include 'plddt' (predicted local distance difference test, 0–100), "
            "'ptm' (predicted TM-score, 0–1), and 'affinity' (predicted binding affinity). "
            "Present only when the 'analysis' step was included in the pipeline."
        ),
    )
    sequence: Optional[str] = Field(
        default=None,
        description=(
            "Amino-acid sequence of the designed chain(s) in one-letter code. "
            "Present only when the 'inverse_folding' step was included in the pipeline."
        ),
    )


class BoltzGenDesignResponse(ResponseModel):
    """Response for design requests."""

    results: list[BoltzGenDesignResult] = Field(
        description=(
            "List of individual design results. Each entry contains the CIF structure, "
            "quality metrics, and sequence for one design."
        )
    )
