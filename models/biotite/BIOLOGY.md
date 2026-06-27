# Biotite -- Biological Context

## Molecule Coverage

### Primary Molecule Type(s)

Biotite operates on **protein 3D structures** in PDB format. It parses atomic coordinate data and performs structural analysis operations -- chain extraction and RMSD computation -- that are fundamental to structural biology workflows.

The tool handles:
- **Single-chain proteins**: Extract sequences and structures from individual protein chains
- **Multi-chain complexes**: Parse complexes and extract individual chains by chain ID
- **Protein-protein complexes**: Compare structures with multiple paired chains

### Cross-Applicability

| Molecule Type | Applicability | Evidence | Caveats |
|---------------|---------------|----------|---------|
| Protein structures | High | Primary design purpose | PDB format required |
| Multi-chain complexes | High | Supports paired chain RMSD | Chain IDs must be specified |
| Protein-ligand complexes | Moderate | Can extract protein chains | Ligand atoms ignored in RMSD (CA only) |
| Nucleic acid structures | Low | PDB parsing works, but no specific analysis | Sequence extraction uses amino acid mapping |
| Small molecules | Not supported | No small molecule analysis | Use chemistry-specific tools |

## Biological Problems Addressed

### Problem 1: Structure Prediction Evaluation

**Why this matters**: When using ML-based structure prediction tools (Boltz, Chai1, ESMFold, AlphaFold2), researchers need to evaluate how well the predicted structure matches the experimental reference. RMSD (Root Mean Square Deviation) is the standard metric for quantifying structural similarity.

**How Biotite addresses it**: The `predict` action computes C-alpha RMSD between two structures after optimal superimposition using the Kabsch algorithm. This allows direct comparison of:
- Predicted vs. experimental structures
- Different prediction methods on the same target
- Conformational changes between different states of the same protein

**Interpreting RMSD values**:
- **< 1.0 Angstroms**: Excellent agreement (comparable to experimental resolution)
- **1.0--2.0 Angstroms**: Good agreement (typical for high-quality predictions)
- **2.0--5.0 Angstroms**: Moderate agreement (correct fold, local differences)
- **> 5.0 Angstroms**: Poor agreement (likely different conformations or wrong fold)

### Problem 2: Chain Extraction from Complexes

**Why this matters**: Structure prediction tools often produce multi-chain complexes (e.g., antibody-antigen, enzyme-substrate, homo-oligomers). Downstream analyses frequently require working with individual chains -- e.g., extracting only the antibody heavy chain, or comparing individual subunits.

**How Biotite addresses it**: The `generate` action extracts specified chains from a PDB structure, returning both:
- **Amino acid sequence**: The 1-letter code sequence of each chain
- **PDB string**: The full atomic coordinate data for each chain

This enables chain-level analysis without manual PDB file manipulation.

### Problem 3: Multi-Model Workflow Integration

**Why this matters**: Modern computational biology workflows often chain multiple tools together -- predict a structure with Boltz, extract individual chains, compare against a reference, score the sequence with ESM2. Having structure parsing and comparison available as an API endpoint enables these workflows to be fully automated.

**How Biotite addresses it**: By providing standardized chain extraction and RMSD computation as BioLM endpoints, Biotite integrates directly with structure prediction models on the same platform. For example:
1. Generate structure with Boltz or Chai1
2. Extract chains with Biotite `generate`
3. Compare with reference using Biotite `predict`
4. Analyze individual chain sequences with ESM2

## Applied Use Cases

### Use Case 1: Structure Prediction Benchmarking (Published)

**Source**: Kunzmann P, Hamacher K. "Biotite: a unifying open source computational biology framework in Python." BMC Bioinformatics (2018). [DOI: 10.1186/s12859-018-2367-z](https://doi.org/10.1186/s12859-018-2367-z)

Biotite is widely used in the computational biology community for structure analysis, comparison, and validation. The BioLM integration enables these capabilities as API-accessible utilities.

### Use Case 2: Automated Structure Comparison Pipelines (Anticipated)

Using Biotite RMSD in automated pipelines that compare predicted protein structures against experimental references (e.g., from the PDB), enabling large-scale benchmarking of structure prediction models.

## Related Models

### Complementary Models

- **Boltz**: Structure prediction model. Use Boltz to predict structures, then Biotite to extract chains and compute RMSD against references.
- **Chai1**: Alternative structure prediction model. Same workflow as Boltz.
- **ESMFold**: Single-sequence structure prediction. Compare ESMFold outputs to experimental structures using Biotite RMSD.
- **ESM2**: Protein language model. Extract chain sequences with Biotite `generate`, then analyze with ESM2 `encode`.

### Alternative Models

| Alternative | Advantage over Biotite | Disadvantage vs Biotite |
|-------------|----------------------|------------------------|
| BioPython PDB | More comprehensive structure analysis | Not API-accessible; requires local setup |
| PyMOL | Visualization; extensive analysis commands | Heavy; GUI-focused; not API-accessible |
| MDAnalysis | Trajectory analysis; flexible atom selection | Focused on simulations; heavier |

## Biological Background

**Protein structure** is central to understanding protein function. Proteins fold from linear amino acid chains into specific three-dimensional shapes that determine their biological activity. Structural biology aims to determine, predict, and analyze these shapes.

**Key concepts relevant to Biotite**:

- **PDB format**: The Protein Data Bank format is the standard file format for storing 3D atomic coordinates of macromolecules. Each atom's position is specified in Cartesian coordinates (x, y, z in Angstroms).
- **Chain**: In multi-molecular complexes, each separate polypeptide or nucleic acid strand is assigned a chain identifier (A, B, C, etc.). A homodimer has two chains with the same sequence; a heterodimer has chains with different sequences.
- **C-alpha (CA) atom**: The central carbon atom in each amino acid residue. C-alpha RMSD is the standard metric for comparing backbone conformations because it provides a one-atom-per-residue representation of the protein's overall shape.
- **RMSD (Root Mean Square Deviation)**: A measure of the average distance between corresponding atoms in two superimposed structures, in Angstroms. Lower RMSD indicates more similar structures.
- **Superimposition (Kabsch algorithm)**: An optimal rotation and translation that minimizes the RMSD between two sets of corresponding atom coordinates. This removes differences due to orientation and position, isolating genuine structural differences.
- **Residue mapping**: Converting between 3-letter amino acid codes (ALA, GLY, etc.) and 1-letter codes (A, G, etc.) is a standard operation in structural bioinformatics.

---

*See also: [README.md](README.md) for API reference | [MODEL.md](MODEL.md) for technical details*
