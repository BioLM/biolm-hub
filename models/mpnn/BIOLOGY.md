# MPNN (ProteinMPNN / LigandMPNN)  --  Biological Context

## Molecule Coverage

### Primary Molecule Type(s)

MPNN operates on **protein structures** (backbone coordinates in PDB format) and designs amino acid sequences predicted to fold into those structures. It handles:

- **Single-chain proteins**: Monomeric globular proteins, enzymes, binding proteins
- **Multi-chain complexes**: Homo-oligomers and hetero-oligomers; can design specific chains while holding others fixed
- **Protein-ligand complexes** (LigandMPNN): Proteins bound to small-molecule ligands, metal ions, cofactors, nucleic acids, and non-standard residues
- **Membrane proteins**: Both global-label and per-residue membrane-aware variants account for the lipid bilayer environment

The model is trained on structures from the Protein Data Bank covering all domains of life. It performs best on well-resolved structures with clear electron density. Performance degrades for:

- Intrinsically disordered regions (no stable backbone to design against)
- Extremely large proteins (>1024 residues, the sequence length limit)
- Structures with significant conformational flexibility or multiple states

### Cross-Applicability

| Molecule Type | Applicability | Evidence | Caveats |
|--------------|---------------|----------|---------|
| Antibodies | High | LigandMPNN paper (Dauparas et al. 2024) demonstrated atomically accurate de novo antibody design | CDR loops are flexible; consider using RFdiffusion for backbone generation first |
| Nanobodies | High | Single-domain antibody design follows same principles | Same CDR flexibility caveats apply |
| Enzymes | High | Widely used for enzyme design; LigandMPNN handles active-site ligands | Active-site residues should typically be fixed; catalytic geometry is not explicitly optimized |
| Peptides | Moderate | Works for structured peptides (helices, beta-hairpins) | Very short peptides (<20 residues) may lack sufficient structural context |
| Membrane proteins | High | Dedicated membrane-aware variants available | Requires knowledge of which residues are transmembrane-buried vs interface |

## Biological Problems Addressed

### Inverse Folding (Structure-to-Sequence Design)

**The core problem**: Given a desired 3D protein backbone structure, what amino acid sequences will fold into that structure? This is the inverse of the protein folding problem and is fundamental to computational protein design.

**Why it matters**: Designing proteins with specific structures enables:
- Creating novel proteins with desired functions (enzymes, binders, scaffolds)
- Optimizing existing proteins for improved stability, solubility, or expression
- Validating computationally generated backbone structures (e.g., from RFdiffusion or Chroma)

**Traditional approaches**: Rosetta energy-function-based fixed-backbone design, which is slower and achieves lower experimental success rates (~15-30% vs ~70-100% for ProteinMPNN).

**How MPNN addresses it**: The model encodes the backbone structure as a graph and autoregressively samples sequences residue-by-residue, conditioned on the local structural environment. Temperature controls the diversity-confidence tradeoff. Multiple sequences can be sampled and ranked by confidence scores.

**Output interpretation**: Each designed sequence comes with:
- **Overall confidence** (exp of negative cross-entropy loss): higher values indicate the model is more confident the sequence is compatible with the structure
- **Sequence recovery**: fraction of positions matching the native sequence (if applicable)
- **Per-residue log probabilities**: identify which positions the model is most/least confident about

### De Novo Protein Design

**The problem**: Creating entirely new proteins that do not exist in nature but fold into specified structures and perform desired functions.

**Why it matters**: De novo design enables creation of proteins for therapeutic, industrial, and research applications that evolution has not explored.

**Typical pipeline**:
1. **Backbone generation**: Use RFdiffusion, Chroma, or other generative models to create novel backbone structures
2. **Sequence design**: Use ProteinMPNN/LigandMPNN to design sequences for those backbones
3. **Validation**: Use AlphaFold2 or ESMFold to predict whether the designed sequences fold to the intended structure (self-consistency check)
4. **Experimental testing**: Express, purify, and characterize designed proteins

