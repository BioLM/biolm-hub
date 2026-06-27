"""
Utility functions for Boltz model processing.

This module contains helper functions for handling YAML construction,
A3M file processing, and constraint management for Boltz predictions.
"""

import tempfile
from typing import Any

import numpy as np

from models.boltz.schema import BoltzEntity, BoltzEntityType, BoltzPredictConstraints
from models.commons.data.a3m import combine_a3ms


def _sanitize_molecule_id(mol_id: str) -> str:
    """Convert problematic IDs to safe 4-char alphabetic IDs for Boltz compatibility."""
    import hashlib

    if mol_id.isalpha() and len(mol_id) <= 4:
        return mol_id

    # Generate 4-letter hash ID (Boltz truncates longer IDs and parses special patterns)
    hash_val = hashlib.md5(mol_id.encode()).hexdigest()[:3]
    sanitized = "X" + "".join(chr(ord("a") + int(c, 16) % 26) for c in hash_val)
    print(f"[Boltz] Sanitized molecule ID '{mol_id}' -> '{sanitized}'")
    return sanitized


def construct_yaml_data(  # noqa: C901
    molecules: list[BoltzEntity],
    constraints: list[BoltzPredictConstraints] = None,
    templates: list = None,
    affinity: dict = None,
    temp_files: list = None,
) -> dict[str, Any]:
    """
    Construct YAML data structure from molecules, constraints, templates, and affinity.

    This function builds the complete YAML configuration needed for Boltz predictions
    by processing all input entities and their associated data.

    Args:
        molecules: List of molecular entities to include in the prediction
        constraints: Optional list of structural constraints to apply
        templates: Optional list of template structures to use
        affinity: Optional affinity property configuration
        temp_files: Optional list to track temporary files created during processing

    Returns:
        Dictionary containing the YAML data structure for Boltz input
    """
    yaml_data = {"sequences": []}

    # Build ID mapping for sanitization
    id_mapping: dict[str, str] = {}
    for seq in molecules:
        if isinstance(seq.id, str):
            id_mapping[seq.id] = _sanitize_molecule_id(seq.id)
        elif isinstance(seq.id, list):
            for id_part in seq.id:
                id_mapping[id_part] = _sanitize_molecule_id(id_part)

    for seq in molecules:
        entity_data = _get_entity_data(seq, temp_files)
        _add_entity_to_yaml(yaml_data, seq, entity_data, id_mapping)

    if constraints:
        yaml_data["constraints"] = _get_constraints_data(constraints, id_mapping)

    # Add templates if provided - write CIF content to temporary files
    if templates:
        template_entries = []
        for _idx, template in enumerate(templates):
            template_data = template.model_dump(exclude_none=True)

            # Write CIF content to temporary file
            with tempfile.NamedTemporaryFile(delete=False, suffix=".cif") as cif_file:
                cif_file.write(template_data["cif"].encode("utf-8"))
                template_data["cif"] = cif_file.name

            template_entries.append(template_data)
            if temp_files is not None:
                temp_files.append(cif_file.name)

        yaml_data["templates"] = template_entries

    if affinity:
        if hasattr(affinity, "model_dump"):
            affinity_dict = affinity.model_dump()
        else:
            affinity_dict = dict(affinity) if isinstance(affinity, dict) else affinity
        if "binder" in affinity_dict and affinity_dict["binder"] in id_mapping:
            affinity_dict["binder"] = id_mapping[affinity_dict["binder"]]
        yaml_data["properties"] = [{"affinity": affinity_dict}]

    return yaml_data


