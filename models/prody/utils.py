"""ProDy utility functions for structure processing and interaction analysis."""

import logging
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import prody

    from models.prody.schema import (
        ProDyEncodeRequestItem,
        ProDyEncodeRequestParams,
        ProDyPredictRequestItem,
        ProDyPredictRequestParams,
    )

from models.prody.schema import (
    AlignmentMethod,
    ChainInteractionSummary,
    ChainPairInteractions,
    FrequentInteractor,
    HydrogenMethod,
    Interaction,
    ProDyEncodeResponseResult,
    ProDyPredictResponseResult,
)

logger = logging.getLogger(__name__)


def get_structure_string_and_format(item) -> tuple[str, str]:
    """Get structure string and format from item (pdb or cif)."""
    if item.pdb is not None:
        return item.pdb, "PDB"
    elif item.cif is not None:
        return item.cif, "CIF"
    else:
        raise ValueError("Either pdb or cif must be provided")


def convert_cif_to_pdb(cif_path: str | Path) -> str:
    """
    Convert CIF file to PDB format using OpenMM (primary) or ProDy (fallback).

    Args:
        cif_path: Path to CIF file

    Returns:
        Path to converted PDB file as string

    Raises:
        ValueError: If conversion fails with both methods
    """
    from prody import parseMMCIF, writePDB

    cif_path_str = str(cif_path)
    cif_path_obj = Path(cif_path)

    # Try OpenMM first (better element symbol preservation)
    try:
        from openmm.app import PDBFile, PDBxFile

        cif = PDBxFile(cif_path_str)
        pdb_path = cif_path_obj.parent / f"{cif_path_obj.stem}_converted.pdb"
        with open(pdb_path, "w") as f:
            PDBFile.writeFile(cif.topology, cif.positions, f)
        logger.info(f"Converted CIF to PDB using OpenMM: {pdb_path}")
        return str(pdb_path)
    except ImportError:
        logger.warning("OpenMM not available, falling back to ProDy conversion")
    except Exception as e:
        logger.warning(f"OpenMM conversion failed: {e}, trying ProDy fallback")

    # Fallback to ProDy conversion
    try:
        structure = parseMMCIF(cif_path_str)
        pdb_path = cif_path_obj.parent / f"{cif_path_obj.stem}.pdb"
        writePDB(str(pdb_path), structure)
        logger.info(f"Converted CIF to PDB using ProDy: {pdb_path}")
        return str(pdb_path)
    except Exception as e:
        raise ValueError(f"Failed to convert CIF to PDB with both methods: {e}") from e


def add_hydrogens(  # noqa: C901
    structure_path: Path, method: HydrogenMethod | str
) -> Path:
    """Add missing hydrogen atoms to structure."""
    from prody import addMissingAtoms

    # Normalize method to string
    if isinstance(method, HydrogenMethod):
        method_str = method.value
    else:
        method_str = str(method)

    structure_path_str = str(structure_path)
    is_cif = structure_path.suffix.lower() in [".cif", ".mmcif"]

    # Convert CIF to PDB if needed (both methods work better with PDB)
    if is_cif:
        if method_str == "pdbfixer":
            logger.info("CIF file detected with pdbfixer. Converting to PDB first.")
        elif method_str == "openbabel":
            logger.info(
                "CIF file detected with openbabel. "
                "Converting to PDB first (OpenBabel handles CIF poorly)."
            )
        structure_path_str = convert_cif_to_pdb(structure_path_str)
        is_cif = False

    output_path = (
        Path(structure_path_str).parent / f"addH_{Path(structure_path_str).name}"
    )

    try:
        addMissingAtoms(structure_path_str, method=method_str)

        if output_path.exists():
            logger.info(f"Hydrogens added using {method_str}, saved to {output_path}")
            return output_path
        else:
            # Sometimes ProDy saves with different naming
            alt_path = (
                Path(structure_path_str).parent
                / f"addH_{Path(structure_path_str).stem}.pdb"
            )
            if alt_path.exists():
                return alt_path
            raise FileNotFoundError(
                f"Hydrogen-added structure not found at {output_path} or {alt_path}"
            )
    except Exception as e:
        logger.error(f"Error adding hydrogens with {method_str}: {e}")
        # If openbabel fails, try pdbfixer as fallback
        if method_str == "openbabel":
            logger.warning(f"OpenBabel failed: {e}. Falling back to pdbfixer.")
            try:
                pdb_path_str = structure_path_str
                if is_cif:
                    pdb_path_str = convert_cif_to_pdb(structure_path_str)

                addMissingAtoms(pdb_path_str, method="pdbfixer")
                output_path = (
                    Path(pdb_path_str).parent / f"addH_{Path(pdb_path_str).name}"
                )
                if output_path.exists():
                    logger.info("Successfully added hydrogens using pdbfixer fallback")
                    return output_path
                alt_path = (
                    Path(pdb_path_str).parent / f"addH_{Path(pdb_path_str).stem}.pdb"
                )
                if alt_path.exists():
                    return alt_path
            except Exception as fallback_e:
                logger.error(f"Fallback to pdbfixer also failed: {fallback_e}")

        raise ValueError(f"Failed to add hydrogens using {method_str}: {e}") from e


