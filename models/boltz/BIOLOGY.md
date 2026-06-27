# Boltz  --  Biological Context

## Molecule Coverage

### Primary Molecule Type(s)

Boltz is designed for **biomolecular complexes**  --  assemblies of multiple interacting molecules. It handles four entity types:

- **Proteins**: Amino acid sequences from all domains of life. Works best for globular proteins and well-structured domains. Performance is strongest for proteins with homologs in the PDB training set. Supports post-translational modifications (specified via CCD codes) and cyclic chains.
- **DNA**: Nucleotide sequences. Effective for protein-DNA complexes such as transcription factor-DNA interactions. Supports modified bases.
- **RNA**: Nucleotide sequences. Handles protein-RNA complexes, though RNA structure prediction accuracy is generally lower than protein structure prediction across all methods.
- **Ligands**: Small molecules specified as SMILES strings or Chemical Component Dictionary (CCD) codes. Best suited for drug-like molecules under ~500 Da. Affinity prediction (Boltz-2) is most reliable for ligands with fewer than ~56 heavy atoms.

The model operates on complexes of these entity types, predicting the 3D arrangement of all atoms simultaneously. Single-chain prediction is supported but the model's primary strength is in multi-chain/multi-molecule complexes.

**Accuracy depends significantly on MSA availability**: When pre-computed multiple sequence alignments (from UniRef90, MGnify, or Small BFD) are provided, prediction quality improves substantially. Without MSA input ("single-sequence mode"), accuracy decreases  --  particularly for proteins with distant homologs.

### Cross-Applicability

| Molecule Type | Applicability | Evidence | Caveats |
|--------------|---------------|----------|---------|
| Antibodies | High | Protein-protein interfaces are a core capability | CDR loop modeling accuracy varies; does not model glycosylation effects |
| Enzymes | High | Active site geometry well-predicted for known folds | Does not model catalytic mechanisms or transition states |
| Peptides | Moderate | Short sequences accepted (min ~5 residues) | Very short peptides lack structural context; accuracy drops below ~15 residues |
| Membrane proteins | Low-Moderate | Can predict fold but not membrane embedding | Training data under-represents membrane proteins; no lipid bilayer modeling |
| Intrinsically disordered proteins | Low | Produces a single conformation from diffusion sampling | IDPs sample an ensemble of conformations; a single predicted structure is misleading |
| Protein-drug complexes | High (Boltz-2) | Core use case for affinity prediction | Affinity calibration assumes drug-like chemical space |

## Biological Problems Addressed

### Structure Prediction of Biomolecular Complexes

**Biological question**: What is the 3D atomic arrangement of a protein-protein, protein-DNA, protein-RNA, or protein-ligand complex?

Knowing the 3D structure of biomolecular complexes is fundamental to understanding biological function. Experimental methods (X-ray crystallography, cryo-EM, NMR) are expensive, slow, and not always feasible  --  many biologically important complexes resist crystallization or are too dynamic for cryo-EM.

Boltz addresses this by predicting atomic-resolution structures from sequence alone (or sequence + MSA). The output is an mmCIF file containing 3D coordinates for all atoms in the complex, along with confidence scores that indicate prediction reliability:

- **pLDDT** (per-residue): Local structural confidence. Values above 70 indicate confident backbone prediction; above 90 indicates high-confidence side-chain placement.
- **pTM / iptm**: Global and interface predicted TM-scores. Values above 0.5 suggest the overall fold and interface are correct.
- **ipSAE**: A newer interface quality metric (Dunbrack 2025) that addresses limitations of ipTM for multi-chain complexes  --  specifically, ipTM is sensitive to chain length and disordered regions that do not participate in the interaction.

**When to use Boltz for structure prediction**: When you need to model a multi-component complex (protein + ligand, protein + protein, protein + DNA/RNA) and no experimental structure is available. Boltz-2 is preferred over Boltz-1 in all cases.

### Binding Affinity Prediction (Boltz-2)

**Biological question**: How strongly does a small molecule bind to a protein target?

