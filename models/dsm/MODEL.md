# DSM -- Technical Details

## Architecture

### Model Type & Innovation

DSM (Diffusion Sequence Model) is a protein language model trained with masked diffusion for both generative protein design and representation learning. Unlike autoregressive models (e.g., ProGen2) that generate sequences left-to-right, DSM uses an iterative denoising process that fills masked positions over multiple steps, enabling conditional and unconditional sequence generation.

The key innovation is the masked diffusion training objective, which unifies the strengths of masked language models (bidirectional context, good embeddings) and diffusion models (high-quality generation). DSM progressively unmasks a fully masked sequence over configurable steps, with remasking strategies that control which positions are denoised at each step.

### Parameters & Layers

| Variant | Parameters | Hidden Dim | Layers | Attention Heads | GPU | Memory |
|---------|-----------|------------|--------|-----------------|-----|--------|
| DSM-150M | 150M | 640 | 30 | 20 | A10G | 16 GB |
| DSM-650M | 650M | 1280 | 33 | 20 | A10G | 32 GB |
| DSM-3B | 3B | 2560 | 36 | 40 | A100 | 64 GB |

DSM models are extended from pre-trained ESM2 checkpoints (Hallee et al., 2025). DSM-150M inherits the ESM2-150M architecture (30 layers, 640 hidden dim, 20 attention heads). DSM-650M inherits the ESM2-650M architecture (33 layers, 1280 hidden dim, 20 attention heads). Both were trained on OMGprot50, a dataset of over 207 million protein sequences clustered at 50% sequence identity from the Open MetaGenomic dataset (OMG). DSM-150M was trained for 100,000 steps with batch size 32 and max sequence length 512. DSM-650M was trained for 100,000 steps with batch size 128 and max sequence length 2048. DSMppi (the PPI variant) was fine-tuned from DSM-650M on protein-protein interaction pairs from the STRING database.

All variants share:
| Property | Value |
|----------|-------|
| Max sequence length | 2048 tokens |
| Vocabulary | Standard amino acid tokenizer |
| Base architecture | Transformer with ESM backbone |

### Training Data

| Variant | Dataset | Description |
|---------|---------|-------------|
| Base (150M, 650M) | omg_prot50 | General protein sequences |
| PPI (650M) | STRING database | Protein-protein interaction pairs |

### Loss Function & Objective

Masked diffusion objective: the model learns to predict the original amino acid at masked positions through iterative denoising. During training, a random fraction of positions are masked and the model predicts the original tokens. The diffusion schedule controls the masking fraction over time.

### Tokenization / Input Processing

| Property | Details |
|----------|---------|
| Tokenizer | ESM-style character-level tokenizer |
| Special tokens | `<mask>`, `<eos>`, standard BOS/EOS |
| Mask token | `<mask>` for infilling positions |
| Separator | `<eos>` between sequences (PPI variant) |
| Max length | 2048 tokens |

## Performance & Benchmarks

### Published Benchmarks

From Hallee et al. (2025): DSM models match or outperform MLM-based and discrete diffusion pLMs (DPLM) of the same size, as well as an autoregressive pLM (ProtCLM-1B) almost twice DSM's size, on downstream representation tasks. DSM was benchmarked against ESM2, GLM2, ProtBert, ProtCLM-1B, ESMC, DPLM, ANKH, and ProtT5 using linear probes on supervised datasets with mean-pooled last hidden state embeddings. On generation quality, DSM produces biomimetic sequences with amino acid compositions, predicted secondary structures, and predicted functions that closely match natural protein distributions, even at 90% token corruption. DSMppi produces protein binder candidates with superior predicted binding affinity compared to known binders on the Bench-tested Binder Benchmark (BenchBB).

### BioLM Verification Results

| Test Case | Tolerance | Status |
|-----------|-----------|--------|
| Unconditional generation | Structure validation | PASS |
| Masked generation | Structure validation | PASS |
| Conditional generation | Structure validation | PASS |
| Mean-pooled embeddings | rel_tol 1e-4, cosine < 0.02 | PASS |
| Per-residue embeddings | rel_tol 1e-4, cosine < 0.02 | PASS |
| Sequence scoring | rel_tol 1e-4 | PASS |

Generation tests validate output structure (valid amino acids, reasonable perplexity) rather than exact sequence matching, since generation is stochastic by design.

### Comparison to Alternatives

