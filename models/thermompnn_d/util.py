"""
ThermoMPNN-D utility functions with PyTorch Lightning checkpoint loading patch.

This module applies a monkey-patch to PyTorch Lightning's load_from_checkpoint method
to force CPU loading by default. This is required for Modal's memory snapshot feature,
which creates snapshots during the build phase when no GPU is available.
"""

import logging
import sys
from functools import wraps
from pathlib import Path
from typing import Any, Optional, Union

import pytorch_lightning as pl
import torch
import torch.nn as nn

logger = logging.getLogger(__name__)

# Monkey-patch PyTorch Lightning to load checkpoints on CPU by default.
# Required for Modal memory snapshots (no GPU available at build time).
_original_load_from_checkpoint = pl.LightningModule.load_from_checkpoint.__func__


@classmethod
@wraps(_original_load_from_checkpoint)
def _cpu_load_from_checkpoint(
    cls, checkpoint_path, *args, map_location="cpu", **kwargs
):
    return _original_load_from_checkpoint(
        cls, checkpoint_path, *args, map_location=map_location, **kwargs
    )


pl.LightningModule.load_from_checkpoint = _cpu_load_from_checkpoint

# Add ThermoMPNN-D to path
THERMOMPNN_D_DIR = Path("/root/ThermoMPNN-D")
sys.path.insert(0, str(THERMOMPNN_D_DIR))

from thermompnn.ssm_utils import get_config, get_dmat, get_model, load_pdb  # noqa: E402
from v2_ssm import (  # noqa: E402
    format_output_double,
    format_output_single,
)
from v2_ssm import (  # noqa: E402
    run_epistatic_ssm as v2_run_epistatic_ssm,
)
from v2_ssm import (  # noqa: E402
    run_single_ssm as v2_run_single_ssm,
)

ALPHABET = "ACDEFGHIKLMNPQRSTVWYX"


# Use functions from v2_ssm.py directly - no need to duplicate


def run_epistatic_ssm(pdb, cfg, model, distance, threshold, batch_size):
    """Run epistatic model on double mutations using v2_ssm function."""
    # Use the v2_ssm run_epistatic_ssm function directly
    return v2_run_epistatic_ssm(pdb, cfg, model, distance, threshold, batch_size)


def load_thermompnn_d(
    model_dir: Path,
    device: torch.device,
    mode: str = "single",
    checkpoint_name: Optional[str] = None,
):
    """
    Load ThermoMPNN-D model based on mode.

    Args:
        model_dir: Directory containing model checkpoints
        device: Torch device to load models on
        mode: Mode to use ('single', 'additive', or 'epistatic')
        checkpoint_name: Optional specific checkpoint name (if None, uses default for mode)

    Returns:
        Tuple of (model, config)
    """
    # Create config for model loading
    config = get_config(mode)

    # Override platform directory
    config.platform.thermompnn_dir = str(model_dir)

    # Load model
    model = get_model(mode, config)
    model.eval()
    model = model.to(device)

    return model, config


def parse_mutation(
    mutation_str: str,
) -> Union[tuple[str, int, str], tuple[str, int, str, str, int, str]]:
    """
    Parse mutation string.

    For single: 'WT{position}MUT' (e.g., 'A100V')
    For double: 'WT1{pos1}MUT1:WT2{pos2}MUT2' (e.g., 'A100V:B200L')

    Returns:
        For single: (wt, position, mut_aa)
        For double: (wt1, pos1, mut_aa1, wt2, pos2, mut_aa2)
    """
    if ":" in mutation_str:
        # Double mutation
        parts = mutation_str.split(":")
        if len(parts) != 2:
            raise ValueError(f"Invalid double mutation format: {mutation_str}")

        wt1, pos1, mut_aa1 = _parse_single_mut(parts[0])
        wt2, pos2, mut_aa2 = _parse_single_mut(parts[1])

        return (wt1, pos1, mut_aa1, wt2, pos2, mut_aa2)
    else:
        # Single mutation
        return _parse_single_mut(mutation_str)


