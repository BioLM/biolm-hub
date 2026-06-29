# TEMPRO

> **One-line summary**: Nanobody melting temperature (Tm) prediction model using ESM2 embeddings with a Keras regression head, specialized for single-domain antibody fragments.

## Overview

TEMPRO is a nanobody melting temperature estimation model developed by Alvarez (2024). It predicts the Tm (in degrees Celsius) of nanobody sequences by combining mean-pooled ESM2 protein language model embeddings with a lightweight Keras neural network. The model is specifically trained on nanobody sequences and targets the typical nanobody length range of 100--160 amino acids.

## Architecture

| Property | Value |
|----------|-------|
| Architecture | ESM2 embeddings + Keras regression head |
| Input | Mean-pooled ESM2 embeddings |
| Output | Tm in degrees Celsius |
| Sequence length | 100--160 amino acids |
| Batch size | 8 |
| Compute (Keras head) | CPU only |

## Model Variants

| Variant | Slug | ESM2 Backbone | ESM2 Layer |
|---------|------|---------------|------------|
| `650m` | `tempro-650m` | ESM2-650M | Layer 33 |
| `3b` | `tempro-3b` | ESM2-3B | Layer 36 |

## Capabilities & Limitations

**CAN be used for:**
- Predicting melting temperature of nanobody (VHH) sequences
- Screening nanobody libraries for thermostable candidates
- Evaluating stability of engineered nanobody variants

**CANNOT be used for:**
- Sequences shorter than 100 or longer than 160 amino acids (rejected at validation)
- General protein Tm prediction (use TemBERTure instead)
- Conventional antibody Tm prediction (VH/VL pairs)
- Structure-based stability analysis (use ThermoMPNN instead)

**Other considerations:**
- Requires a deployed ESM2 endpoint (esm2-650m or esm2-3b) -- will fail if ESM2 is unavailable
- Expected prediction accuracy is approximately +/- 4.5--5.5 degrees C MAE
- The 650m variant is faster; the 3b variant may provide slightly different predictions

## Actions / Endpoints

### `predict`

Predict melting temperature for nanobody sequences.

**Request Parameters:**

| Parameter | Type | Default | Range | Description |
|-----------|------|---------|-------|-------------|
| `items[].sequence` | str | Required | 100--160 residues | Nanobody amino acid sequence |

**Response:**

```json
{
  "results": [
    {
      "tm": 72.5
    }
  ]
}
```

## Usage Examples

```python
from models.tempro.schema import (
    TemproPredictRequest,
    TemproPredictRequestItem,
)

# Predict Tm for a nanobody sequence
request = TemproPredictRequest(
    items=[
        TemproPredictRequestItem(
            sequence="GSHMEVQLVESGGGLVQAGDSLRLSCTASGRTFSRAVMGWFRQAPGKEREFVAAISAAPGTAYYAFYADSVRGRFSISADSAKNTVYLQMNSLKPEDTAVYYCAADLKMQVAAYMNQRSVDYWGQGTQVTVSS"
        ),
    ],
)
```

## Performance & Benchmarks

### Published Results

Validation against 6 nanobodies with known experimental Tms:

| PDB ID | Experimental Tm (degrees C) | Sequence Length |
|--------|---------------------------|-----------------|
| 4IDL | 46.75 | 121 |
| 4TYU | 85.1 | 133 |
| 4U05 | 84.0 | 133 |
| 4W68 | 88.0 | 134 |
| 4W70 | 60.0 | 131 |
| 5SV3 | 69.3 | 130 |

### SOTA Status

TEMPRO is a specialized nanobody Tm predictor. As of 2024, few models are specifically designed for nanobody thermal stability prediction.

## Implementation Verification

### Verification Method

Golden output comparison (Option A) with 10% relative tolerance for Tm predictions, reflecting the expected MAE of approximately 4.5--5.5 degrees C.

### Test Cases

Tests include single-sequence prediction, batch prediction (4 sequences), and validation against 6 nanobodies with known experimental Tms (PDB IDs: 4IDL, 4TYU, 4U05, 4W68, 4W70, 5SV3).

### Verification Status

**Status: VERIFIED** -- All test cases pass for both 650m and 3b variants.

## Resource Requirements

| Resource | Value |
|----------|-------|
| GPU | None (CPU only for Keras head) |
| Memory | 4 GB |
| CPU | 1 core |
| Cold start | Memory snapshot enabled |
| Dependencies | Requires `esm2-650m` or `esm2-3b` endpoint deployed |

## Implementation Notes

- Uses Modal memory snapshots for faster cold starts
- Keras model is loaded during snapshot creation; TensorFlow runs on CPU
- ESM2 embeddings are obtained via Modal function lookup (`modal.Cls.from_name`), not local inference
- The `app_username` parameter is forwarded to ESM2 for request attribution
- TensorFlow CPU-only build is used to minimize image size (no GPU needed for the Keras head)

## License

The upstream repository (https://github.com/Jerome-Alvarez/TEMPRO) has no LICENSE
file (GitHub API: license null). The model code and weights are not open-source;
all rights are reserved by the original authors by default. See [LICENSE](LICENSE)
for details. An explicit license grant from the authors is required for redistribution
or commercial use. The published paper is CC-BY 4.0 (Sci. Reports 14:19074, 2024).

## References & Citations

### Papers

1. Alvarez, Jerome Anthony E. and Dean, Scott N. "TEMPRO: nanobody melting temperature estimation model using protein embeddings." *Scientific Reports*, 14, 19074 (2024). DOI: [10.1038/s41598-024-70101-6](https://doi.org/10.1038/s41598-024-70101-6)

### BibTeX

```bibtex
@article{alvarez2024tempro,
  title={TEMPRO: nanobody melting temperature estimation model using protein embeddings},
  author={Alvarez, Jerome Anthony E. and Dean, Scott N.},
  journal={Scientific Reports},
  volume={14},
  pages={19074},
  year={2024},
  doi={10.1038/s41598-024-70101-6}
}
```

### Links

- **Code**: [GitHub Jerome-Alvarez/TEMPRO](https://github.com/Jerome-Alvarez/TEMPRO)

---

*See also: [MODEL.md](MODEL.md) for technical deep-dive | [BIOLOGY.md](BIOLOGY.md) for biological context*
