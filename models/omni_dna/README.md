# Omni-DNA

> **One-line summary**: A family of multi-task DNA foundation models (20M--1B parameters) using BPE tokenization on the OLMo architecture, supporting embedding extraction and autoregressive log-probability scoring.

## Overview

Omni-DNA is a family of multi-task, cross-modal genomic transformers that can handle DNA-based tasks in a single auto-regressive framework. Built on the OLMo (Open Language Model) architecture, Omni-DNA uses BPE (byte-pair encoding) tokenization to learn data-driven subword units from DNA sequences, providing an alternative to fixed k-mer (Nucleotide Transformer) or byte-level (Evo) tokenization approaches.

The model provides two actions: **embedding extraction** (mean or last-token pooling) and **log-probability scoring** for DNA sequences.

**Reference**: [Omni-DNA on HuggingFace](https://huggingface.co/collections/zehui127/omni-dna-67a2230c352d4fd8f4d1a4bd)

## Architecture

| Property | Value |
|----------|-------|
| Architecture | OLMo Transformer (AutoModelForCausalLM) |
| Tokenization | BPE, vocabulary size 4096 |
| Training objective | Autoregressive (causal language modeling) |
| Max sequence length | 2,048 BPE tokens |
| Input alphabet | A, C, G, T only |
| License | Apache-2.0 |

For detailed architecture information, see [MODEL.md](MODEL.md).

## Model Variants

| Variant | Slug | Parameters | GPU | Memory | Status |
|---------|------|-----------|-----|--------|--------|
| 20M | `omni-dna-20m` | ~20M | T4 | 4 GB | Planned |
| 60M | `omni-dna-60m` | ~60M | T4 | 4 GB | Planned |
| 116M | `omni-dna-116m` | ~116M | T4 | 8 GB | Planned |
| 300M | `omni-dna-300m` | ~300M | T4 | 10 GB | Planned |
| 700M | `omni-dna-700m` | ~700M | T4 | 16 GB | Planned |
| **1B** | `omni-dna-1b` | ~1B | L4 | 16 GB | **Enabled** |

The default variant is **1B** (`zehui127/Omni-DNA-1B`).

## Capabilities & Limitations

**CAN be used for:**
- Extracting DNA sequence embeddings (mean-pooled or last-token) for downstream ML tasks
- Scoring DNA sequences via total autoregressive log-probability
- Zero-shot variant effect assessment by comparing log-probabilities
- Batch processing of up to 2 sequences per request

**CANNOT be used for:**
- DNA sequence generation (no generate endpoint)
- Sequences containing ambiguous bases (N, R, Y, etc.) -- only A, C, G, T accepted
- RNA sequences (U is not accepted)
- Protein sequences (use ESM2 or similar)

**Other considerations:**
- BPE tokenization means sequence length in tokens does not directly map to nucleotide count
- Sequences are truncated at 2,048 BPE tokens (approximately 4,000--8,000 nucleotides)
- DNA sequences are tokenized using a BPE tokenizer that may split a sequence into sub-tokens (e.g., "A", "AA", "TG", etc.)

## Actions / Endpoints

### `encode`

Returns embeddings for each DNA sequence. Embeddings are extracted from the final hidden layer.

**Request Schema**: `OmniDNAEncodeRequest`

| Parameter | Type | Default | Range | Description |
|-----------|------|---------|-------|-------------|
| `items[].sequence` | str | (required) | 1--2048 nt | DNA sequence (A/C/G/T only) |
| `params.include` | list[str] | `["mean"]` | `mean`, `last` | Pooling strategies to include |

**Batch limit**: 1--2 items per request.

**Response Schema**: `OmniDNAEncodeResponse`

```json
{
  "results": [
    {
      "mean": [{"embedding": [0.012, -0.034, ...]}],
      "last": [{"embedding": [0.008, -0.021, ...]}]
    }
  ]
}
```

Fields are omitted when not included in the `include` parameter.

### `predict_log_prob`

Computes the total log-probability of each DNA sequence under the auto-regressive model. The model processes the batch in one forward pass, applies log-softmax over the entire vocabulary, and sums the log probabilities corresponding to the actual tokens (ignoring padded positions).

**Request Schema**: `OmniDNAPredictLogProbRequest`

| Parameter | Type | Default | Range | Description |
|-----------|------|---------|-------|-------------|
| `items[].sequence` | str | (required) | 1--2048 nt | DNA sequence (A/C/G/T only) |

**Batch limit**: 1--2 items per request.

**Response Schema**: `OmniDNAPredictLogProbResponse`

```json
{
  "results": [
    {
      "log_prob": -15.234
    }
  ]
}
```

## Usage Examples

```python
# Encode -- get mean embeddings
from models.omni_dna.schema import (
    OmniDNAEncodeIncludeOptions,
    OmniDNAEncodeRequest,
    OmniDNAEncodeRequestItem,
    OmniDNAEncodeRequestParams,
)

encode_request = OmniDNAEncodeRequest(
    params=OmniDNAEncodeRequestParams(
        include=[OmniDNAEncodeIncludeOptions.MEAN, OmniDNAEncodeIncludeOptions.LAST],
    ),
    items=[OmniDNAEncodeRequestItem(sequence="ACGTACGTACGTACGT")],
)

# Score DNA sequences
from models.omni_dna.schema import (
    OmniDNAPredictLogProbRequest,
    OmniDNAPredictLogProbRequestItem,
)

logprob_request = OmniDNAPredictLogProbRequest(
    items=[OmniDNAPredictLogProbRequestItem(sequence="ATGATGATGATGATG")]
)
```

## Performance & Benchmarks

### Published Results

From Li (2025):
- Omni-DNA demonstrates competitive performance on multi-task DNA benchmarks
- Unified framework handles embedding extraction and sequence scoring within a single model

<!-- TODO: Extract specific benchmark numbers from Li 2025 paper -->

### SOTA Status

Omni-DNA is a recent model (2025) that explores BPE tokenization for DNA foundation models. Comparative benchmarks against established models are pending full publication.

## Implementation Verification

### Verification Method

Numerical reproduction: integration tests compare model outputs against golden fixtures with relative tolerance of 1e-4.

### Test Cases

| Action | Input | Tolerance | Status |
|--------|-------|-----------|--------|
| `encode` | DNA sequence, mean pooling | rel_tol=1e-4 | PASS |
| `predict_log_prob` | DNA sequence | rel_tol=1e-4 | PASS |

### Verification Status

**Status: VERIFIED** -- Integration tests pass for the 1B variant with rel_tol=1e-4.

## Resource Requirements

| Variant | GPU | Memory | CPU |
|---------|-----|--------|-----|
| `omni-dna-1b` | L4 | 16 GB | 4 cores |

| Resource | Value |
|----------|-------|
| Cold start | Reduced via Modal GPU memory snapshot |
| Batch size | 2 items max per request |
| Key dependencies | `transformers==4.47.0`, `ai2-olmo==0.6.0`, `safetensors==0.4.5` |

## Implementation Notes

- **Memory snapshots**: Uses `@modal.enter(snap=True)` to load model directly on GPU for GPU memory snapshot.
- **BillingMixinSnap**: Inherits from `BillingMixinSnap` for snapshot-compatible billing.
- **GPU snapshots**: Enabled via `experimental_options={"enable_gpu_snapshot": True}`.
- **Container image**: Built from `pytorch/pytorch:2.3.1-cuda11.8-cudnn8-runtime`.
- **Weight loading**: Model weights loaded from `.safetensors` file via HuggingFace `AutoModelForCausalLM`.
- **Determinism**: Seeds set to 42 (`torch.manual_seed(42)`, `torch.cuda.manual_seed_all(42)`).
- **BPE tokenization**: Uses `AutoTokenizer.from_pretrained()` with `trust_remote_code=True`.

## Notes

1. **BPE Encoding & Context:**
   DNA sequences are segmented into BPE tokens (e.g., "A", "C", "AA", "TG", etc.). Although the model is trained on sequences of up to about 250 BPE tokens, it can handle sequences of roughly 512 tokens.

2. **DNA-only Validation:**
   Input sequences must contain only the unambiguous nucleotide characters: A, C, G, and T.

3. **Resource Usage:**
   The 1B variant requires a GPU such as L4.

4. **Multi-Task Capabilities:**
   For advanced tasks (e.g., adding classification heads), the model could be loaded via `AutoModelForSequenceClassification` with the same identifier.

## License

- **Code**: Apache-2.0
- **Weights**: Apache-2.0 ([HuggingFace](https://huggingface.co/zehui127/Omni-DNA-1B))

## References & Citations

### Papers

1. Li Z. "Omni-DNA: A Unified Multi-Task Framework for DNA Foundation Models." Preprint (2025).

### Links

- **Model weights**: [huggingface.co/zehui127/Omni-DNA-1B](https://huggingface.co/zehui127/Omni-DNA-1B)
- **HuggingFace collection**: [Omni-DNA collection](https://huggingface.co/collections/zehui127/omni-dna-67a2230c352d4fd8f4d1a4bd)

---

*See also: [MODEL.md](MODEL.md) for technical deep-dive | [BIOLOGY.md](BIOLOGY.md) for biological context*
