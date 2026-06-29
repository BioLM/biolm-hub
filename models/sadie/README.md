# SADIE

> **One-line summary**: Algorithmic antibody and TCR sequence annotation tool that performs numbering (IMGT/Kabat/Chothia), region identification, germline gene assignment, and species detection from amino acid sequences.

## Overview

SADIE (Sequencing Analysis and Data Library for Immunoinformatics Exploration) is an antibody sequence analysis and annotation tool developed by Willis. Unlike the language models on this platform, SADIE is an algorithmic tool that uses HMM-based alignment to identify immunoglobulin and TCR domains, assign standardized residue numbering, annotate framework and CDR regions, and identify germline V and J gene segments.

SADIE serves as a critical preprocessing step in antibody engineering pipelines. It supports multiple numbering schemes (IMGT, Kabat, Chothia) and region definitions (IMGT, Kabat, Chothia, AbM, Contact, SCDR), handles antibody heavy chains, kappa and lambda light chains, all four TCR chain types, and single-chain variable fragments (scFv).

## Architecture

| Property | Value |
|----------|-------|
| Architecture | Algorithmic (HMM-based alignment) |
| Method | HMMER-based domain identification and numbering |
| Input | Amino acid sequences (antibody or TCR) |
| Max sequence length | 2048 residues |
| Chain support | H, K, L (antibody); A, B, G, D (TCR) |
| License | MIT |

## Model Variants

SADIE is a single-variant tool with no size options.

| Variant | GPU | Memory | CPU | Use Case |
|---------|-----|--------|-----|----------|
| `sadie` | None (CPU) | 1 GB | 0.125 cores | All antibody/TCR annotation tasks |

## Capabilities & Limitations

**CAN be used for:**
- Antibody variable domain numbering (IMGT, Kabat, Chothia schemes)
- CDR and framework region identification (6 region definitions)
- Germline V-gene and J-gene assignment with identity scores
- Species detection (HMM-based and identity-based)
- Chain type identification (heavy, kappa, lambda, TCR alpha/beta/gamma/delta)
- scFv domain parsing
- E-value-based alignment quality assessment

**CANNOT be used for:**
- Sequence embedding (use AbLang2, IgBERT, IgT5, or NanoBERT)
- Sequence generation or completion (use AbLang2 or IgBERT `generate`)
- Log-probability scoring (use AbLang2 or IgBERT `log_prob`)
- Non-immunoglobulin/non-TCR proteins
- 3D structure prediction

**Other considerations:**
- Runs on CPU only with minimal resource requirements
- Batch size capped at 8 sequences per request
- Processes sequences independently (no batch-level analysis)
- Requires Pydantic v1 compatibility (library constraint)

## Actions / Endpoints

### `predict`

Annotates antibody or TCR sequences with numbering, region boundaries, germline gene assignment, and quality metrics.

**Request Parameters:**

| Parameter | Type | Default | Range | Description |
|-----------|------|---------|-------|-------------|
| `items[].sequence` | str | *(required)* | 1--2048 chars | Amino acid sequence (extended alphabet) |
| `params.scheme` | str | `"chothia"` | `imgt`, `kabat`, `chothia` | Numbering scheme |
| `params.region_assign` | str | `"imgt"` | `imgt`, `kabat`, `chothia`, `abm`, `contact`, `scdr` | CDR/FWR region definition |
| `params.scfv` | bool | `false` | -- | Parse as single-chain variable fragment |
| `params.allowed_chain` | list[str] | `["H", "K", "L"]` | `H`, `K`, `L`, `A`, `B`, `G`, `D` | Chain types to consider |

**Response:**

```json
{
  "results": [
    {
      "domain_no": 0,
      "hmm_species": "human",
      "chain_type": "H",
      "e_value": 1.2e-50,
      "score": 180.5,
      "identity_species": "human",
      "v_gene": "IGHV3-23*01",
      "v_identity": 95.2,
      "j_gene": "IGHJ4*02",
      "j_identity": 92.3,
      "Chain": "H",
      "Numbering": [1, 2, 3, ...],
      "Insertion": ["", "", "", ...],
      "scheme": "chothia",
      "region_definition": "imgt",
      "fwr1_aa_gaps": "QVQLVQSGAEVKKPGASVKVSC...",
      "fwr1_aa_no_gaps": "QVQLVQSGAEVKKPGASVKVSC...",
      "cdr1_aa_gaps": "GYTFTS...",
      "cdr1_aa_no_gaps": "GYTFTS...",
      "fwr2_aa_gaps": "WVRQAPGQGLEWMG...",
      "fwr2_aa_no_gaps": "WVRQAPGQGLEWMG...",
      "cdr2_aa_gaps": "ISPY...",
      "cdr2_aa_no_gaps": "ISPY...",
      "fwr3_aa_gaps": "...",
      "fwr3_aa_no_gaps": "...",
      "cdr3_aa_gaps": "AR...",
      "cdr3_aa_no_gaps": "AR...",
      "fwr4_aa_gaps": "WGQGTTVTVSS",
      "fwr4_aa_no_gaps": "WGQGTTVTVSS",
      "leader": "",
      "follow": ""
    }
  ]
}
```

**Schema classes**: `SADIEPredictRequest` -> `SADIEPredictResponse`

**Response fields explained:**

