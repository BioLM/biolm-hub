# ESMStabP -- Biological Context

## Molecule Coverage

### Primary Molecule Type(s)

ESMStabP is designed for single-chain proteins from all domains of life. It predicts melting temperature (Tm), the temperature at which 50% of a protein population is unfolded. The model was trained on a combined dataset from DeepStabP, DeepTM, and TemBERTure, which includes proteins from:

- **Thermophilic organisms** (growth temperature > 60 degrees C): archaeal and bacterial proteins from hot springs, hydrothermal vents
- **Mesophilic organisms** (growth temperature 20-45 degrees C): including human, E. coli, and common model organisms
- **Psychrophilic organisms** (growth temperature < 20 degrees C): cold-adapted organisms from polar and deep-sea environments

The model handles globular, soluble proteins best. Performance may degrade for:
- Membrane proteins (stability depends on lipid environment, not captured)
- Intrinsically disordered proteins (no stable folded state to "melt")
- Very large multi-domain proteins (mean-pooled embedding averages over domains)
- Maximum sequence length: 1022 residues (ESM2 limit)

### Cross-Applicability

| Molecule Type | Applicability | Evidence | Caveats |
|--------------|---------------|----------|---------|
| Globular enzymes | High | Training data includes diverse enzymes | Best when growth_temp is provided |
| Industrial enzymes | High | Thermostability is a key engineering target | Context-blind to formulation conditions |
| Antibodies | Low-Moderate | Can predict Tm of Fab/scFv fragments | Not trained on antibody-specific data; ignores Fc stability |
| Peptides | Low | Short sequences produce noisy embeddings | Consider peptide-specific stability models |
| Membrane proteins | Low | Stability depends on detergent/lipid environment | Not modeled; predictions unreliable |

## Biological Problems Addressed

### Problem 1: Protein Thermostability Prediction

**Why it matters**: Protein thermal stability -- quantified as melting temperature (Tm) -- is a fundamental biophysical property that determines whether a protein remains functional under given conditions. Proteins that unfold at temperatures below their operating environment lose function, aggregate, and can trigger immune responses (for therapeutics) or process failure (for industrial enzymes).

**Experimental approaches**: Differential scanning calorimetry (DSC), differential scanning fluorimetry (DSF/Thermofluor), circular dichroism (CD) thermal melts, and thermo-proteome profiling (TPP) mass spectrometry. These methods are accurate but require purified protein and are low-throughput (DSC: ~1 protein/hour; TPP: proteome-scale but expensive).

