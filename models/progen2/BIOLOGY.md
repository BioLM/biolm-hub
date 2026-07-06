# ProGen2 -- Biological Context

## Molecule Coverage

### Primary Molecule Type(s)

ProGen2 is trained on protein sequences and is designed for protein sequence generation. The model's capabilities vary by variant:

- **General protein variants** (medium, large, bfd90): Trained on large-scale protein databases (UniRef90, BFD90) covering proteins from all domains of life -- bacteria, archaea, eukaryota, and viruses. These variants handle globular proteins well and can generate plausible sequences for most protein families represented in the training data.
- **Antibody-specific variant** (oas): Trained exclusively on the Observed Antibody Space database, covering paired and unpaired antibody variable region sequences from diverse immune repertoires. This variant is specialized for antibody sequence generation and will produce poor results on non-antibody proteins.

Performance characteristics by protein type:
- **Globular, soluble proteins**: Strong generation quality. These dominate the training data for medium/large/bfd90 variants.
- **Enzymes**: Well-represented in training data. The model can generate plausible enzyme sequences, though it has no explicit understanding of catalytic mechanisms.
- **Antibodies**: Best served by the OAS variant. General variants can generate antibody-like sequences but lack the specificity of the OAS-trained model.
- **Membrane proteins**: Under-represented in training data. Generated sequences may not faithfully reproduce transmembrane topology.
- **Intrinsically disordered proteins**: Poorly modeled -- the autoregressive objective may struggle with low-complexity, repetitive regions.

### Cross-Applicability

| Molecule Type | Applicability | Evidence | Caveats |
|--------------|---------------|----------|---------|
| Antibodies | High (OAS variant) / Moderate (general variants) | OAS variant trained on 554M antibody sequences (clustered at 85% identity from ~1.5B raw OAS sequences) | OAS variant is antibody-only; general variants lack CDR-specific knowledge |
| Enzymes | High | BFD90 and UniRef90 training data are rich in enzyme families | No explicit modeling of active sites, cofactor binding, or catalytic residues |
| Peptides | Low--Moderate | Short sequences provide limited context for autoregressive generation | Context window may be too short for meaningful conditioning; consider peptide-specific models |
| Therapeutic proteins (non-antibody) | Moderate | General protein training covers many therapeutic targets | No explicit optimization for developability, immunogenicity, or stability |
| Fibrous proteins | Low | Under-represented in training; repetitive sequences are difficult to model autoregressively | Generated sequences may degenerate into repeats |

## Biological Problems Addressed

### Protein Sequence Generation (De Novo Design)

**Problem**: Designing entirely new protein sequences that fold into functional structures is a central challenge in protein engineering. Traditional approaches rely on directed evolution (iterative rounds of mutation and selection) or rational design (structure-guided mutagenesis), both of which are experimentally expensive and limited in the sequence space they can explore.

**How ProGen2 helps**: The `generate` action takes a short amino acid context (seed sequence) and autoregressively extends it, sampling from the learned distribution of natural proteins. The model has internalized statistical patterns of amino acid co-occurrence, secondary structure preferences, and long-range dependencies from millions of protein sequences. Generated sequences are biologically plausible completions of the given context.

**Biological meaning**: A generated sequence with a high log-likelihood (ll_mean close to 0) is one that the model considers consistent with natural protein sequences -- it follows the "grammar" of proteins. Lower likelihoods suggest the sequence deviates from natural patterns and may be less likely to fold or function. The num_samples parameter allows generating multiple candidates for experimental screening.

**Practical considerations**: Generated sequences should be validated computationally (e.g., structure prediction with ESMFold or Chai-1, stability estimation with ThermoMPNN) before experimental testing. ProGen2 generates sequences that look statistically natural but provides no guarantee of function.

### Protein Fitness Prediction (Sequence Scoring)

**Problem**: Given a set of protein sequence variants (e.g., from a mutagenesis library), predicting which variants retain function, fold correctly, or have improved properties. Experimental characterization of every variant is infeasible for large libraries.

**How ProGen2 helps**: Each generated sequence receives a log-likelihood score (ll_sum and ll_mean) computed as the average of forward and reverse autoregressive log-probabilities. These scores correlate with experimental measures of protein fitness -- sequences with higher log-likelihood tend to be more functional, stable, and well-folded.

**Biological meaning**: The log-likelihood measures how "natural" a sequence appears under the model's learned distribution. Deleterious mutations that disrupt conserved patterns reduce the likelihood; neutral or beneficial mutations at tolerant positions maintain or increase it. The bidirectional averaging (forward + reverse) reduces positional bias inherent in left-to-right autoregressive models.

### Directed Evolution Guidance

**Problem**: Directed evolution campaigns generate large mutant libraries but require efficient screening to identify improved variants. Computational pre-screening can reduce the experimental burden by orders of magnitude.

**How ProGen2 helps**: By generating sequences conditioned on a starting context (the wild-type or a promising variant), ProGen2 produces a focused library of plausible next-step sequences. The accompanying likelihood scores enable ranking without additional computation. Researchers can select the top-scoring candidates for experimental characterization.

**Biological meaning**: The context-conditioned generation mimics natural sequence diversification -- the model generates sequences that are plausible relatives of the input, much as natural evolution produces homologs through mutation and selection. The temperature parameter controls the "evolutionary distance" from the context: low temperature produces conservative variants, high temperature produces more diverse (but potentially less stable) sequences.

## Applied Use Cases

ProGen2 and its predecessor ProGen have been used in several applied settings:

