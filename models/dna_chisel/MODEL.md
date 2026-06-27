# DNA-Chisel -- Technical Details

## Architecture

### Model Type & Innovation

DNA-Chisel is **not a machine learning model**. It is an algorithmic DNA sequence analysis toolkit built on the DnaChisel library from the Edinburgh Genome Foundry. Rather than learning representations from data, it computes 20 biophysical and sequence-composition features using deterministic algorithms -- GC content, codon adaptation, hairpin detection, restriction site counting, and more.

The key value of wrapping DNA-Chisel as a BioLM endpoint is providing a standardized, always-available API for DNA feature extraction that can be composed with ML-based models (e.g., Evo, Nucleotide Transformer) in multi-model workflows. Unlike ML models, DNA-Chisel is fully deterministic, requires no GPU, and has negligible latency.

### Parameters & Layers

| Property | Value |
|----------|-------|
| Architecture | Algorithmic (rule-based) |
| Learnable parameters | 0 |
| GPU required | No |
| Deterministic | Yes |

### Training Data

Not applicable. DNA-Chisel does not use training data. Feature computations rely on:
- **Codon usage tables**: From `python_codon_tables`, covering 6 species (E. coli, S. cerevisiae, H. sapiens, C. elegans, B. subtilis, D. melanogaster)
- **Restriction enzyme database**: From Biopython's `Bio.Restriction` module
- **Primer3**: For melting temperature calculation

### Loss Function & Objective

Not applicable (algorithmic tool).

### Tokenization / Input Processing

| Property | Details |
|----------|---------|
| Input type | Raw DNA sequence (string) |
| Alphabet | A, C, G, T (unambiguous DNA only) |
| Preprocessing | Uppercased before feature computation |
| Max length | No hard limit (practical limit depends on feature) |
| Batch size | 1 sequence per request |

## Performance & Benchmarks

### Published Benchmarks

Not applicable. DNA-Chisel computes standard bioinformatics features; there are no accuracy benchmarks in the ML sense.

### BioLM Verification Results

| Metric | Threshold | Status |
|--------|-----------|--------|
| Relative tolerance | 1e-4 | PASS |

Tests cover both explicit parameter selection (subset of features) and default parameters (all 20 features).

### Comparison to Alternatives

| Tool | Advantage | Disadvantage |
|------|-----------|--------------|
| **DNA-Chisel (this)** | 20 features in one API call; composable with BioLM models | Not a learning model; no embeddings |
| BioPython SeqUtils | More comprehensive sequence utilities | No unified API; requires local installation |
| Benchling API | Full design suite with GUI | Commercial; not open-source |
| CodonW | Specialized codon usage analysis | Narrower scope; command-line only |

### Error Bars & Confidence

All features are deterministic. The same input always produces the same output. No stochasticity or hardware-dependent variation.

## Strengths & Limitations

### Pros

- Fully deterministic -- no randomness, no hardware-dependent variation
- No GPU required -- runs on CPU with minimal resources (0.25 CPU, 1 GB RAM)
- Fast inference -- all features computed in milliseconds
- Comprehensive -- 20 distinct DNA features in a single endpoint
- Species-aware -- codon-related features use species-specific codon tables
- Configurable -- select any subset of features via the `include` parameter

### Cons

- Not a learning model -- cannot generalize to novel patterns
- Single-sequence processing only (batch_size = 1)
- Some features require sequence length to be a multiple of 3 (in-frame stop codons, methionine frequency)
- Kozak sequence strength is a naive binary check (starts with "GCCRCCATGG" or not)
- Hairpin detection uses fixed parameters (stem_size=20, window=200)

### Known Failure Modes

- **Very short sequences** (< 6 nt): Some features like non-unique 6-mer count and GC content std dev will return 0 or degenerate values
- **Non-divisible-by-3 sequences**: In-frame stop codon count and methionine frequency return `null` (not an error)
- **Invalid restriction enzymes**: Validation catches these at request time with a clear error message

## Implementation Details

### Inference Pipeline

```
Request
  |-- 1. Validate DNA sequence (A/C/G/T only)
  |-- 2. Uppercase sequence
  |-- 3. For each feature in params.include:
  |     |-- Dispatch to compute_* method
  |     |-- GC content: dnachisel.biotools.gc_content
  |     |-- CAI: python_codon_tables lookup + geometric mean
  |     |-- Hairpin: AvoidHairpins specification scoring
  |     |-- Melting temp: primer3.calc_tm
  |     |-- Restriction sites: DnaNotationPattern matching
  |     |-- Entropy features: scipy.stats.entropy
  |     |-- Others: custom algorithms on raw sequence
  |-- 4. Assemble DnaChiselPredictResponseResult
  |-- 5. Return DnaChiselPredictResponse
```

### Memory & Compute Profile

| Property | Value |
|----------|-------|
| GPU | None (CPU only) |
| Memory | 1 GB |
| CPU | 0.25 cores |
| Cold start | Fast (memory snapshot enabled) |

### Determinism & Reproducibility

| Setting | Value |
|---------|-------|
| Deterministic | Yes (all features) |
| Random seeds | Not applicable |
| Hardware dependence | None |

All features are computed using exact arithmetic or well-defined numerical algorithms. Results are identical across all hardware.

### Caching Behavior

- Standard BioLM Redis + R2 two-tier caching via `BillingMixin`
- Cache key derived from input sequence and parameters (include list, species, restriction enzymes)
- Cache hits are always valid since outputs are deterministic

## Versions & Changelog

| Version | Date | Changes |
|---------|------|---------|
| v1 | -- | Initial implementation with 20 DNA features via encode action |

---

*See also: [README.md](README.md) for API reference | [BIOLOGY.md](BIOLOGY.md) for biological context*
