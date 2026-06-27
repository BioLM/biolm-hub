# ZymCTRL -- Biological Context

## Molecule Coverage

### Primary Molecule Type(s)

ZymCTRL is designed exclusively for **enzymes** -- proteins that catalyze biochemical reactions. The model covers enzymes from all domains of life (bacteria, archaea, eukaryota), as represented in UniProt's enzyme annotation database (July 2022 snapshot, 37M sequences).

Coverage characteristics:
- **Well-represented**: Enzymes with abundant UniProt entries and well-established EC classifications (e.g., oxidoreductases, transferases, hydrolases)
- **Moderate coverage**: Enzymes with fewer training examples or recently classified EC numbers
- **Limited coverage**: Membrane-associated enzymes, multi-subunit enzyme complexes (model generates single chains), and enzymes requiring post-translational modifications for activity
- **Sequence length**: Up to ~1000 amino acids (1024 token limit includes EC number and control tokens)

### Cross-Applicability

| Molecule Type | Applicability | Evidence | Caveats |
|---------------|---------------|----------|---------|
| Enzymes (primary) | High | 37M training sequences, experimental validation | Best for EC classes with many representatives |
| Non-enzyme proteins | Not applicable | Not trained on non-enzyme proteins | Use ProtGPT2 or ESM2 for general proteins |
| Peptides | Not applicable | Too short for meaningful EC-conditioned generation | Minimum useful output ~50 residues |
| Antibodies | Not applicable | Not in training distribution | Use antibody-specific models |
| DNA/RNA | Not applicable | Protein-only model | Use nucleotide-specific models |

## Biological Problems Addressed

### Problem 1: De Novo Enzyme Design

**Biological context**: Designing new enzymes with specific catalytic functions is a central challenge in protein engineering and synthetic biology. Traditional approaches rely on directed evolution (iterative rounds of random mutagenesis and screening) or rational design (structure-guided mutations). Both are expensive, slow, and limited to modifying existing enzymes.

**How ZymCTRL addresses it**: ZymCTRL generates entirely new enzyme sequences conditioned on an EC number, which specifies the desired catalytic reaction. The user provides an EC number (e.g., "4.2.1.1" for carbonic anhydrase), and the model generates novel amino acid sequences predicted to catalyze that reaction.

**What the output means biologically**: Each generated sequence is a candidate enzyme that, according to the model's learned distribution, is consistent with the structural and functional properties of enzymes in that EC class. The accompanying perplexity score indicates how well the sequence fits the learned distribution -- lower perplexity suggests higher likelihood of being a functional enzyme.

**Practical workflow**:
1. Specify the target EC number for the desired catalytic activity
2. Generate hundreds to thousands of candidate sequences
3. Rank by perplexity (threshold: <1.75 for high confidence)
4. Filter top 5% of candidates
5. Validate computationally (e.g., structure prediction with AlphaFold/Boltz, active site analysis)
6. Synthesize and test experimentally

### Problem 2: Exploring Enzyme Sequence Space

**Biological context**: Natural enzymes represent a tiny fraction of possible functional sequences. Understanding the broader sequence space of functional enzymes is important for discovering novel catalytic mechanisms, improving enzyme stability, and finding sequences with properties not found in nature (e.g., thermostability, solvent tolerance).

**How ZymCTRL addresses it**: By generating sequences that are novel (average ~53% identity to natural proteins), ZymCTRL samples from regions of sequence space that evolution has not explored but that are predicted to be functional. This is fundamentally different from homology-based methods that are constrained to sequences similar to known proteins.

**Biological significance**: The 53% average identity to natural enzymes means generated sequences are in a "twilight zone" where they share fold-level similarity to natural enzymes but differ substantially in primary sequence, potentially yielding enzymes with new combinations of properties.

### Problem 3: Enzyme Embedding and Functional Similarity Analysis

**Biological context**: Comparing enzymes by function rather than just sequence similarity is important for understanding enzyme evolution, predicting function of uncharacterized enzymes, and identifying functionally equivalent enzymes from different organisms.

**How ZymCTRL addresses it**: The encode action extracts embeddings from ZymCTRL's internal representations. Because the model was trained on EC-annotated sequences, its embeddings capture functional information beyond raw sequence similarity. Optionally providing an EC number as context further biases the embedding toward functional representation.

**Applications**:
- Clustering enzymes by functional similarity rather than sequence similarity
- Identifying functionally equivalent enzymes across organisms
- Detecting enzymes with similar catalytic mechanisms but divergent sequences

## Applied Use Cases

### Use Case 1: Carbonic Anhydrase Design

