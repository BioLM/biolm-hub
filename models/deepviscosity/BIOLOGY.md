# DeepViscosity -- Biological Context

## Molecule Coverage

### Primary Molecule Type(s)

DeepViscosity is designed exclusively for **monoclonal antibodies (mAbs)**, specifically their variable fragment (Fv) regions. It takes paired heavy chain variable (VH) and light chain variable (VL) sequences as input.

**Scope**:
- Therapeutic monoclonal antibodies (IgG format)
- VH and VL Fv domains only (excludes constant regions, Fc, hinge)
- Sequences must be alignable to IMGT numbering via ANARCI
- All organism sources are theoretically supported, but the training data is from humanized/human therapeutic mAbs

**Performance considerations**:
- Best performance on antibodies similar to the AstraZeneca training set (humanized/human IgGs)
- Performance degrades on antibody sets with very high internal sequence homology
- Non-antibody proteins (enzymes, receptors) cannot be processed -- ANARCI alignment will fail

### Cross-Applicability

| Molecule Type | Applicability | Evidence | Caveats |
|--------------|---------------|----------|---------|
| Therapeutic mAbs (IgG1/2/4) | High | Primary training domain | Fc effects not captured |
| Biosimilar antibodies | High | Same Fv architecture | Trained on innovator mAbs; biosimilar-specific behavior untested |
| Bispecific antibodies | Low | Not tested | Single Fv pair input only; cannot model bispecific geometry |
| Nanobodies (VHH) | None | Not applicable | Requires paired VH/VL; single-domain antibodies not supported |
| Fab fragments | Moderate | Fv region is shared | Viscosity of Fab vs full IgG may differ due to missing Fc |
| Non-antibody proteins | None | Not applicable | ANARCI alignment requires antibody variable domains |

## Biological Problems Addressed

### Problem 1: High-Concentration Antibody Viscosity Screening

**Why this matters**: Therapeutic antibodies are typically administered as subcutaneous injections at high concentrations (100-200 mg/mL) to deliver sufficient drug in a small injection volume (1-2 mL). At these concentrations, many mAbs exhibit dramatically increased viscosity due to reversible self-association of the antibody molecules. High viscosity (>20 cP) causes:

- Difficulty in syringe-based injection (patient compliance, injection pain)
- Manufacturing challenges (filtration, fill-finish, pump limitations)
- Formulation instability and aggregation risk
- Increased development cost and timeline

**Traditional approaches**: Viscosity is measured experimentally using cone-and-plate rheometry or microfluidic viscometers, which require purified protein at scale (milligrams to grams). This is expensive and slow, particularly in early-stage discovery when hundreds of candidates may need screening.

**How DeepViscosity helps**: From just the VH and VL amino acid sequences, DeepViscosity predicts whether an antibody is likely to have low (<=20 cP) or high (>20 cP) viscosity at 150 mg/mL. This enables:

- **Early-stage triage**: Screen antibody candidates computationally before any protein expression
- **Lead optimization guidance**: Identify sequence features driving high viscosity via DeepSP spatial properties
- **Reduced experimental burden**: Focus expensive viscosity measurements on borderline or high-priority candidates

**Accuracy**: 87.5% on the independent Lai_mAb_16 test set, with ensemble uncertainty estimates (probability_std) indicating prediction confidence.

### Problem 2: Antibody Engineering for Reduced Viscosity

**Why this matters**: When a promising therapeutic antibody exhibits high viscosity, engineers must modify the sequence to reduce viscosity while preserving binding affinity and other functional properties. This is typically done through iterative mutagenesis -- an expensive trial-and-error process.

**How DeepViscosity helps**: The optional DeepSP feature output (30 spatial properties across 10 antibody domains) reveals which regions contribute most to predicted viscosity:

- **SAP_pos** (Spatial Aggregation Propensity, positive): Hydrophobic patches that promote self-association
- **SCM_neg** (Spatial Charge Map, negative): Negatively charged surface patches
- **SCM_pos** (Spatial Charge Map, positive): Positively charged surface patches

By examining which CDR or framework region has the highest SAP_pos or most extreme charge features, engineers can prioritize mutation sites to reduce viscosity. For example, high SAP_pos in CDR H3 suggests that hydrophobic mutations in that loop may improve viscosity without disrupting the binding paratope in other CDRs.

**Limitations**: DeepViscosity predicts the effect of the current sequence but cannot directly suggest specific mutations. It should be used as a scoring function within a broader engineering workflow, not as a standalone design tool.

## Applied Use Cases

### Use Case 1: Pre-Clinical mAb Candidate Screening

