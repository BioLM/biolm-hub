# ImmuneFold -- Biological Context

## Molecule Coverage

### Primary Molecule Type(s)

ImmuneFold is designed for two major classes of adaptive immune receptor proteins:

- **Antibodies**: Paired heavy chain (VH) and light chain (VL) variable regions, single-domain nanobodies (VHH), and antibody-antigen complexes (when antigen PDB is provided)
- **T-cell receptors (TCRs)**: Paired alpha and beta chains, including peptide and MHC context

The model leverages ESM-2 protein language model representations for enhanced accuracy compared to models trained solely on structural data. It outputs full-atom 3D structures in PDB format along with confidence scores (pTM, pLDDT) for quality assessment.

### Cross-Applicability

| Molecule Type | Applicability | Evidence | Caveats |
|--------------|---------------|----------|---------|
| Paired antibodies (VH/VL) | High | Primary training target | VH >= 90 AA, VL >= 85 AA minimum |
| Nanobodies (VHH) | High | Supported via H-only input | Single heavy chain input |
| Antibody-antigen complexes | High | Supported with antigen PDB | Antigen must be provided as PDB string |
| Alpha/beta TCRs | High | Dedicated TCR checkpoint | Requires all 4 chains (B, A, P, M) |
| Gamma/delta TCRs | Low | Not specifically trained | May work but not validated |
| General proteins | Not applicable | Immune-protein-specific | Use AlphaFold2 or ESMFold |

## Biological Problems Addressed

### High-Accuracy Antibody Structure Prediction

**Biological context**: Antibody CDR loops, especially CDR-H3, exhibit extreme structural diversity due to V(D)J recombination and somatic hypermutation. Accurately predicting CDR-H3 conformation is critical for understanding antigen binding, rational affinity maturation, and structure-guided design. While ImmuneBuilder provides useful predictions, PLM-enhanced models capture deeper evolutionary patterns that improve loop prediction.

**How ImmuneFold helps**: By combining ESM-2 3B representations (encoding evolutionary information from 250M protein sequences) with immune-protein-specific structural supervision, ImmuneFold achieves the highest CDR-H3 accuracy among single-sequence methods. The pTM and pLDDT confidence scores allow users to assess prediction reliability and identify regions of uncertainty.

**Output interpretation**: The `ptm` score (0--1) indicates global structural confidence (>0.7 is generally reliable). The `full_plddt` is the mean per-residue confidence. Per-residue `plddt` scores identify which regions are predicted most/least confidently -- typically framework regions score highest and CDR-H3 scores lowest.

### Antibody-Antigen Complex Prediction

**Biological context**: Understanding how an antibody binds its antigen at atomic resolution is essential for epitope mapping, rational design of affinity-matured variants, and predicting cross-reactivity. Experimental complex structures are expensive to obtain.

**How ImmuneFold helps**: When provided with both antibody sequences (H/L) and an antigen PDB structure, ImmuneFold predicts the antibody structure in the context of the antigen interface. This enables structural analysis of the paratope-epitope interaction without requiring an experimental co-crystal structure.

### TCR Structure Prediction for Immunotherapy

**Biological context**: T-cell receptors recognize peptide-MHC complexes and are central to cancer immunotherapy (TCR-T cell therapy, checkpoint inhibitors) and autoimmune disease. Structural knowledge of the TCR-pMHC interface is critical for engineering TCRs with desired specificity and affinity.

**How ImmuneFold helps**: The TCR variant takes four chains as input -- beta (B), alpha (A), peptide (P), and MHC (M) -- and predicts the full complex structure. This enables rapid structural characterization of TCR candidates for therapeutic development.

## Applied Use Cases

ImmuneFold enables computational structure prediction for immune proteins in drug development contexts:

- **Antibody candidate characterization**: Rapid structural assessment of therapeutic antibody candidates from discovery campaigns
- **Epitope mapping**: Predicting antibody-antigen complex structures to identify binding epitopes
- **TCR engineering**: Structural modeling of engineered TCRs for immunotherapy applications
- **Input for downstream tools**: Providing structures for inverse folding (AntiFold) or docking studies

## Related Models

### Predecessor Models

- **ImmuneBuilder** (Abanades et al., 2023): The non-PLM predecessor that uses EGNN ensembles trained directly on structural data. ImmuneFold improves upon ImmuneBuilder by incorporating ESM-2 pre-training, achieving lower RMSD on CDR loops.
- **ABodyBuilder2**: The antibody sub-model within ImmuneBuilder. ImmuneFold's antibody variant is a direct improvement.

### Complementary Models

- **AntiFold**: Inverse folding model that can redesign sequences conditioned on ImmuneFold-predicted structures.
- **ESM2**: The underlying language model used by ImmuneFold; can also provide independent sequence fitness scores.

### Alternative Models

| Alternative | Advantage over ImmuneFold | Disadvantage vs ImmuneFold |
|-------------|---------------------------|----------------------------|
| ImmuneBuilder | CPU-only; faster; lighter | Lower CDR accuracy |
| AlphaFold2 Multimer | MSA-enhanced; handles any complex | Slower; requires MSA; not immune-specialized |
| ESMFold | Much faster; single-sequence | Not immune-specialized; lower accuracy on CDRs |

## Biological Background

### Protein Language Models for Structure Prediction

Protein language models (PLMs) like ESM-2 are trained on millions of protein sequences using masked language modeling objectives, analogous to BERT in natural language processing. Through this training, PLMs learn implicit evolutionary constraints -- which residues co-evolve, which positions tolerate substitutions, and which patterns indicate specific folds. These learned representations encode structural information that can be extracted and used for downstream structure prediction.

ImmuneFold exploits this by using ESM-2 3B (the largest freely available ESM-2 variant) as a feature extractor. The ESM-2 embeddings capture both local secondary structure preferences and long-range contacts that are particularly valuable for predicting CDR loop conformations, where sequence diversity makes purely structural approaches less effective.

### Antibody Variable Domain Architecture

The antibody variable domain consists of:
- **Framework regions (FR1-FR4)**: Structurally conserved beta-sheet scaffold
- **CDR loops (CDR1, CDR2, CDR3)**: Hypervariable loops that form the antigen-binding surface
- **Disulfide bond**: Conserved Cys23-Cys104 (IMGT numbering) stabilizing the immunoglobulin fold

CDR-H3 is generated by V(D)J recombination with N-nucleotide additions, creating extreme length and sequence diversity. This makes CDR-H3 the most challenging region to predict and the area where PLM-enhanced models show the greatest improvement.

### IMGT Numbering and Domain Detection

ImmuneFold uses IMGT-based domain numbering internally to identify framework and CDR boundaries. Sequences that are too short to contain the conserved framework residues required for IMGT numbering (Cys-23, Trp-41, Cys-104, Phe/Trp-118) will fail domain detection. This is why minimum sequence lengths are enforced: VH >= 90 AA, VL >= 85 AA.

---

*See also: [README.md](README.md) for API reference | [MODEL.md](MODEL.md) for technical details*
