# ESM C

> **One-line summary**: Next-generation protein representation model from EvolutionaryScale providing high-quality embeddings, masked token prediction, and sequence log-probability scoring in a 300M parameter variant.

## Overview

ESM C (ESM Cambrian) is the latest generation of protein language models from EvolutionaryScale (2024). It provides highly effective embeddings and logits for protein sequences, surpassing older ESM2 models on many benchmarks with improved parameter efficiency. The 300M variant surpasses ESM2-650M. EvolutionaryScale also publishes a 600M variant (Cambrian Non-Commercial); it is not distributed in this catalog.

Three actions are available: `encode` for extracting embeddings and logits, `predict` for masked token prediction, and `log_prob` for computing sequence fitness scores.

## Architecture

| Property | Value |
|----------|-------|
| Architecture | Transformer (optimized for proteins) |
| 300M variant | ~300M parameters |
| Max sequence length | 2048 residues |
| Software package | `esm==3.1.3` |
| Input | Amino acid sequences |
| Output | Embeddings, per-token logits, log-probabilities |

## Model Variants

| Variant | Slug | GPU | HuggingFace Repo |
|---------|------|-----|-----------------|
| 300M | `esmc-300m` | A10G | `EvolutionaryScale/esmc-300m-2024-12` |

## Capabilities & Limitations

**CAN be used for:**
- Extracting mean-pooled or per-token protein embeddings at any Transformer layer
- Computing per-position logits restricted to 20 canonical amino acids
- Predicting amino acid probabilities at masked positions (one or more masks)
- Computing total sequence log-probability as a fitness proxy
- Batch processing up to 8 sequences per request
- Handling sequences with gap characters (`-`) in the encode action

**CANNOT be used for:**
- Sequences longer than 2048 residues
- Nucleic acid sequences (protein-only model)
- Structure prediction directly (use ESMFold or Boltz)
- Generating new protein sequences (use generative models like ProGen2 or Evo)
- Non-canonical amino acid handling in log_prob (requires standard 20 only)

## Actions / Endpoints

### `encode`

Extract embeddings and/or logits from protein sequences.

**Request Parameters:**

| Parameter | Type | Default | Range | Description |
|-----------|------|---------|-------|-------------|
| `params.repr_layers` | list[int] | [-1] | Any valid layer index | Transformer layers to extract (negative indices supported) |
| `params.include` | list[str] | ["mean"] | "mean", "per_token", "logits" | What to include in response |
| `items` | list[ESMCEncodeRequestItem] | (required) | 1--8 items | Sequences to encode |
| `items[].sequence` | str | (required) | 1--2048 chars | Amino acid sequence (extended alphabet + gap) |

**Response:**

```json
{
  "results": [
    {
      "embeddings": [
        {"layer": 29, "embedding": [0.1, -0.2, ...]}
      ],
      "per_token_embeddings": [
        {"layer": 29, "embeddings": [[0.1, ...], [0.2, ...], ...]}
      ],
      "logits": [[0.5, -0.3, ...], ...],
      "vocab_tokens": ["A", "C", "D", "E", "F", ...]
    }
  ]
}
```

Fields are conditionally included based on the `include` parameter. `embeddings` and `per_token_embeddings` have BOS/EOS tokens removed. `logits` are restricted to 20 canonical amino acids.

### `predict`

Predict per-token logits for sequences containing `<mask>` tokens.

**Request Parameters:**

| Parameter | Type | Default | Range | Description |
|-----------|------|---------|-------|-------------|
| `items` | list[ESMCPredictRequestItem] | (required) | 1--8 items | Masked sequences |
| `items[].sequence` | str | (required) | 1--2048 chars | Sequence with one or more `<mask>` tokens |

**Response:**

```json
{
  "results": [
    {
      "logits": [[0.5, -0.3, ...], ...],
      "sequence_tokens": ["M", "K", "T", ...],
      "vocab_tokens": ["A", "C", "D", "E", "F", ...]
    }
  ]
}
```

