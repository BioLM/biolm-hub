# ImmuneBuilder -- Technical Details

## Architecture

### Model Type & Innovation

ImmuneBuilder is an ensemble of deep learning models for predicting the 3D structures of immune proteins -- antibodies, nanobodies, and T-cell receptors (TCRs). It consists of four specialized sub-models, each trained on distinct structural classes: ABodyBuilder2 (antibody VH/VL), NanoBodyBuilder2 (single-domain VHH), TCRBuilder2 (alpha/beta TCR), and TCRBuilder2Plus (improved TCR with updated weights). Each sub-model uses an equivariant graph neural network (EGNN) architecture that operates directly on residue-level graphs, iteratively refining predicted 3D coordinates.

The key innovation is decomposing the immune protein structure prediction problem into specialized sub-models, each trained on curated structural databases (SAbDab for antibodies, STCRDab for TCRs). This specialization yields higher accuracy on immune proteins compared to general-purpose structure predictors. The models output PDB-format structures with relaxed coordinates via OpenMM energy minimization.

### Parameters & Layers

| Component | Details |
|-----------|---------|
| Architecture | Equivariant Graph Neural Network (EGNN) ensemble |
| Sub-models | ABodyBuilder2, NanoBodyBuilder2, TCRBuilder2, TCRBuilder2Plus |
| Ensemble members | 4 per sub-model (antibody_model_1..4, nanobody_model_1..4, tcr_model_1..4, tcr2_model_1..4) |
| Input | Amino acid sequences for appropriate chain pairs |
| Output | PDB-format 3D atomic coordinates |
| Coordinate refinement | OpenMM energy minimization with AMBER force field |
| Numbering | ANARCI / IMGT for antibody and TCR region identification |

### Training Data

| Property | Details |
|----------|---------|
| Antibody training | SAbDab (Structural Antibody Database) -- paired VH/VL crystal structures |
| Nanobody training | SAbDab -- single-domain VHH structures |
| TCR training | STCRDab (Structural TCR Database) -- paired alpha/beta TCR structures |
| TCRBuilder2Plus | Updated weights on expanded TCR structural data |
| Numbering scheme | IMGT (ImMunoGeneTics) numbering via ANARCI |

### Loss Function & Objective

Each EGNN sub-model is trained to minimize the distance between predicted and experimental atomic coordinates, using a combination of coordinate RMSD loss and auxiliary geometric losses (bond lengths, angles). The ensemble of 4 models per sub-type provides robustness -- final predictions are obtained by averaging over ensemble members.

### Tokenization / Input Processing

- **Input format**: Amino acid sequences provided as single-letter codes
- **Chain specification**: `heavy_chain`, `light_chain` for antibodies; `tcr_alpha`, `tcr_beta` for TCRs; `heavy_chain` only for nanobodies (legacy single-letter aliases `H`/`L`/`A`/`B` are still accepted)
- **Validation**: Extended amino acid alphabet (including ambiguous residues)
- **Type inference**: The model type is automatically inferred from the chain combination:
  - `heavy_chain` + `light_chain` => ABodyBuilder2
  - `heavy_chain` only => NanoBodyBuilder2
  - `tcr_alpha` + `tcr_beta` => TCRBuilder2 and TCRBuilder2Plus
- **Numbering**: ANARCI assigns IMGT numbering before structure prediction
- **Post-processing**: OpenMM relaxation produces physically realistic bond geometries

## Performance & Benchmarks

### Published Benchmarks

#### Antibody Structure Prediction (ABodyBuilder2)

| Model | CDR-H3 RMSD (A) | Overall VH/VL RMSD (A) | Notes |
|-------|------------------|------------------------|-------|
| **ABodyBuilder2** | **2.81** | **~1.5** | Avg on SAbDab test set |
| AlphaFold2 | 3.42 | ~1.8 | General-purpose |
| ABlooper | 3.15 | -- | CDR-only predictor |

Abanades et al., *Communications Biology* (2023). Table values are approximate from paper figures.

#### Nanobody Structure Prediction (NanoBodyBuilder2)

| Model | CDR-H3 RMSD (A) | Notes |
|-------|------------------|-------|
| **NanoBodyBuilder2** | **~2.5** | Specialized for VHH |
| AlphaFold2 | ~3.0 | Not nanobody-specific |

