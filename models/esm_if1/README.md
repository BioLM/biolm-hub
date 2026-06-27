# ESM-IF1 Inverse Fold

> **One-line summary**: General-purpose protein inverse folding model that generates amino acid sequences compatible with a given 3D backbone structure, using a GVP-Transformer architecture trained on 12M predicted structures.

## Overview

ESM-IF1 (ESM Inverse Folding 1) is a protein inverse folding model from Meta AI (Hsu et al. 2022). Given a protein backbone structure in PDB format, it autoregressively samples amino acid sequences that are predicted to fold into that structure. The model uses a GVP-Transformer encoder to process backbone coordinates and a 16-layer Transformer decoder to generate sequences. A key innovation is training on 12 million AlphaFold2-predicted structures in addition to experimental structures from CATH, which significantly improves sequence recovery.

## Architecture

| Property | Value |
|----------|-------|
| Architecture | GVP-Transformer (GNN encoder + autoregressive decoder) |
| Model identifier | `esm_if1_gvp4_t16_142M_UR50` |
| Parameters | 142M |
| Encoder | GVP-Transformer with 4 GVP layers |
| Decoder | 16-layer autoregressive Transformer |
| Training data | CATH 4.3 + 12M AlphaFold2 predicted structures |
| Input | PDB backbone coordinates (N, CA, C) |
| Output | Sampled amino acid sequences with recovery rates |

## Model Variants

Single variant -- no size options. The model slug is `esm-if1`.

## Capabilities & Limitations

**CAN be used for:**
- Generating amino acid sequences compatible with a given protein backbone structure
- Sampling multiple diverse sequences from a single structure (up to 3 per request)
- Controlling sequence diversity via temperature parameter (0.0--8.0)
- Computing sequence recovery rate (fraction matching native sequence)
- Working with any single-chain protein structure

**CANNOT be used for:**
- Multichain protein complexes (not yet implemented)
- Sequence-only inputs (requires 3D structure in PDB format)
- Structure prediction (inverse direction -- use ESMFold or Boltz)
- Antibody-specific design (use AntiFold for better CDR recovery)
- Deterministic output without explicit seed (stochastic by default)

## Actions / Endpoints

### `generate`

Sample amino acid sequences compatible with a given backbone structure.

**Request Parameters:**

| Parameter | Type | Default | Range | Description |
|-----------|------|---------|-------|-------------|
| `params.chain` | str | "A" | Single character | PDB chain ID to redesign |
| `params.num_samples` | int | 1 | 1--3 | Number of sequences to sample |
| `params.temperature` | float | 0.6 | 0.0--8.0 | Sampling temperature (higher = more diverse) |
| `params.multichain_backbone` | bool | false | true/false | Multichain mode (not yet supported) |
| `params.seed` | int | None | Any int or null | Random seed for reproducibility |
| `items` | list[ESMIF1GenerateRequestItem] | (required) | Exactly 1 item | PDB structure input |
| `items[].pdb` | str | (required) | Valid PDB string | PDB structure content |

**Response:**

```json
{
  "results": [
    [
      {
        "sequence": "MKFLILLFNILCSGFHYAEGEFMTGAKEITPL...",
        "recovery": 0.42
      },
      {
        "sequence": "MKVLILLFNILCRGFHYAEGEFMTGAQEITPL...",
        "recovery": 0.38
      }
    ]
  ]
}
```

- `results`: Nested list -- one inner list per input PDB, each containing `num_samples` sampled sequences
- `sequence`: Generated amino acid sequence
- `recovery`: Fraction of positions matching the native sequence (0.0--1.0)

## Usage Examples

### Generate sequences from a protein structure

```python
from models.esm_if1.schema import (
    ESMIF1GenerateRequest,
    ESMIF1GenerateParams,
    ESMIF1GenerateRequestItem,
)

request = ESMIF1GenerateRequest(
    params=ESMIF1GenerateParams(
        chain="A",
        num_samples=3,
        temperature=0.6,
        seed=42,
    ),
    items=[
        ESMIF1GenerateRequestItem(pdb=pdb_string),
    ],
)
```

### Generate with higher diversity