def _get_entity_data(seq: BoltzEntity, temp_files: list = None) -> dict[str, Any]:
    """
    Extract entity data from a BoltzEntity for YAML construction.

    This function processes a molecular entity and extracts all relevant
    information needed for Boltz prediction, including sequences, alignments,
    modifications, and structural properties.

    Args:
        seq: The molecular entity to process
        temp_files: Optional list to track temporary files created

    Returns:
        Dictionary containing the processed entity data
    """
    entity_data = {}

    # Add basic sequence information
    if seq.sequence is not None:
        entity_data["sequence"] = seq.sequence
    if seq.smiles is not None:
        entity_data["smiles"] = seq.smiles
    if seq.ccd is not None:
        entity_data["ccd"] = seq.ccd

    # Handle multiple sequence alignments (MSAs)
    if seq.alignment is not None and isinstance(seq.alignment, dict):
        if len(seq.alignment) > 1:
            print(
                f"[Boltz] Merging {len(seq.alignment)} A3Ms for molecule id={seq.id}: "
                f"{list(seq.alignment.keys())}"
            )
        else:
            print(
                f"[Boltz] Using single A3M for molecule id={seq.id}: "
                f"{list(seq.alignment.keys())}"
            )

        # Combine all A3M strings in the dict into one temporary file
        with tempfile.NamedTemporaryFile(delete=False, suffix=".a3m") as msa_file:
            combine_a3ms(list(seq.alignment.values()), msa_file.name)
            entity_data["msa"] = msa_file.name
            if temp_files is not None:
                temp_files.append(msa_file.name)

    # Handle protein sequences without alignments
    elif seq.sequence is not None and seq.type == BoltzEntityType.PROTEIN:
        entity_data["msa"] = "empty"

    # Add post-translational modifications
    if seq.modifications:
        entity_data["modifications"] = [
            {"position": m.position, "ccd": m.ccd} for m in seq.modifications
        ]

    # Add cyclic property
    if seq.cyclic:
        entity_data["cyclic"] = True

    return entity_data


def _add_entity_to_yaml(
    yaml_data: dict[str, Any],
    seq: BoltzEntity,
    entity_data: dict[str, Any],
    id_mapping: dict[str, str],
) -> None:
    """Add a processed entity to the YAML data structure."""
    if isinstance(seq.id, str):
        sanitized_id = id_mapping.get(seq.id, seq.id)
    elif isinstance(seq.id, list):
        sanitized_id = [id_mapping.get(id_part, id_part) for id_part in seq.id]
    else:
        sanitized_id = seq.id
    yaml_data["sequences"].append({seq.type.value: {"id": sanitized_id, **entity_data}})


def _get_constraints_data(
    constraints: list[BoltzPredictConstraints],
    id_mapping: dict[str, str],
) -> list[dict[str, Any]]:
    """Process structural constraints for YAML inclusion with sanitized IDs."""
    constraints_data = []
    for constraint in constraints:
        if constraint.bond:
            constraints_data.append(
                {
                    "bond": {
                        "atom1": constraint.bond.atom1,
                        "atom2": constraint.bond.atom2,
                    }
                }
            )
        if constraint.pocket:
            constraints_data.append(
                {
                    "pocket": {
                        "binder": id_mapping.get(
                            constraint.pocket.binder, constraint.pocket.binder
                        ),
                        "contacts": [
                            [id_mapping.get(chain_id, chain_id), residue]
                            for chain_id, residue in constraint.pocket.contacts
                        ],
                    }
                }
            )
    return constraints_data


def ptm_func(x: np.ndarray, d0: float) -> np.ndarray:
    """
    PTM function: 1.0/(1+(x/d0)**2.0)

    Args:
        x: PAE values
        d0: d0 parameter

    Returns:
        PTM-transformed values
    """
    return 1.0 / (1 + (x / d0) ** 2.0)


def calc_d0(L: float, pair_type: str = "protein") -> float:
    """
    Calculate d0 parameter based on chain length.
    From Yang and Skolnick, PROTEINS: Structure, Function, and Bioinformatics 57:702–710 (2004)

    Args:
        L: Chain length (number of residues)
        pair_type: 'protein' or 'nucleic_acid'

    Returns:
        d0 value
    """
    L = float(L)
    if L < 27:
        L = 27
    min_value = 1.0
    if pair_type == "nucleic_acid":
        min_value = 2.0
    d0 = 1.24 * (L - 15) ** (1.0 / 3.0) - 1.8
    return max(min_value, d0)


def calc_d0_array(L: np.ndarray, pair_type: str = "protein") -> np.ndarray:
    """
    Vectorized d0 calculation for arrays.

    Args:
        L: Array of chain lengths
        pair_type: 'protein' or 'nucleic_acid'

    Returns:
        Array of d0 values
    """
    L = np.array(L, dtype=float)
    L = np.maximum(27, L)
    min_value = 1.0
    if pair_type == "nucleic_acid":
        min_value = 2.0
    return np.maximum(min_value, 1.24 * (L - 15) ** (1.0 / 3.0) - 1.8)


