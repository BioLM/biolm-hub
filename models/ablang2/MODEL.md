# AbLang2 -- Technical Details

## Architecture

### Model Type & Innovation

AbLang2 is a paired antibody language model based on the BERT (bidirectional transformer encoder) architecture. It is trained with a masked language modeling (MLM) objective on paired heavy-light chain antibody sequences from the Observed Antibody Space (OAS) database.

The key innovation of AbLang2 over its predecessor AbLang is the explicit handling of germline bias. The original AbLang model learned representations that were dominated by germline gene usage patterns, limiting its ability to capture functionally relevant somatic mutations. AbLang2 addresses this by training on paired heavy-light chain sequences and applying debiasing techniques that reduce the influence of germline identity, producing representations that better reflect antibody function, specificity, and developability rather than germline origin.

AbLang2 uses a transformer encoder with rotary position embeddings (via `rotary-embedding-torch`). It processes paired sequences in a concatenated format (`<heavy>|<light>`) with a separator token between chains, enabling the model to learn cross-chain dependencies.

### Parameters & Layers

| Property | Value |
|----------|-------|
| Architecture | Transformer encoder (BERT-style) |
| Training objective | Masked language modeling (MLM) |
| Positional encoding | Rotary position embeddings |
| Input format | Paired heavy+light: `<heavy>\|<light>` |
| Max sequence length | 1024 tokens per chain |
| Vocabulary | 20 canonical amino acids + special tokens |

AbLang-2 uses 12 transformer layers with an embedding size of 480 (12L + 480ES), based on the ESM-2 architecture with SwiGLU activation. It was pre-trained on 35.6M unpaired VH/VL sequences for 200,000 steps, then fine-tuned on 1.26M paired antibody sequences for 10,000 steps, using focal loss and modified masking (Olsen et al., 2024, Table 1).

### Training Data

| Property | Details |
|----------|---------|
| Dataset | Observed Antibody Space (OAS) -- paired sequences |
| Composition | Paired heavy-light chain antibody sequences from multiple species |
| Debiasing | Germline bias correction to reduce V-gene dominance |

The training data consists of paired antibody sequences from OAS, which aggregates antibody repertoire sequencing data from published studies. The debiasing procedure reduces over-representation of common germline genes, ensuring the model learns sequence-function relationships beyond germline identity.

### Loss Function & Objective

Masked language modeling (MLM) with cross-entropy loss:

```
L = -Sum_i log P(x_masked_i | x_visible)
```

During training, a fraction of input tokens are randomly masked and the model predicts the original amino acid at each masked position from the surrounding context, including cross-chain context from the paired heavy-light sequence.

### Tokenization / Input Processing

| Property | Details |
|----------|---------|
| Tokenizer | Character-level (one token per amino acid) |
| Input format | `<heavy>\|<light>` with separator |
| Special tokens | Start/end tokens, separator `\|`, `*` for masking |
| Max sequence per chain | 1024 residues |
| Batch size | 32 sequences |

Input sequences are validated against the extended amino acid alphabet. For the `generate` action, `*` characters mark positions to be restored.

## Performance & Benchmarks

### Published Benchmarks

The AbLang2 paper demonstrates improvements over AbLang and general protein language models on antibody-specific tasks.

From Olsen et al. (2024), Tables 2-3: AbLang-2 achieves near-perfect germline residue prediction (perplexity ~1.1) while substantially improving non-germline (NGL) residue prediction compared to prior models. NGL perplexity scores for AbLang-2: VH FWR 9.92, VH CDR1/2 11.13, VH CDR3 12.47, VL FWR 10.09, VL CDR1/2 9.54, VL CDR3 10.77. By comparison, prior antibody LMs (AntiBERTy, AbLang-1) had NGL perplexities near or worse than random (20). The largest improvement came from switching to focal loss, which heavily skews training toward poorly predicted NGL residues. On clonotype mutation analysis, AbLang-2 achieved ~15% cumulative probability for known NGL residues in VH (vs. <2% for AntiBERTy and AbLang-1), while maintaining ~90-100% cumulative probability when germline residues are included.