**Source**: Munsamy et al. "Conditional language models enable the efficient design of proficient enzymes." *bioRxiv* (2024). [DOI](https://doi.org/10.1101/2024.05.03.592223)

The authors used ZymCTRL to generate novel carbonic anhydrases (EC 4.2.1.1), an enzyme class important in carbon capture, biosensors, and medical applications. Generated sequences were filtered by perplexity, structurally validated using ESMFold, and experimentally tested. Multiple designs showed catalytic activity, demonstrating that ZymCTRL can produce functional enzymes without fine-tuning.

### Use Case 2: Lactate Dehydrogenase Fine-Tuning

**Source**: Munsamy et al. (same paper, Figure 4)

For more targeted design, the authors fine-tuned ZymCTRL on lactate dehydrogenase (EC 1.1.1.27) sequences. Fine-tuning improved generation quality for this specific EC class, demonstrating that the base model can be further specialized. This approach is relevant when users need many high-quality designs for a particular enzyme class and are willing to invest in fine-tuning.

## Related Models

### Predecessor Models

- **ProtGPT2** (Ferruz et al., 2022): ZymCTRL's direct predecessor. Same GPT-2 architecture but trained on general UniRef50 proteins without EC conditioning. ProtGPT2 generates unconditional protein sequences; ZymCTRL adds the critical EC-conditioning mechanism for targeted enzyme design.

### Complementary Models

- **ESM2 / ESMFold / Boltz**: Use for structural validation of ZymCTRL-generated sequences. Typical pipeline: ZymCTRL generates sequences, then structure prediction confirms proper folding and active site geometry.
- **ESM2 embeddings**: Can be used alongside ZymCTRL embeddings for a complementary view -- ESM2 captures general protein properties while ZymCTRL embeddings are enzyme-function-aware.

### Alternative Models

| Alternative | Advantage over ZymCTRL | Disadvantage |
|-------------|------------------------|--------------|
| ProtGPT2 | Broader protein coverage (not limited to enzymes) | No functional conditioning; cannot target specific catalytic activity |
| ProGen2 | Supports taxonomy and broader function tags | Not specifically optimized for enzyme EC hierarchy |
| ESM2 (zero-shot scoring) | Can score/rank existing sequences | Cannot generate new sequences de novo |
| Directed evolution (experimental) | Produces experimentally validated enzymes | Orders of magnitude slower and more expensive |

## Biological Background

### Enzymes and the EC Classification System

**Enzymes** are biological catalysts -- proteins that accelerate chemical reactions in living organisms. Nearly all metabolic reactions in cells are catalyzed by enzymes, making them essential for life and valuable in biotechnology (industrial biocatalysis, pharmaceutical synthesis, diagnostics, bioremediation).

The **Enzyme Commission (EC) number** system is the standard hierarchical classification for enzyme function. It uses a four-level numerical code:

- **First level**: General reaction type (1=oxidoreductases, 2=transferases, 3=hydrolases, 4=lyases, 5=isomerases, 6=ligases, 7=translocases)
- **Second level**: Substrate type or bond acted upon
- **Third level**: More specific substrate or co-factor
- **Fourth level**: Specific enzyme

For example, EC 4.2.1.1 (carbonic anhydrase): class 4 (lyase), subclass 4.2 (carbon-oxygen lyases), sub-subclass 4.2.1 (hydro-lyases), enzyme 4.2.1.1 (carbonate dehydratase).

### Why Computational Enzyme Design Matters

Engineering new enzymes is important for:
- **Industrial biocatalysis**: Enzymes that function at high temperatures, extreme pH, or in organic solvents for chemical manufacturing
- **Pharmaceutical synthesis**: Stereoselective catalysts for drug production
- **Environmental remediation**: Enzymes that degrade pollutants or plastics
- **Carbon capture**: Engineered carbonic anhydrases for CO2 sequestration
- **Diagnostics**: Enzyme-based biosensors

Traditional enzyme engineering (directed evolution) requires multiple rounds of mutagenesis and screening, which is time-consuming and expensive. Computational design tools like ZymCTRL can dramatically accelerate this process by generating diverse candidate sequences for experimental testing, reducing the search space from astronomical (20^N possible sequences for an N-residue protein) to a manageable set of high-probability candidates.

### Key Terminology

- **EC number**: Enzyme Commission classification number specifying catalytic function (e.g., 3.5.5.1)
- **Perplexity**: Information-theoretic measure of how well a sequence fits the model's learned distribution. Lower values indicate the model considers the sequence more "enzyme-like" for the given EC class. Threshold of <1.75 recommended for high-quality candidates.
- **Control tag**: The EC number prepended to the sequence during training and generation, which conditions the model's output on a specific catalytic function
- **Zero-shot generation**: Generating enzymes for an EC class without additional fine-tuning on that specific class
- **Biocatalysis**: Using enzymes to catalyze chemical reactions in industrial processes

---

*See also: [README.md](README.md) for API reference | [MODEL.md](MODEL.md) for technical details*
