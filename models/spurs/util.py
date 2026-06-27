"""Utility functions for SPURS model mutation handling."""

import io

from models.commons.core.logging import get_logger

logger = get_logger(__name__)


def extract_sequence_from_structure(
    structure: str,
    structure_format: str,
    chain_id: str,
) -> tuple[str, dict[int, int]]:
    """
    Extract the amino acid sequence from a PDB or CIF structure.

    Args:
        structure: Structure content as string
        structure_format: Format type ('pdb' or 'cif')
        chain_id: Chain identifier to extract

    Returns:
        Tuple of (sequence_string, residue_mapping) where residue_mapping maps
        PDB residue numbers to 0-indexed sequence positions

    Raises:
        ValueError: If structure format is unsupported or chain not found
    """
    from biotite.structure.io import pdb as biotite_pdb
    from biotite.structure.io.pdbx import get_structure as pdbx_get_structure

    try:
        from biotite.structure.io.pdbx import PDBxFile as CIFLikeFile
    except ImportError:
        from biotite.structure.io.pdbx import CIFFile as CIFLikeFile

    fmt = structure_format.lower()

    # Parse structure directly from string using StringIO
    if fmt == "cif":
        string_io = io.StringIO(structure)
        pdbx_file = CIFLikeFile.read(string_io)
        pdbx_block = pdbx_get_structure(
            pdbx_file,
            model=1,
            extra_fields=["atom_id", "b_factor", "occupancy"],
        )
        structure_obj = pdbx_block[pdbx_block.chain_id == chain_id]

    elif fmt == "pdb":
        string_io = io.StringIO(structure)
        pdb_file = biotite_pdb.PDBFile.read(string_io)
        structure_obj = biotite_pdb.get_structure(
            pdb_file,
            model=1,
            extra_fields=["atom_id", "b_factor", "occupancy"],
        )
        structure_obj = structure_obj[structure_obj.chain_id == chain_id]
    else:
        raise ValueError(f"Unsupported structure format '{structure_format}'")

    if len(structure_obj) == 0:
        raise ValueError(f"Chain '{chain_id}' not found in structure")

    # Filter to CA atoms only to get residue sequence
    ca_atoms = structure_obj[structure_obj.atom_name == "CA"]

    if len(ca_atoms) == 0:
        raise ValueError(f"No CA atoms found for chain '{chain_id}'")

    # Get sequence and residue numbering mapping
    residue_ids = ca_atoms.res_id
    residue_names = ca_atoms.res_name

    # Convert 3-letter codes to 1-letter codes
    sequence = "".join([_three_to_one(res_name) for res_name in residue_names])

    # Create mapping from PDB residue number to 0-indexed position
    residue_mapping = {res_id: idx for idx, res_id in enumerate(residue_ids)}

    return sequence, residue_mapping


def _three_to_one(three_letter_code: str) -> str:
    """Convert three-letter amino acid code to one-letter code."""
    conversion_dict = {
        "ALA": "A",
        "CYS": "C",
        "ASP": "D",
        "GLU": "E",
        "PHE": "F",
        "GLY": "G",
        "HIS": "H",
        "ILE": "I",
        "LYS": "K",
        "LEU": "L",
        "MET": "M",
        "ASN": "N",
        "PRO": "P",
        "GLN": "Q",
        "ARG": "R",
        "SER": "S",
        "THR": "T",
        "VAL": "V",
        "TRP": "W",
        "TYR": "Y",
    }
    code = three_letter_code.upper()
    if code not in conversion_dict:
        raise ValueError(f"Unknown amino acid code: {three_letter_code}")
    return conversion_dict[code]


def extract_sequence_for_validation(
    structure_text: str, structure_format: str, chain_id: str
) -> str:
    """
    Lightweight wrapper for schema validation - returns sequence only.

    This function is designed for use in Pydantic schema validation where
    only the sequence is needed (not the residue mapping).

    Args:
        structure_text: PDB or CIF content as string
        structure_format: Format type ('pdb' or 'cif')
        chain_id: Chain identifier

    Returns:
        Extracted sequence as string

    Raises:
        ValueError: If structure cannot be parsed or chain not found
    """
    sequence, _ = extract_sequence_from_structure(
        structure_text, structure_format, chain_id
    )
    return sequence


def calculate_mutations(parent_sequence: str, mutant_sequence: str) -> list[str]:
    """
    Calculate mutations between parent and mutant sequences.

    Args:
        parent_sequence: Original amino acid sequence
        mutant_sequence: Mutated amino acid sequence

    Returns:
        List of mutation strings in format '<WT><position><MT>' (1-indexed positions)

    Raises:
        ValueError: If sequences have different lengths
    """
    if len(parent_sequence) != len(mutant_sequence):
        raise ValueError(
            f"Sequence length mismatch: parent has {len(parent_sequence)} residues, "
            f"mutant has {len(mutant_sequence)} residues. Sequences must be the same length."
        )

    mutations = []
    for i, (parent_aa, mutant_aa) in enumerate(
        zip(parent_sequence, mutant_sequence, strict=True)
    ):
        if parent_aa != mutant_aa:
            # Use 1-indexed position
            mutation = f"{parent_aa}{i + 1}{mutant_aa}"
            mutations.append(mutation)

    return mutations


def validate_sequence_compatibility(
    structure_sequence: str,
    input_sequence: str,
    residue_mapping: dict[int, int],
) -> None:
    """
    Validate that structure sequence and input sequence are compatible.

    This checks length compatibility and provides helpful error messages
    for common issues like residue numbering mismatches.

    Args:
        structure_sequence: Sequence extracted from structure
        input_sequence: User-provided input sequence
        residue_mapping: Mapping from PDB residue numbers to sequence positions

    Raises:
        ValueError: If sequences are incompatible
    """
    if len(structure_sequence) != len(input_sequence):
        raise ValueError(
            f"Sequence length mismatch: structure has {len(structure_sequence)} "
            f"residues, input sequence has {len(input_sequence)} residues. "
            f"When return_full_dms=False, the input sequence must match the "
            f"structure sequence length to calculate mutations."
        )

    # Check if there are gaps in residue numbering
    if residue_mapping:
        res_ids = sorted(residue_mapping.keys())
        expected_range = res_ids[-1] - res_ids[0] + 1
        if len(res_ids) != expected_range:
            logger.warning(
                "Structure has non-contiguous residue numbering "
                "(found %s residues across range %s-%s). "
                "This may indicate missing residues in the structure.",
                len(res_ids),
                res_ids[0],
                res_ids[-1],
            )
