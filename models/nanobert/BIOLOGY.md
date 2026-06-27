# NanoBERT -- Biological Context

## Molecule Coverage

### Primary Molecule Type(s)

NanoBERT is trained exclusively on nanobody (VHH) sequences -- the variable domains of camelid heavy-chain-only antibodies. The model operates at the amino acid level and processes single-domain sequences of up to 154 residues.

NanoBERT handles different nanobody structural elements:

- **Framework regions (FWR1-4)**: Excellent representation quality. The conserved beta-sheet scaffold of VHH domains is well-captured.
- **CDR1 and CDR2**: Good representation quality. These loops follow canonical structure classifications similar to conventional VH domains.
- **CDR3**: Good representation quality despite high diversity. Nanobody CDR3 loops are often longer than conventional VH CDR3 loops, and NanoBERT is specifically designed to capture this extended diversity.
- **Hallmark residues**: The model captures the characteristic VHH framework substitutions (e.g., positions 37, 44, 45, 47 in Kabat numbering) that distinguish nanobodies from conventional VH domains.

### Cross-Applicability

| Molecule Type | Applicability | Evidence | Caveats |
|--------------|---------------|----------|---------|
| Camelid nanobodies (VHH) | High | Primary training target | Max 154 residues |
| Shark VNARs | Low--Moderate | Single-domain antibodies with some structural similarity | Not trained on VNAR data; limited applicability |
| Conventional VH domains | Low | Different sequence patterns from VHH | Hallmark residue positions differ; use IgBERT instead |
| Conventional paired antibodies | Not applicable | Single-domain model | Use AbLang2 or IgBERT |
| General proteins | Not applicable | Nanobody-specialized model | Use ESM-2 |

## Biological Problems Addressed

### Nanobody Mutational Landscape Navigation

**Problem**: Nanobody engineering requires understanding which amino acid substitutions are tolerated at each position in a VHH sequence. The mutational landscape is high-dimensional (20^L possible sequences for length L), and experimental exploration is costly and incomplete. Germline gene-based analysis can bias exploration toward germline-similar sequences, potentially missing functional solutions.

**How NanoBERT helps**: The `encode` action produces embeddings that map nanobody sequences into a continuous space where functionally similar nanobodies are proximal. The `predict_log_prob` action scores sequences for plausibility, enabling efficient exploration of the mutational landscape. The gene-agnostic design ensures the model does not bias predictions toward particular germline families.

**Biological meaning**: NanoBERT embeddings capture the biophysical and evolutionary constraints on nanobody sequences. Positions with narrow predicted distributions (high confidence predictions) are likely structurally or functionally constrained, while positions with broad distributions are more tolerant of substitution. This information guides rational mutagenesis and library design.

### Nanobody Sequence Completion

**Problem**: Nanobody sequences obtained from phage display selections, NGS, or single-cell sequencing may have missing or uncertain residues. Recovering these positions using nanobody-specific context is important for downstream expression and characterization.

**How NanoBERT helps**: The `generate` action takes sequences with `*` placeholder characters and predicts the most likely amino acid at each position using the full sequence context. Because NanoBERT is trained specifically on nanobody sequences, its predictions reflect VHH-specific constraints rather than general protein or conventional antibody patterns.

**Biological meaning**: Restored residues reflect the model's estimate of the most structurally and functionally plausible amino acid given the nanobody context. This is particularly valuable for CDR3 restoration, where the extended length and diversity of nanobody CDR3 loops require specialized knowledge.

### Nanobody Sequence Scoring

**Problem**: Evaluating whether an engineered nanobody sequence is biophysically plausible -- will it fold, be stable, and express well -- requires scoring against known nanobody sequence patterns.

**How NanoBERT helps**: The `predict_log_prob` action computes total sequence log-probability by summing log P(residue_i | context) across all positions. This provides a single scalar score for nanobody sequence plausibility.

**Biological meaning**: Higher (less negative) log-probability scores indicate sequences more consistent with natural nanobody patterns. Scores can be used to compare wild-type vs mutant nanobodies, rank designed variants, or filter libraries for developability.

