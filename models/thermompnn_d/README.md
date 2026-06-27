# ThermoMPNN-D

> **One-line summary**: Structure-based prediction of protein stability changes (ddG) for single and double mutations, with epistatic interaction modeling via transfer learning from ProteinMPNN.

## Overview

ThermoMPNN-D is a graph neural network developed by Dieckhaus and Kuhlman (2024) that predicts changes in protein thermostability (ddG in kcal/mol) for both single and double mutations. It extends ThermoMPNN by adding explicit modeling of epistatic (non-additive) interactions between paired mutation sites. The model supports three modes: single mutation prediction, additive double mutation estimation, and full epistatic double mutation prediction with distance-based filtering.

## Architecture

| Property | Value |
|----------|-------|
| Architecture | Message-passing neural network (GNN) with epistatic module |
| Base model | ProteinMPNN (v_48_020) |
| Models loaded | 2 (single + epistatic) |
| Input | PDB structure + mutations |
| Output | ddG in kcal/mol (+ CA-CA distance for doubles) |
| Max sequence length | 1024 residues |
| Batch size | 1 PDB per request |

## Model Variants

Single variant -- no size options. Internally loads both single and epistatic model checkpoints.

## Capabilities & Limitations

**CAN be used for:**
- Single mutation ddG prediction given a PDB structure
- Additive double mutation ddG estimation (sum of individual effects)
- Epistatic double mutation ddG prediction (non-additive interactions)
- Full SSM scans in all three modes
- Distance-based filtering of double mutation pairs
- Threshold-based filtering of results by ddG value

**CANNOT be used for:**
- Sequence-only prediction (requires PDB structure input)
- Triple or higher-order mutations
- Proteins longer than 1024 residues
- Membrane protein stability in lipid bilayer context

**Other considerations:**
- Single mutations: format `WT{position}MUT` (e.g., `A100V`)
- Double mutations: format `WT1{pos1}MUT1:WT2{pos2}MUT2` (e.g., `A100V:B200L`)
- When `mutations` is `null`, a full SSM scan is performed in the selected mode
- Distance threshold (default 5.0 A) filters double mutations by CA-CA distance
- ddG threshold (default -0.5 kcal/mol) filters results; set to high value (100) to return all

## Actions / Endpoints

### `predict`

Predict ddG for single or double mutations, or perform SSM scan.

**Request Parameters:**

| Parameter | Type | Default | Range | Description |
|-----------|------|---------|-------|-------------|
| `params.mode` | str | `single` | `single`, `additive`, `epistatic` | Prediction mode |
| `params.chain` | str | null | Any valid chain ID | Chain to analyze; defaults to first chain |
| `params.distance` | float | 5.0 | >= 0.0 | CA-CA distance threshold (Angstroms) for double mutations |
| `params.threshold` | float | -0.5 | any float | ddG threshold (kcal/mol); only results <= threshold returned |
| `items[].pdb` | str | Required | Valid PDB format | PDB structure string |
| `items[].mutations` | list[str] | null | See format above | Mutations to evaluate; null triggers SSM scan |

**Response (single mode):**

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

**Response (additive/epistatic mode):**

```json
{
  "results": [
    {
      "mutation": "A100V:B200L",
      "position1": 100,
      "position2": 200,
      "wildtype1": "A",
      "wildtype2": "B",
      "mutation_aa1": "V",
      "mutation_aa2": "L",
      "ddg": -0.92,
      "distance": 4.3
    }
  ]
}
```

## Usage Examples

