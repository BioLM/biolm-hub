# MPNN (ProteinMPNN / LigandMPNN)

> **One-line summary**: Message-passing neural network for inverse folding --- designs amino acid sequences that fold into a given protein backbone structure, with optional ligand and membrane awareness.

## Overview

MPNN implements the ProteinMPNN and LigandMPNN family of models developed by Justas Dauparas and David Baker's group at the University of Washington. ProteinMPNN (Science, 2022) is a graph neural network that solves the inverse folding problem: given a protein backbone structure, it designs amino acid sequences predicted to fold into that structure. It achieves dramatically higher experimental success rates (~70-100%) compared to prior methods like Rosetta fixed-backbone design (~15-30%).

LigandMPNN extends ProteinMPNN to handle non-protein atoms including small-molecule ligands, metal ions, nucleic acids, and non-standard residues. Additional specialized variants handle membrane proteins (global and per-residue transmembrane labels) and soluble protein optimization.

## Architecture

| Property | Value |
|----------|-------|
| Architecture | Message-passing GNN (encoder-decoder) |
| Hidden dimensions | 128 |
| Encoder layers | 3 |
| Decoder layers | 3 |
| Graph type | k-nearest neighbor on backbone CA atoms |
| Input | PDB-format backbone coordinates |
| Output | Amino acid sequences + confidence scores |
| Max sequence length | 1024 residues |

For detailed architecture specifications see [MODEL.md](MODEL.md).

## Model Variants

All variants share the same GNN architecture but use different checkpoint weights trained for specific contexts.

| Variant Slug | Checkpoint | Description | Use Case |
|-------------|------------|-------------|----------|
| `protein-mpnn` | `proteinmpnn_v_48_020.pt` | Standard ProteinMPNN | General protein design |
| `ligand-mpnn` | `ligandmpnn_v_32_010_25.pt` | Ligand-aware MPNN | Proteins with bound ligands, metals, DNA/RNA |
| `soluble-mpnn` | `solublempnn_v_48_020.pt` | Solubility-optimized | Designing soluble proteins |
| `global-label-membrane-mpnn` | `global_label_membrane_mpnn_v_48_020.pt` | Global membrane label | Membrane protein design (whole-protein label) |
| `per-residue-label-membrane-mpnn` | `per_residue_label_membrane_mpnn_v_48_020.pt` | Per-residue membrane labels | Membrane protein design (fine-grained) |
| `hyper-mpnn` | `v48_020_epoch300_hyper.pt` | HyperMPNN retrained variant | Improved thermostability (retrained on hyperthermophiles) |

All variants run on CPU (no GPU required) with 3 GB memory.

## Capabilities & Limitations

**CAN be used for:**
- Designing amino acid sequences for a given protein backbone structure (inverse folding)
- Multi-chain complex design with selective chain redesign
- Ligand-aware design accounting for bound small molecules, metals, cofactors, nucleic acids (LigandMPNN)
- Membrane protein design with transmembrane-aware constraints
- Constrained design with fixed residues, redesigned residues, and amino acid biases
- Symmetric/homo-oligomer design with linked positions
- Side-chain packing to generate all-atom models from designed sequences
- Batch sampling of multiple diverse sequences per backbone

**CANNOT be used for:**
- Backbone structure generation or remodeling (use RFdiffusion or Chroma for that)
- Sequences longer than 1024 residues
- Predicting protein structure from sequence (use AlphaFold2, ESMFold, or Chai-1)
- Directly predicting or optimizing catalytic activity
- Handling non-PDB input formats (requires valid PDB string)

**Other considerations:**
- Output is stochastic by default; provide a `seed` parameter for reproducible results
- Lower temperature (e.g., 0.1) produces more conservative designs; higher temperature (e.g., 0.5-1.0) produces more diverse designs
- Confidence scores indicate structural compatibility, not guaranteed foldability
- Side-chain packing is optional and approximate; consider downstream refinement for high-accuracy applications

## Actions / Endpoints

### `generate`

Designs amino acid sequences for a given protein backbone structure. Supports constrained design, amino acid biases, symmetry, and side-chain packing.

**Request Schema**: `MPNNGenerateRequest`

**Top-Level Structure:**

