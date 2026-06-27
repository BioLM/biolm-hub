from typing import Annotated, Any, Optional, Union

from pydantic import BeforeValidator, Field, field_validator, model_validator

from models.commons.data.structure_validator import validate_cif, validate_pdb
from models.commons.model.base import ModelParams
from models.commons.model.pydantic import (
    EnhancedStringEnum,
    RequestModel,
    ResponseModel,
)

### ProDy Params


class ProDyParams(ModelParams):
    params_version = "v1"
    display_name = "ProDy"
    base_model_slug = "prody"
    log_identifier = "PRODY"
    batch_size = 8
    max_sequence_len = 10000  # Large structures


### ProDy Encode (InSty) Request


class HydrogenMethod(EnhancedStringEnum):
    """Method for adding missing hydrogen atoms."""

    OPENBABEL = "openbabel"
    PDBFIXER = "pdbfixer"


class AlignmentMethod(EnhancedStringEnum):
    """Method for aligning structures for RMSD calculation."""

    SEQUENCE = "sequence"
    STRUCTURAL = "structural"


class ProDyEncodeRequestParams(RequestModel):
    """Parameters for ProDy InSty analysis."""

    add_hydrogens: bool = Field(
        default=False,
        description="Whether to add missing hydrogen atoms to the structure",
    )
    hydrogen_method: Optional[HydrogenMethod] = Field(
        default=HydrogenMethod.PDBFIXER,
        description="Method to use for adding hydrogens (openbabel or pdbfixer)",
    )
    compute_all_interactions: bool = Field(
        default=True,
        description="Whether to compute all types of interactions",
    )
    return_interaction_matrix: bool = Field(
        default=False,
        description="Whether to return the interaction matrix",
    )
    return_energy_matrix: bool = Field(
        default=False,
        description="Whether to return the interaction energy matrix",
    )
    return_frequent_interactors: bool = Field(
        default=False,
        description="Whether to return frequent interactors",
    )
    frequent_interactors_min_contacts: int = Field(
        default=1,
        ge=1,
        description="Minimum number of contacts for frequent interactors",
    )