Binding affinity  --  typically measured as IC50, Kd, or Ki  --  determines whether a drug candidate will be effective at therapeutic concentrations. Experimental measurement requires synthesizing compounds and running biochemical assays, which is expensive and slow for large chemical libraries.

Computational approaches fall into two categories:
1. **Physics-based** (FEP, molecular dynamics): Highly accurate but extremely expensive computationally (~hours per compound).
2. **Machine learning**: Fast but historically much less accurate than physics-based methods.

Boltz-2 closes this gap. It predicts binding affinity as log10(IC50) in micromolar units, achieving Pearson correlation of ~0.6 with experimental values on the FEP+ benchmark  --  comparable to Schrodinger's FEP+ at approximately 1000x lower computational cost.

**Output interpretation**:
- `affinity_pred_value`: Predicted log10(IC50) in uM. More negative = stronger binding. Use for ranking compounds in lead optimization.
- `affinity_probability_binary`: Probability [0, 1] that the molecule is a binder. Use for hit discovery / virtual screening to separate binders from non-binders.

**Practical considerations**:
- Affinity predictions are highly stochastic (80%+ variance between runs). Run multiple diffusion samples and use the ensemble average.
- Most reliable for protein targets with drug-like small molecule ligands (MW < 500, < 56 heavy atoms).
- Not validated for RNA/DNA targets.

### Molecular Docking with Pocket Constraints (Boltz-2)

**Biological question**: Where and how does a ligand bind within a known or hypothesized binding pocket?

Traditional molecular docking programs (AutoDock, Glide) search for favorable ligand poses within a defined binding site. Boltz-2 integrates docking into the structure prediction framework via pocket constraints  --  you specify which protein residues define the binding pocket, and the model generates the complex structure with the ligand positioned accordingly.

This is particularly useful when:
- You know the binding site from mutagenesis data, co-crystal structures of related ligands, or computational predictions
- You want to simultaneously refine the protein backbone around the binding site (induced fit)
- You need combined structure + affinity predictions in a single workflow

## Applied Use Cases

### De Novo Binder Design via Model Inversion

