# ThermoMPNN

> **One-line summary**: Structure-based prediction of protein thermal stability changes (ddG) for single-point mutations, using transfer learning from ProteinMPNN.

## Overview

ThermoMPNN is a graph neural network developed by Dieckhaus et al. (2023) at the Kuhlman Lab that predicts changes in protein thermostability (ddG in kcal/mol) upon single amino acid substitutions. It leverages transfer learning from ProteinMPNN -- a protein sequence design model -- by fine-tuning its structural representations for stability prediction. The model takes a PDB structure as input and supports both targeted mutation predictions and full site-saturation mutagenesis (SSM) scans.

## Architecture

| Property | Value |
|----------|-------|
| Architecture | Message-passing neural network (GNN) |
| Base model | ProteinMPNN (v_48_020) |
| Prediction head | 2 dense layers ([64, 32]) with light attention |
| Input | PDB structure + mutations |
| Output | ddG in kcal/mol |
| Max sequence length | 1024 residues |
| Batch size | 1 PDB per request |

## Model Variants

Single variant -- no size options.

## Capabilities & Limitations

**CAN be used for:**
- Predicting ddG for specific single-point mutations given a PDB structure
- Running complete site-saturation mutagenesis (SSM) scans over all positions
- Identifying stabilizing mutations for protein engineering
- Evaluating the stability impact of disease-associated mutations

**CANNOT be used for:**
- Sequence-only prediction (requires PDB structure input)
- Double or multi-point mutations (use ThermoMPNN-D instead)
- Proteins longer than 1024 residues
- Membrane protein stability in lipid bilayer context

**Other considerations:**
- Mutations use 1-indexed positions within the selected chain's modeled sequence (not PDB residue numbers) in format `WT{position}MUT` (e.g., `A100V` means the 100th residue in the parsed chain sequence)
- When `mutations` is `null`, a full SSM scan is performed (20 substitutions x N positions)
- Chain ID can be specified; defaults to first chain if not provided

## Actions / Endpoints

### `predict`

Predict ddG for single-point mutations or perform SSM scan.

**Request Parameters:**

| Parameter | Type | Default | Range | Description |
|-----------|------|---------|-------|-------------|
| `params.chain` | str | null | Any valid chain ID | Chain to analyze; defaults to first chain |
| `items[].pdb` | str | Required | Valid PDB format | PDB structure string |
| `items[].mutations` | list[str] | null | `WT{pos}MUT` format | Mutations to evaluate; null triggers SSM scan |

**Response:**

```json
{
  "results": [
    {
      "mutation": "A100V",
      "position": 100,
      "wildtype": "A",
      "mutation_aa": "V",
      "ddg": -0.45
    }
  ]
}
```

## Usage Examples

```python
from models.thermompnn.schema import (
    ThermoMPNNPredictParams,
    ThermoMPNNPredictRequest,
    ThermoMPNNPredictRequestItem,
)

# Predict ddG for specific mutations
request = ThermoMPNNPredictRequest(
    params=ThermoMPNNPredictParams(chain="A"),
    items=[
        ThermoMPNNPredictRequestItem(
            pdb=pdb_string,
            mutations=["M1V", "V2A", "L3I"],
        )
    ],
)

# Full SSM scan (mutations=None)
ssm_request = ThermoMPNNPredictRequest(
    params=ThermoMPNNPredictParams(chain="A"),
    items=[
        ThermoMPNNPredictRequestItem(
            pdb=pdb_string,
            mutations=None,
        )
    ],
)
```

## Performance & Benchmarks

### Published Results

From Dieckhaus et al. (2023): ThermoMPNN achieves Spearman correlation of 0.725 on the Megascale test set (272,712 mutations, 298 proteins) and 0.657 on the Fireprot test set (3,438 mutations, 100 proteins). On the symmetrical SSYM benchmark, ThermoMPNN achieves Pearson correlation of 0.72 (direct) and 0.60 (inverse mutations). On S669, Pearson correlation is 0.43. ThermoMPNN outperformed Rosetta, RaSP, and PROSTATA on both internal datasets.

### SOTA Status

ThermoMPNN demonstrates that transfer learning from protein design models (ProteinMPNN) significantly improves stability prediction compared to training from scratch (Dieckhaus et al., 2023).

## Implementation Verification

### Verification Method

Structural validation (Option B). Tests verify response format, presence of required fields (mutation, position, wildtype, mutation_aa, ddg), and that ddG values are numeric. Four test cases cover single mutations, multiple mutations, chain specification, and SSM scan.

### Test Cases

| Test | Description |
|------|-------------|
| Input 1 | Two specific mutations (M1V, V2A), auto chain |
| Input 2 | Two specific mutations (L3I, M1L), chain A |
| Input 3 | Single mutation (V2F), chain A |
| Input 4 | SSM scan (no mutations), chain A |

### Verification Status

**Status: VERIFIED** -- All 4 test cases pass structural validation.

## Resource Requirements

| Resource | Value |
|----------|-------|
| GPU | T4 |
| Memory | 8 GB |
| CPU | 2 cores |
| Cold start | Memory snapshot enabled |
| Dependencies | None (self-contained; ThermoMPNN repo cloned into image) |

## Implementation Notes

- Uses Modal memory snapshots: model loaded on CPU during snap (`@modal.enter(snap=True)`), then transferred to GPU (`@modal.enter(snap=False)`)
- ThermoMPNN repository is cloned at image build time (`git checkout` pinned to commit `11a1c5b`)
- PDB files are written to temporary directories per request to avoid race conditions, and cleaned up after prediction
- Mutation positions are 1-indexed within the selected chain's modeled sequence (not PDB residue numbers) and converted to 0-indexed internally for the model
- The ProteinMPNN backbone weights are frozen; only the prediction head is trained
- PyTorch Lightning checkpoint loading is used with `TransferModelPL.load_from_checkpoint`

## License

- **Code**: MIT ([GitHub](https://github.com/Kuhlman-Lab/ThermoMPNN/blob/main/LICENSE))

## References & Citations

### Papers

1. Dieckhaus H, Brocidiacono M, Randolph N, Kuhlman B. "Transfer learning to leverage larger datasets for improved prediction of protein stability changes." *bioRxiv* (2023). [DOI](https://doi.org/10.1101/2023.07.27.550881)

### BibTeX

```bibtex
@article{dieckhaus2023thermompnn,
  title={Transfer learning to leverage larger datasets for improved prediction of protein stability changes},
  author={Dieckhaus, Henry and Brocidiacono, Michael and Randolph, Nicholas and Kuhlman, Brian},
  journal={bioRxiv},
  year={2023},
  doi={10.1101/2023.07.27.550881}
}
```

### Links

- **Paper**: [bioRxiv 2023.07.27.550881](https://doi.org/10.1101/2023.07.27.550881)
- **Code**: [GitHub Kuhlman-Lab/ThermoMPNN](https://github.com/Kuhlman-Lab/ThermoMPNN)

---

*See also: [MODEL.md](MODEL.md) for technical deep-dive | [BIOLOGY.md](BIOLOGY.md) for biological context*
