# ESM-1b -- Biological Context

## Molecule Coverage

### Primary Molecule Type(s)

ESM-1b is trained on UniRef50, which covers protein sequences from all domains of life -- bacteria, archaea, eukaryota, and viruses. The model accepts single-chain protein sequences of up to 1022 residues (1024 tokens including BOS/EOS).

ESM-1b handles **globular, soluble proteins** best, as these dominate the training data. Performance characteristics vary by protein type:

- **Globular, soluble proteins**: Good representation quality. These constitute the bulk of UniRef50.
- **Membrane proteins**: Functional but degraded -- transmembrane regions are under-represented in UniRef50.
- **Intrinsically disordered proteins/regions (IDPs/IDRs)**: The model can embed these, but structural inferences will be unreliable since disordered regions lack stable 3D structure.
- **Multi-domain proteins**: Each domain is reasonably represented, but the 1022-residue limit means many multi-domain proteins must be truncated.
- **Fibrous proteins** (collagen, keratin): Under-represented in training data. Repetitive sequences may produce degenerate embeddings.

**Legacy note**: ESM-2 (the successor model) covers the same molecule types with improved representation quality and a longer maximum sequence length (2046 residues). For new work, ESM-2 is preferred.

### Cross-Applicability

| Molecule Type | Applicability | Evidence | Caveats |
|--------------|---------------|----------|---------|
| Antibodies | Moderate | ESM-1b embeddings used in early antibody engineering studies | Variable regions (CDRs) are represented; specialized antibody models (IgBERT, AntiBERTy) may outperform on antibody-specific tasks |
| Enzymes | High | Active site conservation patterns captured by embeddings | No explicit catalytic mechanism modeling -- information is implicit in evolutionary signal |
| Peptides | Low–Moderate | Short sequences (< 30 residues) provide limited context | Consider peptide-specific models for very short sequences |

## Biological Problems Addressed

### Protein Representation Learning

**Problem**: Downstream protein analysis tasks (function prediction, localization, interaction prediction) require numerical representations of protein sequences. Traditional approaches use hand-crafted features (amino acid composition, physicochemical scales) or alignment-based profiles (PSSM, HMM), which are limited in expressiveness or computationally expensive.

**How ESM-1b helps**: The `encode` action produces dense vector embeddings that capture evolutionary, structural, and biophysical properties learned from hundreds of millions of protein sequences. These embeddings serve as general-purpose features for any downstream model.

**Biological meaning**: A mean-pooled ESM-1b embedding is a 1280-dimensional vector encoding the "evolutionary fingerprint" of a protein. Proteins with similar function, structure, or evolutionary origin cluster together in embedding space, even at low sequence identity. Per-token embeddings capture position-specific information useful for residue-level predictions (e.g., binding sites, post-translational modification sites).

**Historical significance**: ESM-1b was the first model to demonstrate at scale that protein language model representations spontaneously encode information about protein tertiary structure -- an emergent property of training on evolutionary data alone. This finding motivated the development of ESM-2, ESMFold, and many subsequent protein foundation models.

### Zero-Shot Variant Effect Prediction

**Problem**: Predicting the functional impact of amino acid substitutions (missense mutations) is critical for clinical genetics, protein engineering, and understanding disease. Experimental methods (deep mutational scanning) are expensive and limited to one protein at a time.

**How ESM-1b helps**: The `log_prob` action computes the summed log-likelihood of a protein sequence in a single unmasked forward pass (wt-marginal scoring). By comparing log P(wildtype) vs log P(mutant), researchers can estimate variant effects without task-specific training. Evolutionarily conserved positions will have high log-probability for the wildtype amino acid and low probability for substitutions.

**Biological meaning**: A large negative change in log-probability (mutant much less likely than wildtype) suggests the mutation disrupts an evolutionarily conserved position and is likely deleterious. The BioLM verification confirms this: real ubiquitin scores dramatically higher (-0.17 per-residue log-prob) than a shuffled version with identical composition (-36.74), demonstrating the model captures evolutionary constraints.

**Note**: ESM-2's `log_prob` provides equivalent functionality with superior representations. For variant effect prediction, ESM-2 is recommended.

### Masked Token Prediction (Sequence Completion)

**Problem**: In protein engineering and directed evolution, researchers want to know which amino acids are compatible at specific positions in a protein, accounting for full sequence context.

**How ESM-1b helps**: The `predict` action takes a sequence with `<mask>` tokens and returns the predicted probability distribution over all 20 standard amino acids at each masked position. This provides a context-aware "consensus" reflecting evolutionary constraints.

**Biological meaning**: The predicted distribution at a masked position reflects the structural and functional constraints on that residue. Positions critical for the protein's fold will have narrow distributions (few amino acids tolerated); surface-exposed loops will have broader distributions (many amino acids acceptable). The BioLM verification confirms that ESM-1b correctly predicts Lysine at position 48 of ubiquitin -- a biologically critical residue required for polyubiquitin chain formation.

## Applied Use Cases

### Plant Protein-Protein Interaction Prediction

