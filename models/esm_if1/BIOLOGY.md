# ESM-IF1 -- Biological Context

## Molecule Coverage

### Primary Molecule Type(s)

ESM-IF1 is designed for **proteins** broadly. It performs inverse folding: given a 3D protein backbone structure, it generates amino acid sequences that are predicted to fold into that structure. The model was trained on a diverse set of protein structures spanning the CATH classification hierarchy, augmented with millions of AlphaFold2-predicted structures.

**Important coverage notes:**
- Works on single-chain protein structures
- Multichain backbone support is not yet implemented (raises NotImplementedError)
- Accepts PDB-format structure strings as input
- Handles proteins of varying sizes, though very large structures may cause memory issues
- Not specialized for any particular protein family

### Cross-Applicability

| Molecule Type | Applicability | Evidence | Caveats |
|--------------|---------------|----------|---------|
| Globular proteins | High | Primary training target (CATH structures) | Standard application |
| Enzymes | High | Well-represented in training data | Active site residues may need special attention |
| Membrane proteins | Moderate | Some representation in training data | Transmembrane regions less well-sampled |
| Antibodies | Moderate | General protein coverage | Use AntiFold for antibody-specific inverse folding |
| Disordered regions | Low | Training data is structure-based | Intrinsically disordered regions lack defined backbone |
| Nucleic acid-binding proteins | Moderate | Protein structures included | Does not model nucleic acid interactions |
| Peptides | Low | Very short chains may lack sufficient context | Minimum structural context needed for meaningful results |

## Biological Problems Addressed

### Protein Sequence Design from Structure (Published)

**Biological context**: The inverse protein folding problem asks: given a desired 3D backbone structure, what amino acid sequences will fold into that structure? This is a fundamental problem in computational protein design. The protein structure-function relationship means that the backbone geometry constrains which amino acids are compatible at each position -- buried positions prefer hydrophobic residues, surface positions prefer hydrophilic ones, and specific geometric constraints (hydrogen bonding, salt bridges, steric packing) further narrow the choices.

**How ESM-IF1 helps**: Given a PDB structure, ESM-IF1 generates one or more amino acid sequences that are compatible with the input backbone. The temperature parameter controls the diversity of generated sequences: lower temperatures produce more conservative designs (closer to the native sequence), while higher temperatures explore more diverse sequence space. Each generated sequence includes a recovery rate indicating what fraction of positions match the native sequence.

**Output interpretation**: The `recovery` metric (0.0--1.0) indicates the fraction of positions where the designed sequence matches the native sequence extracted from the PDB. Higher recovery indicates the model "rediscovered" the native solution. For design applications, moderate recovery (0.3--0.6) often represents a good balance between structural compatibility and sequence novelty.

### Protein Engineering and Optimization (Published)

**Biological context**: Protein engineers often need to modify a protein's amino acid sequence while maintaining its 3D fold. Applications include improving thermostability, enhancing catalytic activity, reducing immunogenicity, and optimizing expression. Traditional approaches use directed evolution or rational design based on structural knowledge.

**How ESM-IF1 helps**: By generating multiple sequences compatible with a target backbone structure at different temperatures, ESM-IF1 provides a computationally derived library of structurally compatible variants. Engineers can filter these sequences using additional criteria (conserved active site residues, known beneficial mutations, predicted stability) to identify promising candidates for experimental testing.

### Scaffold-Based Protein Design (Published)

**Biological context**: In de novo protein design, researchers first design or select a backbone scaffold with desired geometry (e.g., a specific binding pocket shape), then need to find amino acid sequences that will realize that backbone. This scaffold-based design approach is central to creating novel enzymes, binding proteins, and biosensors.

**How ESM-IF1 helps**: ESM-IF1 can be applied to computationally designed backbones (not just natural structures) to propose sequences. The model's training on 12M AlphaFold2-predicted structures means it has seen a much wider range of backbone geometries than models trained on experimental structures alone, potentially improving performance on novel scaffold designs.

### Fixed-Backbone Enzyme Design (Anticipated)

**Biological context**: Designing enzymes with novel catalytic activities often starts from an existing enzyme scaffold with a known backbone geometry. The goal is to introduce mutations that create or optimize a catalytic site while maintaining the overall fold.

**How ESM-IF1 helps**: By generating sequences at multiple temperatures, ESM-IF1 can suggest positions where the native amino acid is not strongly preferred by the backbone geometry, indicating positions tolerant to mutation. Conversely, positions with very high native recovery across samples are likely structurally critical and should be preserved. This structural tolerance information can guide enzyme engineering campaigns. However, ESM-IF1 does not explicitly model catalytic function, so designed sequences require additional validation.

