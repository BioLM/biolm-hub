# DNABERT-2 -- Technical Details

## Architecture

### Model Type & Innovation

DNABERT-2 is a **BERT-style masked language model** for DNA sequences, developed by Zhou et al. at Northwestern University. It is the successor to the original DNABERT model and introduces a fundamental shift in how DNA sequences are tokenized for language modeling.

The key innovation of DNABERT-2 is replacing **k-mer tokenization with Byte Pair Encoding (BPE)**. The original DNABERT (and models like Nucleotide Transformers) use fixed-length k-mer tokenization, where DNA is split into overlapping or non-overlapping subsequences of a fixed length (e.g., 6-mers). This approach has drawbacks: the vocabulary grows exponentially with k (4^k possible k-mers), information leaks between overlapping tokens, and the model cannot represent sub-k-mer patterns.

DNABERT-2's BPE tokenizer learns a data-driven vocabulary of variable-length DNA subwords. This provides:

- **Compact vocabulary**: A BPE vocabulary of ~4,096 tokens replaces the exponentially large k-mer space.
- **Multi-resolution encoding**: The tokenizer can represent both short motifs and longer conserved patterns as single tokens, adapting granularity to the data.
- **Multi-species generalization**: BPE tokens generalize across species because they are learned from the data distribution rather than imposed as a fixed-length sliding window.

The underlying architecture uses the Transformer encoder from the `BertForMaskedLM` framework (via the `triton_flash_bert` configuration), yielding a compact 117M-parameter model that achieves performance comparable to or exceeding much larger k-mer-based DNA models.

### Parameters & Layers

| Component | Details |
|-----------|---------|
| Architecture | Transformer encoder (BERT-style) |
| Parameters | 117M |
| Hidden dimensions | 768 |
| Attention heads | 12 |
| Layers | 12 |
| Vocabulary | ~4,096 tokens (BPE-learned) |
| Positional encoding | Learned absolute positional embeddings |
| Activation | GELU |
| Max input length | 2,048 tokens (BioLM enforced) |

DNABERT-2 is a single-variant model with no size options.

### Training Data

| Property | Details |
|----------|---------|
| Dataset | Multi-species genomes |
| Scope | Genomes from diverse species across all domains of life |
| Data type | Raw genomic DNA sequences |
| Preprocessing | BPE tokenization learned from training corpus |
| Scale | Large-scale genomic corpus (exact token count not specified in paper) |

Known biases: like other multi-species genomic models, training data is skewed toward well-sequenced model organisms. Performance on underrepresented taxa may be lower.

### Loss Function & Objective

Masked language modeling (MLM): a fraction of BPE tokens are replaced with a `[MASK]` token, and the model is trained to predict the original token from context via cross-entropy loss.

```
L = - sum_i log P(x_masked_i | x_visible)
```

This self-supervised objective forces the model to learn contextual relationships between DNA subsequences, capturing conservation patterns, regulatory grammar, and coding-region structure.

### Tokenization / Input Processing

- **Tokenizer**: Byte Pair Encoding (BPE), learned from multi-species genomic DNA. This is the defining innovation of DNABERT-2 compared to predecessors.
- **Vocabulary**: ~4,096 tokens of variable-length DNA subwords.
- **Special tokens**: `[CLS]`, `[SEP]`, `[PAD]`, `[MASK]`, `[UNK]`
- **Input alphabet**: A, C, G, T only (validated by `validate_dna_unambiguous`; ambiguous IUPAC codes are rejected).
- **Max length**: 2,048 tokens (BioLM enforced). Because BPE tokens represent variable-length substrings, the effective nucleotide span per request varies but is typically on the order of 4--8 kbp.
- **Truncation**: Sequences exceeding max token length are truncated.

**Comparison of DNA tokenization strategies:**

| Model | Tokenization | Resolution | Vocabulary | Context (approx.) |
|-------|-------------|------------|------------|-------------------|
| DNABERT-2 | BPE | Variable (sub-k-mer to multi-k-mer) | ~4,096 | ~4-8 kbp |
| Nucleotide Transformers | 6-mer | 6 nt fixed | ~4,105 | ~12 kbp |
| Evo | Byte-level | Single nucleotide | ~8 | Up to 131 kbp |
| DNABERT (v1) | k-mer (k=3..6) | k nt fixed | 4^k | ~2 kbp |

## Performance & Benchmarks

### Published Benchmarks

From Zhou et al. (arXiv 2306.15006), DNABERT-2 was evaluated on the Genome Understanding Evaluation (GUE) benchmark, which spans 36 datasets across 9 task categories.

#### GUE Benchmark (Overall)

| Model | Parameters | GUE Aggregate | Notes |
|-------|-----------|--------------|-------|
| **DNABERT-2** | **117M** | **Best overall** | Outperforms models up to 21x larger |
| NT-v2-500M | 500M | Second best | 4.3x larger |
| HyenaDNA | 1.6M-6.6M | Competitive on some tasks | Much smaller |
| DNABERT v1 (6-mer) | ~117M | Baseline | Original k-mer approach |

<!-- TODO: Extract exact GUE numerical scores per task category from Zhou et al. 2023 Table 2  --  requires paper PDF from R2 -->

Key findings from the paper:
- DNABERT-2 achieves top performance on most GUE tasks despite having only 117M parameters -- significantly fewer than competing models.
- The BPE tokenization strategy contributes to strong multi-species generalization, with consistent performance across human, mouse, and yeast genomic tasks.
- DNABERT-2 outperforms models up to 21x its size (NT 2.5B) on several benchmark tasks.

