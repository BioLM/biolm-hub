import sys
from pathlib import Path
from typing import Optional

import torch
import torch.nn as nn
from omegaconf import OmegaConf

# Add ThermoMPNN to path
THERMOMPNN_DIR = Path("/root/ThermoMPNN")
sys.path.insert(0, str(THERMOMPNN_DIR))

from datasets import Mutation  # noqa: E402
from protein_mpnn_utils import alt_parse_PDB  # noqa: E402
from train_thermompnn import TransferModelPL  # noqa: E402

ALPHABET = "ACDEFGHIKLMNPQRSTVWYX"


def load_thermompnn(
    model_dir: Path,
    device: torch.device,
    checkpoint_name: str = "thermoMPNN_default.pt",
    protein_mpnn_checkpoint: str = "v_48_020.pt",
):
    """
    Load ThermoMPNN model following the base inference script pattern.

    Args:
        model_dir: Directory containing model checkpoints
        device: Torch device to load models on
        checkpoint_name: Name of ThermoMPNN checkpoint file
        protein_mpnn_checkpoint: Name of base ProteinMPNN checkpoint file (unused, kept for compatibility)

    Returns:
        Tuple of (thermompnn_model, config)
    """
    # Define config for model loading (matching base inference script)
    config = {
        "platform": {
            "thermompnn_dir": str(model_dir),
        },
        "training": {
            "num_workers": 8,
            "learn_rate": 0.001,
            "epochs": 100,
            "lr_schedule": True,
        },
        "model": {
            "hidden_dims": [64, 32],
            "subtract_mut": True,
            "num_final_layers": 2,
            "freeze_weights": True,
            "load_pretrained": True,
            "lightattn": True,
            "lr_schedule": True,
        },
    }

    # Convert to OmegaConf and merge (following base script pattern)
    cfg = OmegaConf.create(config)

    # Load ThermoMPNN model using PyTorch Lightning checkpoint loader
    checkpoint_path = model_dir / checkpoint_name
    if not checkpoint_path.exists():
        raise FileNotFoundError(f"ThermoMPNN checkpoint not found: {checkpoint_path}")

    model_pl = TransferModelPL.load_from_checkpoint(
        str(checkpoint_path),
        cfg=cfg,
        map_location=device,
    )

    model = model_pl.model
    model.eval()
    model = model.to(device)

    return model, cfg


def parse_mutation(mutation_str: str) -> tuple[str, int, str]:
    """
    Parse mutation string in format 'WT{position}MUT' (e.g., 'A100V').

    Args:
        mutation_str: Mutation string

    Returns:
        Tuple of (wildtype, position, mutation_aa)
    """
    if not mutation_str or len(mutation_str) < 3:
        raise ValueError(f"Invalid mutation format: {mutation_str}")

    wt = mutation_str[0]
    mut_aa = mutation_str[-1]

    try:
        position = int(mutation_str[1:-1])
    except ValueError as err:
        raise ValueError(
            f"Invalid mutation format: {mutation_str}. Position must be numeric."
        ) from err

    if wt not in ALPHABET:
        raise ValueError(f"Invalid wildtype amino acid: {wt}")
    if mut_aa not in ALPHABET:
        raise ValueError(f"Invalid mutation amino acid: {mut_aa}")

    return wt, position, mut_aa


def get_chains(pdb_path: str) -> list[str]:
    """Get chain IDs from PDB file."""
    from Bio.PDB import PDBParser

    parser = PDBParser(QUIET=True)
    structure = parser.get_structure("", pdb_path)
    chains = [c.id for c in structure.get_chains()]
    return chains


def get_ssm_mutations(pdb):
    """
    Generate site-saturation mutagenesis (SSM) mutations for all positions.
    Following base script pattern from analysis/SSM.py

    Args:
        pdb: Parsed PDB dictionary (from alt_parse_PDB)

    Returns:
        List of mutation strings in format 'WT{position}MUT' (0-indexed positions)
    """
    mutation_list = []
    for seq_pos in range(len(pdb["seq"])):
        wtAA = pdb["seq"][seq_pos]
        # check for missing residues
        if wtAA != "-":
            # add each mutation option (exclude X from ALPHABET)
            for mutAA in ALPHABET[:-1]:  # Exclude 'X' and '-'
                mutation_list.append(wtAA + str(seq_pos) + mutAA)
        else:
            mutation_list.append(None)

    return mutation_list


