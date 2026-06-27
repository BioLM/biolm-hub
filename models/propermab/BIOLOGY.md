# ProperMAB -- Biological Context

## Molecule Coverage

### Primary Molecule Type(s)

ProperMAB is designed exclusively for **antibodies** -- specifically the variable fragment (Fv) domain consisting of paired heavy chain (VH) and light chain (VL) sequences. The framework extracts 34 biophysical features that characterize the molecular surface properties relevant to antibody developability.

The features are computed from both the amino acid sequence and the predicted 3D structure (via ABodyBuilder2). Sequence features depend on isotype (IgG1, IgG2, IgG4) and light chain type (kappa, lambda), while structure features depend on the predicted 3D conformation.

### Cross-Applicability

| Molecule Type | Applicability | Evidence | Caveats |
|--------------|---------------|----------|---------|
| Conventional antibodies (VH/VL) | High | Primary target; validated on 135 mAbs | Requires both heavy and light chain sequences |
| IgG1 antibodies | High | HIC RT correlation r=0.71 | Strongest validation |
| IgG4 antibodies | Moderate | Viscosity correlation rho=0.48 | Complex viscosity mechanisms |
| IgG2 antibodies | Moderate | Supported via isotype parameter | Less extensively validated |
| Nanobodies (VHH) | Not applicable | Requires paired VH/VL input | Use ImmuneBuilder for structure prediction |
| Non-antibody proteins | Not applicable | Antibody-specific features (CDR, Fv, Fc) | Not meaningful for other proteins |
| Bispecific antibodies | Low | Not validated | Each arm would need separate feature extraction |

## Biological Problems Addressed

### Antibody Developability Assessment

**Biological context**: Therapeutic antibody candidates must not only bind their target effectively but also possess acceptable biophysical properties for manufacturing, formulation, and clinical use. These "developability" properties include:

- **Hydrophobic interaction chromatography (HIC) retention time**: Measures surface hydrophobicity; higher RT correlates with aggregation risk and poor formulation stability
- **High-concentration viscosity**: Antibodies for subcutaneous injection (typically 100-200 mg/mL) must have viscosity <20 cP for syringeability
- **Aggregation propensity**: Aggregates can trigger immunogenic responses and reduce shelf life
- **Solubility**: Poor solubility limits achievable concentrations

Experimentally measuring these properties for thousands of candidates is expensive and time-consuming. ProperMAB enables computational pre-screening by extracting features that correlate with these properties.

**How ProperMAB helps**: The 34 biophysical features serve as inputs to machine learning models trained on experimental developability data. For example, an ElasticNet model using ProperMAB features achieves Pearson r=0.71 for HIC RT prediction on 135 clinical antibodies.

**Output interpretation**: Features are numerical descriptors, not direct predictions. Users must train their own ML models using these features combined with experimental measurements of the specific property of interest.

### HIC Retention Time Prediction

**Biological context**: HIC RT is a widely used surrogate for surface hydrophobicity, which is the primary driver of antibody self-association, aggregation, and non-specific binding. Antibodies with high surface hydrophobicity tend to have:
- Higher aggregation rates during manufacturing
- Poorer stability in formulation
- Increased non-specific binding in vivo (reduced half-life)

**Key features**: `hyd_patch_area_cdr` (hydrophobic patches near CDRs, r=0.60 as single predictor), `aromatic_asa` (aromatic surface area, r=0.55), `heiden_score` (surface hydrophobic potential, r=0.54). Multi-feature models using 23/35 features achieve r=0.71.

### High-Concentration Viscosity Prediction

**Biological context**: Subcutaneous injection of therapeutic antibodies requires high concentrations (100-200 mg/mL). At these concentrations, reversible self-association can cause dramatic viscosity increases, making the formulation difficult to inject. Viscosity is driven by electrostatic and hydrophobic interactions between antibody molecules in solution.

**Key features**: Charge asymmetry features (`dipole_moment`, `Fv_chml`) are most predictive for IgG4 viscosity. Notably, the SCM score (frequently cited as a viscosity predictor in earlier literature) was found NOT to be predictive in the larger IgG4 dataset (rho=0.12), highlighting the importance of ProperMAB's comprehensive feature set.

## Applied Use Cases

### Published Validation

ProperMAB was validated by Li et al. (2025) on multiple datasets:

- **Jain et al. 2017 (PNAS)**: 135 clinical-stage antibodies with standardized HIC RT measurements
- **Regeneron IgG4 dataset**: 58 IgG4 antibodies with high-concentration viscosity measurements (largest published IgG4 viscosity dataset)
- **OAS (Observed Antibody Space)**: 10,000 antibodies for sequence-based feature prediction training

