# MSA Transformer -- Biological Context

## Molecule Coverage

### Primary Molecule Type(s)

The MSA Transformer operates on **protein Multiple Sequence Alignments (MSAs)** -- collections of evolutionarily related protein sequences aligned to a common coordinate system. It is designed to capture the patterns of amino acid conservation and covariation that arise from shared evolutionary history.

The model handles:
- **Globular proteins**: Excellent performance when deep MSAs (> 64 sequences) are available
- **Enzymes**: Strong coverage in UniRef50; active site conservation well-captured
- **Membrane proteins**: Functional but may have shallower MSAs due to under-representation in databases
- **Antibodies**: Variable regions may have limited homologs; framework regions are better represented

Input requirements:
- The first sequence in the MSA is the **query** (reference) sequence
- All sequences must be **pre-aligned** to identical length
- Gap character (`-`) and insert character (`.`) are supported
- Standard and extended amino acid alphabet accepted

### Cross-Applicability

| Molecule Type | Applicability | Evidence | Caveats |
|---------------|---------------|----------|---------|
| Protein families (deep MSAs) | High | Core design purpose; 26M MSAs in training | Best with >= 64 sequences in MSA |
| Enzymes | High | Well-represented in UniRef50 | Active site covariation well-captured |
| Antibodies | Moderate | Variable regions have limited homologs | CDRs may lack evolutionary signal; consider antibody-specific models |
| Orphan proteins | Low | Requires homologs for MSA construction | No benefit over single-sequence models if homologs unavailable |
| Peptides | Low | Very short alignments provide minimal signal | Consider peptide-specific models |
| DNA/RNA | Not applicable | Protein-only model | Use Evo, NT, or RNA-specific models |
| Protein complexes | Not supported | Single-chain MSA input only | Concatenated MSAs could work but are not validated |

## Biological Problems Addressed

### Problem 1: Evolutionary Covariation Analysis

**Why this matters**: When two positions in a protein are in physical contact in the 3D structure, mutations at one position create evolutionary pressure for compensatory mutations at the other. This "covariation" signal is the basis for unsupervised protein structure prediction and has been used since the 1990s (e.g., DCA, PSICOV, Gremlin). However, traditional covariation methods require hundreds of sequences and struggle with indirect correlations.

**How MSA Transformer addresses it**: The tied row attention mechanism naturally learns to attend to covarying positions. By extracting and symmetrizing the attention maps, the model produces **contact predictions** without any supervised training on known structures. The APC (Average Product Correction) applied to the attention maps removes background correlations, revealing direct contacts.

**Biological meaning**: High-scoring entries in the contact map indicate residue pairs likely to be within ~8 Angstroms in the protein's 3D structure. Long-range contacts (positions far apart in sequence but close in space) are particularly informative for determining the protein's fold.

### Problem 2: MSA-Aware Protein Representation Learning

**Why this matters**: Single-sequence protein language models (e.g., ESM-2) learn representations from individual sequences, capturing the "grammar" of amino acid sequences. However, the evolutionary signal encoded in MSAs -- which positions are conserved, which covary, which are free to vary -- provides additional information about protein structure and function that single-sequence models cannot directly access.

**How MSA Transformer addresses it**: The `encode` action produces embeddings that incorporate both within-sequence context (row attention) and evolutionary context (column attention). These MSA-aware embeddings capture information about:
- **Conservation**: Positions with low variation across the MSA are likely functionally important
- **Covariation**: Positions that change in concert across the MSA are likely structurally coupled
- **Insertion/deletion patterns**: Gap distributions reveal loop regions and domain boundaries

**Biological meaning**: MSA Transformer embeddings can be more informative than single-sequence ESM-2 embeddings for tasks where evolutionary signal is important -- protein family classification, function prediction, and structure-informed applications. The tradeoff is requiring a pre-computed MSA as input.

### Problem 3: Unsupervised Protein Structure Insight

