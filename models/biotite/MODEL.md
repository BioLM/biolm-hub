# Biotite -- Technical Details

## Architecture

### Model Type & Innovation

Biotite is **not a machine learning model**. It is a computational biology toolkit for protein structure analysis, wrapped as a BioLM endpoint. The `biotite` Python library provides efficient, well-tested algorithms for reading, writing, and analyzing macromolecular structures in PDB format.

The BioLM Biotite endpoint exposes two key structural analysis capabilities:
1. **Chain extraction** (`generate` action): Parse PDB structures and extract individual chains with their sequences and atomic coordinates. The `generate` verb follows BioLM platform convention; this is a **utility extraction operation**, not ML-based generation.
2. **RMSD computation** (`predict` action): Compute root-mean-square deviation between two structures after optimal superimposition. The `predict` verb follows BioLM platform convention; this is a **structural metric computation**, not ML-based property prediction.

These are essential utilities for structure prediction workflows -- e.g., comparing predicted structures from Chai1 or ESMFold against experimental references, or extracting individual chains from multi-chain complexes for downstream analysis.

### Parameters & Layers

| Property | Value |
|----------|-------|
| Architecture | Algorithmic (structure analysis toolkit) |
| Learnable parameters | 0 |
| GPU required | No (CPU only) |
| Deterministic | Yes |

### Training Data

Not applicable. Biotite uses deterministic algorithms for structure parsing and RMSD computation. No training data is involved.

### Loss Function & Objective

Not applicable (algorithmic tool).

### Tokenization / Input Processing

| Property | Details |
|----------|---------|
| Input type | PDB structure strings |
| Validation | PDB format validation via `validate_pdb` |
| Chain IDs | Single-character chain identifiers |
| Coordinate system | Cartesian (Angstroms) |
| RMSD atoms | C-alpha (CA) backbone atoms |
| Batch size | 8 items per request |

## Performance & Benchmarks

### Published Benchmarks

Not applicable in the ML sense. Biotite implements standard structural biology algorithms:
- **RMSD**: Root-mean-square deviation after optimal Kabsch superimposition
- **Chain extraction**: Direct PDB parsing and filtering

### BioLM Verification Results

| Test | Input | Tolerance | Status |
|------|-------|-----------|--------|
| Chain extraction | Multi-chain PDB, extract chains A and B | Exact match | PASS |
| RMSD computation | Same structure vs. itself | rel_tol=1e-4, RMSD=0.0 | PASS |

### Comparison to Alternatives

| Tool | Advantage | Disadvantage |
|------|-----------|--------------|
| **Biotite (this)** | Integrated with BioLM; composable with prediction models | Limited to chain extraction and RMSD |
| BioPython PDB | More comprehensive PDB analysis | Not available as API; requires local setup |
| PyMOL | Full visualization and analysis | Heavy; GUI-focused; commercial for some uses |
| MDAnalysis | Trajectory analysis; extensive atom selection | Focused on MD simulations; heavier dependency |
| ProDy | ENM analysis; dynamics | More specialized; not structure comparison focused |

### Error Bars & Confidence

All computations are deterministic. RMSD is computed using Biotite's `struc.superimpose()` (Kabsch algorithm) followed by `struc.rmsd()`, both of which are exact up to floating-point precision.

## Strengths & Limitations

### Pros

- Fully deterministic -- no randomness or hardware-dependent variation
- No GPU required -- runs on CPU with minimal resources
- Fast execution -- structure parsing and RMSD computation complete in milliseconds
- Composable -- designed to work with structure prediction models (Chai1, ESMFold) in multi-step workflows
- Standard algorithms -- uses well-validated Kabsch superimposition for RMSD
- Batch processing -- up to 8 items per request

### Cons

- Limited scope -- only chain extraction and RMSD, not a general structure analysis suite
- PDB format only -- does not accept mmCIF or other structure formats
- C-alpha RMSD only -- does not compute all-atom or side-chain RMSD
- Requires matching chain lengths -- RMSD fails if C-alpha atom counts differ between structures
- 3-letter to 1-letter conversion uses a fixed mapping -- non-standard residues mapped to "X"

### Known Failure Modes

- **Mismatched chain lengths**: RMSD computation requires identical numbers of C-alpha atoms in compared chains
- **Missing chains**: Requesting extraction of a chain ID not present in the PDB returns an error
- **Non-standard residues**: Residues not in the standard amino acid mapping are converted to "X"
- **Multi-model PDB files**: Only model 1 is extracted
- **Very large structures**: While no hard limit, very large PDB strings may approach memory limits

## Implementation Details

### Inference Pipeline

```
Request
  |-- Route to action:
  |
  |-- [generate] (extract chains)
  |     |-- Validate PDB string
  |     |-- Parse with biotite.structure.io.pdb.PDBFile
  |     |-- Get structure (model=1)
  |     |-- For each requested chain_id:
  |     |     |-- Filter atoms by chain_id
  |     |     |-- Extract sequence (3-letter to 1-letter conversion)
  |     |     |-- Write chain to temporary PDB file
  |     |-- Return chain_sequences and chain_pdb_strings
  |
  |-- [predict] (compute RMSD)
        |-- Validate both PDB strings
        |-- Parse structures A and B
        |-- For each chain pair (a_i, b_i):
        |     |-- Extract C-alpha (CA) coordinates
        |     |-- Verify matching atom counts
        |-- Concatenate all chain coordinates
        |-- Superimpose with struc.superimpose() (Kabsch algorithm)
        |-- Compute RMSD with struc.rmsd()
        |-- Return RMSD in Angstroms
```

### Memory & Compute Profile

| Property | Value |
|----------|-------|
| GPU | None (CPU only) |
| Memory | 8 GB |
| CPU | 2 cores |
| Cold start | Fast (memory snapshot enabled) |

### Determinism & Reproducibility

| Setting | Value |
|---------|-------|
| Deterministic | Yes (all computations) |
| Random seeds | Not applicable |
| Hardware dependence | None (within floating-point precision) |

### Caching Behavior

Response caching is available as an optional, off-by-default gateway feature (`BIOLM_CACHE_ENABLED`) -- see the gateway docs; it is not handled by the model container.

- Cache key derived from PDB strings, chain IDs, and action type
- Cache hits are always valid since outputs are deterministic

## Versions & Changelog

| Version | Date | Changes |
|---------|------|---------|
| v1 | -- | Initial implementation with generate (chain extraction) and predict (RMSD) actions |

---

*See also: [README.md](README.md) for API reference | [BIOLOGY.md](BIOLOGY.md) for biological context*
