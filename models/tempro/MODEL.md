# TEMPRO -- Technical Details

## Architecture

### Model Type & Innovation

TEMPRO is a nanobody melting temperature (Tm) prediction model that combines ESM2 protein language model embeddings with a Keras neural network regression head. The key innovation is using pre-computed mean-pooled ESM2 embeddings as input features for a lightweight Keras model specifically trained on nanobody Tm data. This two-stage approach leverages the rich protein representations from ESM2 while keeping the prediction head simple and focused on nanobodies.

### Parameters & Layers

| Component | Details |
|-----------|---------|
| Architecture | ESM2 embeddings + Keras regression head |
| Input features | Mean-pooled ESM2 embeddings |
| ESM2 650M layer | Layer 33 (last layer) |
| ESM2 3B layer | Layer 36 (last layer) |
| Prediction head | Keras dense network |
| Input constraint | 100--160 amino acids (nanobody length range) |

### Training Data

The model was trained on nanobody sequences with experimentally measured melting temperatures. The fixture validation includes 6 nanobodies with known Tms from PDB structures: 4IDL (46.75 degrees C), 4TYU (85.1 degrees C), 4U05 (84.0 degrees C), 4W68 (88.0 degrees C), 4W70 (60.0 degrees C), and 5SV3 (69.3 degrees C).

<!-- TODO: Extract full training dataset details from Alvarez (2024) preprint -- requires PDF access -->

### Loss Function & Objective

Mean squared error (MSE) regression loss for predicting melting temperature in degrees Celsius.

### Tokenization / Input Processing

Input processing occurs in two stages:

1. **ESM2 encoding**: Sequences are tokenized using the ESM2 tokenizer, processed through the ESM2 model, and mean-pooled embeddings are extracted from the specified layer.
2. **Keras prediction**: Mean-pooled embedding vectors are passed directly to the Keras model for Tm prediction.

## Performance & Benchmarks

### Published Benchmarks

<!-- TODO: Extract benchmark results from Alvarez (2024) preprint -- requires PDF access -->

Validation on 6 nanobodies with known Tms shows the model captures the range of thermal stabilities (46.75--88.0 degrees C). Tests use 10% relative tolerance for Tm predictions, reflecting the expected MAE of approximately 4.5--5.5 degrees C.

### BioLM Verification Results

Both variants (650m, 3b) are tested with golden output comparison. Validation sequences with known experimental Tms are included in the test suite.

### Comparison to Alternatives

| Model | Task | Input | Advantage |
|-------|------|-------|-----------|
| **TEMPRO** | Nanobody Tm | Sequence only | Specialized for nanobodies |
| TemBERTure | General protein Tm | Sequence only | Broader applicability, not nanobody-specific |

## Strengths & Limitations

### Pros

- Specialized for nanobody sequences (single-domain antibody fragments)
- Sequence-only input -- no structure required
- Lightweight prediction head (Keras) on top of powerful ESM2 embeddings
- Multiple ESM2 backbone sizes available (650M, 3B)
- CPU-only inference for the Keras head (low cost)

### Cons

- Narrow sequence length range: 100--160 amino acids only
- Exclusively for nanobodies -- not applicable to general proteins
- Requires a deployed ESM2 endpoint (dependency on ESM2 model)
- Expected MAE of approximately 4.5--5.5 degrees C

### Known Failure Modes

- Sequences outside 100--160 residues are rejected at validation
- Non-nanobody sequences may produce unreliable predictions
- Depends on ESM2 endpoint availability -- will fail if ESM2 is not deployed

## Implementation Details

### Inference Pipeline

```
Request --> Validate sequences (100-160 AA)
  --> Call ESM2 remotely (Modal function lookup)
  --> Extract mean-pooled embeddings
  --> [CPU] Keras model prediction
  --> Response (Tm in degrees C)
```

### Memory & Compute Profile

| Resource | Value |
|----------|-------|
| GPU | None (CPU only for Keras) |
| Memory | 4 GB |
| CPU | 1 core |
| External dependency | ESM2 endpoint (esm2-650m or esm2-3b) |

### Determinism & Reproducibility

- TensorFlow random seed: Yes (42)
- Keras model loaded from saved checkpoint
- ESM2 embeddings are deterministic (from deployed endpoint)

### Caching Behavior

Response caching (Redis/R2 two-tier) is handled by the BioLM platform layer, not by the model container. ESM2 calls may benefit from ESM2's own platform-layer caching.

## Versions & Changelog

| Version | Date | Changes |
|---------|------|---------|
| v1 | 2024 | Initial implementation with 650M and 3B variants |

---

*See also: [README.md](README.md) for API reference | [BIOLOGY.md](BIOLOGY.md) for biological context*
