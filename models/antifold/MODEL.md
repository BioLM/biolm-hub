# AntiFold  --  Technical Details

## Architecture

### Model Type & Innovation

AntiFold is an antibody-specific inverse folding model built by fine-tuning ESM-IF1 (Inverse Folding) on paired antibody-antigen structural data. While ESM-IF1 is a general-purpose protein inverse folding model, AntiFold specializes it for antibody sequences by training on antibody-antigen complexes from the Structural Antibody Database (SAbDab) with IMGT-numbered residues.

The key innovation is that AntiFold conditions sequence predictions on the 3D backbone structure of the antibody, including the antigen context when available. This allows it to propose amino acid substitutions that are structurally compatible with the antibody fold while maintaining or improving binding properties. Unlike sequence-only models, AntiFold captures the geometric constraints imposed by the CDR loop conformations.

The model uses a GNN-based encoder (from ESM-IF1) that processes backbone coordinates to produce structure-conditioned representations, followed by an autoregressive decoder that generates amino acid probabilities at each position.

### Parameters & Layers

| Component | Details |
|-----------|---------|
| Architecture | GNN encoder + autoregressive decoder (ESM-IF1 backbone) |
| Base model | ESM-IF1 (ESM Inverse Folding 1) |
| Fine-tuning | Antibody-antigen complexes from SAbDab |
| Embedding dimensions | 512 |
| Vocabulary | 20 standard amino acids |
| Input | Backbone atom coordinates (N, CA, C, O) from PDB structures |
| Output | Per-residue amino acid log-probabilities |

### Training Data

| Property | Details |
|----------|---------|
| Base model training | ESM-IF1 trained on CATH 4.3 structures (12M backbones from ~19K structures) |
| Fine-tuning dataset | SAbDab (Structural Antibody Database) antibody-antigen complexes |
| Numbering scheme | IMGT (ImMunoGeneTics) numbering |
| Chain types | Heavy chain (VH), light chain (VL), nanobody (VHH) |
| Antigen context | Optional antigen chain included during training |
| Data augmentation | Structural noise and masking strategies for robust learning |

### Loss Function & Objective

AntiFold is trained with a cross-entropy loss over the 20 standard amino acid types at each residue position, conditioned on the 3D backbone coordinates. The training objective is:

```
L = -sum_i log P(aa_i | backbone_coordinates, context)
```

where the sum runs over all residue positions in the antibody chain(s) and the context includes neighboring residues and optional antigen coordinates.

### Tokenization / Input Processing

- **Input format**: PDB-format structure strings containing backbone atom coordinates
- **Chain specification**: Users specify heavy chain, light chain (or nanobody chain), and optionally antigen chain by PDB chain ID
- **Coordinate extraction**: Backbone atoms (N, CA, C, O) are extracted per residue using Biotite
- **IMGT numbering**: Residues are mapped to IMGT positions for consistent CDR/framework region identification
- **Multi-chain handling**: Heavy and light chains are processed together; antigen chain provides structural context
- **Graph construction**: Backbone coordinates are converted to a graph representation for the GNN encoder

## Performance & Benchmarks

### Published Benchmarks

#### Inverse Folding Recovery Rate

AntiFold reports improved sequence recovery rates compared to ESM-IF1 and ProteinMPNN on antibody CDR regions:

| Model | CDR-H3 Recovery ↑ | Overall Recovery ↑ | Notes |
|-------|-------------------|-------------------|-------|
| **AntiFold** | **~38%** | **~45%** | Antibody-specific fine-tuning |
| ESM-IF1 | ~28% | ~38% | General protein inverse folding |
| ProteinMPNN | ~30% | ~40% | General protein design |

Results are from the AntiFold paper (Hoie et al., 2024), evaluated on held-out SAbDab structures.

### BioLM Verification Results

The BioLM implementation is verified against the original AntiFold codebase using test structures from PDB:

