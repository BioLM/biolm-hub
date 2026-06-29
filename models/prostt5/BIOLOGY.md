# ProstT5 -- Biological Context

## Molecule Coverage

### Primary Molecule Type(s)

ProstT5 is designed for **proteins** -- it operates on amino acid sequences and their corresponding Foldseek 3Di structural alphabet representations. The model is applicable to any protein that can be represented as:
- A standard amino acid sequence (uppercase, 20-letter alphabet + X for ambiguous)
- A 3Di structural token sequence (lowercase, 20-letter alphabet: acdefghiklmnpqrstvwy)

The model does not directly handle nucleic acids, small molecules, or multi-chain complexes. It treats each protein as an independent sequence.

### Cross-Applicability

| Molecule Type | Applicability | Evidence | Caveats |
|--------------|---------------|----------|---------|
| Globular proteins | High | Primary training target | Well-represented in AlphaFold DB |
| Enzymes | High | Well-represented in training data | 3Di tokens capture active site geometry |
| Membrane proteins | Moderate | Included in AlphaFold DB structures | Less diverse training examples |
| Disordered proteins | Low | 3Di alphabet assumes local structure exists | Disordered regions have ambiguous 3Di assignments |
| Antibodies | Moderate | General protein coverage | Specialized models (ImmuneBuilder) may be better for CDR loops |
| Peptides | Low | Short sequences have limited context | 3Di tokens need sufficient local context |
| Nucleic acids | Not applicable | Not in training vocabulary | Use specialized models |
| Small molecules | Not applicable | Not in training vocabulary | Use RDKit or molecular docking |

## Biological Problems Addressed

### Protein Structure Representation via Structural Alphabet

**Biological context**: Protein 3D structures are traditionally represented as sets of atomic coordinates, which are high-dimensional and computationally expensive to process. The Foldseek 3Di alphabet compresses local 3D geometry into a single character per residue, creating a "structural sequence" that can be processed by sequence models. This dramatically reduces the complexity of structural comparison and search.

**How ProstT5 helps**: ProstT5 learns the bidirectional mapping between amino acid sequences and 3Di structural tokens. The `encode` action in AA2fold direction produces embeddings that capture both sequence and structural information, enabling structure-aware downstream predictions (fold classification, function annotation) without requiring explicit 3D coordinates.

**Output interpretation**: For the `encode` action, the 1024-dimensional mean representation captures the global structural/sequence properties of the protein. These embeddings can be used for clustering, classification, or as features for downstream ML models.

### Protein Fold Classification and Remote Homology Detection

**Biological context**: Identifying the structural fold of a protein is essential for function prediction, as proteins with similar folds often share evolutionary relationships and biochemical functions, even when sequence similarity is low (remote homology). Traditional methods rely on sequence alignment, which fails for remote homologs with <20% sequence identity.

**How ProstT5 helps**: Because ProstT5 embeddings encode structural information learned from the translation task, they are better at detecting remote homology than pure sequence-based embeddings. Proteins with similar folds but different sequences will have similar ProstT5 embeddings, enabling classification of proteins into structural families.

### Inverse Folding (Structure-to-Sequence Translation)

**Biological context**: Given a desired protein structure (represented as 3Di tokens from Foldseek), predicting which amino acid sequences could adopt that structure is the inverse folding problem. This is central to protein design: it allows computational generation of novel sequences that fold into target structures.

**How ProstT5 helps**: The `generate` action in fold2AA direction takes a 3Di structural sequence and generates amino acid sequences predicted to adopt that structure. Multiple samples can be generated with different temperatures and sampling strategies to explore the sequence space of structurally compatible designs.

**Output interpretation**: Generated amino acid sequences are uppercase strings of the same length as the input 3Di sequence. Higher temperature produces more diverse sequences; lower temperature produces sequences more similar to the training distribution. Multiple samples should be generated and evaluated experimentally.

### Forward Folding (Sequence-to-Structure Translation)

**Biological context**: Predicting the 3Di structural representation from an amino acid sequence is a lightweight alternative to full 3D structure prediction. While less detailed than atomic-level prediction (AlphaFold2, ESMFold), 3Di predictions enable rapid structural annotation and comparison using Foldseek.

**How ProstT5 helps**: The `generate` action in AA2fold direction translates amino acid sequences to 3Di tokens. This enables rapid structural annotation of large protein databases without running full structure prediction. The output 3Di sequences can be searched against structural databases using Foldseek.