### BioLM Verification Results

| Action | Test Input | Tolerance | Status |
|--------|-----------|-----------|--------|
| `encode` | "ACGTACGT" | rel_tol=1e-4 (golden fixture) | PASS |
| `predict_log_prob` | "ACGT", "ACGTACGT" | rel_tol=1e-4 (golden fixture) | PASS |

### Comparison to Alternatives

| Model | Parameters | Tokenization | Context | When to prefer |
|-------|-----------|-------------|---------|----------------|
| **DNABERT-2** | 117M | BPE | ~4-8 kbp | Lightweight; fine-grained tokenization; multi-species generalization |
| NT-v2-250M | 250M | 6-mer | ~12 kbp | Longer context; strong multi-species genomic benchmarks |
| NT-v2-500M | 500M | 6-mer | ~12 kbp | Best NT accuracy; longer context |
| Evo | 7B | Byte-level | 131 kbp | Very long genomic contexts; generative DNA tasks |

## Strengths & Limitations

### Pros

- **Compact model**: At 117M parameters, DNABERT-2 is substantially smaller than competing DNA foundation models while achieving competitive or superior performance.
- **BPE tokenization**: Variable-length tokens capture multi-scale DNA patterns, from short motifs to longer conserved blocks, without the rigid k-mer vocabulary.
- **Multi-species generalization**: BPE tokens learned from diverse genomes transfer well across species, unlike fixed k-mers that may over-fit species-specific codon usage.
- **Low resource requirements**: Runs on a T4 GPU with 4 GB memory, making it one of the most cost-effective DNA language models available.

### Cons

- **Shorter effective context** than NT or Evo: the ~4-8 kbp effective span is sufficient for promoters and regulatory elements but too short for full gene bodies or large regulatory domains.
- **Single variant only**: No size options -- users cannot trade off between accuracy and speed across model sizes.
- **BPE token boundaries are not biologically meaningful**: Unlike k-mers (which have a fixed biological interpretation), BPE token boundaries are data-driven and may not align with codons, motifs, or other biologically relevant boundaries.

### Known Failure Modes

- **Repetitive low-complexity DNA** (e.g., microsatellites, telomeric repeats): BPE may collapse repetitive regions into few tokens, yielding embeddings with limited discriminative power.
- **Very short sequences** (< ~10 nt): insufficient context for meaningful embeddings or log-probability scores.
- **Non-standard DNA** (RNA, modified bases, ambiguous IUPAC codes): input validation rejects non-A/C/G/T characters.
- **Sequences near the token limit**: because BPE token lengths vary, the effective nucleotide coverage for a 2,048-token input depends on sequence composition.

## Implementation Details

### Inference Pipeline

#### encode

```
Request
  |-- 1. Validate DNA sequences (A/C/G/T only, length <= 2048 nt)
  |-- 2. Batch tokenize with BPE tokenizer (padding + truncation)
  |-- 3. Forward pass on GPU (base_model output)
  |      |-- 12 transformer encoder layers
  |      +-- Extract last hidden states: [B, L, 768]
  |-- 4. Mean pool over non-padded tokens (attention mask weighted)
  +-- 5. Return per-sequence embedding vectors (768-dimensional)
```

#### predict_log_prob

```
Request (processed per-sequence)
  |-- 1. Validate DNA sequence
  |-- 2. Tokenize single sequence with special tokens
  |-- 3. Identify valid (non-special) token positions
  |-- 4. Create masked batch: one copy per valid position, each with one token masked
  |-- 5. Batch forward pass on GPU (MLM head logits)
  |-- 6. Gather log P(original_token) at each masked position
  +-- 7. Sum log-probs -> pseudo-likelihood score
```

### Memory & Compute Profile

| Property | Value |
|----------|-------|
| GPU | T4 (16 GB) |
| GPU Memory (model) | ~1-2 GB |
| CPU | 2 cores |
| System Memory | 4 GB |
| Batch size | Up to 10 items per request |

Attention complexity is O(n^2) in token length. The 2,048 token limit keeps memory usage well within T4 capacity even at full batch size.

The `predict_log_prob` action is significantly more expensive than `encode` because it requires N forward passes (one per non-special token in the sequence).

### Determinism & Reproducibility

| Setting | Value |
|---------|-------|
| Torch manual seed | 42 |
| CUDA manual seed | 42 (all devices) |
| Model mode | eval() with torch.no_grad() |

Seeds are set during model loading. Inference uses `torch.no_grad()` and the model is in `eval()` mode. Results should be deterministic for the same input on the same hardware. Minor floating-point variations may occur across different GPU architectures.

### Caching Behavior

- **Redis caching**: Enabled via `BillingMixinSnap` (Modal Dict + R2 two-tier caching).
- **Memory snapshots**: GPU memory snapshots are enabled (`enable_memory_snapshot=True`, `enable_gpu_snapshot=True`) for faster cold starts.
- **Cache key**: Determined by action name, input payload, and model variant.

## Versions & Changelog

| Version | Date | Changes |
|---------|------|---------|
| v1 (params_version) | 2025 | Initial BioLM deployment with encode and predict_log_prob actions |

---

*See also: [README.md](README.md) for API reference | [BIOLOGY.md](BIOLOGY.md) for biological context*