class ProDyEncodeRequestItem(RequestModel):
    """Input structure for ProDy InSty analysis."""

    pdb: Optional[
        Annotated[
            str,
            BeforeValidator(validate_pdb),
            Field(default=None, min_length=1, description="PDB structure as string"),
        ]
    ] = None
    cif: Optional[
        Annotated[
            str,
            BeforeValidator(validate_cif),
            Field(default=None, min_length=1, description="CIF structure as string"),
        ]
    ] = None
    chain_ids: Optional[list[str]] = Field(
        default=None,
        description="List of chain IDs to analyze. If None, all chains are analyzed.",
    )
    chain_pairs: Optional[list[tuple[str, str]]] = Field(
        default=None,
        description="List of chain pairs (tuple of two chain IDs) to analyze interactions between. "
        "If None, all chain pairs are analyzed. Format: [['A', 'B'], ['A', 'C']]",
    )

    @model_validator(mode="before")
    @classmethod
    def convert_chain_pairs_to_tuples(cls, data: Any) -> Any:
        """Convert chain_pairs from lists to tuples if needed (JSON deserialization issue)."""
        if (
            isinstance(data, dict)
            and "chain_pairs" in data
            and data["chain_pairs"] is not None
        ):
            # Convert each pair from list to tuple
            data["chain_pairs"] = [
                tuple(pair) if isinstance(pair, list) else pair
                for pair in data["chain_pairs"]
            ]
        return data

    @field_validator("chain_pairs")
    @classmethod
    def validate_chain_pairs(cls, v):
        """Validate chain pairs format."""
        if v is None:
            return v
        for pair in v:
            if not isinstance(pair, list | tuple) or len(pair) != 2:
                raise ValueError(
                    f"Chain pair must be a list/tuple of 2 chain IDs, got: {pair}"
                )
            if not all(isinstance(chain_id, str) for chain_id in pair):
                raise ValueError(f"Chain IDs in pair must be strings, got: {pair}")
        return v

    @model_validator(mode="after")
    def validate_structure_provided(self):
        """Validate that either PDB or CIF is provided."""
        if self.pdb is None and self.cif is None:
            raise ValueError("Either 'pdb' or 'cif' must be provided")
        if self.pdb is not None and self.cif is not None:
            raise ValueError("Only one of 'pdb' or 'cif' should be provided")
        return self

    @model_validator(mode="after")
    def validate_chain_selection(self):
        """Validate that chain_ids and chain_pairs are consistent."""
        if self.chain_ids is not None and self.chain_pairs is not None:
            # Check that all chains in chain_pairs are in chain_ids
            chain_set = set(self.chain_ids)
            for pair in self.chain_pairs:
                if pair[0] not in chain_set or pair[1] not in chain_set:
                    raise ValueError(
                        f"Chain pair {pair} contains chains not in chain_ids {self.chain_ids}"
                    )
        return self

    @model_validator(mode="after")
    def validate_chains_are_protein(self):  # noqa: C901
        """Validate that all specified chains are protein chains."""
        try:
            import tempfile
            from pathlib import Path

            from prody import parseMMCIF, parsePDB
        except ImportError:
            # If ProDy is not available during validation, skip chain validation
            # It will be caught later during processing
            return self

        # Get structure string and format
        structure_str = self.pdb if self.pdb is not None else self.cif
        structure_format = "PDB" if self.pdb is not None else "CIF"

        # Parse structure to check chain types
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            structure_file = (
                tmp_path / f"structure.{'cif' if structure_format == 'CIF' else 'pdb'}"
            )

            with open(structure_file, "w") as f:
                f.write(structure_str)

            # Parse structure
            if structure_format == "CIF":
                structure = parseMMCIF(str(structure_file))
            else:
                structure = parsePDB(str(structure_file))

            if structure is None:
                # Can't parse, skip validation (will be caught later)
                return self

            # Get all chains to check
            chains_to_check = set()
            if self.chain_ids is not None:
                chains_to_check.update(self.chain_ids)
            if self.chain_pairs is not None:
                for pair in self.chain_pairs:
                    chains_to_check.add(pair[0])
                    chains_to_check.add(pair[1])

            # If no chains specified, check all chains - sort for determinism
            if not chains_to_check:
                available_chains = sorted(set(structure.getChids()))
                chains_to_check = set(available_chains)

            # Check each chain
            for chain_id in chains_to_check:
                chain_sel = structure.select(f"chain {chain_id}")
                if chain_sel is None or chain_sel.numAtoms() == 0:
                    raise ValueError(f"Chain {chain_id} not found in structure")

                # Check if it's a protein chain
                protein_sel = chain_sel.select("protein")
                if protein_sel is None or protein_sel.numAtoms() == 0:
                    # Not a protein chain, determine what it is
                    molecule_type = self._determine_molecule_type(chain_sel)
                    raise ValueError(
                        f"Chain {chain_id} is not a protein chain. "
                        f"It appears to be a {molecule_type}."
                    )

        return self

    @staticmethod
    def _determine_molecule_type(chain_selection):
        """Determine the type of molecule in a chain selection."""
        # Get residue names
        residues = chain_selection.getResnames()
        if len(residues) == 0:
            return "empty chain"

        unique_residues = set(residues)

        # Check for nucleotides
        nucleotide_names = {"A", "T", "G", "C", "U", "DA", "DT", "DG", "DC", "DU"}
        rna_names = {"A", "G", "C", "U"}
        dna_names = {"DA", "DT", "DG", "DC"}

        if unique_residues & rna_names:
            return "RNA"
        if unique_residues & dna_names:
            return "DNA"
        if unique_residues & nucleotide_names:
            return "nucleic acid"

        # Check for standard amino acids
        amino_acids = {
            "ALA",
            "ARG",
            "ASN",
            "ASP",
            "CYS",
            "GLN",
            "GLU",
            "GLY",
            "HIS",
            "ILE",
            "LEU",
            "LYS",
            "MET",
            "PHE",
            "PRO",
            "SER",
            "THR",
            "TRP",
            "TYR",
            "VAL",
        }
        if any(res in amino_acids for res in unique_residues):
            return "protein"  # Shouldn't reach here if validation worked

        # Check for ions (single atom or very small)
        if len(unique_residues) == 1 and chain_selection.numAtoms() <= 2:
            resname = list(unique_residues)[0]
            # Common ion names
            if resname in {"MG", "CA", "ZN", "FE", "NA", "K", "CL", "SO4", "PO4"}:
                return f"ion ({resname})"
            return f"ion or small molecule ({resname})"

        # Likely a ligand or small molecule
        if len(unique_residues) < 10:
            return f"ligand or small molecule (residues: {', '.join(list(unique_residues)[:5])})"

        return "unknown molecule type"


