# CLEAN -- Biological Context

## Molecule Coverage

### Primary Molecule Type(s)

CLEAN is designed for **enzyme protein sequences** -- proteins that catalyze biochemical reactions. It operates on single-chain amino acid sequences from all domains of life (bacteria, archaea, eukaryotes). The model was trained on SwissProt enzyme entries clustered at 100% identity (split100), covering approximately 220,000 sequences across 5,242 EC classes.

Performance characteristics by protein type:
- **Well-characterized enzymes**: Highest accuracy and confidence, especially for EC classes with many training examples
- **Novel or understudied enzymes**: Strong performance demonstrated on newly deposited enzymes (New-392 benchmark), a key advantage over alignment-based methods
- **Multifunctional enzymes**: Can detect promiscuity (multiple EC annotations) via the max-separation algorithm, though capped at 5 predictions per sequence
- **Non-enzyme proteins**: Not designed for this use case; will produce meaningless predictions with typically low confidence scores
- **Membrane proteins and IDPs**: Supported as input but EC prediction accuracy depends on representation in training data

Sequence constraints:
- Maximum 1022 amino acids (ESM-1b positional encoding limit)
- Standard and extended amino acid alphabets accepted (non-canonical residues mapped to standard equivalents)

### Cross-Applicability

| Molecule Type | Applicability | Evidence | Caveats |
|--------------|---------------|----------|---------|
| Enzymes (catalytic proteins) | High | Published benchmarks on New-392 and Price-149 datasets | Primary design target; ~5,242 EC classes covered |
| Non-enzyme proteins | Not applicable | Not evaluated | Model will assign nearest EC cluster; results are meaningless for non-enzymes |
| Peptides (<30 residues) | Low | Not evaluated | Short sequences produce poor ESM-1b representations |
| Antibodies | Not applicable | Not evaluated | Antibody function is not described by EC numbers |
| DNA/RNA | Not applicable | N/A | Model only accepts amino acid sequences |

**Published use case**: CLEAN is specifically trained and validated for enzyme EC number prediction. It should not be applied to non-enzyme proteins or non-protein molecules.

**Anticipated cross-applicability**: The 128-dimensional CLEAN embeddings encode enzyme functional similarity and may be useful as features for downstream enzyme engineering tasks (e.g., clustering enzyme families, identifying functionally similar enzymes across species). This use has not been formally validated but follows logically from the contrastive learning objective.

## Biological Problems Addressed

### Problem 1: Enzyme Function Annotation

**Biological context**: Enzyme Commission (EC) numbers are the standard classification system for enzyme-catalyzed reactions. As genomic sequencing outpaces experimental characterization, the majority of predicted protein sequences lack functional annotation. Traditional computational approaches (BLASTp, HMMER) depend on sequence similarity to annotated proteins and fail for novel or distantly related enzymes.

**Why this matters**: Accurate enzyme annotation is essential for:
- Understanding metabolic pathways in newly sequenced organisms
- Identifying biosynthetic gene clusters for natural product discovery
- Annotating metagenomics datasets from environmental samples
- Predicting enzymatic activities for biotechnology applications

**How CLEAN addresses it**: CLEAN embeds protein sequences into a functional similarity space where distance correlates with EC classification, rather than sequence identity. This enables:
- Annotation of enzymes with low sequence similarity to known entries
- Confidence-scored predictions via GMM ensemble
- Automatic determination of prediction count via the max-separation algorithm
- Detection of promiscuous enzymes with multiple activities

**Accuracy**: CLEAN achieves F1=0.760 on the New-392 benchmark (enzymes deposited after training cutoff), compared to F1=0.117 for BLASTp, demonstrating strong generalization to novel enzymes.

### Problem 2: Enzyme Similarity Search and Clustering

**Biological context**: Grouping enzymes by functional similarity is fundamental to understanding enzyme evolution, identifying isozymes across species, and discovering new members of enzyme families. Sequence-based clustering (e.g., CD-HIT, MMseqs2) groups by sequence identity, which does not always correlate with function -- convergently evolved enzymes may share function but not sequence.