| Test Structure | Action | Verification | Status |
|---------------|--------|-------------|--------|
| 3HFM | encode | Cosine distance < 0.02, rel_tol 3e-4 | PASS |
| 8OI2 (IMGT) | encode | Cosine distance < 0.02, rel_tol 3e-4 | PASS |
| 3HFM | predict_log_prob | rel_tol 1e-4 | PASS |
| 3HFM | score | rel_tol 1e-4 | PASS |
| 3HFM | generate | Structure validation (sequence count) | PASS |
| 8OI2 (IMGT) | generate | Structure validation (sequence count) | PASS |
| 6Y1L (IMGT) | generate | Structure validation (sequence count) | PASS |

### Comparison to Alternatives

| Model | Task | Strength | When to prefer |
|-------|------|----------|----------------|
| **AntiFold** | Antibody inverse folding | Antibody-specific, CDR-aware | Antibody/nanobody design |
| ESM-IF1 | General inverse folding | Broader protein coverage | Non-antibody proteins |
| ProteinMPNN | General inverse folding | Robust, well-validated | General protein design |

## Strengths & Limitations

### Pros

- Antibody-specialized: significantly better CDR sequence recovery than general inverse folding models
- Supports both conventional antibodies (VH/VL) and nanobodies (VHH)
- Antigen-aware: can condition sequence design on the antigen interface
- Region-specific design: users can target specific CDRs, framework regions, or individual positions
- Lightweight: runs on CPU (no GPU required), making it cost-effective
- Provides multiple output types: sequences, embeddings, log-probabilities, and per-position logits

### Cons

- Limited to antibody and nanobody structures; not suitable for general proteins
- Requires a 3D structure as input (PDB format), not sequence-only
- Based on IMGT numbering; structures must be IMGT-numbered or compatible
- Single variant only (no model size options)
- CDR-H3 is inherently difficult to predict due to high structural diversity

### Known Failure Modes

- Structures with unusual or non-standard IMGT numbering may produce incorrect region assignments
- Very long CDR-H3 loops (>20 residues) may have lower prediction quality
- Antigen chains that are far from the antibody paratope provide minimal useful context
- PDB files with missing backbone atoms will cause processing errors

## Implementation Details

### Inference Pipeline

```
Request
  |-- 1. Validate PDB string and chain IDs
  |-- 2. Write PDB to temporary file
  |-- 3. Build input DataFrame (chain assignments)
  |-- 4. Extract backbone coordinates (Biotite)
  |-- 5. Construct graph representation
  |-- 6. Forward pass through GNN encoder
  |-- 7. Autoregressive decoding (for generate) or single-pass (for encode/score)
  |-- 8. Post-process outputs (logits, embeddings, sequences)
  |-- 9. Clean up temporary files
  |-- 10. Format and return response
```

### Memory & Compute Profile

| Resource | Value |
|----------|-------|
| GPU | None (CPU-only) |
| Memory | 2 GB RAM |
| CPU | 1.0 cores |
| Batch size (encode/score/predict_log_prob) | 32 |
| Batch size (generate) | 1 |

The model runs entirely on CPU, which is sufficient given the relatively small model size. The GNN encoder processes backbone coordinates efficiently without requiring GPU acceleration.

### Determinism & Reproducibility

| Setting | Value |
|---------|-------|
| Torch manual seed | Yes (42 at model load) |
| CUDA manual seed | Yes (42, if available) |
| NumPy seed | Set per-request for generate |
| User-specified seed | Supported via `seed` parameter in generate |

The `encode`, `score`, and `predict_log_prob` actions are deterministic. The `generate` action is stochastic by default (time-based seed) but can be made reproducible by providing a `seed` parameter.

### Caching Behavior

Standard BioLM caching is applied via the `BillingMixinSnap` base class:

- Redis (Modal Dict) caching for fast repeated lookups
- R2 caching for persistence
- Cache keys are determined by the full request payload (PDB content + parameters)

## Versions & Changelog

| Version | Date | Changes |
|---------|------|---------|
| v1 | 2024 | Initial implementation with encode, generate, score, predict_log_prob actions |

---

*See also: [README.md](README.md) for API reference | [BIOLOGY.md](BIOLOGY.md) for biological context*