```python
from models.thermompnn_d.schema import (
    ThermoMPNNDMode,
    ThermoMPNNDPredictParams,
    ThermoMPNNDPredictRequest,
    ThermoMPNNDPredictRequestItem,
)

# Single mutation prediction
single_request = ThermoMPNNDPredictRequest(
    params=ThermoMPNNDPredictParams(
        mode=ThermoMPNNDMode.SINGLE,
        chain="A",
    ),
    items=[
        ThermoMPNNDPredictRequestItem(
            pdb=pdb_string,
            mutations=["M1V", "V2A"],
        )
    ],
)

# Epistatic double mutation prediction
epistatic_request = ThermoMPNNDPredictRequest(
    params=ThermoMPNNDPredictParams(
        mode=ThermoMPNNDMode.EPISTATIC,
        chain="A",
        distance=5.0,
        threshold=-0.5,
    ),
    items=[
        ThermoMPNNDPredictRequestItem(
            pdb=pdb_string,
            mutations=["M1V:V2A"],
        )
    ],
)

# Full SSM scan in epistatic mode
ssm_request = ThermoMPNNDPredictRequest(
    params=ThermoMPNNDPredictParams(
        mode=ThermoMPNNDMode.EPISTATIC,
        chain="A",
        distance=5.0,
        threshold=100.0,  # Return all mutations
    ),
    items=[
        ThermoMPNNDPredictRequestItem(
            pdb=pdb_string,
            mutations=None,
        )
    ],
)
```

## Performance & Benchmarks

### Published Results

<!-- TODO: Extract benchmark results from Dieckhaus & Kuhlman (2024) bioRxiv 2024.10.10.617658 -- requires PDF access -->

### SOTA Status

ThermoMPNN-D extends ThermoMPNN with double mutation and epistasis support (Dieckhaus & Kuhlman, 2024).

## Implementation Verification

### Verification Method

Structural validation (Option B). Tests verify response format with mode-specific field checks: single mutations require `position`, `wildtype`, `mutation_aa`; double mutations require `position1`, `position2`, `wildtype1`, `wildtype2`, `mutation_aa1`, `mutation_aa2`.

### Test Cases

| Test | Mode | Description |
|------|------|-------------|
| Input 1 | Single | Two targeted single mutations |
| Input 2 | Additive | One targeted double mutation |
| Input 3 | Epistatic | One targeted double mutation |
| Input 4 | Single | SSM scan |
| Input 5 | Additive | SSM scan |
| Input 6 | Epistatic | SSM scan |

### Verification Status

**Status: VERIFIED** -- All 6 test cases pass structural validation across all three modes.

## Resource Requirements

| Resource | Value |
|----------|-------|
| GPU | T4 |
| Memory | 12 GB (loads 2 models) |
| CPU | 2 cores |
| Cold start | Memory snapshot enabled |
| Dependencies | None (self-contained; ThermoMPNN-D repo cloned into image) |

## Implementation Notes

- Loads two models at startup: single model (used for single and additive modes) and epistatic model
- Uses Modal memory snapshots: both models loaded on CPU during snap, then transferred to GPU
- PyTorch Lightning `load_from_checkpoint` is monkey-patched to default to CPU `map_location` for Modal snapshot compatibility
- ThermoMPNN-D repository is cloned at image build time (`git checkout` pinned to commit `64a24fe`)
- PDB files are written to temporary directories per request and cleaned up after prediction
- Epistatic SSM scans use batched inference (batch_size=2048) for efficiency
- The `v2_ssm` module from the ThermoMPNN-D repository is used for SSM computation and output formatting

## License

- **Code**: MIT ([GitHub](https://github.com/Kuhlman-Lab/ThermoMPNN-D/blob/main/LICENSE))

## References & Citations

### Papers

1. Dieckhaus H, Kuhlman B. "Predicting the effect of single and multiple mutations on protein stability." *bioRxiv* (2024). [DOI](https://doi.org/10.1101/2024.10.10.617658)

### BibTeX

```bibtex
@article{dieckhaus2024thermompnnd,
  title={Predicting the effect of single and multiple mutations on protein stability},
  author={Dieckhaus, Henry and Kuhlman, Brian},
  journal={bioRxiv},
  year={2024},
  doi={10.1101/2024.10.10.617658}
}
```

### Links

- **Paper**: [bioRxiv 2024.10.10.617658](https://doi.org/10.1101/2024.10.10.617658)
- **Code**: [GitHub Kuhlman-Lab/ThermoMPNN-D](https://github.com/Kuhlman-Lab/ThermoMPNN-D)

---

*See also: [MODEL.md](MODEL.md) for technical deep-dive | [BIOLOGY.md](BIOLOGY.md) for biological context*
