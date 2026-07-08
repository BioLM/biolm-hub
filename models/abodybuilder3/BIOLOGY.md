# AbodyBuilder3 -- Biological Context

## Molecule Coverage

### Primary Molecule Type(s)

AbodyBuilder3 is designed for **antibody** Fv (variable fragment) structures. It takes paired heavy chain (VH) and light chain (VL) amino acid sequences as input and predicts the 3D atomic coordinates of the Fv region.

**Important coverage notes:**
- Requires both heavy and light chain sequences (paired input)
- Predicts the Fv region only, not constant domains (CH1, CL, Fc)
- Does not support nanobodies (VHH) or single-chain inputs
- Does not predict antibody-antigen complex structures

### Cross-Applicability

| Molecule Type | Applicability | Evidence | Caveats |
|--------------|---------------|----------|---------|
| Conventional antibodies (VH/VL) | High | Primary training target (SAbDab structures) | Fv region only |
| Nanobodies (VHH) | Not applicable | Requires paired heavy/light input | Use alternative structure predictors |
| Fab fragments | Partial | Predicts Fv portion only | Constant domains not modeled |
| T-cell receptors (TCRs) | Low | Not trained on TCR structures | Structural similarity exists but untested |
| General proteins | Not applicable | Antibody-specific architecture | Use ESMFold, Chai-1, or AlphaFold2 |

## Biological Problems Addressed

### Antibody Structure Prediction (Published)

**Biological context**: Understanding the 3D structure of an antibody is critical for rational engineering of binding affinity, specificity, and developability. Experimental structure determination by X-ray crystallography or cryo-EM is expensive and slow (months per structure). Computational structure prediction enables rapid hypothesis generation and design iteration.

The most challenging aspect of antibody structure prediction is the CDR-H3 loop, which is the most diverse in both sequence and structure among all antibody regions. CDR-H3 is often the primary determinant of antigen specificity, and its conformation cannot be reliably predicted from sequence templates alone.

**How AbodyBuilder3 helps**: Given paired heavy and light chain sequences, AbodyBuilder3 predicts the full Fv backbone and side-chain coordinates. The language variant leverages ProtT5 protein language model embeddings for enhanced accuracy, particularly in the CDR regions. The output is a standard PDB file that can be directly used for downstream structure-based analysis and design.

**Output interpretation**: The PDB output contains predicted atom coordinates with standard chain and residue labeling. When pLDDT scores are requested, per-residue confidence values (0--100 scale) indicate the model's confidence in each position. Regions with pLDDT > 70 are generally reliable; regions below 50 should be interpreted with caution, particularly in the CDR-H3 loop.

### Structure-Based Antibody Engineering (Published)

**Biological context**: Many antibody engineering tasks -- including CDR grafting, humanization, affinity maturation, and developability optimization -- benefit from structural information. Knowing the spatial arrangement of CDR loops relative to the framework scaffold guides the selection of mutations that improve function without destabilizing the fold.

**How AbodyBuilder3 helps**: Predicted structures serve as input for structure-based design tools (e.g., AntiFold for inverse folding, molecular docking for binding prediction). Having rapid access to antibody structures enables high-throughput structure-based screening of antibody libraries.

### Virtual Antibody Library Characterization (Anticipated)

**Biological context**: Antibody discovery campaigns produce large sequence libraries from phage display, yeast display, or B-cell sequencing. Understanding the structural diversity of these libraries -- particularly the CDR loop conformations -- helps assess library quality and guide selection strategies.

**How AbodyBuilder3 helps**: The fast inference speed enables structure prediction for hundreds or thousands of antibody sequences, providing structural annotations at library scale. This can reveal CDR-H3 loop conformation clusters, identify structurally redundant candidates, and prioritize structurally diverse subsets for experimental characterization. However, this application has not yet been validated at scale.

## Applied Use Cases

AbodyBuilder3 was published in 2024. The following applied literature benchmarks or builds on this model:

- **Dreyer et al. (mAbs, 2025)** — Ibex (Prescient Design/Genentech) benchmarks ABodyBuilder3 head-to-head on the ImmuneBuilder test set; reports CDR H3 backbone RMSD of 2.86 Å, CDR L3 RMSD of 1.13 Å for ABodyBuilder3.
- **BioGeometry Team (bioRxiv, 2025)** — GeoFlow-V2-ab benchmarks ABodyBuilder3 alongside AlphaFold-Multimer V2.3 on 205 antibody test structures; ABodyBuilder3 serves as the antibody-specific baseline.
- **Ali et al. (bioRxiv, 2025)** — Adopts the ABodyBuilder3 architecture as the foundation for nanobody-specific structure predictors via self-distillation from unlabelled VHH sequences.
- **Ali et al. (bioRxiv, 2026)** — NbForge, a nanobody folding model with blueprint- and disulphide-aware inductive biases, is explicitly described as "derived from ABodyBuilder3/AlphaFold2."

## Related Models

### Predecessor Models

- **AbodyBuilder** (Leem et al., 2016): The original antibody structure prediction tool using homology modeling with SAbDab templates. AbodyBuilder3 replaces the template-based approach with a learned GNN architecture.
- **AbodyBuilder2**: Intermediate version with improved template selection and loop modeling.

### Complementary Models

AbodyBuilder3 works well in combination with other models in this catalog:

- **AntiFold**: For inverse folding on predicted structures. Pipeline: predict structure with AbodyBuilder3, then design sequences with AntiFold.
- **AbLEF**: For sequence-level developability screening. Pipeline: predict structure for visualization, assess developability from sequence with AbLEF.
- **ESM2**: For general protein representation. Embeddings from ESM2 can complement structural information from AbodyBuilder3.

### Alternative Models

| Alternative | Advantage over AbodyBuilder3 | Disadvantage vs AbodyBuilder3 |
|-------------|----------------------------|------------------------------|
| AlphaFold2 (antibody mode) | Higher accuracy, especially CDR-H3 | Much slower, requires MSA |
| IgFold | Antibody-specific, fast | Different accuracy/speed tradeoff |
| ESMFold | General protein coverage | Not antibody-specialized |
| Boltz | State-of-the-art general structure | Slower, designed for complexes |

## Biological Background

### Antibody Structure

Antibodies are Y-shaped proteins with two identical heavy chains and two identical light chains. The antigen-binding site is formed by the variable domains of the heavy chain (VH) and light chain (VL), collectively known as the Fv (variable fragment) region.

**Variable domain architecture:**

```
VH Domain
  |-- Framework 1 (FR1)
  |-- CDR-H1
  |-- Framework 2 (FR2)
  |-- CDR-H2
  |-- Framework 3 (FR3)
  |-- CDR-H3  <-- most variable, hardest to predict
  |-- Framework 4 (FR4)

VL Domain
  |-- Framework 1 (FR1)
  |-- CDR-L1
  |-- Framework 2 (FR2)
  |-- CDR-L2
  |-- Framework 3 (FR3)
  |-- CDR-L3
  |-- Framework 4 (FR4)
```

The framework regions form a conserved beta-sandwich scaffold (immunoglobulin fold), while the CDR loops protrude from this scaffold to form the antigen-binding surface (paratope).

### CDR-H3 Loop Prediction Challenge

CDR-H3 is the most sequence-diverse and structurally variable of all six CDR loops. It is formed by V-D-J recombination with junctional diversity, producing loop lengths ranging from 1 to over 30 residues. Unlike CDR-H1, CDR-H2, and the light chain CDRs, CDR-H3 conformations cannot be reliably predicted from canonical class assignments. This makes CDR-H3 structure prediction the primary benchmark for antibody modeling methods.

### pLDDT Confidence Scores

Predicted Local Distance Difference Test (pLDDT) is a per-residue confidence metric (0--100 scale) that estimates the accuracy of predicted atom positions. Originally introduced with AlphaFold2, pLDDT has become a standard measure for structure prediction confidence. For antibodies, framework regions typically have high pLDDT (>80), while CDR loops -- especially CDR-H3 -- often have lower pLDDT reflecting genuine structural uncertainty.

---

*See also: [README.md](README.md) for API reference | [MODEL.md](MODEL.md) for technical details*
