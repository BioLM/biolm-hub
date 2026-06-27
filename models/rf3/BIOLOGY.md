# RosettaFold3 (RF3) -- Biological Context

## Molecule Coverage

### Primary Molecule Type(s)

RosettaFold3 is a general-purpose all-atom biomolecular structure prediction model covering:

- **Proteins**: Single chains and multi-chain complexes, with or without MSA
- **DNA**: Single-stranded and double-stranded DNA
- **RNA**: Single-stranded RNA
- **Small molecule ligands**: Via SMILES strings or Chemical Component Dictionary (CCD) codes
- **Complexes**: Any combination of the above (protein-protein, protein-DNA, protein-RNA, protein-ligand, etc.)

The model also supports cyclic peptides, non-canonical amino acids (via CCD codes), and covalent modifications. Template structures can be provided to condition predictions on partial experimental data.

### Cross-Applicability

| Molecule Type | Applicability | Evidence | Caveats |
|--------------|---------------|----------|---------|
| Protein monomers | High | Primary training target | MSA improves accuracy |
| Protein-protein complexes | High | Multi-chain support | Large complexes may exceed memory |
| Antibodies | Moderate | Handles as general proteins | Specialized models (ImmuneFold) may be more accurate for CDR loops |
| Protein-ligand complexes | High | SMILES/CCD input for ligands | Improved chiral ligand handling over RF2 |
| Protein-DNA complexes | High | DNA sequence input supported | Less validated than protein-only |
| Protein-RNA complexes | High | RNA sequence input supported | Less validated than protein-only |
| Cyclic peptides | Moderate | Via `cyclic_chains` parameter | Specialized feature |
| Small molecules alone | Low | Designed for biomolecular context | Use RDKit/molecular docking for small molecules alone |

## Biological Problems Addressed

### Protein Structure Prediction

**Biological context**: Knowing the 3D structure of a protein is fundamental to understanding its function, designing drugs that target it, and engineering proteins with desired properties. Experimental methods (X-ray crystallography, cryo-EM, NMR) are slow and expensive, while computational prediction from sequence enables rapid structural characterization.

**How RF3 helps**: RF3 predicts full-atom protein structures from amino acid sequences, optionally enhanced with MSA information. The diffusion-based approach generates multiple diverse conformations, allowing exploration of conformational space rather than producing a single point estimate. Confidence metrics (pTM, pLDDT) enable quality assessment.

**Output interpretation**: Each output is an mmCIF structure file with associated confidence scores. `ptm` indicates global fold confidence (>0.7 is generally reliable). `plddt` per-residue scores identify confident vs uncertain regions. Multiple samples from diffusion allow selection of the best structure via `ranking_score`.

### Multi-Component Complex Prediction

**Biological context**: Most biological processes involve interactions between multiple molecules -- protein-protein signaling, transcription factor-DNA binding, ribosome-mRNA interactions, enzyme-substrate complexes. Understanding these interactions at atomic resolution is critical for drug design and mechanistic biology.

**How RF3 helps**: RF3 natively handles multi-component inputs: users specify each molecular entity (protein chain, DNA strand, RNA strand, or ligand) as a named component, and RF3 predicts the full complex structure including inter-molecular interfaces. The `iptm` (interface pTM) score specifically evaluates the quality of predicted interfaces.

### Protein-Ligand Docking

**Biological context**: Drug discovery requires predicting how small molecules bind to protein targets. Accurate binding pose prediction enables virtual screening, lead optimization, and understanding of drug resistance mechanisms.

**How RF3 helps**: Ligands can be specified via SMILES strings or CCD codes as input components alongside protein sequences. RF3 jointly predicts protein structure and ligand binding pose. Template conditioning via `ground_truth_conformer_selection` can fix the ligand conformation while folding the protein around it.

### Template-Guided Structure Prediction

**Biological context**: In many scenarios, partial structural information is available -- an experimental structure of a homolog, a known domain fold, or crystallographic data for part of a complex. Incorporating this information improves prediction accuracy.

**How RF3 helps**: The `template_selection` parameter allows users to specify which parts of the input should be treated as structural templates. RF3 conditions its prediction on these templates while freely predicting the remaining structure. This is valuable for:
- Homology-guided folding
- Loop prediction with known framework
- Complex prediction with known subunit structures