```python
from models.esm_if1.schema import (
    ESMIF1GenerateRequest,
    ESMIF1GenerateParams,
    ESMIF1GenerateRequestItem,
)

request = ESMIF1GenerateRequest(
    params=ESMIF1GenerateParams(
        chain="A",
        num_samples=3,
        temperature=1.0,  # Higher temperature for more diversity
    ),
    items=[
        ESMIF1GenerateRequestItem(pdb=pdb_string),
    ],
)
```

## Performance & Benchmarks

### Published Results

From Hsu et al., *ICML* (2022):

| Model | Sequence Recovery (%) ↑ | Training Data |
|-------|------------------------|---------------|
| **ESM-IF1** | **51.0** | CATH + 12M AF2 structures |
| GVP | 39.4 | CATH experimental only |
| StructGNN | 35.0 | CATH experimental only |
| GraphTrans | 34.8 | CATH experimental only |

### SOTA Status

ESM-IF1 was state-of-the-art for inverse folding at time of publication (2022). ProteinMPNN achieves slightly higher recovery (~52%) on experimental structures but uses a different architecture without language model pre-training.

## Implementation Verification

### Verification Method

Option C -- Functional Validation: since sequence generation is stochastic, verification confirms that generated sequences are valid amino acid strings with reasonable recovery rates.

### Test Cases

| Input | Action | Tolerance | Status |
|-------|--------|-----------|--------|
| Standard PDB structure | generate | rel_tol 0.5, is_generated_seq=True | PASS |

### Verification Status

**Status: VERIFIED** -- Generated sequences are valid with expected recovery characteristics.

## Resource Requirements

| Resource | Value |
|----------|-------|
| GPU | T4 |
| Memory | 16 GB |
| CPU | 4.0 cores |
| Batch size | 1 (one PDB per request) |
| Max samples | 3 per request |
| Memory snapshot | Enabled (GPU snapshot) |

## Implementation Notes

- **Memory snapshots**: Uses `@modal.enter(snap=True)` with GPU memory snapshot enabled. The model is loaded directly on GPU during snapshot creation.
- **Container image**: Based on `pytorch/pytorch:2.0.1-cuda11.7-cudnn8-runtime` with `fair-esm` installed from GitHub commit `2b369911`, plus OpenFold and its dependencies.
- **Model loading**: Uses `esm.pretrained.esm_if1_gvp4_t16_142M_UR50()` which loads the model and alphabet. Model weights are stored in R2 under the `checkpoints` subdirectory.
- **CUDA OOM handling**: If a structure causes CUDA out-of-memory during generation, the error is caught, an empty result is returned for that structure, and the GPU cache is cleared.
- **Seeding**: When no seed is provided, uses `int(time.time_ns() % (2**32))` for time-based entropy. When a seed is provided, it is applied to Python random, NumPy, Torch, and CUDA before sampling.
- **Dependencies**: `torch==2.0.1`, `biotite==0.39.0`, `torch_geometric==2.4.0`, `torch_scatter==2.1.2`, OpenFold (from GitHub), `scipy==1.11.4`.

## License

- **License**: MIT ([GitHub](https://github.com/facebookresearch/esm/blob/main/LICENSE))

## References & Citations

### Papers

1. Hsu C, Verkuil R, Liu J, Lin Z, Hie B, Sercu T, Lerer A, Rives A. "Learning inverse folding from millions of predicted structures." *ICML* (2022). [arXiv: 2208.01304](https://arxiv.org/abs/2208.01304). [DOI: 10.1101/2022.04.10.487779](https://doi.org/10.1101/2022.04.10.487779)

### BibTeX

```bibtex
@inproceedings{hsu2022learning,
  title={Learning inverse folding from millions of predicted structures},
  author={Hsu, Chloe and Verkuil, Robert and Liu, Jason and Lin, Zeming and Hie, Brian and Sercu, Tom and Lerer, Adam and Rives, Alexander},
  booktitle={International Conference on Machine Learning},
  year={2022}
}
```

### Links

- **Paper**: [arXiv:2208.01304](https://arxiv.org/abs/2208.01304)
- **Code**: [GitHub facebookresearch/esm](https://github.com/facebookresearch/esm)

---

*See also: [MODEL.md](MODEL.md) for technical deep-dive | [BIOLOGY.md](BIOLOGY.md) for biological context*
