# ESMFold -- Biological Context

## Molecule Coverage

### Primary Molecule Type(s)

ESMFold is designed for **protein structure prediction** from amino acid sequences. It accepts single-chain proteins and small multi-chain complexes (up to 4 chains concatenated with `:` separators) with a maximum total length of 768 residues.

The model is trained on structures from the Protein Data Bank (PDB) and AlphaFold2 distillation data, covering proteins from all domains of life. Performance characteristics vary by protein type:

- **Globular, soluble proteins**: Best performance. These represent the majority of PDB training data, and the ESM-2 backbone has strong representations for this category.
- **Single-domain proteins**: Excellent accuracy when the protein has detectable homologs in UniRef50. For well-covered families, pLDDT > 70 typically corresponds to TM-score > 0.8 relative to experimental structures.
- **Multi-domain proteins**: Each domain may be predicted well individually, but relative domain orientations can be unreliable, especially for flexible linker regions.
- **Multi-chain complexes**: Supported but with degraded accuracy compared to single chains. Performance decreases with the number of chains.
- **Membrane proteins**: Under-represented in training data. Transmembrane regions may be poorly predicted, especially for multi-pass helical bundles.
- **Intrinsically disordered regions**: The model will assign low pLDDT scores to these regions (correctly reflecting uncertainty), but the predicted coordinates do not represent the biological ensemble of conformations.

### Cross-Applicability

| Molecule Type | Applicability | Evidence | Caveats |
|--------------|---------------|----------|---------|
| Globular proteins | High | Core training and evaluation target (CAMEO, CASP14) | Best performance category |
| Enzymes | High | Active site geometry generally well-predicted for globular enzymes | Catalytic mechanism and substrate binding not modeled |
| Antibodies | Moderate | Can fold individual Fv domains | CDR loop conformations may be inaccurate; dedicated antibody structure predictors (e.g., ABodyBuilder2) may outperform |
| Protein complexes | Moderate | Supports up to 4 chains via `:` separator | Interface contacts are less reliable than dedicated complex predictors (Chai-1) |
| Peptides | Low | Very short sequences (< 30 residues) provide limited context for the ESM-2 backbone | Structure prediction for short peptides is inherently difficult; consider experimental NMR data |
| DNA/RNA-binding proteins | Moderate | Protein structure itself can be predicted | Nucleic acid partners are not modeled |

## Biological Problems Addressed

### Rapid Protein Structure Prediction

**Problem**: Determining a protein's three-dimensional structure is essential for understanding its function, designing drugs that target it, and engineering proteins with desired properties. Experimental methods (X-ray crystallography, cryo-EM, NMR spectroscopy) are slow, expensive, and not always feasible. Computational methods like AlphaFold2 provide high accuracy but require multiple sequence alignments (MSAs) that take minutes to hours to compute, creating a bottleneck for high-throughput applications.

**How ESMFold helps**: ESMFold predicts protein structure from a single amino acid sequence in seconds, bypassing the MSA computation entirely. The ESM-2 language model backbone has already learned structural patterns from evolutionary data during pre-training, so explicit MSA signals are not needed for many proteins.

**Biological meaning**: The output is a full-atom 3D structure in PDB format, with per-residue confidence scores (pLDDT) indicating which parts of the structure are reliable. A mean pLDDT above 70 generally indicates a usable fold. The predicted TM-score (pTM) provides a global assessment of whether the overall fold topology is correct.

**Practical considerations**: ESMFold trades some accuracy relative to AlphaFold2 for dramatically faster inference. This makes it ideal for screening large protein sets where rapid structure assessment is more important than maximum accuracy.

### Large-Scale Structural Screening

**Problem**: Genome sequencing projects produce millions of predicted protein sequences, but structural characterization lags far behind. Metagenomic studies routinely identify hundreds of thousands of novel protein families with no experimental structure. Understanding even the rough fold of these proteins can provide functional insights.

**How ESMFold helps**: The speed of ESMFold (seconds per prediction) makes it feasible to predict structures for entire proteomes or metagenomes. The authors of the ESMFold paper used it to predict structures for over 600 million metagenomic protein sequences, demonstrating the scalability of the approach.

**Biological meaning**: Even low-confidence predictions (pLDDT 50–70) can reveal fold-level similarity to known structures, enabling functional annotation of previously uncharacterized proteins. High-confidence predictions (pLDDT > 70) can be used as starting points for more accurate methods or experimental validation.

### Structure-Guided Protein Engineering

**Problem**: Protein engineers often need rapid structural feedback when designing mutations or evaluating variant libraries. Traditional structure prediction is too slow for iterative design cycles where hundreds of variants need structural assessment.

**How ESMFold helps**: The fast inference time allows researchers to predict structures for mutant libraries, evaluate structural stability of designed sequences, and filter candidates before expensive experimental testing.

**Biological meaning**: Comparing predicted structures of wild-type and mutant proteins can reveal whether mutations disrupt the protein fold, alter active site geometry, or create steric clashes. Large changes in pLDDT or pTM between wild-type and mutant suggest the mutation may be destabilizing.

## Applied Use Cases

ESMFold has been widely adopted for rapid structure prediction workflows. Selected published applications:

- **Protein-peptide docking** (Zalewski et al., 2025): ESMFold-predicted structures used for protein-peptide docking without MSAs, achieving 20–28% acceptable-quality poses using an efficient polyglycine linker approach.
- **Binding-site prediction** (DeepProSite, Fang et al., 2023): ESMFold-predicted structures fed into a topology-aware graph transformer for protein binding-site prediction, outperforming sequence-only baselines.
- **Protein-engineering ranking** (APPRAISE, Ding et al., 2024): ESMFold structures used to rapidly rank engineered protein variants (AAVs, nanobodies, miniproteins) by target-binding propensity before wet-lab testing.
- **Antimicrobial peptide classification** (Cordoves-Delgado et al., 2024): ESMFold-predicted structures as graph representations for antimicrobial peptide classification, outperforming 20 state-of-the-art methods on a 67,058-peptide dataset.
- **Joint structure and fitness prediction** (SPIRED-Fitness, 2024): ESMFold used as a benchmark for a new end-to-end structure-and-fitness prediction framework, demonstrating 5-fold inference acceleration while maintaining comparable accuracy.

## Related Models

### Predecessor Models

- **ESM-1b** (Rives et al., 2021): The predecessor protein language model. ESMFold uses the improved ESM-2 backbone rather than ESM-1b.
- **AlphaFold2** (Jumper et al., 2021): The MSA-dependent structure prediction method whose folding module architecture inspired ESMFold's structure prediction component. AlphaFold2 remains more accurate but is much slower due to MSA computation.

### Complementary Models

ESMFold is closely related to other models in this catalog:

- **ESM-2**: ESMFold uses the ESM-2 3B language model as its backbone. ESM-2 embeddings (`encode` action) capture the same evolutionary representations that ESMFold uses for structure prediction. Users who need embeddings rather than structures should use ESM-2 directly.
- **ThermoMPNN**: Predicts stability changes (ddG) from structure. Combining ESMFold structure predictions with ThermoMPNN stability estimates provides a more complete characterization of engineered protein variants.

Typical multi-model workflows:
1. Use ESMFold for rapid structure prediction of a candidate set, then use Chai-1 for high-accuracy prediction of the top candidates
2. Use ESM-2 `log_prob` to score variant effects, then use ESMFold to assess structural impact of top-ranked variants
3. Use ESMFold to generate initial structure models, then use MPNN for sequence design on the predicted structures

### Alternative Models

| Alternative | Advantage Over ESMFold | Disadvantage vs ESMFold |
|-------------|----------------------|------------------------|
| AlphaFold2 | Higher accuracy, especially for multi-domain proteins | Requires MSA, much slower inference |
| Chai-1 | Handles ligands, nucleic acids, and diverse complexes; higher accuracy for multi-chain | Slower inference, more resource-intensive |

**When to choose ESMFold**: Use ESMFold when you need fast, single-sequence protein structure predictions for screening, prototyping, or large-scale analysis where speed matters more than maximum accuracy. It is the fastest structure prediction option in this catalog.

**When to choose alternatives**: Use Chai-1 when you need predictions for protein-ligand complexes, RNA/DNA-containing complexes, or when maximum structural accuracy is required. Use AlphaFold2 when you have MSAs available and need the highest accuracy for single-chain or multi-chain protein structures.

## Biological Background

**Protein structure prediction** is one of the grand challenges of computational biology. Proteins are linear chains of amino acids that fold into specific three-dimensional structures dictated by their sequence. The 3D structure determines the protein's function: enzymes have precisely shaped active sites, receptors have complementary binding surfaces, and structural proteins form organized assemblies. Understanding protein structure is therefore central to drug design, enzyme engineering, and fundamental biological research.

**The protein folding problem**: Given an amino acid sequence, predicting the 3D structure the protein adopts under physiological conditions has been studied for over 50 years. The breakthrough came with AlphaFold2 (2020), which achieved near-experimental accuracy by combining multiple sequence alignments (MSAs) -- evolutionary profiles showing which amino acids co-vary at different positions -- with a neural network architecture. However, computing MSAs requires searching large sequence databases, which takes minutes to hours per protein.

**Single-sequence structure prediction**: ESMFold demonstrated that protein language models trained on evolutionary sequence data already learn enough structural information to predict 3D structure without explicit MSA input. The language model's internal representations capture the same co-evolutionary signals that MSAs provide, but compressed into a single forward pass. This is analogous to how a human expert who has studied thousands of protein structures can make reasonable fold predictions from sequence alone.

**Key terminology**:
- **pLDDT (predicted Local Distance Difference Test)**: A per-residue confidence score (0-100) estimating how accurately the local structure around each residue is predicted. Values above 70 generally indicate reliable predictions.
- **pTM (predicted TM-score)**: A global score (0-1) estimating the overall fold correctness. Values above 0.5 indicate a broadly correct fold topology; values above 0.8 indicate high-confidence predictions.
- **PDB format**: The standard text format for representing 3D molecular structures, specifying atomic coordinates, chain identifiers, and metadata.
- **MSA (Multiple Sequence Alignment)**: An alignment of a query protein against evolutionarily related sequences from databases like UniRef. Co-varying positions in the MSA reveal structural contacts.
- **Recycling**: Iterative refinement of structure predictions by feeding outputs back through the model. ESMFold uses 4 recycles by default to progressively improve the predicted structure.

---

*See also: [README.md](README.md) for API reference | [MODEL.md](MODEL.md) for technical details*