- `logits`: 2D array (sequence_length x 20), restricted to canonical amino acids
- `sequence_tokens`: Decoded sequence characters (including `<mask>` positions)
- `vocab_tokens`: Amino acid identity for each logit column

### `log_prob`

Compute total log-probability of an unmasked sequence under the model.

**Request Parameters:**

| Parameter | Type | Default | Range | Description |
|-----------|------|---------|-------|-------------|
| `items` | list[ESMCPredictLogProbRequestItem] | (required) | 1--8 items | Unmasked sequences |
| `items[].sequence` | str | (required) | 1--2048 chars | Amino acid sequence (standard 20 only) |

**Response:**

```json
{
  "results": [
    {
      "log_prob": -145.67
    }
  ]
}
```

- `log_prob`: Total log-probability summed over all positions, computed over 20 canonical amino acids only. Always negative or zero.

## Usage Examples

### Extract mean embeddings

```python
from models.esmc.schema import (
    ESMCEncodeRequest,
    ESMCEncodeRequestItem,
    ESMCEncodeRequestParams,
    ESMCEncodeIncludeOptions,
)

request = ESMCEncodeRequest(
    params=ESMCEncodeRequestParams(
        repr_layers=[-1],
        include=[ESMCEncodeIncludeOptions.MEAN],
    ),
    items=[
        ESMCEncodeRequestItem(
            sequence="TPSSKEMMSQALKATFSGFTKEQQRLGIPKDPRQWTETHVRDWVMWAVNEFSLKGVDFQKF"
        )
    ],
)
```

### Extract per-token embeddings and logits

```python
from models.esmc.schema import (
    ESMCEncodeRequest,
    ESMCEncodeRequestItem,
    ESMCEncodeRequestParams,
    ESMCEncodeIncludeOptions,
)

request = ESMCEncodeRequest(
    params=ESMCEncodeRequestParams(
        repr_layers=[-1],
        include=[
            ESMCEncodeIncludeOptions.PER_TOKEN,
            ESMCEncodeIncludeOptions.LOGITS,
        ],
    ),
    items=[
        ESMCEncodeRequestItem(sequence="MKTAYVNNKELSKDVR")
    ],
)
```

### Predict masked positions

```python
from models.esmc.schema import (
    ESMCPredictRequest,
    ESMCPredictRequestItem,
)

request = ESMCPredictRequest(
    items=[
        ESMCPredictRequestItem(
            sequence="MKTAY<mask>NNKELSKDVR"
        )
    ],
)
```

### Compute sequence log-probability

```python
from models.esmc.schema import (
    ESMCPredictLogProbRequest,
    ESMCPredictLogProbRequestItem,
)

request = ESMCPredictLogProbRequest(
    items=[
        ESMCPredictLogProbRequestItem(
            sequence="TPSSKEMMSQALKATFSGFTKEQQRLGIPKDPRQWTETHVRDWVMWAVNEFSLKGVDFQKF"
        )
    ],
)
```

## Performance & Benchmarks

### Published Results

From the EvolutionaryScale blog post (2024):

| Model | Parameters | Relative Performance |
|-------|------------|---------------------|
| **ESMC-300M** | 300M | Surpasses ESM2-650M |
| ESMC-600M (upstream) | 600M | Approaches ESM2-3B (Cambrian Non-Commercial; not distributed here) |
| ESM2-650M | 650M | Established baseline |
| ESM2-3B | 3B | Previous best open model |

### SOTA Status

ESM C represents the current state-of-the-art for open protein language models in its parameter class. The distributed 300M variant surpasses ESM2-650M. EvolutionaryScale also publishes a 600M variant (Cambrian Non-Commercial) that approaches ESM2-3B quality; it is not distributed in this catalog.

## Implementation Verification

### Verification Method

