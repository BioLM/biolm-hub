# AntiFold  --  Biological Context

## Molecule Coverage

### Primary Molecule Type(s)

AntiFold is designed for **antibody** and **nanobody** structures. Specifically:

- **Conventional antibodies**: Paired heavy chain (VH) and light chain (VL) variable regions
- **Nanobodies**: Single-domain antibodies (VHH) derived from camelid heavy-chain-only antibodies
- **Antibody-antigen complexes**: When antigen structure is available, it can be included as context

The model operates on 3D structures in PDB format and uses IMGT numbering to identify CDR and framework regions. It is trained on structures from the Structural Antibody Database (SAbDab), which predominantly contains crystallographic structures of human and mouse antibodies, with some representation from other species.

**Important coverage notes:**
- Works best on structures with standard IMGT numbering
- Handles both paired (VH/VL) and unpaired (VH-only or VHH) formats
- Antigen chain inclusion is optional but improves context-aware design
- Not designed for constant region (Fc) engineering -- only variable domains

### Cross-Applicability

| Molecule Type | Applicability | Evidence | Caveats |
|--------------|---------------|----------|---------|
| Conventional antibodies (VH/VL) | High | Primary training target | Requires PDB structure input |
| Nanobodies (VHH) | High | Explicitly supported with dedicated chain mode | Smaller training set than conventional antibodies |
| T-cell receptors (TCRs) | Low | Not trained on TCR structures | Structural similarities exist but CDR definitions differ |
| General proteins | Not applicable | Model is antibody-specific | Use ESM-IF1 or ProteinMPNN instead |
| Peptides | Not applicable | Too short for meaningful inverse folding | Not relevant |

## Biological Problems Addressed

### Antibody CDR Optimization

**Biological context**: Complementarity-Determining Regions (CDRs) are the hypervariable loops of antibodies that directly contact antigens. Optimizing CDR sequences while maintaining the structural fold is central to improving antibody affinity, specificity, and developability. Experimentally, this requires constructing and screening large combinatorial libraries, which is expensive and time-consuming.

**How AntiFold helps**: Given a known antibody structure (e.g., from X-ray crystallography or computational modeling), AntiFold can propose alternative CDR sequences that are compatible with the observed backbone conformation. Users can target specific CDRs (e.g., CDRH3 only, or all CDRs simultaneously) and control sequence diversity via sampling temperature. The model outputs multiple candidate sequences ranked by global score, allowing prioritization for experimental testing.

**Output interpretation**: The `global_score` reflects the overall log-likelihood of the designed sequence given the structure. Higher (less negative) scores indicate better structural compatibility. The `seq_recovery` metric shows what fraction of positions match the wild-type sequence, and `mutations` counts the number of changed positions.

### Antibody Humanization

**Biological context**: Therapeutic antibodies often originate from non-human species (typically mouse). To reduce immunogenicity in human patients, the antibody framework regions must be humanized -- replaced with human-like sequences -- while preserving the antigen-binding CDRs. Traditional humanization requires expert knowledge and iterative experimental validation.

**How AntiFold helps**: By conditioning on the antibody backbone structure, AntiFold can suggest framework sequences that are structurally compatible with the existing CDR conformations. Users can restrict redesign to framework regions only (FWH, FWL, or specific frameworks like FWH1-FWH4) while keeping CDR sequences fixed. This provides a structure-informed starting point for humanization that preserves the geometric constraints needed for antigen binding.

### Antibody Sequence Liability Assessment

**Biological context**: Certain amino acid motifs in antibodies are associated with manufacturing or clinical liabilities, such as deamidation (NG motifs), oxidation (exposed methionine), or aggregation-prone hydrophobic patches. Identifying and removing these liabilities while maintaining function is a key step in antibody developability assessment.

**How AntiFold helps**: The `score` action evaluates how well the current sequence fits the observed structure, providing a global compatibility score. The `log_prob` action gives a per-structure log-probability that can be used to compare wild-type versus engineered variants. Positions with low per-residue log-probabilities may indicate residues that are structurally strained and could be targets for optimization.

### Structure-Based Antibody Library Design

**Biological context**: Synthetic antibody libraries are widely used in phage display, yeast display, and other selection platforms. Designing libraries with high functional diversity while maintaining structural integrity requires balancing sequence variation with fold stability.

**How AntiFold helps**: The `generate` action can produce large numbers (up to 50,000 per request) of structure-compatible sequences across specified regions. By using the `regions` parameter to target specific CDRs and adjusting `sampling_temp` to control diversity, users can design focused libraries enriched for sequences that are compatible with the target backbone conformation. The `limit_expected_variation` option further constrains sampling to the natural range of variation observed in known antibody structures.

## Applied Use Cases

Since its publication in 2024, AntiFold has been evaluated in several applied and benchmark studies:

- **CDR benchmark (PLoS ONE 2025)** — Li et al. (BioMap Research) benchmarked AntiFold against ProteinMPNN, ESM-IF, and LM-Design on Fab and VHH CDR sequence recovery tasks, finding AntiFold superior for conventional Fab antibody design. (DOI: 10.1371/journal.pone.0324566)

- **Computational antibody design pipeline (Nature 2025)** — Demonstrated in the RFdiffusion antibody paper (Bennett et al.) as part of a multi-stage pipeline where inverse folding tools including AntiFold are used for CDR sequence optimization after backbone diffusion. (DOI: 10.1038/s41586-025-09721-5)

