# E1 -- Biological Context

## Molecule Coverage

### Primary Molecule Type(s)

E1 operates on **protein sequences** and supports retrieval-augmented inference where homologous context sequences improve prediction quality. It accepts sequences using the extended amino acid alphabet (20 standard + B, X, Z, U, O).

Performance characteristics by protein type:

- **Globular proteins**: Primary use case. Both embeddings and masked predictions benefit from evolutionary context provided via context sequences.
- **Enzymes**: Well-suited for active-site analysis via masked prediction at catalytic positions.
- **Protein families with known homologs**: E1 excels when context sequences (homologs) are provided, simulating MSA information without explicit alignment.
- **Orphan proteins**: Can be encoded without context, but predictions may be less accurate than when homologs are available.
- **Antibodies**: Variable regions can be analyzed; providing germline or related antibody sequences as context may improve CDR predictions.
- **Peptides**: Short sequences provide limited context; consider peptide-specific models.

### Cross-Applicability

| Molecule Type | Applicability | Evidence | Caveats |
|--------------|---------------|----------|---------|
| Globular proteins | High | Primary design target | Context sequences improve quality |
| Enzymes | High | Active-site residues well-captured by MLM | No explicit catalytic mechanism |
| Protein families | High | Context sequences simulate MSA | Up to 50 context sequences supported |
| Antibodies | Moderate | Can analyze variable regions | Not antibody-specific trained |
| Orphan proteins | Moderate | Works without context, lower accuracy | No evolutionary context available |
| Peptides | Low | Short sequences lack context | Use peptide-specific models |
| DNA/RNA | Not supported | Not in training data | Protein sequences only |

## Biological Problems Addressed

### Retrieval-Augmented Protein Representation

**Problem**: Traditional protein language models (e.g., ESM2) process sequences in isolation. Important evolutionary information captured in multiple sequence alignments (MSAs) is lost unless explicitly computed -- and MSA computation is slow (minutes to hours per query).

**How E1 helps**: The `encode` action accepts optional `context_sequences` (homologous sequences) that are processed jointly with the query using block-causal attention. The query sequence attends to all context, gaining evolutionary context without explicit MSA construction.

**Biological meaning**: Context sequences provide the model with information about which positions are conserved (functionally important) and which are variable (tolerant to substitution) across related proteins. This is the same information encoded in MSAs but provided in a more flexible format -- any set of related sequences works, without requiring formal alignment.

### Zero-Shot Fitness Prediction

**Problem**: Predicting whether a mutation improves or degrades protein function is critical for protein engineering and disease variant interpretation. Experimental testing is expensive.

**How E1 helps**: The `predict_log_prob` action computes the total log probability of a sequence. By comparing log P(wild-type) vs log P(mutant), researchers can estimate mutation effects. When context sequences are provided, the model conditions on evolutionary information, typically improving fitness predictions.

**Biological meaning**: A large drop in log probability (mutant much less likely than wild-type) suggests the mutation disrupts an evolutionarily conserved position and is likely deleterious. Context sequences sharpen this signal by providing explicit examples of what evolution "expects" at each position.

### Masked Sequence Prediction

**Problem**: Determining which amino acids are compatible at specific positions in a protein, accounting for both local and evolutionary context.

**How E1 helps**: The `predict` action takes sequences with `?` mask tokens and returns logits over the 20 canonical amino acids at each masked position. Context sequences can be provided to improve predictions.

**Biological meaning**: The predicted distribution at each masked position reflects evolutionary constraints. Highly constrained positions (active sites, structural cores) will have narrow distributions; tolerant positions (surface loops) will have broad distributions. This guides rational mutagenesis and sequence design.

### Protein Embedding for Downstream Tasks

**Problem**: Numerical representations of proteins are needed for machine learning tasks such as function prediction, clustering, and similarity search.

**How E1 helps**: The `encode` action produces mean-pooled, per-token, or logit-based representations from specified transformer layers. Multiple layers can be requested simultaneously.