## Applied Use Cases

ESM-IF1 has been used in several published protein design studies since its release in 2022. Selected examples:

- **AntiFold** (Høie et al., 2025): Fine-tunes ESM-IF1 on solved and predicted antibody structures to achieve state-of-the-art antibody sequence recovery and refolding, demonstrating ESM-IF1 as a strong backbone for domain-specific inverse folding. (DOI: 10.1093/bioadv/vbae202)
- **Peptide binder design** (Johansson-Åkhe & Wallner, 2023): Combines ESM-IF1 with Foldseek and AlphaFold2 for de novo peptide binder design, showing ESM-IF1 designs successful binders for 6.5% of heteromeric interfaces versus 1.5% for ProteinMPNN. (DOI: 10.1038/s42004-023-01029-7)
- **ProteinBench** (Gao et al., 2024): Comprehensive benchmark evaluating multiple protein design models including ESM-IF1 and ProteinMPNN across inverse folding and structure prediction tasks. (arXiv: 2409.06744)
- **AiCE** (2025): Samples mutations from inverse folding models (including ESM-IF1) with structural and evolutionary constraints; outperforms other AI methods by 36–90% across 60 deep mutational scanning datasets. (DOI: 10.1016/j.cell.2025.06.014)
- **Inverse folding consensus ranking** (2025): Evaluates ESM-IF1 alongside ProteinMPNN, LigandMPNN, CARBonAra, and ProRefiner on 25,716 protein-ligand complexes; consensus-ranked sequences outperform individual models in stability, binding affinity, and structural fidelity. (DOI: 10.1145/3768322.3769031)

## Related Models

### Predecessor Models

- **GVP** (Jing et al., 2021): The Geometric Vector Perceptron framework that ESM-IF1's encoder is built upon. GVP introduced the idea of using equivariant neural networks for processing protein structures.
- **StructGNN** and **GraphTrans**: Earlier structure-based sequence design models that ESM-IF1 outperforms.

### Complementary Models

ESM-IF1 works well in combination with other models on the BioLM platform:

- **Structure prediction models** (ESMFold, Chai-1, AbodyBuilder3): Generate the input 3D structure needed by ESM-IF1 when an experimental structure is unavailable. Pipeline: predict structure, then design sequences with ESM-IF1.
- **Protein language models** (ESM2, ESMC): Score ESM-IF1-designed sequences using pseudo-log-likelihoods or embeddings for additional fitness assessment.
- **Stability predictors** (ThermoMPNN): Estimate stability changes (ddG) for designed sequences.

### Alternative Models

| Alternative | Advantage over ESM-IF1 | Disadvantage vs ESM-IF1 |
|-------------|----------------------|------------------------|
| ProteinMPNN | Slightly higher recovery on experimental structures, multi-chain | Not trained on AlphaFold2 structures |
| AntiFold | Antibody-specialized, CDR-aware | Only works for antibodies |
| LigandMPNN | Handles ligand context | More specialized setup |

## Biological Background

### Inverse Protein Folding

The protein folding problem -- predicting 3D structure from amino acid sequence -- has been revolutionized by AlphaFold2 and related methods. The inverse problem -- predicting sequence from structure -- is equally important for protein design but fundamentally different in nature. While folding maps many sequences to one structure (many-to-one), inverse folding maps one structure to many possible sequences (one-to-many). This degeneracy is biologically meaningful: natural proteins with the same fold often share less than 30% sequence identity, demonstrating that backbone geometry alone vastly under-constrains the sequence.

### Structure-Based Sequence Design

Structure-based sequence design exploits the physical constraints imposed by a protein's 3D backbone geometry on its amino acid sequence. Key principles include:

- **Packing**: Buried positions in the protein core must be filled by residues with compatible van der Waals volumes
- **Electrostatics**: Charged and polar residues at the surface; hydrophobic residues in the core
- **Backbone geometry**: Local backbone angles (phi/psi) constrain which residues can occupy each position
- **Hydrogen bonding**: Secondary structure elements (helices, sheets) require specific backbone hydrogen bonding patterns satisfied by compatible side chains

### Sequence Recovery as a Metric

Sequence recovery -- the fraction of designed positions that match the native sequence -- is the standard benchmark for inverse folding models. Higher recovery indicates the model better captures the sequence-structure relationship. Typical values for state-of-the-art models are 45--55% overall, compared to ~5% expected by random chance (1/20 amino acids). Recovery varies by position type: buried core residues show higher recovery than solvent-exposed positions, reflecting stronger structural constraints on buried residues.

---

*See also: [README.md](README.md) for API reference | [MODEL.md](MODEL.md) for technical details*
