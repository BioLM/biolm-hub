# E1 -- Technical Details

## Architecture

### Model Type & Innovation

E1 is an encrypted protein language model developed by Profluent Bio and Synthyra. It is a masked language model based on a transformer encoder architecture with a novel feature: retrieval-augmented inference. E1 supports conditioning on homologous context sequences via block-causal attention, enabling improved predictions when evolutionary context is available.

The key innovation is the multi-sequence input format: context sequences (homologs) are prepended to the query sequence, and the model uses block-causal attention so that the query attends to both itself and the context, while context sequences only attend to themselves. This simulates the information in a multiple sequence alignment (MSA) without requiring explicit MSA construction.

E1 uses `?` as the mask token (rather than `<mask>` used by ESM models).

### Parameters & Layers

| Variant | Parameters | Layers | GPU | Dtype |
|---------|-----------|--------|-----|-------|
| E1-150M | 150M | 20 | T4 | float16 |
| E1-300M | 300M | 20 | L4 | bfloat16 |
| E1-600M | 600M | 30 | L4 | bfloat16 |

From Jain et al. (2025): E1 models use a standard Transformer encoder architecture augmented with block-causal attention for retrieval augmentation. Global block-causal attention is used every three layers, while all other layers use intra-sequence attention. All models use Rotary Position Embedding (RoPE). E1 150M has 20 layers, E1 300M has 20 layers, and E1 600M has 30 layers. Models were trained on 4 trillion tokens (batch size 2^20 tokens) from the Profluent Protein Atlas (PPA-1) and UniRef Version 2411 datasets, using a warmup-stable-decay learning rate schedule with Stable AdamW optimizer. E1 600M was trained on 64 H100 GPUs for 25 days. Training used curriculum learning, gradually increasing total length (8192 to 32768 tokens) and number of sequences per instance (2 to 512). PPA-1 was used exclusively for the first 1.5 trillion tokens, then mixed with UniRef in a 60:40 ratio.

Common across all variants:

| Property | Value |
|----------|-------|
| Max sequence length | 2048 tokens |
| Max context sequences | 50 |
| Mask token | `?` |
| Tokenizer | Custom E1 tokenizer |
| Multi-sequence format | Comma-separated (context sequences, then query) |
| Tokenization per sequence | `<bos> 1 SEQUENCE 2 <eos>` |

### Training Data

| Property | Details |
|----------|---------|
| Source | Protein sequence databases (details not published) |
| Training objective | Masked language modeling with block-causal attention |

### Loss Function & Objective

Masked language modeling (MLM) with cross-entropy loss, enhanced by block-causal attention that enables retrieval-augmented training where context sequences inform the query prediction.

### Tokenization / Input Processing

| Property | Details |
|----------|---------|
| Encode sequences | Extended amino acid alphabet (20 standard + B, X, Z, U, O) |
| Predict sequences | Extended AA + `?` mask token (one or more `?` required) |
| Predict log prob sequences | 20 canonical amino acids only |
| Context sequences | Optional list of homologs (max 50, no `?` tokens allowed) |
| Multi-sequence format | `CONTEXT1,CONTEXT2,...,QUERY` |
| Per-sequence tokenization | `<bos> 1 SEQUENCE 2 <eos>` (5 overhead tokens per sequence) |

## Performance & Benchmarks

### Published Benchmarks

From Jain et al. (2025), Table 1 -- ProteinGym v1.3 (217 DMS substitution assays), average Spearman correlation:

| Model | Mode | Avg Spearman | NDCG@10 |
|-------|------|-------------|---------|
| ESM2-150M | Single sequence | 0.387 | 0.729 |
| ESM2-650M | Single sequence | 0.414 | 0.747 |
| ESMC-600M | Single sequence | 0.405 | 0.746 |
| **E1 150M** | Single sequence | 0.401 | 0.744 |
| **E1 300M** | Single sequence | 0.416 | 0.748 |
| **E1 600M** | Single sequence | 0.420 | 0.749 |
| PoET | + Homologs | 0.470 | 0.784 |
| **E1 150M** | + Homologs | 0.473 | 0.785 |
| **E1 300M** | + Homologs | 0.475 | 0.787 |
| **E1 600M** | + Homologs | 0.477 | 0.788 |

E1 outperforms all ESM-2 and ESMC family models in single-sequence mode at comparable sizes. With retrieval augmentation, E1 achieves state-of-the-art performance among publicly available models, surpassing PoET and MSA Pairformer. E1 also achieves superior unsupervised contact-map prediction (Precision@L) on CAMEO subsets.

### BioLM Verification Results

| Test Case | Tolerance | Status |
|-----------|-----------|--------|
| Encode (mean, single sequence) | rel_tol 1e-4, cosine < 0.02 | PASS |
| Encode (mean, multiple sequences) | rel_tol 1e-4, cosine < 0.02 | PASS |
| Encode (with context sequences) | rel_tol 1e-4, cosine < 0.02 | PASS |
| Predict (masked tokens) | rel_tol 1e-4, cosine < 0.02 | PASS |
| Predict log prob (single) | Negative finite float | PASS |
| Predict log prob (with context) | Negative finite float | PASS |

