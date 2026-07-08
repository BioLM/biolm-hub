# Omni-DNA -- Biological Context

## Molecule Coverage

### Primary Molecule Type(s)

Omni-DNA is designed for **genomic DNA sequences** composed of the four canonical bases (A, C, G, T). It uses BPE (byte-pair encoding) tokenization, which learns data-driven subword units from DNA sequences -- potentially capturing biologically meaningful motifs as individual tokens.

The model is applicable to:
- **Coding regions**: Exons, open reading frames, gene bodies
- **Non-coding DNA**: Intergenic regions, regulatory elements
- **Genomic sequences of varying complexity**: The BPE tokenizer handles both repetitive and complex sequences

### Cross-Applicability

| Molecule Type | Applicability | Evidence | Caveats |
|---------------|---------------|----------|---------|
| Genomic DNA | High | Primary training domain | Performance varies by organism representation in training data |
| Coding DNA | High | Codon patterns captured by BPE tokenization | |
| Regulatory DNA | Moderate | BPE may capture regulatory motifs | Less validated than NT or DNABERT on regulatory benchmarks |
| Synthetic DNA | Moderate | Can score via log-probability | Novel motifs may be out-of-distribution for BPE vocabulary |
| RNA sequences | Not supported | Input validation rejects non-ACGT characters | Use RNA-specific models |
| Protein sequences | Not applicable | DNA-only model | Use ESM2 or similar protein LMs |

## Biological Problems Addressed

### Problem 1: DNA Sequence Representation Learning

**Why this matters**: Producing fixed-dimensional numerical representations of DNA sequences is essential for downstream ML tasks -- gene classification, regulatory element identification, variant effect prediction, and sequence clustering. Unlike k-mer-based tokenization (Nucleotide Transformer) or byte-level tokenization (Evo), BPE tokenization learns variable-length subword units from the data itself.

**How Omni-DNA addresses it**: The `encode` action extracts embeddings from the final hidden layer of the transformer. Users can request mean-pooled (averaging over all non-padded tokens) or last-token embeddings. These serve as feature vectors for any downstream supervised or unsupervised task.

**Biological meaning**: The BPE tokenizer may learn biologically meaningful tokens -- common dinucleotides, codons, or regulatory motifs -- as individual vocabulary entries. This could provide an intermediate granularity between single-nucleotide models (Evo) and fixed 6-mer models (NT).

### Problem 2: DNA Sequence Fitness Scoring

**Why this matters**: Evaluating whether a DNA sequence is consistent with natural genomic patterns is important for variant interpretation, synthetic biology, and gene annotation.

**How Omni-DNA addresses it**: The `log_prob` action computes the total autoregressive log-probability of each sequence. The model processes sequences through its causal language model, computes log-softmax over the BPE vocabulary, and sums the log-probabilities of the actual tokens at each position.

**Interpreting scores**:
- More negative values indicate sequences less consistent with the training distribution
- Scores are summed over BPE tokens (not nucleotides), so comparison across sequences of different lengths requires normalization
- Wild-type vs. mutant comparisons can identify potentially deleterious mutations

## Applied Use Cases

### Use Case 1: Multi-Task DNA Analysis (Published)

**Source**: Li et al. "Omni-DNA: A Unified Genomic Foundation Model for Cross-Modal and Multi-Task Learning." arXiv:2502.03499 (2025).

The paper demonstrates that a unified auto-regressive framework can handle multiple DNA tasks within a single model, potentially simplifying pipelines that currently require separate models for embedding extraction and sequence scoring.

### Use Case 2: Cross-Modal Genomic Feature Engineering (Anticipated)

Using Omni-DNA embeddings alongside protein embeddings (from ESM2) and deterministic DNA features (from DNA-Chisel) for multi-modal genomic analysis workflows.

## Related Models

### Complementary Models

- **ESM2**: Protein language model. For DNA-to-protein workflows, use Omni-DNA for DNA analysis and ESM2 for protein analysis.
- **Evo / Evo2**: Autoregressive DNA models with generation capability. Use when sequence generation is needed.
- **DNA-Chisel**: Deterministic feature extraction. Provides interpretable features that complement learned embeddings.

### Alternative Models

| Alternative | Advantage over Omni-DNA | Disadvantage vs Omni-DNA |
|-------------|------------------------|-------------------------|
| Nucleotide Transformer | Established benchmarks; multi-species training | Fixed 6-mer tokenization; no autoregressive scoring |
| Evo 2 | Generation capability; multi-domain training | Much larger model; byte-level only |
| DNABERT-2 | Also uses BPE; well-benchmarked | Shorter context; masked LM only |

## Biological Background

**DNA** (deoxyribonucleic acid) encodes genetic information as a sequence of four nucleotide bases: adenine (A), cytosine (C), guanine (G), and thymine (T). Language models for DNA learn the statistical patterns in genomic sequences -- codon usage, regulatory motifs, compositional biases -- through self-supervised training objectives.

**Key concepts relevant to Omni-DNA**:

- **BPE tokenization**: Byte-pair encoding is a subword tokenization algorithm that iteratively merges the most frequent pairs of tokens. Applied to DNA, BPE discovers variable-length "words" in the genomic sequence -- common dinucleotides, codons, or short motifs -- as vocabulary entries. This provides a data-driven alternative to fixed k-mer tokenization.
- **Autoregressive scoring**: The model predicts each BPE token given all preceding tokens. The total log-probability of a sequence reflects how well it conforms to the patterns learned during training.
- **Embedding extraction**: The hidden states of the transformer capture contextual information about each position in the sequence. Mean pooling over positions yields a fixed-dimensional representation of the entire sequence.
- **Multi-task learning**: Training a single model on multiple objectives (or using a single architecture for multiple downstream tasks) can improve generalization by forcing the model to learn broadly useful representations.

---

*See also: [README.md](README.md) for API reference | [MODEL.md](MODEL.md) for technical details*
