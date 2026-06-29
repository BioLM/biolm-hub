# Biotite

> **One-line summary**: A structure analysis toolkit providing PDB chain extraction and C-alpha RMSD computation as API endpoints, enabling automated structure comparison and chain-level analysis in multi-model workflows.

## Overview

Biotite is a computational biology toolkit for protein structure analysis, based on the [biotite](https://github.com/biotite-dev/biotite) Python library. It is **not a machine learning model** -- it provides deterministic, CPU-only structural analysis algorithms wrapped as BioLM endpoints.

The BioLM Biotite endpoint serves two primary functions:
1. **Chain extraction**: Parse multi-chain PDB structures and extract individual chains with their amino acid sequences and atomic coordinates
2. **RMSD computation**: Compute root-mean-square deviation between two protein structures after optimal Kabsch superimposition

These utilities are designed to integrate with structure prediction models on the BioLM platform (Boltz, Chai1, ESMFold) for end-to-end structure prediction and evaluation workflows.

## Architecture

| Property | Value |
|----------|-------|
| Architecture | Algorithmic (structure analysis toolkit) |
| Parameters | 0 (no learnable parameters) |
| GPU required | No (CPU only) |
| Deterministic | Yes |
| License | BSD-3-Clause |

## Model Variants

Biotite is a single-variant model with no size options.

| Variant | Slug | GPU | Memory | Use Case |
|---------|------|-----|--------|----------|
| **Biotite** | `biotite` | None (CPU) | 8 GB | Structure analysis |

## Capabilities & Limitations

**CAN be used for:**
- Extracting individual chains from multi-chain PDB structures
- Computing amino acid sequences from PDB atomic coordinates
- Computing C-alpha RMSD between two protein structures
- Comparing predicted structures against experimental references
- Batch processing of up to 8 structure pairs per request

**CANNOT be used for:**
- Structure prediction (use Boltz, Chai1, or ESMFold instead)
- All-atom RMSD (only C-alpha backbone RMSD is computed)
- mmCIF or other structure formats (PDB format only)
- Ligand or small molecule analysis
- Sequence analysis (use ESM2, Evo, or similar)

**Other considerations:**
- Only model 1 is extracted from multi-model PDB files
- Non-standard residues are mapped to "X" in sequence extraction
- RMSD computation requires matching C-alpha atom counts between compared chains

## Actions / Endpoints

> **Note on action verb naming**: Biotite uses the BioLM platform action verbs `generate` and
> `predict` by convention, but both are **utility operations**, not machine-learning generation
> or property prediction. `generate` here means "extract / produce structured data from a PDB"
> (chain extraction), and `predict` here means "compute a structural metric" (RMSD). This
> naming follows the platform contract; the docs below clarify what each action actually does.

### `generate` (Extract Chains)

Extracts specified chains from PDB structures, returning amino acid sequences and PDB coordinate strings for each chain.

**Request Schema**: `BiotiteExtractChainsRequest`

| Parameter | Type | Default | Range | Description |
|-----------|------|---------|-------|-------------|
| `items[].pdb` | str | (required) | valid PDB | PDB structure as string |
| `items[].chain_ids` | list[str] | (required) | 1--10 IDs | Chain identifiers to extract |

**Batch limit**: 1--8 items per request.

**Response Schema**: `BiotiteExtractChainsResponse`

```json
{
  "results": [
    {
      "chain_sequences": {
        "A": "MKTVRQERL...",
        "B": "GVQVETISP..."
      },
      "chain_pdb_strings": {
        "A": "ATOM      1  N   ALA A   1 ...",
        "B": "ATOM      6  N   GLY B   1 ..."
      }
    }
  ]
}
```

### `predict` (Compute RMSD)

Computes C-alpha RMSD between two PDB structures after optimal Kabsch superimposition. Supports multi-chain comparisons with explicit chain mapping.

**Request Schema**: `BiotiteRMSDRequest`

| Parameter | Type | Default | Range | Description |
|-----------|------|---------|-------|-------------|
| `items[].pdb_a` | str | (required) | valid PDB | First PDB structure |
| `items[].pdb_b` | str | (required) | valid PDB | Second PDB structure |
| `items[].chain_a` | list[str] | (required) | 1+ IDs | Chain IDs from `pdb_a` to compare |
| `items[].chain_b` | list[str] | (required) | 1+ IDs | Chain IDs from `pdb_b` to compare |

`chain_a` and `chain_b` are paired lists: `chain_a[i]` in `pdb_a` is compared against `chain_b[i]` in `pdb_b`. Both lists must have equal length.

**Batch limit**: 1--8 items per request.

**Response Schema**: `BiotiteRMSDResponse`

```json
{
  "results": [
    {
      "rmsd": 1.234
    }
  ]
}
```

The `rmsd` value is in Angstroms.

## Usage Examples

```python
# Extract chains from a multi-chain PDB
from models.biotite.schema import (
    BiotiteExtractChainsRequest,
    BiotiteExtractChainsRequestItem,
)

extract_request = BiotiteExtractChainsRequest(
    items=[
        BiotiteExtractChainsRequestItem(
            pdb="ATOM      1  N   ALA A   1 ...\nATOM      6  N   GLY B   1 ...\nEND",
            chain_ids=["A", "B"],
        )
    ]
)

# Compute RMSD between two structures
from models.biotite.schema import (
    BiotiteRMSDRequest,
    BiotiteRMSDRequestItem,
)

rmsd_request = BiotiteRMSDRequest(
    items=[
        BiotiteRMSDRequestItem(
            pdb_a="ATOM  ... (predicted structure) ... END",
            pdb_b="ATOM  ... (reference structure) ... END",
            chain_a=["A"],
            chain_b=["A"],
        )
    ]
)
```

## Performance & Benchmarks

Not applicable (algorithmic tool). All outputs are deterministic and exact.

## Implementation Verification

### Verification Method

Deterministic output comparison: test fixtures verify chain extraction and RMSD computation against golden reference outputs.

### Test Cases

| Test Case | Action | Input | Verification |
|-----------|--------|-------|--------------|
| Chain extraction | `generate` | Multi-chain PDB, chains A and B | Exact match to golden output |
| RMSD self-comparison | `predict` | Same structure vs. itself | RMSD = 0.0 (within tolerance) |

### Verification Status

**Status: VERIFIED** -- Integration tests pass for both actions with rel_tol=1e-4.

## Resource Requirements

| Resource | Value |
|----------|-------|
| GPU | None (CPU only) |
| Memory | 8 GB |
| CPU | 2 cores |
| Cold start | Fast (memory snapshot enabled) |
| Batch size | 8 items max per request |
| Dependencies | `biotite==1.3.0`, `numpy==2.4.3` |

## Implementation Notes

- **Memory snapshots**: Uses `@modal.enter(snap=True)` to pre-import biotite modules for faster cold starts.
- **Base class**: Inherits from `ModelMixinSnap` (health/snapshot hooks; no billing logic in the model container).
- **PDB parsing**: Uses `biotite.structure.io.pdb.PDBFile` for reading and writing PDB files.
- **Superimposition**: Uses `biotite.structure.superimpose()` which implements the Kabsch algorithm for optimal rigid-body alignment.
- **RMSD calculation**: Uses `biotite.structure.rmsd()` on C-alpha atoms after superimposition.
- **Sequence extraction**: Converts 3-letter amino acid codes to 1-letter codes using a fixed mapping (25 residue types including non-standard). Unknown residues map to "X".
- **Caching**: Response caching is handled by the platform layer, not the model container.

## License

- **Code**: BSD-3-Clause ([LICENSE](https://github.com/biotite-dev/biotite/blob/main/LICENSE.rst))
- **Library**: BSD-3-Clause (biotite)

## References & Citations

### Papers

1. Kunzmann P, Hamacher K. "Biotite: a unifying open source computational biology framework in Python." BMC Bioinformatics (2018). [DOI: 10.1186/s12859-018-2367-z](https://doi.org/10.1186/s12859-018-2367-z)

### Links

- **GitHub**: [github.com/biotite-dev/biotite](https://github.com/biotite-dev/biotite)
- **PyPI**: [pypi.org/project/biotite](https://pypi.org/project/biotite/)
- **Documentation**: [biotite-dev.github.io/biotite](https://www.biotite-dev.github.io/biotite/)

---

*See also: [MODEL.md](MODEL.md) for technical deep-dive | [BIOLOGY.md](BIOLOGY.md) for biological context*
