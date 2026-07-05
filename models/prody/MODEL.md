# ProDy -- Technical Details

## Architecture

### Model Type & Innovation

ProDy is not a neural network -- it is an algorithmic protein structure analysis library that computes molecular interactions and structural comparisons using physics-based distance and angle cutoffs. The BioLM implementation wraps ProDy's InSty (Interactions by Structural Topology) module and RMSD calculation into a serving endpoint.

The key utility is that ProDy computes **non-covalent interactions** (hydrogen bonds, salt bridges, hydrophobic contacts, pi-stacking, cation-pi, repulsive ionic) between residues using standardized geometric criteria, and **RMSD** between protein structures using structural or sequence-based alignment.

### Parameters & Layers

ProDy is parameter-free -- it uses physics-based cutoffs rather than learned weights.

| Interaction Type | Distance Cutoff | Other Criteria |
|-----------------|-----------------|----------------|
| Hydrogen bond | 2.7-3.4 Angstrom | Angle constraints |
| Salt bridge | 3.3-3.5 Angstrom | Charged residue pairs |
| Hydrophobic | 3.4-4.5 Angstrom | Non-polar residue contacts |
| Pi-stacking | Variable | Aromatic ring geometry |
| Cation-pi | Variable | Cation and aromatic ring |
| Repulsive ionic | Variable | Like-charge pairs |

### Training Data

Not applicable -- ProDy is a physics-based tool with no training data.

### Loss Function & Objective

Not applicable.

### Tokenization / Input Processing

| Property | Details |
|----------|---------|
| Structure input | PDB or CIF format |
| Chain validation | Must be protein chains (DNA/RNA/ligands rejected) |
| Minimum residues | 5 (for meaningful interaction analysis) |
| Hydrogen addition | PDBFixer (default, more accurate) or OpenBabel (faster) |
| CIF conversion | OpenMM (primary) or ProDy (fallback) |

## Performance & Benchmarks

### Published Benchmarks

ProDy's interaction detection follows standard crystallographic distance/angle criteria. Validation is inherent in the method rather than requiring benchmark comparisons.

### BioLM Verification Results

| Metric | Threshold | Status |
|--------|-----------|--------|
| Hydrogen bond counts | Exact (+/-1 tolerance) | PASS |
| Salt bridge counts | Exact match | PASS |
| Hydrophobic counts | Exact match | PASS |
| RMSD (identical structures) | Near-zero (~1e-14) | PASS |
| RMSD (different structures) | 5% relative tolerance | PASS |

Hydrogen bond counts may vary by +/-1 between runs due to borderline detection at distance/angle cutoffs after non-deterministic hydrogen placement.

### Comparison to Alternatives

| Tool | Key Advantage | Key Disadvantage |
|------|---------------|------------------|
| **ProDy (this)** | Comprehensive interaction types, energy matrices, frequent interactors | Requires hydrogen addition for H-bond detection |
| PLIP | Integrated visualization | Fewer interaction types |
| Arpeggio | More interaction types, handles nucleic acids | Heavier dependencies |
| GetContacts | Fast contact analysis | Less robust hydrogen handling |

### Error Bars & Confidence

ProDy is deterministic for non-hydrogen interactions. Hydrogen bond counts may vary +/-1 due to non-deterministic hydrogen placement by PDBFixer/OpenBabel energy minimization.

## Strengths & Limitations

### Pros

- Comprehensive interaction analysis (6 interaction types) with standardized cutoffs
- RMSD calculation with structural or sequence-based alignment
- CPU-only -- no GPU required, low resource footprint
- Handles both single-chain and multi-chain interaction analysis
- Returns interaction matrices, energy matrices, and frequent interactor analysis
- Supports both PDB and CIF input formats

### Cons

- Hydrogen bond counts are slightly non-deterministic (+/-1)
- ProDy C extensions are not thread-safe; batch processing is sequential
- Requires at least 5 residues for meaningful analysis
- Only analyzes protein chains (nucleic acids and small molecules rejected)
- Hydrogen addition adds processing time (~1-5s per structure)

### Known Failure Modes

- **Non-protein chains**: Requesting analysis of DNA, RNA, or ligand chains raises a `ValueError` with the detected molecule type
- **Very small structures**: Structures with fewer than 5 residues are rejected
- **ProDy index errors**: Some unusual structure geometries trigger internal ProDy indexing bugs
- **Hydrophobic calculation bugs**: Known ProDy issue with certain structure geometries

## Implementation Details

### Inference Pipeline

**Encode (InSty) pipeline:**
```
Request
  |-- 1. Validate structure (PDB/CIF, protein chains only)
  |-- 2. Parse structure (ProDy parsePDB/parseMMCIF)
  |-- 3. Add hydrogens if requested (PDBFixer or OpenBabel)
  |-- 4. Create ProDy Interactions object
  |-- 5. Calculate protein interactions (calcProteinInteractions)
  |-- 6. Extract intra-chain interactions per chain
  |-- 7. Extract inter-chain interactions per chain pair
  |-- 8. Build interaction/energy matrices if requested
  |-- 9. Get frequent interactors if requested
  |-- 10. Return ProDyEncodeResponse
```

**Predict (RMSD) pipeline:**
```
Request
  |-- 1. Parse both structures (ProDy)
  |-- 2. Select specified chains (protein only)
  |-- 3. Extract CA atoms
  |-- 4. Match chains (structural or sequence alignment)
  |-- 5. Calculate transformation and apply
  |-- 6. Compute RMSD
  |-- 7. Return ProDyPredictResponse
```

### Memory & Compute Profile

| Component | Resource |
|-----------|----------|
| CPU | 4 cores |
| Memory | 16 GB RAM |
| GPU | None (CPU-only) |
| Inference time (encode) | 2-10s per structure (depends on chain count and hydrogen addition) |
| Inference time (predict) | 1-5s per pair |

### Determinism & Reproducibility

| Setting | Value |
|---------|-------|
| `random.seed` | 42 |
| `numpy.random.seed` | 42 |
| Hydrogen bonds | +/-1 non-determinism |
| All other interactions | Fully deterministic |

### Caching Behavior

Response caching is available as an optional, off-by-default gateway feature (`BIOLM_CACHE_ENABLED`) -- see the gateway docs; it is not handled by the model container. Memory snapshots are disabled (`enable_memory_snapshot=False`) to ensure fresh code execution on each container start.

## Versions & Changelog

| Version | Date | Changes |
|---------|------|---------|
| v1 | 2026-02-14 | Initial implementation with encode (InSty) and predict (RMSD) actions |
| v1 (updated) | 2026-02-14 | Added chain validation (protein-only, with molecule type detection) |
| v1 (updated) | 2026-02-14 | Added multi-chain analysis with chain_pairs parameter |

---

*See also: [README.md](README.md) for API reference | [BIOLOGY.md](BIOLOGY.md) for biological context*
