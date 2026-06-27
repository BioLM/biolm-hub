# MSA Transformer

> **One-line summary**: A 100M-parameter protein language model that operates on Multiple Sequence Alignments (MSAs) using axial attention with tied row attention, producing evolutionary-aware embeddings and unsupervised contact predictions.

## Overview

The MSA Transformer is a protein language model that combines the benefits of evolutionary covariation analysis with deep learning. Unlike single-sequence models (e.g., ESM-2) that process one protein at a time, the MSA Transformer takes a Multiple Sequence Alignment as input, enabling it to directly capture patterns of conservation and covariation across evolutionarily related sequences.

Developed by Meta AI / FAIR as part of the ESM suite, the MSA Transformer uses an axial attention mechanism that alternates between row attention (across positions) and column attention (across sequences). Row attention is tied across all sequences, reducing memory requirements while enabling direct extraction of contact information from attention weights.

## Architecture

| Property | Value |
|----------|-------|
| Architecture | Axial Transformer with tied row attention |
| Parameters | 100M |
| Layers | 12 |
| Embedding dimension | 768 |
| Attention heads | 12 |
| Training data | 26M MSAs from UniRef50/UniClust30 (avg 1192 sequences per MSA) |
| License | MIT |

The model uses axial attention that alternates between row attention (across positions) and column attention (across sequences). Row attention is tied across all sequences, reducing memory from O(ML^2) to O(L^2) while enabling direct extraction of contact information.

For detailed architecture information, see [MODEL.md](MODEL.md).

## Model Variants

MSA Transformer is a single-variant model.

| Variant | Slug | Parameters | GPU | Memory | Status |
|---------|------|-----------|-----|--------|--------|
| **MSA Transformer** | `msa-transformer` | 100M | T4 | 16 GB | Enabled |

## Capabilities & Limitations

**CAN be used for:**
- Extracting evolutionary-aware embeddings from protein family alignments
- Unsupervised contact prediction from attention maps
- Structure-informed representations for downstream tasks
- Transfer learning with MSA-based features
- Per-token embeddings for residue-level prediction tasks

**CANNOT be used for:**
- Proteins without pre-computed MSAs (the model does not perform sequence search)
- Sequence generation or design
- DNA, RNA, or non-protein molecules
- Multi-chain or protein complex analysis
- Proteins longer than 1,024 residues

**Other considerations:**
- Requires pre-computed MSA as input (does not perform sequence search)
- Maximum sequence length: 1,024 residues
- Maximum MSA depth: 256 sequences (recommended)
- Performance degrades significantly with very shallow MSAs (< 16 sequences)
- Not suitable for orphan proteins without homologs
- First sequence in MSA must be the query/reference sequence
- All sequences must be pre-aligned to identical length
- Gap character (`-`) and insert character (`.`) are supported
- Contact predictions are derived from symmetrized, APC-corrected attention maps

## Actions / Endpoints

### `encode`

Encodes MSAs and returns embeddings, attention maps, and/or contact predictions. Multiple output types can be requested simultaneously.

**Request Schema**: `MSATransformerEncodeRequest`

| Parameter | Type | Default | Range | Description |
|-----------|------|---------|-------|-------------|
| `items[].msa` | list[str] | (required) | 2--256 sequences | Aligned protein sequences (first is query) |
| `params.repr_layers` | list[int] | `[-1]` | valid layer indices | Transformer layers to extract representations from |
| `params.include` | list[str] | `["mean"]` | `mean`, `per_token`, `row_attention`, `contacts` | Output types to include |

**Batch limit**: 1--4 items per request.

**Response Schema**: `MSATransformerEncodeResponse`

```json
{
  "results": [
    {
      "sequence_index": 0,
      "embeddings": [{"layer": 12, "embedding": [0.012, -0.034, ...]}],
      "per_token_embeddings": null,
      "row_attentions": null,
      "contacts": null
    }
  ]
}
```

**Output descriptions**:

- **`mean`**: Mean embedding of the query sequence (first row) from each requested layer. Shape: [embed_dim] per layer. Averaged over residue positions, excluding BOS/EOS.
- **`per_token`**: Per-position embeddings of the query sequence. Shape: [seq_len, embed_dim] per layer. Useful for residue-level prediction tasks.
- **`row_attention`**: Tied row attention maps averaged over heads. Shape: [num_layers, seq_len, seq_len]. These directly encode structural contact information.
- **`contacts`**: Predicted contact map derived from symmetrized, APC-corrected attention weights. Shape: [seq_len, seq_len]. Values indicate predicted probability of physical contact between residue pairs.

Fields are `null` (omitted from JSON) unless their corresponding `include` option is set.

## Usage Examples

