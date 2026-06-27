# Evo  --  Biological Context

## Molecule Coverage

### Primary Molecule Type(s)

Evo is designed for **DNA sequences**, operating at single-nucleotide resolution across genomic scales. It was trained on the OpenGenome dataset, which consists primarily of prokaryotic (bacterial and archaeal) whole genomes and bacteriophage sequences.

The model handles:
- **Prokaryotic genomes**: Bacterial and archaeal chromosomes and plasmids  --  the core of the training distribution. Evo has strong coverage of diverse microbial taxa.
- **Bacteriophage genomes**: Viral genomes that infect bacteria are well-represented in the training data.
- **Coding regions**: Genes, operons, and coding sequences across diverse organisms.
- **Non-coding regions**: Intergenic sequences, promoters, terminators, and regulatory elements in prokaryotic contexts.

**Performance considerations:**
- Best performance is on prokaryotic DNA, which dominates the training data.
- Eukaryotic DNA (plant, animal, fungal genomes) is not the primary training domain. While Evo can process eukaryotic sequences, its learned distribution may not accurately capture eukaryotic-specific features like complex splicing signals, large introns, or distal enhancer-promoter interactions.
- The model accepts only unambiguous DNA bases (A, C, G, T). Ambiguity codes (N, R, Y, W, S, etc.) are rejected at the validation layer.

### Cross-Applicability

| Molecule / Domain | Applicability | Evidence | Caveats |
|-------------------|---------------|----------|---------|
| Prokaryotic genomes | High | Core training domain (OpenGenome) | Best performance; primary use case |
| Bacteriophage genomes | High | Included in training data | Phage genomic organization is well-captured |
| Regulatory elements (prokaryotic) | High | Promoters, RBS, terminators are modeled | Log-prob scoring reflects regulatory constraint |
| CRISPR systems | High | Specialized fine-tuned variant exists (v1-8k-crispr) | Fine-tuned variant not yet enabled on BioLM |
| Transposable elements | Moderate-High | Specialized fine-tuned variant exists (v1-8k-transposon) | Fine-tuned variant not yet enabled on BioLM |
| Eukaryotic coding regions | Moderate | Codon usage patterns are partially transferable | Eukaryotic codon bias differs from prokaryotic |
| Eukaryotic regulatory elements | Low | Training data underrepresents eukaryotic regulation | Enhancers, splicing signals, CpG islands poorly modeled |
| RNA sequences | Not supported | Input validation rejects non-DNA characters (U) | Use RNA-specific models instead |
| Protein sequences | Not applicable | Evo operates on DNA, not amino acid sequences | Use ESM2 or similar protein language models |

## Biological Problems Addressed

### Problem 1: Genome-Scale DNA Sequence Generation

**Why this matters:**
Synthetic biology aims to design novel genetic constructs, from individual genes to entire synthetic genomes. Generating biologically plausible DNA sequences at scale is essential for:
- Designing synthetic microbial genomes for biotechnology applications
- Creating novel genetic circuits with realistic genomic context
- Exploring the space of possible genomes for engineering organisms with desired properties

**Traditional approaches:**
- Codon optimization tools generate coding sequences but ignore genomic context (intergenic regions, regulatory elements, genome-wide compositional biases).
- Random sequence generation produces biologically implausible DNA.
- Template-based design is limited to known natural sequences.

**How Evo addresses it:**
Evo's `generate` action produces new DNA sequences by sampling from its learned distribution of natural genomic sequences. Given a prompt (a short DNA seed sequence), the model autoregressively generates subsequent nucleotides that are statistically consistent with the patterns observed in real genomes. The generated sequences exhibit:
- Realistic codon usage
- Plausible open reading frame structures
- Genomic organizational features (e.g., operon-like gene arrangements)

**Practical considerations:**
- Generation quality depends on the prompt. A biologically meaningful seed (e.g., the start of a known gene) produces more contextually appropriate continuations.
- Temperature and top-k/top-p sampling parameters control the diversity-quality tradeoff. Low temperature (0.0-0.5) produces conservative sequences close to the training distribution; higher temperature increases novelty but may reduce biological plausibility.
- Generated sequences should be validated experimentally or computationally (e.g., ORF prediction, structure prediction) before use in synthetic biology applications.

### Problem 2: DNA Sequence Fitness Scoring

**Why this matters:**
Evaluating whether a DNA sequence is "natural-like" or functionally constrained is fundamental to:
- **Variant effect prediction**: Assessing whether a mutation disrupts function by comparing log-probabilities of wild-type vs. mutant sequences.
- **Gene essentiality**: Regions under strong evolutionary constraint (essential genes, critical regulatory elements) tend to have higher log-probabilities under a well-trained genomic model.
- **Synthetic sequence evaluation**: Scoring designed sequences to assess how well they match the distribution of natural genomes.

**Traditional approaches:**
- Conservation analysis (multiple sequence alignment) requires homologous sequences and is slow for large-scale screening.
- Experimental fitness assays (e.g., deep mutational scanning) are accurate but expensive and limited to specific genes.

**How Evo addresses it:**
The `log_prob` action computes the total log-probability of a DNA sequence under Evo's autoregressive distribution. This score reflects how well the sequence fits the model's learned representation of natural genomic sequences. Higher log-probabilities indicate sequences that are more consistent with the patterns in the training data, which correlates with:
- Evolutionary conservation
- Functional constraint
- Biological plausibility

**Interpreting scores:**
- Log-probabilities are negative values (log of probabilities between 0 and 1).
- More negative values indicate less likely sequences.
- Scores are summed over all positions, so longer sequences naturally have more negative total log-probs. For length-normalized comparisons, divide by sequence length (the model uses `reduce_method="sum"` internally).
- Relative comparisons (wild-type vs. mutant) are more informative than absolute values.