def parse_structure(
    structure_path: str | Path, structure_format: str
) -> "prody.Atomic":
    """Parse structure file into ProDy Atomic object.

    Automatically detects file format from extension to handle cases where
    CIF files are converted to PDB during hydrogen addition.
    """
    from prody import parseMMCIF, parsePDB

    if isinstance(structure_path, Path):
        structure_path_str = str(structure_path)
        file_ext = structure_path.suffix.lower()
        if file_ext == ".pdb":
            actual_format = "PDB"
        elif file_ext in [".cif", ".mmcif"]:
            actual_format = "CIF"
        else:
            actual_format = structure_format
    else:
        structure_path_str = structure_path
        if structure_path_str.endswith(".pdb"):
            actual_format = "PDB"
        elif structure_path_str.endswith((".cif", ".mmcif")):
            actual_format = "CIF"
        else:
            actual_format = structure_format

    if actual_format == "CIF":
        try:
            structure = parseMMCIF(structure_path_str)
        except Exception as e:
            logger.warning(f"Failed to parse as mmCIF: {e}, trying PDB parser")
            structure = parsePDB(structure_path_str)
    else:
        structure = parsePDB(structure_path_str)

    if structure is None:
        raise ValueError("Failed to parse structure")

    return structure


def parse_interaction_list(  # noqa: C901
    interaction_list: list, interaction_type: str
) -> list[Interaction]:
    """Parse ProDy interaction list into Interaction objects.

    ProDy returns lists in format:
    - [residue1, atom1, chain1, residue2, atom2, chain2, distance, energy?]
    """
    interactions = []

    if not isinstance(interaction_list, list):
        return interactions

    for inter in interaction_list:
        if not isinstance(inter, list | tuple):
            logger.warning(f"Unexpected interaction format (not a list): {inter}")
            continue

        if len(inter) < 6:
            logger.warning(
                f"Interaction list too short (need at least 6 elements): {inter}"
            )
            continue

        try:
            residue1 = str(inter[0]) if inter[0] is not None else ""
            atom1 = str(inter[1]) if len(inter) > 1 and inter[1] is not None else None
            chain1 = str(inter[2]) if len(inter) > 2 and inter[2] is not None else ""
            residue2 = str(inter[3]) if len(inter) > 3 and inter[3] is not None else ""
            atom2 = str(inter[4]) if len(inter) > 4 and inter[4] is not None else None
            chain2 = str(inter[5]) if len(inter) > 5 and inter[5] is not None else ""

            distance = None
            energy = None
            if len(inter) > 6:
                try:
                    distance = float(inter[6])
                except (ValueError, TypeError):
                    pass
            if len(inter) > 7:
                try:
                    energy = float(inter[7])
                except (ValueError, TypeError):
                    pass

            if not residue1 or not residue2 or not chain1 or not chain2:
                logger.warning(f"Incomplete interaction data: {inter}")
                continue

            interactions.append(
                Interaction(
                    interaction_type=interaction_type,
                    chain1=chain1,
                    residue1=residue1,
                    atom1=atom1,
                    chain2=chain2,
                    residue2=residue2,
                    atom2=atom2,
                    distance=distance,
                    energy=energy,
                )
            )
        except Exception as e:
            logger.warning(f"Error parsing interaction {inter}: {e}")
            continue

    return interactions