def predict(  # noqa: C901
    model: nn.Module,
    pdb_path: str,
    mutations: Optional[list[str]] = None,
    chain: Optional[str] = None,
) -> list[dict]:
    """
    Run ThermoMPNN prediction on a PDB with mutations, following base inference script pattern.
    If mutations are not provided, performs site-saturation mutagenesis (SSM) scan.

    Args:
        model: Loaded ThermoMPNN model (should be in eval mode and on correct device)
        pdb_path: Path to PDB file
        mutations: Optional list of mutation strings in format 'WT{position}MUT' (1-indexed PDB positions).
                   If None, performs SSM scan for all positions.
        chain: Chain ID to use (if None, uses first chain)

    Returns:
        List of prediction dictionaries with keys: mutation, position, wildtype, mutation_aa, ddg
    """
    # Get chain if not specified (following base script pattern)
    if chain is None or len(chain) < 1:
        chains = get_chains(pdb_path)
        if not chains:
            raise ValueError("No chains found in PDB file")
        chain = chains[0]

    # Parse PDB (following base script)
    mut_pdb = alt_parse_PDB(pdb_path, chain)

    # Generate mutations: either use provided list or perform SSM scan (following base script)
    is_ssm_scan = mutations is None or len(mutations) == 0
    if is_ssm_scan:
        # Perform site-saturation mutagenesis scan (following base script)
        mutation_list = get_ssm_mutations(mut_pdb[0])
    else:
        # Use provided mutations
        mutation_list = mutations

    # Build mutation objects (following base script pattern)
    # Note: get_ssm_mutations returns 0-indexed positions (e.g., "M0V" = position 0)
    # User-provided mutations use 1-indexed PDB positions (e.g., "M1V" = position 1)
    final_mutation_list = []
    for m in mutation_list:
        if m is None:
            final_mutation_list.append(None)
            continue

        m = m.strip()  # clear whitespace (following base script)
        wtAA, position, mutAA = str(m[0]), int(str(m[1:-1])), str(m[-1])

        # Validate amino acids (following base script pattern)
        if wtAA not in ALPHABET:
            raise ValueError(
                f"Wild type residue {wtAA} invalid, please try again with one of the following options: {ALPHABET}"
            )
        if mutAA not in ALPHABET:
            raise ValueError(
                f"Mutation residue {mutAA} invalid, please try again with one of the following options: {ALPHABET}"
            )

        # Convert position: SSM uses 0-indexed, user input uses 1-indexed
        if is_ssm_scan:
            # SSM returns 0-indexed positions directly
            position_0_indexed = position
        else:
            # User input uses 1-indexed PDB positions, convert to 0-indexed
            position_0_indexed = position - 1

        mutation_obj = Mutation(
            position=position_0_indexed,
            wildtype=wtAA,
            mutation=mutAA,
            ddG=None,
            pdb=mut_pdb[0]["name"],
        )
        final_mutation_list.append(mutation_obj)

    # Run prediction (following base script pattern)
    with torch.no_grad():
        pred, _ = model(mut_pdb, final_mutation_list)

    # Format results (following base script pattern)
    results = []
    for mut, out in zip(final_mutation_list, pred, strict=False):
        if mut is None or out is None:
            continue

        # Extract ddG (following base script)
        ddg = out["ddG"].cpu().item()

        # Return 1-indexed position to match user input format
        results.append(
            {
                "mutation": f"{mut.wildtype}{mut.position + 1}{mut.mutation}",  # Convert back to 1-indexed for output
                "position": mut.position + 1,  # Convert back to 1-indexed for output
                "wildtype": mut.wildtype,
                "mutation_aa": mut.mutation,
                "ddg": ddg,
            }
        )

    return results