MPNN is the standard tool for step 2 in this pipeline, used extensively by the David Baker lab and the broader protein design community.

### Enzyme Engineering

**The problem**: Designing or redesigning enzyme active sites to catalyze desired reactions, improve catalytic efficiency, or alter substrate specificity.

**How MPNN addresses it**: LigandMPNN can design sequences in the context of bound substrates, transition-state analogs, cofactors, and metal ions. Key workflow:
1. Provide structure with substrate/ligand bound in the active site
2. Fix catalytic residues that must be preserved
3. Let LigandMPNN redesign surrounding residues to optimize packing around the ligand
4. Sample multiple designs and filter by confidence scores

**Caveats**: MPNN optimizes for structural compatibility, not directly for catalytic activity. Transition-state stabilization and dynamic effects require additional computational or experimental screening.

### Protein Stabilization and Solubility Optimization

**The problem**: Many proteins of interest are marginally stable or poorly soluble, limiting their practical utility.

**How MPNN addresses it**: The SolubleMPNN variant is specifically trained to bias designs toward soluble proteins. By redesigning surface residues while fixing the protein core, MPNN can suggest mutations that improve solubility and expression without disrupting the fold. The `fixed_residues` parameter enables selective redesign of only surface positions.

### Membrane Protein Design

**The problem**: Designing proteins that function within lipid bilayer membranes, where the hydrophobic environment imposes distinct sequence constraints compared to soluble proteins.

**How MPNN addresses it**: Two specialized variants handle membrane context:
- **Global membrane MPNN**: Applies a single label (membrane or soluble) to the entire protein, biasing the amino acid distribution accordingly
- **Per-residue membrane MPNN**: Allows specifying which residues are transmembrane-buried vs. at the lipid-water interface, enabling fine-grained control over the hydrophobicity profile

## Applied Use Cases

### De Novo Protein Design with RFdiffusion