def extract_interactions(
    interactions_obj, chain1: str | None = None, chain2: str | None = None
) -> dict[str, list[Interaction]]:
    """Extract all interaction types from ProDy InSty interactions object."""
    all_interactions: dict[str, list[Interaction]] = {}

    selection1 = f"chain {chain1}" if chain1 else None
    selection2 = f"chain {chain2}" if chain2 else None

    # Extract different interaction types - use sorted order for determinism
    interaction_methods = {
        "hydrogen_bond": "getHydrogenBonds",
        "salt_bridge": "getSaltBridges",
        "hydrophobic": "getHydrophobic",
        "pi_stacking": "getPiStacking",
        "cation_pi": "getPiCation",
        "repulsive_ionic": "getRepulsiveIonicBonding",
    }

    for inter_type, method_name in sorted(interaction_methods.items()):
        try:
            method = getattr(interactions_obj, method_name, None)
            if method is None:
                continue

            if selection1 and selection2:
                inter_list = method(selection=selection1, selection2=selection2)
            elif selection1:
                inter_list = method(selection=selection1)
            else:
                inter_list = method()

            if inter_list and len(inter_list) > 0:
                parsed = parse_interaction_list(inter_list, inter_type)
                if parsed:
                    all_interactions[inter_type] = parsed
        except Exception as e:
            logger.warning(f"Error extracting {inter_type} interactions: {e}")

    return all_interactions


def interaction_sort_key(interaction: Interaction) -> tuple:
    """Generate sort key for interactions to ensure consistent ordering."""
    return (
        interaction.interaction_type or "",
        interaction.chain1 or "",
        interaction.chain2 or "",
        interaction.residue1 or "",
        interaction.residue2 or "",
        interaction.atom1 or "",
        interaction.atom2 or "",
        interaction.distance if interaction.distance is not None else float("inf"),
    )


def process_chain_pair_interactions(
    interactions_obj, chain1: str, chain2: str
) -> ChainPairInteractions:
    """Process interactions for a single chain pair."""
    pair_interactions_dict_result = extract_interactions(
        interactions_obj, chain1=chain1, chain2=chain2
    )

    pair_interactions_list: list[Interaction] = []
    for interactions in pair_interactions_dict_result.values():
        pair_interactions_list.extend(interactions)

    pair_interactions_list.sort(key=interaction_sort_key)

    interaction_counts: dict[str, int] = {}
    for inter in pair_interactions_list:
        interaction_counts[inter.interaction_type] = (
            interaction_counts.get(inter.interaction_type, 0) + 1
        )

    return ChainPairInteractions(
        chain_pair=(chain1, chain2),
        interactions=pair_interactions_list,
        interaction_counts=interaction_counts,
        total_interactions=len(pair_interactions_list),
    )


def summarize_interactions(
    interactions: list[Interaction],
) -> ChainInteractionSummary:
    """Create summary of interactions."""
    if not interactions:
        return ChainInteractionSummary(
            chain_id=None,
            chain_pair=None,
            interaction_counts={},
            total_interactions=0,
            interactions=[],
        )

    counts: dict[str, int] = {}
    for inter in interactions:
        counts[inter.interaction_type] = counts.get(inter.interaction_type, 0) + 1

    chain_id = None
    chain_pair = None
    first_inter = interactions[0]
    if first_inter.chain1 == first_inter.chain2:
        chain_id = first_inter.chain1
    else:
        chain_pair = (first_inter.chain1, first_inter.chain2)

    return ChainInteractionSummary(
        chain_id=chain_id,
        chain_pair=chain_pair,
        interaction_counts=counts,
        total_interactions=len(interactions),
        interactions=interactions,
    )