## Applied Use Cases

### Published Applications

RF3 is based on the foundry framework from RosettaCommons. Published and anticipated use cases include:

- **Structure-based drug design**: Predicting protein-ligand complex structures for virtual screening
- **Antibody-antigen complex modeling**: Predicting binding interfaces for therapeutic antibody development
- **Protein engineering**: Understanding structure-function relationships for directed evolution
- **Nucleic acid-protein interactions**: Predicting transcription factor-DNA binding for gene regulation studies

<!-- TODO: Add specific applied literature citations from post-publication studies -->

### Anticipated Use Cases

- **Cryo-EM model building**: Using RF3 predictions as starting models for cryo-EM refinement
- **Allosteric mechanism discovery**: Sampling multiple conformations via diffusion to identify allosteric states
- **Multi-drug resistance prediction**: Modeling how mutations affect drug binding

## Related Models

### Predecessor Models

- **RosettaFold2** (Baek et al., 2023): The previous generation from the Baker Lab, which RF3 improves upon with diffusion-based sampling and better ligand handling.
- **AlphaFold2** (Jumper et al., 2021): The landmark structure prediction model that RF-series models build upon and compete with.

### Complementary Models

- **ESM2**: Provides protein language model embeddings that can be used independently of structure prediction for sequence fitness assessment.
- **Boltz**: Alternative open-source structure prediction that can serve as a cross-validation for RF3 predictions.
- **ProperMAB**: Can use RF3-predicted antibody structures for extracting developability features (though ProperMAB uses ABodyBuilder2 internally).

### Alternative Models

| Alternative | Advantage over RF3 | Disadvantage vs RF3 |
|-------------|---------------------|---------------------|
| AlphaFold2/3 | Higher accuracy on some single-chain benchmarks | Closed-source (AF3); no diffusion sampling (AF2) |
| Boltz | Similar AF3-like architecture; open-source | May not handle templates/cyclic peptides as well |
| Chai-1 | Multi-modal; commercially supported | Different licensing terms |
| ESMFold | Much faster; no MSA needed | Single-chain only; lower accuracy on multi-chain |

## Biological Background

### Protein Folding Problem

The protein folding problem -- predicting 3D structure from amino acid sequence -- was considered one of biology's grand challenges for over 50 years. AlphaFold2's breakthrough in 2020 demonstrated that deep learning could achieve experimental-level accuracy. RF3 builds on this foundation with additional capabilities for multi-molecular complexes and diffusion-based sampling.

### Diffusion Models for Structure Prediction

RF3 uses a diffusion-based approach for structure generation. In the forward process, atomic coordinates are progressively corrupted with noise. The model learns to reverse this process -- given noisy coordinates, it predicts the denoising step that recovers the true structure. This approach has several advantages:

- **Multiple samples**: Each denoising trajectory produces a different structure, enabling exploration of conformational space
- **Confidence-aware**: The model can identify low-confidence predictions early and stop
- **Diverse outputs**: Different random seeds produce structurally diverse predictions that can be ranked by confidence

### Multiple Sequence Alignments (MSAs)

MSAs are collections of evolutionarily related sequences aligned to a query. Co-evolutionary patterns in MSAs encode 3D contact information: residue pairs that co-evolve tend to be spatially close in the folded structure. Providing MSAs significantly improves prediction accuracy, especially for proteins with many homologs. RF3 supports MSAs in A3M format from databases including UniRef90, MGnify, and Small BFD.

### Confidence Metrics

RF3 provides several confidence measures:
- **pTM (predicted TM-score)**: Global structural similarity metric, 0--1. Values >0.7 generally indicate reliable folds.
- **ipTM (interface pTM)**: Evaluates the quality of inter-chain interfaces in multi-chain predictions.
- **pLDDT (predicted LDDT)**: Per-residue confidence, 0--100. Values >90 indicate very high confidence.
- **PAE (Predicted Aligned Error)**: Per-residue-pair distance error matrix, indicating relative positioning confidence.
- **Ranking score**: Composite score: 0.8 * ipTM + 0.2 * pTM - 100 * has_clash.

---

*See also: [README.md](README.md) for API reference | [MODEL.md](MODEL.md) for technical details*
