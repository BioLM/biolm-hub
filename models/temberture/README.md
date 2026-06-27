# TemBERTure

> **One-line summary**: Protein thermostability prediction using adapter-tuned ProtBERT, providing both thermophilicity classification and melting temperature regression from sequence alone.

## Overview

TemBERTure is a deep learning model for protein thermostability prediction developed by Rodella et al. (2024) at the University of Bern. It fine-tunes ProtBERT-BFD with adapter modules to predict whether a protein is thermophilic or non-thermophilic (classifier) and to estimate melting temperature in degrees Celsius (regression). The model operates on amino acid sequences alone, requiring no structural information.

## Architecture

| Property | Value |
|----------|-------|
| Architecture | BERT encoder + adapter layers |
| Base model | ProtBERT-BFD |
| Hidden dimensions | 1024 |
| Max sequence length | 512 residues |
| Batch size | 8 |
| Adapter type | Bottleneck adapters (AdapterBERT) |

## Model Variants

| Variant | Slug | Task | Output |
|---------|------|------|--------|
| `classifier` | `temberture-classifier` | Thermophilicity classification | Probability (0--1) + label |
| `regression` | `temberture-regression` | Melting temperature prediction | Tm in degrees C |

## Capabilities & Limitations

**CAN be used for:**
- Classifying proteins as thermophilic or non-thermophilic (classifier variant)
- Predicting melting temperature (Tm) in degrees Celsius (regression variant)
- Extracting protein embeddings (mean, per-residue, CLS) from the fine-tuned model
- Screening protein libraries for thermostable candidates

**CANNOT be used for:**
- Sequences longer than 512 residues (truncated)
- Structure-based stability prediction (use ThermoMPNN instead)
- Per-mutation ddG prediction (use ThermoMPNN instead)
- Non-standard amino acids beyond the extended alphabet plus gap character

**Other considerations:**
- The classifier variant returns a probability and label ("Thermophilic" or "Non-thermophilic")
- The regression variant returns a raw Tm value in degrees C
- Both variants share the same ProtBERT base model but use different adapter heads

## Actions / Endpoints

### `encode`

Extract embeddings from protein sequences using the TemBERTure fine-tuned model.

**Request Parameters:**

| Parameter | Type | Default | Range | Description |
|-----------|------|---------|-------|-------------|
| `params.include` | list[str] | `["mean"]` | `mean`, `per_residue`, `cls` | Embedding types to include |
| `items[].sequence` | str | Required | 1--512 residues | Amino acid sequence |

**Response:**

```json
{
  "results": [
    {
      "sequence_index": 0,
      "embeddings": [0.1, 0.2, ...],
      "per_residue_embeddings": [[0.1, ...], ...],
      "cls_embeddings": [0.1, 0.2, ...]
    }
  ]
}
```

### `predict`

Predict thermophilicity (classifier) or melting temperature (regression) for protein sequences.

**Request Parameters:**

| Parameter | Type | Default | Range | Description |
|-----------|------|---------|-------|-------------|
| `items[].sequence` | str | Required | 1--512 residues | Amino acid sequence |

**Response (classifier):**

```json
{
  "results": [
    {
      "prediction": 0.85,
      "classification": "Thermophilic"
    }
  ]
}
```

**Response (regression):**

```json
{
  "results": [
    {
      "prediction": 72.5
    }
  ]
}
```

## Usage Examples

```python
from models.temberture.schema import (
    TemBERTureEncodeRequest,
    TemBERTureEncodeRequestItem,
    TemBERTureEncodeRequestParams,
    TemBERTureEncodeIncludeOptions,
    TemBERTurePredictRequest,
    TemBERTurePredictRequestItem,
)

# Encode request
encode_request = TemBERTureEncodeRequest(
    params=TemBERTureEncodeRequestParams(
        include=[
            TemBERTureEncodeIncludeOptions.MEAN,
            TemBERTureEncodeIncludeOptions.CLS,
        ]
    ),
    items=[
        TemBERTureEncodeRequestItem(
            sequence="MKTVRQERLKSIVRILERSKEPVSGAQLAEELSVSRQVIVQDIAYLRSLGYNIVATPRGYVLAGG"
        ),
    ],
)

# Predict request
predict_request = TemBERTurePredictRequest(
    items=[
        TemBERTurePredictRequestItem(
            sequence="MKTVRQERLKSIVRILERSKEPVSGAQLAEELSVSRQVIVQDIAYLRSLGYNIVATPRGYVLAGG"
        ),
    ],
)
```

## Performance & Benchmarks

### Published Results

<!-- TODO: Extract benchmark numbers from Rodella et al. (2024) Bioinformatics paper Table/Figure -- requires PDF access via bm r2 cat -->

### SOTA Status

TemBERTure advances protein thermostability prediction using deep learning with attention mechanisms (published 2024 in Bioinformatics).

## Implementation Verification

### Verification Method

Golden output comparison (Option A -- Numerical Reproduction). Integration tests compare model outputs against stored expected outputs with relative tolerance of 1e-4 and cosine distance threshold of 0.02 for embeddings.

### Test Cases

Tests cover both variants (classifier and regression) with two actions each (encode and predict), using two test sequences of varying lengths.

### Verification Status

**Status: VERIFIED** -- Integration tests pass for both classifier and regression variants across encode and predict actions.

## Resource Requirements

| Resource | Value |
|----------|-------|
| GPU | T4 |
| Memory | 16 GB |
| CPU | 4 cores |
| Cold start | Memory snapshot enabled |
| Dependencies | None (self-contained) |

## Implementation Notes

- Uses Modal GPU memory snapshots (`enable_gpu_snapshot=True`) for faster cold starts
- Model loaded directly on GPU during snapshot creation (`@modal.enter(snap=True)`)
- ProtBERT base model and adapter weights are stored separately: shared base model in R2, variant-specific adapters downloaded from GitHub archive
- Sequences are preprocessed by inserting spaces between amino acids as required by ProtBERT tokenization
- Classifier variant applies sigmoid to logits and classifies as "Thermophilic" (>0.5) or "Non-thermophilic"

## License

- **Code**: MIT ([GitHub](https://github.com/ibmm-unibe-ch/TemBERTure))

## References & Citations

### Papers

1. Rodella C, Lazaro F, Lemmin T. "TemBERTure: advancing protein thermostability prediction with deep learning and attention mechanisms." *Bioinformatics* (2024). [DOI](https://doi.org/10.1093/bioinformatics/btae157)

### BibTeX

```bibtex
@article{rodella2024temberture,
  title={TemBERTure: advancing protein thermostability prediction with deep learning and attention mechanisms},
  author={Rodella, Chiara and Lazaro, Florian and Lemmin, Thomas},
  journal={Bioinformatics},
  year={2024},
  doi={10.1093/bioinformatics/btae157}
}
```

### Links

- **Paper**: [Bioinformatics](https://doi.org/10.1093/bioinformatics/btae157)
- **Code**: [GitHub ibmm-unibe-ch/TemBERTure](https://github.com/ibmm-unibe-ch/TemBERTure)
- **Base model**: [HuggingFace Rostlab/prot_bert_bfd](https://huggingface.co/Rostlab/prot_bert_bfd)

---

*See also: [MODEL.md](MODEL.md) for technical deep-dive | [BIOLOGY.md](BIOLOGY.md) for biological context*
