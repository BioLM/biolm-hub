# TemBERTure -- Technical Details

## Architecture

### Model Type & Innovation

TemBERTure is a fine-tuned ProtBERT model that predicts protein thermostability. It uses adapter modules on top of a pre-trained BERT model (ProtBERT-BFD) to classify proteins as thermophilic or non-thermophilic (classifier variant) and to predict melting temperature (Tm) in degrees Celsius (regression variant). The key innovation is the use of lightweight adapter layers for transfer learning, allowing efficient fine-tuning without modifying the full ProtBERT backbone.

### Parameters & Layers

| Component | Details |
|-----------|---------|
| Architecture | BERT encoder with adapter layers |
| Base model | ProtBERT-BFD (Rostlab/prot_bert_bfd) |
| Hidden dimensions | 1024 |
| Adapter type | AdapterBERT (bottleneck adapters) |
| Tokenization | Character-level (space-separated amino acids) |
| Max sequence length | 512 residues |

### Training Data

<!-- TODO: Extract training dataset details from paper (Rodella et al., 2024, Bioinformatics) -- requires PDF access -->

The model is trained on a curated dataset of protein sequences labeled with thermostability properties (thermophilic/non-thermophilic classification and melting temperature values).

### Loss Function & Objective

- **Classifier variant**: Binary cross-entropy loss for thermophilic vs non-thermophilic classification
- **Regression variant**: Mean squared error (MSE) loss for melting temperature (Tm) prediction in degrees Celsius

### Tokenization / Input Processing

ProtBERT uses character-level tokenization where each amino acid is treated as a separate token, with spaces inserted between residues. Special tokens include [CLS] (classification), [SEP] (separator), and [PAD] (padding). Sequences are truncated to the maximum length of 512 tokens.

## Performance & Benchmarks

### Published Benchmarks

<!-- TODO: Extract benchmark results from Rodella et al. (2024) Table/Figure -- requires PDF access -->

### BioLM Verification Results

Both classifier and regression variants have been verified through integration tests with golden output comparison (relative tolerance 1e-4, cosine distance threshold 0.02 for embeddings).

### Comparison to Alternatives

| Model | Task | Input | Advantage |
|-------|------|-------|-----------|
| **TemBERTure** | Thermophilicity + Tm | Sequence only | Dual prediction (classification + regression) |
| ThermoMPNN | ddG prediction | Structure (PDB) | Structure-aware, per-mutation predictions |
| TEMPRO | Nanobody Tm | Sequence only | Specialized for nanobodies |

## Strengths & Limitations

### Pros

- Dual-mode: classification (thermophilic/non-thermophilic) and regression (Tm in degrees C)
- Sequence-only input -- no structure required
- Lightweight adapter approach enables efficient fine-tuning
- Provides embeddings for downstream tasks (mean, per-residue, CLS)

### Cons

- Limited to 512 residues maximum
- Based on older ProtBERT architecture (not ESM2)
- Regression predictions may have limited accuracy for proteins far from training distribution

### Known Failure Modes

- Very long proteins (>512 residues) are truncated, which may affect predictions
- Non-standard amino acids beyond extended alphabet may cause tokenization issues

## Implementation Details

### Inference Pipeline

```
Request --> Validate sequences --> Space-separate AAs --> Tokenize (ProtBERT)
  --> [GPU] Forward pass through BERT + adapter --> Post-process --> Response
```

For `encode`: extracts hidden states from last layer, computes mean/per-residue/CLS embeddings.
For `predict`: passes through classification/regression head, applies sigmoid (classifier) or returns raw value (regression).

### Memory & Compute Profile

| Resource | Value |
|----------|-------|
| GPU | T4 |
| Memory | 16 GB |
| CPU | 4 cores |

### Determinism & Reproducibility

- Torch manual seed: Yes (42)
- CUDA manual seed: Yes (42)
- Model set to eval mode: Yes
- Inference under `torch.no_grad()`: Yes

### Caching Behavior

- Redis (Modal Dict) caching: Enabled via `BillingMixinSnap`
- R2 caching: Enabled via `BillingMixinSnap`

## Versions & Changelog

| Version | Date | Changes |
|---------|------|---------|
| v1 | 2024 | Initial implementation with classifier and regression variants |

---

*See also: [README.md](README.md) for API reference | [BIOLOGY.md](BIOLOGY.md) for biological context*
