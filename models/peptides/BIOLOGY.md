# peptides -- Biological Context

## Molecule Coverage

### Primary Molecule Type(s)

The peptides module is designed for peptides and proteins composed of standard amino acids. It handles:

- **Peptides**: Short amino acid chains (typically 2-50 residues). This is the primary use case. Features like antimicrobial peptide descriptors, Boman index, and hydrophobic moment are most meaningful for peptides.
- **Proteins**: Full-length proteins up to 2048 residues. While all features can be computed for longer sequences, some (e.g., hydrophobic moment, instability index) were originally validated on shorter sequences and may have reduced biological relevance for very long proteins.

The module accepts the extended amino acid alphabet including ambiguous codes (B, Z, X), though physicochemical properties for ambiguous residues are approximate.

### Cross-Applicability

| Molecule Type | Applicability | Evidence | Caveats |
|--------------|---------------|----------|---------|
| Antimicrobial peptides | High | Original package designed for AMP data mining (Osorio et al., 2015) | Features most validated for this use case |
| Cell-penetrating peptides | High | Physicochemical features are standard CPP descriptors | Amphipathicity features especially relevant |
| Globular proteins | Moderate | All features computable; biological relevance varies | Some features (hydrophobic moment) less meaningful for large proteins |
| Enzymes | Moderate | Amino acid composition and physicochemical features applicable | No active site or catalytic mechanism features |
| Antibodies | Low | Can compute features but not designed for immunoglobulin-specific properties | Use antibody-specific models for CDR analysis |
| Membrane proteins | Low | Hydrophobicity features applicable but incomplete | No transmembrane topology prediction |

## Biological Problems Addressed

### Antimicrobial Peptide (AMP) Discovery

Antimicrobial peptides are short (typically 12-50 residues) host defense molecules that kill bacteria, fungi, and viruses. With rising antibiotic resistance, there is strong interest in discovering new AMPs or engineering improved variants.

The peptides module provides the standard feature set used in AMP prediction and classification:
- **Charge and hydrophobicity**: AMPs are typically cationic and amphipathic
- **Boman index**: Measures protein-protein interaction potential, relevant for membrane disruption
- **Hydrophobic moment**: Quantifies amphipathicity, a key AMP property
- **Amino acid composition**: AMP sequences are enriched in Arg, Lys, Leu, and other specific residues

These features serve as inputs to machine learning classifiers that predict whether a given peptide sequence has antimicrobial activity.

### Peptide Property Prediction and Screening

In peptide drug development, physicochemical properties determine key pharmacological characteristics:
- **Molecular weight**: Affects oral bioavailability and membrane permeability
- **Isoelectric point (pI)**: Determines solubility at different pH values, critical for formulation
- **Instability index**: Predicts in vivo stability; values below 40 suggest a stable peptide
- **Hydrophobicity**: Influences membrane interactions and cell penetration

The module enables rapid screening of peptide libraries by computing these properties for thousands of candidate sequences, filtering for desired property ranges before expensive experimental validation.

### Feature Engineering for ML Pipelines

Many protein and peptide machine learning models benefit from physicochemical features as input descriptors. The peptides module provides a standardized, comprehensive feature set that can be used:
- As input features for custom ML models (random forests, SVMs, neural networks)
- For exploratory data analysis of peptide/protein datasets
- As baseline features to compare against learned representations (e.g., ESM2 embeddings)
- For interpretable models where feature meaning matters (vs. opaque embedding dimensions)

## Applied Use Cases

The `peptides` package has been used extensively in the antimicrobial peptide research community since its initial release as an R package in 2015. Common applications include:

### AMP Classification

Researchers use the feature set to train classifiers that distinguish AMPs from non-AMPs. The combination of physicochemical properties and descriptor vectors provides a compact, interpretable feature space for this binary classification task.

### Peptide Library Design

In combinatorial peptide library design, the features enable computational pre-screening to select candidates with desirable physicochemical profiles (e.g., target charge range, hydrophobicity, stability) before synthesis.

### Protein Characterization

Beyond peptides, the features are used for general protein characterization tasks: comparing protein families by amino acid composition, clustering proteins by physicochemical similarity, and identifying outliers in protein datasets.

## Related Models

### Complementary Models

- **ESM2**: Provides learned embeddings that capture evolutionary and structural information not present in physicochemical features. ESM2 embeddings and peptides features can be concatenated for richer feature representations.
- **ESMStabP**: Uses ESM2 embeddings for stability prediction. Peptides features (instability index, aliphatic index) provide complementary stability signals.

### Alternative Models

| Alternative | Advantage over peptides | Disadvantage |
|-------------|------------------------|--------------|
| ESM2 embeddings | Captures evolutionary and structural context | Opaque features; requires GPU |
| Biopython ProtParam | Built into Biopython; no extra dependency | Far fewer features (no descriptors, no profiles) |
| Local peptides library | No network latency | No batch API; no caching; manual integration |

## Biological Background

### Peptides and Proteins

Peptides are short chains of amino acids, typically 2-50 residues long, joined by peptide bonds. Proteins are longer polypeptide chains (50 to thousands of residues) that fold into complex three-dimensional structures. Both are composed of the same 20 standard amino acids, each with distinct physicochemical properties (size, charge, hydrophobicity, etc.).

The physicochemical properties of a peptide or protein arise from the collective properties of its constituent amino acids. For example:
- A peptide enriched in positively charged residues (Arg, Lys) will have a high net positive charge
- A peptide with alternating hydrophobic and hydrophilic residues will be amphipathic
- A protein with many aliphatic residues (Ala, Val, Ile, Leu) tends to be thermostable

### Why Physicochemical Features Matter

Unlike learned representations (embeddings), physicochemical features have direct physical interpretations:
- **Molecular weight** determines pharmacokinetics and filtration behavior
- **Isoelectric point** determines solubility, which affects drug formulation
- **Hydrophobicity** governs membrane interactions, critical for cell-penetrating peptides and AMPs
- **Charge** influences electrostatic interactions with cell membranes and binding partners
- **Instability index** predicts whether a protein will survive in biological fluids

These features remain valuable even in the era of deep learning because they are interpretable, computationally cheap, and grounded in well-understood physical chemistry. They are especially useful when training data is limited (small peptide datasets where deep learning may overfit) or when model interpretability is required (regulatory or clinical settings).

### Antimicrobial Peptides

Antimicrobial peptides (AMPs) are a class of host defense molecules found across all kingdoms of life. They typically:
- Are 12-50 residues long
- Carry a net positive charge (+2 to +9)
- Are amphipathic (one face hydrophobic, one face hydrophilic)
- Kill microbes by disrupting cell membranes

With the rise of antibiotic-resistant bacteria, AMPs are promising candidates for new therapeutics. Computational screening using physicochemical features enables rapid identification of AMP candidates from large sequence libraries.

---

*See also: [README.md](README.md) for API reference | [MODEL.md](MODEL.md) for technical details*