| Field | Description |
|-------|-------------|
| `domain_no` | Domain index (0-based) within the input sequence |
| `hmm_species` | Species identified by HMM profile matching |
| `chain_type` | Detected chain type (H, K, L, A, B, G, D) |
| `e_value` | HMM alignment E-value (lower = better match) |
| `score` | HMM alignment score (higher = better match) |
| `identity_species` | Species from sequence identity analysis |
| `v_gene` / `v_identity` | Closest V-gene and percent identity |
| `j_gene` / `j_identity` | Closest J-gene and percent identity |
| `Numbering` / `Insertion` | Per-residue numbering and insertion codes |
| `fwr*_aa_gaps` / `fwr*_aa_no_gaps` | Framework region sequences (with/without alignment gaps) |
| `cdr*_aa_gaps` / `cdr*_aa_no_gaps` | CDR sequences (with/without alignment gaps) |
| `leader` / `follow` | Sequence before FWR1 / after FWR4 |

## Usage Examples

```python
# Predict -- annotate an antibody heavy chain
from models.sadie.schema import (
    SADIEPredictRequest,
    SADIEPredictRequestItem,
    SADIEPredictRequestParams,
)

predict_request = SADIEPredictRequest(
    params=SADIEPredictRequestParams(
        scheme="chothia",
        region_assign="imgt",
        scfv=False,
        allowed_chain=["H", "K", "L"],
    ),
    items=[
        SADIEPredictRequestItem(
            sequence="QVQLVQSGAEVKKPGASVKVSCKASGYTFTSYGISWVRQAPGQGLEWMGWISAYNGNTNYAQKLQGRVTMTTDTSTSTAYMELRSLRSDDTAVYYCARDGYSSGYYGMDVWGQGTTVTVSS",
        ),
    ],
)

# Annotate with IMGT numbering and Kabat region definitions
predict_imgt = SADIEPredictRequest(
    params=SADIEPredictRequestParams(
        scheme="imgt",
        region_assign="kabat",
    ),
    items=[
        SADIEPredictRequestItem(
            sequence="DIQMTQSPSSVSASVGDRVTITCRASQSIGSFLAWYQQKPGKAPKLLIYEASTLKPGVPSRFSGSGSGTDFTLTISSLQPEDFANYYCHQYAAYPWTFGGGTKVEIK",
        ),
    ],
)

# Parse an scFv sequence
predict_scfv = SADIEPredictRequest(
    params=SADIEPredictRequestParams(
        scfv=True,
    ),
    items=[
        SADIEPredictRequestItem(
            sequence="QVQLVQSGAEVKKPGASVKVSCKASGYTFTSYGISWVRQAPGQGLEWMGWISAYNGNTNYAQKLQGRVTMTTDTSTSTAYMELSSLRSEDTAVYYCARDGYSSGYYGMDVWGQGTTVTVSSGGGGSGGGGSGGGGSDIQMTQSPSSVSASVGDRVTITCRASQSIGSFLAWYQQKPGKAPKLLIYEASTLKPGVPSRFSGSGSGTDFTLTISSLQPEDFANYYCHQYAAYPWTFGGGTKVEIK",
        ),
    ],
)
```

## Performance & Benchmarks

### Published Results

SADIE is an algorithmic tool; its accuracy is determined by the quality of HMM profiles and reference databases rather than learned model parameters.

### SOTA Status

SADIE provides a programmatic interface comparable to established tools like ANARCI, IMGT/DomainGapAlign, and IgBLAST for antibody annotation, with the advantage of combining numbering, region annotation, and germline assignment in a single API call.

## Implementation Verification

### Verification Method

Output comparison: The BioLM implementation uses the `sadie-antibody` PyPI package (v1.0.6). Test fixtures compare annotation outputs against golden reference outputs stored in R2.

### Test Cases

| Test Case | Action | Input | Verification |
|-----------|--------|-------|--------------|
| Antibody annotation | `predict` | Antibody sequence | Exact match to golden output (rel_tol 1e-5 for float fields) |

### Verification Status

**Status: VERIFIED** -- Integration tests pass with rel_tol=1e-5.

## Resource Requirements

| Variant | GPU | Memory | CPU |
|---------|-----|--------|-----|
| `sadie` | None (CPU) | 1 GB | 0.125 cores |

## Implementation Notes

- **Memory snapshots**: SADIE uses `@modal.enter(snap=True)` to import the `Renumbering` class into the memory snapshot (the HMM databases are loaded on first request, not snapshotted); `@modal.enter(snap=False)` logs the ready state.
- **Determinism**: SADIE is fully deterministic -- HMM alignment is not stochastic.
- **Dependencies**: `sadie-antibody==1.0.6` (requires Pydantic v1 internally; accommodated in schema design).
- **Sequence hashing**: Sequences are hashed with SHA-256 for internal tracking.
- **No GPU**: SADIE runs entirely on CPU with minimal resource allocation.
- **Caching**: Response caching is handled outside the model container.

## License

- **Code**: MIT ([LICENSE](https://github.com/jwillis0720/sadie/blob/main/LICENSE))
- **Library**: MIT (same license for sadie-antibody package)

## References & Citations

### Papers

1. Willis JR. "SADIE: Sequencing Analysis and Data Library for Immunoinformatics Exploration." (2022). Software tool — no peer-reviewed paper published. Available via GitHub and PyPI.

### BibTeX

```bibtex
@software{willis2022sadie,
  title={SADIE: Sequencing Analysis and Data Library for Immunoinformatics Exploration},
  author={Willis, Jordan R and Sincomb, Troy M and Kibet, Caleb K},
  year={2022},
  url={https://github.com/jwillis0720/sadie}
}
```

### Links

- **Code**: [github.com/jwillis0720/sadie](https://github.com/jwillis0720/sadie)
- **PyPI**: [pypi.org/project/sadie-antibody](https://pypi.org/project/sadie-antibody/)

---

*See also: [MODEL.md](MODEL.md) for technical deep-dive | [BIOLOGY.md](BIOLOGY.md) for biological context*