**Source**: Kalejaye et al. "Accelerating high-concentration monoclonal antibody development with large-scale viscosity data and ensemble deep learning." *mAbs* (2025). [DOI](https://doi.org/10.1080/19420862.2025.2483944)

The primary paper demonstrates using DeepViscosity to screen mAb candidates before experimental viscosity measurement. On the Lai_mAb_16 independent test set, the model correctly classified 14 of 16 antibodies, identifying high-viscosity candidates that would otherwise require weeks of experimental characterization. The ensemble approach (102 models) provides uncertainty estimates that flag borderline predictions for experimental follow-up.

### Use Case 2: Formulation Development Prioritization (Anticipated)

While not explicitly demonstrated in the published literature, DeepViscosity predictions could guide formulation development prioritization. Antibodies predicted as low-viscosity with high confidence may proceed directly to standard formulation screens, while those predicted as high-viscosity may require specialized formulation strategies (e.g., viscosity-reducing excipients like arginine or NaCl) from the outset. This could reduce development timelines by weeks to months per candidate.

## Related Models

### Predecessor Models

- **DeepSP** (Rawat et al. 2019): The CNN feature extraction component of DeepViscosity. DeepSP predicts spatial aggregation propensity (SAP) and spatial charge map (SCM) features from sequence alone, replacing the need for 3D structure-based calculations. DeepViscosity extends DeepSP by adding an ensemble classification layer on top of these features.

### Complementary Models

No models currently on the BioLM platform are direct complements for a viscosity prediction workflow. Potential future integrations:

- **Structure prediction** (ABodyBuilder3, ESMFold): Generate 3D structures for mAbs predicted as high-viscosity, enabling physics-based analysis of self-association interfaces
- **Inverse folding** (ProteinMPNN): Design sequence variants that maintain fold stability while reducing predicted viscosity

### Alternative Models

| Alternative | Advantage over DeepViscosity | Disadvantage |
|-------------|------------------------------|--------------|
| CamSol (not on BioLM) | General solubility predictor; structure-aware | Not viscosity-specific; requires 3D coordinates |
| TAP (not on BioLM) | Multi-property developability score | Requires 3D homology model; coarser viscosity proxy |
| Sharma et al. ML models | Trained on larger proprietary datasets | Not publicly available; no ensemble uncertainty |

DeepViscosity is currently the only open-source, sequence-only viscosity classifier with ensemble uncertainty estimates.

## Biological Background

### Antibody Structure

Antibodies (immunoglobulins) are Y-shaped proteins produced by the immune system to recognize foreign molecules (antigens). A typical IgG antibody consists of two heavy chains and two light chains. The antigen-binding region is formed by the **variable fragment (Fv)**, which comprises:

- **VH (Variable Heavy)**: The variable domain of the heavy chain (~110-130 residues)
- **VL (Variable Light)**: The variable domain of the light chain (~110-130 residues)

Within each variable domain, three hypervariable loops called **complementarity-determining regions (CDRs)** form the antigen-binding site (paratope). CDR H3 is typically the most variable and often dominant in antigen recognition. The remaining residues form the **framework regions** that maintain the structural scaffold.

### IMGT Numbering

The International ImMunoGeneTics (IMGT) numbering system provides a standardized way to number antibody residues across species and germlines. This is critical for DeepViscosity because the model requires a fixed-length representation: by aligning all antibodies to IMGT positions, diverse sequences become directly comparable. ANARCI is the tool that performs this alignment using hidden Markov models (HMMs).

### Viscosity at High Concentration

At therapeutic concentrations (100-200 mg/mL), antibody solutions can become highly viscous due to **reversible self-association**. This is driven by:

- **Electrostatic interactions**: Charge patches on the antibody surface attract neighboring molecules
- **Hydrophobic interactions**: Exposed hydrophobic regions (measured by SAP) promote clustering
- **Fab-Fab and Fab-Fc interactions**: Both intra- and inter-molecular contacts contribute

The 20 cP threshold used by DeepViscosity is a commonly cited upper limit for subcutaneous injectability. Solutions above this viscosity are difficult to push through narrow-gauge needles (typically 25-27 gauge) used for patient self-administration.

### Why This Matters for Drug Development

Approximately 80% of approved monoclonal antibody therapies use subcutaneous injection, which requires high concentration formulations. Viscosity is one of the most common developability liabilities, affecting:

- **Patient compliance**: High-viscosity injections are painful and slow
- **Manufacturing**: Filtration, filling, and pumping become difficult above 20-50 cP
- **Stability**: Self-association at high concentration can promote irreversible aggregation
- **Cost**: Late-stage reformulation or sequence redesign to address viscosity can cost millions and delay timelines by 6-12 months

Early computational screening with tools like DeepViscosity can identify viscosity risks before any protein is expressed, potentially saving significant development time and cost.

---

*See also: [README.md](README.md) for API reference | [MODEL.md](MODEL.md) for technical details*
