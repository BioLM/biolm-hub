# peptides -- Technical Details

## Architecture

### Model Type & Innovation

The peptides module is not a machine learning model but an algorithmic feature extractor. It computes physicochemical properties, amino acid composition statistics, and descriptor vectors from amino acid sequences using published scales and formulas from the biochemistry literature.

The implementation wraps the `peptides` Python package (v0.3.4) — [althonos/peptides.py](https://github.com/althonos/peptides.py) by Martin Larralde, an independent Python reimplementation that computes the physicochemical scales popularized by the R `Peptides` package (Osorio et al., 2015). The innovation is in providing a comprehensive, standardized set of sequence-derived features through a unified API, consolidating dozens of individual physicochemical scales into a single computation.

### Parameters & Layers

Not applicable. This is a formula-based computation with no trainable parameters.

| Component | Details |
|-----------|---------|
| Architecture | Algorithmic (lookup tables + formulas) |
| Parameters | 0 (no learned weights) |
| Input | Amino acid sequences (extended alphabet) |
| Output | Dictionary of scalar and vector features |
| Computation | CPU-only, no GPU required |

### Training Data

Not applicable. The physicochemical scales and indices used are derived from experimental measurements and published literature, not from training on a dataset. Key sources include:

- **Amino acid property tables**: Experimentally measured hydrophobicity, charge, volume, and other physical properties
- **BLOSUM matrices**: Derived from blocks of aligned protein sequences
- **Kidera factors**: Principal component analysis of 188 published amino acid properties
- **VHSE scales**: PCA of 18 hydrophobicity scales, steric parameters, and electronic properties

### Loss Function & Objective

Not applicable. No training or optimization is involved.

### Tokenization / Input Processing

- **Alphabet**: Extended amino acid alphabet (standard 20 + ambiguous codes)
- **Validation**: Sequences validated using `validate_aa_extended` from commons
- **Maximum length**: 2048 residues
- **No special tokens**: Sequences are passed directly to the `peptides.Peptide` class constructor
- **Case handling**: Handled by the peptides library internally

## Performance & Benchmarks

### Published Benchmarks

Not applicable in the traditional ML sense. The computed features are deterministic outputs of established formulas. Their utility depends on the downstream application:

- **Instability index**: Guruprasad et al. (1990) validated on 12 stable and 12 unstable proteins, achieving correct classification in all cases with a threshold of 40.
- **Boman index**: Boman (2003) showed correlation with experimentally measured protein-protein interaction propensities.
- **Isoelectric point**: Calculated pI values typically agree with experimental values within 0.5 pH units for most globular proteins.

### BioLM Verification Results

The BioLM implementation produces identical output to calling the `peptides` Python library directly. The only transformation applied is numpy float to Python float32 conversion for JSON serialization.

### Comparison to Alternatives

| Tool | Features | Speed | Integration | When to prefer |
|------|----------|-------|-------------|----------------|
| **peptides (BioLM)** | Comprehensive (scalar + vector + descriptors) | ~ms per sequence | API endpoint, batch support | Production pipelines, integration with other BioLM models |
| peptides (local) | Same features | ~ms per sequence | Python library | Local development, prototyping |
| Biopython ProtParam | Subset (MW, pI, charge, instability) | ~ms per sequence | Python library | Only basic properties needed |
| ProPy | Descriptors similar to peptides | ~ms per sequence | Python library | Alternative descriptor set |

### Error Bars & Confidence

Not applicable. Outputs are deterministic and have no associated uncertainty. However, the biological relevance of specific features varies by application:
- Hydrophobicity scales are well-calibrated for globular proteins but may be less reliable for membrane proteins
- Instability index predictions are most accurate for proteins in the 100-500 residue range
- Descriptor-based features may have limited interpretability for very short peptides (<5 residues)

## Strengths & Limitations

### Pros

- Deterministic and reproducible: identical inputs always produce identical outputs
- Extremely fast: milliseconds per sequence, no GPU required
- Minimal resources: 1 GB memory, 0.125 CPU cores
- Comprehensive: dozens of features computed in a single call
- Well-established: based on decades of published physicochemical research
- Interpretable: each feature has a clear physical or chemical meaning

### Cons

- No sequence context: each residue is treated independently (no structural or evolutionary context)
- Limited to canonical amino acids: non-standard amino acids and post-translational modifications not supported
- No learned representations: cannot capture complex sequence patterns that neural models detect
- Feature relevance varies: not all features are useful for all downstream tasks
- No confidence scores: cannot assess reliability of individual feature values

### Known Failure Modes

- Very short sequences (1-3 residues): some features (e.g., hydrophobic moment) may be poorly defined or uninformative
- Homopolymeric sequences (e.g., "AAAAAAA"): frequency-based features will be trivial; some descriptors may have edge-case behavior
- Sequences with many ambiguous residues (X, B, Z): physicochemical properties are approximate for ambiguous codes

## Implementation Details

### Inference Pipeline

```
Request
  +-- 1. Validate sequences (extended amino acid alphabet)
  +-- 2. Check batch size (max 10)
  +-- 3. For each sequence:
  |     +-- Create peptides.Peptide object
  |     +-- Compute numeric features (aliphatic_index, boman, charge, ...)
  |     +-- Compute descriptors (BLOSUM, Kidera, Cruciani, ...)
  |     +-- Compute amino acid frequencies
  |     +-- [Optional] Compute vector features (profiles)
  |     +-- Convert numpy floats to Python float32
  |     +-- Flatten descriptors and frequencies into features dict
  +-- 4. Package results into response
```

### Memory & Compute Profile

| Input Size | Memory | Inference Time | Batch Size |
|------------|--------|----------------|------------|
| 10 residues | <100 MB | <5ms | 10 |
| 100 residues | <100 MB | <10ms | 10 |
| 1000 residues | <100 MB | <50ms | 10 |
| 2048 residues | <100 MB | <100ms | 10 |

Memory usage is effectively constant regardless of input size. Compute time scales linearly with sequence length for most features, with some features (profiles) scaling as O(n) per residue.

### Determinism & Reproducibility

- Fully deterministic: no random seeds needed
- No GPU computation: no CUDA non-determinism
- All numpy floats converted to float32 for consistent serialization
- Identical inputs will always produce bit-identical outputs

### Caching Behavior

Response caching (Redis/R2 two-tier) is handled by the BioLM platform layer, not by the model container:

- Cache key composition: Based on input sequence and include parameters
- Caching is effective since outputs are deterministic

## Versions & Changelog

| Version | Date | Changes |
|---------|------|---------|
| v1 | 2024 | Initial implementation using peptides v0.3.4 |

---

*See also: [README.md](README.md) for API reference | [BIOLOGY.md](BIOLOGY.md) for biological context*
