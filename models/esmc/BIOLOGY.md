# ESM C -- Biological Context

## Molecule Coverage

### Primary Molecule Type(s)

ESM C is a general-purpose protein representation model that works across all protein types. It was trained on broad protein sequence databases and produces high-quality embeddings, per-token logits, and sequence log-probabilities applicable to diverse biological problems.

**Important coverage notes:**
- Works with any protein sequence up to 2048 residues
- Supports all 20 standard amino acids plus extended characters and gaps
- Trained on diverse protein families covering the known proteome
- Not specialized for any particular protein family but broadly applicable

### Cross-Applicability

| Molecule Type | Applicability | Evidence | Caveats |
|--------------|---------------|----------|---------|
| Globular proteins | High | Primary training target | Standard application |
| Enzymes | High | Well-represented in training data | Active site may need specialized analysis |
| Antibodies | High | Present in training data | Use AbLEF/AntiFold for antibody-specific tasks |
| Membrane proteins | Moderate-High | Present in training data | Transmembrane topology not explicitly modeled |
| Peptides | Moderate | Short sequences have less context | Works for peptides >~10 residues |
| Disordered proteins | Moderate | Present in training data | Disordered regions have less sequence conservation |
| Viral proteins | Moderate-High | Present in training data | Rapidly evolving proteins may benefit from MSA-based methods |
| Nucleic acids | Not applicable | Protein-only model | Use DNABERT2 or nucleotide transformer |

## Biological Problems Addressed

### Protein Representation and Feature Extraction (Published)

**Biological context**: Many computational biology tasks require representing proteins as fixed-dimensional vectors for downstream machine learning. The quality of these representations fundamentally affects performance on tasks such as function prediction, localization prediction, family classification, and interaction prediction. Traditional approaches used hand-crafted features (amino acid composition, physicochemical properties) or evolutionary features (MSA profiles), but protein language models provide richer, context-aware representations learned from millions of sequences.

**How ESMC helps**: The `encode` action produces embeddings at multiple granularities:
- **Mean-pooled embeddings**: A single vector per sequence (dimension depends on model variant) for sequence-level tasks like classification or clustering
- **Per-token embeddings**: A vector per residue for position-level tasks like secondary structure prediction, binding site prediction, or disorder prediction
- **Logits**: Per-position probability distributions over amino acids for analyzing sequence preferences

Users can request embeddings from any Transformer layer via `repr_layers`, enabling multi-scale feature extraction. Negative indices are supported (e.g., -1 for the last layer).

**Output interpretation**: Embeddings can be used directly as features for supervised learning, clustering, or similarity search. Mean-pooled embeddings capture global sequence properties, while per-token embeddings capture local sequence context. The last layer typically captures the most task-relevant features, while earlier layers may capture more local patterns.

### Masked Token Prediction and Sequence Design (Published)

**Biological context**: Understanding which amino acids are compatible at each position in a protein sequence is valuable for multiple tasks: identifying positions tolerant to mutation, predicting the effects of variants, and designing new sequences. Masked language models learn this information implicitly during training by predicting randomly masked positions from their sequence context.

**How ESMC helps**: The `predict` action accepts sequences with one or more `<mask>` tokens and returns the model's per-token logits restricted to the 20 canonical amino acids. This enables:
- Variant effect prediction (compare wild-type vs mutant log-likelihoods)
- Filling in unknown residues in partial sequences
- Generating position-specific scoring matrices (PSSMs) from a single sequence

**Output interpretation**: The `logits` field contains a 2D array (sequence_length x 20) of raw logits. Higher logits indicate amino acids more compatible with the sequence context. The `sequence_tokens` field shows the decoded sequence, and `vocab_tokens` maps the 20 columns to amino acid identities.

### Sequence Fitness Scoring (Published)

**Biological context**: Assessing the overall "fitness" or "naturalness" of a protein sequence is useful for evaluating designed sequences, scoring variant libraries, and filtering computationally generated candidates. A sequence that deviates significantly from the statistical patterns learned from natural sequences is more likely to be non-functional.

**How ESMC helps**: The `log_prob` action computes the total log-probability of an unmasked sequence, summing over all positions. This provides a single scalar score that reflects how well the sequence matches the patterns learned from the training data. More negative values indicate less "natural" sequences.

**Output interpretation**: The log-probability is always negative (or zero for a theoretically perfect sequence). Relative comparisons are more meaningful than absolute values: comparing log-probabilities of a wild-type sequence versus a mutant, or ranking a library of designed sequences by their log-probabilities. Note that log-probabilities are computed over only the 20 canonical amino acids at each position.

### Protein Property Prediction (Anticipated)

