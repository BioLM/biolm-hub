# IgBERT -- Biological Context

## Molecule Coverage

### Primary Molecule Type(s)

IgBERT is trained on immunoglobulin (antibody) sequences, supporting both paired heavy-light chain analysis and individual chain analysis depending on the deployed variant. The model operates at the amino acid level.

IgBERT handles different antibody regions and contexts:

- **Variable domains (VH/VL)**: Primary target. Framework and CDR regions are both well-represented.
- **Paired sequences**: The paired variant captures heavy-light chain co-evolution, which is critical for understanding binding specificity.
- **Unpaired sequences**: The unpaired variant can process individual heavy or light chains when paired data is unavailable.
- **Constant regions**: Can be included in unpaired mode but are not the primary focus.

### Cross-Applicability

| Molecule Type | Applicability | Evidence | Caveats |
|--------------|---------------|----------|---------|
| IgG antibodies (paired) | High | Primary training target for paired variant | Use `igbert-paired` variant |
| IgG antibodies (single chain) | High | Primary training target for unpaired variant | Use `igbert-unpaired` variant |
| Nanobodies (VHH) | Low--Moderate | Single-domain; use unpaired variant | Not specifically trained on nanobodies |
| TCRs | Low | Some structural homology to immunoglobulins | Not trained on TCR data |
| General proteins | Not applicable | Antibody-specialized model | Use ESM-2 or similar |

## Biological Problems Addressed

### Paired Antibody Representation

**Problem**: Antibody function depends on the combined properties of the heavy and light chain variable domains. Traditional analysis treats chains independently, missing important inter-chain interactions that determine binding specificity, affinity, and developability.

**How IgBERT helps**: The paired variant (`igbert-paired`) processes both chains jointly with a `[SEP]` separator, learning contextual representations that account for heavy-light chain pairing. The `encode` action produces embeddings that capture paired chain properties.

**Biological meaning**: Paired embeddings encode information about the combined paratope formed by VH and VL domains. Two antibodies with identical heavy chains but different light chains will produce different paired embeddings, reflecting the biological reality that light chain identity significantly influences binding specificity.

### Antibody Sequence Completion

**Problem**: Antibody sequences from high-throughput screening or NGS may have missing or uncertain residues. Computationally predicting these positions using antibody-specific sequence context can recover functional sequences.

**How IgBERT helps**: The `generate` action takes sequences with `*` placeholders and uses the BERT masked language modeling head to predict the most likely canonical amino acid at each masked position. The prediction uses full sequence context (and cross-chain context for the paired variant).

**Biological meaning**: The predicted residues at masked positions represent the model's estimate of the most evolutionary and structurally plausible amino acid given the surrounding context. For CDR positions, this reflects the diversity of CDR sequences seen in training; for framework positions, predictions tend to be highly confident and match germline consensus.

### Antibody Sequence Scoring

**Problem**: Evaluating whether engineered or mutant antibody sequences are biophysically plausible requires scoring them against known antibody sequence patterns.

**How IgBERT helps**: The `log_prob` action computes the total log-probability of a sequence under the IgBERT model by summing log P(residue_i | context) at each position (excluding special tokens). This provides a single scalar score for sequence plausibility.

**Biological meaning**: Higher (less negative) log-probability scores indicate sequences more consistent with natural antibody patterns. Comparing scores between wild-type and mutant sequences can identify mutations that disrupt conserved structural motifs or introduce unfavorable interactions.

## Applied Use Cases

IgBERT is applicable to several antibody engineering and analysis workflows:

- **Antibody repertoire analysis**: Embed and cluster paired or unpaired antibody sequences to identify clonal families and convergent evolution (published)
- **Paired chain association**: Use paired embeddings to study heavy-light chain pairing preferences (published)
- **Sequence completion**: Restore missing CDR or framework residues from partial sequences (anticipated)
- **Variant scoring**: Rank engineered antibody variants by sequence plausibility (anticipated)
- **Feature extraction for ML**: Use IgBERT embeddings as input features for downstream property predictors (anticipated)

## Related Models

### Complementary Models

IgBERT is published alongside IgT5, from the same paper:

- **IgT5**: T5-based antibody encoder from the same authors. Provides embedding-only functionality with a different architecture. IgBERT uses BERT (encoder-only), while IgT5 uses T5 (encoder from encoder-decoder).

Other complementary models in this catalog:

- **SADIE**: Use for antibody numbering and annotation before IgBERT embedding
- **AbLang2**: Alternative antibody LM with germline debiasing

Typical multi-model workflows:
1. Use SADIE to annotate and number sequences
2. Use IgBERT `encode` to generate embeddings for clustering
3. Use IgBERT `log_prob` to score engineered variants

### Alternative Models

| Alternative | Advantage Over IgBERT | Disadvantage vs IgBERT |
|-------------|----------------------|----------------------|
| AbLang2 | Germline debiasing, restore mode | Paired only, custom library |
| IgT5 | Same paper, T5 architecture | Encode only, no generate or log_prob |
| ESM-2 | Broad protein coverage, multiple sizes | Not antibody-specialized |
| AntiBERTy | Large OAS training set | Single-chain only |

**When to choose IgBERT**: Use IgBERT when you need a HuggingFace-compatible antibody model with both paired and unpaired variants, or when you need both embedding and sequence generation capabilities.

**When to choose alternatives**: Consider AbLang2 for germline-debiased representations; consider IgT5 for T5-architecture embeddings; use the unpaired variant for nanobody sequences.

## Biological Background

Immunoglobulins (antibodies) are the primary effector molecules of the humoral adaptive immune system. Their remarkable diversity arises from combinatorial V(D)J recombination, junctional diversity, and somatic hypermutation, generating an estimated >10^13 unique antibody sequences in the human body.

**Paired chain biology**: The antigen-binding specificity of an antibody is determined by the combined properties of the heavy chain variable domain (VH) and the light chain variable domain (VL). The six CDR loops (three from each chain) form the paratope that contacts the antigen. Heavy-light chain pairing is not random -- certain VH-VL combinations are favored due to structural compatibility at the VH-VL interface. Language models trained on paired sequences can learn these pairing preferences.

**Scale and diversity**: Large-scale antibody sequencing studies (e.g., from the Observed Antibody Space and Exscientia datasets) have generated millions of paired antibody sequences. Training language models at this scale enables them to learn the rules governing antibody sequence diversity, including germline gene usage, CDR length distributions, and somatic hypermutation patterns.

**Key terminology**:
- **Paired sequences**: Matched heavy and light chains from the same B cell, preserving the natural pairing.
- **Unpaired sequences**: Individual heavy or light chains analyzed independently, without pairing information.
- **V(D)J recombination**: Somatic DNA rearrangement that generates the initial antibody variable domain sequence.
- **Paratope**: The antigen-binding surface formed by CDR loops from both VH and VL domains.
- **Clonal family**: A group of antibodies derived from the same V(D)J rearrangement event, related by somatic hypermutation.

---

*See also: [README.md](README.md) for API reference | [MODEL.md](MODEL.md) for technical details*
