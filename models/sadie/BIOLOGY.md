# SADIE -- Biological Context

## Molecule Coverage

### Primary Molecule Type(s)

SADIE is designed for antibody and T-cell receptor (TCR) sequence annotation. It processes amino acid sequences and identifies immunoglobulin/TCR domains, assigns numbering according to standard schemes, and annotates framework and complementarity-determining regions.

SADIE handles the following chain types:

- **Heavy chains (H)**: Full or partial variable domain sequences. SADIE identifies FWR1-4 and CDR1-3 boundaries, assigns germline V and J genes, and provides numbering.
- **Kappa light chains (K)**: Variable domain annotation with kappa-specific germline assignment.
- **Lambda light chains (L)**: Variable domain annotation with lambda-specific germline assignment.
- **TCR alpha chains (A)**: T-cell receptor alpha chain annotation.
- **TCR beta chains (B)**: T-cell receptor beta chain annotation.
- **TCR gamma chains (G)**: T-cell receptor gamma chain annotation.
- **TCR delta chains (D)**: T-cell receptor delta chain annotation.

### Cross-Applicability

| Molecule Type | Applicability | Evidence | Caveats |
|--------------|---------------|----------|---------|
| Antibody heavy chains | High | Primary use case | Supports H chain fully |
| Antibody light chains (kappa/lambda) | High | Primary use case | Supports K and L chains |
| TCR chains (alpha/beta/gamma/delta) | High | Supported via `allowed_chain` parameter | TCR-specific HMM profiles |
| Nanobodies (VHH) | Moderate | Processed as H chains | May not distinguish VHH-specific hallmark positions |
| scFv sequences | High | Supported via `scfv=True` parameter | Both VH and VL domains identified in a single sequence |
| General proteins | Not applicable | Annotation tool for immunoglobulins/TCRs only | Will fail or produce meaningless results |

## Biological Problems Addressed

### Antibody Sequence Numbering

**Problem**: Antibody variable domain sequences vary in length, particularly in CDR loops. Comparing sequences across different antibodies requires a consistent numbering system that aligns corresponding positions. Multiple numbering schemes exist (IMGT, Kabat, Chothia), each with different conventions, and researchers need to convert between them.

**How SADIE helps**: The `predict` action assigns positional numbers to each residue according to the selected numbering scheme (IMGT, Kabat, or Chothia). The output includes both the numbering and insertion codes, enabling precise position-by-position comparison across antibodies.

**Biological meaning**: Numbered positions correspond to structurally equivalent locations across antibodies. For example, IMGT position 104 is always the conserved cysteine forming the intra-domain disulfide bond, regardless of the specific antibody sequence. This structural correspondence is the foundation for comparative antibody analysis.

### Region Identification

**Problem**: Identifying framework regions (FWR1-4) and complementarity-determining regions (CDR1-3) is essential for antibody engineering. CDR definitions vary across schemes -- IMGT, Kabat, Chothia, AbM, Contact, and SCDR all define different boundaries for the CDR loops. Manually applying these definitions is error-prone.

**How SADIE helps**: The `predict` action outputs the amino acid sequences of each region (FWR1, CDR1, FWR2, CDR2, FWR3, CDR3, FWR4) both with gaps (aligned to the numbering scheme) and without gaps (raw sequence). The `region_assign` parameter selects which CDR definition to use.

**Biological meaning**: CDR loops are the primary determinants of antigen binding specificity. Different CDR definitions capture different structural boundaries -- Chothia defines CDRs based on canonical loop structures, Kabat defines them based on sequence variability, IMGT uses a standardized system based on the IMGT unique numbering, AbM is a hybrid approach, and Contact defines CDRs based on antigen contact analysis. The choice of definition affects downstream engineering decisions.

### Germline Gene Assignment

**Problem**: Determining which germline V and J gene segments encode an antibody variable domain is critical for understanding the antibody's developmental origin, assessing somatic hypermutation burden, and guiding humanization efforts.

**How SADIE helps**: The `predict` action identifies the closest V-gene and J-gene matches along with identity percentages (`v_identity`, `j_identity`). It also reports the species of origin (`hmm_species`, `identity_species`) and alignment quality metrics (`e_value`, `score`).

**Biological meaning**: The V-gene identity percentage indicates how much somatic hypermutation has occurred relative to the germline. High V-gene identity (>95%) suggests a naive or minimally matured antibody, while lower identity (80-90%) indicates extensive affinity maturation. J-gene assignment helps define the junction region at the CDR3 boundary.

### scFv Domain Parsing

**Problem**: Single-chain variable fragments (scFvs) contain both VH and VL domains connected by a peptide linker. Identifying the boundaries of each domain and parsing them separately is necessary for downstream analysis.

**How SADIE helps**: When `scfv=True` is set, SADIE identifies both VH and VL domains within a single input sequence, annotating each domain independently.