class ProDyEncodeRequest(RequestModel):
    params: ProDyEncodeRequestParams = ProDyEncodeRequestParams()
    items: Annotated[
        list[ProDyEncodeRequestItem],
        Field(min_length=1, max_length=ProDyParams.batch_size),
    ]


### ProDy Predict (RMSD) Request


class ProDyPredictRequestParams(RequestModel):
    """Parameters for ProDy RMSD calculation."""

    alignment_method: AlignmentMethod = Field(
        default=AlignmentMethod.STRUCTURAL,
        description="Method for aligning structures: 'sequence' or 'structural' (default: structural)",
    )


class ProDyPredictRequestItem(RequestModel):
    """Input structures for RMSD calculation."""

    pdb_a: Optional[
        Annotated[
            str,
            BeforeValidator(validate_pdb),
            Field(
                default=None, min_length=1, description="First PDB structure as string"
            ),
        ]
    ] = None
    cif_a: Optional[
        Annotated[
            str,
            BeforeValidator(validate_cif),
            Field(
                default=None, min_length=1, description="First CIF structure as string"
            ),
        ]
    ] = None
    chain_a: Union[str, list[str]] = Field(
        ...,
        description="Chain ID(s) to use from first structure. Can be a single chain ID or a list of chain IDs.",
    )
    pdb_b: Optional[
        Annotated[
            str,
            BeforeValidator(validate_pdb),
            Field(
                default=None, min_length=1, description="Second PDB structure as string"
            ),
        ]
    ] = None
    cif_b: Optional[
        Annotated[
            str,
            BeforeValidator(validate_cif),
            Field(
                default=None, min_length=1, description="Second CIF structure as string"
            ),
        ]
    ] = None
    chain_b: Union[str, list[str]] = Field(
        ...,
        description="Chain ID(s) to use from second structure. Can be a single chain ID or a list of chain IDs.",
    )

    @model_validator(mode="after")
    def validate_structure_a_provided(self):
        """Validate that either PDB or CIF is provided for structure A."""
        if self.pdb_a is None and self.cif_a is None:
            raise ValueError("Either 'pdb_a' or 'cif_a' must be provided")
        if self.pdb_a is not None and self.cif_a is not None:
            raise ValueError("Only one of 'pdb_a' or 'cif_a' should be provided")
        return self

    @model_validator(mode="after")
    def validate_structure_b_provided(self):
        """Validate that either PDB or CIF is provided for structure B."""
        if self.pdb_b is None and self.cif_b is None:
            raise ValueError("Either 'pdb_b' or 'cif_b' must be provided")
        if self.pdb_b is not None and self.cif_b is not None:
            raise ValueError("Only one of 'pdb_b' or 'cif_b' should be provided")
        return self

    @model_validator(mode="after")
    def validate_chains_exist(self):  # noqa: C901
        """Validate that the specified chains exist and are protein chains."""
        import tempfile
        from pathlib import Path

        try:
            import prody  # noqa: F401
        except ImportError:
            # If ProDy is not available during validation, skip chain validation
            # It will be caught later during processing
            return self

        # Normalize chain_a and chain_b to lists
        chains_a = [self.chain_a] if isinstance(self.chain_a, str) else self.chain_a
        chains_b = [self.chain_b] if isinstance(self.chain_b, str) else self.chain_b

        # Validate chains_a in structure_a
        structure_a_str = self.pdb_a if self.pdb_a is not None else self.cif_a
        format_a = "PDB" if self.pdb_a is not None else "CIF"

        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            file_a = tmp_path / f"structure_a.{'cif' if format_a == 'CIF' else 'pdb'}"
            with open(file_a, "w") as f:
                f.write(structure_a_str)

            try:
                from prody import parseMMCIF, parsePDB

                if format_a == "CIF":
                    structure_a = parseMMCIF(str(file_a))
                else:
                    structure_a = parsePDB(str(file_a))

                if structure_a is None:
                    raise ValueError(f"Failed to parse structure_a as {format_a}")

                available_chains_a = set(structure_a.getChids())
                for chain_id in chains_a:
                    chain_sel = structure_a.select(f"chain {chain_id}")
                    if chain_sel is None or chain_sel.numAtoms() == 0:
                        raise ValueError(
                            f"Chain '{chain_id}' not found in structure_a. "
                            f"Available chains: {sorted(available_chains_a) if available_chains_a else 'none'}"
                        )

                    # Check if it's a protein chain
                    protein_sel = chain_sel.select("protein")
                    if protein_sel is None or protein_sel.numAtoms() == 0:
                        molecule_type = ProDyEncodeRequestItem._determine_molecule_type(
                            chain_sel
                        )
                        raise ValueError(
                            f"Chain '{chain_id}' in structure_a is not a protein chain. "
                            f"It appears to be a {molecule_type}."
                        )
            except Exception as e:
                if (
                    "not found" in str(e)
                    or "Chain" in str(e)
                    or "not a protein" in str(e)
                ):
                    raise
                # If parsing fails for other reasons, skip validation
                # It will be caught during actual processing
                pass

        # Validate chains_b in structure_b
        structure_b_str = self.pdb_b if self.pdb_b is not None else self.cif_b
        format_b = "PDB" if self.pdb_b is not None else "CIF"

        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            file_b = tmp_path / f"structure_b.{'cif' if format_b == 'CIF' else 'pdb'}"
            with open(file_b, "w") as f:
                f.write(structure_b_str)

            try:
                from prody import parseMMCIF, parsePDB

                if format_b == "CIF":
                    structure_b = parseMMCIF(str(file_b))
                else:
                    structure_b = parsePDB(str(file_b))

                if structure_b is None:
                    raise ValueError(f"Failed to parse structure_b as {format_b}")

                available_chains_b = set(structure_b.getChids())
                for chain_id in chains_b:
                    chain_sel = structure_b.select(f"chain {chain_id}")
                    if chain_sel is None or chain_sel.numAtoms() == 0:
                        raise ValueError(
                            f"Chain '{chain_id}' not found in structure_b. "
                            f"Available chains: {sorted(available_chains_b) if available_chains_b else 'none'}"
                        )

                    # Check if it's a protein chain
                    protein_sel = chain_sel.select("protein")
                    if protein_sel is None or protein_sel.numAtoms() == 0:
                        molecule_type = ProDyEncodeRequestItem._determine_molecule_type(
                            chain_sel
                        )
                        raise ValueError(
                            f"Chain '{chain_id}' in structure_b is not a protein chain. "
                            f"It appears to be a {molecule_type}."
                        )
            except Exception as e:
                if (
                    "not found" in str(e)
                    or "Chain" in str(e)
                    or "not a protein" in str(e)
                ):
                    raise
                # If parsing fails for other reasons, skip validation
                # It will be caught during actual processing
                pass

        return self


