# ESM1v

> **One-line summary**: Zero-shot protein variant effect prediction using a 5-model ensemble of 650M-parameter masked language models, predicting the functional impact of single amino acid mutations from sequence context alone.

## Overview

ESM1v is a protein language model from Meta AI (Meier et al. 2021) designed for zero-shot prediction of the effects of mutations on protein function. It consists of five independently trained 650M-parameter Transformer encoder models (n1--n5). Given a protein sequence with a single masked position, each model predicts the probability distribution over all 20 standard amino acids at that position, enabling variant effect scoring without any task-specific training data.

The BioLM platform deploys all 5 individual models (n1--n5) plus an "all" variant that loads all 5 simultaneously for ensemble predictions.

## Architecture

| Property | Value |
|----------|-------|
| Architecture | Transformer encoder (BERT-style, 33 layers) |
| Parameters | 650M per model |
| Ensemble size | 5 models (n1--n5) |
| Training data | UniRef90 (~98M sequences) |
| Training objective | Masked Language Modeling (MLM) |
| Input | Protein sequence with one `<mask>` token |
| Output | Sorted amino acid probabilities at masked position |

## Model Variants

| Variant | Slug | GPU | Description |
|---------|------|-----|-------------|
| n1 | `esm1v-n1` | None (CPU) | Individual model 1 |
| n2 | `esm1v-n2` | None (CPU) | Individual model 2 |
| n3 | `esm1v-n3` | None (CPU) | Individual model 3 |
| n4 | `esm1v-n4` | None (CPU) | Individual model 4 |
| n5 | `esm1v-n5` | None (CPU) | Individual model 5 |
| all | `esm1v-all` | T4 | All 5 models loaded, ensemble predictions |

## Capabilities & Limitations

**CAN be used for:**
- Zero-shot prediction of single amino acid mutation effects on protein function
- Computing amino acid probability distributions at any position in a protein
- Ensemble-averaged predictions for reduced variance (via "all" variant)
- Batch processing up to 5 sequences per request

**CANNOT be used for:**
- Multi-site mutation effects (only one `<mask>` per sequence)
- Sequences longer than 1022 residues
- Generating protein embeddings (use ESM2 or ESMC for embeddings)
- Structure-aware predictions (sequence-only model)
- Absolute fitness prediction (outputs are relative probabilities)

## Actions / Endpoints

### `predict`

Predict amino acid probabilities at a masked position in a protein sequence.

**Request Parameters:**

| Parameter | Type | Default | Range | Description |
|-----------|------|---------|-------|-------------|
| `items` | list[ESM1vPredictRequestItem] | (required) | 1--5 items | List of masked sequences |
| `items[].sequence` | str | (required) | 1--1022 chars | Amino acid sequence with exactly one `<mask>` token |

**Response (individual variant n1--n5):**

```json
{
  "results": [
    [
      {"token": 5, "token_str": "A", "score": 0.23, "sequence": "MKTAY..."},
      {"token": 10, "token_str": "V", "score": 0.18, "sequence": "MKTVAY..."},
      ...
    ]
  ]
}
```

**Response (all variant):**

```json
{
  "results": [
    {
      "esm1v-n1": [
        {"token": 5, "token_str": "A", "score": 0.23, "sequence": "MKTAY..."},
        ...
      ],
      "esm1v-n2": [
        {"token": 5, "token_str": "A", "score": 0.21, "sequence": "MKTAY..."},
        ...
      ],
      ...
    }
  ]
}
```

- `token`: Integer token ID from the tokenizer vocabulary
- `token_str`: Single-letter amino acid code
- `score`: Model probability for this amino acid at the masked position
- `sequence`: Full sequence with the mask replaced by this amino acid

Results are sorted by score in descending order. Only the 20 standard amino acids are included.

## Usage Examples

### Predict variant effects at a single position

```python
from models.esm1v.schema import (
    ESM1vPredictRequest,
    ESM1vPredictRequestItem,
)

# Mask position 5 to predict which amino acids are compatible
request = ESM1vPredictRequest(
    items=[
        ESM1vPredictRequestItem(
            sequence="MKTAY<mask>NNKELSKDVR"
        )
    ]
)
```

### Batch prediction for multiple positions

```python
from models.esm1v.schema import (
    ESM1vPredictRequest,
    ESM1vPredictRequestItem,
)

# Test multiple positions in the same protein
request = ESM1vPredictRequest(
    items=[
        ESM1vPredictRequestItem(sequence="<mask>KTAYVNNKELSKDVR"),
        ESM1vPredictRequestItem(sequence="M<mask>TAYVNNKELSKDVR"),
        ESM1vPredictRequestItem(sequence="MK<mask>AYVNNKELSKDVR"),
    ]
)
```

