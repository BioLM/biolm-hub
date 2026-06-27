# ImmuneFold -- Technical Details

## Architecture

### Model Type & Innovation

ImmuneFold is a structure prediction model for antibodies and T-cell receptors that integrates protein language model (PLM) representations with geometric deep learning. It uses ESM-2 (3B parameter variant, `esm2_t36_3B_UR50D`) as a pre-trained sequence encoder, whose embeddings are fed into a structure prediction module that outputs 3D atomic coordinates with per-residue confidence scores.

The key innovation is combining the evolutionary information captured by ESM-2 (trained on billions of protein sequences) with immune-protein-specific structural supervision. This PLM-enhanced approach achieves higher accuracy than models trained from scratch on immune protein structures alone (e.g., ImmuneBuilder), particularly on CDR loops where sequence diversity is highest.

ImmuneFold supports two modes: antibody folding (VH/VL paired, VH-only nanobody, and VH/VL with antigen PDB) and TCR folding (alpha/beta/peptide/MHC four-chain input).

### Parameters & Layers

| Component | Details |
|-----------|---------|
| Sequence encoder | ESM-2 3B (esm2_t36_3B_UR50D) -- 36 layers, 2560-dim embeddings |
| Structure module | Transformer + GNN hybrid |
| Antibody checkpoint | immunefold-ab.ckpt |
| TCR checkpoint | immunefold-tcr.ckpt |
| Input | Amino acid sequences (optionally with antigen PDB) |
| Output | PDB structure, pTM score, full pLDDT, per-residue pLDDT |
| Numbering | IMGT-based domain numbering (internal) |

### Training Data

| Property | Details |
|----------|---------|
| PLM pre-training | ESM-2 trained on UniRef50 (~250M sequences) |
| Antibody fine-tuning | Paired antibody structures from structural databases |
| TCR fine-tuning | Alpha/beta TCR structures |
| Antigen handling | Antibody-antigen complexes for complex prediction |
| Domain detection | Internal IMGT-based renumbering pipeline |

### Loss Function & Objective

ImmuneFold is trained with a combination of:
- Frame-Aligned Point Error (FAPE) loss for structural accuracy
- pTM (predicted TM-score) auxiliary loss for confidence calibration
- pLDDT (predicted local distance difference test) loss for per-residue confidence

### Tokenization / Input Processing

- **Antibody input**: `H` (heavy chain), `L` (light chain, optional for nanobodies)
- **TCR input**: `B` (beta), `A` (alpha), `P` (peptide), `M` (MHC)
- **Antigen PDB**: Optional PDB string for antibody-antigen complex prediction
- **Sequence validation**: Extended amino acid alphabet; min lengths enforced (VH >= 90, VL >= 85 AA) to ensure IMGT numbering success
- **Type inference**: Automatically inferred from chain combination:
  - H + L => antibody (paired)
  - H only => nanobody
  - B + A + P + M => TCR
- **Internal processing**: FASTA-format intermediate files; Hydra-based config system

## Performance & Benchmarks

### Published Benchmarks

From Wu et al., *bioRxiv* (2024):

#### Antibody Structure Prediction

| Model | CDR-H3 RMSD (A) | Overall RMSD (A) | Notes |
|-------|------------------|-------------------|-------|
| **ImmuneFold** | **~2.0** | **~1.2** | PLM-enhanced |
| ABodyBuilder2 | ~2.8 | ~1.5 | ImmuneBuilder |
| AlphaFold2 | ~3.4 | ~1.8 | General-purpose |

#### TCR Structure Prediction

| Model | CDR3-beta RMSD (A) | Notes |
|-------|---------------------|-------|
| **ImmuneFold** | **~1.8** | PLM-enhanced |
| TCRBuilder2 | ~2.2 | ImmuneBuilder |

### BioLM Verification Results

| Variant | Test Case | Tolerance | Status |
|---------|-----------|-----------|--------|
| antibody | Paired VH/VL | rel_tol 1e-4, PDB RMSD < 1e-4A | PASS |
| antibody | Nanobody (VH only) | rel_tol 1e-4, PDB RMSD < 1e-4A | PASS |
| antibody | Antigen complex | rel_tol 1e-4, PDB RMSD < 1e-4A | PASS |
| tcr | Alpha/beta TCR | rel_tol 1e-4, PDB RMSD < 1e-4A | PASS |

### Comparison to Alternatives

| Model | Strength | When to prefer |
|-------|----------|----------------|
| **ImmuneFold** | PLM-enhanced; highest accuracy on immune proteins | When accuracy matters most; antibody-antigen complexes |
| ImmuneBuilder | Faster; CPU-only; no GPU required | Quick predictions; resource-constrained environments |
| AlphaFold2 | Handles any protein | Non-immune proteins |
| ESMFold | Very fast | Rapid screening when accuracy is less critical |

## Strengths & Limitations

### Pros

- Highest accuracy for antibody CDR-H3 prediction among single-sequence methods
- Supports antibody-antigen complex prediction with antigen PDB input
- Confidence scores (pTM, pLDDT) for prediction quality assessment
- Supports nanobodies (VH-only) and TCRs in addition to paired antibodies
- ESM-2 backbone captures evolutionary information without MSA

### Cons

- Requires GPU (T4) due to ESM-2 3B model -- larger resource footprint than ImmuneBuilder
- Minimum sequence lengths enforced (VH >= 90, VL >= 85 AA) for IMGT numbering
- Maximum sequence length of 256 AA per chain (512 for unpaired)
- Relies on external Hydra config system and cloned GitHub repository
- Domain numbering failures on unusual sequences produce assertion errors

### Known Failure Modes

- Sequences shorter than minimum lengths (VH < 90, VL < 85) fail domain numbering
- Non-standard immune protein sequences that cannot be assigned IMGT numbering
- Very long sequences exceeding 256 AA per chain
- TCR inputs that lack all four required chains (B, A, P, M)

## Implementation Details

### Inference Pipeline

```
Request
  |-- 1. Validate sequences (amino acid alphabet, length constraints)
  |-- 2. Infer type from chain combination (antibody/nanobody/TCR)
  |-- 3. Write FASTA file with appropriate header
  |-- 4. If antigen PDB provided, write PDB file
  |-- 5. Load Hydra config with model-specific overrides
  |-- 6. Run ImmuneFold inference (ESM-2 encoding -> structure prediction)
  |-- 7. Read output PDB and confidence scores
  |-- 8. Clean up temporary files
  |-- 9. Return PDB string, pTM, full pLDDT, per-residue pLDDT
```

### Memory & Compute Profile

| Resource | Value |
|----------|-------|
| GPU | T4 (16 GB VRAM) |
| Memory | 16 GB RAM |
| CPU | 3.0 cores |
| Batch size | 32 |
| Max sequence length | 256 per chain |

### Determinism & Reproducibility

| Setting | Value |
|---------|-------|
| Torch manual seed | Yes (42 at model load) |
| CUDA manual seed | Yes (42, if available) |
| ESM-2 eval mode | Enabled |

### Caching Behavior

Standard BioLM caching via `BillingMixinSnap`:
- Redis (Modal Dict) caching for fast repeated lookups
- R2 caching for persistence

## Versions & Changelog

| Version | Date | Changes |
|---------|------|---------|
| v1 | 2025 | Initial implementation with antibody and TCR variants |

---

*See also: [README.md](README.md) for API reference | [BIOLOGY.md](BIOLOGY.md) for biological context*