def classify_chain_type(
    chain_ids: np.ndarray, residue_types: np.ndarray
) -> dict[str, str]:
    """
    Classify chains as protein or nucleic_acid.

    Args:
        chain_ids: Array of chain IDs
        residue_types: Array of residue type names

    Returns:
        Dictionary mapping chain ID to type ('protein' or 'nucleic_acid')
    """
    nuc_residue_set = {"DA", "DC", "DT", "DG", "A", "C", "U", "G"}
    chain_types = {}
    unique_chains = np.unique(chain_ids)

    for chain in unique_chains:
        indices = np.where(chain_ids == chain)[0]
        chain_residues = residue_types[indices]
        nuc_count = sum(residue in nuc_residue_set for residue in chain_residues)
        chain_types[chain] = "nucleic_acid" if nuc_count > 0 else "protein"

    return chain_types


def calculate_ipsae(  # noqa: C901
    pae_matrix: np.ndarray,
    chain_ids: list[str],
    residue_types: list[str],
    pae_cutoff: float = 10.0,
) -> dict[str, dict[str, dict[str, float]]]:
    """
    Calculate interface predicted aligned error (ipSAE) for all chain pairs.

    Based on Dunbrack 2025 "Res ipSAE loquunt" (PMC11844409), this calculates
    multiple variants of ipSAE:
    - ipSAE_d0chn: d0 based on total chain pair length
    - ipSAE_d0dom: d0 based on residues with good PAE values
    - ipSAE_d0res: d0 based on residues per residue (most detailed)

    Also calculates min, max, and avg aggregations.

    Reference: https://github.com/DunbrackLab/IPSAE

    Args:
        pae_matrix: PAE matrix of shape (n_residues, n_residues)
        chain_ids: List of chain IDs for each residue
        residue_types: List of residue type names
        pae_cutoff: PAE cutoff for filtering (default 10.0 for Boltz)

    Returns:
        Dictionary with structure:
        {
            chain1: {
                chain2: {
                    'ipsae_min': float,
                    'ipsae_max': float,
                    'ipsae_avg': float,
                    'ipsae_d0chn': float,
                    'ipsae_d0dom': float,
                    'ipsae_d0res': float,
                }
            }
        }
    """
    chain_ids_array = np.array(chain_ids)
    residue_types_array = np.array(residue_types)
    unique_chains = np.unique(chain_ids_array)
    num_residues = len(chain_ids)

    # Classify chain types
    chain_types = classify_chain_type(chain_ids_array, residue_types_array)

    # Determine chain pair types
    chain_pair_types = {}
    for chain1 in unique_chains:
        chain_pair_types[chain1] = {}
        for chain2 in unique_chains:
            if chain1 == chain2:
                continue
            if (
                chain_types[chain1] == "nucleic_acid"
                or chain_types[chain2] == "nucleic_acid"
            ):
                chain_pair_types[chain1][chain2] = "nucleic_acid"
            else:
                chain_pair_types[chain1][chain2] = "protein"

    # Initialize results
    results = {}

    for chain1 in unique_chains:
        results[chain1] = {}
        for chain2 in unique_chains:
            if chain1 == chain2:
                continue

            # Get residue indices for each chain
            idx1 = np.where(chain_ids_array == chain1)[0]
            idx2 = np.where(chain_ids_array == chain2)[0]

            if idx1.size == 0 or idx2.size == 0:
                results[chain1][chain2] = {
                    "ipsae_min": 0.0,
                    "ipsae_max": 0.0,
                    "ipsae_avg": 0.0,
                    "ipsae_d0chn": 0.0,
                    "ipsae_d0dom": 0.0,
                    "ipsae_d0res": 0.0,
                }
                continue

            pair_type = chain_pair_types[chain1][chain2]

            # Calculate n0chn and d0chn (based on total chain pair length)
            n0chn = len(idx1) + len(idx2)
            d0chn = calc_d0(n0chn, pair_type)

            # Calculate PTM matrix with d0chn
            ptm_matrix_d0chn = ptm_func(pae_matrix, d0chn)

            # Filter by PAE cutoff
            valid_pairs_matrix = (chain_ids_array == chain2) & (pae_matrix < pae_cutoff)

            # Calculate ipSAE_d0chn (by residue)
            ipsae_d0chn_byres = np.zeros(num_residues)
            for i in idx1:
                valid_pairs = valid_pairs_matrix[i]
                if valid_pairs.any():
                    ipsae_d0chn_byres[i] = ptm_matrix_d0chn[i, valid_pairs].mean()

            # Calculate n0dom and d0dom (based on residues with good PAE)
            unique_residues_chain1 = set()
            unique_residues_chain2 = set()
            for i in idx1:
                valid_pairs = valid_pairs_matrix[i]
                if valid_pairs.any():
                    unique_residues_chain1.add(i)
                    for j in np.where(valid_pairs)[0]:
                        unique_residues_chain2.add(j)

            n0dom = len(unique_residues_chain1) + len(unique_residues_chain2)
            d0dom = calc_d0(n0dom, pair_type) if n0dom > 0 else d0chn

            # Calculate ipSAE_d0dom
            ptm_matrix_d0dom = ptm_func(pae_matrix, d0dom)
            ipsae_d0dom_byres = np.zeros(num_residues)
            for i in idx1:
                valid_pairs = valid_pairs_matrix[i]
                if valid_pairs.any():
                    ipsae_d0dom_byres[i] = ptm_matrix_d0dom[i, valid_pairs].mean()

            # Calculate ipSAE_d0res (per-residue d0)
            n0res_byres = np.sum(valid_pairs_matrix, axis=1)
            d0res_byres = calc_d0_array(n0res_byres, pair_type)
            ipsae_d0res_byres = np.zeros(num_residues)
            for i in idx1:
                valid_pairs = valid_pairs_matrix[i]
                if valid_pairs.any():
                    ptm_row_d0res = ptm_func(pae_matrix[i], d0res_byres[i])
                    ipsae_d0res_byres[i] = ptm_row_d0res[valid_pairs].mean()

            # Aggregate metrics (focusing on ipSAE_d0res as the main metric)
            ipsae_d0res_values = ipsae_d0res_byres[idx1]
            valid_vals = ipsae_d0res_values[ipsae_d0res_values > 0.0]

            if valid_vals.size > 0:
                ipsae_min = float(np.min(valid_vals))
                ipsae_max = float(np.max(valid_vals))
                ipsae_avg = float(np.mean(valid_vals))
            else:
                ipsae_min = ipsae_max = ipsae_avg = 0.0

            # Get max values for d0chn and d0dom variants
            ipsae_d0chn_max = (
                float(np.max(ipsae_d0chn_byres[idx1]))
                if np.any(ipsae_d0chn_byres[idx1] > 0)
                else 0.0
            )
            ipsae_d0dom_max = (
                float(np.max(ipsae_d0dom_byres[idx1]))
                if np.any(ipsae_d0dom_byres[idx1] > 0)
                else 0.0
            )

            results[chain1][chain2] = {
                "ipsae_min": ipsae_min,
                "ipsae_max": ipsae_max,
                "ipsae_avg": ipsae_avg,
                "ipsae_d0chn": ipsae_d0chn_max,
                "ipsae_d0dom": ipsae_d0dom_max,
                "ipsae_d0res": ipsae_max,  # Use max as the main d0res value
            }

    return results