| Model | Type | Key Advantage | Key Disadvantage |
|-------|------|---------------|------------------|
| **DSM (this)** | Masked diffusion | Unified generation + embedding model | Newer, fewer benchmarks |
| ProGen2 | Autoregressive | Established generation quality | Left-to-right only, no bidirectional embeddings |
| ESM2 | Masked LM | Best single-sequence embeddings | No generation capability |
| EvoDiff | Discrete diffusion | Structure-conditioned generation | Requires structural guidance |
| ESM3 | Multimodal | Structure + function + sequence | More complex, larger resource requirements |

### Error Bars & Confidence

Generation is inherently stochastic. When `seed` is provided in the request, generation is reproducible. When `seed` is None, time-based entropy is used for diversity. Embedding and scoring are deterministic.

## Strengths & Limitations

### Pros

- Unified model for both generation and representation learning
- Three generation modes: unconditional, masked infilling, conditional from prefix
- PPI variant for protein-protein interaction design
- Configurable remasking strategies (random, low_confidence, low_logit, dual)
- Multiple size variants (150M to 3B) for speed/quality tradeoff
- Embeddings competitive with dedicated embedding models

### Cons

- Generate batch size limited to 1 item per request (diffusion is compute-intensive)
- No structure conditioning (sequence-only generation)
- PPI variant only available for 650M size
- 3B variant not yet released on HuggingFace
- Generation quality depends on step_divisor parameter tuning

### Known Failure Modes

- **Very long generation**: Generating sequences close to 2048 tokens may produce lower quality output
- **PPI dual decode failures**: PPI variant's `decode_dual_input` may fail for some inputs; falls back to single-sequence decode
- **Empty input validation**: Empty sequences are allowed for unconditional generation; non-empty sequences without `<mask>` are treated as conditional

## Implementation Details

### Inference Pipeline

**Generate pipeline:**
```
Request
  |-- 1. Set random seed (user-provided or time-based)
  |-- 2. Tokenize input sequence
  |-- 3. Repeat input for num_sequences
  |-- 4. Run mask_diffusion_generate with remasking strategy
  |-- 5. Decode output sequences (dual decode for PPI)
  |-- 6. Calculate log_prob and perplexity for each
  |-- 7. Return DSMGenerateResponse
```

**Encode pipeline:**
```
Request
  |-- 1. Tokenize sequences with special tokens
  |-- 2. Forward pass through ESM backbone
  |-- 3. Extract hidden states
  |-- 4. Post-process: mean pooling, per-residue, or CLS token
  |-- 5. Return DSMEncodeResponse
```

**Score pipeline:**
```
Request
  |-- 1. Tokenize sequence
  |-- 2. Forward pass -> logits
  |-- 3. Compute log-softmax
  |-- 4. Sum autoregressive log probabilities
  |-- 5. Calculate perplexity
  |-- 6. Return DSMScoreResponse
```

### Memory & Compute Profile

| Variant | GPU | VRAM | Generate Latency | Encode Latency |
|---------|-----|------|-------------------|----------------|
| DSM-150M | A10G | ~4 GB | ~500ms/seq | ~100ms/seq |
| DSM-650M | A10G | ~12 GB | ~1-2s/seq | ~150ms/seq |
| DSM-3B | A100 | ~24 GB | ~5-10s/seq | ~500ms/seq |

### Determinism & Reproducibility

| Setting | Value |
|---------|-------|
| `torch.manual_seed` | User seed or time-based |
| `random.seed` | Same as torch seed |
| `numpy.random.seed` | Same as torch seed |
| `torch.cuda.manual_seed_all` | Same as torch seed |
| Generation | Deterministic when seed is provided |
| Embedding/scoring | Always deterministic |

### Caching Behavior

DSM uses `BillingMixinSnap` with GPU memory snapshots. Standard Redis/R2 two-tier caching applies. Note: generation with time-based seed will not benefit from caching since inputs differ.

## Versions & Changelog

| Version | Date | Changes |
|---------|------|---------|
| v1 | 2025-12-06 | Initial implementation with generate, encode, and score actions |
| v1 (updated) | 2025-12-11 | Added PPI variant support with dual-sequence decode |
| v1 (updated) | 2026-01-16 | Pinned DSM repo to commit `ca7b5c8c` for reproducibility |

---

*See also: [README.md](README.md) for API reference | [BIOLOGY.md](BIOLOGY.md) for biological context*
