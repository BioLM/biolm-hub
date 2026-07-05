# ThermoMPNN -- Biological Context

## Molecule Coverage

### Primary Molecule Type(s)

ThermoMPNN is designed for globular proteins with known 3D structures (PDB format). It predicts the thermodynamic effect (ddG) of single amino acid substitutions on protein stability. The model handles single-chain proteins up to 1024 residues and requires backbone atom coordinates (N, CA, C, O) for each residue.

### Cross-Applicability

| Molecule Type | Applicability | Evidence | Caveats |
|--------------|---------------|----------|---------|
| Globular proteins | High | Primary training target | Best for well-folded soluble proteins |
| Enzymes | High | Well-represented in stability datasets | Useful for engineering thermostable enzymes |
| Antibodies | Moderate | Single-chain Fv or Fab structures may work | Multi-chain requires specifying chain ID |
| Membrane proteins | Low | Under-represented in training data | Stability in membrane context not modeled |
| Intrinsically disordered | Not applicable | Requires folded structure | No stable baseline state |

## Biological Problems Addressed

### Protein Stability Engineering

Protein stability is a critical property for therapeutic proteins, industrial enzymes, and research reagents. The change in Gibbs free energy of unfolding (ddG) quantifies how a mutation affects stability: negative ddG indicates stabilization, positive ddG indicates destabilization.

Experimental methods for measuring ddG (e.g., thermal denaturation, urea unfolding) are laborious and require purified protein for each variant. ThermoMPNN enables computational screening of all possible single-point mutations in a protein, identifying stabilizing candidates for experimental validation.

**Applications include:**
- Identifying stabilizing mutations for therapeutic proteins
- Engineering thermostable industrial enzymes
- Understanding disease-causing mutations that destabilize proteins
- Rational protein design guided by stability predictions

### Site-Saturation Mutagenesis (SSM) Scanning

When no specific mutations are provided, ThermoMPNN performs a complete SSM scan -- predicting ddG for all 20 possible amino acid substitutions at every position. This produces a comprehensive stability landscape that reveals:

- Mutation-tolerant positions (many neutral substitutions)
- Critical positions (most substitutions are destabilizing)
- Potential stabilizing mutations (negative ddG)

## Applied Use Cases

ThermoMPNN has been applied in several published studies:

- **Epistatic double mutations (ThermoMPNN-D)**: Dieckhaus & Kuhlman (2025, *Protein Science*) extended ThermoMPNN to double-mutant predictions and demonstrated that stability models fail to capture epistatic interactions, motivating the ThermoMPNN-D variant.
- **Thermostable protein design**: Ertelt et al. (2024, *bioRxiv*) built on the ProteinMPNN backbone (shared with ThermoMPNN) in HyperMPNN to design thermostable proteins from hyperthermophilic data, achieving designs stable at 95°C from a 65°C starting point.
- **PNAS peer-reviewed benchmark**: The peer-reviewed PNAS (2024) publication of ThermoMPNN established state-of-the-art single-mutation ddG prediction (PCC ~0.75, RMSE ~0.71 kcal/mol) on the Megascale dataset.
- **Human Domainome benchmarking**: Beltran et al. (2025, *Nature*) benchmarked ThermoMPNN on 500K+ missense variants across 500 human protein domains and found it to be the best stability predictor overall (median rho = 0.50, 0.57 excluding zinc-fingers), outperforming all other dedicated stability predictors.
- **SPURS comparison**: Li & Luo (2025, *Nature Communications*) introduced SPURS and benchmarked it against ThermoMPNN on the Megascale test set, with ThermoMPNN achieving Spearman correlation of 0.77 (SPURS: 0.83).

## Related Models

### Predecessor Models

ThermoMPNN builds on ProteinMPNN (Dauparas et al., 2022), a message-passing neural network for protein sequence design. ProteinMPNN was trained to predict amino acid sequences compatible with a given backbone structure. ThermoMPNN transfers these learned structural representations to the task of stability prediction.

### Complementary Models

- **ThermoMPNN-D**: Extended version supporting double (paired) mutations with epistatic interaction modeling. Use when evaluating combinations of two mutations.
- **ESM2**: General protein language model for sequence-based property prediction. Can provide complementary sequence-based stability signals.
- **ESMFold / Chai-1**: Structure prediction models. Use to generate input PDB structures when experimental structures are unavailable.

### Alternative Models

| Alternative | Advantage over ThermoMPNN | Disadvantage |
|-------------|--------------------------|--------------|
| ThermoMPNN-D | Handles double mutations and epistasis | More complex, higher resource usage |
| TemBERTure | Sequence-only input, no structure needed | No per-mutation ddG, only global stability |
| RaSP | Anticipated: rapid stability prediction | Different training data and approach |

## Biological Background

Protein stability refers to the thermodynamic balance between the folded (native) and unfolded states of a protein. The Gibbs free energy of unfolding (delta-G) quantifies this balance: proteins with more negative delta-G are more stable. When a mutation is introduced, the change in stability (ddG = delta-G_mutant - delta-G_wildtype) indicates whether the mutation stabilizes (ddG < 0) or destabilizes (ddG > 0) the protein.

The structural basis of protein stability involves:
- **Hydrophobic core packing**: Mutations that disrupt the hydrophobic core are typically destabilizing
- **Hydrogen bonds**: Loss of hydrogen bonds generally destabilizes the structure
- **Salt bridges**: Charged residue pairs that contribute favorably to stability
- **Conformational entropy**: Mutations to more flexible residues (e.g., Gly) can destabilize through increased unfolded-state entropy
- **Steric clashes**: Large-to-small or small-to-large substitutions that create unfavorable contacts

Graph neural networks like ThermoMPNN are well-suited to this task because protein structures are naturally represented as graphs, where nodes are residues and edges encode spatial proximity and chemical interactions.

---

*See also: [README.md](README.md) for API reference | [MODEL.md](MODEL.md) for technical details*
