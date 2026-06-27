# Evo2 -- Technical Details

## Architecture

### Model Type & Innovation

Evo 2 is a **large-scale autoregressive DNA foundation model** developed by the Arc Institute, Stanford, and collaborators. It is the successor to Evo 1 and represents a major scaling advance in genomic language modeling. Evo 2 extends the StripedHyena hybrid architecture -- combining gated convolutions (Hyena operators) with multi-head attention -- to model sizes of 1B, 7B, and 40B parameters.

The key innovations of Evo 2 over its predecessor include:
- **Massive scaling**: From 7B (Evo 1) to 40B parameters, demonstrating continued scaling benefits for genomic modeling
- **Multi-domain training**: Trained on genomes from all domains of life (prokaryotes, eukaryotes, and viruses), unlike Evo 1 which focused on prokaryotic genomes
- **Embedding extraction**: Unlike Evo 1, Evo 2 exposes per-layer embedding extraction via the `encode` action, enabling use as a feature extractor for downstream tasks
- **Three-action API**: Supports embedding extraction, log-probability scoring, and sequence generation in a single model

### Parameters & Layers

| Variant | Parameters | Context | Architecture | GPU |
|---------|-----------|---------|--------------|-----|
| evo2-1b-base | ~1B | 8k nt | StripedHyena | L4 |
| evo2-7b-base | ~7B | 8k nt | StripedHyena | L4 |

Additional variants defined but not currently deployed: evo2-7b (1M context), evo2-40b-base (8k), evo2-40b (1M context).

Common across all variants:

| Property | Value |
|----------|-------|
| Architecture | StripedHyena (hybrid gated convolution + attention) |
| Tokenization | Byte-level (single nucleotide per token) |
| Vocabulary | A, C, G, T + special tokens |
| Positional encoding | Implicit via convolutional filters + RoPE in attention layers |

### Training Data

| Property | Details |
|----------|---------|
| Dataset | Multi-domain genomic sequences |
| Composition | Prokaryotic, eukaryotic, and viral genomes |
| Preprocessing | Byte-level tokenization; single nucleotide per token |

<!-- TODO: Extract exact dataset size and composition from Brixi et al. 2025 when full paper is published -->

### Loss Function & Objective

Standard autoregressive (next-token prediction) objective:

```
L = -sum_{t=1}^{T} log P(x_t | x_{<t})
```

This yields both generative capability (sampling new sequences) and scoring capability (evaluating log-probability of existing sequences).

### Tokenization / Input Processing

| Property | Details |
|----------|---------|
| Tokenizer | Byte-level (character-level), single nucleotide tokens |
| Special tokens | BOS, PAD |
| Max sequence length | 4,096 nt (BioLM API limit) |
| Input validation | A, C, G, T only (unambiguous DNA) |
| Batch size | 1 sequence per request |

## Performance & Benchmarks

### Published Benchmarks

From Brixi et al. "Genome modeling and design across all domains of life with Evo 2" (bioRxiv, 2025):

<!-- TODO: Extract specific numerical benchmarks from Brixi et al. when full paper is available -->

Key reported findings:
- Evo 2 outperforms Evo 1 on DNA fitness prediction benchmarks
- Multi-domain training improves generalization to eukaryotic sequences
- Scaling from 1B to 40B parameters yields consistent improvements

### BioLM Verification Results

| Action | Test Input | Tolerance | Status |
|--------|-----------|-----------|--------|
| `encode` | "ACGTACGTAC", layer 22 | rel_tol=1e-4 | PASS |
| `log_prob` | "ACGTACGTAC" | rel_tol=1e-4 | PASS |
| `generate` | Prompt "ACGT", 10 tokens | Valid DNA output | PASS |

### Comparison to Alternatives

| Model | Key Advantage | Key Disadvantage |
|-------|---------------|------------------|
| **Evo2 (this)** | Multi-domain training; embeddings + generation + scoring | Larger compute footprint than Evo 1 |
| Evo 1 | Proven in Science 2024; lighter weight | Prokaryotic bias; no embedding endpoint |
| Nucleotide Transformer | 6-mer tokenization captures broader context per token | No generation; encoder-only |
| DNABERT-2 | Lightweight (117M); BPE tokenization | Short context; no generation |

### Error Bars & Confidence

- `encode` and `log_prob` are deterministic for the same input and hardware
- `generate` is stochastic by default; provide explicit `seed` for reproducibility
- Small floating-point differences (within 1e-4) may occur across different GPU architectures

## Strengths & Limitations

### Pros

- Multi-domain training covers prokaryotic, eukaryotic, and viral genomes
- Three complementary actions: embedding extraction, scoring, and generation
- Byte-level tokenization preserves single-nucleotide resolution
- StripedHyena architecture enables near-linear scaling with sequence length
- Multiple model sizes (1B, 7B) allow speed/quality tradeoffs

### Cons

- Large model footprint -- 7B variant requires significant GPU resources
- Max API sequence length of 4,096 nt limits some genomic applications
- Stochastic generation requires explicit seed management for reproducibility
- Newer model with less downstream validation than Evo 1

### Known Failure Modes

- **Very short sequences** (< 10 nt): Insufficient context for meaningful embeddings or log-probabilities
- **Repetitive sequences**: Highly repetitive DNA (microsatellites, tandem repeats) may receive unreliable scores
- **Non-DNA input**: Only A, C, G, T accepted; ambiguity codes and RNA are rejected

## Implementation Details

### Inference Pipeline

```
Request
  |-- 1. Validate input (DNA bases only, length <= 4096)
  |-- 2. Route to action:
  |
  |-- [encode]
  |     |-- Tokenize sequences
  |     |-- Pad batch to max length
  |     |-- Forward pass with return_embeddings=True
  |     |-- Extract requested layers (blocks.N.mlp.l3)
  |     |-- Compute mean/last pooling over non-padded tokens
  |     |-- Return per-layer embeddings
  |
  |-- [log_prob]
  |     |-- Tokenize sequences
  |     |-- model.score_sequences(reduce_method="sum")
  |     |-- Return total log-prob per sequence
  |
  |-- [generate]
        |-- Set random seeds (user-provided or time-based)
        |-- model.generate(cached_generation=True)
        |-- Return generated sequence
```

### Memory & Compute Profile

| Variant | GPU | Memory | CPU |
|---------|-----|--------|-----|
| evo2-1b-base | L4 | 16 GB | 4 cores |
| evo2-7b-base | L4 | 16 GB | 4 cores |

### Determinism & Reproducibility

| Action | Deterministic | Notes |
|--------|---------------|-------|
| `encode` | Yes | Pure forward pass, no randomness |
| `log_prob` | Yes | Uses score_sequences with sum reduction |
| `generate` | With seed | Time-based entropy when seed=None; reproducible with explicit seed |

When a seed is provided for `generate`:
- `random.seed(seed)`, `np.random.seed(seed)`, `torch.manual_seed(seed)`, `torch.cuda.manual_seed_all(seed)`

### Caching Behavior

Response caching (Redis/R2 two-tier) is handled by the BioLM platform layer, not by the model container:
- Cache key derived from full request payload including parameters
- For `generate` with no seed, cache misses are expected on repeated calls

## Versions & Changelog

| Version | Date | Changes |
|---------|------|---------|
| v1 | -- | Initial implementation with encode, log_prob, and generate actions; 1b-base and 7b-base variants |

---

*See also: [README.md](README.md) for API reference | [BIOLOGY.md](BIOLOGY.md) for biological context*
