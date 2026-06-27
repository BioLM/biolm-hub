# SPURS

> **One-line summary**: Structure-aware protein stability predictor that computes ddG values for single and multi-residue mutations, with full deep mutational scanning matrix generation.

## Overview

SPURS (Structure Prediction Using Residue-level and Secondary structure information) is a protein stability prediction model developed by the Luo Group. It combines ESM2-650M sequence embeddings with 3D structural features to predict the change in free energy (ddG) upon amino acid substitution.

SPURS supports three prediction modes: single-mutation ddG prediction, multi-mutation combined ddG with per-mutation contributions, and full saturation mutagenesis (DMS) matrix generation covering all possible single-residue substitutions.

## Architecture

| Property | Value |
|----------|-------|
| Architecture | Structure-aware GNN + ESM2-650M |
| Task | ddG prediction (kcal/mol) |
| Input | Protein sequence + 3D structure (PDB/CIF) |
| Max sequence length | 1024 residues |
| Output | ddG values or L x 20 DMS matrix |
| License | MIT |

## Model Variants

SPURS is a single-variant model (no size variants).

| Variant | GPU | Memory | CPU | Use Case |
|---------|-----|--------|-----|----------|
| `spurs` | T4 | 16 GB | 4 cores | All stability predictions |

## Capabilities & Limitations

**CAN be used for:**
- Predicting ddG for single point mutations
- Predicting combined ddG for multiple simultaneous mutations
- Generating full saturation mutagenesis (DMS) matrices
- Comparing wild-type and variant sequences to quantify stability differences
- Screening mutation libraries for stability-preserving variants

**CANNOT be used for:**
- Sequences without 3D structure (requires PDB or CIF input)
- Sequences longer than 1024 residues
- Multi-chain stability analysis (single chain only)
- Predicting catalytic activity, binding affinity, or other functional properties
- Non-protein molecules

**Other considerations:**
- Batch size is capped at 4 items per request
- Mutations use 1-indexed positions in format `<WT><position><MT>` (e.g., "M3L")
- The full DMS matrix returns L x 20 values (20 canonical amino acids)
- GPU memory snapshots are enabled for fast cold starts

## Actions / Endpoints

### `predict`

Predicts ddG values for protein mutations. Supports three modes:

1. **Single/multi-mutation**: Provide `mutations` list
2. **Full DMS matrix**: Omit `mutations` (or set `return_full_dms=True`)
3. **Variant comparison**: Provide `variant_sequence` with `return_full_dms=False`

**Request Parameters:**

| Parameter | Type | Default | Range | Description |
|-----------|------|---------|-------|-------------|
| `items[].sequence` | str | *(required)* | 1-1024 AA | Wild-type protein sequence (canonical 20 AA) |
| `items[].pdb` | str | None | -- | PDB format structure content |
| `items[].cif` | str | None | -- | mmCIF format structure content |
| `items[].chain_id` | str | "A" | 1 char | Chain identifier in structure |
| `items[].mutations` | list[str] | None | -- | Mutations in `<WT><pos><MT>` format (e.g., ["K2L"]) |
| `items[].variant_sequence` | str | None | 1-1024 AA | Variant sequence for auto-mutation calculation |
| `items[].return_full_dms` | bool | True | -- | Return full DMS matrix when mutations is None |

**Response (single/multi-mutation):**

```json
{
  "results": [
    {
      "mutations": ["K2L"],
      "ddG": -0.534,
      "ddG_contributions": null,
      "ddG_matrix": null
    }
  ]
}
```

**Response (full DMS matrix):**

```json
{
  "results": [
    {
      "mutations": null,
      "ddG": null,
      "ddG_contributions": null,
      "ddG_matrix": {
        "values": [[0.0, -0.5, ...], ...],
        "residue_axis": ["M", "K", "A", ...],
        "amino_acid_axis": ["A", "C", "D", ..., "Y"]
      }
    }
  ]
}
```

## Usage Examples

```python
# Single mutation ddG prediction
from models.spurs.schema import SpursPredictRequest, SpursPredictRequestItem

request = SpursPredictRequest(
    items=[
        SpursPredictRequestItem(
            sequence="MKAAVDLKTF",
            pdb=pdb_content,
            chain_id="A",
            mutations=["K2L"],
        )
    ],
)

# Full DMS matrix
request_dms = SpursPredictRequest(
    items=[
        SpursPredictRequestItem(
            sequence="MKAAVDLKTF",
            pdb=pdb_content,
            chain_id="A",
            mutations=None,
            return_full_dms=True,
        )
    ],
)

# Variant sequence comparison
request_variant = SpursPredictRequest(
    items=[
        SpursPredictRequestItem(
            sequence="MKAAVDLKTF",
            pdb=pdb_content,
            chain_id="A",
            variant_sequence="MLAAVDLRTF",
            mutations=None,
            return_full_dms=False,
        )
    ],
)
```

## Performance & Benchmarks

### SOTA Status

SPURS provides structure-aware ddG prediction with multi-mutation support. Benchmarks against standard stability prediction datasets are pending.

<!-- TODO: Add specific benchmark numbers from SPURS paper when published -->

## Implementation Verification

### Verification Method

Golden output comparison: Test fixtures compare outputs against reference values stored in R2 with relative tolerance of 1e-4.

### Test Cases

| Test Case | Action | Input | Verification |
|-----------|--------|-------|--------------|
| Single mutation | `predict` | 1 mutation + structure | ddG value comparison (rel_tol 1e-4) |
| Multi-mutation | `predict` | Multiple mutations + structure | Combined ddG + contributions comparison |
| Full DMS matrix | `predict` | No mutations (full matrix) | Matrix value comparison (rel_tol 1e-4) |
| Variant sequence | `predict` | variant_sequence + structure | Auto-calculated mutations ddG comparison |

### Verification Status

**Status: VERIFIED** -- Integration tests pass for all test cases with rel_tol=1e-4.

## Resource Requirements

| Variant | GPU | Memory | CPU |
|---------|-----|--------|-----|
| `spurs` | T4 (16 GB VRAM) | 16 GB | 4 cores |

## Implementation Notes

- **Memory snapshots**: Uses `@modal.enter(snap=True)` with GPU memory snapshots for fast cold starts
- **ESM2-650M**: Embeddings computed locally (not via cross-app call) using cached weights
- **SPURS repository**: Cloned at pinned commit (`2bae5fed`) into `/opt/spurs`
- **Structure handling**: CIF files converted to PDB via biotite before SPURS processing
- **Determinism**: Seeds set via SPURS `seed_everything(42)` utility
- **Caching**: Response caching (Redis/R2 two-tier) is handled by the BioLM platform layer, not by the model container

## License

- **Code**: MIT ([LICENSE](https://github.com/luo-group/SPURS/blob/main/LICENSE))
- **Weights**: MIT (HuggingFace `cyclization9/SPURS`)

## References & Citations

### Links

- **Code**: [github.com/luo-group/SPURS](https://github.com/luo-group/SPURS)
- **Weights**: [huggingface.co/cyclization9/SPURS](https://huggingface.co/cyclization9/SPURS)

---

*See also: [MODEL.md](MODEL.md) for technical deep-dive | [BIOLOGY.md](BIOLOGY.md) for biological context*
