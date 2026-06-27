# TemBERTure -- Biological Context

## Molecule Coverage

### Primary Molecule Type(s)

TemBERTure is designed for protein sequences from all domains of life. It handles single-chain protein sequences up to 512 residues. The model was trained on proteins with known thermostability properties, covering both thermophilic organisms (optimal growth above 45 degrees C) and mesophilic organisms.

### Cross-Applicability

| Molecule Type | Applicability | Evidence | Caveats |
|--------------|---------------|----------|---------|
| Globular proteins | High | Primary training target | Best for proteins with known structural context |
| Enzymes | High | Well-represented in training data | Industrial enzyme engineering use case |
| Nanobodies | Moderate | Single-domain antibody fragments are proteins | Consider TEMPRO for nanobody-specific Tm prediction |
| Peptides | Low | Short sequences may lack sufficient context | Minimum meaningful length depends on the fold |
| Membrane proteins | Unknown | May be under-represented in training | Use predictions with caution |

## Biological Problems Addressed

### Thermostability Classification

Protein thermostability is a critical property for biotechnology and industrial enzyme applications. Thermostable proteins maintain their structure and function at elevated temperatures, making them valuable for applications such as industrial catalysis, therapeutic protein development, and food processing. Traditional experimental methods for measuring thermostability (differential scanning calorimetry, thermal shift assays) are time-consuming and require purified protein.

TemBERTure's classifier variant predicts whether a protein is thermophilic (stable at high temperatures) or non-thermophilic from sequence alone. This enables rapid screening of large protein libraries for thermostable candidates without experimental measurement.

### Melting Temperature Prediction

The melting temperature (Tm) is the temperature at which 50% of a protein population is unfolded. It is a quantitative measure of protein thermal stability. Knowing the Tm helps in:

- Protein engineering: designing mutations that increase stability
- Drug formulation: selecting storage conditions for therapeutic proteins
- Industrial applications: choosing enzymes that function at process temperatures

TemBERTure's regression variant predicts the Tm in degrees Celsius from sequence alone, providing a quantitative stability estimate.

## Applied Use Cases

No applied literature entries have been catalogued yet.

<!-- TODO: Search for papers citing TemBERTure (Rodella et al., 2024) for applied use cases -- search Google Scholar/Semantic Scholar -->

## Related Models

### Predecessor Models

TemBERTure builds on ProtBERT-BFD (Elnaggar et al., 2022), a BERT model pre-trained on the BFD protein database. ProtBERT provides the base representations; TemBERTure adds task-specific adapter layers for thermostability prediction.

### Complementary Models

- **ThermoMPNN / ThermoMPNN-D**: Structure-based stability prediction (ddG for mutations). Use when you have a 3D structure and want to evaluate specific mutations.
- **ESM2**: General-purpose protein language model. Use ESM2 embeddings for broader protein property prediction tasks.

### Alternative Models

| Alternative | Advantage over TemBERTure | Disadvantage |
|-------------|--------------------------|--------------|
| ThermoMPNN | Structure-aware, per-mutation ddG | Requires PDB structure input |
| TEMPRO | Specialized for nanobody Tm | Only applicable to nanobodies |

## Biological Background

Proteins are chains of amino acids that fold into three-dimensional structures to perform biological functions. Thermal stability -- the ability of a protein to resist unfolding at elevated temperatures -- is determined by a complex interplay of intramolecular interactions including hydrogen bonds, hydrophobic packing, salt bridges, and disulfide bonds.

Organisms that thrive in extreme temperatures (thermophiles, growing above 45 degrees C; hyperthermophiles, above 80 degrees C) have evolved proteins with enhanced thermal stability. These adaptations include increased hydrophobic core packing, additional salt bridges, shorter surface loops, and higher proline content. Understanding and predicting these stability determinants is valuable for protein engineering, where enhancing thermostability can improve protein shelf life, process efficiency, and therapeutic applicability.

---

*See also: [README.md](README.md) for API reference | [MODEL.md](MODEL.md) for technical details*