#### TCR Structure Prediction (TCRBuilder2)

| Model | CDR3-alpha RMSD (A) | CDR3-beta RMSD (A) | Notes |
|-------|---------------------|---------------------|-------|
| **TCRBuilder2** | **~1.8** | **~2.2** | Specialized for TCR |
| AlphaFold2 | ~2.5 | ~3.0 | General-purpose |

### BioLM Verification Results

| Variant | Action | Tolerance | Status |
|---------|--------|-----------|--------|
| abodybuilder2 | fold | rel_tol 1e-4, PDB RMSD < 1A | PASS |
| nanobodybuilder2 | fold | rel_tol 1e-4, PDB RMSD < 1A | PASS |
| tcrbuilder2 | fold | rel_tol 1e-4, PDB RMSD < 1A | PASS |
| tcrbuilder2plus | fold | rel_tol 1e-4, PDB RMSD < 1A | PASS |

### Comparison to Alternatives

| Model | Strength | When to prefer |
|-------|----------|----------------|
| **ImmuneBuilder** | Immune protein specialist; fast; no MSA needed | Antibody/nanobody/TCR structure prediction |
| AlphaFold2 | General-purpose; higher accuracy on some targets | Non-immune proteins; when MSA available |
| ESMFold | Single-sequence; very fast | Quick single-chain protein folding |
| ImmuneFold | PLM-enhanced antibody/TCR folding | When higher accuracy on antibodies is needed |

## Strengths & Limitations

### Pros

- Specialized for immune proteins with dedicated sub-models for each structural class
- No MSA required -- single-sequence input for fast predictions
- Supports antibodies, nanobodies, and TCRs in a unified framework
- OpenMM energy minimization produces physically realistic structures
- Lightweight CPU-only inference (no GPU required)
- Deterministic with fixed random seed

### Cons

- Limited to immune protein variable domains (not for general proteins)
- CDR-H3 accuracy lower than AlphaFold2 Multimer for some targets
- No antigen-bound complex prediction
- Ensemble of 4 models per variant adds overhead vs single-model approaches
- Maximum sequence length of 2048 residues per chain

### Known Failure Modes

- Sequences that fail ANARCI numbering (highly unusual or non-standard immune protein sequences) will produce errors
- Very long CDR-H3 loops (>25 residues) may have reduced accuracy
- Proteins that are not antibodies, nanobodies, or TCRs will produce meaningless results

## Implementation Details

### Inference Pipeline

```
Request
  |-- 1. Validate amino acid sequences
  |-- 2. Infer model type from chain combination (H+L, H-only, A+B)
  |-- 3. Route to appropriate sub-model (ABodyBuilder2/NanoBodyBuilder2/TCRBuilder2/TCRBuilder2Plus)
  |-- 4. Run EGNN ensemble (4 models) to predict coordinates
  |-- 5. Average ensemble predictions
  |-- 6. OpenMM energy minimization (AMBER force field)
  |-- 7. Write to temporary PDB file
  |-- 8. Read PDB string and clean up
  |-- 9. Return PDB string in response
```

### Memory & Compute Profile

| Resource | Value |
|----------|-------|
| GPU | None (CPU-only) |
| Memory | 8 GB RAM |
| CPU | 2.0 cores |
| Batch size | 8 |
| Max sequence length | 2048 |

### Determinism & Reproducibility

| Setting | Value |
|---------|-------|
| Torch manual seed | Yes (42 at model load) |
| CUDA manual seed | Yes (42, if available) |
| NumPy seed | Set per-request |
| User-specified seed | Supported via `seed` parameter (default: 42) |
| PYTHONHASHSEED | Set to seed value |
| cuDNN deterministic | Enabled |

### Caching Behavior

Response caching (Redis/R2 two-tier) is handled by the BioLM platform layer, not by the model container:
- Redis (Modal Dict) caching for fast repeated lookups
- R2 caching for persistence
- Cache keys determined by full request payload

## Versions & Changelog

| Version | Date | Changes |
|---------|------|---------|
| v1 | 2025 | Initial implementation with 4 sub-model variants |

---

*See also: [README.md](README.md) for API reference | [BIOLOGY.md](BIOLOGY.md) for biological context*