**Biological meaning**: E1 embeddings capture evolutionary, structural, and biophysical properties. Proteins with similar function or structure have similar embeddings, enabling clustering, nearest-neighbor search, and feature extraction for downstream classifiers.

## Applied Use Cases

E1 is a recent model (2024). Anticipated use cases include:

- **Variant effect prediction**: Scoring mutations using predict_log_prob with context sequences for improved accuracy
- **Sequence design**: Using masked prediction to explore compatible amino acids at design positions
- **Protein family analysis**: Encoding protein families with shared context for consistent embeddings
- **Antibody humanization**: Using germline sequences as context when predicting at CDR positions
- **Feature extraction**: Using E1 embeddings as input to downstream stability, function, or localization classifiers

## Related Models

### Complementary Models

- **ESM2** (this platform): E1 provides retrieval-augmented embeddings as an alternative to ESM2's single-sequence approach. Use ESM2 when no homologs are available; use E1 when context sequences can be provided.
- **SPURS** (this platform): Can use E1 embeddings or log-prob scores alongside structure-based ddG predictions.
- **Boltz / Chai-1** (this platform): Structure prediction models that can validate E1-guided sequence designs.

### Alternative Models

| Alternative | Advantage Over E1 | Disadvantage vs E1 |
|-------------|----------------------|----------------------|
| ESM2 | Most widely adopted, proven benchmarks | No retrieval augmentation |
| MSA Transformer | Direct MSA processing | Requires explicit (slow) MSA computation |
| SaProt | Structure tokens improve representations | Requires structure input |
| ESM3 | Multimodal (sequence + structure + function) | Larger resource requirements |
| ProtTrans (ProtT5) | Encoder-decoder, generation capable | Larger compute footprint |

**When to choose E1**: Use E1 when you have homologous sequences available and want to improve embedding/prediction quality without computing a full MSA. E1 is also a good choice when you need log-probability scoring with evolutionary context.

**When to choose alternatives**: Use ESM2 when homologs are not available or for compatibility with existing pipelines; use MSA Transformer when a high-quality MSA is already computed; use SaProt when structure is available.

## Biological Background

**Protein language models** learn the statistical patterns of amino acid sequences from large protein databases. By training on millions of sequences from diverse organisms, they implicitly learn which amino acids are compatible at each position given the surrounding context -- capturing evolutionary conservation, structural constraints, and biophysical properties.

**Retrieval-augmented inference**: Traditional protein LMs process sequences independently. E1 introduces a retrieval-augmented approach where related sequences (homologs) are provided as context. The model uses block-causal attention: the query sequence can attend to all context sequences, while context sequences only attend to themselves. This provides the query with information about evolutionary conservation without requiring formal sequence alignment.

**Block-causal attention**: An attention pattern where different parts of the input have different visibility. In E1, context sequences form independent blocks (each only sees itself), while the query sequence can see all blocks. This simulates the effect of reading across an MSA column -- the query "sees" what amino acids appear at corresponding positions in related proteins.

**Key terminology**:
- **Context sequences**: Homologous protein sequences provided alongside the query to improve predictions. These serve as an implicit MSA.
- **Block-causal attention**: Attention pattern where query attends to all sequences but context sequences only attend to themselves.
- **Log probability / pseudo-log-likelihood**: A score measuring how "expected" a sequence is under the model. Higher (less negative) values indicate more natural sequences.
- **Masked language modeling**: Training objective where random positions are masked and the model predicts the original amino acid.
- **MSA (Multiple Sequence Alignment)**: An alignment of multiple related protein sequences that reveals patterns of conservation and variation. E1's context sequences provide similar information without requiring explicit alignment.
- **Homolog**: A protein related by common evolutionary ancestry. Orthologs (same gene, different species) and paralogs (gene duplication) are both useful as context sequences.

---

*See also: [README.md](README.md) for API reference | [MODEL.md](MODEL.md) for technical details*
