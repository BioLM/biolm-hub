# Evo  --  Technical Details

## Architecture

### Model Type & Innovation

Evo is a **7-billion parameter autoregressive language model** for DNA sequences. Unlike the majority of biological sequence models that use the Transformer architecture, Evo is built on **StripedHyena**  --  a hybrid architecture combining gated convolutions with multi-head attention. This is a key architectural innovation: StripedHyena replaces the standard quadratic self-attention mechanism with a combination of hyena operators (long convolutions parameterized implicitly) and a reduced number of attention layers. The result is **near-linear scaling** with sequence length, enabling Evo to process contexts up to 131,072 nucleotides  --  far beyond what standard Transformers can handle efficiently.

The StripedHyena architecture interleaves:
- **Hyena layers**: Use implicitly parameterized long convolutions for efficient sequence mixing with sub-quadratic complexity.
- **Attention layers**: Standard multi-head attention inserted periodically (every few layers) to preserve the model's ability to capture precise long-range dependencies.

This hybrid design allows Evo to operate at **byte-level tokenization** (single nucleotide resolution) without the prohibitive cost that would come from running full attention over sequences of 100k+ tokens.

### Parameters & Layers

| Component | Details |
|-----------|---------|
| Architecture | StripedHyena (hybrid gated convolution + attention) |
| Total parameters | ~7 billion |
| Tokenization | Byte-level (character-level), single nucleotide tokens |
| Vocabulary | DNA bases: A, C, G, T (plus special tokens) |
| Context lengths | 8,192 (8k variants) or 131,072 (131k variant) |
| Positional encoding | Implicit via convolutional filters (Hyena layers); RoPE in attention layers |

### Training Data

| Property | Details |
|----------|---------|
| Dataset | OpenGenome |
| Composition | Prokaryotic and phage genomes spanning diverse taxonomic groups |
| Sequence type | Whole-genome DNA sequences |
| Scale | ~300 billion tokens of DNA sequence data |
| Preprocessing | Byte-level tokenization; no k-mer encoding or BPE |

The OpenGenome dataset was curated to provide broad coverage of microbial genomic diversity. Evo 1.5 was trained on approximately 50% more data than the original Evo 1 release, improving general DNA modeling capability.

**Known biases:**
- Training data is heavily weighted toward prokaryotic genomes. Performance on eukaryotic sequences (especially large mammalian genomes) may be lower.
- Viral and phage genomes are included but represent a smaller fraction of the training distribution.
- No explicit inclusion of synthetic sequences or engineered constructs.

### Loss Function & Objective

Evo is trained with a standard **autoregressive (next-token prediction) objective**:

```
L = -sum_{t=1}^{T} log P(x_t | x_{<t})
```

At each position, the model predicts the probability distribution over the next nucleotide given all preceding nucleotides. This objective naturally yields both:
- **Generative capability**: Sample new sequences by iteratively predicting the next token.
- **Scoring capability**: Evaluate the log-probability of an existing sequence under the learned distribution.

### Tokenization / Input Processing

Evo uses **byte-level (character-level) tokenization**, where each DNA nucleotide (A, C, G, T) is a single token. This is distinct from k-mer or BPE tokenization used by some other genomic models.

- **Token vocabulary**: A, C, G, T, plus special tokens (BOS)
- **No subword encoding**: Each nucleotide maps to exactly one token
- **Maximum sequence length**: 4,096 nucleotides (BioLM API cap; the underlying model supports 8,192 for the 8k variant)
- **Input validation**: Only unambiguous DNA bases (A, C, G, T) are accepted; ambiguity codes (N, R, Y, etc.) are rejected

The byte-level approach preserves single-nucleotide resolution, which is essential for tasks like scoring point mutations or generating sequences where every base matters.

## Performance & Benchmarks

### Published Benchmarks

From the primary paper (Nguyen et al., Science 2024):

#### Zero-Shot Fitness Prediction

Evo was evaluated on zero-shot prediction of variant fitness across multiple experimental datasets, using per-sequence log-probabilities as the fitness proxy.

| Benchmark | Metric | Evo Performance | Notes |
|-----------|--------|----------------|-------|
| Prokaryotic DMS datasets | Spearman rho | Competitive with protein LMs | DNA-level scoring without protein translation |
| ProteinGym (prokaryotic subset) | Spearman rho | Comparable to ESM-1v on relevant targets | First DNA model evaluated on protein fitness |

#### Gene Essentiality Prediction

Evo's log-probabilities correlate with gene essentiality in prokaryotic genomes, demonstrating that the model captures functional constraint signals.

| Benchmark | Metric | Evo Performance | Notes |
|-----------|--------|----------------|-------|
| Bacterial gene essentiality | AUROC | Discriminates essential vs. non-essential | Log-prob scores reflect functional constraint |

#### Sequence Generation Quality

Generated sequences were evaluated for:
- Codon usage statistics matching natural genomes
- Predicted protein structure quality (using ESMFold) for genes within generated sequences
- Realistic genomic organization (operon-like gene arrangements)

