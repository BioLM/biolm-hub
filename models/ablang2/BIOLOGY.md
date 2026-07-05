# AbLang2 -- Biological Context

## Molecule Coverage

### Primary Molecule Type(s)

AbLang2 is trained exclusively on paired antibody sequences -- heavy and light chain pairs from the Observed Antibody Space (OAS) database. The model operates on the amino acid level and processes both chains jointly, enabling it to capture inter-chain co-evolutionary signals.

AbLang2 handles different antibody regions with varying quality:

- **Framework regions (FWRs)**: Excellent representation quality. Framework residues are highly conserved and well-represented in training data.
- **Complementarity-determining regions (CDRs)**: Good representation quality. CDR diversity is well-captured, though CDR-H3 (the most variable region) may have higher prediction uncertainty.
- **Constant regions**: Not applicable -- AbLang2 is designed for variable domain sequences only.
- **Nanobodies / VHH**: Not supported -- requires paired heavy+light chains. For single-domain antibodies, use the unpaired IgBERT or IgT5 variant.

### Cross-Applicability

| Molecule Type | Applicability | Evidence | Caveats |
|--------------|---------------|----------|---------|
| IgG antibodies | High | Primary training molecule; paired H+L modeling | Both chains required |
| IgM / IgA | Moderate | Variable domains share structural features with IgG | Trained primarily on IgG; isotype-specific features not modeled |
| Nanobodies (VHH) | Not applicable | Requires paired sequences | Use the unpaired IgBERT or IgT5 variant instead |
| TCRs | Low | Some structural homology to antibodies | Not trained on TCR sequences; use TCR-specific models |
| General proteins | Not applicable | Antibody-specialized model | Use ESM-2 or similar general protein LMs |

## Biological Problems Addressed

### Antibody Sequence Embedding

**Problem**: Antibody engineering requires numerical representations of antibody sequences for computational screening, clustering, and property prediction. Traditional approaches use germline gene identity, CDR sequence similarity, or hand-crafted features, which either conflate germline identity with functional properties or fail to capture the complex interplay between heavy and light chains.

**How AbLang2 helps**: The `encode` action with `seqcoding` mode produces a fixed-length embedding vector for paired heavy-light sequences. The `rescoding` mode produces per-residue embeddings. Both modes use germline-debiased representations that focus on functional properties rather than germline origin.

**Biological meaning**: A seqcoding embedding captures the "functional fingerprint" of an antibody pair, encoding information about binding specificity, developability, and structural stability. Antibodies targeting similar epitopes will have similar embeddings, even if they derive from different germline genes. Rescoding embeddings capture position-specific properties useful for identifying key contact residues and predicting the structural role of individual positions.

### Antibody Sequence Restoration

**Problem**: Antibody sequences obtained from next-generation sequencing (NGS) or single-cell sequencing often contain missing or ambiguous residues due to sequencing errors, low coverage, or primer mismatches. Reconstructing these missing positions is essential for downstream analysis and expression.

**How AbLang2 helps**: The `generate` action takes sequences with `*` placeholder characters marking unknown positions and predicts the most likely amino acid at each position, using the full paired heavy-light context. This leverages the model's understanding of antibody sequence constraints to fill gaps with evolutionarily and structurally plausible residues.

**Biological meaning**: The restored residues reflect what the model considers most compatible with the surrounding sequence context, accounting for both intra-chain and inter-chain constraints. This is particularly useful for CDR restoration where the heavy and light chain context provides complementary information.

### Antibody Likelihood Scoring

**Problem**: Evaluating whether an engineered or mutant antibody sequence is biophysically plausible requires assessing how well it fits known antibody sequence patterns. This is important for filtering designed sequences, assessing humanization quality, and predicting developability.

**How AbLang2 helps**: The `predict` action returns per-position likelihood scores, and `log_prob` returns total sequence log-probability. These scores quantify how "antibody-like" a sequence is under the model.

**Biological meaning**: A high likelihood score indicates the sequence is consistent with natural antibody patterns. Positions with low likelihood may indicate destabilizing mutations, unusual CDR conformations, or deviations from canonical structures. The germline debiasing ensures these scores reflect functional plausibility rather than proximity to common germline genes.

## Applied Use Cases

AbLang2 embeddings and predictions are applicable to several antibody engineering workflows:

- **Antibody humanization assessment**: Score humanized sequences for how well they match human antibody patterns (published)
- **Developability prediction**: Use embeddings as features for predicting expression level, aggregation propensity, and stability (published)
- **CDR restoration from NGS data**: Fill in missing residues from low-quality sequencing reads (published)
- **Antibody library design**: Score designed sequences for biophysical plausibility (anticipated)
- **Repertoire analysis**: Cluster and compare antibody repertoires using germline-debiased embeddings (anticipated)

## Related Models

### Predecessor Models

- **AbLang** (Olsen et al., 2022): The direct predecessor. A single-chain antibody language model trained on unpaired sequences from OAS. AbLang2 improves on AbLang by modeling paired sequences and debiasing germline influence.

### Complementary Models

AbLang2 can be combined with other models on the BioLM platform:

- **SADIE**: Use SADIE for numbering and annotation, then AbLang2 for embedding and likelihood scoring
- **IgBERT/IgT5**: Alternative antibody language models for comparison or ensemble approaches
- **AntiFold**: Use AbLang2 embeddings for sequence selection, then AntiFold for structure-based inverse folding

Typical multi-model workflows:
1. Use SADIE `predict` to annotate and number antibody sequences
2. Use AbLang2 `encode` to generate embeddings for clustering and property prediction
3. Use AbLang2 `log_prob` to score engineered variants

### Alternative Models

| Alternative | Advantage Over AbLang2 | Disadvantage vs AbLang2 |
|-------------|----------------------|----------------------|
| IgBERT | HuggingFace-compatible, paired and unpaired variants | No germline debiasing |
| ESM-2 | Broader protein coverage, more size variants | Not antibody-specialized, no paired chain modeling |
| AntiBERTy | Pre-trained on large OAS dataset | Single-chain only, no paired modeling |

**When to choose AbLang2**: Use AbLang2 when you need germline-debiased paired antibody representations, sequence restoration, or likelihood scoring and always have both heavy and light chain sequences available.

**When to choose alternatives**: Consider IgBERT for unpaired (single-chain) analysis; consider ESM-2 when comparing antibodies to non-antibody proteins; consider the unpaired IgBERT or IgT5 variant for nanobody/VHH sequences.

## Biological Background

Antibodies (immunoglobulins) are Y-shaped proteins produced by B cells of the adaptive immune system. Each antibody molecule consists of two identical heavy chains and two identical light chains, linked by disulfide bonds. The variable domains of the heavy chain (VH) and light chain (VL) together form the antigen-binding site (paratope) that determines binding specificity.

**Germline genes and somatic hypermutation**: Antibody variable domains are encoded by rearranged germline gene segments (V, D, J for heavy chains; V, J for light chains). After initial rearrangement, B cells undergo somatic hypermutation (SHM) in germinal centers, introducing point mutations that are selected for improved antigen binding (affinity maturation). Traditional antibody analysis methods heavily rely on germline gene assignment, which can bias functional comparisons -- two antibodies from different germline families may have converged on similar binding properties through SHM.

**Germline bias in language models**: When trained naively on antibody repertoire data, language models tend to learn germline gene usage patterns as the dominant signal, since germline identity explains most of the sequence variance in a repertoire. AbLang2 specifically addresses this by debiasing the training objective, forcing the model to learn signals beyond germline identity -- such as CDR conformation, paratope chemistry, and developability determinants.

**Key terminology**:
- **Heavy chain / Light chain**: The two polypeptide chains forming an antibody; heavy chains are ~450 residues (variable + constant), light chains are ~214 residues.
- **Variable domain (VH/VL)**: The N-terminal domain of each chain containing the antigen-binding CDRs.
- **CDR (Complementarity-Determining Region)**: Three hypervariable loops per chain (CDR1, CDR2, CDR3) that directly contact the antigen.
- **Framework region (FWR)**: Conserved beta-sheet scaffold supporting the CDR loops.
- **Germline gene**: The inherited, un-mutated gene segment encoding the initial antibody variable domain.
- **Somatic hypermutation (SHM)**: Process of introducing point mutations during B cell maturation.
- **OAS (Observed Antibody Space)**: Database of antibody repertoire sequencing data from published studies.

---

*See also: [README.md](README.md) for API reference | [MODEL.md](MODEL.md) for technical details*
