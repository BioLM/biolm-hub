# TEMPRO -- Biological Context

## Molecule Coverage

### Primary Molecule Type(s)

TEMPRO is designed exclusively for nanobodies (also called VHH antibodies or single-domain antibodies). Nanobodies are the variable domains of heavy-chain-only antibodies found naturally in camelids (camels, llamas, alpacas). They are typically 100--160 amino acids in length and fold into a single immunoglobulin domain with three complementarity-determining regions (CDRs).

The model's sequence length constraints (100--160 residues) are specifically matched to the typical nanobody length range.

### Cross-Applicability

| Molecule Type | Applicability | Evidence | Caveats |
|--------------|---------------|----------|---------|
| Nanobodies (VHH) | High | Primary training target | Best performance within 100--160 AA |
| Single-domain antibodies (sdAb) | Moderate | Similar fold to nanobodies | Shark VNARs may differ from camelid VHH |
| Conventional antibodies (VH/VL) | Low | Different fold and stability profile | Use antibody-specific tools instead |
| General proteins | Not applicable | Model rejects sequences outside 100--160 AA | Use TemBERTure for general protein Tm |

## Biological Problems Addressed

### Nanobody Thermal Stability Prediction

Nanobodies are increasingly important as therapeutic and diagnostic agents due to their small size (~15 kDa), high stability, ease of production, and ability to bind epitopes inaccessible to conventional antibodies. However, thermal stability varies significantly among nanobodies (typical Tm range: 40--90+ degrees C), and this property critically affects their developability, shelf life, and performance in demanding applications.

Experimental Tm determination requires expression, purification, and biophysical characterization -- a process that can take weeks per candidate. TEMPRO enables rapid computational screening of nanobody Tm from sequence alone, facilitating:

- **Therapeutic nanobody development**: Prioritizing thermostable candidates early in the pipeline
- **Library screening**: Rapidly assessing Tm of large nanobody libraries from phage/yeast display
- **Engineering guidance**: Evaluating stability impact of CDR grafting or framework mutations

## Applied Use Cases

TEMPRO has been benchmarked and used as a baseline in several independent studies:

- **NanoMelt (Ramon et al., 2025, MAbs)** directly benchmarks against TEMPRO for nanobody Tm prediction. NanoMelt, trained on 640 nanobodies using ESM-1b + SVR, achieves Pearson 0.751 on an external test set of 83 samples vs TEMPRO's R2=0.67 on a 6-sample external set. The comparison validates TEMPRO's problem formulation while demonstrating room for improvement with larger datasets.

- **Murakami et al. (2025, bioRxiv)** performs mechanistic interpretability analysis of fine-tuned protein language models for nanobody thermostability and directly benchmarks against TEMPRO. A smaller fine-tuned ESM-2 8M model achieves RMSE=5.402 degrees C, outperforming TEMPRO's best ESM-2 15B-backed configuration (RMSE=5.661 degrees C). Uses Sparse Autoencoders to interpret the learned thermostability features.

- **NBsTem (ACS Applied Materials & Interfaces, 2026)** benchmarks against TEMPRO on the Tm-118 external test set. NBsTem achieves MAE=2.30 degrees C and R=0.83, significantly outperforming TEMPRO (MAE=5.29 degrees C, R=0.66). NBsTem combines experimental Tm data with MD-simulation-derived theoretical indicators.

- **NbBench (Zhang and Tsuda, 2025, arXiv:2505.02022)** — the first comprehensive nanobody benchmark suite — collects thermostability data from NbThermo, TEMPRO, and NanoMelt datasets. Evaluates 11 protein language models on thermostability regression, finding best Spearman correlation ~0.59 (AntiBERTa2). TEMPRO's dataset is used as a core data source in the benchmark.

## Related Models

### Predecessor Models

TEMPRO builds on ESM2 (Lin et al., 2023) as its embedding backbone. The ESM2 protein language model provides the sequence representations that TEMPRO's Keras head uses for Tm prediction.

### Complementary Models

- **ESM2**: Provides the embeddings used by TEMPRO. Must be deployed as a prerequisite.
- **TemBERTure**: General-purpose protein thermostability prediction. Use for proteins outside the nanobody length range.
- **ThermoMPNN**: Structure-based stability change prediction. Use when a 3D structure is available and you want per-mutation ddG values.

### Alternative Models

| Alternative | Advantage over TEMPRO | Disadvantage |
|-------------|----------------------|--------------|
| TemBERTure | Works on any protein, not just nanobodies | Not specialized for nanobodies; different Tm accuracy |
| Nano-HKU (if available) | Anticipated: may offer nanobody-specific features | Not available in the catalog |

## Biological Background

Nanobodies are the smallest naturally occurring antigen-binding fragments, derived from the variable domain (VHH) of heavy-chain-only antibodies unique to camelids. Unlike conventional antibodies that require pairing of heavy and light chain variable domains (VH and VL), nanobodies function as independent single-domain binding units.

Key structural features of nanobodies:
- **Framework regions (FR1--FR4)**: Provide the structural scaffold, analogous to conventional antibody frameworks
- **Complementarity-determining regions (CDR1--CDR3)**: Form the antigen-binding surface; CDR3 is often elongated in nanobodies compared to VH domains
- **Hallmark residues**: Hydrophilic substitutions at the former VH-VL interface (positions 37, 44, 45, 47) that confer solubility without a light chain partner

Thermal stability of nanobodies is influenced by framework composition, CDR loop characteristics, and intramolecular interactions. The Tm -- the temperature at which 50% of the nanobody population is unfolded -- is a key metric for developability assessment. Nanobodies with Tm values above 60--70 degrees C are generally considered suitable for therapeutic development.

---

*See also: [README.md](README.md) for API reference | [MODEL.md](MODEL.md) for technical details*