Option A -- Numerical Reproduction: embeddings, logits, and log-probabilities from the BioLM implementation are compared against golden outputs generated using the `esm==3.1.3` package directly.

### Test Cases

| Variant | Action | Tolerance | Status |
|---------|--------|-----------|--------|
| 300m | encode (test 1) | cosine_distance < 0.02, rel_tol 1e-4 | PASS |
| 300m | encode (test 2) | cosine_distance < 0.02, rel_tol 1e-4 | PASS |
| 300m | predict | cosine_distance < 0.02, rel_tol 1e-4 | PASS |
| 300m | log_prob | Negative finite value | PASS |

### Verification Status

**Status: VERIFIED** -- All 4 test cases pass across all 3 actions for the 300M variant.

## Resource Requirements

| Resource | 300M Variant |
|----------|-------------|
| GPU | A10G |
| Memory | 24 GB |
| CPU | 2.0 cores |
| Batch size | 8 |
| Max sequence length | 2048 |
| Memory snapshot | Enabled (GPU snapshot) |

## Implementation Notes

- **Memory snapshots**: Uses `@modal.enter(snap=True)` with GPU memory snapshot enabled. Model is loaded directly on GPU during snapshot creation.
- **Container image**: Based on `pytorch/pytorch:2.6.0-cuda12.4-cudnn9-runtime` with `esm==3.1.3` and `huggingface_hub==0.36.2`.
- **Model loading**: Uses `ESMC.from_pretrained(model_name, device)` from the official `esm` package. HuggingFace Hub cache directory is set to the R2-downloaded model directory via `HF_HUB_CACHE` environment variable, with forced reload of `huggingface_hub.constants` to pick up the new path.
- **Canonical amino acid filtering**: At model setup, a mapping from each of the 20 canonical amino acids to its tokenizer index is built. This mapping is used to slice logits to only the 20 canonical amino acids across all three actions.
- **Determinism**: All outputs are deterministic (seed 42 set at model load, no stochastic operations).
- **HuggingFace revisions**: Pinned to specific commit hash for reproducibility: 300M at `a19d363f`.

## License

- **Model weights (ESM C)**: EvolutionaryScale Cambrian Open License Agreement ([agreement](https://www.evolutionaryscale.ai/policies/cambrian-open-license-agreement)). Requires a prominent "Built with ESM" attribution and an "ESM"-prefixed name for derivative works. See the per-model `LICENSE` file.
- **`esm` package code**: MIT-licensed separately ([GitHub](https://github.com/evolutionaryscale/esm/blob/main/LICENSE.md)); this does not extend to the model weights.
- **Note**: Review the Cambrian Open License Agreement before commercial use.

## References & Citations

### Papers

1. EvolutionaryScale Team. "ESM Cambrian: Next-generation protein representation models." EvolutionaryScale blog post (2024). [Blog](https://www.evolutionaryscale.ai/blog/esm-cambrian)

### BibTeX

```bibtex
@misc{esmc2024,
  title={ESM Cambrian: Next-generation protein representation models},
  author={EvolutionaryScale Team},
  year={2024},
  url={https://www.evolutionaryscale.ai/blog/esm-cambrian}
}
```

### Links

- **Blog post**: [EvolutionaryScale ESM Cambrian](https://www.evolutionaryscale.ai/blog/esm-cambrian)
- **Code**: [GitHub evolutionaryscale/esm](https://github.com/evolutionaryscale/esm)
- **HuggingFace (300M)**: [EvolutionaryScale/esmc-300m-2024-12](https://huggingface.co/EvolutionaryScale/esmc-300m-2024-12)
- **HuggingFace (600M, upstream only)**: [EvolutionaryScale/esmc-600m-2024-12](https://huggingface.co/EvolutionaryScale/esmc-600m-2024-12) _(Cambrian Non-Commercial; not distributed in this catalog)_

---

*See also: [MODEL.md](MODEL.md) for technical deep-dive | [BIOLOGY.md](BIOLOGY.md) for biological context*