## Applied Use Cases

NanoBERT is applicable to nanobody engineering and design workflows:

- **Nanobody library design**: Score designed sequences for VHH-specific plausibility (published)
- **Mutational scanning in silico**: Evaluate all single-point mutations at each position to identify tolerated substitutions (published)
- **CDR3 design**: Navigate the extended CDR3 sequence space specific to nanobodies (published)
- **Nanobody developability prediction**: Use embeddings as features for predicting expression, stability, and aggregation (anticipated)
- **Nanobody clustering**: Group nanobody repertoires by functional similarity using embedding distance (anticipated)

## Related Models

### Complementary Models

- **SADIE**: Use for nanobody numbering and annotation (SADIE supports single-domain antibodies)
- **ESM-2**: Use as a general-purpose protein embedding for comparison with NanoBERT-specific embeddings
- **IgBERT (unpaired)**: Alternative for VHH sequences, though not nanobody-specialized

Typical multi-model workflows:
1. Use SADIE to number and annotate nanobody sequences
2. Use NanoBERT `encode` to generate VHH-specific embeddings
3. Use NanoBERT `predict_log_prob` to score engineered variants

### Alternative Models

| Alternative | Advantage Over NanoBERT | Disadvantage vs NanoBERT |
|-------------|------------------------|------------------------|
| IgBERT (unpaired) | Longer max sequence, generate action | Not nanobody-specialized |
| ESM-2 | Broad protein coverage, multiple sizes | Not nanobody-specialized |
| AbLang2 | Germline debiasing, paired chains | Requires paired sequences; not for nanobodies |

**When to choose NanoBERT**: Use NanoBERT when working specifically with nanobody/VHH sequences for embedding, sequence completion, or scoring tasks. It is the only nanobody-specialized model on the platform.

**When to choose alternatives**: Consider IgBERT (unpaired) for nanobody sequences longer than 154 residues; consider ESM-2 for comparing nanobodies with other proteins.

## Biological Background

Nanobodies (VHH domains) are the variable antigen-binding domains of heavy-chain-only antibodies (HCAbs) found naturally in camelids (camels, llamas, alpacas) and cartilaginous fish (sharks -- VNARs). Unlike conventional antibodies that require both VH and VL domains for antigen binding, nanobodies bind antigens as single domains, conferring several advantages for biotechnology applications.

**Structural features of nanobodies**: Nanobodies are approximately 12-15 kDa (~120-130 residues) and adopt the immunoglobulin variable domain fold. They differ from conventional VH domains in several key ways:
- **Hallmark substitutions**: Positions 37, 44, 45, and 47 (Kabat numbering) carry hydrophilic substitutions that increase solubility and stability in the absence of a VL partner.
- **Extended CDR3**: Nanobody CDR3 loops are often longer than conventional VH CDR3 loops, allowing them to probe concave epitopes (e.g., enzyme active sites) that are inaccessible to conventional antibodies.
- **CDR1 diversity**: VHH CDR1 is often more diverse than conventional VH CDR1, contributing to antigen recognition.

**Advantages for engineering**: Nanobodies are small, stable, soluble, and easy to produce in microbial expression systems. They can be linked into multivalent constructs, fused to effector domains, or conjugated to nanoparticles. Their single-domain nature makes them ideal targets for computational design and language model-based engineering.

**Key terminology**:
- **Nanobody / VHH**: The variable domain of a camelid heavy-chain-only antibody.
- **HCAb (Heavy-chain-only antibody)**: A naturally occurring antibody lacking light chains, found in camelids and sharks.
- **Hallmark residues**: Amino acid positions characteristic of VHH domains that distinguish them from conventional VH domains.
- **CDR-H3**: The third complementarity-determining region of the heavy chain, which is the most variable region and a primary determinant of antigen specificity.
- **Gene-agnostic**: An analytical approach that does not rely on germline gene assignments, instead learning sequence patterns directly from the data.

---

*See also: [README.md](README.md) for API reference | [MODEL.md](MODEL.md) for technical details*
