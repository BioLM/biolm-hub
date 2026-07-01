# ESM C -- Technical Details

## Architecture

### Model Type & Innovation

ESM C (ESM Cambrian) is the latest generation of protein representation models from EvolutionaryScale (2024). It represents a significant advancement over the ESM2 family, achieving comparable or superior performance with substantially fewer parameters and more efficient inference. The "Cambrian" name references the Cambrian explosion of biodiversity, reflecting the model's improved ability to capture the diversity of protein sequence space.

ESM C uses a Transformer architecture optimized for protein sequences, with improvements in training procedure, tokenization, and model scaling that yield better embeddings than ESM2 at equivalent or smaller model sizes. EvolutionaryScale also publishes a 600M variant (also MIT) that approaches the quality of ESM2-3B; it is not distributed in this catalog.

### Parameters & Layers

| Component | Details |
|-----------|---------|
| Architecture | Transformer (optimized for proteins) |
| 300M variant | ~300M parameters |
| Input | Amino acid sequences (up to 2048 residues) |
| Output | Per-residue embeddings, logits over vocabulary, log-probabilities |
| Tokenizer | ESM Cambrian tokenizer (20 canonical amino acids + special tokens) |
| Hidden states | Available at each Transformer layer |

### Training Data

| Property | Details |
|----------|---------|
| Training approach | Large-scale protein language model training |
| Source | EvolutionaryScale proprietary training pipeline |
| Scope | Broad protein sequence databases |

### Loss Function & Objective

ESM C is trained with a language modeling objective optimized for protein sequences. The specific training details are described in the EvolutionaryScale blog post and associated technical documentation.

### Tokenization / Input Processing

- **Input format**: Amino acid sequence strings
- **Encode action**: Accepts extended amino acid alphabet plus gap character (`-`)
- **Predict action**: Accepts extended amino acid alphabet plus `<mask>` token, requires one or more `<mask>` tokens
- **Predict log prob action**: Accepts only the 20 unambiguous amino acids (no mask, no gaps)
- **Maximum length**: 2048 residues
- **Special tokens**: BOS (beginning of sequence) and EOS (end of sequence) tokens are added automatically and removed from output embeddings/logits

## Performance & Benchmarks

### Published Benchmarks

From the EvolutionaryScale blog post (2024):

| Model | Parameters | Benchmark Performance |
|-------|------------|----------------------|
| **ESMC-300M** | 300M | Surpasses ESM2-650M on multiple benchmarks |
| ESMC-600M (upstream) | 600M | Approaches ESM2-3B quality (also MIT; not distributed here) |
| ESM2-650M | 650M | Established baseline |
| ESM2-3B | 3B | Previous state-of-the-art open model |


### BioLM Verification Results

| Variant | Action | Tolerance | Status |
|---------|--------|-----------|--------|
| 300m | encode (test 1) | cosine_distance < 0.02, rel_tol 1e-4 | PASS |
| 300m | encode (test 2) | cosine_distance < 0.02, rel_tol 1e-4 | PASS |
| 300m | predict | cosine_distance < 0.02, rel_tol 1e-4 | PASS |
| 300m | log_prob | Negative finite value validation | PASS |

### Comparison to Alternatives

| Model | Strength | When to prefer |
|-------|----------|----------------|
| **ESMC-300M** | Efficient, surpasses ESM2-650M | Quick prototyping, resource-constrained |
| ESM2-650M | Well-established, widely benchmarked | Backward compatibility with existing pipelines |
| ESM2-3B | Largest ESM2 model | Maximum ESM2-era quality |
| ESM1v | Variant effect prediction specialist | Specifically optimized for mutation effect scoring |

## Strengths & Limitations

### Pros

- Better parameter efficiency than ESM2 (more performance per parameter)
- Three distinct actions: embeddings, masked prediction, sequence log-probability
- Multi-layer embedding extraction with user-specified layers
- Mean-pooled, per-token, and logit outputs available from encode
- Log-probability scoring for sequence fitness assessment
- Efficient 300M model surpassing ESM2-650M on multiple benchmarks
- Supports gap character (`-`) in encode for alignment-aware embeddings

### Cons

- Licensed under MIT (re-released by CZ Biohub, 2026); no commercial-use restriction
- Maximum sequence length of 2048 residues
- Predict action requires at least one `<mask>` token
- No ensemble mode (unlike ESM1v with 5 models)
- Relatively new model with less published benchmarking than ESM2

### Known Failure Modes

- Sequences near or exceeding 2048 residues may be truncated
- Requesting layer indices outside the valid range raises a `ValidationError400` (HTTP 400)
- Predict_log_prob only considers 20 canonical amino acids; sequences with non-standard residues will have those positions excluded
- Very short sequences (<5 residues) may produce low-quality embeddings

## Implementation Details

### Inference Pipeline

#### Encode

```
Request
  |-- 1. Validate sequences (extended AA + gap)
  |-- 2. Tokenize sequences with ESMC tokenizer
  |-- 3. Batched forward pass
  |-- 4. For each requested layer:
  |     |-- [if mean] Mean-pool hidden states (excluding BOS/EOS)
  |     |-- [if per_token] Extract per-residue embeddings (excluding BOS/EOS)
  |-- 5. [if logits] Slice sequence_logits to 20 canonical AAs
  |-- 6. Format and return response
```

#### Predict

```
Request
  |-- 1. Validate sequences (extended AA + <mask>)
  |-- 2. Tokenize and forward pass
  |-- 3. Remove BOS/EOS from logits
  |-- 4. Slice to 20 canonical AAs
  |-- 5. Detokenize to get sequence tokens
  |-- 6. Return logits, sequence_tokens, vocab_tokens
```

#### Predict Log Prob

```
Request
  |-- 1. Validate sequences (unambiguous AA only)
  |-- 2. Tokenize and forward pass
  |-- 3. For each position in sequence:
  |     |-- Gather logits for 20 canonical AAs
  |     |-- Compute log-softmax over canonical AAs
  |     |-- Add log-prob of actual residue to sum
  |-- 4. Return total log-probability per sequence
```

### Memory & Compute Profile

| Resource | 300M Variant |
|----------|-------------|
| GPU | A10G |
| Memory | 24 GB RAM |
| CPU | 2.0 cores |
| Batch size | 8 |
| Max sequence length | 2048 |

### Determinism & Reproducibility

| Setting | Value |
|---------|-------|
| Torch manual seed | Yes (42 at model load) |
| CUDA manual seed | Yes (42, if available) |
| Deterministic outputs | Yes (all three actions are deterministic) |

### Caching Behavior

Response caching is handled outside the model container:
- In-memory caching for fast repeated lookups within a container lifetime
- Persistent storage caching for cross-request reuse
- Cache keys determined by full request payload (sequences + parameters)

## Versions & Changelog

| Version | Date | Changes |
|---------|------|---------|
| v1 | 2024 | Initial implementation with encode, predict, log_prob actions |

---

*See also: [README.md](README.md) for API reference | [BIOLOGY.md](BIOLOGY.md) for biological context*