**Source**: (2025). "BoltzDesign1: Inverting All-Atom Structure Prediction Model for Generalized Biomolecular Binder Design." *bioRxiv*. [DOI: 10.1101/2025.04.06.647261](https://doi.org/10.1101/2025.04.06.647261)

BoltzDesign1 inverts the Boltz-1 structure prediction model for de novo binder design, targeting metal ions, nucleic acids, and post-translationally modified proteins. This work demonstrates that Boltz's learned representations of biomolecular interactions can be repurposed for generative design -- extending its utility beyond prediction into the protein engineering space.

### Virtual Screening and Competitive Docking for Drug Discovery

**Source**: (2025). "AI-guided competitive docking for virtual screening and compound efficacy prediction." *bioRxiv*. [DOI: 10.1101/2025.10.28.685112](https://doi.org/10.1101/2025.10.28.685112)

Boltz-1 and Boltz-2 co-folding was applied for competitive docking across 17 protein-ligand benchmark systems for drug discovery. This study validates Boltz's practical applicability to real-world virtual screening campaigns, demonstrating that its combined structure + affinity predictions can guide compound prioritization in lead discovery and optimization workflows.

### Structure Prediction Benchmarking Across Plant Proteomes

**Source**: (2025). "Why do some predicted protein structures fold poorly? Benchmarking AlphaFold, ESMFold, and Boltz in maize." *bioRxiv*. [DOI: 10.1101/2025.07.05.663230](https://doi.org/10.1101/2025.07.05.663230)

Boltz-1 and Boltz-2 were benchmarked alongside AlphaFold2/3 on 417 maize proteins for structure prediction quality. This study provides an independent assessment of Boltz's accuracy on plant proteins -- a domain less represented in typical benchmarks -- and highlights cases where prediction quality varies across structure prediction methods.

### Structural Biology: Complex Assembly Modeling

For researchers studying multi-protein complexes, protein-nucleic acid interactions, or signaling complexes, Boltz predicts the arrangement of all components simultaneously. The ipSAE and ipae confidence metrics help assess which interfaces are well-predicted and which are uncertain.

### Protein Engineering: Interface Design

Boltz can model how mutations at protein-protein or protein-ligand interfaces affect binding geometry. By comparing predicted structures of wild-type and mutant complexes, engineers can identify mutations that strengthen or weaken specific interactions.

## Related Models

### Predecessor Models

- **AlphaFold2**: Revolutionized single-chain protein structure prediction but did not handle complexes natively. Boltz builds on the insight that diffusion-based approaches (pioneered by AlphaFold3) handle multi-molecule complexes naturally.
- **AlphaFold3**: Introduced diffusion-based structure prediction for complexes but is not fully open-source. Boltz-1 was the first open-source model to match its accuracy.

### Complementary Models

| Model | Use with Boltz | Workflow |
|-------|---------------|----------|
| ESM2 | Generate protein embeddings for downstream tasks | Use ESM2 for fast embedding-based screening, Boltz for detailed structural modeling of top candidates |
| ProteinMPNN | Inverse folding / sequence design | Predict structure with Boltz, then design sequences with ProteinMPNN that fold into the same structure |
| MSA generators | Provide MSA input to improve Boltz accuracy | Pre-compute MSAs with MMseqs2/HHblits, pass as `alignment` to Boltz for improved predictions |

### Alternative Models

| Alternative | Advantage over Boltz | Disadvantage vs Boltz |
|-------------|---------------------|-----------------------|
| AlphaFold3 | Potentially higher accuracy on some targets | Not open-source; no affinity prediction |
| Chai-1 | Alternative open architecture | No affinity prediction; no constraint support |
| ESMFold | Much faster inference; no MSA needed | Single-chain only; no ligands, DNA, RNA, or complexes |
| RoseTTAFold All-Atom | Handles small molecules | Less accurate on protein-ligand affinity; no dedicated affinity head |
| FEP+ (Schrodinger) | Slightly higher affinity accuracy | ~1000x slower; requires licenses; physics-based |

## Biological Background

### Biomolecular Structure

Biological function arises from the 3D arrangement of atoms in molecules. Proteins fold into specific shapes determined by their amino acid sequence; these shapes determine what other molecules they can interact with. DNA and RNA adopt double-helical and complex tertiary structures that mediate gene regulation and catalysis. Small molecules (drugs, metabolites, cofactors) bind to proteins and nucleic acids in specific pockets, modulating their function.

**Structure prediction** is the computational problem of determining these 3D arrangements from sequence information alone, bypassing the need for expensive experimental methods. The 2020 breakthrough by AlphaFold2 showed that deep learning could predict protein structures with near-experimental accuracy. Since then, the field has expanded to predicting multi-molecular complexes and their interaction properties.

### Binding Affinity

When two molecules interact, the strength of their association is quantified as **binding affinity**  --  typically measured as a dissociation constant (Kd) or inhibitory concentration (IC50). Tighter binding (lower Kd / IC50) generally means stronger biological effect.

In drug discovery, predicting binding affinity computationally is one of the most valuable and most difficult problems. A drug must bind its target tightly enough to be effective at safe doses, but not so tightly to related proteins that it causes side effects. The gold standard computational method  --  free-energy perturbation (FEP)  --  requires extensive molecular dynamics simulations costing hours per compound. Boltz-2 approximates FEP-level accuracy using a learned diffusion model, enabling affinity prediction in minutes rather than hours.

### Interface Quality Metrics

Predicting whether a multi-chain complex prediction is correct requires specialized confidence metrics. Traditional metrics like pLDDT measure local backbone accuracy, while pTM/ipTM assess global fold quality. However, ipTM has known limitations: it is sensitive to total chain length and disordered regions that do not participate in the interaction, producing misleading confidence estimates for complexes with long disordered tails or multi-domain proteins.

The **ipSAE** metric (Dunbrack, 2025) addresses these limitations by filtering to only residue pairs with low predicted aligned error (PAE < 10 angstroms) and using adaptive normalization based on the number of high-confidence interfacial residues. This provides a more reliable assessment of whether a predicted protein-protein or protein-ligand interface is likely to be correct.

---

*See also: [README.md](README.md) for API reference | [MODEL.md](MODEL.md) for technical details*