**Source**: (2023). "Pre-trained protein language model sheds new light on the prediction of Arabidopsis protein-protein interactions." *Plant Methods*. [DOI: 10.1186/s13007-023-01119-6](https://doi.org/10.1186/s13007-023-01119-6)

ESM-1b embeddings were combined with an MLP classifier for Arabidopsis protein-protein interaction prediction, achieving AUPR of 0.810 on unseen protein pairs. This demonstrates ESM-1b's utility as a feature extractor for organism-specific interaction networks, even without fine-tuning on the target organism.

### Domain-Adaptive Pretraining for DNA-Binding Proteins

**Source**: (2024). "Improving prediction performance of general protein language model by domain-adaptive pretraining on DNA-binding protein." *Nature Communications*. [DOI: 10.1038/s41467-024-52293-7](https://doi.org/10.1038/s41467-024-52293-7)

ESM-1b was domain-adapted for DNA-binding protein prediction through continued pretraining on DBP sequences, outperforming the base model on DBP classification. This study establishes a pattern for specializing general-purpose protein language models to specific functional classes via domain-adaptive pretraining.

### Few-Shot Fitness Prediction

**Source**: (2024). "Enhancing efficiency of protein language models with minimal wet-lab data through few-shot learning." *Nature Communications*. [DOI: 10.1038/s41467-024-49798-6](https://doi.org/10.1038/s41467-024-49798-6)

ESM-1b and ESM-1v were benchmarked with few-shot fine-tuning across 87 deep mutational scanning datasets for protein fitness prediction. The study demonstrates that even a small number of experimental measurements (few-shot) can substantially improve PLM-based fitness predictions over zero-shot baselines, a practically important finding for protein engineering campaigns with limited experimental budgets.

Many of these applications have since migrated to ESM-2, which provides improved performance with the same API patterns.

## Related Models

### Predecessor Models

- **ESM-1** (Rives et al., earlier versions): Smaller-scale precursors that established the protein language modeling approach. ESM-1b was the largest and best-performing model in the original ESM series.

### Successor Models

- **ESM-2** (Lin et al., 2023): The direct successor to ESM-1b. Available in five size variants (8M to 3B parameters), ESM-2 provides strictly better representations than ESM-1b through improved training procedures and systematic scaling. **ESM-2 is the recommended choice for all new work.**
- **ESMFold** (Lin et al., 2023): Uses ESM-2 embeddings for single-sequence protein structure prediction.
- **ESM3** (EvolutionaryScale, 2024): A multimodal protein model handling sequence, structure, and function simultaneously.

### Complementary Models

ESM-1b embeddings can be used as input features for downstream models:

- **ESMFold / Chai-1**: Structure prediction for top-scoring variants from ESM-1b log-likelihood screening

### Alternative Models

| Alternative | Advantage Over ESM-1b | Disadvantage vs ESM-1b |
|-------------|----------------------|----------------------|
| ESM-2 (650M) | Better representations at same parameter count; longer max sequence | None -- strictly superior for all tasks |
| ProtTrans (ProtT5) | Encoder-decoder enables generation | Larger compute footprint |
| SaProt | Structure-aware tokens when structure is available | Requires predicted or experimental structure input |
| ESM3 | Multimodal (sequence + structure + function) | Newer, fewer downstream benchmarks |

**When to use ESM-1b**: Only when reproducing results from published studies that specifically used ESM-1b, or when backward compatibility with existing ESM-1b-based pipelines is required.

**When to use alternatives**: For all new work, use ESM-2. Consider SaProt when structural information is available; consider ESM3 for multimodal protein understanding.

## Biological Background

Proteins are linear chains of amino acids (typically 50-2000 residues long) that fold into three-dimensional structures to carry out virtually all cellular functions -- catalysis, signaling, transport, structural support, and immune defense. The sequence of amino acids (the "primary structure") determines the protein's 3D structure and, consequently, its function.

**Evolutionary conservation**: Over billions of years of evolution, natural selection has preserved amino acids critical for protein function while allowing variation at less constrained positions. By analyzing millions of protein sequences from diverse organisms, patterns of conservation and co-variation encode deep information about protein structure and function. This is the fundamental insight that protein language models like ESM-1b exploit.

**Masked language modeling on proteins**: Just as BERT learns grammar and semantics by predicting masked words in sentences, ESM-1b learns the "grammar" of proteins -- which amino acids are compatible at each position given the surrounding context. A position deep in the hydrophobic core "expects" hydrophobic residues (L, I, V, F); a surface-exposed loop tolerates most amino acids; a catalytic residue is highly constrained. The model learns these rules implicitly from evolutionary data.

**Historical context**: ESM-1b (2021) was the first model to show convincingly that these learned representations encode three-dimensional structural information as an emergent property. Attention heads in the model learn to attend to residue pairs that are physically close in 3D space, despite never seeing protein structures during training. This discovery was a major milestone in computational biology and directly motivated the development of ESMFold and subsequent protein foundation models.

**Key terminology**:
- **Embedding**: A dense numerical vector representing a protein (or a position within it) in a high-dimensional space. Similar proteins have similar embeddings.
- **Masked language modeling (MLM)**: Training objective where random positions are hidden and the model must predict the original amino acid from context.
- **Log-likelihood / pseudo-log-likelihood**: A score measuring how "expected" a sequence is under the model. Higher (less negative) scores indicate the sequence is more consistent with evolutionary patterns.
- **UniRef50**: A clustered version of the UniProt Reference Clusters database where sequences are grouped at 50% sequence identity, reducing redundancy while preserving diversity.
- **Remote homology**: Evolutionary relationship between proteins that share a common ancestor but have diverged to the point where sequence similarity is undetectable by standard alignment methods. ESM-1b's embeddings can detect such relationships.

---

*See also: [README.md](README.md) for API reference | [MODEL.md](MODEL.md) for technical details*