class ProDyPredictRequest(RequestModel):
    params: ProDyPredictRequestParams = ProDyPredictRequestParams()
    items: Annotated[
        list[ProDyPredictRequestItem],
        Field(min_length=1, max_length=ProDyParams.batch_size),
    ]


### ProDy Encode (InSty) Response


class InteractionType(EnhancedStringEnum):
    """Types of interactions computed by ProDy InSty."""

    HYDROGEN_BOND = "hydrogen_bond"
    SALT_BRIDGE = "salt_bridge"
    DISULFIDE_BOND = "disulfide_bond"
    HYDROPHOBIC = "hydrophobic"
    PI_STACKING = "pi_stacking"
    CATION_PI = "cation_pi"
    VAN_DER_WAALS = "van_der_waals"
    IONIC = "ionic"
    COVALENT = "covalent"


class Interaction(ResponseModel):
    """A single interaction between two residues/atoms."""

    interaction_type: str = Field(..., description="Type of interaction")
    chain1: str = Field(..., description="Chain ID of first residue")
    residue1: str = Field(..., description="Residue identifier (e.g., 'ALA 1')")
    atom1: Optional[str] = Field(default=None, description="Atom name in first residue")
    chain2: str = Field(..., description="Chain ID of second residue")
    residue2: str = Field(..., description="Residue identifier (e.g., 'GLY 2')")
    atom2: Optional[str] = Field(
        default=None, description="Atom name in second residue"
    )
    distance: Optional[float] = Field(default=None, description="Distance in Angstroms")
    energy: Optional[float] = Field(
        default=None, description="Interaction energy in kcal/mol"
    )