## Applied Use Cases

### Published Applications

- **Structural database search**: Generate 3Di tokens from query sequences for Foldseek structural search without running AlphaFold2
- **Protein function prediction**: Use ProstT5 embeddings as features for function classifiers
- **Fold-level classification**: Assign SCOP/CATH fold families using structure-aware embeddings

### Anticipated Use Cases

- **Protein design**: Generate diverse sequences from target 3Di structures as starting points for experimental validation
- **Metagenomic annotation**: Rapidly annotate structural families for millions of metagenomic sequences
- **Evolutionary analysis**: Use structural embeddings to detect remote homology in protein family studies

Published applications include: CATHe2 (Mouret & Abbass, 2025, Biology Methods and Protocols) using ProstT5
3Di embeddings for remote homology detection across ~1700 CATH superfamilies; GraphPBSP (2024, International
Journal of Biological Macromolecules) for protein binding site prediction; and Phold (2026, Nucleic Acids
Research) for phage genome annotation via 3Di-based Foldseek search of 1.36M phage proteins.

## Related Models

### Predecessor Models

- **ProtT5-XL-U50** (Elnaggar et al., 2022): The amino acid-only protein language model that ProstT5 is fine-tuned from. ProtT5 provides strong sequence embeddings but lacks structural awareness.
- **ESM-2** (Lin et al., 2023): Alternative protein language model with similar embedding capabilities. ProstT5 differs by explicitly modeling the structure-sequence relationship via translation.

### Complementary Models

- **Foldseek**: The structural alignment tool that defines the 3Di alphabet ProstT5 operates on. Foldseek can convert PDB/mmCIF structures to 3Di tokens for ProstT5 input.
- **AlphaFold2 / ESMFold**: Full 3D structure prediction models. Their predicted structures can be converted to 3Di tokens for ProstT5 encoding.
- **ESM2**: Alternative embedding model. ProstT5 and ESM2 embeddings capture complementary information and can be combined for downstream tasks.

### Alternative Models

| Alternative | Advantage over ProstT5 | Disadvantage vs ProstT5 |
|-------------|------------------------|--------------------------|
| ESM2 | Larger models available (3B); wider validation | No structural alphabet translation capability |
| ProtT5 | Simpler (AA-only); same base architecture | Lacks structure-aware embeddings |
| SaProt | Similar bilingual approach with SA tokens | Different structural alphabet (not 3Di) |
| ESMFold | Full 3D structure prediction | Heavier compute; no embedding generation mode |

## Biological Background

### The 3Di Structural Alphabet

The 3Di alphabet, introduced by van Kempen et al. (2023) in Foldseek, encodes the local 3D geometry around each residue using a 20-letter alphabet. Each 3Di token captures:
- Backbone dihedral angles (phi, psi, omega)
- Relative orientations of adjacent residues
- Local structural context (secondary structure, loop geometry)

The 20 3Di states roughly correspond to different local structural environments: alpha-helix interior, beta-strand, various turn types, and loop conformations. Two proteins with identical 3Di sequences share very similar local structures throughout their chains.

### Protein Structure-Sequence Relationships

The relationship between amino acid sequence and protein structure is many-to-many:
- **Forward folding**: One sequence typically folds into one dominant structure (with thermal fluctuations)
- **Inverse folding**: Many different sequences can adopt the same 3D structure

ProstT5 captures this asymmetry: AA->3Di translation is relatively accurate (the structure is largely determined by the sequence), while 3Di->AA translation is inherently stochastic (many sequences are compatible with a given structure). The generation parameters (temperature, top_k, top_p) control the diversity of the generated sequences.

### Applications of Structural Alphabets in Bioinformatics

Structural alphabets enable treating structure comparison as a sequence comparison problem, which is dramatically faster. Applications include:
- **Foldseek**: Structural database search in seconds (vs hours for coordinate-based methods)
- **Fold classification**: Assigning proteins to structural families using sequence alignment tools
- **Structural clustering**: Grouping proteins by structural similarity at genome/metagenome scale
- **Structure-conditioned generation**: Designing proteins with desired structural properties

ProstT5 extends these applications by providing a neural model that can translate between the two languages, enabling structure-aware protein understanding without explicit 3D coordinates.

---

*See also: [README.md](README.md) for API reference | [MODEL.md](MODEL.md) for technical details*