**Biological context**: Many protein properties of practical interest -- stability, solubility, expression level, binding affinity -- correlate with sequence features that can be captured by protein language model embeddings. Using ESMC embeddings as features for supervised models can yield property predictors that generalize better than models trained on raw sequence features alone.

**How ESMC helps**: ESMC embeddings can serve as the input layer for task-specific prediction models. For example, a simple linear model trained on ESMC embeddings and labeled stability data could predict the thermal stability of novel sequences. The improved embedding quality of ESMC over ESM2 should translate to better downstream prediction performance. However, this application depends on having labeled training data for the property of interest.

## Applied Use Cases

ESM C was released in late 2024 and the applied literature is still emerging. The ESM model family broadly has been used in hundreds of published studies for protein engineering, variant interpretation, and function prediction. See `sources.yaml` for known applied literature entries.

## Related Models

### Predecessor Models

- **ESM2** (Lin et al., 2023): The previous generation of ESM protein language models. ESM2 was trained on UniRef50 and is available in sizes from 8M to 15B parameters. ESMC improves on ESM2's parameter efficiency, achieving comparable performance with fewer parameters.
- **ESM-1b** (Rives et al., 2021): The original large-scale ESM model (650M parameters). ESMC represents two generations of improvement.

### Complementary Models

ESMC works well in combination with other models in this catalog:

- **ESMFold**: Uses ESM2 embeddings for structure prediction. ESMC embeddings may be useful in similar structure prediction pipelines.
- **ESM1v**: Specialized for variant effect prediction. ESMC's predict and log_prob actions provide alternative (potentially superior) variant scoring.
- **AbLEF**: Uses AbLang embeddings for antibody developability. ESMC embeddings could serve a similar role for general proteins.
- **Structure prediction models** (ESMFold, Chai-1): ESMC embeddings can complement structural features for integrated analysis.

### Alternative Models

| Alternative | Advantage over ESMC | Disadvantage vs ESMC |
|-------------|--------------------|--------------------|
| ESM2-650M | Well-established, widely benchmarked | Lower parameter efficiency |
| ESM2-3B | Larger model, more capacity | EvolutionaryScale's 600M variant (also MIT; not distributed here) approaches ESM2-3B quality; the distributed 300M variant surpasses ESM2-650M |
| ESM1v | Specifically optimized for variant effects | Only variant prediction, no embeddings |
| ProtTrans (ProtT5) | Available through HuggingFace | Older architecture, lower efficiency |

## Biological Background

### Protein Language Models

Protein language models apply natural language processing techniques to amino acid sequences, treating proteins as "sentences" in a 20-letter "language." By training on millions of natural protein sequences, these models learn statistical patterns that encode evolutionary information about protein structure, function, and fitness. The key insight is that positions in a protein sequence are not independent -- they co-evolve due to structural contacts, functional constraints, and phylogenetic relationships. Language models capture these dependencies in their learned representations.

### Embeddings for Proteins

A protein embedding is a dense vector representation of a protein sequence that captures biologically relevant information in a form suitable for computational analysis. Good embeddings have the property that proteins with similar functions, structures, or evolutionary origins have similar embeddings (close in vector space). ESMC produces:

- **Sequence-level (mean) embeddings**: Capture global sequence properties. Useful for comparing proteins, clustering, or predicting sequence-level properties.
- **Residue-level (per-token) embeddings**: Capture the local context of each amino acid. Useful for predicting residue-level properties (secondary structure, solvent accessibility, binding sites).

### Sequence Log-Probability as Fitness Proxy

The total log-probability of a protein sequence under a language model serves as a proxy for evolutionary fitness. Sequences with high log-probability are more "natural" -- they resemble the patterns found in the training data (millions of natural sequences shaped by evolution). This is biologically meaningful because evolution selects for functional sequences, so the statistical patterns in natural sequences encode functional constraints. A mutation that reduces the sequence's log-probability is more likely to be deleterious, while mutations that maintain or increase it are more likely to be tolerated.

### ESM Model Evolution

The ESM (Evolutionary Scale Modeling) family of protein language models has progressed through several generations:

1. **ESM-1b** (2021): First large-scale protein language model (650M parameters)
2. **ESM1v** (2021): Variant effect prediction specialist (5x650M ensemble)
3. **ESM2** (2023): Improved architecture, multiple sizes (8M--15B)
4. **ESM C** (2024, Cambrian): Latest generation with improved parameter efficiency

Each generation has improved the quality of learned representations while the underlying principle remains the same: learning the statistical structure of natural protein sequences to capture biologically meaningful patterns.

---

*See also: [README.md](README.md) for API reference | [MODEL.md](MODEL.md) for technical details*
