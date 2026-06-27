# ESM1v -- Biological Context

## Molecule Coverage

### Primary Molecule Type(s)

ESM1v is designed for **proteins** broadly. It was trained on the UniRef90 database, which represents the full diversity of known protein sequences. The model is particularly suited for predicting the effects of single amino acid mutations on protein function, using a zero-shot approach that requires no task-specific training data.

**Important coverage notes:**
- Works with any protein sequence up to 512 residues
- Requires exactly one `<mask>` token per sequence (single-site analysis)
- Trained on UniRef90, covering all protein families with known sequences
- Does not handle nucleic acid sequences or non-standard amino acids

### Cross-Applicability

| Molecule Type | Applicability | Evidence | Caveats |
|--------------|---------------|----------|---------|
| Globular proteins | High | Primary training target, validated on 41 DMS datasets | Standard application |
| Enzymes | High | Well-represented in training data and DMS benchmarks | Active site mutations may need structural context |
| Membrane proteins | Moderate | Present in UniRef90 | Fewer DMS benchmarks available |
| Antibodies | Moderate | Antibody sequences in UniRef90 | Use antibody-specific models for CDR engineering |
| Viral proteins | Moderate | Present in UniRef90 | Rapid evolution may limit context |
| Peptides | Low | Very short sequences lack context for meaningful MLM | Minimum ~20 residues recommended |
| Disordered proteins | Moderate | Present in training data | Mutations in disordered regions may have different selection pressures |

## Biological Problems Addressed

### Zero-Shot Variant Effect Prediction (Published)

**Biological context**: Understanding how single amino acid mutations affect protein function is central to genetics, molecular biology, and drug development. Deep mutational scanning (DMS) experiments systematically measure the functional effects of all possible single mutations at every position, but these experiments are expensive, require functional assays, and have been completed for only a small fraction of the proteome. Computational prediction of variant effects can prioritize mutations for experimental testing and interpret clinical variants of uncertain significance.

**How ESM1v helps**: For any protein sequence, ESM1v can predict the relative fitness effect of all possible amino acid substitutions at a given position in a zero-shot manner -- without any task-specific training data. The user provides the sequence with a `<mask>` token at the position of interest, and the model returns the probability of each of the 20 standard amino acids at that position. The log-likelihood difference between the mutant and wild-type amino acid serves as a proxy for the mutation's functional effect.

**Output interpretation**: The response contains a sorted list of amino acid predictions with scores for each model (or all 5 models for the "all" variant). Higher scores indicate amino acids that are more compatible with the sequence context. To compute a variant effect score, compare the score of the mutant amino acid to the wild-type amino acid: positive differences suggest tolerated or beneficial mutations, while negative differences suggest deleterious mutations.

### Clinical Variant Interpretation (Published)

**Biological context**: Human genetic studies increasingly identify variants of uncertain significance (VUS) -- genetic changes whose functional impact is unknown. For protein-coding genes, predicting whether a missense variant is pathogenic or benign is critical for clinical genetics, particularly in cancer genomics and rare disease diagnosis.

**How ESM1v helps**: By computing the log-likelihood of the wild-type versus mutant amino acid at a given position, ESM1v provides a sequence-based prediction of whether a mutation is likely to be functionally disruptive. The ensemble of 5 models reduces variance in predictions. This information can complement other pathogenicity predictors (SIFT, PolyPhen, CADD) that use different features.

### Protein Engineering Guidance (Anticipated)

**Biological context**: When engineering a protein for improved properties (stability, activity, specificity), researchers need to decide which positions to mutate and which amino acid substitutions to try. Exhaustive experimental screening is impractical for proteins with hundreds of residues and 19 possible substitutions per position.

**How ESM1v helps**: By scoring all possible substitutions at each position, ESM1v can identify positions where the native amino acid is weakly preferred (tolerable to mutate) versus positions where it is strongly preferred (likely essential). This information can prioritize positions for mutagenesis and suggest which substitutions are most likely to be tolerated by the protein fold. However, ESM1v predicts evolutionary fitness, not specific engineered properties, so predictions should be combined with domain knowledge.

## Applied Use Cases

ESM1v has been used in several published studies since its release in 2021, particularly for benchmarking variant effect prediction methods and interpreting clinical variants.

<!-- TODO: Add specific applied literature entries from sources.yaml as they are populated -->

## Related Models

### Predecessor Models

- **ESM-1b** (Rives et al., 2021): The base model architecture that ESM1v extends. ESM-1b is a single 650M parameter model trained on UniRef50. ESM1v improves upon ESM-1b by training on UniRef90 (larger, less redundancy-reduced dataset) and using a 5-model ensemble for reduced variance.

### Complementary Models

ESM1v works well in combination with other models on the BioLM platform:

- **ESM2 / ESMC**: For general protein embeddings and representation. ESM1v focuses on variant effect prediction, while ESM2/ESMC provide richer embeddings for downstream tasks.
- **Structure prediction models** (Boltz, ESMFold): For understanding the structural context of mutations. Pipeline: predict structure to visualize mutation location, use ESM1v for functional effect prediction.
- **ESMStabP**: For stability-specific predictions. ESM1v predicts general fitness, while ESMStabP specifically predicts thermostability effects.

### Alternative Models

| Alternative | Advantage over ESM1v | Disadvantage vs ESM1v |
|-------------|---------------------|----------------------|
| ESM2 | Newer architecture, multiple sizes, embeddings | Not specifically optimized for variant effects |
| GEMME | Uses evolutionary conservation from MSA | Requires MSA computation |
| PoET | Generative model, MSA-conditioned | Requires MSA, more complex setup |
| EVmutation | Established MSA-based method | Requires MSA, older approach |

## Biological Background

### Variant Effect Prediction

The effect of a single amino acid mutation on protein function depends on multiple factors:

- **Structural context**: Is the position buried in the protein core or exposed on the surface? Buried positions are more sensitive to mutations due to packing constraints.
- **Evolutionary conservation**: Positions that are highly conserved across homologs are more likely to be functionally important. Mutations at these positions are more likely to be deleterious.
- **Physicochemical properties**: Substitutions between amino acids with similar properties (e.g., Leu -> Ile, both hydrophobic) are generally better tolerated than those between dissimilar amino acids (e.g., Gly -> Trp).
- **Functional role**: Active site residues, ligand-binding residues, and residues involved in protein-protein interactions are often under strong selection and sensitive to mutation.

### Deep Mutational Scanning (DMS)

Deep mutational scanning is an experimental technique that systematically measures the functional effects of all possible single amino acid mutations across a protein. A library of mutant variants is created, subjected to a functional selection, and the relative fitness of each variant is quantified by sequencing. DMS datasets serve as the primary benchmark for computational variant effect predictors like ESM1v.

### Masked Language Modeling for Proteins

Protein language models like ESM1v treat amino acid sequences as "sentences" and learn statistical patterns from millions of natural sequences. The masked language modeling objective -- predicting randomly masked amino acids from their sequence context -- implicitly learns the evolutionary constraints on each position. At inference time, masking a specific position and examining the model's predictions reveals which amino acids are compatible with the surrounding sequence context, providing a proxy for evolutionary fitness.

### Ensemble Approach

ESM1v uses an ensemble of 5 independently trained models (n1--n5) rather than a single model. Each model is trained with a different random initialization, leading to partially independent learned representations. Averaging predictions across the ensemble reduces noise and improves calibration. The "all" variant loads all 5 models simultaneously for ensemble prediction, while individual variants (n1--n5) are available for faster single-model queries.

---

*See also: [README.md](README.md) for API reference | [MODEL.md](MODEL.md) for technical details*