Key findings from the paper:
- Germline debiasing significantly improves representation quality for functional prediction tasks
- Paired sequence modeling captures heavy-light chain co-evolution
- AbLang2 outperforms general protein language models (ESM-2, ProtTrans) on antibody-specific tasks

### BioLM Verification Results

The BioLM implementation uses official pre-trained weights loaded via `ablang2.pretrained.pretrained()`. Numerical verification is performed against golden reference outputs:

| Metric | Threshold | Status |
|--------|-----------|--------|
| Relative tolerance | 1e-4 | PASS |
| Cosine distance | < 0.02 | PASS |

Tests cover encode (seqcoding + rescoding), predict, generate, and log_prob actions.

### Comparison to Alternatives

| Model | Type | Key Advantage | Key Disadvantage |
|-------|------|---------------|------------------|
| **AbLang2 (this)** | Antibody LM | Germline-debiased, paired H+L | Antibody-specific only |
| IgBERT | Antibody LM | HuggingFace Transformers compatible | No germline debiasing |
| ESM-2 | General protein LM | Broad protein coverage | Not antibody-specialized |
| AntiBERTy | Antibody LM | Unpaired chain modeling | No paired chain support |

### Error Bars & Confidence

AbLang2 is deterministic when seeds are set (as in the BioLM implementation). The same input produces the same output on the same hardware.

Sources of variability across runs:
- Different GPU architectures may produce slightly different floating-point results (within 1e-4 relative tolerance)

## Strengths & Limitations

### Pros

- Germline-debiased representations capture functional properties beyond V-gene identity
- Paired heavy-light chain modeling captures inter-chain dependencies
- Multiple output modes: seqcoding (sequence-level), rescoding (residue-level), likelihood, restore
- CPU inference supported (no GPU required)
- BSD-3-Clause licensed

### Cons

- Antibody-specific -- cannot be used for general proteins
- Single variant only (no size options)
- Requires both heavy and light chains (no single-chain mode)
- `align=True` option for rescoding/restore not yet supported in BioLM (requires ANARCI)

### Known Failure Modes

- **Non-antibody sequences**: Model expects antibody sequences; non-antibody input will produce meaningless embeddings
- **Single-chain input**: Both heavy and light chains are required; single-chain analysis is not supported
- **Very short CDRs**: Sequences with atypically short CDR regions may produce lower-quality predictions
- **Non-standard numbering**: The model does not enforce numbering schemes; sequences should be provided as raw amino acid strings

## Implementation Details

### Inference Pipeline

```
Request
  |-- 1. Validate sequences (alphabet, length, batch size)
  |-- 2. Format as paired input: (heavy, light) tuples
  |-- 3. Forward pass via ablang2 library
  |     |-- encode: seqcoding or rescoding mode
  |     |-- predict: likelihood mode (logits)
  |     |-- generate: restore mode (fill masked positions)
  |     |-- log_prob: logits -> log_softmax -> sum
  |-- 4. Post-process outputs to response schema
  |-- 5. Return typed response
```

### Memory & Compute Profile

| Property | Value |
|----------|-------|
| GPU | None (CPU only) |
| Memory | 4 GB |
| CPU | 2 cores |
| Batch size | 32 |

The model runs entirely on CPU, making it cost-effective for high-throughput antibody screening.

### Determinism & Reproducibility

| Setting | Value |
|---------|-------|
| `torch.manual_seed` | 42 |
| `torch.cuda.manual_seed_all` | 42 (if GPU available) |
| `torch.no_grad` | Yes (inference) |
| `model.freeze()` | Yes |

### Caching Behavior

Response caching (Redis/R2 two-tier) is handled by the BioLM platform layer, not by the model container:
- **Redis (Modal Dict)**: Fast lookup, TTL-based expiration
- **R2**: Persistent storage for cached results
- **Cache key**: Determined by the request payload (sequences, params, mode)

## Versions & Changelog

| Version | Date | Changes |
|---------|------|---------|
| v1 | 2025-02-05 | Initial implementation with encode, predict, generate, log_prob actions |

---

*See also: [README.md](README.md) for API reference | [BIOLOGY.md](BIOLOGY.md) for biological context*
