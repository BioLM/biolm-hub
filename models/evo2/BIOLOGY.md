# Evo2 -- Biological Context

## Molecule Coverage

### Primary Molecule Type(s)

Evo 2 is trained on **genomic DNA** from all domains of life -- prokaryotes (bacteria and archaea), eukaryotes (including human and other multicellular organisms), and viruses. This is a major expansion over Evo 1, which was limited to prokaryotic and phage genomes.

The model handles:
- **Prokaryotic genomes**: Bacterial and archaeal chromosomes, plasmids, and operons -- the strongest domain due to training data composition
- **Eukaryotic genomes**: Coding and non-coding regions from diverse eukaryotes, including human
- **Viral genomes**: Bacteriophage and eukaryotic virus sequences
- **Coding regions**: Genes, exons, open reading frames across all domains
- **Non-coding regions**: Intergenic sequences, regulatory elements, introns

Performance considerations:
- Multi-domain training improves eukaryotic sequence modeling compared to Evo 1
- The model accepts only unambiguous DNA bases (A, C, G, T)
- Single-nucleotide (byte-level) tokenization preserves full sequence resolution

### Cross-Applicability

| Molecule / Domain | Applicability | Evidence | Caveats |
|-------------------|---------------|----------|---------|
| Prokaryotic genomes | High | Strong training domain; successor to Evo 1 | Best performance expected |
| Eukaryotic coding regions | Moderate-High | Multi-domain training includes eukaryotes | Less training emphasis than prokaryotes |
| Eukaryotic regulatory elements | Moderate | Trained on eukaryotic genomes including enhancers | Complex distal regulation may be poorly captured |
| Viral genomes | High | Included in training data | Diverse viral architectures well-represented |
| Synthetic DNA | Moderate | Can score constructs via log-probability | Novel synthetic motifs may be out-of-distribution |
| RNA sequences | Not supported | Input validation rejects non-ACGT characters | Convert U to T or use RNA-specific models |
| Protein sequences | Not applicable | DNA-only model | Use ESM2, SaProt, or similar protein LMs |

## Biological Problems Addressed

### Problem 1: DNA Embedding Extraction

**Why this matters**: Many downstream genomic analyses require fixed-dimensional numerical representations of variable-length DNA sequences. Unlike Evo 1, Evo 2 provides per-layer embedding extraction, enabling use as a feature backbone for supervised learning tasks -- gene classification, regulatory element prediction, variant effect scoring, and more.

**How Evo 2 addresses it**: The `encode` action computes embeddings from specified transformer layers. Users can request mean-pooled or last-token embeddings, and can specify which internal layers to extract from (supporting negative indexing). This flexibility allows researchers to experiment with different representation depths.

**Biological meaning**: Embeddings from earlier layers tend to capture local sequence patterns (dinucleotide composition, codon usage), while deeper layers capture more abstract, long-range dependencies (gene structure, regulatory context).

### Problem 2: DNA Sequence Fitness Scoring

**Why this matters**: Evaluating whether a DNA sequence is evolutionarily plausible or functionally constrained is fundamental to variant effect prediction, synthetic sequence evaluation, and gene essentiality analysis.

**How Evo 2 addresses it**: The `log_prob` action computes the total log-probability of a DNA sequence under the autoregressive distribution. Higher (less negative) scores indicate sequences more consistent with the training distribution.

**Interpreting scores**:
- More negative values = less likely sequences under the model
- Relative comparisons (wild-type vs. mutant) are more informative than absolute values
- Scores are summed over positions; normalize by length for cross-length comparisons

### Problem 3: DNA Sequence Generation

**Why this matters**: Synthetic biology requires generating novel DNA sequences that are biologically plausible -- realistic codon usage, proper gene structure, and functional regulatory elements. Evo 2's multi-domain training makes it suitable for generating sequences across all domains of life, not just prokaryotes.

**How Evo 2 addresses it**: The `generate` action produces new DNA by autoregressively sampling from the learned distribution, given a seed prompt. Parameters (temperature, top-k, top-p) control the diversity-quality tradeoff. Generated sequences should be validated computationally and experimentally before use.

## Applied Use Cases

### Use Case 1: Multi-Domain Genome Modeling (Published)

**Source**: Brixi et al. "Genome modeling and design across all domains of life with Evo 2." bioRxiv (2025). [doi:10.1101/2025.02.18.638918](https://doi.org/10.1101/2025.02.18.638918)

Evo 2 demonstrates improved genome modeling across prokaryotic, eukaryotic, and viral domains compared to Evo 1, establishing the benefit of multi-domain training for genomic foundation models.

### Use Case 2: Eukaryotic Variant Effect Prediction (Anticipated)

Using Evo 2 embeddings or log-probability scores to predict the functional impact of mutations in human and other eukaryotic genomes -- a task where Evo 1's prokaryotic bias was a limitation.

## Related Models

### Predecessor Models

- **Evo 1** (Nguyen et al., Science 2024): The original 7B DNA model trained on prokaryotic genomes. Evo 2 extends this with multi-domain training and additional model sizes. Evo 1 is available separately on the BioLM platform.

### Complementary Models

- **Nucleotide Transformer**: BERT-style DNA embeddings. Use NT for masked language modeling tasks; use Evo 2 for generation and autoregressive scoring.
- **ESM2**: Protein language model. For DNA-to-protein workflows, use Evo 2 for DNA analysis and ESM2 for downstream protein analysis.
- **DNA-Chisel**: Deterministic DNA feature extraction. Combine with Evo 2 embeddings for interpretable feature engineering.

### Alternative Models

| Alternative | Advantage over Evo 2 | Disadvantage vs Evo 2 |
|-------------|----------------------|----------------------|
| Evo 1 | Published in Science; well-validated | Prokaryotic only; no embedding endpoint |
| Nucleotide Transformer | 6-mer tokenization; good for classification | No generation; encoder-only |
| DNABERT-2 | Lightweight; BPE tokenization | Shorter context; no generation |
| HyenaDNA | Very long context (up to 1M bp) | Smaller model; less training data |

## Biological Background

**DNA** (deoxyribonucleic acid) is the molecule encoding genetic information in all cellular life. It consists of four nucleotide bases -- adenine (A), cytosine (C), guanine (G), and thymine (T) -- arranged in a double-helical structure. The sequence of these bases encodes genes (transcribed to RNA, often translated to protein) and regulatory instructions controlling gene expression.

**Key concepts relevant to Evo 2**:

- **Autoregressive modeling**: Predicting the next nucleotide given all preceding nucleotides. This objective naturally captures the statistical structure of genomes -- codon usage, regulatory motifs, gene boundaries -- without explicit supervision.
- **Multi-domain training**: By training on genomes from bacteria, archaea, eukaryotes, and viruses, Evo 2 learns universal patterns of DNA organization that transcend individual species, while also capturing domain-specific features.
- **Embeddings**: Dense numerical vectors representing DNA sequences in a learned high-dimensional space. Similar sequences (by function, structure, or evolutionary origin) cluster together in embedding space.
- **Log-probability scoring**: The total log-probability of a sequence under the model serves as a proxy for evolutionary plausibility. Functionally constrained regions (essential genes, conserved regulatory elements) tend to have higher log-probabilities.
- **StripedHyena**: A hybrid architecture that combines efficient gated convolutions (for capturing long-range patterns without quadratic cost) with attention layers (for precise positional interactions), enabling modeling of long genomic sequences.

---

*See also: [README.md](README.md) for API reference | [MODEL.md](MODEL.md) for technical details*