class ChainInteractionSummary(ResponseModel):
    """Summary of interactions for a chain or chain pair."""

    chain_id: Optional[str] = Field(
        default=None, description="Chain ID (for intra-chain interactions)"
    )
    chain_pair: Optional[tuple[str, str]] = Field(
        default=None, description="Chain pair (for inter-chain interactions)"
    )
    interaction_counts: dict[str, int] = Field(
        ..., description="Count of each interaction type"
    )
    total_interactions: int = Field(..., description="Total number of interactions")
    interactions: list[Interaction] = Field(
        default_factory=list, description="List of all interactions"
    )


class FrequentInteractor(ResponseModel):
    """A frequent interactor residue."""

    residue: str = Field(..., description="Residue identifier (e.g., 'ARG215A')")
    interactors: list[str] = Field(
        ..., description="List of interacting residues with interaction types"
    )
    contact_count: int = Field(..., description="Number of contacts")


class ChainPairInteractions(ResponseModel):
    """Interactions for a specific chain pair."""

    chain_pair: tuple[str, str] = Field(
        ..., description="Chain pair (e.g., ('A', 'B'))"
    )
    interactions: list[Interaction] = Field(
        ..., description="Interactions between the two chains"
    )
    interaction_counts: dict[str, int] = Field(
        ..., description="Count of each interaction type for this pair"
    )
    total_interactions: int = Field(
        ..., description="Total number of interactions for this pair"
    )


class ProDyEncodeResponseResult(ResponseModel):
    """Result of ProDy InSty analysis for a single structure."""

    structure_format: str = Field(
        ..., description="Format of input structure (PDB or CIF)"
    )
    chains_analyzed: list[str] = Field(
        ..., description="List of chain IDs that were analyzed"
    )
    chain_pairs_analyzed: Optional[list[tuple[str, str]]] = Field(
        default=None,
        description="List of chain pairs that were analyzed for inter-chain interactions",
    )
    intra_chain_interactions: dict[str, ChainInteractionSummary] = Field(
        default_factory=dict,
        description="Intra-chain interactions keyed by chain ID (e.g., {'A': {...}, 'B': {...}})",
    )
    pair_interactions: dict[str, ChainPairInteractions] = Field(
        default_factory=dict,
        description="Inter-chain interactions keyed by chain pair (e.g., {'A-B': {...}})",
    )
    hydrogens_added: bool = Field(
        default=False,
        description="Whether hydrogen atoms were added to the structure",
    )
    interaction_matrix: Optional[list[list[float]]] = Field(
        default=None,
        description="Interaction matrix (2D array) if requested",
    )
    energy_matrix: Optional[list[list[float]]] = Field(
        default=None,
        description="Interaction energy matrix (2D array) if requested",
    )
    frequent_interactors: Optional[list[FrequentInteractor]] = Field(
        default=None,
        description="Frequent interactors if requested",
    )


class ProDyEncodeResponse(ResponseModel):
    results: list[ProDyEncodeResponseResult]


### ProDy Predict (RMSD) Response


class ProDyPredictResponseResult(ResponseModel):
    """Result of RMSD calculation between two structures."""

    rmsd: float = Field(..., description="Root mean square deviation in Angstroms")
    alignment_method: str = Field(..., description="Alignment method used")
    chain_a: Union[str, list[str]] = Field(
        ..., description="Chain ID(s) from first structure"
    )
    chain_b: Union[str, list[str]] = Field(
        ..., description="Chain ID(s) from second structure"
    )
    matched_residues: Optional[int] = Field(
        default=None,
        description="Number of matched residues after alignment (for sequence alignment)",
    )


class ProDyPredictResponse(ResponseModel):
    results: list[ProDyPredictResponseResult]