def _parse_single_mut(mut_str: str) -> tuple[str, int, str]:
    """Parse single mutation string 'WT{position}MUT'"""
    if not mut_str or len(mut_str) < 3:
        raise ValueError(f"Invalid mutation format: {mut_str}")

    wt = mut_str[0]
    mut_aa = mut_str[-1]

    try:
        position = int(mut_str[1:-1])
    except ValueError as err:
        raise ValueError(
            f"Invalid mutation format: {mut_str}. Position must be numeric."
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


def predict_single(
    model: nn.Module,
    config: Any,
    pdb_path: str,
    mutations: Optional[list[str]] = None,
    chain: Optional[str] = None,
    threshold: float = -0.5,
) -> list[dict]:
    """Run single mutation predictions. If mutations is None, performs SSM scan using v2_ssm functions."""
    # Load PDB
    if chain is None:
        chains = get_chains(pdb_path)
        if not chains:
            raise ValueError("No chains found in PDB file")
        chain = chains[0]

    pdb_data = load_pdb(pdb_path, [chain] if chain else None)

    # Run SSM using v2_ssm function
    ddg, S = v2_run_single_ssm(pdb_data, config, model)

    # If mutations is None, perform SSM scan using v2_ssm format_output_single
    if mutations is None or len(mutations) == 0:
        # Use v2_ssm format_output_single function
        ddg_list, mut_list = format_output_single(ddg, S, threshold=threshold)

        # Convert to our response format
        results = []
        for mut_str, pred_ddg in zip(mut_list, ddg_list, strict=False):
            wt, position, mut_aa = parse_mutation(mut_str)
            results.append(
                {
                    "mutation": mut_str,
                    "position": position,
                    "wildtype": wt,
                    "mutation_aa": mut_aa,
                    "ddg": float(pred_ddg),
                }
            )
        return results

    # Format output for requested mutations
    # Use v2_ssm format_output_single with very high threshold to get all mutations
    # Then filter to requested ones
    ddg_list, mut_list = format_output_single(ddg, S, threshold=1000.0)

    # Create a lookup for requested mutations
    requested_mutations = set(mutations)
    results = []

    for mut_str, pred_ddg in zip(mut_list, ddg_list, strict=False):
        if mut_str in requested_mutations:
            wt, position, mut_aa = parse_mutation(mut_str)
            results.append(
                {
                    "mutation": mut_str,
                    "position": position,
                    "wildtype": wt,
                    "mutation_aa": mut_aa,
                    "ddg": float(pred_ddg),
                }
            )

    return results


def predict_additive(
    model: nn.Module,
    config: Any,
    pdb_path: str,
    mutations: Optional[list[str]] = None,
    chain: Optional[str] = None,
    distance: float = 5.0,
    threshold: float = -0.5,
) -> list[dict]:
    """Run additive double mutation predictions. If mutations is None, performs SSM scan using v2_ssm functions."""
    # Load PDB
    if chain is None:
        chains = get_chains(pdb_path)
        if not chains:
            raise ValueError("No chains found in PDB file")
        chain = chains[0]

    pdb_data = load_pdb(pdb_path, [chain] if chain else None)

    # Run single SSM first using v2_ssm function
    ddg, S = v2_run_single_ssm(pdb_data, config, model)

    # If mutations is None, perform SSM scan using v2_ssm format_output_double
    if mutations is None or len(mutations) == 0:
        # Use v2_ssm format_output_double function
        ddg_list, mut_list = format_output_double(
            ddg, S, threshold=threshold, pdb=pdb_data, distance=distance
        )

        # Get distance matrix for distance values
        dmat = get_dmat(pdb_data)

        # Convert to our response format
        results = []
        for mut_str, pred_ddg in zip(mut_list, ddg_list, strict=False):
            wt1, pos1, mut_aa1, wt2, pos2, mut_aa2 = parse_mutation(mut_str)
            pos1_idx = pos1 - 1
            pos2_idx = pos2 - 1
            ca_distance = float(dmat[pos1_idx, pos2_idx])

            results.append(
                {
                    "mutation": mut_str,
                    "position1": pos1,
                    "position2": pos2,
                    "wildtype1": wt1,
                    "wildtype2": wt2,
                    "mutation_aa1": mut_aa1,
                    "mutation_aa2": mut_aa2,
                    "ddg": float(pred_ddg),
                    "distance": ca_distance,
                }
            )
        return results

    # Format output for requested mutations
    # Use v2_ssm format_output_double with very high threshold to get all mutations
    # Then filter to requested ones
    ddg_list, mut_list = format_output_double(
        ddg, S, threshold=1000.0, pdb=pdb_data, distance=1000.0
    )

    # Get distance matrix for distance values
    dmat = get_dmat(pdb_data)

    # Create a lookup for requested mutations
    requested_mutations = set(mutations)
    results = []

    for mut_str, pred_ddg in zip(mut_list, ddg_list, strict=False):
        if mut_str in requested_mutations:
            wt1, pos1, mut_aa1, wt2, pos2, mut_aa2 = parse_mutation(mut_str)
            pos1_idx = pos1 - 1
            pos2_idx = pos2 - 1
            ca_distance = float(dmat[pos1_idx, pos2_idx])

            results.append(
                {
                    "mutation": mut_str,
                    "position1": pos1,
                    "position2": pos2,
                    "wildtype1": wt1,
                    "wildtype2": wt2,
                    "mutation_aa1": mut_aa1,
                    "mutation_aa2": mut_aa2,
                    "ddg": float(pred_ddg),
                    "distance": ca_distance,
                }
            )

    return results


def predict_epistatic(  # noqa: C901
    model: nn.Module,
    config: Any,
    pdb_path: str,
    mutations: Optional[list[str]] = None,
    chain: Optional[str] = None,
    distance: float = 5.0,
    threshold: float = -0.5,
    batch_size: int = 2048,
) -> list[dict]:
    """Run epistatic double mutation predictions. If mutations is None, performs SSM scan using v2_ssm functions."""
    # Load PDB
    if chain is None:
        chains = get_chains(pdb_path)
        if not chains:
            raise ValueError("No chains found in PDB file")
        chain = chains[0]

    pdb_data = load_pdb(pdb_path, [chain] if chain else None)

    # If mutations is None, perform SSM scan using v2_ssm run_epistatic_ssm
    if mutations is None or len(mutations) == 0:
        # Run epistatic SSM with distance and threshold (uses v2_ssm internally)
        ddg, mut_list = v2_run_epistatic_ssm(
            pdb_data, config, model, distance, threshold, batch_size
        )

        # Format output
        results = []
        ddg_list = ddg.tolist() if isinstance(ddg, torch.Tensor) else ddg
        dmat = get_dmat(pdb_data)

        for mut_str, pred_ddg in zip(mut_list, ddg_list, strict=False):
            wt1, pos1, mut_aa1, wt2, pos2, mut_aa2 = parse_mutation(mut_str)
            pos1_idx = pos1 - 1
            pos2_idx = pos2 - 1
            ca_distance = float(dmat[pos1_idx, pos2_idx])

            results.append(
                {
                    "mutation": mut_str,
                    "position1": pos1,
                    "position2": pos2,
                    "wildtype1": wt1,
                    "wildtype2": wt2,
                    "mutation_aa1": mut_aa1,
                    "mutation_aa2": mut_aa2,
                    "ddg": float(pred_ddg),
                    "distance": ca_distance,
                }
            )
        return results

    # Format output for requested mutations
    # Use v2_ssm run_epistatic_ssm with very high threshold/distance to get all mutations
    # Then filter to requested ones
    dmat = get_dmat(pdb_data)

    # Find max distance needed for requested mutations
    max_distance_needed = distance
    for mut_str in mutations:
        try:
            wt1, pos1, mut_aa1, wt2, pos2, mut_aa2 = parse_mutation(mut_str)
            pos1_idx = pos1 - 1
            pos2_idx = pos2 - 1
            if (
                pos1_idx >= 0
                and pos1_idx < dmat.shape[0]
                and pos2_idx >= 0
                and pos2_idx < dmat.shape[1]
            ):
                mut_distance = float(dmat[pos1_idx, pos2_idx])
                if mut_distance > max_distance_needed:
                    max_distance_needed = mut_distance
        except Exception as e:
            logger.warning(f"Skipping invalid mutation '{mut_str}': {e}")
            continue

    # Run with very permissive settings to ensure all requested mutations are included
    effective_distance = max(
        max_distance_needed + 1.0, 100.0
    )  # Add buffer, ensure it's large
    ddg, mut_list = run_epistatic_ssm(
        pdb_data,
        config,
        model,
        effective_distance,
        1000.0,
        batch_size,  # Very permissive threshold
    )

    # Create a lookup for requested mutations
    requested_mutations = set(mutations)
    results = []
    ddg_list = ddg.tolist() if isinstance(ddg, torch.Tensor) else ddg

    for mut_str, pred_ddg in zip(mut_list, ddg_list, strict=False):
        if mut_str in requested_mutations:
            wt1, pos1, mut_aa1, wt2, pos2, mut_aa2 = parse_mutation(mut_str)
            pos1_idx = pos1 - 1
            pos2_idx = pos2 - 1
            ca_distance = float(dmat[pos1_idx, pos2_idx])

            results.append(
                {
                    "mutation": mut_str,
                    "position1": pos1,
                    "position2": pos2,
                    "wildtype1": wt1,
                    "wildtype2": wt2,
                    "mutation_aa1": mut_aa1,
                    "mutation_aa2": mut_aa2,
                    "ddg": float(pred_ddg),
                    "distance": ca_distance,
                }
            )

    return results


def predict(
    model: nn.Module,
    config: Any,
    pdb_path: str,
    mutations: Optional[list[str]],
    mode: str,
    chain: Optional[str] = None,
    distance: float = 5.0,
    threshold: float = -0.5,
    batch_size: int = 2048,
) -> list[dict]:
    """
    Run ThermoMPNN-D prediction on a PDB with mutations.
    If mutations is None, performs a site-saturation mutagenesis (SSM) scan.

    Args:
        model: Loaded ThermoMPNN-D model
        config: Model configuration
        pdb_path: Path to PDB file
        mutations: Optional list of mutation strings. If None, performs SSM scan.
        mode: Prediction mode ('single', 'additive', or 'epistatic')
        chain: Chain ID to use (if None, uses first chain)
        distance: Distance threshold for double mutations
        threshold: ddG threshold for filtering
        batch_size: Batch size for epistatic mode

    Returns:
        List of prediction dictionaries
    """
    if mode == "single":
        return predict_single(model, config, pdb_path, mutations, chain, threshold)
    elif mode == "additive":
        return predict_additive(
            model, config, pdb_path, mutations, chain, distance, threshold
        )
    elif mode == "epistatic":
        return predict_epistatic(
            model, config, pdb_path, mutations, chain, distance, threshold, batch_size
        )
    else:
        raise ValueError(
            f"Invalid mode: {mode}. Must be 'single', 'additive', or 'epistatic'"
        )
