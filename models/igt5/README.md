# IgT5

> **One-line summary**: T5 encoder-based antibody language model with paired and unpaired variants that produces sequence-level and per-residue embeddings for immunoglobulin sequences.

## Overview

IgT5 (Immunoglobulin T5) is an antibody language model developed by Kenlay, Dreyer, Sherborne, and Deane. It uses the encoder component of the T5 architecture, fine-tuned on large-scale antibody sequence data. IgT5 is available in two variants: a paired variant that processes concatenated heavy-light chain sequences and an unpaired variant for individual chain analysis.

IgT5 is published alongside IgBERT in "Large scale paired antibody language models" (Kenlay et al., 2024). While both models target antibody representation learning, IgT5 uses the T5 encoder (with relative position biases) and IgBERT uses BERT (with absolute positional embeddings). IgT5 is an embedding-only model -- for sequence generation or log-probability scoring, use IgBERT instead.

## Architecture

| Property | Value |
|----------|-------|
| Architecture | T5 encoder (T5EncoderModel) |
| Training objective | Span corruption |
| Training data | Large-scale antibody sequences (Exscientia) |
| Tokenizer | T5Tokenizer (SentencePiece) |
| Positional encoding | Relative position biases |
| License | CC-BY-4.0 ([Zenodo](https://zenodo.org/doi/10.5281/zenodo.10876908)) |

**License note**: Zenodo deposit (the authoritative release linked from the arXiv paper) specifies CC-BY-4.0. HuggingFace metadata lists MIT, but Zenodo is the canonical source.

## Model Variants

| Variant | Input Type | Max Seq Length | GPU | Memory | CPU |
|---------|------------|----------------|-----|--------|-----|
| `igt5-paired` | Heavy + Light | 256 per chain | T4 | 16 GB | 4 cores |
| `igt5-unpaired` | Single chain | 512 | T4 | 16 GB | 4 cores |

The paired variant processes both chains jointly (separated by `</s>`). The unpaired variant processes individual heavy or light chains.

## Capabilities & Limitations

**CAN be used for:**
- Generating mean-pooled sequence embeddings for antibody sequences
- Generating per-residue embeddings for position-level analysis
- Both paired (heavy+light) and unpaired (single chain) analysis

**CANNOT be used for:**
- Masked residue prediction / sequence generation (use IgBERT instead)
- Log-probability sequence scoring (use IgBERT instead)
- Non-antibody proteins (use ESM-2 or similar)
- 3D structure prediction
- Antibody numbering and annotation (use SADIE)
- Mixing paired and unpaired items in a single request

**Other considerations:**
- Both variants require GPU (T4)
- Batch size capped at 8 sequences per request
- All items in a request must match the deployed variant (all paired or all unpaired)

## Actions / Endpoints

### `encode`

Generates embeddings for antibody sequences. Supports mean-pooled and per-residue embedding outputs.

**Request Parameters:**

| Parameter | Type | Default | Range | Description |
|-----------|------|---------|-------|-------------|
| `items[].heavy` | str | `null` | 1--256 chars | Heavy chain sequence (paired mode) |
| `items[].light` | str | `null` | 1--256 chars | Light chain sequence (paired mode) |
| `items[].sequence` | str | `null` | 1--512 chars | Single chain sequence (unpaired mode) |
| `params.include` | list[str] | `["mean"]` | `mean`, `residue` | Output types to include |

Provide either (`heavy` + `light`) for paired mode or `sequence` for unpaired mode. Do not mix both.

**Response:**

```json
{
  "results": [
    {
      "embeddings": [0.012, -0.034, ...],
      "residue_embeddings": null
    }
  ]
}
```

Fields are `null` (omitted from JSON) unless their corresponding `include` option is set.

**Schema classes**: `IgT5EncodeRequest` -> `IgT5EncodeResponse`

## Usage Examples

```python
# Encode -- paired antibody embeddings
from models.igt5.schema import (
    IgT5EncodeRequest,
    IgT5EncodeRequestItem,
    IgT5EncodeRequestParams,
)

encode_request = IgT5EncodeRequest(
    params=IgT5EncodeRequestParams(include=["mean"]),
    items=[
        IgT5EncodeRequestItem(
            heavy="QVQLVQSGAEVKKPGASVKVSCKVSGYTSPTTIHWVRQAPGKGLEWMG",
            light="DIQMTQSPSSVSASVGDRVTITCRASQSIGSFLAWYQQKPGKAPKLLIY",
        ),
    ],
)

# Encode -- unpaired single chain with residue embeddings
encode_unpaired = IgT5EncodeRequest(
    params=IgT5EncodeRequestParams(include=["mean", "residue"]),
    items=[
        IgT5EncodeRequestItem(
            sequence="QVQLVQSGAEVKKPGASVKVSCKVSGYTSPTTIHWVRQAPGKGLEWMG",
        ),
    ],
)
```

## Performance & Benchmarks

### Published Results

IgT5 is evaluated alongside IgBERT, comparing T5 and BERT architectures for antibody representation learning.

<!-- TODO: Extract IgT5-specific benchmark numbers from Kenlay et al. 2024 -- see sources.yaml primary_papers[0] (arXiv: 2403.17889) -->

### SOTA Status

IgT5 provides a strong baseline for antibody embedding quality, particularly with its T5-based relative position encoding. It complements IgBERT by offering an alternative architectural approach for antibody representation.

## Implementation Verification

### Verification Method

Numerical reproduction: The BioLM implementation loads official pre-trained weights from HuggingFace via `T5EncoderModel.from_pretrained()` and `T5Tokenizer.from_pretrained()`. Test fixtures compare outputs against golden reference outputs stored in R2.

### Test Cases

| Test Case | Action | Variant | Verification |
|-----------|--------|---------|--------------|
| Paired encode | `encode` | paired | Relative tolerance 1e-4 |
| Unpaired encode | `encode` | unpaired | Relative tolerance 1e-4 |

### Verification Status

**Status: VERIFIED** -- Integration tests pass for both paired and unpaired variants with rel_tol=1e-4.

## Resource Requirements

| Variant | GPU | Memory | CPU |
|---------|-----|--------|-----|
| `igt5-paired` | T4 | 16 GB | 4 cores |
| `igt5-unpaired` | T4 | 16 GB | 4 cores |

## Implementation Notes

- **Memory snapshots**: IgT5 uses GPU memory snapshots (`enable_memory_snapshot=True`, `enable_gpu_snapshot=True`) for fast cold starts.
- **Determinism**: Seeds are set (`torch.manual_seed(42)`, `torch.cuda.manual_seed_all(42)`) for reproducible outputs.
- **Weight loading**: Weights are downloaded from R2 and loaded via HuggingFace `T5EncoderModel.from_pretrained()`.
- **Dependencies**: `transformers==4.48.1`, `sentencepiece==0.2.0`, `safetensors==0.5.3`
- **Variant dispatch**: The model type (paired/unpaired) is set at deployment time via the `MODEL_TYPE` environment variable.
- **Embedding computation**: Special tokens are masked out before mean pooling. Per-residue embeddings include padding positions which are zeroed out.
- **Caching**: Inherits standard Redis/R2 two-tier caching from `BillingMixinSnap`.

## License

- **Code and weights**: CC-BY-4.0 ([Zenodo](https://zenodo.org/doi/10.5281/zenodo.10876908); HuggingFace metadata says MIT but Zenodo is the canonical source)

## References & Citations

### Papers

1. Kenlay H, Dreyer FA, Sherborne B, Deane CM. "Large scale paired antibody language models." *arXiv preprint* (2024). [arXiv: 2403.17889](https://arxiv.org/abs/2403.17889)

### BibTeX

```bibtex
@article{kenlay2024large,
  title={Large scale paired antibody language models},
  author={Kenlay, Henry and Dreyer, Fr{\'e}d{\'e}ric A and Sherborne, Berton and Deane, Charlotte M},
  journal={arXiv preprint arXiv:2403.17889},
  year={2024}
}
```

### Links

- **Paper**: [arXiv: 2403.17889](https://arxiv.org/abs/2403.17889)
- **Model weights (paired)**: [huggingface.co/Exscientia/IgT5](https://huggingface.co/Exscientia/IgT5)
- **Model weights (unpaired)**: [huggingface.co/Exscientia/IgT5_unpaired](https://huggingface.co/Exscientia/IgT5)

---

*See also: [MODEL.md](MODEL.md) for technical deep-dive | [BIOLOGY.md](BIOLOGY.md) for biological context*