def parse_frequent_interactors(
    interactors_output: str,
) -> list[FrequentInteractor]:
    """Parse frequent interactors from ProDy output string."""
    frequent_interactors = []

    lines = interactors_output.strip().split("\n")
    for line in lines:
        line = line.strip()
        if not line or "Legend" in line or "<--->" not in line:
            continue

        if line.startswith("@>"):
            line = line[2:].strip()

        parts = line.split("<--->")
        if len(parts) == 2:
            residue = parts[0].strip()
            interactors_str = parts[1].strip()
            interactors = interactors_str.split() if interactors_str else []
            contact_count = len(interactors)

            if residue:
                frequent_interactors.append(
                    FrequentInteractor(
                        residue=residue,
                        interactors=interactors,
                        contact_count=contact_count,
                    )
                )

    return frequent_interactors


def validate_structure_for_prody(structure, protein_atoms) -> tuple[bool, str | None]:
    """Validate structure is suitable for ProDy interaction calculation."""
    import numpy as np

    if protein_atoms is None or protein_atoms.numAtoms() == 0:
        return False, "No protein atoms found in structure"

    coords = protein_atoms.getCoords()
    if coords is None or len(coords) == 0:
        return False, "No coordinates found for protein atoms"

    if np.any(np.isnan(coords)) or np.any(np.isinf(coords)):
        return False, "Structure contains NaN or infinite coordinates"

    chains = protein_atoms.getChids()
    if chains is None or len(set(chains)) == 0:
        return False, "No valid chain assignments found"

    resnames = protein_atoms.getResnames()
    if resnames is None or len(resnames) == 0:
        return False, "No residue names found"

    num_residues = len(set(protein_atoms.getResnums()))
    if num_residues < 5:
        return (
            False,
            f"Structure too small ({num_residues} residues), need at least 5 for meaningful interactions",
        )

    return True, None


def reinitialize_structure_after_hydrogen_addition(
    structure_file: Path, structure_format: str
) -> tuple["prody.Atomic", "prody.Atomic"]:
    """Re-initialize structure and protein_atoms after hydrogen addition."""
    structure = parse_structure(structure_file, structure_format)
    protein_atoms = structure.select("protein")
    if protein_atoms is None or protein_atoms.numAtoms() == 0:
        protein_atoms = structure

    return structure, protein_atoms


def validate_interactions_calculated(interactions_obj) -> tuple[bool, bool]:
    """Check if ProDy Interactions object actually calculated interactions."""
    if interactions_obj is None:
        return False, False

    try:
        hb = interactions_obj.getHydrogenBonds()
        has_interactions = bool(hb) if hb is not None else False
        return True, has_interactions
    except Exception:
        return False, False