**How ESMStabP addresses it**: Given a protein sequence (and optionally the organism's optimal growth temperature and experimental condition), ESMStabP predicts Tm in degrees Celsius. This enables:
- Rapid screening of thousands of candidate sequences before expression
- Prioritization of variants for experimental validation
- Integration into computational protein design pipelines

**Accuracy context**: MAE of ~3-4 degrees C on the test set. For comparison, experimental DSC measurements typically have reproducibility of +/-0.5-1 degrees C between labs. The model is useful for ranking and screening but not for replacing experimental measurement when precise Tm values are needed.

### Problem 2: Enzyme Engineering for Thermostability

**Why it matters**: Industrial enzymes (for detergents, food processing, biofuels, pharmaceuticals) must function at elevated temperatures for process efficiency and shelf life. Engineering thermostable enzyme variants traditionally requires directed evolution (labor-intensive, months of work) or rational design (requires structural knowledge).

**How ESMStabP addresses it**: Researchers can computationally screen libraries of enzyme variants by predicting the Tm of each mutant sequence. Variants predicted to have higher Tm can be prioritized for experimental testing, substantially reducing the experimental search space.

**Practical workflow**:
1. Generate a library of mutant sequences (e.g., saturation mutagenesis at key positions)
2. Predict Tm for each variant using ESMStabP
3. Rank variants by predicted Tm
4. Experimentally validate the top-N candidates
5. Iterate with additional rounds if needed

### Problem 3: Biologic Drug Stability Assessment

**Why it matters**: Therapeutic proteins (antibodies, enzymes, peptide drugs) must remain stable during manufacturing, storage, and administration. Low thermal stability correlates with aggregation propensity, reduced shelf life, and immunogenicity. Regulatory agencies require stability data for drug approval.

**How ESMStabP addresses it**: Early-stage computational Tm screening can flag candidates with potentially low stability before expensive manufacturing and formulation studies. This is particularly valuable in the discovery phase when hundreds of candidates are being evaluated.

**Limitations for this use case**: The model does not account for formulation conditions (pH, excipients, ionic strength) that strongly influence therapeutic protein stability. It provides a sequence-intrinsic stability estimate only.

## Applied Use Cases

The ESMStabP paper (bioRxiv 2025.02.18.638450) is recent and applied literature using this specific model is not yet available. However, the general approach of using protein language model embeddings for thermostability prediction has been applied in several contexts:

### Use Case 1: High-Throughput Enzyme Variant Screening

Computational screening of enzyme variant libraries for thermostability is a common application of Tm prediction models. ESMStabP's fast CPU-only inference (after embedding extraction) makes it suitable for screening libraries of 10,000+ variants in minutes, compared to weeks of experimental characterization.

### Use Case 2: Protein Design Pipeline Integration

Thermostability prediction can be integrated as a filter in generative protein design pipelines. After generating candidate sequences (e.g., via ProteinMPNN or other inverse folding models), ESMStabP can filter out candidates predicted to be thermally unstable, reducing the experimental validation burden.

## Related Models

### Predecessor Models

- **DeepSTABp**: Neural network-based Tm prediction using ProtT5 embeddings. ESMStabP outperforms it on matched benchmarks (R-squared 0.94 vs 0.81).
- **ProTstab2**: Machine learning-based stability prediction. Lower accuracy than ESMStabP (R-squared 0.51 vs 0.94).
- **TemBERTure**: BERT-based thermostability classification. Contributed training data but is outperformed by ESMStabP's regression approach.

### Complementary Models

- **ESM2-650M** (`esm2-650m`): Provides the embedding features that ESMStabP uses. ESM2 must be deployed for ESMStabP to function. ESM2 embeddings are also useful for many other downstream tasks.
- **CamSol**: Predicts protein solubility. Solubility and thermostability are correlated but distinct properties -- using both provides a more complete biophysical profile.

### Alternative Models

| Alternative | Advantage over ESMStabP | Disadvantage |
|-------------|------------------------|--------------|
| DeepSTABp | Uses ProtT5 (may capture different features) | Lower accuracy (R-squared 0.81 vs 0.94) |
| ProTstab2 | Simpler architecture | Substantially lower accuracy (R-squared 0.51) |
| Experimental DSC/DSF | Ground-truth measurement | Low throughput, requires purified protein |

## Biological Background

### Protein Thermostability

Proteins are linear chains of amino acids that fold into specific three-dimensional structures to perform biological functions. This folded state is only marginally stable -- the free energy difference between folded and unfolded states is typically just 5-15 kcal/mol, equivalent to a few hydrogen bonds.

**Melting temperature (Tm)** is the temperature at which 50% of a protein population is unfolded. It is the most widely used single metric for protein thermal stability. Tm values range from below 0 degrees C (extremely unstable) to above 120 degrees C (hyperthermophilic proteins). Most mesophilic proteins have Tm values between 40-70 degrees C.

### Determinants of Thermostability

Protein thermostability is determined by a combination of factors:

- **Hydrophobic core packing**: Tighter hydrophobic cores increase stability
- **Salt bridges and hydrogen bonds**: Electrostatic interactions stabilize the folded state
- **Disulfide bonds**: Covalent crosslinks reduce entropy of the unfolded state
- **Proline residues**: Reduce backbone flexibility, increasing stability
- **Surface charge distribution**: Optimized charge networks in thermophilic proteins
- **Organism adaptation**: Proteins from thermophilic organisms have evolved multiple stabilizing features simultaneously

### Optimal Growth Temperature (OGT)

The optimal growth temperature of the source organism is strongly correlated with protein Tm. This is why ESMStabP's Model 2 (which includes OGT as a feature) substantially outperforms Model 1 (embedding only). Thermophilic organisms (OGT > 60 degrees C) have evolved proteomes with systematically higher Tm values. The model uses OGT to derive binary thermophilic/nonThermophilic flags that help calibrate predictions.

### Practical Significance

Thermostability prediction is relevant to:

- **Industrial biotechnology**: Enzymes for laundry detergents, food processing, and biofuel production must withstand elevated temperatures
- **Pharmaceutical development**: Therapeutic proteins must be stable during manufacturing, shipping, and storage (typically 2-8 degrees C, but excursions to 25-40 degrees C occur)
- **Protein engineering**: Understanding stability enables rational design of more robust protein variants
- **Evolutionary biology**: Tm patterns across species reveal adaptation strategies to different thermal environments

---

*See also: [README.md](README.md) for API reference | [MODEL.md](MODEL.md) for technical details*