**Biological meaning**: scFv constructs are widely used in therapeutic antibody formats (e.g., CAR-T cells, bispecific antibodies). Automated domain parsing enables high-throughput analysis of scFv libraries.

## Applied Use Cases

SADIE is used as a preprocessing step in antibody engineering pipelines:

- **Antibody repertoire analysis**: Number and annotate thousands of sequences from NGS data for downstream statistical analysis (published)
- **Humanization assessment**: Compare germline gene assignments and mutation patterns between species (published)
- **CDR extraction**: Extract CDR sequences for clustering, diversity analysis, or input to CDR-focused models (published)
- **Quality control**: Validate antibody sequences and identify truncated or mis-annotated sequences (published)
- **Multi-model pipeline preprocessing**: Annotate sequences before passing to AbLang2, IgBERT, or IgT5 for embedding (anticipated)

## Related Models

### Complementary Models

SADIE serves as a preprocessing tool that feeds into other models in this catalog:

- **AbLang2**: Use SADIE to extract and number variable domains, then AbLang2 for embedding and scoring
- **IgBERT/IgT5**: Use SADIE for annotation, then IgBERT/IgT5 for embedding
- **Nanobodies / VHH**: Use SADIE to identify VHH domains, then the unpaired IgBERT or IgT5 variant for embedding

Typical multi-model workflows:
1. Use SADIE `predict` to annotate and number sequences
2. Use germline assignment and CDR extraction for quality filtering
3. Feed annotated variable domains into embedding models (AbLang2, IgBERT, IgT5)
4. Use embedding models for downstream analysis (clustering, scoring, design)

### Alternative Tools

| Alternative | Advantage Over SADIE | Disadvantage vs SADIE |
|-------------|---------------------|---------------------|
| ANARCI | Widely adopted, standalone C implementation | Numbering only, no germline assignment, no region parsing |
| IMGT/DomainGapAlign | Gold standard IMGT numbering | Web-based, not programmatically accessible at scale |
| IgBLAST | NCBI-backed, comprehensive alignment | Complex output, requires local BLAST installation |
| AbNumber | Fast numbering | Limited to numbering, fewer scheme options |

**When to choose SADIE**: Use SADIE when you need combined numbering, region annotation, germline assignment, and species detection in a single API call, especially as part of an automated pipeline.

**When to choose alternatives**: Consider ANARCI for standalone numbering in local environments; consider IMGT/DomainGapAlign for gold-standard IMGT validation; consider IgBLAST for comprehensive alignment analysis.

## Biological Background

The adaptive immune system generates an enormous diversity of antigen receptors -- antibodies (immunoglobulins) and T-cell receptors (TCRs) -- to recognize and respond to pathogens. Each receptor molecule contains variable domains that determine binding specificity.

**Antibody structure**: Antibody variable domains consist of a conserved beta-sheet framework supporting hypervariable loops (CDRs). The framework provides structural stability, while the CDRs form the antigen-binding surface. Residue positions within the variable domain are structurally conserved across different antibodies, enabling standardized numbering systems.

**Numbering schemes**: Several numbering systems have been developed to provide consistent position labels across antibodies:
- **IMGT**: International ImMunoGeneTics numbering (Lefranc, 1999). Positions 1-128 for variable domains, with standardized gap positions. The most systematic and species-independent scheme.
- **Kabat**: Based on sequence variability analysis (Wu & Kabat, 1970). Historically the most widely used scheme, with CDR definitions based on sequence hypervariability.
- **Chothia**: Based on structural loop definitions (Chothia & Lesk, 1987). CDR boundaries correspond to canonical loop structures observed in crystal structures.
- **AbM** (Oxford Molecular): A hybrid combining Kabat and Chothia CDR definitions.
- **Contact**: Based on crystal structure analysis of antigen contacts (MacCallum et al., 1996).
- **SCDR**: Standardized CDR definition.

**V(D)J recombination and germline genes**: Antibody variable domains are encoded by rearranged germline gene segments. The heavy chain uses V (variable), D (diversity), and J (joining) gene segments; the light chain uses V and J segments. Identifying these germline genes is essential for understanding antibody development and engineering.

**Key terminology**:
- **Numbering scheme**: A system for assigning consistent position labels to residues in antibody variable domains.
- **CDR (Complementarity-Determining Region)**: Hypervariable loops that contact the antigen. Three per chain (CDR1, CDR2, CDR3).
- **Framework region (FWR)**: Conserved beta-sheet regions flanking the CDRs. Four per chain (FWR1, FWR2, FWR3, FWR4).
- **Germline gene**: The inherited, un-rearranged gene segment encoding a portion of the variable domain.
- **E-value**: Statistical measure of alignment quality from HMM search; lower values indicate better matches.
- **scFv (single-chain variable fragment)**: An antibody format where VH and VL are connected by a peptide linker.

---

*See also: [README.md](README.md) for API reference | [MODEL.md](MODEL.md) for technical details*