def process_structure_for_insty(  # noqa: C901
    item: "ProDyEncodeRequestItem", params: "ProDyEncodeRequestParams"
) -> ProDyEncodeResponseResult:
    """Process a single structure for InSty analysis."""
    import os
    import random
    from contextlib import redirect_stdout
    from io import StringIO

    import numpy as np

    # Ensure deterministic behavior
    seed = 42
    random.seed(seed)
    np.random.seed(seed)
    os.environ["PYTHONHASHSEED"] = str(seed)

    structure_str, structure_format = get_structure_string_and_format(item)
    hydrogens_added = False

    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        structure_file = (
            tmp_path / f"structure.{'cif' if structure_format == 'CIF' else 'pdb'}"
        )

        with open(structure_file, "w") as f:
            f.write(structure_str)

        structure_file_original = structure_file
        hydrogens_added = False

        # Parse structure
        structure = parse_structure(structure_file, structure_format)
        try:
            _ = structure.numAtoms()
            _ = structure.numCoordsets()
        except Exception:
            import traceback

            traceback.print_exc()
            raise

        # Get available chains - sort for determinism
        try:
            raw_chids = structure.getChids()
            available_chains = sorted(set(raw_chids)) if raw_chids is not None else []
        except Exception as e:
            import traceback

            traceback.print_exc()
            raise ValueError(f"Could not extract chain IDs from structure: {e}") from e

        # Filter chains if specified
        if item.chain_ids is not None:
            chains_to_analyze = sorted(
                [c for c in item.chain_ids if c in available_chains]
            )
        else:
            chains_to_analyze = available_chains

        if not chains_to_analyze:
            raise ValueError(
                f"No valid chains found. Requested: {item.chain_ids}, Available: {available_chains}"
            )

        from prody import Interactions

        interactions_obj = None
        protein_atoms = structure.select("protein")
        if protein_atoms is None or protein_atoms.numAtoms() == 0:
            protein_atoms = structure

        # Validate structure
        is_valid, error_msg = validate_structure_for_prody(structure, protein_atoms)
        if not is_valid:
            raise ValueError(f"Structure validation failed: {error_msg}")

        # Add hydrogens if requested
        if params.add_hydrogens and not hydrogens_added:
            logger.info(
                "Adding hydrogens before interaction calculation as requested..."
            )
            try:
                hydrogen_method = (
                    params.hydrogen_method.value
                    if params.hydrogen_method
                    else HydrogenMethod.PDBFIXER.value
                )
                structure_file = add_hydrogens(structure_file_original, hydrogen_method)
                hydrogens_added = True

                del structure, protein_atoms
                structure, protein_atoms = (
                    reinitialize_structure_after_hydrogen_addition(
                        structure_file, structure_format
                    )
                )

                is_valid, error_msg = validate_structure_for_prody(
                    structure, protein_atoms
                )
                if not is_valid:
                    raise ValueError(
                        f"Structure validation failed after hydrogen addition: {error_msg}"
                    )

                logger.info(
                    f"Structure after H addition: {protein_atoms.numAtoms()} atoms"
                )
            except Exception as e:
                logger.error(f"Failed to add hydrogens before calculation: {e}")
                raise ValueError(f"Hydrogen addition failed: {e}") from e

        # Calculate interactions
        try:
            logger.info(
                "Creating ProDy Interactions object and calculating interactions..."
            )
            interactions_obj = Interactions(str(structure_file))
            interactions_obj.calcProteinInteractions(protein_atoms)

            calc_succeeded, has_interactions = validate_interactions_calculated(
                interactions_obj
            )
            if not calc_succeeded:
                raise ValueError(
                    "ProDy interaction calculation did not complete successfully"
                )

            if has_interactions:
                logger.info("Interactions calculated successfully")
            else:
                logger.warning(
                    "No interactions found (structure may be too small or have no interactions)"
                )

        except Exception as e:
            error_msg = str(e).lower()
            if "hydrogen" in error_msg or "hydrogens" in error_msg:
                logger.info(
                    f"Interaction calculation requires hydrogens: {e}. "
                    "Adding hydrogens and retrying..."
                )
                try:
                    hydrogen_method = (
                        params.hydrogen_method.value
                        if params.hydrogen_method
                        else "pdbfixer"
                    )
                    structure_file = add_hydrogens(
                        structure_file_original, hydrogen_method
                    )
                    hydrogens_added = True

                    del structure, protein_atoms
                    structure, protein_atoms = (
                        reinitialize_structure_after_hydrogen_addition(
                            structure_file, structure_format
                        )
                    )

                    is_valid, error_msg = validate_structure_for_prody(
                        structure, protein_atoms
                    )
                    if not is_valid:
                        raise ValueError(
                            f"Structure validation failed after hydrogen addition: {error_msg}"
                        )

                    logger.info(
                        f"Added hydrogens: structure now has {protein_atoms.numAtoms()} atoms"
                    )

                    interactions_obj = Interactions(str(structure_file))
                    interactions_obj.calcProteinInteractions(protein_atoms)

                    calc_succeeded, has_interactions = validate_interactions_calculated(
                        interactions_obj
                    )
                    if not calc_succeeded:
                        raise ValueError(
                            "Interaction calculation did not complete successfully after adding hydrogens"
                        )

                    logger.info(
                        "Successfully computed interactions after adding hydrogens"
                    )
                except Exception as retry_e:
                    retry_error_msg = str(retry_e).lower()
                    logger.error(
                        f"Failed to compute interactions even after adding hydrogens: {retry_e}. "
                        f"Structure: {protein_atoms.numAtoms()} atoms, chains: {available_chains}"
                    )

                    if (
                        "index" in retry_error_msg
                        and "out of bounds" in retry_error_msg
                    ):
                        error_detail = (
                            "ProDy index out of bounds error persists after hydrogen addition. "
                            "This indicates a fundamental incompatibility with this structure."
                        )
                    elif (
                        "nonetype" in retry_error_msg
                        or "not subscriptable" in retry_error_msg
                    ):
                        error_detail = (
                            "ProDy NoneType error persists after hydrogen addition. "
                            "This structure has features ProDy cannot handle."
                        )
                    elif "listofatomtocompare" in retry_error_msg.replace(" ", ""):
                        error_detail = (
                            "ProDy hydrophobic calculation bug. "
                            "This is a known ProDy issue with certain structure geometries."
                        )
                    else:
                        error_detail = f"Unexpected error: {retry_e}"

                    raise ValueError(
                        f"Failed to compute interactions: {error_detail}"
                    ) from retry_e
            elif "index" in error_msg and "out of bounds" in error_msg:
                logger.error(
                    f"ProDy index out of bounds error: {e}. "
                    f"Structure has {protein_atoms.numAtoms()} atoms but ProDy is accessing higher indices. "
                    "This is a ProDy bug that occurs when atom indices become inconsistent."
                )
                raise ValueError(
                    f"ProDy index mismatch error (structure has {protein_atoms.numAtoms()} atoms): {e}. "
                    "This structure cannot be processed with ProDy due to internal indexing issues."
                ) from e
            elif "nonetype" in error_msg or "not subscriptable" in error_msg:
                logger.error(
                    f"ProDy NoneType error: {e}. "
                    "ProDy's internal functions returned None for this structure. "
                    "This usually indicates the structure has unusual features ProDy cannot handle."
                )
                raise ValueError(
                    f"ProDy NoneType error - structure cannot be processed: {e}"
                ) from e
            elif "listofatomtocompare" in error_msg.replace(" ", "").lower():
                logger.error(
                    f"ProDy hydrophobic calculation error: {e}. "
                    "This is a known ProDy bug in hydrophobic interaction calculation."
                )
                raise ValueError(
                    f"ProDy hydrophobic interaction calculation failed: {e}. "
                    "This structure triggers a ProDy bug and cannot be fully analyzed."
                ) from e
            else:
                logger.error(
                    f"ProDy interaction calculation failed with unexpected error: {e}. "
                    f"Structure info: {protein_atoms.numAtoms()} atoms, "
                    f"{len(available_chains)} chains: {available_chains}"
                )
                raise

        if interactions_obj is None:
            raise ValueError(
                "Failed to create interactions object - cannot extract results"
            )

        # If explicitly requested to add hydrogens but they weren't added yet
        if params.add_hydrogens and not hydrogens_added:
            try:
                hydrogen_method = (
                    params.hydrogen_method.value
                    if params.hydrogen_method
                    else HydrogenMethod.PDBFIXER.value
                )
                structure_file = add_hydrogens(structure_file_original, hydrogen_method)
                hydrogens_added = True
                structure, protein_atoms = (
                    reinitialize_structure_after_hydrogen_addition(
                        structure_file, structure_format
                    )
                )
                interactions_obj = Interactions(str(structure_file))
                interactions_obj.calcProteinInteractions(protein_atoms)
            except Exception as e:
                logger.warning(f"Failed to add hydrogens as requested: {e}")

        # Process intra-chain interactions
        intra_chain_dict = {}
        for chain_id in chains_to_analyze:
            chain_interactions_dict = extract_interactions(
                interactions_obj, chain1=chain_id, chain2=chain_id
            )
            chain_interactions_list: list[Interaction] = []
            for interactions in chain_interactions_dict.values():
                chain_interactions_list.extend(interactions)

            chain_interactions_list.sort(key=interaction_sort_key)

            summary = summarize_interactions(chain_interactions_list)
            summary.chain_id = chain_id
            intra_chain_dict[chain_id] = summary

        # Process inter-chain interactions
        pair_interactions_dict = {}
        chain_pairs_analyzed: list[tuple[str, str]] = []

        if item.chain_pairs is not None:
            for chain1, chain2 in item.chain_pairs:
                if chain1 not in chains_to_analyze or chain2 not in chains_to_analyze:
                    continue
                chain_pairs_analyzed.append((chain1, chain2))

                pair_data = process_chain_pair_interactions(
                    interactions_obj, chain1, chain2
                )
                pair_key = f"{chain1}-{chain2}"
                pair_interactions_dict[pair_key] = pair_data
        else:
            for i, chain1 in enumerate(chains_to_analyze):
                for chain2 in chains_to_analyze[i + 1 :]:
                    chain_pairs_analyzed.append((chain1, chain2))

                    pair_data = process_chain_pair_interactions(
                        interactions_obj, chain1, chain2
                    )
                    pair_key = f"{chain1}-{chain2}"
                    pair_interactions_dict[pair_key] = pair_data

        # Build interaction matrices if requested
        interaction_matrix = None
        energy_matrix = None
        if params.return_interaction_matrix or params.return_energy_matrix:
            if item.chain_pairs is not None and len(pair_interactions_dict) > 0:
                selection1 = f"chain {item.chain_pairs[0][0]}"
                selection2 = f"chain {item.chain_pairs[0][1]}"
                try:
                    interactions_obj.getInteractions(
                        selection=selection1, selection2=selection2, replace=True
                    )
                except Exception as e:
                    logger.warning(f"Could not filter interactions for matrix: {e}")

            if params.return_interaction_matrix:
                try:
                    matrix = interactions_obj.buildInteractionMatrix()
                    if matrix is not None:
                        interaction_matrix = (
                            matrix.tolist() if hasattr(matrix, "tolist") else matrix
                        )
                except Exception as e:
                    logger.warning(f"Error building interaction matrix: {e}")

            if params.return_energy_matrix:
                try:
                    matrix_en = interactions_obj.buildInteractionMatrixEnergy()
                    if matrix_en is not None:
                        energy_matrix = (
                            matrix_en.tolist()
                            if hasattr(matrix_en, "tolist")
                            else matrix_en
                        )
                except Exception as e:
                    logger.warning(f"Error building energy matrix: {e}")

        # Get frequent interactors if requested
        frequent_interactors = None
        if params.return_frequent_interactors:
            try:
                f = StringIO()
                with redirect_stdout(f):
                    interactions_obj.getFrequentInteractors(
                        contacts_min=params.frequent_interactors_min_contacts
                    )
                output = f.getvalue()

                frequent_interactors = parse_frequent_interactors(output)
            except Exception as e:
                logger.warning(f"Error getting frequent interactors: {e}")

        return ProDyEncodeResponseResult(
            structure_format=structure_format,
            chains_analyzed=chains_to_analyze,
            chain_pairs_analyzed=(
                chain_pairs_analyzed if chain_pairs_analyzed else None
            ),
            intra_chain_interactions=intra_chain_dict,
            pair_interactions=pair_interactions_dict,
            hydrogens_added=hydrogens_added,
            interaction_matrix=interaction_matrix,
            energy_matrix=energy_matrix,
            frequent_interactors=frequent_interactors,
        )