### Anticipated Use Cases

- **Early-stage candidate selection**: Screening thousands of antibody sequences from NGS campaigns for developability risks before committing to experimental characterization
- **Lead optimization**: Identifying which surface properties of a lead candidate contribute to poor developability, guiding rational mutagenesis
- **Formulation development**: Using feature profiles to predict which candidates will be amenable to high-concentration formulation
- **Patent landscape analysis**: Characterizing the biophysical property space of competitor antibodies

<!-- TODO: Add citations for applied studies using ProperMAB as they are published -->

## Related Models

### Predecessor Tools

- **TAP (Therapeutic Antibody Profiler)**: Rule-based developability flags using 5 parameters (CDR-H3 length, patches of surface hydrophobicity/positive charge/negative charge, total charge). Simpler but less predictive than ProperMAB.
- **SCM (Spatial Charge Map)**: Single-feature charge asymmetry score. ProperMAB showed SCM is not predictive for IgG4 viscosity (rho=0.12).

### Complementary Models

- **ImmuneBuilder / ImmuneFold**: Provide alternative structure predictions that could be used as input. Currently ProperMAB uses ABodyBuilder2 internally.
- **ESM2**: Protein language model embeddings can complement ProperMAB's biophysical features for ML models.
- **CamSol**: Sequence-based solubility predictor that addresses a related but different aspect of developability.

### Alternative Approaches

| Alternative | Advantage over ProperMAB | Disadvantage vs ProperMAB |
|-------------|--------------------------|---------------------------|
| TAP score | Instant; no structure needed | Only 5 rule-based parameters; less predictive |
| SCM score | Single interpretable feature | Not predictive for IgG4 viscosity |
| Commercial platforms | Validated pipelines; regulatory support | Closed-source; expensive |
| Sequence-predicted features | 1000x faster (no structure needed) | ~5% performance drop vs structure-based |

## Biological Background

### Antibody Developability

Developability refers to the collection of biophysical properties that determine whether an antibody can be successfully manufactured, formulated, and administered as a therapeutic. Key properties include:

- **Expression yield**: How much antibody is produced per liter of cell culture
- **Purification efficiency**: How well the antibody behaves on Protein A and polishing columns
- **Stability**: Thermal stability (Tm), conformational stability, colloidal stability
- **Aggregation**: Propensity to form irreversible aggregates during storage
- **Viscosity**: Solution viscosity at high concentrations (relevant for subcutaneous injection)
- **Self-association**: Reversible self-association that affects PK/PD and viscosity
- **Non-specific binding**: Off-target binding that reduces efficacy and half-life

These properties are primarily determined by the surface properties of the antibody Fv domain, particularly the CDR regions that are exposed to solvent and can mediate intermolecular interactions.

### Surface Hydrophobicity and Aggregation

Exposed hydrophobic patches on the antibody surface are the primary drivers of aggregation, non-specific binding, and poor formulation stability. In solution, hydrophobic patches on different antibody molecules interact, leading to reversible self-association (at low concentrations) or irreversible aggregation (at high concentrations or under stress).

ProperMAB quantifies surface hydrophobicity through multiple complementary features:
- `hyd_asa` / `hyd_patch_area`: Total hydrophobic surface area
- `hyd_patch_area_cdr`: Hydrophobic patches specifically near CDR regions (the strongest HIC RT predictor)
- `heiden_score`: Surface hydrophobic potential mapped from electrostatic calculations
- `hyd_moment`: Hydrophobic moment (amphiphilicity measure)

### Charge Distribution and Viscosity

At high antibody concentrations (100-200 mg/mL), electrostatic interactions between molecules dominate solution behavior. The spatial distribution of charged residues on the surface determines:
- Whether molecules attract or repel each other
- The magnitude of the electric dipole moment (charge asymmetry)
- Whether concentrated solutions are viscous or free-flowing

ProperMAB captures charge distribution through features like `dipole_moment`, `Fv_chml` (VH-VL charge difference), and spatial charge clustering indices (ANN, Ripley's K).

### Spatial Point Pattern Analysis

ProperMAB introduces spatial statistics borrowed from geographic information science:
- **Average Nearest Neighbor (ANN) index**: Measures whether charged/aromatic residues are clustered (<1) or dispersed (>1) on the surface. Clustered patches create stronger local interactions.
- **Ripley's K function**: Measures spatial correlation at a defined distance (6 Angstroms). K ratios >1 indicate more clustering than random placement.

These features capture information about the spatial organization of surface properties that is missed by simple aggregate statistics like total charge or hydrophobic area.

---

*See also: [README.md](README.md) for API reference | [MODEL.md](MODEL.md) for technical details*
