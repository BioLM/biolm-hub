# Evo2

> **One-line summary**: A multi-domain autoregressive DNA foundation model (1B--40B parameters) built on StripedHyena, supporting embedding extraction, log-probability scoring, and sequence generation across prokaryotic, eukaryotic, and viral genomes.

## Overview

**Evo 2** is the successor to Evo 1, developed by the Arc Institute, Stanford, and collaborators. It extends the StripedHyena hybrid architecture to larger scales (up to 40B parameters) and, critically, is trained on genomes from **all domains of life** -- prokaryotes, eukaryotes, and viruses -- overcoming Evo 1's prokaryotic bias.

Evo 2 offers three actions: **embedding extraction** (new in Evo 2), **log-probability scoring**, and **sequence generation**. This makes it a versatile DNA foundation model suitable for both analysis (embeddings, scoring) and design (generation) workflows.

The model was described in Brixi et al. "Genome modeling and design across all domains of life with Evo 2" (bioRxiv, 2025).

## Architecture

| Property | Value |
|----------|-------|
| Architecture | StripedHyena (hybrid gated convolution + attention) |
| Tokenization | Byte-level (single nucleotide per token) |
| Vocabulary | A, C, G, T + special tokens |
| Training data | Multi-domain genomes (prokaryotic, eukaryotic, viral) |
| Training objective | Autoregressive next-token prediction |
| Max sequence length | 4,096 nt (BioLM API) |
| License | Apache-2.0 |

For detailed architecture information, see [MODEL.md](MODEL.md).

## Model Variants

| Variant | Slug | Parameters | Context | GPU | Memory | Status |
|---------|------|-----------|---------|-----|--------|--------|
| **Evo2 1B Base** | `evo2-1b-base` | ~1B | 8k nt | L4 | 16 GB | Enabled |
| **Evo2 7B Base** | `evo2-7b-base` | ~7B | 8k nt | L4 | 16 GB | Enabled |
| Evo2 7B | `evo2-7b` | ~7B | 1M nt | -- | -- | Planned |
| Evo2 40B Base | `evo2-40b-base` | ~40B | 8k nt | -- | -- | Planned |
| Evo2 40B | `evo2-40b` | ~40B | 1M nt | -- | -- | Planned |

The default variant is **evo2-1b-base**. Only the 1b-base variant is actively tested.

## Capabilities & Limitations

**CAN be used for:**
- Extracting per-layer DNA embeddings (mean or last-token pooling) for downstream ML tasks
- Scoring DNA sequences via total log-probability under the autoregressive distribution
- Generating novel DNA sequences from a seed prompt with configurable sampling parameters
- Zero-shot variant effect assessment by comparing wild-type vs. mutant log-probabilities
- Multi-domain genomic analysis (prokaryotic, eukaryotic, viral)

**CANNOT be used for:**
- Sequences containing ambiguous bases (N, R, Y, etc.) -- only A, C, G, T accepted
- Sequences longer than 4,096 nucleotides (BioLM API limit)
- RNA sequences (U is not accepted)
- Protein sequences (use ESM2 or similar)

**Other considerations:**
- The `generate` action is stochastic by default; provide an explicit `seed` for reproducibility
- Log-probability scores are summed over all positions; normalize by length for cross-length comparisons
- Batch size is limited to 1 item per request

## Actions / Endpoints

### `encode`

Extracts per-layer embeddings from specified transformer blocks. Returns mean-pooled and/or last-token embeddings.

**Request Schema**: `Evo2EncodeRequest`

| Parameter | Type | Default | Range | Description |
|-----------|------|---------|-------|-------------|
| `items[].sequence` | str | (required) | 1--4096 nt | DNA sequence (A/C/G/T only) |
| `params.embedding_layers` | list[int] | `[-2]` | valid layer indices | Transformer layers to extract (negative indexing supported) |
| `params.mlp_layer` | int | `3` | -- | MLP sublayer index within each block |
| `params.include` | list[str] | `["mean"]` | `mean`, `last` | Pooling strategies to include |

**Batch limit**: 1 item per request.

**Response Schema**: `Evo2EncodeResponse`

```json
{
  "results": [
    {
      "embeddings": [
        {
          "layer": 22,
          "mean": [0.012, -0.034, ...],
          "last": [0.008, -0.021, ...]
        }
      ]
    }
  ]
}
```

### `log_prob`

Computes the total log-probability of each DNA sequence under Evo 2's autoregressive distribution.

**Request Schema**: `Evo2PredictLogProbRequest`

| Parameter | Type | Default | Range | Description |
|-----------|------|---------|-------|-------------|
| `items[].sequence` | str | (required) | 1--4096 nt | DNA sequence (A/C/G/T only) |

**Batch limit**: 1 item per request.

**Response Schema**: `Evo2PredictLogProbResponse`

```json
{
  "results": [
    {
      "log_prob": -15.234
    }
  ]
}
```

### `generate`

Generates new DNA sequences from a prompt using autoregressive sampling.

**Request Schema**: `Evo2GenerateRequest`

| Parameter | Type | Default | Range | Description |
|-----------|------|---------|-------|-------------|
| `items[].prompt` | str | (required) | 1--4096 nt | DNA seed sequence (A/C/G/T only) |
| `params.max_new_tokens` | int | `100` | 1--4096 | Number of tokens to generate |
| `params.temperature` | float | `1.0` | >= 0.0 | Sampling temperature |
| `params.top_k` | int | `4` | >= 1 | Top-k sampling parameter |
| `params.top_p` | float | `1.0` | 0.0--1.0 | Nucleus sampling parameter |
| `params.seed` | int or null | `null` | -- | Random seed for reproducibility |

**Batch limit**: 1 item per request.