## Performance & Benchmarks

### Published Results

From Meier et al., *NeurIPS* (2021):

| Model | Spearman rho (41 DMS avg) ↑ | Method |
|-------|----------------------------|--------|
| **ESM1v (5-model avg)** | **0.47** | Zero-shot, ensemble |
| ESM-1b | 0.43 | Zero-shot, single model |
| EVmutation | 0.42 | MSA-based |
| DeepSequence | 0.41 | VAE, MSA-based |

### SOTA Status

ESM1v was state-of-the-art for zero-shot variant effect prediction at time of publication (2021). Newer models (ESM2, ESMC) may achieve comparable or better performance on some benchmarks but were not specifically optimized for this task.

## Implementation Verification

### Verification Method

Option A -- Numerical Reproduction: outputs from the BioLM implementation are compared against golden outputs generated using the HuggingFace Transformers pipeline on identical inputs.

### Test Cases

| Variant | Action | Tolerance | Status |
|---------|--------|-----------|--------|
| n1 | predict | rel_tol 1e-4 | PASS |
| n2 | predict | rel_tol 1e-4 | PASS |
| n3 | predict | rel_tol 1e-4 | PASS |
| n4 | predict | rel_tol 1e-4 | PASS |
| n5 | predict | rel_tol 1e-4 | PASS |
| all | predict | rel_tol 1e-4 | PASS |

### Verification Status

**Status: VERIFIED** -- All 6 variants produce outputs matching reference implementation within tolerance.

## Resource Requirements

| Resource | Individual (n1--n5) | All Variant |
|----------|-------------------|-------------|
| GPU | None (CPU-only) | T4 |
| Memory | 8 GB | 28 GB |
| CPU | 2.0 cores | 4.0 cores |
| Models loaded | 1 | 5 |
| Batch size | 5 | 5 |
| Max sequence length | 1022 | 1022 |
| Memory snapshot | Enabled (GPU snapshot) | Enabled (GPU snapshot) |

## Implementation Notes

- **Memory snapshots**: Uses `@modal.enter(snap=True)` with GPU memory snapshot enabled. Models are loaded directly on GPU during snapshot creation.
- **Container image**: Based on `pytorch/pytorch:2.6.0-cuda12.4-cudnn9-runtime` with `transformers==4.36.2` and `safetensors==0.5.3`.
- **Model loading**: Uses HuggingFace `EsmForMaskedLM.from_pretrained()` and `EsmTokenizer.from_pretrained()` from local model directories downloaded from R2. For the "all" variant, all 5 model directories are loaded and wrapped in separate `fill-mask` pipelines.
- **Pipeline**: Uses HuggingFace `pipeline("fill-mask")` with targets restricted to the 20 standard unambiguous amino acids.
- **Response format**: Individual variants (n1--n5) return a flat list of predictions per sequence. The "all" variant returns a dictionary mapping each model name (e.g., "esm1v-n1") to its predictions.
- **Weights source**: HuggingFace hub models `facebook/esm1v_t33_650M_UR90S_1` through `_5`.

## License

- **License**: MIT ([GitHub](https://github.com/facebookresearch/esm/blob/main/LICENSE))

## References & Citations

### Papers

1. Meier J, Rao R, Verkuil R, Liu J, Sercu T, Rives A. "Language models enable zero-shot prediction of the effects of mutations on protein function." *NeurIPS* (2021). [arXiv: 2108.07684](https://arxiv.org/abs/2108.07684). [DOI: 10.1101/2021.07.09.450648](https://doi.org/10.1101/2021.07.09.450648)

### BibTeX

```bibtex
@inproceedings{meier2021language,
  title={Language models enable zero-shot prediction of the effects of mutations on protein function},
  author={Meier, Joshua and Rao, Roshan and Verkuil, Robert and Liu, Jason and Sercu, Tom and Rives, Alexander},
  booktitle={Advances in Neural Information Processing Systems},
  year={2021}
}
```

### Links

- **Paper**: [arXiv:2108.07684](https://arxiv.org/abs/2108.07684)
- **Code**: [GitHub facebookresearch/esm](https://github.com/facebookresearch/esm)
- **HuggingFace**: [facebook/esm1v_t33_650M_UR90S_1](https://huggingface.co/facebook/esm1v_t33_650M_UR90S_1)

---

*See also: [MODEL.md](MODEL.md) for technical deep-dive | [BIOLOGY.md](BIOLOGY.md) for biological context*