def calculate_ipae(
    pae_matrix: np.ndarray,
    chain_ids: list[str],
) -> dict[str, dict[str, float]]:
    """
    Calculate interface predicted aligned error (ipae) for all chain pairs.

    Computes the symmetrized mean PAE between each pair of chains:
    ipae(A, B) = 0.5 * (mean(PAE[A, B]) + mean(PAE[B, A]))

    Args:
        pae_matrix: PAE matrix of shape (n_residues, n_residues)
        chain_ids: List of chain IDs for each residue

    Returns:
        Dictionary: {chain1: {chain2: float}} with symmetrized mean PAE values
    """
    chain_ids_array = np.array(chain_ids)
    unique_chains = np.unique(chain_ids_array)
    result: dict[str, dict[str, float]] = {}

    for chain1 in unique_chains:
        result[chain1] = {}
        for chain2 in unique_chains:
            if chain1 == chain2:
                continue
            idx1 = np.where(chain_ids_array == chain1)[0]
            idx2 = np.where(chain_ids_array == chain2)[0]
            if idx1.size > 0 and idx2.size > 0:
                pae12 = pae_matrix[np.ix_(idx1, idx2)].mean()
                pae21 = pae_matrix[np.ix_(idx2, idx1)].mean()
                result[chain1][chain2] = float(0.5 * (pae12 + pae21))

    return result


