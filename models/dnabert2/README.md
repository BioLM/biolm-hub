# DNABERT-2

> **One-line summary**: A 117M-parameter BERT-style masked language model for DNA sequences using BPE tokenization, providing sequence embeddings and pseudo-likelihood scoring for multi-species genomic analysis.

## Overview

**DNABERT-2** is a foundation model for genomic DNA developed by Zhou et al. at Northwestern University. It applies the BERT masked language modeling paradigm to DNA sequences, producing dense embeddings and pseudo-log-likelihood scores useful for variant effect prediction, regulatory element classification, and general genomic representation learning.

The key innovation of DNABERT-2 over its predecessor (DNABERT) and other DNA language models is the use of **Byte Pair Encoding (BPE) tokenization** instead of fixed-length k-mer tokenization. BPE learns a compact vocabulary of variable-length DNA subwords from the training data, enabling the model to represent patterns at multiple scales -- from short motifs to longer conserved blocks -- in a single unified vocabulary. This design allows DNABERT-2 to achieve competitive or superior performance to much larger models (up to 21x its size) on the Genome Understanding Evaluation (GUE) benchmark while requiring only 117M parameters.

## Architecture

| Property | Value |
|----------|-------|
| Architecture | Transformer encoder (BERT-style) |
| Parameters | 117M |
| Hidden dimensions | 768 |
| Attention heads | 12 |
| Layers | 12 |
| Tokenization | Byte Pair Encoding (BPE), ~4,096 tokens |
| Training data | Multi-species genomic DNA |
| Training objective | Masked language modeling (MLM) |
| Max sequence length | 2,048 tokens (BioLM API) |

See [MODEL.md](MODEL.md) for detailed architecture specifications and tokenization comparison.

## Model Variants

Single variant -- no size options. The model slug is `dnabert2`.

## Capabilities & Limitations

**CAN be used for:**
- Extracting mean-pooled 768-dimensional embeddings from DNA sequences for downstream tasks
- Computing pseudo-likelihood log-probabilities for DNA sequences (zero-shot variant effect assessment)
- Regulatory element classification (promoters, enhancers, splice sites) via embedding-based downstream classifiers
- Cross-species genomic analysis leveraging BPE's multi-species generalization

**CANNOT be used for:**
- Sequences containing ambiguous bases (N, R, Y, W, S, etc.) -- only A, C, G, T accepted
- Sequences longer than 2,048 nucleotides
- RNA sequences (use RNA-specific models)
- Protein sequences (use ESM-2 or similar protein language models)
- DNA sequence generation (use Evo for generative tasks)
- Tasks requiring very long genomic context (>8 kbp) -- consider Nucleotide Transformers or Evo

**Other considerations:**
- BPE tokens have variable nucleotide lengths, so the effective genomic span covered by 2,048 tokens depends on sequence composition (typically 4--8 kbp)
- The `predict_log_prob` action requires N forward passes (one per non-special token) and is significantly slower than `encode`
- Uses GPU memory snapshots for reduced cold start times

## Actions / Endpoints

### `encode`

Computes a single mean-pooled embedding vector (768 dimensions) for each input DNA sequence. Tokenizes input sequences with the BPE tokenizer, runs a forward pass through the transformer encoder, and performs mean pooling over non-padded tokens.

**Request Parameters:**

| Parameter | Type | Default | Range | Description |
|-----------|------|---------|-------|-------------|
| `items[].sequence` | str | (required) | 1-2048 nt | DNA sequence (A/C/G/T only) |

**Batch limit**: 1-10 items per request.

**Request schema**: `DNABERT2EncodeRequest` containing a list of `DNABERT2EncodeRequestItem`.

**Response:**

```json
{
  "results": [
    {
      "embedding": [0.123, -0.456, 0.789, "... (768 floats)"]
    }
  ]
}
```

| Field | Type | Description |
|-------|------|-------------|
| `embedding` | list[float] | 768-dimensional mean-pooled embedding vector from the final hidden layer |

**Response schema**: `DNABERT2EncodeResponse` containing a list of `DNABERT2EncodeResponseResult`.

### `predict_log_prob`

Computes a pseudo-likelihood log-probability for each input DNA sequence. For each non-special token in the sequence, the token is masked and the model predicts the probability of the original token. The log-probabilities are summed to produce a single score per sequence.

**Request Parameters:**

| Parameter | Type | Default | Range | Description |
|-----------|------|---------|-------|-------------|
| `items[].sequence` | str | (required) | 1-2048 nt | DNA sequence (A/C/G/T only) |

**Batch limit**: 1-10 items per request.

**Request schema**: `DNABERT2PredictLogProbRequest` containing a list of `DNABERT2PredictLogProbRequestItem`.

**Response:**

```json
{
  "results": [
    {
      "log_prob": -15.234
    }
  ]
}
```

| Field | Type | Description |
|-------|------|-------------|
| `log_prob` | float | Pseudo-likelihood log-probability (sum of per-position masked log-probs); higher values indicate the sequence is more "natural" according to the model |

**Response schema**: `DNABERT2PredictLogProbResponse` containing a list of `DNABERT2PredictLogProbResponseResult`.

## Usage Examples

```python
from models.dnabert2.schema import (
    DNABERT2EncodeRequest,
    DNABERT2EncodeRequestItem,
)

# Encode DNA sequences to get embeddings
request = DNABERT2EncodeRequest(
    items=[
        DNABERT2EncodeRequestItem(sequence="ACGTACGTACGTACGT"),
        DNABERT2EncodeRequestItem(sequence="ATGATGATGATGATG"),
    ]
)
```

