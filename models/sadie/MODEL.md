# SADIE -- Technical Details

## Architecture

### Model Type & Innovation

SADIE (Sequencing Analysis and Data Library for Immunoinformatics Exploration) is an algorithmic antibody sequence analysis tool -- not a neural network model. It performs antibody numbering, domain identification, germline gene assignment, and region annotation using hidden Markov model (HMM) based alignment to reference databases.

The key innovation of SADIE is its unified interface for antibody and TCR sequence annotation, combining multiple numbering schemes (IMGT, Kabat, Chothia) and region definitions (IMGT, Kabat, Chothia, AbM, Contact, SCDR) into a single analysis pipeline. SADIE processes sequences through HMM alignment to identify domains, assign numbering, and extract framework and CDR region boundaries.

Unlike the language models on this platform (AbLang2, IgBERT, IgT5, NanoBERT), SADIE does not produce embeddings or learn representations from data. It applies rule-based numbering schemes and HMM-based gene assignment to annotate sequences with structured metadata.

### Algorithm Components

| Component | Method |
|-----------|--------|
| Domain identification | HMM alignment (HMMER-based) |
| Numbering | IMGT, Kabat, or Chothia scheme |
| Region assignment | IMGT, Kabat, Chothia, AbM, Contact, or SCDR |
| Germline assignment | V-gene and J-gene identification with identity scores |
| Species detection | HMM-based species classification |
| Chain type | Heavy (H), Kappa (K), Lambda (L), TCR chains (A, B, G, D) |

### Input Processing

| Property | Details |
|----------|---------|
| Input type | Single amino acid sequence per item |
| Max sequence length | 2048 residues |
| Batch size | 8 sequences |
| Validation | Extended amino acid alphabet |
| scFv support | Optional (`scfv=True`) for single-chain variable fragment sequences |

SADIE can process raw sequences without prior numbering or annotation. It handles both antibody and TCR sequences, identifying the chain type automatically.

## Performance & Benchmarks

### Published Benchmarks

SADIE is a sequence analysis tool rather than a predictive model; its accuracy depends on the quality of the underlying HMM profiles and reference databases.

Key characteristics:
- Domain identification relies on HMMER E-values; high E-values indicate poor matches
- Germline assignment accuracy depends on the completeness of the reference germline database
- Numbering accuracy follows the definitions of each scheme exactly

### BioLM Verification Results

The BioLM implementation uses the `sadie-antibody` PyPI package (v1.0.6). Numerical verification is performed against golden reference outputs:

| Metric | Threshold | Status |
|--------|-----------|--------|
| Relative tolerance | 1e-5 | PASS |

Tests cover the predict action with default parameters.

### Comparison to Alternatives

| Tool | Type | Key Advantage | Key Disadvantage |
|------|------|---------------|------------------|
| **SADIE (this)** | Annotation tool | Unified interface, multiple schemes | Python library dependency |
| ANARCI | Numbering tool | Widely adopted, standalone | Numbering only, no germline assignment |
| IMGT/DomainGapAlign | Web tool | Gold standard for IMGT numbering | Web-based, not programmatic |
| AbNum | Numbering tool | Fast, standalone | Limited to numbering |
| IgBLAST | Alignment tool | NCBI-backed, comprehensive | Requires BLAST installation, more complex output |

## Strengths & Limitations

### Pros

- Multiple numbering schemes in a single tool (IMGT, Kabat, Chothia)
- Multiple region definitions (IMGT, Kabat, Chothia, AbM, Contact, SCDR)
- Germline V-gene and J-gene identification with identity scores
- Species and chain type detection
- TCR support (alpha, beta, gamma, delta chains)
- scFv support for single-chain variable fragments
- CPU-only, minimal resource requirements (0.125 cores, 1 GB memory)
- MIT licensed

### Cons

- Not a predictive model -- no embeddings, no generation, no scoring
- Depends on HMM reference databases (may not cover all species or synthetic sequences)
- Single sequence processing (no batch parallelization within SADIE)
- Requires Pydantic v1 compatibility (SADIE library constraint)
- Cannot handle non-antibody/non-TCR proteins

### Known Failure Modes

- **Non-immunoglobulin sequences**: SADIE expects antibody or TCR sequences; other proteins will fail or produce high E-values
- **Highly engineered sequences**: Synthetic antibodies with many non-germline mutations may receive poor germline assignments
- **Incomplete variable domains**: Truncated sequences missing framework regions may fail domain identification
- **Novel species**: Sequences from species not in the reference database will receive approximate species assignments

## Implementation Details

### Inference Pipeline

```
Request
  |-- 1. Validate sequences (alphabet, length)
  |-- 2. Parse parameters (scheme, region_assign, scfv, allowed_chain)
  |-- 3. For each sequence:
  |     |-- Create Renumbering instance with specified scheme/region
  |     |-- Run HMM alignment via run_single()
  |     |-- Extract domain, numbering, germline, and region annotations
  |     |-- Convert to SADIEPredictResponseResult
  |-- 4. Return SADIEPredictResponse
```

### Memory & Compute Profile

| Property | Value |
|----------|-------|
| GPU | None (CPU only) |
| Memory | 1 GB |
| CPU | 0.125 cores |
| Batch size | 8 |

SADIE is the most lightweight model/tool on the platform, requiring minimal compute resources.

### Determinism & Reproducibility

SADIE is fully deterministic -- the same input always produces the same output. HMM alignment scores are computed analytically, not stochastically.

### Caching Behavior

Response caching is handled outside the model container. The cache key is determined by the request payload (sequence, scheme, region, scfv, allowed_chain).

## Versions & Changelog

| Version | Date | Changes |
|---------|------|---------|
| v1 | 2025-01-30 | Initial implementation with predict action |

---

*See also: [README.md](README.md) for API reference | [BIOLOGY.md](BIOLOGY.md) for biological context*