def parse_structure_from_cif(
    cif_content: str,
) -> tuple[list[str], np.ndarray, list[str]]:
    """
    Parse chain IDs, coordinates, and residue types from mmCIF file content.

    Extracts chain IDs, CA/CB coordinates, and residue types from the CIF file.
    Only includes CA atoms (or C1' for nucleic acids) to match the PAE matrix dimensions.
    This matches the token filtering logic in ipsae_w_ipae.py.

    Args:
        cif_content: Content of the mmCIF file as a string

    Returns:
        Tuple of (chain_ids, coordinates, residue_types):
        - chain_ids: List of chain IDs for each CA/C1' atom
        - coordinates: NumPy array of shape (n_residues, 3) with xyz coordinates
        - residue_types: List of residue type names
    """
    chain_ids = []
    coordinates = []
    residue_types = []
    lines = cif_content.split("\n")
    field_indices = {}
    field_num = 0
    in_data_section = False

    for line in lines:
        line_stripped = line.strip()

        # Parse field definitions
        if line_stripped.startswith("_atom_site."):
            field_name = line_stripped.split(".")[1].split()[0]
            field_indices[field_name] = field_num
            field_num += 1
            in_data_section = True
            continue

        # Parse atom site lines (only ATOM and HETATM lines after field definitions)
        if in_data_section and (
            line_stripped.startswith("ATOM") or line_stripped.startswith("HETATM")
        ):
            parts = line_stripped.split()
            if len(parts) < max(field_indices.values()) + 1:
                continue

            # Get required field indices
            atom_name_idx = field_indices.get("label_atom_id", -1)
            chain_id_idx = field_indices.get("label_asym_id", -1)
            residue_name_idx = field_indices.get("label_comp_id", -1)
            residue_seq_idx = field_indices.get("label_seq_id", -1)
            x_idx = field_indices.get("Cartn_x", -1)
            y_idx = field_indices.get("Cartn_y", -1)
            z_idx = field_indices.get("Cartn_z", -1)

            if (
                atom_name_idx < 0
                or chain_id_idx < 0
                or residue_name_idx < 0
                or x_idx < 0
                or y_idx < 0
                or z_idx < 0
            ):
                continue

            atom_name = parts[atom_name_idx] if atom_name_idx < len(parts) else ""
            chain_id = parts[chain_id_idx] if chain_id_idx < len(parts) else ""
            residue_name = (
                parts[residue_name_idx] if residue_name_idx < len(parts) else ""
            )
            residue_seq = parts[residue_seq_idx] if residue_seq_idx < len(parts) else ""

            # Skip ligands (residue_seq_id == ".")
            if residue_seq == ".":
                continue

            # Only include CA atoms (or C1' for nucleic acids) to match PAE matrix
            # This matches the token_mask logic in ipsae_w_ipae.py
            is_ca = atom_name == "CA"
            is_c1 = "C1" in atom_name

            if is_ca or is_c1:
                chain_ids.append(chain_id)
                residue_types.append(residue_name)
                try:
                    x = float(parts[x_idx]) if x_idx < len(parts) else 0.0
                    y = float(parts[y_idx]) if y_idx < len(parts) else 0.0
                    z = float(parts[z_idx]) if z_idx < len(parts) else 0.0
                    coordinates.append([x, y, z])
                except (ValueError, IndexError):
                    # Skip if coordinates can't be parsed
                    chain_ids.pop()
                    residue_types.pop()

    coords_array = np.array(coordinates) if coordinates else np.array([]).reshape(0, 3)
    return chain_ids, coords_array, residue_types