- **Binding affinity maturation benchmark (AbBiBench 2025)** — Benchmarked AntiFold alongside 14 other protein models on 184,500+ experimental antibody-antigen binding measurements. Inverse folding models as a class outperformed all other model categories, though AntiFold showed a small correlation drop versus ESM-IF in the complex-level binding prediction setting, suggesting some trade-offs from antibody-specific fine-tuning. (arXiv: 2506.04235)

- **nanoFOLD comparison (bioRxiv 2025)** — A nanobody-specific inverse folding model (nanoFOLD) fine-tuned from ESM-IF was benchmarked directly against AntiFold on VHH sequence recovery and binder enrichment. nanoFOLD outperforms AntiFold on nanobody-specific tasks (75% VHH recovery vs AntiFold), while AntiFold retains superiority on Fab antibody design, quantifying the domain-specificity trade-off. (DOI: 10.1101/2025.04.29.651236)

- **GPCR-peptide drug discovery benchmark (Briefings in Bioinformatics 2025)** — Contextualizes antibody-specific inverse folding tools (including AntiFold) in the broader landscape of structure prediction and sequence design for drug discovery. (DOI: 10.1093/bib/bbaf186)

## Related Models

### Predecessor Models

- **ESM-IF1** (Hsu et al., 2022): The general-purpose inverse folding model that AntiFold is built upon. ESM-IF1 uses a GNN encoder to process backbone coordinates and an autoregressive decoder for sequence generation. It was trained on CATH 4.3 structures covering diverse protein folds. AntiFold fine-tunes ESM-IF1 specifically for antibody structures, yielding significant improvements in CDR sequence recovery.

### Complementary Models

AntiFold works well in combination with other models on the BioLM platform:

- **Structure prediction models** (e.g., ABodyBuilder3, ESMFold): Generate the input 3D structure needed by AntiFold when an experimental structure is unavailable. Pipeline: predict structure with ABodyBuilder3, then design sequences with AntiFold.
- **Protein language models** (e.g., ESM2): Use ESM2 pseudo-log-likelihoods to independently score AntiFold-designed sequences for general protein fitness.

### Alternative Models

| Alternative | Advantage over AntiFold | Disadvantage vs AntiFold |
|-------------|------------------------|--------------------------|
| ESM-IF1 | Handles any protein, not just antibodies | Lower CDR recovery rates on antibodies |
| ProteinMPNN | Well-validated, handles multi-chain complexes | Not antibody-specialized, no IMGT-aware regions |
| AbLang / IgBert | Sequence-only input (no structure needed) | Cannot condition on 3D structure |

## Biological Background

### Antibody Structure

Antibodies (immunoglobulins) are Y-shaped proteins produced by B cells of the immune system. Each antibody consists of two heavy chains and two light chains linked by disulfide bonds. The antigen-binding site is formed by the variable domains of the heavy chain (VH) and light chain (VL).

**Variable domain architecture:**

```
Variable Domain (VH or VL)
  |-- Framework Region 1 (FR1/FW1)
  |-- CDR1 (Complementarity-Determining Region 1)
  |-- Framework Region 2 (FR2/FW2)
  |-- CDR2
  |-- Framework Region 3 (FR3/FW3)
  |-- CDR3
  |-- Framework Region 4 (FR4/FW4)
```

- **Framework regions (FR/FW)**: Structurally conserved beta-sheet scaffold that maintains the immunoglobulin fold. Relatively tolerant of sequence variation within the same germline family.
- **CDRs**: Hypervariable loops that protrude from the framework scaffold and make direct contact with the antigen. CDR-H3 (the third CDR of the heavy chain) is the most diverse in both sequence and structure, and is often the primary determinant of antigen specificity.

### IMGT Numbering

The IMGT (ImMunoGeneTics) numbering system provides a standardized way to number antibody residues across different species and germlines. It assigns fixed position numbers to framework and CDR residues, enabling consistent identification of equivalent positions across different antibodies. AntiFold uses IMGT numbering internally to define regions for targeted sequence design.

### Nanobodies

Nanobodies (VHH domains) are single-domain antibodies derived from the heavy-chain-only antibodies found in camelids (llamas, camels, alpacas). They lack a light chain entirely, relying on an extended CDR-H3 loop and adapted framework residues to achieve antigen binding. Nanobodies are smaller (~15 kDa vs ~50 kDa for conventional Fab), more stable, and easier to produce, making them attractive for therapeutic and diagnostic applications.

### Inverse Folding

Inverse folding is the computational problem of predicting which amino acid sequences are compatible with a given 3D backbone structure. It is the inverse of the protein folding problem (which predicts structure from sequence). In the context of antibody engineering, inverse folding enables structure-based sequence design: given a desired CDR loop conformation, what sequences will adopt that conformation?

This approach is particularly valuable for:
- **Affinity maturation**: Proposing mutations in CDRs that maintain the binding geometry
- **Stability engineering**: Identifying framework mutations that reinforce the immunoglobulin fold
- **Library design**: Generating diverse but structurally viable sequence candidates for experimental screening

---

*See also: [README.md](README.md) for API reference | [MODEL.md](MODEL.md) for technical details*
