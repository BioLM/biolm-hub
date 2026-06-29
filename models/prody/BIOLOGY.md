# ProDy -- Biological Context

## Molecule Coverage

### Primary Molecule Type(s)

ProDy analyzes **protein structures** -- both single-chain and multi-chain complexes. It accepts PDB or CIF format structures and requires that analyzed chains contain protein residues (not DNA, RNA, or small molecules).

Performance characteristics by structure type:

- **Single-chain proteins**: Full intra-chain interaction analysis. All 6 interaction types detected.
- **Protein complexes**: Both intra-chain and inter-chain interaction analysis. Chain pairs can be specified explicitly or all pairs are analyzed.
- **Antibody-antigen complexes**: Supported. Inter-chain interaction analysis between antibody and antigen chains reveals binding interface contacts.
- **Enzyme-substrate complexes**: Protein chains are analyzed; small-molecule ligands are excluded from interaction calculation.
- **Membrane proteins**: Supported if structure is available. Interactions within transmembrane domains are detected normally.

### Cross-Applicability

| Molecule Type | Applicability | Evidence | Caveats |
|--------------|---------------|----------|---------|
| Proteins (single-chain) | High | Primary use case | Full interaction analysis |
| Protein complexes | High | Multi-chain analysis with chain pairs | Sequential processing (C extensions not thread-safe) |
| Antibodies | High | Protein chains analyzed normally | Only protein-protein interactions; no CDR-specific logic |
| Enzymes | High | Active-site interactions detectable | Ligand interactions not computed |
| DNA/RNA chains | Not supported | Rejected with error | Chains must be protein |
| Ligands/small molecules | Not supported | Not analyzed | ProDy InSty is protein-only |

## Biological Problems Addressed

### Protein-Protein Interface Characterization

**Problem**: Understanding which residues mediate protein-protein interactions is essential for drug design, antibody engineering, and understanding disease mechanisms. Crystallographic structures show the 3D arrangement but do not directly enumerate the non-covalent interactions that stabilize the interface.

**How ProDy helps**: The `encode` action with `chain_pairs` specified computes all inter-chain interactions between two protein chains. It returns hydrogen bonds, salt bridges, hydrophobic contacts, pi-stacking, cation-pi, and repulsive ionic interactions with residue-level resolution, distances, and optional energy estimates.

**Biological meaning**: The interaction profile reveals the chemical nature of the binding interface. A salt-bridge-rich interface suggests electrostatic complementarity; a hydrophobic-dominated interface indicates burial of non-polar surface area. Frequent interactor analysis identifies "hotspot" residues that make many contacts -- these are often critical for binding and are prime targets for mutagenesis.

### Structural Comparison via RMSD

**Problem**: Comparing protein structures -- before/after mutation, across conformational states, between homologs -- requires quantitative structural similarity metrics. RMSD (root mean square deviation) is the standard metric.

**How ProDy helps**: The `predict` action computes RMSD between two structures after alignment. It supports structural alignment (default) and sequence-based alignment for homologous proteins with different sequences.

**Biological meaning**: RMSD quantifies the average displacement of matched atoms (CA atoms) between two structures. An RMSD of 0-1 Angstrom indicates nearly identical conformations; 1-3 Angstrom indicates similar fold with local differences; >5 Angstrom indicates major structural changes. This is used to assess conformational changes upon ligand binding, mutation effects on structure, and homology model quality.

### Intra-Chain Interaction Networks

**Problem**: Identifying the network of non-covalent interactions within a protein reveals which residues stabilize the fold, form functional sites, or create allosteric pathways.

**How ProDy helps**: The `encode` action computes all intra-chain interactions within each specified chain. The interaction matrix and energy matrix options provide a global view of the interaction network.

**Biological meaning**: Dense clusters of hydrogen bonds and salt bridges often indicate structured, stable regions. Hydrophobic cores are revealed by dense hydrophobic contact networks. Pi-stacking and cation-pi interactions in aromatic clusters can indicate functional sites. The energy matrix quantifies the energetic contribution of each interaction.

## Applied Use Cases