**How CLEAN addresses it**: The 128-dimensional CLEAN embeddings capture functional similarity: enzymes with the same EC number cluster together regardless of sequence identity. These embeddings can be used for:
- Functional clustering of enzyme databases
- Identifying functionally equivalent enzymes across divergent organisms
- Nearest-neighbor search for enzymes with similar catalytic activities

**Published evidence**: The CLEAN paper demonstrates that the learned embedding space correctly separates enzyme classes and places functionally related enzymes nearby, even when sequence identity is low.

### Problem 3: Enzyme Promiscuity Detection

**Biological context**: Many enzymes catalyze more than one reaction (enzyme promiscuity). This is biologically significant for understanding metabolic flexibility and is exploited in enzyme engineering to develop biocatalysts with altered or broadened specificity.

**How CLEAN addresses it**: By computing distances to multiple EC cluster centers and applying the max-separation algorithm, CLEAN can identify when a sequence is close to multiple EC classes, suggesting promiscuous activity. The top-k predictions (up to 5 by the max-separation cap) with associated confidence scores indicate which additional activities are plausible.

**Published evidence**: The CLEAN paper validates promiscuity detection on known multi-functional enzymes from SwissProt.

## Applied Use Cases

### Use Case 1: Annotation of Newly Characterized Enzymes (Published)

