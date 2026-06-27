# ThermoMPNN-D -- Biological Context

## Molecule Coverage

### Primary Molecule Type(s)

ThermoMPNN-D is designed for globular proteins with known 3D structures (PDB format). It predicts the thermodynamic effect (ddG) of single and double amino acid substitutions on protein stability. The model handles single-chain proteins up to 1024 residues and requires backbone atom coordinates.

### Cross-Applicability

| Molecule Type | Applicability | Evidence | Caveats |
|--------------|---------------|----------|---------|
| Globular proteins | High | Primary training target | Best for well-folded soluble proteins |
| Enzymes | High | Well-represented in stability datasets | Useful for thermostable enzyme engineering |
| Antibodies | Moderate | Single-chain structures may work | Multi-chain requires specifying chain |
| Membrane proteins | Low | Under-represented in training data | Membrane stability context not modeled |
| Intrinsically disordered | Not applicable | Requires folded structure | No stable baseline state |

## Biological Problems Addressed

### Epistatic Stability Prediction

In protein engineering, mutations rarely occur in isolation. When two mutations are introduced simultaneously, their combined effect may differ from the sum of their individual effects -- a phenomenon called epistasis. Epistasis can be:

- **Positive epistasis**: The double mutant is more stable than predicted by summing individual effects
- **Negative epistasis**: The double mutant is less stable than predicted
- **Sign epistasis**: One mutation is stabilizing alone but destabilizing in combination with another

Understanding epistasis is critical for:
- **Combinatorial protein engineering**: Identifying synergistic stabilizing mutation pairs
- **Directed evolution**: Predicting which mutation combinations to test experimentally
- **Understanding evolutionary constraints**: Why certain mutation combinations are favored or forbidden in nature

ThermoMPNN-D's epistatic mode directly models these pairwise interactions, going beyond simple additive approximations.

### Single Mutation Stability Prediction

Like its predecessor ThermoMPNN, the model supports single mutation ddG prediction and full SSM scans. The single mode provides a baseline for comparison with the additive and epistatic double-mutation predictions.

### Additive Double Mutation Prediction

The additive mode estimates double mutation ddG by summing the individual single-mutation effects. While this approximation misses epistatic interactions, it is computationally cheaper and provides a useful baseline. Comparing additive vs epistatic predictions reveals which mutation pairs exhibit significant non-additive effects.

## Applied Use Cases

No applied literature entries have been catalogued yet.

<!-- TODO: Search for papers citing ThermoMPNN-D (Dieckhaus & Kuhlman, 2024) for applied use cases -- search Google Scholar/Semantic Scholar -->

## Related Models

### Predecessor Models

ThermoMPNN-D extends ThermoMPNN (Dieckhaus et al., 2023), which itself builds on ProteinMPNN (Dauparas et al., 2022). The progression is:

1. **ProteinMPNN**: Protein sequence design from structure
2. **ThermoMPNN**: Single mutation stability prediction via transfer learning
3. **ThermoMPNN-D**: Single + double mutation stability with epistasis modeling

### Complementary Models

- **ThermoMPNN**: For single mutations only (simpler, faster). Use when double mutations are not needed.
- **ESM2**: Sequence-based representations that can complement structure-based stability predictions.
- **Boltz / AlphaFold**: Structure prediction models to generate input PDB structures when experimental structures are unavailable.

### Alternative Models

| Alternative | Advantage over ThermoMPNN-D | Disadvantage |
|-------------|---------------------------|--------------|
| ThermoMPNN | Simpler, lower memory (8 GB vs 12 GB) | No double mutation or epistasis support |
| TemBERTure | Sequence-only, no structure needed | No per-mutation ddG predictions |

## Biological Background

Protein stability engineering often requires introducing multiple mutations to achieve desired stability improvements. While individual stabilizing mutations can be identified through computational screening, their combined effects are not always additive.

Epistasis in protein stability arises from the complex network of intramolecular interactions. Two mutations may interact through:

- **Direct contact**: Mutations at spatially proximal residues that physically interact
- **Allosteric coupling**: Mutations at distant sites that communicate through the protein structure
- **Compensatory effects**: One mutation disrupts a local interaction while another restores it in a different way

The CA-CA distance threshold used by ThermoMPNN-D (default 5.0 Angstroms) focuses predictions on spatially proximal mutation pairs, where direct epistatic interactions are most likely. This distance-based filtering also reduces the computational burden of scanning all possible double mutations, which scales as O(N^2) with sequence length.

Understanding and predicting epistasis is particularly important in:
- **Thermostable enzyme engineering**: Where multiple mutations may be needed to reach process-temperature stability
- **Therapeutic protein development**: Where stability, activity, and immunogenicity must be simultaneously optimized
- **Ancestral sequence reconstruction**: Where epistatic constraints shape evolutionary trajectories

---

*See also: [README.md](README.md) for API reference | [MODEL.md](MODEL.md) for technical details*