**Source**: Watson et al. "De novo design of protein structure and function with RFdiffusion." *Nature* (2023). [DOI](https://doi.org/10.1038/s41586-023-06415-8)

ProteinMPNN is the standard sequence design step in the RFdiffusion pipeline. After RFdiffusion generates novel backbone structures, ProteinMPNN designs 8-48 sequences per backbone, which are then filtered using AlphaFold2 self-consistency. This pipeline has produced hundreds of experimentally validated de novo proteins, including binders, symmetric assemblies, and enzyme scaffolds.

### Atomically Accurate Antibody Design

**Source**: Dauparas et al. "Atomically accurate de novo design of single-domain antibodies." *bioRxiv* (2024). [DOI](https://doi.org/10.1101/2024.03.14.585103)

The LigandMPNN paper demonstrated design of single-domain antibodies (nanobodies) with atomic accuracy, confirmed by X-ray crystallography. The model was used to design CDR loops and framework regions simultaneously, accounting for antigen contacts. This establishes LigandMPNN as a tool for therapeutic antibody design pipelines.

### Broad Experimental Validation

**Source**: Dauparas et al. "Robust deep learning-based protein sequence design using ProteinMPNN." *Science* (2022). [DOI](https://doi.org/10.1126/science.add2187)

The original paper tested ProteinMPNN across 8 diverse protein topologies (including beta-barrels, TIM barrels, and NTF2-like folds). 70-100% of designs expressed as soluble monomers, and X-ray structures confirmed sub-angstrom agreement with design targets. This level of experimental validation is unmatched by prior sequence design methods.

### Protein Expression, Stability, and Function Improvement

**Source**: (2024). "Improving Protein Expression, Stability, and Function with ProteinMPNN." *Journal of the American Chemical Society*. [DOI: 10.1021/jacs.3c10941](https://doi.org/10.1021/jacs.3c10941)

ProteinMPNN was applied to redesign myoglobin and TEV protease, achieving improved expression levels, increased melting temperature (Tm), and enhanced catalytic activity. This study demonstrates ProteinMPNN's practical utility beyond de novo design -- as a tool for optimizing existing proteins for industrial and therapeutic applications.

### Enzyme Stabilization for Directed Evolution

**Source**: (2025). "Computational Stabilization of a Non-Heme Iron Enzyme Enables Efficient Evolution of New Function." *Angewandte Chemie International Edition*. [DOI: 10.1002/anie.202414705](https://doi.org/10.1002/anie.202414705)

ProteinMPNN was used to stabilize Fe(II)/alpha-ketoglutarate-dependent enzymes as a prerequisite for directed evolution, yielding an 80-fold activity increase for a new catalytic function. This work establishes a powerful workflow: use ProteinMPNN to create a thermostable scaffold, then apply directed evolution to evolve new activity on the stabilized background.

### Property-Guided Sequence Generation

**Source**: (2025). "ProteinGuide: On-the-fly property guidance for protein sequence generative models." *arXiv:2505.04823*. [arXiv](https://arxiv.org/abs/2505.04823)

ProteinGuide demonstrated guiding ProteinMPNN generation conditioned on stability, enzyme class, and fold properties without retraining the model. This approach enables multi-objective protein design where ProteinMPNN's inverse folding is steered toward sequences satisfying additional property constraints beyond structural compatibility.

## Related Models

### Predecessor Models

- **Rosetta fixed-backbone design**: The dominant prior method for inverse folding, using physics-based energy functions. ProteinMPNN largely supersedes it for sequence design due to higher success rates and faster speed.
- **StructGNN / GraphTrans**: Earlier GNN-based inverse folding methods that ProteinMPNN outperforms.

### Complementary Models

- **RFdiffusion / Chroma / FrameDiff**: Backbone generation models --- use MPNN downstream to design sequences for generated backbones
- **ESMFold / Chai-1 / AlphaFold2**: Structure prediction models --- use as self-consistency validation (does the designed sequence fold back to the intended structure?)
- **ESM2**: Protein language model --- embeddings can be used to filter/rank MPNN designs by evolutionary plausibility

### Alternative Models

| Alternative | Advantage over MPNN | Disadvantage |
|-------------|---------------------|--------------|
| ESM-IF (Inverse Folding) | Leverages ESM pretraining; handles partial structures | Less experimentally validated; slower |
| Rosetta fixed-backbone | Physics-based; explicit energy terms | Much slower; lower success rates |
| ProteinSolver | Graph-based | Earlier method with less validation |

## Biological Background

**Protein design** is the challenge of creating amino acid sequences that fold into specific three-dimensional structures and perform desired functions. Proteins are linear chains of 20 standard amino acids that fold into complex 3D structures determined by their sequence. The relationship between sequence and structure is encoded by evolution and physics: hydrophobic residues pack into the protein core, polar residues face the solvent, and specific geometric arrangements enable catalysis and molecular recognition.

**Inverse folding** specifically refers to the problem of finding sequences compatible with a given backbone structure. This is distinct from (and complementary to) protein folding, which predicts structure from sequence. While many sequences can fold into the same backbone (the sequence-structure mapping is many-to-one), designing sequences that reliably fold into a target structure requires understanding the statistical patterns that evolution has encoded across millions of protein structures.

**Key terminology**:
- **Backbone**: The repeating N-CA-C-O atoms in a protein chain; defines the overall fold
- **Side chains**: The variable R-groups attached to each CA atom; determine amino acid identity
- **Sequence recovery**: Fraction of designed positions matching the native/wild-type sequence
- **Self-consistency**: When a structure prediction model (AlphaFold2) predicts the designed sequence folds to the target structure
- **Fixed residues**: Positions held constant during design (e.g., catalytic residues)
- **Temperature**: Sampling parameter controlling diversity; lower = more conservative (closer to most-likely), higher = more diverse

---

*See also: [README.md](README.md) for API reference | [MODEL.md](MODEL.md) for technical details*