**Source**: Yu et al. "Enzyme function prediction using contrastive learning." *Science* (2023). [DOI](https://doi.org/10.1126/science.adf2465)

The CLEAN paper itself validates the model on the New-392 dataset -- 392 enzymes deposited in UniProt after the training data cutoff. CLEAN correctly annotated 74.1% of these enzymes (recall), compared to 9.0% for BLASTp. This demonstrates the model's primary use case: annotating enzymes that cannot be classified by sequence alignment.

### Use Case 2: Structure-Enhanced Enzyme Function Annotation (CLEAN-Contact)

**Source**: (2024). "Improved enzyme functional annotation prediction using contrastive learning with structural inference." *Communications Biology*. [DOI: 10.1038/s42003-024-07359-z](https://doi.org/10.1038/s42003-024-07359-z)

CLEAN-Contact extends the CLEAN framework by incorporating structural data (ESM-2 contact maps + ResNet50), improving EC number prediction accuracy across benchmarks. This work validates the CLEAN contrastive learning paradigm and demonstrates that structural information can further enhance enzyme function annotation -- relevant for users deciding between sequence-only CLEAN and structure-augmented approaches.

### Use Case 3: Benchmarking Against Graph-Based Enzyme Function Predictors

**Source**: (2024). "Accurately predicting enzyme functions through geometric graph learning on ESMFold-predicted structures." *Nature Communications*. [DOI: 10.1038/s41467-024-52533-w](https://doi.org/10.1038/s41467-024-52533-w)

GraphEC benchmarked against CLEAN on 52,037 unannotated Swiss-Prot proteins, finding 21% agreement on EC annotations between the two methods. This comparison establishes CLEAN as a baseline for newer structure-based enzyme function predictors and highlights the complementary nature of sequence-based (CLEAN) and structure-based (GraphEC) approaches for enzyme annotation.

### Use Case 4: Metagenomics Enzyme Discovery (Anticipated)

Environmental metagenomics projects produce millions of predicted protein sequences, many from uncultured organisms with no close homologs in databases. CLEAN's ability to annotate enzymes without requiring high sequence similarity to known entries makes it suitable for functional annotation of metagenomic enzyme predictions.

**Status**: Anticipated use case based on model capabilities. Not formally validated in published literature for metagenomics-scale datasets.

### Use Case 5: Enzyme Engineering and Directed Evolution (Anticipated)

In directed evolution campaigns, researchers generate libraries of enzyme variants. CLEAN embeddings could be used to:
- Predict whether mutations alter enzyme function (EC class change)
- Cluster variant libraries by predicted function
- Screen for variants that retain desired activity

**Status**: Anticipated use case. The Price-149 benchmark (from a directed evolution study) provides indirect evidence that CLEAN can handle engineered enzyme variants.

## Related Models

### Predecessor Models

- **BLASTp / HMMER**: Sequence alignment methods that transfer annotations from homologs. CLEAN dramatically outperforms these on distantly related enzymes but alignment methods remain useful when high-identity homologs exist.
- **DeepEC**: Deep learning classifier for EC prediction. CLEAN uses a fundamentally different contrastive learning approach rather than fixed-class classification.
- **ProteInfer**: CNN-based enzyme function predictor. CLEAN outperforms ProteInfer on both New-392 and Price-149 benchmarks.

### Complementary Models

- **ESM-2** (on BioLM): General-purpose protein embeddings. Use ESM-2 for general protein representation tasks; use CLEAN specifically when EC number prediction or enzyme functional similarity is needed.
- **Structure prediction models** (Boltz, ESMFold): Can provide 3D structure context that complements CLEAN's sequence-based functional prediction.

### Alternative Models

| Alternative | Advantage over CLEAN | Disadvantage vs CLEAN |
|-------------|---------------------|----------------------|
| BLASTp | Faster; interpretable alignments | Fails on novel enzymes (F1=0.117 vs 0.760 on New-392) |
| DeepEC | No embedding computation needed | Lower accuracy; fixed EC class set |
| ProteInfer | Predicts GO terms beyond EC numbers | Lower EC prediction accuracy |
| ECPred | Hierarchical EC prediction | Lower accuracy on novel enzymes |

## Biological Background

### Enzyme Commission (EC) Numbers

Enzymes are proteins that catalyze biochemical reactions. The Enzyme Commission (EC) classification system assigns a four-level hierarchical number to each enzyme based on the reaction it catalyzes:

```
EC X.Y.Z.W
|  | | |
|  | | +-- Serial number (specific enzyme)
|  | +---- Sub-subclass (type of bond or group acted on)
|  +------ Subclass (type of chemical group transferred)
+--------- Class (general reaction type)
```

The seven main EC classes are:
1. **Oxidoreductases** (EC 1): Transfer electrons between molecules
2. **Transferases** (EC 2): Transfer functional groups between molecules
3. **Hydrolases** (EC 3): Break bonds using water
4. **Lyases** (EC 4): Break bonds without hydrolysis or oxidation
5. **Isomerases** (EC 5): Rearrange atoms within a molecule
6. **Ligases** (EC 6): Join molecules using ATP energy
7. **Translocases** (EC 7): Move molecules across membranes

As of 2023, there are over 8,000 defined EC numbers, though SwissProt contains experimental evidence for approximately 5,242. Many predicted genes in sequenced genomes encode putative enzymes with unknown EC assignments, making computational annotation a critical bottleneck.

### Contrastive Learning for Protein Function

Traditional enzyme classifiers train a neural network to output probabilities over a fixed set of EC classes. This approach has two fundamental limitations:
1. Adding new EC classes requires retraining the entire model
2. EC classes with few training examples are poorly learned

Contrastive learning avoids both problems by learning a distance metric rather than a classifier. The model learns to embed sequences such that:
- Sequences with the **same** EC number have **small** Euclidean distance
- Sequences with **different** EC numbers have **large** Euclidean distance

At inference time, a new sequence is embedded and compared against precomputed cluster centers for all known EC classes. New EC classes can be added simply by computing their cluster centers from a few example sequences, without retraining.

### Relevance to Biotechnology

Accurate enzyme annotation has direct applications in:
- **Drug metabolism**: Predicting which enzymes metabolize drug compounds
- **Industrial biocatalysis**: Identifying enzymes for green chemistry applications
- **Synthetic biology**: Designing metabolic pathways from annotated enzyme parts
- **Agriculture**: Understanding pest resistance mechanisms through metabolic pathway analysis
- **Bioremediation**: Discovering enzymes that degrade environmental pollutants

---

*See also: [README.md](README.md) for API reference | [MODEL.md](MODEL.md) for technical details*