### Problem 3: Gene Regulation and Promoter Design

**Why this matters:**
Controlling gene expression is central to synthetic biology, metabolic engineering, and gene therapy. Designing promoters, ribosome binding sites (RBS), and terminators that drive desired expression levels requires understanding the sequence patterns that govern transcription and translation.

**How Evo contributes:**
While Evo is not explicitly trained on regulatory function labels, its autoregressive objective learns the statistical regularities of promoter regions, RBS motifs, and terminator sequences as they appear in natural genomes. This enables:
- **Scoring regulatory elements**: Compare log-probabilities of candidate promoter variants to assess which are most "natural-like."
- **Generating regulatory sequences**: Use generation with appropriate prompts to produce novel regulatory element candidates.
- **Context-aware design**: Unlike motif-based tools, Evo considers the broader genomic context surrounding a regulatory element.

## Applied Use Cases

### Use Case 1: Synthetic Genome Design

**Source**: Nguyen et al. "Sequence modeling and design from molecular to genome scale with Evo." *Science* (2024). [DOI](https://doi.org/10.1126/science.ado9336)

The Evo paper demonstrated generation of synthetic DNA sequences at genome scale. Generated sequences were evaluated for:
- Realistic gene density and operon organization
- Protein structure quality of encoded genes (assessed via ESMFold)
- Codon usage statistics matching natural prokaryotic genomes

Key finding: Evo-generated sequences encode proteins with plausible predicted structures, suggesting the model has learned not just nucleotide-level statistics but also the higher-order organization of genetic information.

### Use Case 2: CRISPR System Design

**Source**: Nguyen et al. "Sequence modeling and design from molecular to genome scale with Evo." *Science* (2024). [DOI](https://doi.org/10.1126/science.ado9336)

A fine-tuned Evo variant (v1-8k-crispr, not yet enabled on BioLM) was applied to generate novel CRISPR-Cas systems. The model produced sequences with:
- Correct CRISPR repeat-spacer array organization
- Functional Cas protein predictions
- Novel CRISPR system architectures not found in existing databases

This demonstrates Evo's potential for designing programmable biological systems.

## Related Models

### Predecessor Models

- **Evo 1 (v1-8k-base, v1-131k-base)**: The original Evo release. Evo 1.5 extends this with ~50% more training data and improved DNA modeling performance. The v1 variants are defined in the codebase but not currently enabled on BioLM.

### Complementary Models

- **Nucleotide Transformer (NT)**: Provides per-token DNA embeddings useful for classification tasks. Use NT when you need embeddings for downstream supervised models; use Evo when you need sequence generation or log-probability scoring.
- **ESM2**: Protein language model. For workflows that go from DNA to protein analysis, generate or score DNA with Evo, then translate coding regions and analyze proteins with ESM2.

### Alternative Models

| Alternative | Advantage over Evo | Disadvantage vs Evo |
|-------------|-------------------|---------------------|
| Nucleotide Transformer | Provides per-token embeddings; multiple model sizes | No generation capability; shorter context |
| DNABERT-2 | Strong on regulatory element classification | No generation; limited context length |
| HyenaDNA | Similar long-context architecture | Smaller model; less training data |

## Biological Background

### DNA and Genomics Primer

**DNA (deoxyribonucleic acid)** is the molecule that encodes genetic information in all cellular life and many viruses. It is a polymer of four nucleotide bases  --  adenine (A), cytosine (C), guanine (G), and thymine (T)  --  arranged in a double-helical structure. The sequence of these bases encodes the instructions for building and maintaining an organism.

**Key concepts relevant to Evo:**

- **Genome**: The complete set of DNA sequences in an organism. Bacterial genomes are typically 1-10 million base pairs; human genomes are ~3.2 billion base pairs.
- **Gene**: A segment of DNA that encodes a functional product (usually a protein). Genes are organized into operons in prokaryotes (multiple genes under shared regulatory control).
- **Regulatory elements**: Non-coding DNA sequences that control when and how much a gene is expressed. Include promoters (transcription start signals), ribosome binding sites (translation start signals), and terminators (transcription stop signals).
- **Codon usage**: The genetic code maps nucleotide triplets (codons) to amino acids. Different organisms prefer different codons for the same amino acid  --  a pattern called codon usage bias.
- **Evolutionary constraint**: Functionally important DNA regions accumulate mutations more slowly than non-functional regions. This "conservation" signal is what allows sequence models like Evo to distinguish functional from non-functional DNA.

**Why DNA language models matter:**

Traditional bioinformatics approaches to DNA analysis rely on explicit alignment to known sequences or hand-crafted features (motif databases, position weight matrices). Language models like Evo learn these patterns implicitly from large corpora of genomic sequences, enabling:
- **Zero-shot analysis**: Score or generate sequences without task-specific training data.
- **Context-dependent evaluation**: Consider the full genomic context of a sequence element, not just local motifs.
- **Generative design**: Produce novel DNA sequences that respect the complex, multi-scale statistical structure of natural genomes.

**Relevance to applications:**
- **Synthetic biology**: Design novel genetic constructs, circuits, and organisms.
- **Genomics**: Interpret genome sequences, predict variant effects, identify functional elements.
- **Biotechnology**: Engineer microorganisms for industrial production, bioremediation, or therapeutics.
- **Gene therapy**: Design optimized gene expression cassettes for therapeutic delivery.

---

*See also: [README.md](README.md) for API reference | [MODEL.md](MODEL.md) for technical details*