### Comparison to Alternatives

| Model | Type | Key Advantage | Key Disadvantage |
|-------|------|---------------|------------------|
| **E1 (this)** | Retrieval-augmented MLM | Context sequences improve predictions without MSA | Newer, fewer benchmarks |
| ESM2 | Standard MLM | Most widely adopted, proven embeddings | No retrieval augmentation |
| SaProt | Structure-aware MLM | Uses structure tokens | Requires structure input |
| MSA Transformer | MSA-based | Direct MSA processing | Requires explicit MSA computation |
| ProtTrans (ProtT5) | Encoder-decoder | Generation capability | Larger compute footprint |

### Error Bars & Confidence

E1 is deterministic when seeds are set. The same input with the same context sequences produces the same output. Adding or removing context sequences will change the output (by design).

GPU-specific note: `torch.compile` / `torch._dynamo` is disabled due to flex_attention compilation errors on PyTorch 2.6.0. This means eager mode is used, which is slightly slower but avoids segmentation faults.

## Strengths & Limitations

### Pros

- Retrieval-augmented inference via context sequences (up to 50 homologs)
- Three size variants (150M, 300M, 600M) for speed/quality tradeoff
- Multiple output types: mean embeddings, per-token, logits, log probabilities
- No MSA computation needed -- just provide homologous sequences as context
- Apache-2.0 license with no restrictions

### Cons

- Newer model with fewer published benchmarks than ESM2
- torch.compile disabled (eager mode only) due to PyTorch 2.6.0 compatibility
- No GPU memory snapshots (causes SIGSEGV on restore) -- slower cold starts
- `?` mask token differs from ESM convention (`<mask>`)
- Logits restricted to 20 canonical amino acids only

### Known Failure Modes

- **GPU snapshot SIGSEGV**: Memory snapshots cause segfaults; disabled entirely
- **torch.compile errors**: flex_attention compilation fails with sympy Relational errors; dynamo disabled
- **Context sequence mask tokens**: Context sequences containing `?` are rejected (only query may have masks)
- **Very long multi-sequence inputs**: Total token count (all context + query + overhead tokens) may exceed memory for many long context sequences

## Implementation Details

### Inference Pipeline

**Encode pipeline:**
```
Request
  |-- 1. Validate sequences (extended AA alphabet)
  |-- 2. Build multi-sequence input (context + query, comma-separated)
  |-- 3. Calculate query token positions
  |-- 4. Forward pass with output_hidden_states=True
  |-- 5. Extract query positions from hidden states
  |-- 6. Post-process: mean pooling, per-token, or logits
  |-- 7. Return E1EncodeResponse
```

**Predict pipeline:**
```
Request
  |-- 1. Validate sequences (extended AA + `?`)
  |-- 2. Build multi-sequence input
  |-- 3. Forward pass -> logits
  |-- 4. Extract query positions, slice to canonical 20 AA
  |-- 5. Return E1PredictResponse
```

**Predict log prob pipeline:**
```
Request
  |-- 1. Validate sequences (canonical 20 AA only)
  |-- 2. Build multi-sequence input
  |-- 3. Forward pass -> logits
  |-- 4. For each query position: log-softmax over canonical 20 AA
  |-- 5. Sum log P(residue_i) across all positions
  |-- 6. Return E1PredictLogProbResponse
```

### Memory & Compute Profile

| Variant | GPU | VRAM | Dtype | Inference Latency |
|---------|-----|------|-------|-------------------|
| E1-150M | T4 (16 GB) | ~4 GB | float16 | ~100ms/seq |
| E1-300M | L4 (24 GB) | ~8 GB | bfloat16 | ~150ms/seq |
| E1-600M | L4 (24 GB) | ~12 GB | bfloat16 | ~250ms/seq |

### Determinism & Reproducibility

| Setting | Value |
|---------|-------|
| `torch.manual_seed` | 42 |
| `torch.cuda.manual_seed_all` | 42 |
| `torch._dynamo.config.disable` | True |
| `torch.no_grad` | Yes (inference) |
| Memory snapshots | Disabled (SIGSEGV on restore) |

### Caching Behavior

E1 uses `BillingMixin` (not `BillingMixinSnap`) since GPU memory snapshots are disabled. Standard Redis/R2 two-tier caching applies. Cache keys include context sequences when provided.

## Versions & Changelog

| Version | Date | Changes |
|---------|------|---------|
| v1 | 2025-12-04 | Initial implementation with encode, predict, and predict_log_prob actions |
| v1 (updated) | 2025-12-04 | Added context_sequences support (retrieval-augmented mode) |
| v1 (updated) | 2025-12-11 | Disabled torch.compile/dynamo to fix flex_attention errors |
| v1 (updated) | 2025-12-13 | Disabled GPU memory snapshots to fix SIGSEGV |

---

*See also: [README.md](README.md) for API reference | [BIOLOGY.md](BIOLOGY.md) for biological context*