ProDy is an established bioinformatics tool (published 2011, >2500 citations). Applied use cases include:

- **Drug-target interaction analysis**: Characterizing binding interfaces between therapeutic targets and partner proteins
- **Mutation impact assessment**: Comparing wild-type and mutant structures via RMSD
- **Antibody-antigen interface mapping**: Identifying critical interface contacts for antibody engineering
- **Protein engineering**: Understanding which interactions stabilize the fold to guide rational design
- **Quality assessment**: RMSD comparison of computational models against experimental structures

## Related Models

### Complementary Models

- **Boltz / Chai-1** (this platform): Structure prediction models that generate the 3D structures ProDy then analyzes
- **SPURS** (this platform): Uses structure as input for stability prediction; ProDy can characterize the interactions SPURS implicitly evaluates
- **Pro4S** (this platform): Uses structure for solubility prediction; ProDy interaction analysis can explain Pro4S predictions

### Alternative Models

| Alternative | Advantage Over ProDy | Disadvantage vs ProDy |
|-------------|----------------------|----------------------|
| PLIP | Built-in visualization | Fewer interaction types |
| Arpeggio | More interaction types, nucleic acid support | Heavier dependencies |
| MDAnalysis | Molecular dynamics trajectory support | More complex API for simple interaction analysis |
| GetContacts | Fast contact extraction | Less robust hydrogen handling |

**When to choose ProDy**: Use ProDy when you need comprehensive protein-protein interaction analysis with energy estimates, interaction matrices, and frequent interactor identification.

**When to choose alternatives**: Use PLIP for quick visualization; use Arpeggio when nucleic acid interactions are needed; use MDAnalysis for trajectory analysis.

## Biological Background

**Non-covalent interactions** are the forces that hold protein structures together and mediate protein-protein recognition. Unlike covalent bonds, they are individually weak (1-40 kcal/mol) but collectively strong enough to stabilize 3D structure and drive specific molecular recognition.

**Types of interactions ProDy detects**:

- **Hydrogen bonds**: The most common non-covalent interaction in proteins. Formed between a hydrogen donor (N-H, O-H) and an acceptor (O, N). Critical for secondary structure (alpha-helices, beta-sheets) and specificity of molecular recognition. Typical distance: 2.7-3.4 Angstrom.

- **Salt bridges**: Electrostatic interactions between oppositely charged residues (e.g., Lys/Arg with Asp/Glu). Important for protein stability and can contribute 1-5 kcal/mol to binding free energy. Typical distance: 3.3-3.5 Angstrom.

- **Hydrophobic interactions**: The thermodynamic driving force for protein folding. Non-polar residues (Leu, Ile, Val, Phe, Trp) pack together in the protein interior to minimize contact with water. Typical distance: 3.4-4.5 Angstrom.

- **Pi-stacking**: Interactions between aromatic rings (Phe, Tyr, Trp, His). Can be face-to-face (sandwich), edge-to-face (T-shaped), or offset stacked. Important in protein-ligand and protein-protein interfaces.

- **Cation-pi**: Interactions between positively charged residues (Lys, Arg) and aromatic rings. Energetically significant (1-5 kcal/mol) and common in protein-protein interfaces.

- **Repulsive ionic**: Repulsive interactions between like-charged residues (e.g., two Asp or two Lys nearby). These destabilize local structure and are relevant for understanding charge-charge repulsion in protein design.

**RMSD (Root Mean Square Deviation)**: The standard metric for quantifying structural similarity between two protein conformations. Calculated as the square root of the mean squared distance between corresponding atom positions after optimal superposition. Lower RMSD indicates more similar structures.

**Key terminology**:
- **InSty**: ProDy's Interactions by Structural Topology module for computing non-covalent interactions
- **Hotspot residue**: A residue that contributes disproportionately to binding affinity; often identified by having many interaction contacts
- **Structural alignment**: Superimposing structures by minimizing RMSD between corresponding atoms
- **Sequence alignment**: Matching structures by aligning their amino acid sequences before RMSD calculation

---

*See also: [README.md](README.md) for API reference | [MODEL.md](MODEL.md) for technical details*
