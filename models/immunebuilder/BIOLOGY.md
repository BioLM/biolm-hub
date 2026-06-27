# ImmuneBuilder -- Biological Context

## Molecule Coverage

### Primary Molecule Type(s)

ImmuneBuilder is designed for the three major classes of adaptive immune receptor proteins:

- **Conventional antibodies**: Paired heavy chain (VH) and light chain (VL) variable regions. Predicted by ABodyBuilder2.
- **Nanobodies**: Single-domain antibodies (VHH) from camelid heavy-chain-only antibodies. Predicted by NanoBodyBuilder2.
- **T-cell receptors (TCRs)**: Paired alpha and beta chain variable regions. Predicted by TCRBuilder2 and TCRBuilder2Plus.

All sub-models operate on amino acid sequences and produce full-atom 3D structures in PDB format. No MSA or template structure is required -- predictions are single-sequence.

### Cross-Applicability

| Molecule Type | Applicability | Evidence | Caveats |
|--------------|---------------|----------|---------|
| Conventional antibodies (VH/VL) | High | Primary target of ABodyBuilder2 | Requires both H and L chain sequences |
| Nanobodies (VHH) | High | Dedicated NanoBodyBuilder2 sub-model | H chain only input |
| Alpha/beta TCRs | High | Dedicated TCRBuilder2/TCRBuilder2Plus sub-models | Requires both A and B chain sequences |
| Gamma/delta TCRs | Low | Not specifically trained | Structural differences from alpha/beta |
| General proteins | Not applicable | Model is immune-protein-specific | Use AlphaFold2 or ESMFold instead |
| Antibody-antigen complexes | Not applicable | Does not model antigen binding | Use ImmuneFold or AlphaFold2 Multimer |

## Biological Problems Addressed

### Antibody Structure Prediction

**Biological context**: Knowing the 3D structure of an antibody, particularly the conformation of its CDR loops, is essential for understanding antigen binding, performing structure-based design, and assessing developability. Experimental structure determination by X-ray crystallography or cryo-EM is slow and expensive. Computational prediction from sequence alone enables rapid structural characterization of antibody candidates.

**How ImmuneBuilder helps**: ABodyBuilder2 takes paired VH/VL sequences and predicts the full 3D structure including all CDR loops. The EGNN ensemble captures the geometric constraints of the immunoglobulin fold, and OpenMM relaxation ensures physically realistic bond geometries. This enables rapid structural characterization of antibody candidates from sequencing data alone.

**Output interpretation**: The output PDB file contains atomic coordinates for all heavy atoms. The structure can be used for downstream analysis such as paratope identification, epitope prediction, docking, or feature extraction (e.g., with ProperMAB).

### Nanobody Structure Prediction

**Biological context**: Nanobodies are emerging as therapeutic and diagnostic reagents due to their small size (~15 kDa), high stability, and ease of production. Their CDR3 loops tend to be longer and more structurally diverse than conventional antibodies, making structure prediction challenging.

**How ImmuneBuilder helps**: NanoBodyBuilder2 is specifically trained on VHH structures from SAbDab, accounting for the unique structural features of nanobodies including extended CDR3 loops and adapted framework residues that compensate for the absence of a light chain.

### TCR Structure Prediction

**Biological context**: T-cell receptors recognize peptide-MHC complexes and are central to adaptive immunity, cancer immunotherapy (e.g., TCR-T cell therapy), and autoimmune disease. Structural knowledge of TCRs is critical for understanding antigen recognition specificity and designing engineered TCR therapeutics.

**How ImmuneBuilder helps**: TCRBuilder2 and TCRBuilder2Plus predict alpha/beta TCR structures from paired chain sequences. TCRBuilder2Plus uses updated weights trained on an expanded structural database for improved accuracy. These predictions enable rational TCR engineering and binding mode analysis.

## Applied Use Cases

ImmuneBuilder addresses computational structure prediction for immune proteins. Key published and anticipated use cases include:

- **Antibody discovery pipelines**: Rapid structural characterization of candidates from NGS sequencing campaigns
- **Structure-based antibody design**: Providing input structures for inverse folding (e.g., AntiFold) or feature extraction (e.g., ProperMAB)
- **TCR-pMHC interaction modeling**: Predicting TCR structures for docking studies with peptide-MHC complexes
- **Nanobody engineering**: Structural assessment of nanobody libraries for CDR loop optimization

<!-- TODO: Add specific applied literature citations as they become available -->

## Related Models

### Predecessor Models

- **ABodyBuilder** (Leem et al., 2016): The original antibody structure prediction tool that ImmuneBuilder extends. Used homology modeling and loop prediction rather than deep learning.
- **ABlooper** (Abanades et al., 2022): CDR loop-only predictor from the same group, which informed the EGNN approach used in ImmuneBuilder.

### Complementary Models

- **ProperMAB**: Uses ABodyBuilder2 structures as input for extracting 34 biophysical developability features. Pipeline: ImmuneBuilder -> ProperMAB.
- **AntiFold**: Antibody inverse folding model that requires 3D structures. ImmuneBuilder can provide predicted structures when experimental structures are unavailable.
- **ESM2**: Protein language model embeddings can complement ImmuneBuilder structures for sequence fitness assessment.

### Alternative Models

| Alternative | Advantage over ImmuneBuilder | Disadvantage vs ImmuneBuilder |
|-------------|------------------------------|-------------------------------|
| ImmuneFold | PLM-enhanced; higher accuracy on some targets | Larger model; requires GPU |
| AlphaFold2 | Handles any protein; MSA-enhanced accuracy | Slower; requires MSA; not immune-specialized |
| ESMFold | Very fast single-sequence prediction | Not immune-protein-specialized |

## Biological Background

### Adaptive Immune Receptors

The adaptive immune system relies on two classes of antigen receptors: antibodies (produced by B cells) and T-cell receptors (produced by T cells). Both use a similar structural framework -- the immunoglobulin fold -- but recognize antigens through different mechanisms:

- **Antibodies**: Bind soluble or cell-surface antigens directly via CDR loops in VH/VL variable domains
- **TCRs**: Recognize processed peptide fragments presented by MHC molecules on cell surfaces

### Immunoglobulin Fold

The immunoglobulin fold is a conserved structural motif consisting of two beta-sheets packed face-to-face, stabilized by a conserved disulfide bond. Both antibody variable domains (VH, VL) and TCR variable domains (V-alpha, V-beta) adopt this fold. The CDR loops emerge from one end of the beta-sandwich and form the antigen-binding surface.

```
Variable Domain Structure:
  |-- Framework Region 1 (FR1)   -- beta-strand
  |-- CDR1                       -- loop
  |-- Framework Region 2 (FR2)   -- beta-strand
  |-- CDR2                       -- loop
  |-- Framework Region 3 (FR3)   -- beta-strand
  |-- CDR3                       -- loop (most variable)
  |-- Framework Region 4 (FR4)   -- beta-strand
```

### CDR Loop Diversity

CDR3, particularly CDR-H3 in antibodies and CDR3-beta in TCRs, is the most structurally diverse loop. It is generated by V(D)J recombination with junctional diversity and is the primary determinant of antigen specificity. Predicting CDR3 conformation is the hardest part of immune protein structure prediction and is where specialized models like ImmuneBuilder provide the greatest advantage over general-purpose predictors.

### Nanobodies vs Conventional Antibodies

Nanobodies (VHH) lack a light chain entirely, relying on:
- Extended CDR-H3 loops (often 15-25+ residues) that provide a large binding surface
- Adapted framework residues at positions that would normally contact VL
- Higher thermal stability and solubility than conventional antibody fragments

These structural differences necessitate a dedicated prediction model (NanoBodyBuilder2) rather than using the conventional antibody predictor.

---

*See also: [README.md](README.md) for API reference | [MODEL.md](MODEL.md) for technical details*
