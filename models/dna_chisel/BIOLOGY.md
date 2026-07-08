# DNA-Chisel -- Biological Context

## Molecule Coverage

### Primary Molecule Type(s)

DNA-Chisel operates on **DNA sequences** composed of the four unambiguous nucleotides (A, C, G, T). It computes biophysical and compositional features that are relevant to gene expression, sequence stability, and synthetic biology design.

The tool is applicable to:
- **Coding sequences (CDS)**: Codon-level features (CAI, rare codon frequency, in-frame stop codons) are most meaningful for protein-coding DNA
- **Promoter regions**: TATA box count and Kozak sequence strength target regulatory elements
- **Any DNA**: Sequence-level features (GC content, entropy, homopolymer runs) apply to any DNA regardless of function

### Cross-Applicability

| Molecule Type | Applicability | Evidence | Caveats |
|---------------|---------------|----------|---------|
| Coding DNA (prokaryotic) | High | CAI and codon tables available for E. coli, B. subtilis | Species-specific codon tables must match target organism |
| Coding DNA (eukaryotic) | High | Codon tables for H. sapiens, C. elegans, D. melanogaster, S. cerevisiae | Kozak strength uses a simple consensus check |
| Promoter/regulatory DNA | Moderate | TATA box and GC content features apply | No comprehensive regulatory motif library |
| Synthetic constructs | High | All features designed for synthetic biology QC | Restriction site counting is configurable |
| Non-coding DNA | Moderate | Compositional features (GC, entropy, dinucleotides) apply | Codon-based features are not meaningful |
| RNA sequences | Not supported | Input validation rejects non-ACGT characters | Convert U to T before analysis if needed |

## Biological Problems Addressed

### Problem 1: Codon Optimization Quality Assessment

**Why this matters**: In synthetic biology and recombinant protein expression, the choice of codons affects translation efficiency, mRNA stability, and protein folding. After codon-optimizing a gene for a target host organism, researchers need to verify that the optimization achieved its goals -- high CAI, low rare codon frequency, and no introduced problems (restriction sites, hairpins, homopolymers).

**How DNA-Chisel addresses it**: The `encode` action computes CAI (Codon Adaptation Index) and rare codon frequency using species-specific codon usage tables. By including `gc_content`, `gc_content_std_dev`, `hairpin_score`, and `homopolymer_run_length`, users get a comprehensive quality report for their optimized sequence in a single API call.

**Practical interpretation**:
- **CAI close to 1.0** indicates codons match the host's preferred usage
- **Rare codon frequency close to 0.0** indicates no codons below the 10% relative usage threshold
- **Homopolymer runs > 6** may cause sequencing or synthesis errors
- **Hairpin score > 0** indicates potential secondary structure issues

### Problem 2: Cloning Compatibility Verification

**Why this matters**: Before ordering synthetic DNA for cloning, researchers must verify that the sequence is free of unwanted restriction enzyme recognition sites that would interfere with the cloning strategy. They also need to check for features that could cause synthesis failures (extreme GC content, long homopolymer runs, repetitive elements).

**How DNA-Chisel addresses it**: The `restriction_site_count` feature counts occurrences of any specified restriction enzyme recognition sites (configurable list, default: EcoRI and BsaI). Combined with `non_unique_6mer_count` (repeated 6-mers that may cause recombination) and `tandem_repeat_count`, this provides a synthesis-readiness assessment.

### Problem 3: Sequence Characterization for ML Pipelines

**Why this matters**: Machine learning models for gene expression prediction, promoter design, or variant effect classification often use hand-engineered features alongside learned representations. DNA-Chisel features (GC content, dinucleotide frequencies, nucleotide entropy, AT/GC skew) provide a standardized, reproducible feature vector for any DNA sequence.

**How DNA-Chisel addresses it**: All 20 features can be computed in a single API call and returned as a structured JSON response, ready for ingestion into downstream ML pipelines. This is especially useful as complementary features to embeddings from models like Evo or Nucleotide Transformer.

## Applied Use Cases

### Use Case 1: Pre-Synthesis Quality Control (Published)

**Source**: Edinburgh Genome Foundry (2020). DnaChisel is used in automated DNA assembly pipelines for quality-checking optimized sequences before synthesis.

DNA-Chisel features serve as a pre-synthesis checklist:
- No unwanted restriction sites
- GC content within synthesis-friendly range (25-65%)
- No extreme homopolymer runs
- Acceptable hairpin score

### Use Case 2: Feature Engineering for Expression Prediction (Anticipated)

Combining DNA-Chisel features with sequence embeddings from DNA foundation models (Evo, Nucleotide Transformer) for training expression level predictors. The deterministic, interpretable features complement the opaque learned representations.

## Related Models

### Complementary Models

- **Evo / Evo2**: DNA language models that provide learned representations and sequence generation. DNA-Chisel features can complement Evo embeddings as interpretable input features for downstream classifiers.
- **Nucleotide Transformer**: Provides learned DNA embeddings. DNA-Chisel features can serve as interpretable baselines or complementary features alongside NT embeddings.

### Alternative Models

| Alternative | Advantage over DNA-Chisel | Disadvantage vs DNA-Chisel |
|-------------|--------------------------|---------------------------|
| BioPython SeqUtils | Broader bioinformatics toolkit | No unified API; requires custom integration |
| Benchling | Full design platform with GUI | Commercial; not composable with BioLM models |
| GenScript tools | Industry-standard codon optimization | Commercial; limited to codon analysis |

## Biological Background

**DNA** (deoxyribonucleic acid) encodes genetic information as a linear sequence of four nucleotide bases: adenine (A), cytosine (C), guanine (G), and thymine (T). When a gene is expressed, the DNA is transcribed into messenger RNA and then translated into protein according to the genetic code, where each triplet of nucleotides (a "codon") specifies one amino acid.

**Key concepts relevant to DNA-Chisel features**:

- **GC content**: The proportion of G and C bases in a sequence. Affects DNA stability (higher GC = higher melting temperature), gene expression efficiency, and synthesis feasibility. Extreme values (< 25% or > 65%) can cause problems for DNA synthesis and PCR.
- **Codon Adaptation Index (CAI)**: A measure of how well the codons in a gene match the preferred codon usage of a target organism. Higher CAI generally correlates with higher protein expression levels. Different organisms use synonymous codons at different frequencies.
- **Restriction enzyme sites**: Short DNA motifs (4-8 bp) recognized and cut by bacterial restriction endonucleases. Essential for molecular cloning, but unwanted sites within a gene can interfere with cloning strategies.
- **Hairpin structures**: Regions where a DNA strand can fold back on itself due to complementary sequences, forming stem-loop structures. These can impede transcription, replication, and DNA synthesis.
- **Homopolymer runs**: Stretches of a single repeated nucleotide (e.g., AAAAAAA). Long runs cause errors in sequencing technologies (especially nanopore and older Illumina chemistry) and can impede DNA synthesis.
- **Dinucleotide frequencies**: The frequency of each possible pair of adjacent nucleotides. Some dinucleotides (e.g., CpG in mammals) have biological significance due to methylation patterns.
- **Shannon entropy**: A measure of sequence complexity. Low entropy indicates repetitive or biased composition; high entropy indicates diverse nucleotide usage.

---

*See also: [README.md](README.md) for API reference | [MODEL.md](MODEL.md) for technical details*