| Field | Type | Description |
|-------|------|-------------|
| `params` | `AllMPNNGenerateParams` | Generation parameters (see below) |
| `items` | `list[MPNNGenerateRequestItem]` | List containing exactly 1 PDB structure |

**Item Fields:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `pdb` | `str` | Yes | PDB-format string of the protein structure |

**Common Parameters (all variants):**

| Parameter | Type | Default | Range | Description |
|-----------|------|---------|-------|-------------|
| `seed` | `int` or `null` | `null` | Any integer | Random seed for reproducibility; null = time-based |
| `temperature` | `float` | `0.1` | >0 | Sampling temperature; lower = more conservative |
| `batch_size` | `int` | `1` | 1-1000 | Number of sequences per batch |
| `number_of_batches` | `int` | `1` | 1-48 | Number of batches to sample |
| `fixed_residues` | `list[str]` | `[]` | e.g., `["A10", "A15"]` | Residues to keep fixed (not redesigned) |
| `redesigned_residues` | `list[str]` | `[]` | e.g., `["A10", "A15"]` | Only these residues will be redesigned (all others fixed) |
| `chains_to_design` | `list[str]` | `[]` | e.g., `["A", "B"]` | Which chains to design; empty = all chains |
| `parse_these_chains_only` | `list[str]` | `[]` | e.g., `["A"]` | Only parse these chains from PDB |
| `bias_AA` | `dict[str, float]` | `{}` | e.g., `{"A": 1.5, "G": -0.5}` | Global amino acid biases (positive = favor, negative = disfavor) |
| `bias_AA_per_residue` | `dict[str, dict[str, float]]` | `{}` | e.g., `{"A10": {"W": 2.0}}` | Per-residue amino acid biases |
| `omit_AA` | `str` | `""` | e.g., `"CM"` | Globally omit these amino acids from designs |
| `omit_AA_per_residue` | `dict[str, str]` | `{}` | e.g., `{"A10": "CP"}` | Per-residue amino acid omissions |
| `symmetry_residues` | `list[list[str]]` | `[]` | e.g., `[["A10", "B10"]]` | Groups of residues that must have the same identity |
| `symmetry_weights` | `list[list[float]]` | `[]` | e.g., `[[0.5, 0.5]]` | Weights for symmetry groups (must match symmetry_residues) |
| `homo_oligomer` | `bool` | `false` | | Automatically link equivalent positions across chains |
| `parse_atoms_with_zero_occupancy` | `bool` | `false` | | Include zero-occupancy atoms from PDB |

**Side-Chain Packing Parameters:**

| Parameter | Type | Default | Range | Description |
|-----------|------|---------|-------|-------------|
| `pack_side_chains` | `bool` | `false` | | Enable side-chain packing for all-atom output |
| `repack_everything` | `bool` | `false` | | Repack all side chains, not just designed positions |
| `number_of_packs_per_design` | `int` | `1` | 1-8 | Number of side-chain packing attempts per design |
| `sc_num_samples` | `int` | `16` | 1-64 | Number of samples for side-chain packer |
| `sc_num_denoising_steps` | `int` | `3` | 1-10 | Denoising steps for side-chain packer |
| `force_hetatm` | `bool` | `false` | | Force HETATM records in packed output |
| `pack_with_ligand_context` | `bool` | `true` | | Include ligand context during packing |

**LigandMPNN-Specific Parameters** (variant `ligand`):

| Parameter | Type | Default | Range | Description |
|-----------|------|---------|-------|-------------|
| `ligand_mpnn_use_atom_context` | `bool` | `true` | - | Use non-protein atom context |
| `ligand_mpnn_cutoff_for_score` | `float` | `8.0` | - | Distance cutoff (Angstroms) for ligand scoring |

**Global Membrane MPNN-Specific Parameters** (variant `global_label_membrane`):

| Parameter | Type | Default | Range | Description |
|-----------|------|---------|-------|-------------|
| `global_transmembrane_label` | `"membrane"` or `"soluble"` | `"soluble"` | - | Whole-protein membrane context label |

**Per-Residue Membrane MPNN-Specific Parameters** (variant `per_residue_label_membrane`):

| Parameter | Type | Default | Range | Description |
|-----------|------|---------|-------|-------------|
| `transmembrane_buried` | `list[str]` or `null` | `null` | - | Residues buried in the membrane |
| `transmembrane_interface` | `list[str]` or `null` | `null` | - | Residues at the membrane-water interface |

