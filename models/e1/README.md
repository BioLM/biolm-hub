# E1

> **One-line summary**: Encrypted protein language model with retrieval-augmented inference that produces embeddings, masked predictions, and log-probability scores, optionally conditioned on homologous context sequences.

## Overview

E1 is a protein language model developed by Profluent Bio and Synthyra. It extends the masked language modeling paradigm with retrieval-augmented inference: users can provide homologous sequences as context, and the model uses block-causal attention to condition predictions on evolutionary information without requiring explicit MSA computation.

E1 is available in three size variants (150M, 300M, 600M parameters) and supports three actions: embedding extraction (`encode`), masked token prediction (`predict`), and sequence log-probability scoring (`predict_log_prob`). All actions support optional context sequences for improved accuracy.

## Architecture

| Property | Value |
|----------|-------|
| Architecture | Transformer encoder (masked LM with block-causal attention) |
| Training objective | Masked language modeling |
| Max sequence length | 2048 tokens |
| Max context sequences | 50 |
| Mask token | `?` |
| License | Apache-2.0 |

## Model Variants

| Variant | Parameters | GPU | Memory | Dtype | Use Case |
|---------|-----------|-----|--------|-------|----------|
| `e1-150m` | 150M | T4 | 8 GB | float16 | Fast prototyping, large-scale screening |
| `e1-300m` | 300M | L4 | 16 GB | bfloat16 | Balanced speed/quality |
| `e1-600m` | 600M | L4 | 24 GB | bfloat16 | Maximum representation quality |

## Capabilities & Limitations

**CAN be used for:**
- Generating per-residue and mean-pooled sequence embeddings
- Masked token prediction (fill-in-the-blank with `?` tokens)
- Zero-shot variant effect prediction via log-probability scoring
- Retrieval-augmented inference with homologous context sequences
- Extracting logits restricted to the 20 canonical amino acids

**CANNOT be used for:**
- Sequence generation or design (encoder-only model)
- 3D structure prediction
- Non-protein molecules (DNA, RNA, small molecules)
- Multi-chain complex modeling

**Other considerations:**
- Mask token is `?` (not `<mask>` used by ESM models)
- GPU memory snapshots are disabled due to SIGSEGV on restore
- `torch.compile` is disabled due to flex_attention compilation errors
- Batch size capped at 8 sequences per request
- Context sequences are limited to 50 per item

## Actions / Endpoints

### `encode`

Generates embeddings and optional logits for protein sequences, with optional retrieval-augmented mode.

**Request Parameters:**

| Parameter | Type | Default | Range | Description |
|-----------|------|---------|-------|-------------|
| `items[].sequence` | str | *(required)* | 1-2048 AA | Query sequence (extended AA alphabet) |
| `items[].context_sequences` | list[str] | None | 0-50 seqs | Optional homologous sequences for context |
| `params.repr_layers` | list[int] | `[-1]` | -- | Transformer layers to extract (negative indexing supported) |
| `params.include` | list[str] | `["mean"]` | -- | Output types: `mean`, `per_token`, `logits` |

**Response:**

```json
{
  "results": [
    {
      "embeddings": [{"layer": 20, "embedding": [0.012, -0.034, ...]}],
      "per_token_embeddings": null,
      "logits": null,
      "vocab_tokens": null,
      "context_sequence_count": 2
    }
  ]
}
```

### `predict`

Performs masked token prediction. Sequences must contain one or more `?` mask tokens.

**Request Parameters:**

| Parameter | Type | Default | Range | Description |
|-----------|------|---------|-------|-------------|
| `items[].sequence` | str | *(required)* | 1-2048 AA | Sequence with `?` mask tokens |
| `items[].context_sequences` | list[str] | None | 0-50 seqs | Optional context (no `?` allowed in context) |

**Response:**

```json
{
  "results": [
    {
      "logits": [[0.1, -0.3, ...], ...],
      "sequence_tokens": ["M", "?", "K", ...],
      "vocab_tokens": ["A", "C", "D", ..., "Y"]
    }
  ]
}
```

`logits` shape is `[L, 20]` restricted to the 20 canonical amino acids.

### `predict_log_prob`

Computes the total log-probability of an unmasked sequence, optionally conditioned on context sequences.

**Request Parameters:**

| Parameter | Type | Default | Range | Description |
|-----------|------|---------|-------|-------------|
| `items[].sequence` | str | *(required)* | 1-2048 AA | Unmasked sequence (canonical 20 AA only) |
| `items[].context_sequences` | list[str] | None | 0-50 seqs | Optional context sequences (canonical 20 AA) |

**Response:**

```json
{
  "results": [
    {
      "log_prob": -245.67
    }
  ]
}
```

## Usage Examples

