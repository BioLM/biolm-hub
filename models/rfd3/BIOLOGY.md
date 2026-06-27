# RFdiffusion3  --  Biological Context

## Molecule Coverage

### Primary Molecule Type(s)

RFdiffusion3 is designed for **de novo biomolecular structure generation** -- creating entirely new protein structures (and multi-molecule complexes) that do not exist in nature. It handles:

- **Proteins**: The primary design target. RFD3 generates all-atom protein structures including backbone and sidechain coordinates for sequences up to 2048 residues. It works best for soluble globular proteins and well-defined structural domains. Performance is strongest for folds represented in the PDB training set, though the model can generate novel topologies.
- **DNA**: Nucleotide components can be included in design tasks, enabling design of protein-DNA complexes where the protein component is generated around a fixed or partially fixed DNA structure.
- **RNA**: Similar to DNA, RNA can be included as a design component for protein-RNA complex design.
- **Ligands**: Small molecules specified as SMILES strings or CCD codes can be fixed during design, enabling creation of proteins that cofold around a specific ligand (e.g., enzyme active site design around a substrate or cofactor).

**Critical distinction**: RFD3 is a **design** model, not a **prediction** model. It creates new structures rather than predicting the native structure of existing sequences. The output is a designed backbone with all-atom coordinates -- not a sequence. Downstream tools (ProteinMPNN, ESM-IF) are needed to design sequences that fold into the generated structures.

### Cross-Applicability

| Molecule Type | Applicability | Evidence | Caveats |
|--------------|---------------|----------|---------|
| Therapeutic proteins | High | Core use case: de novo binder and scaffold design | Designs require experimental validation; success rates vary |
| Antibody scaffolds | High | Binder design mode generates protein binders to any target | Does not model CDR loops specifically; combine with antibody-specific tools |
| Enzymes | High | Motif scaffolding preserves catalytic residues while generating new scaffolds | Does not model catalytic mechanisms; active site geometry must be specified |
| Peptides | Moderate | Short designs possible but limited structural context | Below ~30 residues, structural diversity is limited |
| Vaccine scaffolds | High | Motif scaffolding can present antigenic epitopes on de novo scaffolds | Epitope geometry must be experimentally validated |
| Symmetric assemblies | High | Built-in symmetric design modes (cyclic, dihedral) | Limited to supported symmetry groups (C_n, D_n) |
| Membrane proteins | Low | Training data under-represents membrane proteins | No lipid bilayer modeling; designs may not be stable in membrane |
| Intrinsically disordered proteins | Not applicable | Model generates a single conformation | IDPs require ensemble descriptions |

## Biological Problems Addressed

### De Novo Protein Design

**Biological question**: Can we create entirely new protein structures with desired properties -- folds, binding surfaces, or functional sites -- that do not exist in nature?

Natural proteins have evolved over billions of years for specific biological functions. However, for many engineering applications (therapeutics, biosensors, industrial catalysts), no natural protein has the desired properties. De novo protein design aims to create custom proteins from scratch.

Experimental approaches to protein design are extremely labor-intensive. Computational methods like Rosetta have historically achieved limited success rates (15-30% of designs fold as intended). RFdiffusion changed this landscape by using deep learning to generate protein backbones with dramatically higher success rates.

**How RFD3 addresses this**: Given a desired length (and optionally structural constraints), RFD3 generates complete all-atom protein structures by sampling from a learned distribution of protein-like coordinates. The typical workflow:

1. RFD3 generates a 3D structure (backbone + sidechains)
2. ProteinMPNN designs amino acid sequences predicted to fold into that structure
3. RF3 or AlphaFold2 predicts the structure of the designed sequences (validation)
4. Self-consistency (scTM between designed and predicted structures) indicates designability
5. Top candidates are synthesized and experimentally characterized

**Practical considerations**: Multiple designs should be generated (using different seeds or `diffusion_batch_size > 1`) and filtered by self-consistency. Not all designs will be experimentally viable -- typical success rates for well-constrained design tasks are 30-70%.

### Binder Design

**Biological question**: Can we create a protein that binds specifically and tightly to a given target molecule?

Protein-protein and protein-ligand interactions drive virtually all biological processes. Designing proteins that bind specific targets has applications in:

- **Therapeutics**: Alternatives to antibodies for neutralizing pathogens or modulating signaling
- **Diagnostics**: Biosensors that detect specific analytes
- **Research tools**: Affinity reagents for pulling down protein complexes

Traditional binder design requires extensive computational docking and experimental screening. Antibody discovery via phage display or immunization is effective but time-consuming.

**How RFD3 addresses this**: In binder design mode, RFD3 takes a target structure and generates a new protein designed to form a complementary interface. RFD3 extends beyond protein targets to include DNA, RNA, and small molecule targets -- a significant advance over backbone-only methods.

**Practical considerations**: Binder design typically requires iterating with multiple random seeds and selecting top candidates by interface metrics (predicted binding energy, shape complementarity). Experimental validation through binding assays (SPR, ITC, ELISA) is essential.

### Motif Scaffolding

**Biological question**: Given a set of key functional residues (a "motif"), can we design a stable protein scaffold that positions those residues precisely?

Many protein functions depend on a small number of residues arranged in a specific 3D geometry. Examples include:

- **Enzyme active sites**: Catalytic triads, metal-binding sites, cofactor-binding pockets
- **Receptor binding epitopes**: Antigenic sites that elicit immune responses
- **Protein-protein interaction hotspots**: Key residues that mediate binding specificity

Motif scaffolding fixes the positions of these critical residues and generates a surrounding protein structure that maintains their geometry while providing thermodynamic stability.

**How RFD3 addresses this**: The user provides a structure with fixed residues (specified via contig strings and `fixed_residues`), and RFD3 generates new backbone and sidechain coordinates for the variable regions while preserving the motif geometry. Unindexed motifs (where the exact position in the scaffold is unknown) are also supported.

**Practical considerations**: The contig specification language is powerful but requires careful construction. Fixed residues must have experimentally determined or high-confidence predicted coordinates. Generated scaffolds should be validated by checking that the motif geometry is preserved after sequence design and structure prediction.

### Symmetric Assembly Design

**Biological question**: Can we design protein oligomers with defined symmetry (rings, cages, filaments)?

Many natural protein complexes exhibit symmetry: viral capsids, ferritin cages, bacterial microcompartments. Designed symmetric assemblies have applications in:

- **Drug delivery**: Protein nanocages for encapsulating therapeutic payloads
- **Vaccines**: Nanoparticle scaffolds displaying multiple copies of an antigen
- **Biomaterials**: Self-assembling protein lattices and fibers

**How RFD3 addresses this**: In symmetric design mode, RFD3 generates a single asymmetric unit (monomer) and applies the specified symmetry operations (e.g., C3 for trimers, D2 for tetramers with 222 symmetry) to produce the full oligomer. The diffusion process ensures that inter-subunit interfaces are compatible with the target symmetry.

**Practical considerations**: Symmetric designs have additional failure modes -- the interfaces must be strong enough to drive self-assembly. Experimental characterization by SEC-MALS, native mass spectrometry, or cryo-EM is needed to confirm oligomeric state.

## Applied Use Cases

### Therapeutic Protein Design