- **Enzyme design**: Generating novel enzyme sequences for industrial biocatalysis, followed by experimental validation of folding and activity

  > **Note**: This is an anticipated use case based on the model's capabilities.

- **Antibody library design**: Using the OAS variant to generate diverse antibody variable region sequences for therapeutic screening campaigns

  > **Note**: This is an anticipated use case based on the model's capabilities.

- **Protein fitness landscapes**: Scoring mutant libraries to predict the effect of mutations on protein function, complementing deep mutational scanning experiments

  > **Note**: This is an anticipated use case based on the model's capabilities.

- **Sequence in-filling**: Using context-conditioned generation to propose plausible sequences for protein regions with missing or ambiguous annotation

  > **Note**: This is an anticipated use case based on the model's capabilities.

## Related Models

### Predecessor Models

- **ProGen** (Madani et al., 2023): The original ProGen model, a conditional transformer trained with taxonomy and function tags. ProGen2 removes the conditioning tags and focuses on pure sequence modeling at larger scale. ProGen is not available on the BioLM platform.

### Complementary Models

ProGen2 is often used in multi-step computational workflows:

- **ProGen2 + ESMFold/Chai-1**: Generate sequences with ProGen2, then predict their 3D structures with a structure prediction model to filter for foldable designs
- **ProGen2 + ThermoMPNN**: Generate sequences, then predict stability changes (ddG) to select candidates with desirable thermal properties
- **ProGen2 + ESM-2**: Use ESM-2 embeddings to cluster or characterize ProGen2-generated sequences, or use ESM-2 log-probabilities as an orthogonal fitness score

Typical workflow:
1. Generate candidate sequences with ProGen2 (diverse sampling, multiple seeds)
2. Score candidates with ESM-2 pseudo-log-likelihood
3. Predict structures for top candidates with Chai-1
4. Estimate stability changes for top candidates with ThermoMPNN
5. Select final candidates for experimental validation

### Alternative Models

| Alternative | Advantage Over ProGen2 | Disadvantage vs ProGen2 |
|-------------|----------------------|------------------------|
| ProtGPT2 | Simpler, widely available | Smaller model, trained on less diverse data |
| ESM-2 (masked prediction) | Better fitness prediction accuracy | Cannot generate sequences autoregressively |
| EvoDiff | Non-autoregressive diffusion enables guided generation | Newer, less benchmarked, slower sampling |
| Tranception | Better fitness prediction via retrieval augmentation | Primarily a scorer, not a generator |
| RFDiffusion | Structure-guided design (backbone + sequence) | Requires structural input, much more complex |

**When to choose ProGen2**: Use ProGen2 when you need to generate novel protein sequences from a context seed, especially when you want controllable diversity (temperature, top-p) and likelihood-based scoring. It is the strongest autoregressive protein generation model available on the platform.

**When to choose alternatives**: Consider ESM-2 for fitness prediction without generation; consider Chai-1 + MPNN for structure-guided sequence design; consider EvoDiff for non-autoregressive generation with potentially better diversity.

## Biological Background

Proteins are linear polymers of amino acids that fold into three-dimensional structures to carry out biological functions. The sequence of amino acids -- typically 50 to 2000 residues long, drawn from a 20-letter alphabet -- determines the protein's structure and function. Natural proteins have been shaped by billions of years of evolution, and the sequences that survive in nature represent a tiny but highly structured subset of all possible amino acid combinations.

**Protein generation**: The goal of computational protein generation is to produce novel amino acid sequences that fold into stable, functional structures. This is central to applications in drug development (designing therapeutic proteins), industrial biotechnology (engineering enzymes for chemical synthesis), and basic research (understanding the sequence-structure-function relationship). An autoregressive language model like ProGen2 learns the statistical rules governing natural protein sequences and can sample new sequences from this learned distribution.

**Autoregressive vs. masked language modeling**: In autoregressive modeling, the protein sequence is treated like a sentence, and each amino acid is predicted from all preceding amino acids (left-to-right). This naturally supports generation -- the model can extend a partial sequence indefinitely. In masked language modeling (e.g., ESM-2), random positions are hidden and predicted from bidirectional context, which produces better representations but does not support generation.

**Fitness landscapes**: In protein engineering, a "fitness landscape" maps every possible sequence variant to an experimentally measurable property (stability, activity, binding affinity). Language model log-likelihoods provide a computational approximation of this landscape -- sequences with high likelihood under the model tend to be functional, while low-likelihood sequences are more likely to be non-functional or deleterious.

**Key terminology**:
- **Autoregressive model**: A model that generates sequences one token at a time, each conditioned on all previous tokens.
- **Nucleus sampling (top-p)**: A sampling strategy that restricts token selection to the smallest set of tokens whose cumulative probability exceeds a threshold p. This balances diversity and quality.
- **Temperature**: A parameter that scales the model's output logits before sampling. Lower temperatures produce more conservative (higher-confidence) outputs; higher temperatures increase diversity.
- **Log-likelihood**: The logarithm of the probability assigned to a sequence by the model. Higher (less negative) values indicate the model considers the sequence more plausible.
- **N-terminal / C-terminal**: The two ends of a protein chain. The N-terminal has a free amino group (-NH2) and is conventionally written first; the C-terminal has a free carboxyl group (-COOH).
- **BFD (Big Fantastic Database)**: A large metagenomic protein sequence database compiled from soil, ocean, and gut metagenomes, clustered at various identity thresholds.
- **OAS (Observed Antibody Space)**: A database of antibody sequences from immune repertoire sequencing studies across multiple species and disease states.

---

*See also: [README.md](README.md) for API reference | [MODEL.md](MODEL.md) for technical details*