```python
from models.dnabert2.schema import (
    DNABERT2PredictLogProbRequest,
    DNABERT2PredictLogProbRequestItem,
)

# Score DNA sequences via pseudo-likelihood
# Compare reference vs. variant to assess mutation impact
reference_request = DNABERT2PredictLogProbRequest(
    items=[
        DNABERT2PredictLogProbRequestItem(sequence="ACGTACGTACGTACGT"),
    ]
)

variant_request = DNABERT2PredictLogProbRequest(
    items=[
        DNABERT2PredictLogProbRequestItem(sequence="ACGTTCGTACGTACGT"),
    ]
)
# delta = variant_log_prob - reference_log_prob
# Negative delta suggests the variant disrupts a learned pattern
```

## Performance & Benchmarks

### Published Results

DNABERT-2 was evaluated on the Genome Understanding Evaluation (GUE) benchmark (28 datasets, 7 task categories):

| Model | Parameters | GUE Aggregate | Notes |
|-------|-----------|--------------|-------|
| **DNABERT-2** | **117M** | **Best overall** | Outperforms models up to 21x larger |
| NT-v2-500M | 500M | Second best | 4.3x larger |
| HyenaDNA | 1.6M-6.6M | Competitive on some tasks | Much smaller |
| DNABERT v1 (6-mer) | ~117M | Baseline | Original k-mer approach |

<!-- TODO: Extract exact GUE numerical scores per task category from Zhou et al. 2023 Table 2  --  requires paper PDF from R2 -->

### SOTA Status

DNABERT-2 achieved state-of-the-art performance on the GUE benchmark at time of publication (2023), outperforming models up to 21x its size. It remains among the top-performing compact DNA foundation models.

## Implementation Verification

### Verification Method

Numerical reproduction (Option A): Integration tests compare model outputs against golden fixtures generated from the reference HuggingFace `transformers` implementation running on the same Modal infrastructure.

### Test Cases

| Action | Input | Tolerance | Status |
|--------|-------|-----------|--------|
| `encode` | "ACGTACGT" | rel_tol=1e-4 (golden fixture) | PASS |
| `predict_log_prob` | "ACGT", "ACGTACGT" | rel_tol=1e-4 (golden fixture) | PASS |

### Verification Status

**Status: VERIFIED** -- Integration tests pass with golden fixture comparison.

## Resource Requirements

| Resource | Value |
|----------|-------|
| GPU | T4 |
| Memory | 4 GB |
| CPU | 2 cores |
| Cold start | Reduced via Modal GPU memory snapshot |
| Batch size | 10 items max per request |
| Dependencies | `transformers==4.29.2`, `huggingface_hub==0.19.4`, `einops==0.7.0`, `torch` (via PyTorch 2.3.1 base image) |

## Implementation Notes

- **Memory snapshots**: Uses `@modal.enter(snap=True)` with GPU snapshot enabled (`enable_memory_snapshot=True`, `enable_gpu_snapshot=True`). The model loads directly on GPU during snapshot creation.
- **BillingMixinSnap**: Inherits from `BillingMixinSnap` for snapshot-compatible billing and caching.
- **Tokenizer**: BPE tokenizer loaded from HuggingFace with `trust_remote_code=True`. Configured with padding and truncation up to `max_sequence_len=2048`.
- **Container image**: Built from `pytorch/pytorch:2.3.1-cuda11.8-cudnn8-runtime`. The `triton` package is uninstalled to avoid conflicts.
- **Determinism**: `torch.manual_seed(42)` and `torch.cuda.manual_seed_all(42)` set at model load time. Model runs in `eval()` mode with `torch.no_grad()`.
- **Download layer**: Model weights are downloaded via the unified `setup_download_layer` system with R2 caching and HuggingFace fallback (pinned to revision `d064dece8a8b41d9fb8729fbe3435278786931f1`).
- **No variants**: Single model with no variant axes. App name is `dnabert2`.

## License

- **Code and Weights**: [Apache-2.0](https://huggingface.co/zhihan1996/DNABERT-2-117M)

## References & Citations

### Papers

1. Zhou Z et al. "DNABERT-2: Efficient Foundation Model and Benchmark For Multi-Species Genome." *arXiv preprint* (2023). [arXiv:2306.15006](https://arxiv.org/abs/2306.15006)

### BibTeX

```bibtex
@article{zhou2023dnabert2,
  title={DNABERT-2: Efficient Foundation Model and Benchmark For Multi-Species Genome},
  author={Zhou, Zhihan and Ji, Yanrong and Li, Weijian and Dutta, Pratik and Davuluri, Ramana and Liu, Han},
  journal={arXiv preprint arXiv:2306.15006},
  year={2023}
}
```

### Links

- **Paper**: [arXiv 2306.15006](https://arxiv.org/abs/2306.15006)
- **Code**: [GitHub MAGICS-LAB/DNABERT_2](https://github.com/MAGICS-LAB/DNABERT_2)
- **Model weights**: [HuggingFace zhihan1996/DNABERT-2-117M](https://huggingface.co/zhihan1996/DNABERT-2-117M)

---

*See also: [MODEL.md](MODEL.md) for technical deep-dive | [BIOLOGY.md](BIOLOGY.md) for biological context*
