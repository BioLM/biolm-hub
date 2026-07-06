# DNA-Chisel

> **One-line summary**: Algorithmic DNA sequence feature extractor that computes 20 biophysical and compositional features -- GC content, codon adaptation, hairpin score, restriction sites, and more -- for synthetic biology quality control and sequence characterization.

## Overview

DNA-Chisel is a deterministic, CPU-only DNA analysis tool built on the [DnaChisel](https://github.com/Edinburgh-Genome-Foundry/DnaChisel) library from the Edinburgh Genome Foundry. It is **not a machine learning model** -- it uses rule-based algorithms to compute sequence features. This makes it fully reproducible, fast, and interpretable.

By default, if no additional parameters are provided, all 20 features are computed. Users can select any subset of features via the `include` parameter and specify species-specific codon tables and restriction enzymes.

## Architecture

| Property | Value |
|----------|-------|
| Architecture | Algorithmic (rule-based) |
| Parameters | 0 (no learnable parameters) |
| GPU required | No (CPU only) |
| Deterministic | Yes |
| License | MIT |

## Model Variants

DNA-Chisel is a single-variant model with no size options.

| Variant | Slug | GPU | Memory | Use Case |
|---------|------|-----|--------|----------|
| **DNA-Chisel** | `dna-chisel` | None (CPU) | 1 GB | DNA feature extraction |

## Capabilities & Limitations

**CAN be used for:**
- Computing GC content, CAI, hairpin score, melting temperature, and 16 other DNA features
- Checking restriction enzyme site counts for cloning compatibility
- Assessing codon optimization quality for a target species
- Generating interpretable feature vectors for downstream ML pipelines
- Pre-synthesis quality control of synthetic DNA constructs

**CANNOT be used for:**
- Sequence generation or design (use Evo or Evo2 instead)
- Learned embeddings or representations (use Nucleotide Transformer or Evo2 instead)
- RNA analysis (input must be DNA: A, C, G, T only)
- Protein analysis (operates on DNA only)

**Other considerations:**
- Batch size is 1 (one sequence per request)
- Some features return `null` when sequence length is not a multiple of 3 (in-frame stop codons, methionine frequency)

## Features

- **GC Content**: Fraction of G and C nucleotides (0–1).
- **CAI**: Codon Adaptation Index for a specified species (default: `e_coli`).
- **Hairpin Score**: Number of potential hairpin-forming regions.
- **Melting Temperature**: Computed melting temperature of the sequence (using `primer3.calc_tm`).
- **Restriction Site Count**: Number of occurrences of specified restriction sites.
  Enzyme names (default: `["EcoRI", "BsaI"]`) are automatically converted into their recognition sequences using Biopython's Restriction module.
- **Codon Usage Entropy**: Shannon entropy of the codon usage distribution.
- **Rare Codon Frequency**: Proportion of rare codons in the sequence.
- **Homopolymer Run Length**: Maximum length of consecutive identical nucleotides.
- **Dinucleotide Frequencies**: Frequencies of each possible dinucleotide.
- **Sequence Length**: Length of the DNA sequence.
- **TATA Box Count**: Number of TATA box motifs.
- **Non-Unique 6-mer Count**: Number of 6-mers that appear more than once.
- **In-Frame Stop Codon Count**: Number of stop codons in the reading frame.
- **Methionine Frequency**: Frequency of methionine in the translated sequence.
- **AT Skew**: (A - T) / (A + T)
- **GC Skew**: (G - C) / (G + C)
- **Nucleotide Entropy**: Shannon entropy of nucleotide distribution.
- **Tandem Repeat Count**: Number of tandem repeats (homopolymers) of length >= 3.
- **GC Content Std Dev**: Standard deviation of GC content in 50bp windows.
- **Kozak Sequence Strength**: Score based on the presence of a Kozak consensus sequence.

## Actions / Endpoints

### `encode`

Computes selected DNA features for a single input sequence. By default, all 20 features are computed.

**Request Schema**: `DnaChiselEncodeRequest`

| Parameter | Type | Default | Range | Description |
|-----------|------|---------|-------|-------------|
| `items[].sequence` | str | (required) | >= 1 nt | DNA sequence (A/C/G/T only) |
| `params.include` | list[DnaChiselFeatureOptions] | all 20 features | -- | Features to compute |
| `params.species` | SupportedSpecies | `e_coli` | 6 species | Species for codon-related features |
| `params.restriction_enzymes` | list[str] or null | `["EcoRI", "BsaI"]` | valid enzyme names | Enzymes for restriction site counting |

**Supported species**: `e_coli`, `s_cerevisiae`, `h_sapiens`, `c_elegans`, `b_subtilis`, `d_melanogaster`

**Batch limit**: 1 item per request.

**Response Schema**: `DnaChiselEncodeResponse`

```json
{
  "results": [
    {
      "gc_content": 0.556,
      "cai": 0.812,
      "hairpin_score": 0.0,
      "melting_temperature": 28.4,
      "restriction_site_count": {"EcoRI": 0, "BsaI": 0},
      "codon_usage_entropy": 3.17,
      "rare_codon_frequency": 0.0,
      "homopolymer_run_length": 1,
      "dinucleotide_frequencies": {"AA": 0.0, "AC": 0.125, ...},
      "sequence_length": 9,
      "tata_box_count": 0,
      "non_unique_6mer_count": 0,
      "in_frame_stop_codon_count": 0,
      "methionine_frequency": 0.333,
      "at_skew": -0.25,
      "gc_skew": 0.0,
      "nucleotide_entropy": 2.0,
      "tandem_repeat_count": 0,
      "gc_content_std_dev": 0.0,
      "kozak_sequence_strength": 0.0
    }
  ]
}
```

Fields are `null` when not included in the `include` list or when computation is not applicable (e.g., in-frame stop codon count when sequence length is not a multiple of 3).

## Usage Examples

```python
# Compute all features with default parameters
from models.dna_chisel.schema import (
    DnaChiselEncodeRequest,
    DnaChiselEncodeRequestItem,
)

request = DnaChiselEncodeRequest(
    items=[DnaChiselEncodeRequestItem(sequence="ATGCGTACG")]
)

# Compute specific features for a target species
from models.dna_chisel.schema import (
    DnaChiselEncodeRequest,
    DnaChiselEncodeRequestItem,
    DnaChiselEncodeRequestParams,
    DnaChiselFeatureOptions,
)

request = DnaChiselEncodeRequest(
    params=DnaChiselEncodeRequestParams(
        include=[
            DnaChiselFeatureOptions.GC_CONTENT,
            DnaChiselFeatureOptions.CAI,
            DnaChiselFeatureOptions.RARE_CODON_FREQUENCY,
        ],
        species="h_sapiens",
        restriction_enzymes=["EcoRI", "BamHI", "HindIII"],
    ),
    items=[DnaChiselEncodeRequestItem(sequence="ATGAAAGCAATTTTCGTACTG")],
)
```

## Performance & Benchmarks

Not applicable (algorithmic tool). All outputs are deterministic and exact.

## Implementation Verification

### Verification Method

Deterministic output comparison: test fixtures compare computed features against golden reference outputs with relative tolerance of 1e-4.

### Test Cases

| Test Case | Action | Input | Verification |
|-----------|--------|-------|--------------|
| Explicit parameters | `encode` | 3 features selected | Exact match to golden output |
| Default parameters | `encode` | All 20 features | Exact match to golden output |

### Verification Status

**Status: VERIFIED** -- Integration tests pass for both explicit and default parameter test cases with rel_tol=1e-4.

## Resource Requirements

| Resource | Value |
|----------|-------|
| GPU | None (CPU only) |
| Memory | 1 GB |
| CPU | 0.25 cores |
| Cold start | Fast (memory snapshot enabled) |
| Batch size | 1 item per request |
| Dependencies | `dnachisel==3.2.13`, `python-codon-tables==0.1.13`, `primer3-py==2.0.3` |

## Implementation Notes

- **Memory snapshots**: Uses `@modal.enter(snap=True)` to pre-load library modules (dnachisel, primer3, scipy, Biopython Restriction) for faster cold starts.
- **Caching**: Response caching is handled by the serving layer, not the model container.
- **Species validation**: The `SupportedSpecies` enum restricts codon table lookups to 6 validated species.
- **Restriction enzyme validation**: Enzyme names are validated against Biopython's full enzyme database at request time.

## License

- **Code**: MIT ([LICENSE](https://github.com/Edinburgh-Genome-Foundry/DnaChisel/blob/master/LICENSE))
- **Library**: MIT (DnaChisel)

## References & Citations

### Papers

1. Zulkower V, Rosser S. "DNA Chisel, a versatile sequence optimizer." *Bioinformatics* 36(16), 4508--4509 (2020). [DOI](https://doi.org/10.1093/bioinformatics/btaa558)

### Links

- **GitHub**: [github.com/Edinburgh-Genome-Foundry/DnaChisel](https://github.com/Edinburgh-Genome-Foundry/DnaChisel)

---

*See also: [MODEL.md](MODEL.md) for technical deep-dive | [BIOLOGY.md](BIOLOGY.md) for biological context*