| Evaluation Criterion | Metric | Result |
|---------------------|--------|--------|
| Protein structure plausibility | ESMFold pTM of encoded ORFs | Generated proteins show plausible folds |
| Codon usage | KL divergence vs. natural genomes | Comparable to natural prokaryotic sequences |
| Genomic organization | Operon-like gene clustering | Realistic multi-gene arrangements observed |

*Note: Exact numerical values require extraction from the paper figures. The above summarizes qualitative findings reported in the text.*

### BioLM Verification Results

| Action | Test Input | Tolerance | Status |
|--------|-----------|-----------|--------|
| `log_prob` | "ACGTAC", "ACGTACGTAC" | rel_tol=1e-4 | Verified via fixture tests |
| `generate` | Prompt "ACGT", 100 tokens | Generated sequence check | Verified via fixture tests |

### Comparison to Alternatives

| Model | Molecule | Task | When to prefer |
|-------|----------|------|----------------|
| **Evo** | DNA | Generation, scoring | Genome-scale DNA generation; long-context scoring |
| Nucleotide Transformer | DNA | Embeddings, classification | When you need per-token embeddings for downstream classifiers |
| DNABERT | DNA | Classification, variant effect | Short regulatory element analysis |

## Strengths & Limitations

### Pros

- **Long-context capability**: Handles sequences up to 131k nucleotides (with the 131k variant), enabling genome-scale modeling in a single forward pass.
- **Near-linear scaling**: StripedHyena architecture avoids the quadratic memory cost of full attention, making long sequences practical.
- **Byte-level resolution**: Single-nucleotide tokenization preserves full sequence fidelity, critical for mutation-level analysis.
- **Dual-use (generation + scoring)**: A single model supports both sequence generation and log-probability scoring without separate fine-tuning.
- **Diverse training data**: OpenGenome covers broad prokaryotic diversity, giving strong generalization across microbial genomes.

### Cons

- **Prokaryotic bias**: Trained primarily on prokaryotic genomes; eukaryotic sequences (especially large mammalian genomes) are underrepresented.
- **No embedding extraction endpoint**: Unlike ESM2 or Nucleotide Transformer, Evo does not expose per-token embeddings for downstream use.
- **Large model footprint**: At 7B parameters, Evo requires a GPU (L4) and has higher cold-start and inference costs than smaller models.
- **Generation is stochastic**: Generated sequences vary between runs unless a seed is provided, making reproducibility require explicit seed management.

### Known Failure Modes

- **Eukaryotic regulatory sequences**: Promoters, enhancers, and splicing signals from eukaryotic genomes may be poorly modeled due to training data composition.
- **Repetitive sequences**: Extremely repetitive regions (microsatellites, tandem repeats) may receive unexpectedly high or low scores.
- **Very short sequences**: Sequences under ~10 nucleotides provide minimal context for meaningful log-probability estimates.

## Implementation Details

### Inference Pipeline

```
Request
  |-- 1. Validate input (DNA bases only, length <= 4096)
  |-- 2. Route to action:
  |
  |-- [log_prob]
  |     |-- Tokenize sequences (CharLevelTokenizer)
  |     |-- Forward pass through StripedHyena model
  |     |-- Gather per-position log-probabilities
  |     |-- Sum log-probs across positions per sequence
  |     |-- Return total log-prob per sequence
  |
  |-- [generate]
        |-- Set random seeds (user-provided or time-based)
        |-- Tokenize prompt
        |-- Autoregressive sampling (temperature, top-k, top-p)
        |-- Cached generation for efficiency
        |-- Return generated sequence + average score
```

### Memory & Compute Profile

| Property | Value |
|----------|-------|
| GPU | L4 |
| Memory | 8 GB |
| CPU | 4 cores |
| Model size on disk | ~14 GB (FP16 weights) |
| Cold start | Reduced via Modal memory snapshots (GPU snapshot enabled) |

### Determinism & Reproducibility

**`log_prob`**: Deterministic. The forward pass is a pure function of the input with no random components.

**`generate`**: Stochastic by default, but reproducible with explicit seed control.

| Seed source | Behavior |
|-------------|----------|
| `seed=None` (default) | Time-based entropy; different output each call |
| `seed=<int>` (user-provided) | Reproducible output for identical inputs |

When a seed is provided, the implementation sets:
- `random.seed(seed)`
- `np.random.seed(seed)`
- `torch.manual_seed(seed)`
- `torch.cuda.manual_seed_all(seed)`

### Caching Behavior

Response caching is handled outside the model container by the serving infrastructure:
- Cache key is derived from the full request payload (including parameters)
- For `generate` with no seed (stochastic), cache misses are expected on repeated calls since the time-based seed differs

## Versions & Changelog

| Version | Date | Changes |
|---------|------|---------|
| v1 (params_version) | 2025-02 | Initial implementation with `log_prob` and `generate` actions; Evo 1.5-8k-base variant |

---

*See also: [README.md](README.md) for API reference | [BIOLOGY.md](BIOLOGY.md) for biological context*
