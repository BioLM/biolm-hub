# ESM-IF1 -- Technical Details

## Architecture

### Model Type & Innovation

ESM-IF1 (ESM Inverse Folding 1) is a general-purpose protein inverse folding model from Meta AI (Hsu et al. 2022). Given a protein backbone structure, it generates amino acid sequences that are predicted to fold into that structure. The key innovation is training on millions of predicted structures from AlphaFold2 in addition to experimentally determined structures, which dramatically improves performance compared to models trained on experimental data alone.

The architecture consists of a GVP-Transformer encoder that processes backbone coordinates using Geometric Vector Perceptrons (GVPs) to capture 3D structural information, followed by an autoregressive Transformer decoder that generates amino acid sequences one position at a time, conditioned on the structural encoding.

### Parameters & Layers

| Component | Details |
|-----------|---------|
| Architecture | GVP-Transformer (GNN encoder + autoregressive decoder) |
| Model name | `esm_if1_gvp4_t16_142M_UR50` |
| Parameters | 142M |
| Encoder | GVP-Transformer with 4 GVP layers |
| Decoder | 16-layer Transformer |
| Input | Backbone atom coordinates (N, CA, C) from PDB structures |
| Output | Sampled amino acid sequences with per-sequence recovery rates |
| Vocabulary | 20 standard amino acids |

### Training Data

| Property | Details |
|----------|---------|
| Experimental structures | CATH 4.3 (~19K protein structures) |
| Predicted structures | 12M AlphaFold2 backbone structures from UniRef50 |
| Total training backbones | ~12M |
| Key innovation | Training on predicted structures dramatically improves performance |

### Loss Function & Objective

ESM-IF1 is trained with autoregressive cross-entropy loss:

```
L = -sum_i log P(aa_i | aa_1, ..., aa_{i-1}, backbone_coordinates)
```

The model learns to predict each amino acid conditioned on all previously generated amino acids and the full 3D backbone structure. The autoregressive formulation allows the model to capture sequence dependencies beyond what the structure alone encodes.

### Tokenization / Input Processing

- **Input format**: PDB-format structure string containing backbone atom coordinates
- **Coordinate extraction**: Backbone atoms (N, CA, C) are extracted per residue using Biotite
- **Chain specification**: Users specify which chain to redesign via the `chain` parameter (default: "A")
- **Graph construction**: Backbone coordinates are converted to a GVP-compatible graph representation
- **Batching**: Single structure per request (batch_size=1) due to variable structure sizes

## Performance & Benchmarks

### Published Benchmarks

From Hsu et al., *ICML* (2022):

| Model | Sequence Recovery (%) ↑ | Training Data |
|-------|------------------------|---------------|
| **ESM-IF1** | **51.0** | CATH + 12M AF2 structures |
| ProteinMPNN | 52.4 | CATH experimental only |
| GVP | 39.4 | CATH experimental only |
| StructGNN | 35.0 | CATH experimental only |
| GraphTrans | 34.8 | CATH experimental only |

Note: ProteinMPNN achieves slightly higher recovery on experimental structures, but ESM-IF1's training on predicted structures gives it broader coverage of the protein structure space.

### BioLM Verification Results

| Test Case | Action | Tolerance | Status |
|-----------|--------|-----------|--------|
| Standard PDB structure | generate | rel_tol 0.5, is_generated_seq=True | PASS |

Sequence generation is stochastic, so verification confirms that generated sequences are valid amino acid strings with reasonable recovery rates, rather than exact numerical reproduction.

### Comparison to Alternatives

| Model | Strength | When to prefer |
|-------|----------|----------------|
| **ESM-IF1** | General protein coverage, trained on 12M structures | General protein sequence design from structure |
| ProteinMPNN | Slightly higher recovery on experimental structures | Standard protein design, multi-chain |
| AntiFold | Antibody-specialized, CDR-aware | Antibody-specific inverse folding |

## Strengths & Limitations

### Pros

- General-purpose: works on any single-chain protein structure
- Trained on 12M structures (experimental + AlphaFold2 predicted)
- Controllable diversity via temperature parameter
- Multiple samples per structure for exploring sequence space
- Provides sequence recovery metric for each sample

### Cons

- Single-chain only (multichain backbone support not yet implemented)
- Stochastic output: different runs produce different sequences
- Batch size limited to 1 (one PDB per request)
- Autoregressive decoding is inherently sequential (slower than parallel methods)
- Requires a 3D structure as input (PDB format)

### Known Failure Modes

- Very large structures may cause CUDA out-of-memory errors (handled gracefully with empty result and cache clearing)
- Structures with missing backbone atoms or non-standard formatting may cause parsing errors
- Very high temperatures (>4.0) produce near-random sequences
- Very low temperatures (<0.1) collapse diversity to near-deterministic output

## Implementation Details

### Inference Pipeline

```
Request
  |-- 1. Validate PDB string
  |-- 2. Set random seeds (user-provided or time-based)
  |-- 3. Extract backbone coordinates (N, CA, C) using Biotite
  |-- 4. For each sample (1 to num_samples):
  |     |-- 4a. Encode backbone with GVP-Transformer
  |     |-- 4b. Autoregressively decode amino acid sequence
  |     |-- 4c. Compute sequence recovery vs native
  |-- 5. Collect all samples with sequences and recovery rates
  |-- 6. Handle CUDA OOM errors gracefully
  |-- 7. Format and return response
```

### Memory & Compute Profile

| Resource | Value |
|----------|-------|
| GPU | T4 |
| Memory | 16 GB RAM |
| CPU | 4.0 cores |
| Batch size | 1 |
| Max samples per request | 3 |

### Determinism & Reproducibility

| Setting | Value |
|---------|-------|
| Default seed | Time-based (non-deterministic) |
| User-specified seed | Supported via `params.seed` |
| Seed scope | Python random, NumPy, Torch, CUDA |

When no seed is provided, the model uses time-based entropy for diversity across requests. Providing a seed enables exact reproducibility of generated sequences.

### Caching Behavior

Response caching is available as an optional, off-by-default gateway feature (`BIOLM_CACHE_ENABLED`) -- see the gateway docs; it is not handled by the model container. Cache keys are determined by the full request payload (PDB content + parameters + seed).

## Versions & Changelog

| Version | Date | Changes |
|---------|------|---------|
| v1 | 2024 | Initial implementation with generate action |

---

*See also: [README.md](README.md) for API reference | [BIOLOGY.md](BIOLOGY.md) for biological context*