**Source**: Watson et al. "De novo design of protein structure and function with RFdiffusion." *Nature* (2023). [DOI](https://doi.org/10.1038/s41586-023-06415-8)

The original RFdiffusion paper demonstrated design of protein binders to therapeutic targets including the SARS-CoV-2 spike protein and influenza hemagglutinin. Designed binders showed nanomolar affinity in experimental binding assays. RFD3 extends this capability to all-atom design, enabling more precise control over binding interfaces.

### Vaccine Scaffold Design

Motif scaffolding has been applied to present conserved viral epitopes on thermostable scaffolds for vaccine development. By fixing the epitope residues and generating diverse scaffolds, researchers can optimize immunogenicity while maintaining structural stability. RFD3's all-atom scaffolding provides higher-fidelity placement of epitope residues compared to backbone-only methods.

### Enzyme Design

Motif scaffolding of catalytic residues enables design of novel enzymes. The fixed residues define the active site geometry (catalytic residues, substrate-binding residues), and the generated scaffold provides a stable framework. RFD3's ligand cofolding capability allows designing enzymes around a specific substrate or cofactor geometry.

## Related Models

### Predecessor Models

- **RFdiffusion (v1)** (Watson et al., Nature 2023): The original backbone-only diffusion model for protein design. Generated backbone coordinates (N, CA, C, O) only -- sidechains and ligands were not modeled. Achieved breakthrough experimental success rates for de novo design. RFD3 builds on this foundation with all-atom generation and multi-molecule support.
- **RoseTTAFold**: The structure prediction model whose architecture underlies both RFdiffusion and RFD3. Provides the three-track (1D/2D/3D) neural network backbone.

### Complementary Models

| Model | Use with RFD3 | Workflow |
|-------|--------------|----------|
| ProteinMPNN | Sequence design for RFD3-generated structures | RFD3 (structure) -> ProteinMPNN (sequence) -> RF3/AF2 (validation) |
| RoseTTAFold3 / AlphaFold2 | Validate designability of RFD3 outputs | Predict structure of designed sequence; compare to RFD3 backbone |
| Boltz | Structure prediction for validation | Alternative validation using Boltz-2 for complexes |
| ESM2 | Embedding analysis of designed sequences | Assess whether designed sequences fall within the natural protein distribution |

### Alternative Models

| Alternative | Advantage over RFD3 | Disadvantage vs RFD3 |
|-------------|---------------------|-----------------------|
| RFdiffusion v1 | Faster; simpler backbone-only output | No all-atom generation; no multi-molecule design |
| Chroma (Generate Biomedicines) | Alternative diffusion architecture | Backbone-only; no ligand or nucleic acid support |
| FrameDiff | SE(3) diffusion on frames | Backbone-only; smaller training set |
| Genie / FoldingDiff | Alternative diffusion approaches | Lower experimental validation; backbone-only |
| Rosetta (fixed-backbone design) | Decades of experimental validation | Much lower success rate (~15-30% vs 50-70%); physics-based, slow |

## Biological Background

### Protein Design

Proteins are linear chains of amino acids that fold into specific three-dimensional structures. The structure determines function: enzymes catalyze reactions because their active sites position catalytic residues precisely; antibodies bind pathogens because their loops form complementary surfaces; structural proteins provide mechanical stability because of their repetitive architectures.

**De novo protein design** is the creation of proteins with structures and functions not found in nature. This contrasts with protein engineering, which modifies existing proteins. The challenge is vast: the space of possible amino acid sequences is astronomically large (20^N for an N-residue protein), and only a tiny fraction of sequences fold into stable structures.

### The Design-Prediction Cycle

Modern computational protein design operates through a cycle:

1. **Structure generation**: A design model (RFD3) creates a target 3D structure
2. **Sequence design**: An inverse folding model (ProteinMPNN) designs sequences likely to fold into that structure
3. **Validation**: A structure prediction model (AlphaFold2, RF3) predicts whether the designed sequence will actually fold as intended
4. **Filtering**: Designs with high self-consistency (designed structure matches predicted structure, measured by scTM or RMSD) are selected for experimental testing

This cycle can be iterated, with RFD3 generating many candidate structures that are progressively filtered. The final candidates are synthesized in the laboratory and characterized by biophysical methods (circular dichroism, SEC-MALS, X-ray crystallography, cryo-EM).

### Diffusion Models for Protein Design

Diffusion models generate new samples by learning to reverse a noise-corruption process. Starting from data (known protein structures), the forward process gradually adds noise until the structure is pure random coordinates. The model learns to reverse this process -- starting from noise and iteratively denoising to produce a protein-like structure.

This approach has several advantages for protein design:

- **Diversity**: Each sample from the diffusion process is unique, enabling exploration of diverse structural solutions
- **Conditioning**: The denoising process can be conditioned on constraints (fixed residues, symmetry, binding targets) to guide design toward desired properties
- **Quality**: The iterative refinement process produces physically plausible structures with proper bond geometry and packing

RFD3 operates in SE(3) -- the group of 3D rotations and translations -- ensuring that generated structures respect the physical symmetries of molecular systems. The number of denoising steps (default: 200) controls the trade-off between computation time and design quality.

---

*See also: [README.md](README.md) for API reference | [MODEL.md](MODEL.md) for technical details*
