# AbodyBuilder3 -- Technical Details

## Architecture

### Model Type & Innovation

AbodyBuilder3 is an antibody structure prediction model developed by Exscientia (Kenlay et al. 2024). It predicts the 3D structure of antibody Fv regions (paired heavy and light chains) from sequence alone. The key innovation is a scalable architecture that achieves accuracy comparable to AlphaFold2-based methods while being significantly faster and more resource-efficient.

AbodyBuilder3 uses a graph neural network (GNN) architecture that processes antibody sequence features to predict backbone and side-chain atom coordinates. It operates in two variants: a "language" variant that incorporates ProtT5 protein language model embeddings for higher accuracy, and a "plddt" variant that uses a lighter-weight approach with confidence estimation (pLDDT scores).

### Parameters & Layers

| Component | Details |
|-----------|---------|
| Architecture | Graph Neural Network (GNN) |
| Language variant | GNN + ProtT5 language model embeddings |
| pLDDT variant | GNN with confidence estimation (no language model) |
| Input | Paired `heavy_chain` and `light_chain` amino acid sequences |
| Output | PDB structure string, optional per-residue pLDDT scores |
| Framework | PyTorch Lightning (LitABB3 module) |

### Training Data

| Property | Details |
|----------|---------|
| Source | Structural Antibody Database (SAbDab) |
| Structure type | Antibody Fv region crystal structures |
| Training approach | Two-stage training with checkpoint selection |

### Loss Function & Objective

AbodyBuilder3 uses a structure prediction loss that optimizes predicted atom positions against experimentally determined crystal structures. The two-stage training process refines the model progressively, with the best checkpoint from the second stage selected for deployment.

### Tokenization / Input Processing

- **Input format**: Paired `heavy_chain` and `light_chain` amino acid sequences (strings)
- **Validation**: Extended amino acid alphabet
- **Maximum length**: 2048 residues per chain
- **Language variant**: Sequences are additionally processed through ProtT5 to obtain per-residue language model embeddings, which are concatenated with the GNN input features
- **Graph construction**: Sequences are converted to graph representations using `string_to_input` utility from the AbodyBuilder3 library

## Performance & Benchmarks

### Published Benchmarks

From Kenlay et al., *Bioinformatics* (2024):

| Model | CDR-H3 RMSD (A) | Overall RMSD (A) | Speed |
|-------|-----------------|-------------------|-------|
| **AbodyBuilder3 (language)** | **Competitive** | **Competitive** | Fast |
| AlphaFold2 (antibody mode) | Best | Best | Slow |
| IgFold | Moderate | Moderate | Moderate |
| ABlooper | CDR-only | N/A | Fast |

<!-- TODO: Add specific numerical RMSD values from the AbodyBuilder3 paper Table 1 once PDF is available in R2 -- see sources.yaml pdf_r2 -->

### BioLM Verification Results

| Test Case | Action | Tolerance | Status |
|-----------|--------|-----------|--------|
| Standard antibody pair | fold | rel_tol 1e-3, cosine_distance < 0.02, pdb_rmsd < 0.05 A | PASS |

### Comparison to Alternatives

| Model | Strength | When to prefer |
|-------|----------|----------------|
| **AbodyBuilder3** | Fast, accurate antibody structure prediction | High-throughput antibody modeling |
| AlphaFold2 | Highest accuracy for general proteins | When maximum accuracy needed, speed not critical |
| IgFold | Good antibody structure prediction | Alternative antibody-specific predictor |
| ESMFold | Fast general protein structure | Non-antibody proteins |
| Boltz | State-of-the-art biomolecular structure | Complex biomolecular assemblies |

## Strengths & Limitations

### Pros

- Fast antibody structure prediction relative to AlphaFold2-based methods
- Two variants allow accuracy/speed tradeoff (language vs pLDDT)
- Outputs standard PDB format directly
- Optional pLDDT confidence scores for per-residue quality assessment
- Deterministic predictions (seeded for reproducibility)

### Cons

- Limited to antibody Fv regions (heavy and light chain pairs only)
- Does not predict antigen binding or antibody-antigen complex structures
- Language variant requires GPU (L40S) for ProtT5 embedding computation
- Does not support nanobodies (single-chain antibodies)
- Batch size limited to 4 per request

### Known Failure Modes

- Unusual CDR-H3 loop conformations (very long or highly constrained) may have lower prediction accuracy
- Sequences with non-standard residues may cause processing errors
- The pLDDT variant may produce lower-quality structures compared to the language variant

## Implementation Details

### Inference Pipeline

```
Request
  |-- 1. Validate paired H/L chain sequences
  |-- 2. Seed all random number generators for determinism
  |-- 3. Convert sequences to graph input (string_to_input)
  |-- 4. [language variant] Compute ProtT5 embeddings
  |-- 5. Batch input and transfer to device
  |-- 6. Forward pass through GNN model
  |-- 7. Add atom37 representation to output
  |-- 8. Convert output to PDB string
  |-- 9. [if plddt=True] Extract per-residue pLDDT scores
  |-- 10. Format and return response
```

### Memory & Compute Profile

| Resource | Language Variant | pLDDT Variant |
|----------|-----------------|---------------|
| GPU | L40S (48 GB VRAM) | None (CPU-only) |
| Memory | 12 GB RAM | 8 GB RAM |
| CPU | 4.0 cores | 2.0 cores |
| Batch size | 4 | 4 |

### Determinism & Reproducibility

| Setting | Value |
|---------|-------|
| Torch manual seed | Yes (42 at model load, configurable per request) |
| CUDA manual seed | Yes (42) |
| NumPy seed | Yes (per request) |
| PyTorch Lightning seed | Yes (per request) |
| cuDNN deterministic | Yes |
| cuDNN benchmark | Disabled |
| Request-level seed | Configurable via `params.seed` (default: 42) |

### Caching Behavior

Response caching (Redis/R2 two-tier) is handled by the BioLM platform layer, not by the model container:
- Redis (Modal Dict) caching for fast repeated lookups
- R2 caching for persistence
- Cache keys determined by full request payload (sequences + parameters)

## Versions & Changelog

| Version | Date | Changes |
|---------|------|---------|
| v1 | 2024 | Initial implementation with language and plddt variants |

---

*See also: [README.md](README.md) for API reference | [BIOLOGY.md](BIOLOGY.md) for biological context*
