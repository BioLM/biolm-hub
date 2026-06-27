# ProperMAB -- Technical Details

## Architecture

### Model Type & Innovation

ProperMAB is **not a prediction model** -- it is a **feature engineering framework** that extracts 34 structure-aware biophysical descriptors from antibody sequences. These features can be used to train machine learning models for specific developability properties (HIC retention time, viscosity, aggregation) when combined with experimental data.

The framework operates as a multi-stage computational pipeline:
1. 3D structure prediction using ABodyBuilder2 (EGNN-based antibody structure predictor)
2. Sequence feature extraction (7 features from amino acid properties)
3. Structure feature extraction (27 features from predicted 3D structure)

The key innovation is the use of spatial point pattern statistics (Average Nearest Neighbor index, Ripley's K function) applied to molecular surface properties -- a novel contribution that captures clustering patterns of charged, hydrophobic, and aromatic residues on the antibody surface. These spatial statistics are the strongest differentiators from prior feature sets.

### Parameters & Layers

| Component | Details |
|-----------|---------|
| Architecture | Multi-tool computational pipeline (not a neural network) |
| Structure predictor | ABodyBuilder2 (EGNN, 4-model ensemble) |
| Surface mesh | NanoShaper (triangulated molecular surface) |
| Electrostatics | APBS v3.0.0 (Poisson-Boltzmann solver) |
| Partial charges | OpenMM + CHARMM36 force field |
| SASA calculator | FreeSASA 2.2.1 |
| Numbering | ANARCI + HMMER 3.3.2 (IMGT scheme) |
| Feature count | 34 total (7 sequence + 27 structure) |

### Feature Computation Details

#### Sequence Features (7) -- Computed Instantly

| Feature | Computation | Units |
|---------|-------------|-------|
| `theoretical_pi` | Henderson-Hasselbalch isoelectric point | pH |
| `n_charged_res` | Count of D, E, K, R residues | count |
| `n_charged_res_fv` | Charged residues in Fv region only | count |
| `fv_charge` | Net charge at pH 7.4 (Fv domain) | charge units |
| `fv_csp` | VH_charge x VL_charge | charge^2 |
| `fc_charge` | Net charge of Fc domain (isotype-dependent) | charge units |
| `fab_fc_csp` | FAB_charge x FC_charge | charge^2 |

#### Structure Features (27) -- Requires ~60s per Run

Computed from the ABodyBuilder2-predicted 3D structure using:
- APBS electrostatic potential mapped onto the molecular surface
- NanoShaper triangulated surface mesh for patch detection
- FreeSASA solvent-accessible surface area calculations
- OpenMM/CHARMM36 partial charge assignments
- ANARCI IMGT numbering for CDR/framework annotation

See `ProperMABStructureFeatures` in `schema.py` for the complete list with descriptions.

### Loss Function & Objective

Not applicable -- ProperMAB is not a trained model. Feature computation is deterministic for sequence features. Structure features depend on ABodyBuilder2 predictions (stochastic across runs).

### Tokenization / Input Processing

- **Input format**: Heavy chain (VH) and light chain (VL) amino acid sequences
- **Sequence validation**: Extended amino acid alphabet; min 100 AA, max 200 AA per chain
- **Parameters**: `num_runs` (1-5), `is_fv` (boolean), `isotype` (igg1/igg2/igg4), `lc_type` (kappa/lambda), `seed`
- **Structure prediction**: ABodyBuilder2 generates PDB structure(s) from sequences
- **Multi-run averaging**: When `num_runs > 1`, float features are averaged; integer features (aromatic_cdr, exposed_aromatic, cdr_h3_length) use the mode

## Performance & Benchmarks

### Published Benchmarks

From Li et al., *mAbs* (2025):

#### HIC Retention Time Prediction (135 mAbs)

| Model/Feature | Pearson r | Spearman rho | Notes |
|---------------|-----------|--------------|-------|
| **ElasticNet (all features)** | **0.71** | **0.75** | Nested LOOCV; 23/35 features retained |
| `hyd_patch_area_cdr` (best single) | 0.60 | -- | Hydrophobic patches near CDRs |
| `aromatic_asa` | 0.55 | -- | Aromatic surface area |
| `heiden_score` | 0.54 | -- | Surface hydrophobic potential |

#### High-Concentration Viscosity (150 mg/mL)

| Dataset | Model | Spearman rho | Pearson r | Notes |
|---------|-------|--------------|-----------|-------|
| **IgG4 (n=58)** | Random Forest | **0.48** | 0.35 | Largest IgG4 viscosity dataset published |

#### Feature Prediction from Sequence

| Metric | Value |
|--------|-------|
| Median Pearson r | 0.87 |
| Test set | 2,000 OAS antibodies |
| Speed | <2 min for 140k sequences (M1 MacBook) |
| Performance drop | ~5% vs structure-calculated features |

### BioLM Verification Results

| Test Case | Parameters | Tolerance | Status |
|-----------|-----------|-----------|--------|
| Pembrolizumab VH/VL | num_runs=1, is_fv=True, IgG1, kappa | Seq: 0.1%, Struct: 200% | PASS |
| Pembrolizumab VH/VL | num_runs=3, is_fv=False, IgG2, lambda | Seq: 0.1%, Struct: 200% | PASS |

Structure feature tolerance is set high (200%) because ABodyBuilder2 predictions are stochastic across different containers, even with a fixed seed.

### Comparison to Alternatives

| Feature Set | Strength | When to prefer |
|-------------|----------|----------------|
| **ProperMAB** | Spatial statistics; CDR-aware patches; open-source | Comprehensive antibody developability assessment |
| SCM score | Simple single feature | Quick screening (but not predictive for IgG4 viscosity) |
| TAP score | Rule-based; fast | Rapid go/no-go decisions |
| Commercial packages | Validated pipelines | Regulatory-grade workflows |

## Strengths & Limitations

### Pros

- Comprehensive: 34 biophysical features covering charge, hydrophobicity, patches, spatial statistics
- Novel spatial statistics (ANN index, Ripley's K) capture residue clustering patterns
- Open-source Python implementation integrable with scikit-learn
- CDR-aware: features computed specifically for CDR regions and surfaces near CDRs
- Published validation on 135 mAbs for HIC RT and 58 mAbs for viscosity
- All dependencies are freely available

### Cons

- Provides features, not direct predictions -- requires experimental data to train downstream ML models
- Slow: ~60 seconds per antibody per run due to structure prediction and surface calculations
- Structure features are stochastic (depend on ABodyBuilder2 predictions)
- Batch size limited to 1 due to computational cost
- Large container image (APBS, OpenMM, NanoShaper, ImmuneBuilder, FreeSASA, etc.)
- Sequence-only input: cannot use experimental structures directly

### Known Failure Modes

- Sequences outside 100-200 AA per chain length range
- ANARCI numbering failures on non-standard antibody sequences
- APBS failures on structures with unusual electrostatic properties
- NaN values in spatial statistics when feature patches are empty (handled with validation)

## Implementation Details

### Inference Pipeline

```
Request
  |-- 1. Validate VH/VL sequences (100-200 AA, amino acid alphabet)
  |-- 2. Set random seeds for reproducibility
  |-- 3. Compute 7 sequence features (instant)
  |     |-- theoretical_pi, charges, charge separation parameters
  |-- 4. For each run (1-5):
  |     |-- 4a. Predict 3D structure with ABodyBuilder2
  |     |-- 4b. Assign partial charges (OpenMM/CHARMM36)
  |     |-- 4c. Compute solvent-accessible surface area (FreeSASA)
  |     |-- 4d. Generate molecular surface mesh (NanoShaper)
  |     |-- 4e. Solve Poisson-Boltzmann electrostatics (APBS)
  |     |-- 4f. Map electrostatic potential to surface
  |     |-- 4g. Detect hydrophobic/charge patches
  |     |-- 4h. Compute spatial statistics (ANN, Ripley's K)
  |     |-- 4i. Compute all 27 structure features
  |-- 5. Average structure features across runs (mode for integers)
  |-- 6. Validate all features (no NaN, no None)
  |-- 7. Return 34 features + metadata
```

### Memory & Compute Profile

| Resource | Value |
|----------|-------|
| GPU | None (CPU-only) |
| Memory | 32 GB RAM |
| CPU | 8.0 cores |
| Batch size | 1 |
| Runtime | ~60s per antibody (single run), ~5-8 min (5 runs) |
| Timeout | 900s (15 minutes) |

### Determinism & Reproducibility

| Setting | Value |
|---------|-------|
| User-specified seed | Supported (default: 42) |
| Torch manual seed | Yes |
| NumPy seed | Yes |
| Python random seed | Yes |
| cuDNN deterministic | Disabled (CPU-only) |
| ABodyBuilder2 stochasticity | Structure features vary between runs/containers |

Sequence features are fully deterministic. Structure features are stochastic due to ABodyBuilder2 prediction variability. Use `num_runs > 1` for more robust averages.

### Caching Behavior

Standard BioLM caching via `BillingMixinSnap`:
- Redis (Modal Dict) caching for fast repeated lookups
- R2 caching for persistence
- Particularly valuable given the ~60s compute time per request

## Versions & Changelog

| Version | Date | Changes |
|---------|------|---------|
| v1 | 2025 | Initial implementation with full 34-feature extraction |

---

*See also: [README.md](README.md) for API reference | [BIOLOGY.md](BIOLOGY.md) for biological context*