def compute_rmsd(  # noqa: C901
    item: "ProDyPredictRequestItem", params: "ProDyPredictRequestParams"
) -> ProDyPredictResponseResult:
    """Compute RMSD between two structures."""
    from prody import calcRMSD

    # Try different import paths for sequence alignment
    try:
        from prody.sequence import alignBioPairwise  # noqa: F401
    except ImportError:
        try:
            from prody import alignBioPairwise  # noqa: F401
        except ImportError:
            try:
                from prody.sequence.align import alignBioPairwise  # noqa: F401
            except ImportError:
                pass

    structure_a_str = item.pdb_a if item.pdb_a is not None else item.cif_a
    structure_b_str = item.pdb_b if item.pdb_b is not None else item.cif_b
    format_a = "PDB" if item.pdb_a is not None else "CIF"
    format_b = "PDB" if item.pdb_b is not None else "CIF"

    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        file_a = tmp_path / f"structure_a.{'cif' if format_a == 'CIF' else 'pdb'}"
        file_b = tmp_path / f"structure_b.{'cif' if format_b == 'CIF' else 'pdb'}"

        with open(file_a, "w") as f:
            f.write(structure_a_str)
        with open(file_b, "w") as f:
            f.write(structure_b_str)

        structure_a = parse_structure(file_a, format_a)
        structure_b = parse_structure(file_b, format_b)

        chains_a = [item.chain_a] if isinstance(item.chain_a, str) else item.chain_a
        chains_b = [item.chain_b] if isinstance(item.chain_b, str) else item.chain_b

        chain_selections_a = []
        for chain_id in chains_a:
            chain_sel = structure_a.select(f"chain {chain_id} and protein")
            if chain_sel is None or chain_sel.numAtoms() == 0:
                chain_sel = structure_a.select(f"chain {chain_id}")
                if chain_sel is None or chain_sel.numAtoms() == 0:
                    raise ValueError(
                        f"Chain {chain_id} not found or empty in structure A"
                    )
            chain_selections_a.append(chain_sel)

        if len(chain_selections_a) == 1:
            chain_a_sel = chain_selections_a[0]
        else:
            chain_a_sel = chain_selections_a[0]
            for sel in chain_selections_a[1:]:
                chain_a_sel = chain_a_sel + sel

        chain_selections_b = []
        for chain_id in chains_b:
            chain_sel = structure_b.select(f"chain {chain_id} and protein")
            if chain_sel is None or chain_sel.numAtoms() == 0:
                chain_sel = structure_b.select(f"chain {chain_id}")
                if chain_sel is None or chain_sel.numAtoms() == 0:
                    raise ValueError(
                        f"Chain {chain_id} not found or empty in structure B"
                    )
            chain_selections_b.append(chain_sel)

        if len(chain_selections_b) == 1:
            chain_b_sel = chain_selections_b[0]
        else:
            chain_b_sel = chain_selections_b[0]
            for sel in chain_selections_b[1:]:
                chain_b_sel = chain_b_sel + sel

        ca_a = chain_a_sel.select("calpha")
        ca_b = chain_b_sel.select("calpha")

        if ca_a is None or ca_a.numAtoms() == 0:
            raise ValueError(
                f"No CA atoms found in structure_a chains {chains_a}. "
                "Make sure the chains contain protein residues."
            )
        if ca_b is None or ca_b.numAtoms() == 0:
            raise ValueError(
                f"No CA atoms found in structure_b chains {chains_b}. "
                "Make sure the chains contain protein residues."
            )

        matched_residues = None
        rmsd = None
        alignment_method_used = params.alignment_method

        try:
            from prody import calcRMSD, calcTransformation
            from prody.proteins import matchChains

            use_pwalign = params.alignment_method == AlignmentMethod.SEQUENCE

            if use_pwalign:
                matches = matchChains(ca_a, ca_b, pwalign=True, seqid=1.0, overlap=1.0)
            else:
                matches = matchChains(ca_a, ca_b, pwalign=False)

            if not matches or len(matches) == 0:
                raise ValueError("No matching chains found between structures")

            match = matches[0]
            atommap_ref = match[0]
            atommap_mobile = match[1]
            overlap = match[3] if len(match) > 3 else None

            if overlap is not None:
                matched_residues = (
                    int(atommap_ref.numAtoms() * overlap / 100.0)
                    if isinstance(overlap, float)
                    else int(overlap)
                )
            else:
                matched_residues = int(atommap_ref.numAtoms())

            transformation = calcTransformation(atommap_mobile, atommap_ref)
            mobile_transformed = transformation.apply(atommap_mobile)
            rmsd = float(calcRMSD(mobile_transformed, atommap_ref))

            if use_pwalign:
                alignment_method_used = AlignmentMethod.SEQUENCE
            else:
                alignment_method_used = AlignmentMethod.STRUCTURAL

        except Exception as e:
            logger.error(f"RMSD calculation failed: {e}")
            raise ValueError(f"Failed to compute RMSD: {e}") from e

        if rmsd is None:
            raise ValueError("RMSD calculation returned None")

        return ProDyPredictResponseResult(
            rmsd=float(rmsd),
            alignment_method=alignment_method_used.value,
            chain_a=item.chain_a,
            chain_b=item.chain_b,
            matched_residues=matched_residues,
        )