**Response Schema**: `MPNNGenerateResponse`

```json
{
  "results": [
    {
      "sequence": "MKLLVFGA...:EQWRTV...",
      "pdb": "ATOM      1  N   MET A   1 ...",
      "overall_confidence": 0.8234,
      "ligand_confidence": 0.7891,
      "seq_rec": 0.4523,
      "log_probs": [[...], ...],
      "sampling_probs": [[...], ...]
    }
  ]
}
```

When `pack_side_chains` is enabled, each result also includes:

```json
{
  "pdb_packed": {
    "packed_1": "ATOM      1  N   MET A   1 ...",
    "packed_2": "..."
  }
}
```

**Response Fields:**

| Field | Type | Description |
|-------|------|-------------|
| `sequence` | `str` | Designed amino acid sequence (chains separated by `:`) |
| `pdb` | `str` | PDB string with designed sequence mapped onto backbone |
| `overall_confidence` | `float` | Overall design confidence (exp of negative loss; higher = better) |
| `ligand_confidence` | `float` | Confidence near ligand atoms (relevant for LigandMPNN) |
| `seq_rec` | `float` | Sequence recovery vs native sequence (0-1) |
| `log_probs` | `list[list[float]]` | Per-residue log probabilities over 21 amino acid types |
| `sampling_probs` | `list[list[float]]` | Per-residue sampling probabilities |
| `pdb_packed` | `dict[str, str]` | (Optional) Packed all-atom PDB strings keyed by pack index |

## Usage Examples

```python
from models.mpnn.schema import (
    MPNNGenerateRequest,
    AllMPNNGenerateParams,
    MPNNGenerateRequestItem,
)

# Basic sequence design
request = MPNNGenerateRequest(
    params=AllMPNNGenerateParams(
        temperature=0.1,
        batch_size=4,
        number_of_batches=1,
        seed=42,
    ),
    items=[
        MPNNGenerateRequestItem(pdb=pdb_string),
    ],
)

# Constrained design: fix active-site residues, redesign rest of chain A
request = MPNNGenerateRequest(
    params=AllMPNNGenerateParams(
        temperature=0.2,
        batch_size=8,
        number_of_batches=2,
        fixed_residues=["A45", "A72", "A103"],  # Catalytic triad
        chains_to_design=["A"],
    ),
    items=[
        MPNNGenerateRequestItem(pdb=pdb_string),
    ],
)

# Homo-oligomer design
request = MPNNGenerateRequest(
    params=AllMPNNGenerateParams(
        temperature=0.1,
        homo_oligomer=True,
        batch_size=4,
    ),
    items=[
        MPNNGenerateRequestItem(pdb=homo_trimer_pdb_string),
    ],
)
```

## Performance & Benchmarks

### Published Results

From Dauparas et al. (Science, 2022):

| Model | Sequence Recovery ↑ | Experimental Success Rate ↑ | Dataset |
|-------|---------------------|---------------------------|---------|
| **ProteinMPNN** | **~52%** | **~70-100%** | 8 diverse topologies |
| Rosetta | ~33% | ~15-30% | Same test set |

### SOTA Status

ProteinMPNN remains the most widely used and experimentally validated inverse folding method as of 2025. LigandMPNN extends this to ligand-aware design with demonstrated atomically accurate antibody design (Dauparas et al. 2024).

## Implementation Verification

### Verification Method

The BioLM implementation wraps the official LigandMPNN repository (commit `091ab1ff`) directly, cloning it into the container image. The `util.py` wrapper adapts the original `load_mpnn` and `infer` functions for the BioLM API pattern. This approach minimizes divergence from the reference implementation.

### Test Cases

Integration tests validate all 6 active variants (protein, ligand, soluble, global_label_membrane, per_residue_label_membrane, hyper) against 4 input fixtures. Tests verify response structure (presence of `results` key, non-empty results list) via a custom validator.

### Verification Status

**Status: VERIFIED** --- All variants pass integration tests. Output format and structure match expected response schemas.

## Resource Requirements

| Resource | Value |
|----------|-------|
| GPU | None (CPU-only) |
| Memory | 3 GB |
| CPU | 1 core |
| Cold start | Fast (memory snapshot enabled) |
| Max batch size | 1000 sequences per batch |
| Max batches | 48 per request |
| Max items | 1 PDB per request |

