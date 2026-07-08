# Chai-1 -- Biological Context

## Molecule Coverage

### Primary Molecule Type(s)

Chai-1 is designed for multi-modal biomolecular structure prediction covering:

- **Proteins**: Globular proteins, enzymes, antibodies, and peptides from all domains of life. Handles single chains up to 1024 residues and multi-chain complexes. Standard 20 canonical amino acids only.
- **DNA**: Double-stranded and single-stranded DNA up to 3072 bases. Useful for modeling protein-DNA interactions such as transcription factor binding.
- **RNA**: Single-stranded and structured RNA up to 3072 bases. Supports modeling of protein-RNA complexes, riboswitches, and aptamer interactions.
- **Small molecule ligands**: Drug-like molecules and cofactors specified via SMILES notation. Enables protein-ligand docking and binding pose prediction.
- **Complexes**: Heterogeneous assemblies combining any of the above molecule types (up to 5 entities per complex).

### Cross-Applicability

| Molecule Type | Applicability | Evidence | Caveats |
|--------------|---------------|----------|---------|
| Globular proteins | High | Primary training target; competitive with AlphaFold3 | Best with MSA; single-sequence mode less accurate |
| Antibodies | High | Protein structure prediction applies to antibody Fv regions | CDR loop modeling accuracy varies; no antibody-specific training |
| Enzymes | High | Protein-ligand docking enables active site modeling | Does not predict catalytic mechanism or transition states |
| Peptides | Moderate | Short sequences within the 1024 residue limit | Very short peptides (<10 residues) may lack structural context |
| Membrane proteins | Moderate | Can predict structure but trained primarily on soluble proteins | No lipid bilayer context; transmembrane regions may be less accurate |
| Nucleic acid complexes | High | Explicit support for DNA and RNA entities | Long nucleic acids (>3072 bases) not supported |
| Drug-like ligands | High | SMILES input with RDKit validation | Complex macrocyclic or metalloorganic ligands may produce poor poses |

## Biological Problems Addressed

### Structure Prediction of Biomolecular Complexes

Determining the three-dimensional structure of biomolecular complexes is fundamental to understanding how biological molecules interact. Experimental methods like X-ray crystallography, cryo-EM, and NMR spectroscopy are time-consuming, expensive, and not always feasible for all complex types.

Chai-1 addresses this by computationally predicting the 3D atomic coordinates of multi-component complexes from sequence information alone. Given protein sequences, nucleic acid sequences, and/or small molecule SMILES strings, it generates plausible 3D structures in mmCIF format.

The output represents a predicted static structure showing the spatial arrangement of all atoms, including how the different molecular components contact each other. This is directly useful for understanding binding interfaces, identifying key interacting residues, and guiding experimental design.

### Protein-Ligand Docking

Understanding how small molecules (drugs, cofactors, metabolites) bind to protein targets is central to drug discovery. Traditional computational docking methods require a known protein structure and use physics-based scoring functions that can be inaccurate.

Chai-1 performs structure prediction and docking simultaneously: given a protein sequence and a ligand SMILES string, it predicts the complex structure including the ligand binding pose. This is particularly valuable in early-stage drug discovery when:
- No experimental structure of the target protein exists
- The binding site location is unknown
- Multiple binding modes need to be explored (via multiple diffusion samples)

### Protein-Nucleic Acid Interactions

Many biological processes depend on protein-DNA and protein-RNA interactions: transcription factor binding, CRISPR-Cas systems, ribosomal machinery, and RNA-binding protein regulation. Predicting these interaction structures helps understand gene regulation and RNA biology.

Chai-1 can model protein-nucleic acid complexes by accepting both protein and DNA/RNA sequences as input entities. The predicted structure reveals the binding interface, including which protein residues contact which nucleotide bases.

### Antibody-Antigen Modeling

Therapeutic antibody development requires understanding how antibody variable regions interact with target antigens. Chai-1 can predict antibody-antigen complex structures, providing insights into:
- Epitope identification (which antigen residues are contacted)
- Paratope characterization (which antibody residues drive binding)
- Binding mode comparison across antibody candidates

## Applied Use Cases

Chai-1 has been evaluated in several independent benchmarking studies since its release:

- **Cross-docking benchmark (PoseX, 2025)**: A large-scale evaluation of 25 structure prediction methods found co-folding approaches including Chai-1 converge at approximately 60–61% success on cross-docking tasks, outperforming classical physics-based docking tools.
- **GPCR-peptide binding (2025)**: Benchmarking on 124 GPCR ligands with 1,240 decoys compared Chai-1 against AlphaFold2, AlphaFold3, and ESMFold for peptide binding prediction.
- **Flexible protein-ligand docking review (2025)**: A systematic review positions Chai-1 among leading deep learning methods for flexible receptor docking in drug discovery pipelines.
- **SARS-CoV-2 Mac1 prospective evaluation (2025)**: Testing on 557 Mac1-ligand poses showed Chai-1 achieves >50% under 2 Å RMSD, comparable to AlphaFold3 and Boltz-2.
- **FoldBench comprehensive benchmark (2025)**: Evaluation across 1,522 assemblies and 9 tasks (protein-ligand, protein-RNA, protein-DNA, antibody-antigen) demonstrates Chai-1's breadth across complex types.
- **Protein-peptide docking (PepPCBench, 2025)**: Benchmarked on 261 protein-peptide complexes (5–30 residues) for docking accuracy and scoring alongside AlphaFold3, HelixFold3, and RFAA.

Chai-1's multi-modal capability enables several practical workflows:

- **Virtual screening**: Dock libraries of small molecules against a protein target to identify candidate binders
- **Binding site identification**: Predict where a ligand binds on a protein of unknown structure
- **Protein engineering**: Model how mutations affect complex formation with binding partners
- **Structural biology**: Generate starting models for molecular replacement in crystallography or for fitting into cryo-EM density maps

## Related Models

### Predecessor Models

- **AlphaFold2** (2021): Revolutionized protein structure prediction but limited to proteins (no ligands, DNA/RNA). Required MSA input. Chai-1 extends this to multi-modal complexes.
- **RoseTTAFold** (2021): Alternative protein structure prediction approach. Single-molecule only.

### Complementary Models

- **ESM2**: Protein language model whose embeddings can be used by Chai-1 (`use_esm_embeddings=True`) to improve structure prediction quality, especially for proteins without good MSA coverage.
- **RF3**: Alternative open-source AF3-like structure prediction model in this catalog. Can be used as a second opinion or for ensemble predictions.

### Alternative Models

| Alternative | Advantage over Chai-1 | Disadvantage |
|-------------|----------------------|--------------|
| AlphaFold3 | Potentially higher accuracy on some benchmarks | Not open-source; API access only |
| Boltz-1 | Different model architecture; useful for ensemble | May differ in accuracy on specific complex types |
| ESMFold | Much faster inference (~1 second); no MSA needed | Proteins only; lower accuracy on hard targets |
| AlphaFold2 | Well-established; extensive validation literature | Proteins only; no ligand/DNA/RNA support |

## Biological Background

### Biomolecular Structure

Biological molecules -- proteins, DNA, RNA, and small molecules -- carry out their functions through specific three-dimensional arrangements of atoms. The spatial structure determines which molecules can interact, how enzymes catalyze reactions, how drugs bind to targets, and how genetic information is read and regulated.

**Proteins** are chains of amino acids that fold into complex 3D shapes. The structure hierarchy includes:
- **Primary**: Linear amino acid sequence
- **Secondary**: Local folding patterns (alpha-helices, beta-sheets)
- **Tertiary**: Overall 3D arrangement of a single chain
- **Quaternary**: Assembly of multiple chains into complexes

**Nucleic acids** (DNA and RNA) adopt specific structures through base pairing and stacking interactions. DNA typically forms a double helix, while RNA folds into diverse structures including hairpins, loops, and pseudoknots.

**Small molecules** (ligands) bind to proteins at specific sites, often triggering biological responses. Drug molecules are designed to bind specific protein targets to modulate their activity.

### Why Structure Prediction Matters

Experimental structure determination is slow (months to years per structure) and expensive. As of 2024, the Protein Data Bank contains ~220,000 experimentally determined structures, but there are hundreds of millions of known protein sequences. Computational structure prediction fills this gap, enabling:

- **Drug discovery**: Understanding target structure accelerates drug design
- **Protein engineering**: Structural models guide rational mutagenesis
- **Basic biology**: Structure reveals function and mechanism
- **Diagnostics**: Understanding disease-associated mutations at the structural level

### The Multi-Modal Challenge

Most biological functions involve interactions between different molecule types. A transcription factor (protein) binds DNA to regulate gene expression. A ribosome (protein + RNA complex) reads mRNA to synthesize proteins. A drug (small molecule) binds a protein to treat disease. Predicting these multi-component structures requires models that understand the physics and chemistry of diverse molecular interactions simultaneously, which is the core capability that Chai-1 provides.

---

*See also: [README.md](README.md) for API reference | [MODEL.md](MODEL.md) for technical details*
