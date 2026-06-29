"""Utility functions for SPURS model mutation handling."""

import io


def extract_sequence_from_structure(
    structure: str,
    structure_format: str,
    chain_id: str,
) -> str:
    """
    Extract the amino acid sequence from a PDB or CIF structure.

    Args:
        structure: Structure content as string
        structure_format: Format type ('pdb' or 'cif')
        chain_id: Chain identifier to extract

    Returns:
        Extracted sequence as string

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

    residue_names = ca_atoms.res_name

    # Convert 3-letter codes to 1-letter codes
    return "".join([_three_to_one(res_name) for res_name in residue_names])


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
    Extract sequence from a structure for schema validation.

    Args:
        structure_text: PDB or CIF content as string
        structure_format: Format type ('pdb' or 'cif')
        chain_id: Chain identifier

    Returns:
        Extracted sequence as string

    Raises:
        ValueError: If structure cannot be parsed or chain not found
    """
    return extract_sequence_from_structure(structure_text, structure_format, chain_id)


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
