# SPURS -- Biological Context

## Molecule Coverage

### Primary Molecule Type(s)

SPURS operates on **single-chain proteins** with available 3D structure (experimental or predicted). It predicts the thermodynamic effect of amino acid substitutions on protein stability (ddG in kcal/mol).

Performance characteristics by protein type:

- **Globular proteins**: Primary training domain. Best prediction accuracy for well-folded single-domain proteins.
- **Enzymes**: Well-suited for evaluating mutations near active sites and in the hydrophobic core.
- **Designed proteins**: Applicable to de novo designs with AlphaFold-predicted structures.
- **Multi-domain proteins**: Each domain can be analyzed independently (single chain, up to 1024 residues).
- **Membrane proteins**: Supported if structure is available, though training data may under-represent transmembrane regions.

### Cross-Applicability

| Molecule Type | Applicability | Evidence | Caveats |
|--------------|---------------|----------|---------|
| Globular proteins | High | Primary training domain | Best accuracy on well-folded proteins |
| Enzymes | High | Active-site mutations well-characterized | Catalytic activity not directly predicted |
| De novo designs | Moderate | Structure from AlphaFold can be used | Training data may not cover novel folds |
| Antibodies | Moderate | Can predict stability of individual chains | No multi-chain analysis for Fab/scFv complexes |
| Membrane proteins | Low--Moderate | Requires structure input | Under-represented in training data |
| Peptides | Low | Short sequences may lack structural context | Minimum structure requirements apply |

## Biological Problems Addressed

### Protein Stability Engineering

**Problem**: Most random mutations destabilize proteins. In protein engineering, maintaining or improving stability while introducing desired functional mutations is a critical challenge. Experimental measurement of ddG for every possible mutation is prohibitively expensive.

**How SPURS helps**: The `predict` action with `mutations=None` (or `return_full_dms=True`) returns a complete saturation mutagenesis matrix (L x 20) predicting the ddG for every possible single-residue substitution. This enables computational screening of all mutations before experimental validation.

**Biological meaning**: Each value in the ddG matrix represents the predicted change in folding free energy (kcal/mol) for substituting the wild-type residue at that position with each of the 20 canonical amino acids. Negative values indicate stabilizing mutations; positive values indicate destabilizing ones. A mutation with ddG < -1 kcal/mol is considered meaningfully stabilizing; ddG > 1 kcal/mol is meaningfully destabilizing.

### Multi-Mutation Effect Prediction

**Problem**: Protein engineering often requires multiple simultaneous mutations. The effects of individual mutations are not simply additive -- they can be synergistic (more stabilizing together) or antagonistic (canceling each other out).

**How SPURS helps**: The `predict` action with multiple mutations uses the SPURSMulti model to predict the combined ddG, along with per-mutation contributions. This captures non-additive effects that would be missed by summing individual ddG predictions.

**Biological meaning**: The combined ddG reflects the total stability impact of all mutations together. Per-mutation contributions show how each mutation contributes to the total, revealing potential epistatic interactions.

### Variant Sequence Comparison

**Problem**: When comparing a wild-type protein to an engineered variant, manually identifying all mutations and predicting their combined effect is tedious.

**How SPURS helps**: The `predict` action with `variant_sequence` automatically identifies all differences between wild-type and variant sequences, calculates mutations, and predicts the combined ddG.

**Biological meaning**: This enables rapid comparison of any two sequences that differ by one or more point mutations, quantifying the expected stability difference in kcal/mol.

## Applied Use Cases

Published use cases for SPURS and related stability prediction models:

- **Therapeutic protein stabilization**: Identifying stabilizing mutations to improve shelf life and manufacturability
- **Enzyme engineering**: Maintaining stability while introducing functional mutations for industrial biocatalysis
- **Protein library design**: Filtering mutation libraries to exclude destabilizing variants before experimental screening
- **Disease variant interpretation**: Assessing whether missense mutations are likely to destabilize protein structure

Anticipated (not yet published) use cases:

- Integration with sequence design tools (ProteinMPNN, RFDiffusion) for stability-guided design
- Multi-round engineering with iterative stability optimization

## Related Models

### Complementary Models

- **ESM2** (this catalog): SPURS uses ESM2-650M embeddings internally for sequence features. ESM2's `log_prob` action provides an orthogonal (evolutionary) signal for mutation impact.
- **Chai-1** (this catalog): Structure prediction model that generates the 3D structures SPURS needs as input.

### Alternative Models

| Alternative | Advantage Over SPURS | Disadvantage vs SPURS |
|-------------|----------------------|----------------------|
| ESM-1v / ESM2 log-prob | No structure needed, faster | Less accurate for structural mutations |
| RaSP | Fast DMS generation | Different model architecture |
| FoldX | Physics-based, interpretable | Slower, requires energy minimization |
| Rosetta ddG | Gold standard for structure-based ddG | Very slow (hours per mutation) |
| GEMME | MSA-based, captures epistasis | Requires MSA, no structural context |

**When to choose SPURS**: Use SPURS when you have a 3D structure and need fast, accurate ddG predictions with multi-mutation support and full DMS matrix capability.

**When to choose alternatives**: Use ESM2 `log_prob` for quick sequence-based scoring without structure; use FoldX/Rosetta for high-accuracy physics-based predictions when speed is not critical.

## Biological Background

**Protein stability** refers to the thermodynamic balance between the folded (native) and unfolded states of a protein. The free energy of folding (delta-G) is typically -5 to -15 kcal/mol for natural proteins -- a narrow margin that can be disrupted by single mutations.

**ddG (delta-delta-G)**: The change in folding free energy caused by a mutation. It is defined as:

```
ddG = delta-G(mutant) - delta-G(wild-type)
```

- **ddG < 0**: Mutation stabilizes the protein (mutant folds more favorably)
- **ddG > 0**: Mutation destabilizes the protein (mutant is less stable)
- **|ddG| < 1 kcal/mol**: Generally considered neutral
- **ddG > 2 kcal/mol**: Likely significantly destabilizing

**Deep mutational scanning (DMS)**: An experimental technique where every possible single-residue substitution is tested simultaneously. SPURS computationally generates the equivalent DMS matrix (L positions x 20 amino acids) in seconds.

**Epistasis**: The phenomenon where the effect of one mutation depends on the presence of other mutations. The SPURSMulti model captures pairwise epistatic effects that would be missed by simply summing individual ddG values.

**Key terminology**:
- **Saturation mutagenesis**: Testing all 20 amino acids at every position in a protein
- **ddG matrix**: An L x 20 matrix where each entry is the predicted ddG for substituting position i with amino acid j
- **Stabilizing mutation**: A mutation with ddG < 0 (increases folding stability)
- **Destabilizing mutation**: A mutation with ddG > 0 (decreases folding stability)
- **Additive model**: Assumes combined ddG = sum of individual ddGs (often inaccurate)
- **Non-additive / epistatic**: Combined effect differs from sum of individual effects

---

*See also: [README.md](README.md) for API reference | [MODEL.md](MODEL.md) for technical details*
