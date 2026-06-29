# ESM2  --  Biological Context

## Molecule Coverage

### Primary Molecule Type(s)

ESM-2 is trained on UniRef50, which covers protein sequences from all domains of life  --  bacteria, archaea, eukaryota, and viruses. The model accepts single-chain protein sequences of up to 2048 amino-acid residues (BOS/EOS tokens are added internally).

ESM-2 handles **globular proteins** best, as these are the most abundant in training data. Performance characteristics vary by protein type:

- **Globular, soluble proteins**: Excellent representation quality. These constitute the bulk of UniRef50.
- **Membrane proteins**: Functional but degraded  --  transmembrane helices and membrane-spanning regions are under-represented in UniRef50 relative to their biological importance.
- **Intrinsically disordered proteins/regions (IDPs/IDRs)**: The model can embed these, but contact predictions and structural inferences will be unreliable since disordered regions lack stable 3D structure by definition.
- **Multi-domain proteins**: Each domain is well-represented; however, inter-domain contacts may be less accurate for very long sequences that approach the 2048-token limit.
- **Fibrous proteins** (collagen, keratin): Under-represented in training data. Repetitive sequences may produce degenerate embeddings.

### Cross-Applicability

| Molecule Type | Applicability | Evidence | Caveats |
|--------------|---------------|----------|---------|
| Antibodies | Moderate–High | ESM-2 embeddings used for antibody developability prediction in multiple studies | Variable regions (CDRs) are well-represented; constant regions are less informative. Specialized antibody models (e.g., IgBERT, AntiBERTy) may outperform on antibody-specific tasks. |
| Enzymes | High | Active site and catalytic residue prediction validated across enzyme families | No explicit catalytic mechanism modeling  --  embeddings capture evolutionary conservation at active sites |
| Peptides | Low–Moderate | Short sequences (< 30 residues) provide limited context for the transformer | Consider peptide-specific models for very short sequences; ESM-2 may still be useful as a feature extractor |
| Antibody-drug conjugates | Low | No training on conjugated or modified proteins | Linker chemistry and payload interactions are invisible to the model |

## Biological Problems Addressed

### Protein Representation Learning

**Problem**: Many downstream protein analysis tasks (function prediction, localization, interaction) require numerical representations of protein sequences. Traditional approaches use hand-crafted features (amino acid composition, physicochemical scales) or alignment-based profiles (PSSM, HMM), both of which have limitations in expressiveness or computational cost.

**How ESM-2 helps**: The `encode` action produces dense vector embeddings that capture evolutionary, structural, and biophysical properties learned from millions of protein sequences. These embeddings can be used as features for any downstream classifier or regressor.

**Biological meaning**: A mean-pooled ESM-2 embedding is a fixed-length vector (dimension = hidden_dim of the chosen variant) that encodes the "evolutionary fingerprint" of a protein. Proteins with similar function, structure, or evolutionary origin will have similar embeddings, even if their sequence identity is low. Per-token embeddings additionally capture position-specific information useful for residue-level predictions.

### Zero-Shot Variant Effect Prediction

**Problem**: Predicting the functional impact of amino acid substitutions (missense mutations) is critical for clinical genetics, protein engineering, and understanding disease mechanisms. Experimental methods (deep mutational scanning) are expensive and limited to one protein at a time.

**How ESM-2 helps**: The `log_prob` action computes the summed per-residue log-probability of a full sequence using a single unmasked forward pass. By comparing log P(wildtype) vs log P(mutant), researchers can estimate variant effects without any task-specific training. The model naturally assigns higher probability to residues that are evolutionarily conserved at a given position. Note: this is a "wt-marginal" score (the model sees the full sequence), not a masked pseudo-log-likelihood (which would mask each position independently).

**Biological meaning**: A large negative delta-log-probability (mutant much less likely than wildtype) suggests the mutation disrupts an evolutionarily conserved position and is likely deleterious. This correlates with experimental measures of protein fitness (stability, activity, binding affinity) as benchmarked on datasets like ProteinGym.

### Masked Token Prediction (Sequence Completion)

**Problem**: In protein engineering and directed evolution, researchers often want to know which amino acids are compatible at specific positions in a protein sequence, accounting for the full sequence context.

**How ESM-2 helps**: The `predict` action takes a sequence with one or more `<mask>` tokens and returns the predicted probability distribution over all 20 standard amino acids at each masked position. This provides a context-aware "consensus" for each position.

**Biological meaning**: The predicted distribution at a masked position reflects evolutionary constraints: positions critical for structure or function will have narrow distributions (few amino acids tolerated), while surface-exposed loop positions will have broader distributions (many amino acids acceptable). This can guide rational mutagenesis campaigns.

### Contact Prediction

**Problem**: Identifying which residue pairs are in physical contact (< 8 Angstroms between C-beta atoms) helps constrain protein structure and reveals functional sites.

**How ESM-2 helps**: The `encode` action with `include=["contacts"]` extracts predicted contact maps from the model's attention weights. This is a byproduct of the transformer's attention mechanism learning structural patterns from evolutionary data.

**Biological meaning**: Predicted contacts between distant residues in sequence (long-range contacts) are particularly informative for protein fold determination. While dedicated structure prediction models (ESMFold, AlphaFold) are more accurate, ESM-2 contact maps are fast to compute and useful for quick structural assessment.

## Applied Use Cases

### Protein-Protein Interaction Scoring with ESM-2 Embeddings