**Why this matters**: Before AlphaFold2, unsupervised contact prediction from MSAs was one of the primary routes to protein structure information. While AlphaFold2 has largely superseded this for full structure prediction, fast contact maps remain useful for:
- Quick structural assessment of novel proteins
- Validating MSA quality (do predicted contacts match known structure?)
- Identifying structurally important residue pairs for mutagenesis

**How MSA Transformer addresses it**: The `contacts` output from the `encode` action provides a fast, unsupervised estimate of the protein's contact map. At the time of publication (2021), this was state-of-the-art among purely unsupervised methods.

## Applied Use Cases

### Use Case 1: Unsupervised Contact Prediction (Published)

**Source**: Rao R, Liu J, Verkuil R, Meier J, Canny J, Abbeel P, Sercu T, Rives A. "MSA Transformer." ICML (2021). [DOI: 10.1101/2021.02.12.430858](https://doi.org/10.1101/2021.02.12.430858)

The paper demonstrates that tied row attention maps, after symmetrization and APC correction, produce contact predictions that outperform previous attention-based methods and approach the accuracy of dedicated covariation analysis tools.

### Use Case 2: Transfer Learning with MSA Features (Anticipated)

Using MSA Transformer embeddings as input features for downstream classifiers -- enzyme function prediction, thermostability classification, or binding site identification -- where evolutionary context provides additional signal beyond single-sequence representations.

## Related Models

### Complementary Models

- **ESM-2**: Single-sequence protein embeddings. For proteins without deep MSAs, use ESM-2. For proteins with rich evolutionary data, MSA Transformer provides complementary evolutionary signal.
- **ESMFold**: Uses ESM-2 embeddings for full 3D structure prediction. MSA Transformer contacts can serve as a quick structural check before running the more expensive ESMFold.
- **Chai-1 / RF3**: Full structure prediction from sequences and MSAs. Use these when you need atomic-level 3D structures rather than contact maps.

### Alternative Models

| Alternative | Advantage over MSA Transformer | Disadvantage vs MSA Transformer |
|-------------|-------------------------------|--------------------------------|
| ESM-2 | No MSA required; fast single-sequence inference | Cannot capture covariation; no contact prediction from attention |
| AlphaFold2 | Full atomic 3D structure | Much heavier; requires templates; overkill for contact-level analysis |
| EVCouplings / DCA | Mathematically principled covariation analysis | Slower; requires very deep MSAs; no learned representations |

## Biological Background

**Multiple Sequence Alignment (MSA)**: A collection of protein sequences from different organisms that share a common ancestor, aligned so that homologous positions are in the same column. MSAs are the primary data structure for studying protein evolution.

**Key concepts relevant to MSA Transformer**:

- **Evolutionary covariation**: When two positions in a protein are structurally coupled (e.g., in physical contact), a mutation at one position often requires a compensatory mutation at the other to maintain function. This creates statistical correlations in the MSA that can be detected computationally.
- **Contact prediction**: Predicting which residue pairs are physically close (< 8 Angstroms) in the 3D structure from sequence information alone. Long-range contacts (positions separated by > 12 residues in sequence) are the most informative for fold determination.
- **Axial attention**: A decomposition of attention into row (across positions) and column (across sequences) components, reducing computational complexity while preserving the ability to capture both within-sequence and between-sequence relationships.
- **Tied row attention**: Sharing attention weights across all sequences in the MSA. This constraint forces the model to learn position-level patterns that are consistent across the entire alignment, naturally encoding structural constraints.
- **APC (Average Product Correction)**: A statistical correction applied to covariation scores that removes the effect of phylogenetic bias and uneven amino acid composition, revealing direct contacts.
- **MSA depth**: The number of sequences in an alignment. Deeper MSAs provide stronger covariation signal. Performance degrades significantly below 16 sequences.

---

*See also: [README.md](README.md) for API reference | [MODEL.md](MODEL.md) for technical details*