## Implementation Notes

- **Memory snapshots**: Uses `@modal.enter(snap=True)` to load the model on CPU into a memory snapshot, then `@modal.enter(snap=False)` to place it on the compute device (CPU for this model) on restore, for faster cold starts
- **External code**: Clones the official LigandMPNN repository (`github.com/dauparas/LigandMPNN`) at a pinned commit into the container
- **Custom util.py**: A modified `util.py` replaces the repository's version, adapting `load_mpnn` and `infer` for API use
- **Side-chain model**: The side-chain packer checkpoint (`ligandmpnn_sc_v_32_002_16.pt`) is always loaded alongside the primary model
- **HyperMPNN download**: Uses R2 primary with GitHub fallback for the HyperMPNN checkpoint
- **Variant dispatch**: Model type is determined at container startup via `MODEL_TYPE` environment variable; parameter validation uses variant-specific schemas
- **Temporary files**: PDB inputs are written to `/tmp_pdbs/` and output files to `/tmp_out/` during inference, cleaned up after each request

## Confidence Metrics

| Metric | Range | Interpretation |
|--------|-------|----------------|
| `overall_confidence` | 0-1 | Exp of negative cross-entropy loss over designed positions; higher = more structurally compatible |
| `ligand_confidence` | 0-1 | Same metric but weighted by proximity to ligand atoms; most relevant for LigandMPNN variant |
| `seq_rec` | 0-1 | Fraction of designed positions matching the native sequence; useful as a sanity check |

## Technical Glossary

**Inverse folding**: The computational problem of finding amino acid sequences compatible with a given backbone structure. The "inverse" of protein folding (sequence to structure).

**Decoding order**: The random permutation in which residues are generated during autoregressive sampling. Randomizing this order, combined with noise injection, prevents the model from copying spatial neighbors.

**Temperature**: Softmax temperature for amino acid sampling. `T=0.1` is near-greedy (picks highest-probability amino acid); `T=1.0` samples proportionally from the predicted distribution.

**Sequence recovery**: The fraction of positions where the designed sequence matches the original/native sequence. Typical ProteinMPNN recovery is ~52%, which is substantially higher than random (~5%) and higher than Rosetta (~33%).

**Chain mask**: Binary mask indicating which residues should be redesigned (1) vs. held fixed (0). Constructed from `chains_to_design`, `fixed_residues`, and `redesigned_residues` parameters.

## License

- **Code**: MIT ([LICENSE](https://github.com/dauparas/LigandMPNN/blob/main/LICENSE))
- **Weights**: Distributed with the code under MIT license

## References & Citations

### Papers

1. Dauparas J, Anishchenko I, Bennett N, Bai H, Baker D, et al. "Robust deep learning-based protein sequence design using ProteinMPNN." *Science* (2022). [DOI](https://doi.org/10.1126/science.add2187)

2. Dauparas J, Baker D, et al. "Atomically accurate de novo design of single-domain antibodies." *bioRxiv* (2024). [DOI](https://doi.org/10.1101/2024.03.14.585103)

### BibTeX

```bibtex
@article{dauparas2022robust,
  title={Robust deep learning-based protein sequence design using ProteinMPNN},
  author={Dauparas, Justas and Anishchenko, Ivan and Bennett, Nathaniel and Bai, Hua and Ragotte, Robert J and Milles, Lukas F and Wicky, Basile IM and Courbet, Alexis and de Haas, Rob J and Bethel, Neville and others},
  journal={Science},
  volume={378},
  number={6615},
  pages={49--56},
  year={2022},
  publisher={American Association for the Advancement of Science},
  doi={10.1126/science.add2187}
}
```

### Links

- **Paper**: [Science (2022)](https://doi.org/10.1126/science.add2187)
- **Code**: [github.com/dauparas/LigandMPNN](https://github.com/dauparas/LigandMPNN)
- **HyperMPNN**: [github.com/meilerlab/HyperMPNN](https://github.com/meilerlab/HyperMPNN)

---

*See also: [MODEL.md](MODEL.md) for technical deep-dive | [BIOLOGY.md](BIOLOGY.md) for biological context*