**Source**: Xu et al. "DeepRank-GNN-esm: a graph neural network for scoring protein-protein models using protein language model." *Bioinformatics Advances* (2024). [DOI: 10.1093/bioadv/vbad191](https://doi.org/10.1093/bioadv/vbad191)

ESM-2 embeddings were used to replace traditional PSSM features for protein-protein interaction scoring in a graph neural network framework. The approach achieved equal or better performance than alignment-based features while being significantly faster to compute, demonstrating that ESM-2 representations capture sufficient evolutionary information to replace computationally expensive multiple sequence alignments in PPI scoring pipelines.

### Transfer Learning Benchmark Across Protein Classification Tasks

**Source**: (2025). "Medium-sized protein language models perform well at transfer learning on realistic datasets." *Nature Scientific Reports*. [DOI: 10.1038/s41598-025-05674-x](https://doi.org/10.1038/s41598-025-05674-x)

A systematic benchmark of ESM-2 650M transfer learning across protein classification tasks showed that medium-sized models match the performance of larger models. This finding is practically important: it validates that the 650M parameter variant (rather than the 3B variant) is sufficient for most downstream tasks, making ESM-2-based pipelines accessible without high-end GPU infrastructure.

### Protein Expression, Stability, and Function Evaluation

**Source**: (2024). "Improving Protein Expression, Stability, and Function with ProteinMPNN." *Journal of the American Chemical Society*. [DOI: 10.1021/jacs.3c10941](https://doi.org/10.1021/jacs.3c10941)

ESM-2 embeddings were used as part of a protein evaluation pipeline for designed protein variants, complementing ProteinMPNN-based inverse folding. The study demonstrates ESM-2's role in multi-model workflows where embeddings serve as a quality filter for computationally designed proteins.

ESM-2 embeddings have additionally been widely adopted for other downstream applications including:

- **Subcellular localization**: Mean-pooled embeddings as features for multi-class classifiers
- **Drug target prioritization**: Embedding-based clustering and functional annotation of proteomes
- **Antibody engineering**: CDR embedding analysis for humanization and developability scoring

## Related Models

### Predecessor Models

- **ESM-1b** (Rives et al., 2021): The direct predecessor to ESM-2. A 650M parameter transformer trained on UniRef50. ESM-2 improves on ESM-1b at every model scale by using improved training procedures and scaling. ESM-1b is superseded and not available on this platform.
- **ESM-1v** (Meier et al., 2021): A variant of ESM-1b specifically evaluated for variant effect prediction. ESM-2's `log_prob` action provides equivalent functionality with better representations.

### Complementary Models

ESM-2 is the foundation for several downstream models on the BioLM platform:

- **ESMFold**: Uses ESM-2 embeddings as input for single-sequence protein structure prediction
- **ESMStabP**: Uses ESM-2 embeddings for protein thermostability (melting temperature) prediction

Typical multi-model workflows:
1. Use ESM-2 `encode` to generate embeddings, then feed into a custom downstream classifier
2. Use ESM-2 `log_prob` to score mutant libraries, then use Boltz to predict structures of top candidates

### Alternative Models

| Alternative | Advantage Over ESM-2 | Disadvantage vs ESM-2 |
|-------------|----------------------|----------------------|
| ProtTrans (ProtT5-XL) | Encoder-decoder architecture allows sequence generation | Larger model, slower inference |
| SaProt | Structure-aware tokens improve representation quality when structure is available | Requires predicted or experimental structure as input |
| ESM3 | Multimodal (sequence + structure + function tokens) | Newer, fewer downstream benchmarks available |
| Ankh | Efficient single-sequence encoder competitive with ESM-2 | Less widely adopted and benchmarked |

**When to choose ESM-2**: Use ESM-2 when you need fast, reliable, single-sequence protein embeddings with the widest downstream compatibility. It is the safest default choice for most protein representation tasks.

**When to choose alternatives**: Consider SaProt when you have structural information available; consider ProtT5 when you need generation capabilities; consider ESM3 when you need multimodal protein understanding.

## Biological Background

Proteins are linear chains of amino acids (typically 50-2000 residues long) that fold into three-dimensional structures to carry out virtually all cellular functions  --  catalysis, signaling, transport, structural support, and immune defense. The sequence of amino acids (the "primary structure") determines the protein's 3D structure and, consequently, its function.

**Evolutionary conservation**: Over billions of years of evolution, natural selection has preserved amino acids critical for protein function while allowing variation at less constrained positions. By analyzing millions of protein sequences from diverse organisms, patterns of conservation and co-variation encode deep information about protein structure and function. This is the fundamental insight that protein language models like ESM-2 exploit.

**Masked language modeling on proteins**: Just as BERT learns the rules of grammar and semantics by predicting masked words in sentences, ESM-2 learns the "grammar" of proteins  --  which amino acids are compatible at each position given the surrounding context. A position deep in the hydrophobic core "expects" hydrophobic residues (L, I, V, F); a surface-exposed loop tolerates most amino acids; a catalytic residue is highly constrained. The model learns these rules implicitly from evolutionary data.

**Key terminology**:
- **Embedding**: A dense numerical vector representing a protein (or a position within it) in a high-dimensional space. Similar proteins have similar embeddings.
- **Masked language modeling (MLM)**: Training objective where random positions are hidden and the model must predict the original amino acid from context.
- **Log-probability / log-likelihood**: A score measuring how "expected" a sequence is under the model. Higher (less negative) scores indicate the sequence is more consistent with evolutionary patterns. ESM-2's `log_prob` action uses a single unmasked forward pass (wt-marginal scoring), not masked pseudo-log-likelihood.
- **Contact map**: A symmetric matrix indicating which residue pairs are physically close in 3D space. Long-range contacts (residues far apart in sequence but close in space) are particularly informative for structure.
- **UniRef50**: A clustered version of the UniProt Reference Clusters database where sequences are grouped at 50% sequence identity, reducing redundancy while preserving diversity.

---

*See also: [README.md](README.md) for API reference | [MODEL.md](MODEL.md) for technical details*
