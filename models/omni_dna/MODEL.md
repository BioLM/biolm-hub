# Omni-DNA -- Technical Details

## Architecture

### Model Type & Innovation

Omni-DNA is a family of **multi-task DNA foundation models** based on the OLMo (Open Language Model) transformer architecture, adapted for genomic sequences. The key innovation is a unified auto-regressive framework that handles multiple DNA tasks (embedding extraction, sequence scoring) within a single model, using BPE (byte-pair encoding) tokenization rather than character-level or fixed k-mer tokenization.

The model uses the `ai2-olmo` (Allen AI OLMo) architecture with custom DNA-specific tokenization. This design choice enables the model to learn data-driven subword units from DNA sequences, potentially capturing biologically meaningful motifs as tokens.

### Parameters & Layers

| Variant | Parameters | Architecture | GPU |
|---------|-----------|--------------|-----|
| omni-dna-1b | ~1B | OLMo Transformer (CausalLM) | L4 |

Additional variants defined but not currently deployed: 20M, 60M, 116M, 300M, 700M.

| Property | Value |
|----------|-------|
| Architecture | OLMo Transformer (AutoModelForCausalLM) |
| Tokenization | BPE (byte-pair encoding), vocabulary size 4096 |
| Max sequence length | 2,048 tokens (BPE tokens, not nucleotides) |
| Positional encoding | As per OLMo architecture |

### Training Data

| Property | Details |
|----------|---------|
| Dataset | DNA sequences (multi-species) |
| Preprocessing | BPE tokenization with vocabulary of 4096 tokens |

<!-- TODO: Extract specific training data details from Li et al. 2025 paper when available -->

### Loss Function & Objective

Standard autoregressive (causal language modeling) objective:

```
L = -sum_{t=1}^{T} log P(x_t | x_{<t})
```

The model predicts the next BPE token given all preceding tokens, learning the statistical structure of DNA at a subword level.

### Tokenization / Input Processing

| Property | Details |
|----------|---------|
| Tokenizer | BPE (AutoTokenizer from HuggingFace) |
| Vocabulary size | 4,096 tokens |
| Token examples | "A", "AA", "TG", "ACGT", etc. |
| Input alphabet | A, C, G, T only (unambiguous DNA) |
| Max length | 2,048 BPE tokens |
| Special tokens | BOS, PAD |
| Batch size | 2 sequences per request |

Note: Due to BPE tokenization, the number of nucleotides per token varies. A 2,048-token input may represent roughly 4,000--8,000 nucleotides depending on sequence composition.

## Performance & Benchmarks

### Published Benchmarks

<!-- TODO: Extract benchmarks from Li et al. "Omni-DNA: A Unified Multi-Task Framework for DNA Foundation Models" when available -->

### BioLM Verification Results

| Action | Test Input | Tolerance | Status |
|--------|-----------|-----------|--------|
| `encode` | DNA sequence, mean pooling | rel_tol=1e-4 | PASS |
| `predict_log_prob` | DNA sequence | rel_tol=1e-4 | PASS |

Tests cover the 1B variant only.

### Comparison to Alternatives

| Model | Key Advantage | Key Disadvantage |
|-------|---------------|------------------|
| **Omni-DNA (this)** | BPE tokenization; unified multi-task framework | Newer, less validated than established models |
| Evo 2 | Multi-domain training; generation capability | Much larger; no BPE tokenization |
| Nucleotide Transformer | 6-mer tokenization; extensive benchmarks | No generation; masked LM only |
| DNABERT-2 | Established; BPE tokenization | Shorter context; no BioLM integration |

### Error Bars & Confidence

- `encode` and `predict_log_prob` are deterministic (seeds set to 42)
- Small floating-point differences may occur across GPU architectures

## Strengths & Limitations

### Pros

- BPE tokenization learns data-driven DNA subword units
- Unified framework for multiple DNA tasks
- Multiple model sizes (20M--1B) for speed/quality tradeoffs (only 1B currently deployed)
- Based on well-tested OLMo architecture
- Supports batched input (batch_size=2)

### Cons

- BPE tokenization means sequence length in tokens does not directly map to nucleotide count
- No generation endpoint (encode and predict_log_prob only)
- Less validated than Evo or Nucleotide Transformer families
- Only the 1B variant is currently deployed

### Known Failure Modes

- **Very short sequences**: Sequences that tokenize to very few BPE tokens provide limited context
- **Highly repetitive DNA**: Repetitive sequences may be over-compressed by BPE, leading to degenerate representations
- **Non-DNA input**: Only A, C, G, T accepted; ambiguity codes and RNA are rejected

## Implementation Details

### Inference Pipeline

```
Request
  |-- 1. Validate input (A/C/G/T only, length <= 2048 BPE tokens)
  |-- 2. Route to action:
  |
  |-- [encode]
  |     |-- Tokenize with BPE (padding, truncation)
  |     |-- Forward pass with output_hidden_states=True
  |     |-- Extract final hidden states [B, L, D]
  |     |-- Compute mean or last pooling over non-padded tokens
  |     |-- Return embeddings
  |
  |-- [predict_log_prob]
        |-- Tokenize without special tokens
        |-- Forward pass
        |-- log_softmax over vocabulary dimension
        |-- Gather log P(token_i) at each position
        |-- Mask padded positions
        |-- Sum per sequence
        |-- Return total log-prob
```

### Memory & Compute Profile

| Variant | GPU | Memory | CPU |
|---------|-----|--------|-----|
| omni-dna-1b | L4 | 16 GB | 4 cores |

### Determinism & Reproducibility

| Setting | Value |
|---------|-------|
| `torch.manual_seed` | 42 |
| `torch.cuda.manual_seed_all` | 42 |
| Model mode | eval() with torch.no_grad() |

Results are reproducible on the same GPU architecture. GPU memory snapshot is enabled for fast cold starts.

### Caching Behavior

- Standard BioLM Redis + R2 two-tier caching via `BillingMixinSnap`
- GPU memory snapshots enabled (`enable_memory_snapshot=True`, `enable_gpu_snapshot=True`)
- Cache key derived from action name, input payload, and model variant

## Versions & Changelog

| Version | Date | Changes |
|---------|------|---------|
| v1 | -- | Initial implementation with encode and predict_log_prob actions; 1B variant |

---

*See also: [README.md](README.md) for API reference | [BIOLOGY.md](BIOLOGY.md) for biological context*