```python
# Single MSA encode with contacts
from models.msa_transformer.schema import (
    MSATransformerEncodeIncludeOptions,
    MSATransformerEncodeRequest,
    MSATransformerEncodeRequestItem,
    MSATransformerEncodeRequestParams,
)

request = MSATransformerEncodeRequest(
    params=MSATransformerEncodeRequestParams(
        repr_layers=[-1],
        include=[
            MSATransformerEncodeIncludeOptions.MEAN,
            MSATransformerEncodeIncludeOptions.CONTACTS,
        ],
    ),
    items=[
        MSATransformerEncodeRequestItem(
            msa=[
                "MKTVRQERLKSIVRILERSKEPVSGAQLAEELSVSRQVIVQDIAYLRSLGYNIVATPRGYVL",
                "MKAVRQERLKSIVRILERSKEPVSGAQLAEELSVSRQVIVQDIAYLRSLGYNIVATPRGYVL",
                "MKTVRQERLKSIIRILERSKEPVSGAQLAEELSVSRQVIVQDIAYLRSLGYNIVATPRGYVL",
                "MKTVRQERLKSIVRILERSKEPVSGAQLAEE-SVSRQVIVQDIAYLRSLGYNIVATPRGYVL",
            ]
        )
    ],
)

# Per-token embeddings for residue-level analysis
request = MSATransformerEncodeRequest(
    params=MSATransformerEncodeRequestParams(
        repr_layers=[-1],
        include=[MSATransformerEncodeIncludeOptions.PER_TOKEN],
    ),
    items=[
        MSATransformerEncodeRequestItem(
            msa=[
                "MKTVRQERLKSIVRILERSKEPVSG",
                "MKAVRQERLKSIVRILERSKEPVSG",
                "MKTVRQERLKSIIRILERSKEPVSG",
            ]
        )
    ],
)
```

## Performance & Benchmarks

### Published Results

From Rao et al., ICML (2021):
- Unsupervised contact prediction from tied row attention achieves state-of-the-art among MSA-based unsupervised methods
- Performance improves with MSA depth up to ~128 sequences, then plateaus
- Contact maps outperform previous attention-based methods (e.g., ESM-1b)

### SOTA Status

At the time of publication (2021), MSA Transformer was state-of-the-art for unsupervised protein contact prediction from MSAs. While AlphaFold2 and ESMFold have since superseded it for full structure prediction, MSA Transformer remains useful for fast contact estimation and evolutionary-aware embeddings.

## Implementation Verification

### Verification Method

Baseline comparison against paper specifications combined with architectural consistency checks and synthetic covariation detection tests.

### Test Cases

| Test | Expected | Actual | Source | Status |
|------|----------|--------|--------|--------|
| Embedding dimension | 768 | 768 | Paper: "768 embedding size" | PASS |
| Number of layers | 12 | 12 | Paper: "12 layers" | PASS |
| Contact map symmetry | Symmetric | max_diff=1.49e-07 | APC correction produces symmetric maps | PASS |
| Proximity bias | Short > Long | Short=0.031, Long=0.006 | Expected from protein folding physics | PASS |
| Attention range | [0, 1] | [0.0009, 0.155] | Post-softmax values | PASS |
| Determinism | Identical runs | max_diff=0.0 | Seeded RNG | PASS |
| Covariation detection | >50th percentile | 89.4th percentile | Synthetic MSA with designed covariation | PASS |

### Verification Status

**Status: VERIFIED** -- 7/7 test cases passed. Contact prediction correctly identifies covarying positions at the 89th percentile of long-range contacts. Embeddings and attention maps match architectural specifications from the paper.

**Verification date**: 2024-12-07

## Resource Requirements

| Resource | Value |
|----------|-------|
| GPU | T4 (16 GB VRAM) |
| Memory | 16 GB |
| CPU | 4 cores |
| Timeout | 20 minutes |
| Cold start | Reduced via Modal GPU memory snapshot |
| Batch size | 4 MSAs max per request |
| Dependencies | `fair-esm` (from GitHub, commit 2b369911bb) |

## Implementation Notes

- **Memory snapshots**: Uses `@modal.enter(snap=True)` to load model directly on GPU for GPU memory snapshot.
- **BillingMixinSnap**: Inherits from `BillingMixinSnap` for snapshot-compatible billing.
- **GPU snapshots**: Enabled via `experimental_options={"enable_gpu_snapshot": True}`.
- **Container image**: Built from `pytorch/pytorch:2.0.1-cuda11.7-cudnn8-runtime`.
- **Weight loading**: Uses `esm.pretrained.esm_msa1b_t12_100M_UR50S()` with `torch.hub.set_dir()` for caching.
- **Determinism**: Seeds set to 42 at model load time.
- **Contact prediction**: Contacts are computed by the ESM library's internal `return_contacts=True` mechanism, which applies symmetrization and APC correction to attention weights.
- **Caching**: Standard Redis/R2 two-tier caching via `BillingMixinSnap`.

## License

- **Code**: MIT ([LICENSE](https://github.com/facebookresearch/esm/blob/main/LICENSE))
- **Weights**: MIT (part of the ESM suite from Meta AI)

## References & Citations

### Papers

1. Rao R, Liu J, Verkuil R, Meier J, Canny J, Abbeel P, Sercu T, Rives A. "MSA Transformer." ICML (2021). [DOI: 10.1101/2021.02.12.430858](https://doi.org/10.1101/2021.02.12.430858)

### BibTeX

```bibtex
@article{rao2021msa,
  title={MSA Transformer},
  author={Rao, Roshan and Liu, Jason and Verkuil, Robert and Meier, Joshua and
          Canny, John and Abbeel, Pieter and Sercu, Tom and Rives, Alexander},
  journal={bioRxiv},
  doi={10.1101/2021.02.12.430858},
  year={2021}
}
```

### Links

- **Paper**: [doi.org/10.1101/2021.02.12.430858](https://doi.org/10.1101/2021.02.12.430858)
- **Code**: [github.com/facebookresearch/esm](https://github.com/facebookresearch/esm)

---

*See also: [MODEL.md](MODEL.md) for technical deep-dive | [BIOLOGY.md](BIOLOGY.md) for biological context*