**Response Schema**: `Evo2GenerateResponse`

```json
{
  "results": [
    {
      "generated": "ACGTACGTACGT..."
    }
  ]
}
```

## Usage Examples

```python
# Encode -- extract embeddings
from models.evo2.schema import (
    Evo2EncodeIncludeOptions,
    Evo2EncodeRequest,
    Evo2EncodeRequestItem,
    Evo2EncodeRequestParams,
)

encode_request = Evo2EncodeRequest(
    params=Evo2EncodeRequestParams(
        embedding_layers=[-2],
        include=[Evo2EncodeIncludeOptions.MEAN, Evo2EncodeIncludeOptions.LAST],
    ),
    items=[Evo2EncodeRequestItem(sequence="ACGTACGTACGTACGT")],
)

# Score DNA sequences
from models.evo2.schema import Evo2PredictLogProbRequest, Evo2PredictLogProbRequestItem

logprob_request = Evo2PredictLogProbRequest(
    items=[Evo2PredictLogProbRequestItem(sequence="ATGATGATGATGATG")]
)

# Generate DNA sequences with seed for reproducibility
from models.evo2.schema import (
    Evo2GenerateRequest,
    Evo2GenerateRequestItem,
    Evo2GenerateRequestParams,
)

generate_request = Evo2GenerateRequest(
    params=Evo2GenerateRequestParams(
        max_new_tokens=100,
        temperature=0.8,
        top_k=10,
        seed=42,
    ),
    items=[Evo2GenerateRequestItem(prompt="ATGAAAGCAATTTTCGTACTG")],
)
```

## Performance & Benchmarks

### Published Results

From Brixi et al. (bioRxiv, 2025):
- Evo 2 outperforms Evo 1 on DNA fitness prediction benchmarks
- Multi-domain training improves eukaryotic sequence modeling
- Scaling from 1B to 40B yields consistent improvements


### SOTA Status

Evo 2 represents the current frontier in multi-domain DNA foundation modeling as of its 2025 preprint release.

## Implementation Verification

### Verification Method

Numerical reproduction: integration tests compare model outputs against golden fixtures generated on the same Modal infrastructure.

### Test Cases

| Action | Input | Tolerance | Status |
|--------|-------|-----------|--------|
| `encode` | "ACGTACGTAC", layer 22, mean+last | rel_tol=1e-4 | PASS |
| `log_prob` | "ACGTACGTAC" | rel_tol=1e-4 | PASS |
| `generate` | Prompt "ACGT", 10 tokens | Valid DNA check | PASS |

### Verification Status

**Status: VERIFIED** -- Integration tests pass for the 1b-base variant across all three actions.

## Resource Requirements

| Variant | GPU | Memory | CPU |
|---------|-----|--------|-----|
| `evo2-1b-base` | L4 | 16 GB | 4 cores |
| `evo2-7b-base` | L4 | 16 GB | 4 cores |

| Resource | Value |
|----------|-------|
| Cold start | Reduced via Modal CPU memory snapshot (CPU two-phase: load on CPU, move to GPU after restore) |
| Batch size | 1 item per request |
| Key dependencies | `torch`, `flash-attn==2.7.3`, `stripedhyena==0.2.2`, `einops==0.8.0`, `transformer-engine==1.13` |

## Implementation Notes

- **Memory snapshots**: Uses `@modal.enter(snap=True)` for CPU-phase setup, then `@modal.enter(snap=False)` to load and move model to GPU after snapshot restore.
- **Snapshot base class**: Inherits from `ModelMixinSnap` for snapshot-compatible health and lifecycle hooks.
- **GPU snapshots**: Not used — transformer_engine/flash-attn prevent GPU snapshot creation. CPU memory snapshot is used instead (`enable_memory_snapshot=True`).
- **Container image**: Built from `pytorch/pytorch:2.4.1-cuda12.4-cudnn9-devel` with flash-attn and Evo2 installed from GitHub at pinned commit `67a079496b`.
- **Download layer**: Model weights downloaded via unified `setup_download_layer` with R2 caching and HuggingFace fallback.
- **Determinism**: `encode` and `log_prob` are fully deterministic. `generate` requires explicit seed for reproducibility.

## License

- **Code**: Apache-2.0 ([LICENSE](https://github.com/ArcInstitute/evo2/blob/main/LICENSE))
- **Weights**: Apache-2.0

## References & Citations

### Papers

1. Brixi G, Durber MG, Nguyen E, Poli M, Bartie LJ, Hie BL, Re C, Hsu PD. "Genome modeling and design across all domains of life with Evo 2." bioRxiv (2025). [doi:10.1101/2025.02.18.638918](https://doi.org/10.1101/2025.02.18.638918)

### BibTeX

```bibtex
@article{brixi2025evo2,
  title={Genome modeling and design across all domains of life with Evo 2},
  author={Brixi, Garyk and Durber, Matthew G and Nguyen, Eric and Poli, Michael and Bartie, Liam J and Hie, Brian L and Re, Christopher and Hsu, Patrick D},
  journal={bioRxiv},
  year={2025},
  doi={10.1101/2025.02.18.638918}
}
```

### Links

- **Preprint**: [bioRxiv 10.1101/2025.02.18.638918](https://www.biorxiv.org/content/10.1101/2025.02.18.638918v1)
- **Code**: [github.com/ArcInstitute/evo2](https://github.com/ArcInstitute/evo2)
- **Model weights**: [huggingface.co/arcinstitute/evo2_1b_base](https://huggingface.co/arcinstitute/evo2_1b_base)

---

*See also: [MODEL.md](MODEL.md) for technical deep-dive | [BIOLOGY.md](BIOLOGY.md) for biological context*
