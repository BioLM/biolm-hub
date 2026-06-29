# IgBERT

> **One-line summary**: BERT-based antibody language model with paired and unpaired variants that produces sequence embeddings, masked residue predictions, and log-probability scores for immunoglobulin sequences.

## Overview

IgBERT (Immunoglobulin BERT) is an antibody language model developed by Kenlay, Dreyer, Sherborne, and Deane. It is based on the BERT architecture, fine-tuned from a general protein language model on large-scale antibody sequence data. IgBERT is available in two variants: a paired variant that processes concatenated heavy-light chain sequences and an unpaired variant for individual chain analysis.

IgBERT is part of the same research effort as IgT5 (also available on this platform), with both models published in "Large scale paired antibody language models" (Kenlay et al., 2024). The key distinction is architecture: IgBERT uses BERT (encoder-only), while IgT5 uses the T5 encoder.

## Architecture

| Property | Value |
|----------|-------|
| Architecture | BERT (BertForMaskedLM) |
| Training objective | Masked language modeling (MLM) |
| Training data | Large-scale antibody sequences (Exscientia) |
| Tokenizer | BertTokenizer (character-level, case-sensitive) |
| Embedding dimension | 768 |
| License | CC-BY-4.0 ([Zenodo](https://zenodo.org/doi/10.5281/zenodo.10876908)) |

**License note**: Zenodo deposit (the authoritative release linked from the arXiv paper) specifies CC-BY-4.0. HuggingFace metadata lists MIT, but Zenodo is the canonical source.

## Model Variants

| Variant | Input Type | Max Seq Length | GPU | Memory | CPU |
|---------|------------|----------------|-----|--------|-----|
| `igbert-paired` | Heavy + Light | 256 per chain | T4 | 6 GB | 3 cores |
| `igbert-unpaired` | Single chain | 512 | T4 | 6 GB | 3 cores |

The paired variant processes both chains jointly (separated by `[SEP]`). The unpaired variant processes individual heavy or light chains.

## Capabilities & Limitations

**CAN be used for:**
- Generating mean-pooled, per-residue, or logit embeddings for antibody sequences
- Masked residue prediction (sequence completion with `*` placeholders)
- Zero-shot antibody sequence scoring via log-probability (`log_prob`)
- Both paired (heavy+light) and unpaired (single chain) analysis

**CANNOT be used for:**
- Mixed paired/unpaired items in a single request
- Non-antibody proteins (use ESM-2 or similar)
- 3D structure prediction
- Antibody numbering and annotation (use SADIE)

**Other considerations:**
- Both variants require GPU (T4)
- Batch size capped at 32 sequences per request
- All items in a request must match the deployed variant (all paired or all unpaired)

## Actions / Endpoints

### `encode`

Generates embeddings for antibody sequences. Supports mean-pooled embeddings, per-residue embeddings, and raw logits.

**Request Parameters:**

| Parameter | Type | Default | Range | Description |
|-----------|------|---------|-------|-------------|
| `items[].heavy_chain` | str | `null` | 1--256 chars | Heavy chain sequence (paired mode) |
| `items[].light_chain` | str | `null` | 1--256 chars | Light chain sequence (paired mode) |
| `items[].sequence` | str | `null` | 1--512 chars | Single chain sequence (unpaired mode) |
| `params.include` | list[str] | `["mean"]` | `mean`, `residue`, `logits` | Output types to include |

Provide either (`heavy` + `light`) for paired mode or `sequence` for unpaired mode. Do not mix both.

**Response:**

```json
{
  "results": [
    {
      "embeddings": [0.012, -0.034, ...],
      "residue_embeddings": null,
      "logits": null
    }
  ]
}
```

Fields are `null` (omitted from JSON) unless their corresponding `include` option is set.

**Schema classes**: `IgBertEncodeRequest` -> `IgBertEncodeResponse`

### `generate`

Restores missing residues marked with `*` by predicting the most likely canonical amino acid at each masked position.

**Request Parameters:**

| Parameter | Type | Default | Range | Description |
|-----------|------|---------|-------|-------------|
| `items[].heavy_chain` | str | `null` | 1--256 chars | Heavy chain with `*` at unknown positions (paired) |
| `items[].light_chain` | str | `null` | 1--256 chars | Light chain with `*` at unknown positions (paired) |
| `items[].sequence` | str | `null` | 1--512 chars | Single chain with `*` at unknown positions (unpaired) |

At least one `*` must be present in each item.

**Response (paired):**

```json
{
  "results": [
    {
      "heavy_chain": "QVQLVQSGAEVKKPGASVKVSC...",
      "light_chain": "DIQMTQSPSSVSASVGDRVTITC...",
      "sequence": null
    }
  ]
}
```

**Response (unpaired):**

```json
{
  "results": [
    {
      "heavy_chain": null,
      "light_chain": null,
      "sequence": "QVQLVQSGAEVKKPGASVKVSC..."
    }
  ]
}
```

**Schema classes**: `IgBertGenerateRequest` -> `IgBertGenerateResponse`

### `log_prob`

Computes the total log-probability of antibody sequences under the IgBERT model by summing log P(residue_i | context) at each non-special-token position.

**Request Parameters:**

| Parameter | Type | Default | Range | Description |
|-----------|------|---------|-------|-------------|
| `items[].heavy_chain` | str | `null` | 1--256 chars | Heavy chain sequence (paired) |
| `items[].light_chain` | str | `null` | 1--256 chars | Light chain sequence (paired) |
| `items[].sequence` | str | `null` | 1--512 chars | Single chain sequence (unpaired) |

**Response:**

```json
{
  "results": [
    {
      "log_prob": -185.42
    }
  ]
}
```

More negative values indicate less likely sequences.

**Schema classes**: `IgBertLogProbRequest` -> `IgBertLogProbResponse`

## Usage Examples

```python
# Encode -- paired antibody embeddings
from models.igbert.schema import (
    IgBertEncodeRequest,
    IgBertEncodeRequestItem,
    IgBertEncodeRequestParams,
)

encode_request = IgBertEncodeRequest(
    params=IgBertEncodeRequestParams(include=["mean"]),
    items=[
        IgBertEncodeRequestItem(
            heavy_chain="QVQLVQSGAEVKKPGASVKVSCKVSGYTSPTTIHWVRQAPGKGLEWMG",
            light_chain="DIQMTQSPSSVSASVGDRVTITCRASQSIGSFLAWYQQKPGKAPKLLIY",
        ),
    ],
)

# Encode -- unpaired single chain
encode_unpaired = IgBertEncodeRequest(
    params=IgBertEncodeRequestParams(include=["mean", "residue"]),
    items=[
        IgBertEncodeRequestItem(
            sequence="QVQLVQSGAEVKKPGASVKVSCKVSGYTSPTTIHWVRQAPGKGLEWMG",
        ),
    ],
)

# Generate -- restore missing residues (paired)
from models.igbert.schema import IgBertGenerateRequest, IgBertGenerateRequestItem

generate_request = IgBertGenerateRequest(
    items=[
        IgBertGenerateRequestItem(
            heavy_chain="QVQLVQSG*EVKKPGASVKVSCKVSGYTSPTTI*WVRQAPGKGLEWMG",
            light_chain="DIQMTQSPSSVSASVGDRVTITCRASQ*IGSFLAWYQQKPGKAPKLLIY",
        ),
    ],
)

# Predict log probability
from models.igbert.schema import IgBertLogProbRequest, IgBertEncodeRequestItem

log_prob_request = IgBertLogProbRequest(
    items=[
        IgBertEncodeRequestItem(
            heavy_chain="QVQLVQSGAEVKKPGASVKVSCKVSGYTSPTTIHWVRQAPGKGLEWMG",
            light_chain="DIQMTQSPSSVSASVGDRVTITCRASQSIGSFLAWYQQKPGKAPKLLIY",
        ),
    ],
)
```

## Performance & Benchmarks

### Published Results

IgBERT was evaluated on antibody embedding quality and paired chain modeling in the context of large-scale antibody language models. See Kenlay et al. (2024) (arXiv: 2403.17889) for binding affinity prediction benchmarks and CDR sequence recovery results.

### SOTA Status

IgBERT provides a strong baseline for antibody representation learning, particularly for paired chain analysis. It is one of few models offering both paired and unpaired variants from the same framework.

## Implementation Verification

### Verification Method

Numerical reproduction: The BioLM implementation loads official pre-trained weights from HuggingFace via `BertForMaskedLM.from_pretrained()` and `BertTokenizer.from_pretrained()`. Test fixtures compare outputs against golden reference outputs stored in R2.

### Test Cases

| Test Case | Action | Variant | Verification |
|-----------|--------|---------|--------------|
| Paired encode | `encode` | paired | Relative tolerance 1e-4 |
| Unpaired encode | `encode` | unpaired | Relative tolerance 1e-4 |
| Paired generate | `generate` | paired | Exact match to golden output |
| Unpaired generate | `generate` | unpaired | Exact match to golden output |
| Paired log prob | `log_prob` | paired | Validates negative finite float |
| Unpaired log prob | `log_prob` | unpaired | Validates negative finite float |

### Verification Status

**Status: VERIFIED** -- Integration tests pass for both paired and unpaired variants with rel_tol=1e-4.

## Resource Requirements

| Variant | GPU | Memory | CPU |
|---------|-----|--------|-----|
| `igbert-paired` | T4 | 6 GB | 3 cores |
| `igbert-unpaired` | T4 | 6 GB | 3 cores |

## Implementation Notes

- **Memory snapshots**: IgBERT uses GPU memory snapshots (`enable_memory_snapshot=True`, `enable_gpu_snapshot=True`) for fast cold starts.
- **Determinism**: Seeds are set (`torch.manual_seed(42)`, `torch.cuda.manual_seed_all(42)`) for reproducible outputs.
- **Weight loading**: Weights are downloaded from R2 and loaded via HuggingFace `BertForMaskedLM.from_pretrained()`.
- **Dependencies**: `transformers==4.48.1`, `sentencepiece==0.2.0`, `safetensors==0.5.3`
- **Variant dispatch**: The model type (paired/unpaired) is set at deployment time via the `MODEL_TYPE` environment variable.
- **Caching**: Response caching is handled outside the model container at the serving layer.

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
- **Model weights (paired)**: [huggingface.co/Exscientia/IgBert](https://huggingface.co/Exscientia/IgBert)
- **Model weights (unpaired)**: [huggingface.co/Exscientia/IgBert_unpaired](https://huggingface.co/Exscientia/IgBert_unpaired)

---

*See also: [MODEL.md](MODEL.md) for technical deep-dive | [BIOLOGY.md](BIOLOGY.md) for biological context*