```python
# Encode with context sequences
from models.e1.schema import (
    E1EncodeRequest,
    E1EncodeRequestItem,
    E1EncodeRequestParams,
)

encode_request = E1EncodeRequest(
    params=E1EncodeRequestParams(repr_layers=[-1], include=["mean"]),
    items=[
        E1EncodeRequestItem(
            sequence="TPSSKEMMSQALKATFSGFTKEQQRLGIPKDPRQWTETHVRDWVMWAVNEFSLKGVDFQKF",
            context_sequences=[
                "MPSSKEMMSQALKATFSGFTKEQQRLGIPKDPRQWTETHVRDWVMWAVNEFSLKGVDFQKL",
                "TPSSKELMSQALKATFSGFTKEQQRLGIPKDPRQWTETHVRDWVMWAVNEFSLKGVDFQKY",
            ],
        ),
    ],
)

# Predict masked positions
from models.e1.schema import E1PredictRequest, E1PredictRequestItem

predict_request = E1PredictRequest(
    items=[
        E1PredictRequestItem(
            sequence="TPSSKE?MSQALKAT?SGFTKEQQ",
        )
    ],
)

# Score log probability with context
from models.e1.schema import E1PredictLogProbRequest, E1PredictLogProbRequestItem

log_prob_request = E1PredictLogProbRequest(
    items=[
        E1PredictLogProbRequestItem(
            sequence="TPSSKEMMSQALKATFSGFTKEQQRLGIPKDPRQWTETHVRDWVMWAVNEFSLKGVDFQKF",
            context_sequences=["MPSSKEMMSQALKATFSGFTKEQQRLGIPKDPRQWTETHVRDWVMWAVNEFSLKGVDFQKL"],
        )
    ],
)
```

## Performance & Benchmarks

### SOTA Status

E1 introduces retrieval-augmented protein language modeling. When context sequences are available, it is expected to improve over single-sequence models on fitness prediction and embedding quality tasks.

From Jain et al. (2025): On ProteinGym v1.3 (217 DMS substitution assays), E1 600M achieves average Spearman correlation of 0.420 in single-sequence mode (outperforming ESM2-650M at 0.414) and 0.477 in retrieval-augmented mode (surpassing PoET at 0.470). Performance scales with model size across all E1 variants (150M, 300M, 600M). E1 also achieves state-of-the-art unsupervised contact-map prediction on CAMEO subsets.

## Implementation Verification

### Verification Method

Golden output comparison: Test fixtures compare outputs against reference values stored in R2 with relative tolerance of 1e-4 and cosine distance threshold of 0.02.

### Test Cases

| Test Case | Action | Input | Verification |
|-----------|--------|-------|--------------|
| Single sequence encode | `encode` | 1 protein, mean pooling | Cosine similarity to golden output |
| Multi-sequence encode | `encode` | Multiple proteins | Cosine similarity to golden output |
| Context-augmented encode | `encode` | Query + 2 context sequences | Cosine similarity to golden output |
| Masked prediction | `predict` | Sequence with `?` tokens | Logit comparison to golden output |
| Log probability (single) | `predict_log_prob` | Unmasked sequence | Negative finite float |
| Log probability (context) | `predict_log_prob` | Sequence + 2 context | Negative finite float |

### Verification Status

**Status: VERIFIED** -- Integration tests pass for all variants (150m, 300m, 600m) across all actions.

## Resource Requirements

| Variant | GPU | Memory | CPU |
|---------|-----|--------|-----|
| `e1-150m` | T4 (16 GB VRAM) | 8 GB | 3 cores |
| `e1-300m` | L4 (24 GB VRAM) | 16 GB | 4 cores |
| `e1-600m` | L4 (24 GB VRAM) | 24 GB | 4 cores |

## Implementation Notes

- **No GPU memory snapshots**: Disabled due to SIGSEGV on restore. Uses `BillingMixin` (not `BillingMixinSnap`).
- **torch.compile disabled**: `torch._dynamo.config.disable = True` to avoid flex_attention compilation errors.
- **Dtype selection**: E1-150M uses float16 (T4 native); E1-300M/600M use bfloat16 (L4 Ada Lovelace native).
- **config.json patching**: auto_map is injected at runtime for trust_remote_code support.
- **Logit slicing**: Only 20 canonical amino acid logits are returned; non-canonical tokens are excluded.
- **Caching**: Standard Redis/R2 two-tier caching via `BillingMixin`.

## License

- **Code & Weights**: Apache-2.0 ([HuggingFace](https://huggingface.co/Synthyra/Profluent-E1-600M))

## References & Citations

### Links

- **Weights (150M)**: [huggingface.co/Synthyra/Profluent-E1-150M](https://huggingface.co/Synthyra/Profluent-E1-150M)
- **Weights (300M)**: [huggingface.co/Synthyra/Profluent-E1-300M](https://huggingface.co/Synthyra/Profluent-E1-300M)
- **Weights (600M)**: [huggingface.co/Synthyra/Profluent-E1-600M](https://huggingface.co/Synthyra/Profluent-E1-600M)

---

*See also: [MODEL.md](MODEL.md) for technical deep-dive | [BIOLOGY.md](BIOLOGY.md) for biological context*
