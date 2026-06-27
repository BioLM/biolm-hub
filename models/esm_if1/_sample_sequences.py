import io
from typing import Any, Optional, Union

import biotite  # type: ignore
import esm  # type: ignore
import numpy as np
import torch
from esm.inverse_folding.gvp_transformer import GVPTransformerModel  # type: ignore

from models.commons.core.logging import get_logger

logger = get_logger(__name__)

"""
These functions below are adapted from the original ESM Inverse Folding repo

https://github.com/facebookresearch/esm/blob/main/examples/inverse_folding/sample_sequences.py
- sample_seq_singlechain()
- sample_seq_multichain()

https://github.com/facebookresearch/esm/blob/main/esm/inverse_folding/util.py
- load_structure()
- get_encoder_output()
"""


def _sample_seq_singlechain(
    pdb_string: str,
    chain: str,
    num_samples: int,
    temperature: float,
    model: GVPTransformerModel,
    device: torch.device,
) -> list[dict[str, Any]]:
    coords, native_seq = _load_coords(pdb_string, chain)
    sampled_sequences = []
    for i in range(num_samples):
        logger.info("Sampling.. (%s of %s)", i + 1, num_samples)
        with torch.no_grad():
            sampled_seq = model.sample(coords, temperature=temperature, device=device)
        recovery = np.mean(
            [(a == b) for a, b in zip(native_seq, sampled_seq, strict=False)]
        )
        sampled_sequences.append(
            {
                "sequence": sampled_seq,
                "recovery": recovery,
            }
        )
    return sampled_sequences


def _sample_seq_multichain(
    pdb_string: str,
    chain: str,
    num_samples: int,
    temperature: float,
    model: GVPTransformerModel,
) -> list[dict[str, Any]]:
    """
    This currently results in a "RuntimeError: CUDA out of memory."
    """
    structure = _load_structure_from_string(pdb_string)
    (
        coords,
        native_seqs,
    ) = esm.inverse_folding.multichain_util.extract_coords_from_complex(structure)
    target_chain_id = chain
    native_seq = native_seqs[target_chain_id]
    logger.info("Native sequence loaded from structure file:")
    logger.debug("Native seq (first 32): %s", native_seq[:32])
    sampled_sequences = []
    for i in range(num_samples):
        logger.info("Sampling.. (%s of %s)", i + 1, num_samples)
        sampled_seq = esm.inverse_folding.multichain_util.sample_sequence_in_complex(
            model, coords, target_chain_id, temperature=temperature
        )
        recovery = np.mean(
            [(a == b) for a, b in zip(native_seq, sampled_seq, strict=False)]
        )
        sampled_sequences.append(
            {
                "sequence": sampled_seq,
                "recovery": recovery,
            }
        )
    return sampled_sequences


def _get_encoder_output(
    pdb_string: str,
    alphabet: esm.data.Alphabet,
    model: GVPTransformerModel,
    device: torch.device,
) -> torch.Tensor:
    coords, native_seq = _load_coords(pdb_string, chain=None)
    batch_converter = esm.inverse_folding.util.CoordBatchConverter(alphabet)
    batch = [(coords, None, None)]
    coords, confidence, strs, tokens, padding_mask = batch_converter(
        batch, device=device
    )
    encoder_out = model.encoder.forward(
        coords, padding_mask, confidence, return_all_hiddens=False
    )
    # remove beginning and end (bos and eos tokens)
    return encoder_out["encoder_out"][0][1:-1, 0]  # type: ignore


def _load_structure_from_string(
    pdb_string: str,
    file_format: str = "pdb",
    chain: Optional[Union[str, list[str]]] = None,
) -> biotite.structure.AtomArray:
    """
    Load a structure from a PDB or CIF string.

    Args:
        pdb_string: A string containing the entire PDB or CIF data.
        file_format: 'pdb' or 'cif' to specify the format of pdb_data.
        chain: The chain ID or list of chain IDs to load.

    Returns:
        An AtomArray containing the loaded structure.
    """
    pdb_file_object = io.StringIO(pdb_string)
    if file_format == "cif":
        pdbxf = biotite.structure.io.pdbx.PDBxFile.read(pdb_file_object)
        structure = biotite.structure.io.pdbx.get_structure(pdbxf, model=1)
    elif file_format == "pdb":
        pdbf = biotite.structure.io.pdb.PDBFile.read(pdb_file_object)
        structure = biotite.structure.io.pdb.get_structure(pdbf, model=1)
    else:
        raise ValueError("Invalid file format. Must be 'pdb' or 'cif'.")
    bbmask = biotite.structure.filter_backbone(structure)
    structure = structure[bbmask]
    all_chains = biotite.structure.get_chains(structure)
    if len(all_chains) == 0:
        raise ValueError("No chains found in the input data.")
    if chain is None:
        chain_ids = all_chains
    elif isinstance(chain, list):
        chain_ids = chain
    else:
        chain_ids = [chain]
    for chain in chain_ids:
        if chain not in all_chains:
            raise ValueError(f"Chain {chain} not found in input data")
    chain_filter = [a.chain_id in chain_ids for a in structure]
    structure = structure[chain_filter]
    return structure


def _load_coords(pdb_string: str, chain: Optional[str]) -> tuple[np.ndarray, str]:  # type: ignore
    """
    Args:
        fpath: filepath to either pdb or cif file
        chain: the chain id
    Returns:
        Tuple (coords, seq)
            - coords is an L x 3 x 3 array for N, CA, C coordinates
            - seq is the extracted sequence
    """
    structure = _load_structure_from_string(pdb_string, file_format="pdb", chain=chain)
    return esm.inverse_folding.util.extract_coords_from_structure(structure)  # type: ignore
