# IgT5 -- Biological Context

## Molecule Coverage

### Primary Molecule Type(s)

IgT5 is trained on immunoglobulin (antibody) sequences, supporting both paired heavy-light chain analysis and individual chain analysis depending on the deployed variant. The model operates at the amino acid level and produces dense vector embeddings suitable for downstream computational tasks.

IgT5 handles different antibody regions and contexts:

- **Variable domains (VH/VL)**: Primary target. Both framework and CDR regions are well-represented.
- **Paired sequences**: The paired variant learns cross-chain representations, capturing how VH and VL domains interact.
- **Unpaired sequences**: The unpaired variant processes individual chains independently, useful when pairing information is unavailable.

### Cross-Applicability

| Molecule Type | Applicability | Evidence | Caveats |
|--------------|---------------|----------|---------|
| IgG antibodies (paired) | High | Primary training target for paired variant | Use `igt5-paired` variant |
| IgG antibodies (single chain) | High | Primary training target for unpaired variant | Use `igt5-unpaired` variant |
| Nanobodies (VHH) | Low--Moderate | Single-domain; could use unpaired variant | Not specifically trained on nanobodies |
| TCRs | Low | Some structural homology | Not trained on TCR data |
| General proteins | Not applicable | Antibody-specialized model | Use ESM-2 or similar |

## Biological Problems Addressed

### Antibody Sequence Embedding

**Problem**: Computational analysis of antibody sequences requires numerical representations that capture relevant biophysical and functional properties. The choice of embedding model can significantly impact the quality of downstream analyses such as clustering, similarity search, and property prediction.

**How IgT5 helps**: The `encode` action produces mean-pooled or per-residue embeddings from the T5 encoder's last hidden state. These embeddings are specialized for antibody sequences and capture both intra-chain and (for the paired variant) inter-chain sequence features.

**Biological meaning**: IgT5 embeddings represent antibody sequences in a high-dimensional space where proximity correlates with functional and structural similarity. The T5 architecture's relative position biases may provide advantages for capturing long-range dependencies, such as between distant framework residues that form the VH-VL interface or between CDR loops that are distant in sequence but proximal in 3D space.

### Paired Chain Representation

**Problem**: Antibody binding specificity is determined by the combined paratope formed by VH and VL CDR loops. Analyzing chains independently loses information about how the two chains work together.

**How IgT5 helps**: The paired variant processes both chains in a single forward pass with a `</s>` separator, producing embeddings that encode cross-chain information. This is particularly valuable for tasks that depend on the combined properties of both chains.

**Biological meaning**: Paired embeddings encode the joint VH-VL sequence context. Two antibodies with identical heavy chains but different light chains will produce different paired embeddings, reflecting the biological reality that light chain identity influences antigen specificity, affinity, and developability properties.

## Applied Use Cases

IgT5 is primarily an embedding model suitable for:

- **Antibody repertoire clustering**: Group antibody sequences by functional similarity using embedding distance (published)
- **Paired chain analysis**: Study heavy-light chain compatibility and pairing preferences (published)
- **Feature extraction for property prediction**: Use IgT5 embeddings as input features for downstream ML models predicting binding affinity, expression level, or stability (anticipated)
- **Antibody similarity search**: Find functionally similar antibodies across different germline families (anticipated)

## Related Models

### Companion Models

- **IgBERT**: BERT-based companion model from the same paper. Offers generate and log_prob actions not available in IgT5. Use IgBERT when you need masked prediction or sequence scoring.

### Complementary Models

- **SADIE**: Use for antibody numbering and annotation before IgT5 embedding
- **AbLang2**: Alternative antibody LM with germline debiasing and additional capabilities (restore, likelihood)

Typical multi-model workflows:
1. Use SADIE to annotate sequences and extract variable domains
2. Use IgT5 `encode` to generate embeddings for clustering or property prediction
3. Use IgBERT `log_prob` to score top candidates from the analysis

### Alternative Models

| Alternative | Advantage Over IgT5 | Disadvantage vs IgT5 |
|-------------|---------------------|---------------------|
| IgBERT | Generate + log_prob actions, smaller memory footprint | BERT vs T5 architecture |
| AbLang2 | Germline debiasing, restore mode, likelihood | Paired only, custom library |
| ESM-2 | Broad protein coverage, multiple size variants | Not antibody-specialized |
| ProtT5 | General protein T5, generation capable | Not antibody-specialized |

**When to choose IgT5**: Use IgT5 when you specifically want T5-architecture embeddings for antibody sequences, or when comparing T5 vs BERT representations for your downstream task.

**When to choose alternatives**: Consider IgBERT for sequence generation and scoring; consider AbLang2 for germline-debiased representations; consider ESM-2 for general protein analysis.

## Biological Background

Antibodies are modular proteins with a conserved architecture: each arm of the Y-shaped molecule contains a variable domain (Fab) responsible for antigen binding and a constant domain (Fc) responsible for effector functions. The variable domain is composed of the VH (heavy chain variable) and VL (light chain variable) regions, each contributing three CDR loops to the antigen-binding surface.

**Sequence-function relationship**: The amino acid sequence of the variable domain encodes information about binding specificity, affinity, stability, and developability. Language models trained on large antibody sequence datasets learn statistical patterns that correlate with these functional properties, enabling computational prediction and design.

**T5 architecture for antibodies**: The T5 model's use of relative position biases (rather than absolute positional embeddings) means the model attends to the distance between positions rather than their absolute location. This may be advantageous for antibody sequences where the relative positions of CDR loops and framework regions carry more biological information than their absolute positions, especially given that antibody sequences vary in length (particularly CDR-H3).

**Key terminology**:
- **T5 (Text-to-Text Transfer Transformer)**: A transformer model originally developed for NLP that uses an encoder-decoder architecture. IgT5 uses only the encoder.
- **Relative position bias**: Attention weights that depend on the distance between query and key positions, rather than their absolute positions.
- **Mean pooling**: Averaging per-residue embeddings (excluding special tokens) to produce a single fixed-length vector per sequence.
- **Embedding**: A dense numerical vector representing a sequence in a high-dimensional space.

---

*See also: [README.md](README.md) for API reference | [MODEL.md](MODEL.md) for technical details*
