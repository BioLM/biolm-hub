# AbLang2

> **One-line summary**: Germline-debiased paired antibody language model that produces sequence embeddings, residue embeddings, likelihood scores, and sequence restoration for paired heavy-light chain antibody sequences.

## Overview

AbLang2 (Antibody Language Model 2) is a paired antibody language model developed by Olsen, Moal, and Deane at the Oxford Protein Informatics Group. It is trained with a masked language modeling objective on paired heavy-light chain sequences from the Observed Antibody Space (OAS) database, with explicit germline debiasing to produce representations that capture functional properties rather than germline gene identity.

AbLang2 improves on its predecessor AbLang by (1) modeling paired heavy-light sequences jointly to capture inter-chain dependencies and (2) correcting for germline bias, which otherwise dominates learned representations. This makes AbLang2 particularly suited for antibody engineering tasks where functional similarity matters more than germline origin.

## Architecture

| Property | Value |
|----------|-------|
| Architecture | Transformer encoder (BERT-style) |
| Training objective | Masked language modeling (MLM) |
| Training data | Observed Antibody Space (OAS) -- paired sequences |
| Max sequence length | 1024 tokens per chain |
| Input format | Paired heavy+light: `<heavy>\|<light>` |
| Positional encoding | Rotary position embeddings |
| License | BSD-3-Clause |

## Model Variants

AbLang2 is a single-variant model with no size options.

| Variant | GPU | Memory | CPU | Use Case |
|---------|-----|--------|-----|----------|
| `ablang2` | None (CPU) | 4 GB | 2 cores | All antibody embedding and scoring tasks |

## Capabilities & Limitations

**CAN be used for:**
- Generating germline-debiased sequence-level embeddings for paired antibodies (`seqcoding`)
- Generating per-residue embeddings for paired antibodies (`rescoding`)
- Computing per-position logits (unnormalized scores) for antibody sequences
- Restoring missing residues in antibody sequences (sequence completion)
- Zero-shot antibody sequence scoring via log-probability (`log_prob`)

**CANNOT be used for:**
- Single-chain (unpaired) antibody analysis -- both heavy and light chains are required
- Non-antibody proteins (use ESM-2 or similar)
- Nanobody / VHH sequences (use the unpaired IgBERT or IgT5 variant)
- 3D structure prediction (use AntiFold, ESMFold, or similar)
- Antibody numbering and annotation (use SADIE)

**Other considerations:**
- Runs on CPU only -- no GPU required
- Batch size capped at 32 sequences per request
- `align=True` option for rescoding/restore is not yet supported (requires ANARCI dependency)

## Actions / Endpoints

### `encode`

Generates sequence-level (`seqcoding`) or residue-level (`rescoding`) embeddings for paired heavy-light antibody sequences.

**Request Parameters:**

| Parameter | Type | Default | Range | Description |
|-----------|------|---------|-------|-------------|
| `items[].heavy_chain` | str | *(required)* | 1--1024 chars | Heavy chain amino acid sequence |
| `items[].light_chain` | str | *(required)* | 1--1024 chars | Light chain amino acid sequence |
| `params.include` | str | `"seqcoding"` | `seqcoding`, `rescoding` | Embedding mode |
| `params.align` | bool | `false` | -- | Alignment mode (rescoding only; not yet supported) |

**Response (seqcoding):**

```json
{
  "results": [
    {
      "embeddings": [0.012, -0.034, ...]
    }
  ]
}
```

**Response (rescoding):**

```json
{
  "results": [
    {
      "residue_embeddings": [[0.012, -0.034, ...], ...]
    }
  ],
  "number_alignment": null
}
```

**Schema classes**: `AbLang2EncodeRequest` -> `AbLang2EncodeResponse`

### `predict`

Returns per-position logits over the 20 canonical amino acids for paired antibody sequences.

**Request Parameters:**

| Parameter | Type | Default | Range | Description |
|-----------|------|---------|-------|-------------|
| `items[].heavy_chain` | str | *(required)* | 1--1024 chars | Heavy chain amino acid sequence |
| `items[].light_chain` | str | *(required)* | 1--1024 chars | Light chain amino acid sequence |

**Response:**

```json
{
  "results": [
    {
      "logits": [[0.1, -0.3, ...], ...],
      "sequence_tokens": ["<", "Q", "V", ...],
      "vocab_tokens": ["A", "R", "N", ...]
    }
  ]
}
```

`logits` shape is `[L, 20]` where L is the total paired sequence length and 20 is the canonical amino acid vocabulary. Values are raw logits (not probabilities); use `log_softmax` to obtain log-probabilities.

**Schema classes**: `AbLang2PredictRequest` -> `AbLang2PredictResponse`

### `generate`

Restores missing residues marked with `*` in paired antibody sequences by predicting the most likely amino acid at each masked position.

**Request Parameters:**

| Parameter | Type | Default | Range | Description |
|-----------|------|---------|-------|-------------|
| `items[].heavy_chain` | str | *(required)* | 1--1024 chars | Heavy chain with `*` at unknown positions |
| `items[].light_chain` | str | *(required)* | 1--1024 chars | Light chain with `*` at unknown positions |
| `params.align` | bool | `false` | -- | Alignment mode (not yet supported) |

At least one `*` must be present across the combined heavy+light sequence.

**Response:**

```json
{
  "results": [
    {
      "heavy_chain": "QVQLVQSGGQMKKPGSSVRVSCKASGYTFTNYGMNWVRQAPGQGLEWMGRI",
      "light_chain": "DIQMTQSPSSLSASVGDRVTITCKASQDVSTAVA"
    }
  ]
}
```

**Schema classes**: `AbLang2GenerateRequest` -> `AbLang2GenerateResponse`

### `log_prob`

Computes the total log-probability of paired antibody sequences under the AbLang2 model. Useful for zero-shot sequence scoring and variant effect prediction.

**Request Parameters:**

| Parameter | Type | Default | Range | Description |
|-----------|------|---------|-------|-------------|
| `items[].heavy_chain` | str | *(required)* | 1--1024 chars | Heavy chain amino acid sequence |
| `items[].light_chain` | str | *(required)* | 1--1024 chars | Light chain amino acid sequence |

**Response:**

```json
{
  "results": [
    {
      "log_prob": -245.67
    }
  ]
}
```

More negative values indicate less likely sequences. Compare wild-type vs mutant log-probabilities to score variant effects.

**Schema classes**: `AbLang2LogProbRequest` -> `AbLang2LogProbResponse`

## Usage Examples

```python
# Encode -- get sequence-level embeddings
from models.ablang2.schema import (
    AbLang2EncodeRequest,
    AbLang2EncodeParams,
    AbLang2SequenceItem,
)

encode_request = AbLang2EncodeRequest(
    params=AbLang2EncodeParams(include="seqcoding"),
    items=[
        AbLang2SequenceItem(
            heavy_chain="QVQLVQSGGQMKKPGSSVRVSCKASGYTFTNYGMNWVRQAPGQGLEWMGRI",
            light_chain="DIQMTQSPSSLSASVGDRVTITCKASQDVSTAVA",
        ),
    ],
)

# Generate -- restore missing residues
from models.ablang2.schema import (
    AbLang2GenerateRequest,
    AbLang2MissingSequenceItem,
    AbLang2RestoreParams,
)

generate_request = AbLang2GenerateRequest(
    params=AbLang2RestoreParams(align=False),
    items=[
        AbLang2MissingSequenceItem(
            heavy_chain="QVQLVQ*GGQMKKPGSSVRVSCKASGYTFTNYGMN**VRQAPGQGLEWMGRI",
            light_chain="DIQMTQSPSSLSA*VGDRVTITCKASQDVSTAVA",
        ),
    ],
)

# Predict log probability -- sequence scoring
from models.ablang2.schema import AbLang2LogProbRequest, AbLang2SequenceItem

log_prob_request = AbLang2LogProbRequest(
    items=[
        AbLang2SequenceItem(
            heavy_chain="QVQLVQSGGQMKKPGSSVRVSCKASGYTFTNYGMNWVRQAPGQGLEWMGRI",
            light_chain="DIQMTQSPSSLSASVGDRVTITCKASQDVSTAVA",
        ),
    ],
)
```

## Performance & Benchmarks

### Published Results

AbLang2 was evaluated on antibody humanization scoring, CDR restoration accuracy, and embedding quality for functional clustering.

From Olsen et al. (2024): AbLang-2 achieves near-perfect germline prediction (perplexity ~1.1) while significantly improving non-germline (NGL) residue prediction. NGL perplexity scores range from 9.54-12.47 across VH/VL regions (vs. near-random or worse for prior antibody LMs). On clonotype NGL mutation prediction, AbLang-2 achieves ~15% cumulative probability for known NGL residues in VH, compared to <2% for AntiBERTy and AbLang-1.

### SOTA Status

AbLang2 is a strong baseline for paired antibody language modeling tasks as of 2024. The germline debiasing approach is a distinguishing feature not present in most competing models.

## Implementation Verification

### Verification Method

Numerical reproduction: The BioLM implementation loads official pre-trained weights via `ablang2.pretrained.pretrained()` from the PyPI package (v0.2.1). Test fixtures compare outputs against golden reference outputs stored in R2.

### Test Cases

| Test Case | Action | Input | Verification |
|-----------|--------|-------|--------------|
| Seqcoding embedding | `encode` | 2 paired sequences | Cosine distance < 0.02 |
| Rescoding embedding | `encode` | 1 paired sequence | Cosine distance < 0.02 |
| Likelihood prediction | `predict` | 1 paired sequence | Relative tolerance 1e-4 |
| Sequence restoration | `generate` | 1 sequence with `*` masks | Exact match to golden output |
| Log probability | `log_prob` | 1 paired sequence | Validates output is negative finite float |

### Verification Status

**Status: VERIFIED** -- Integration tests pass with tolerances of rel_tol=1e-4 and cosine_distance_threshold=0.02.

## Resource Requirements

| Variant | GPU | Memory | CPU |
|---------|-----|--------|-----|
| `ablang2` | None (CPU) | 4 GB | 2 cores |

## Implementation Notes

- **Memory snapshots**: AbLang2 uses `@modal.enter(snap=True)` for CPU model loading and `@modal.enter(snap=False)` for GPU transfer.
- **Determinism**: Seeds are set (`torch.manual_seed(42)`) for reproducible outputs.
- **Weight loading**: Weights are downloaded from R2 with library-managed fallback. A symlink is created from the ablang2 library's expected weights location to the managed weights directory.
- **Dependencies**: `ablang2==0.2.1`, `einops==0.8.1`, `rotary-embedding-torch==0.8.9`
- **Caching**: Response caching is handled outside the model container.

## License

- **Code**: BSD-3-Clause ([LICENSE](https://github.com/oxpig/AbLang2/blob/main/LICENSE))
- **Weights**: BSD-3-Clause (same license)

## References & Citations

### Papers

1. Olsen TH, Moal IH, Deane CM. "AbLang: An antibody language model for completing antibody sequences." *Bioinformatics Advances* (2022). [DOI: 10.1093/bioadv/vbac046](https://doi.org/10.1093/bioadv/vbac046)

2. Olsen TH, Moal IH, Deane CM. "AbLang2: Addressing the Antibody Germline Bias and Its Effect on Language Models for Improved Antibody Design." *bioRxiv* (2024). [DOI: 10.1101/2024.02.02.578678](https://doi.org/10.1101/2024.02.02.578678)

### BibTeX

```bibtex
@article{olsen2024ablang2,
  title={AbLang2: Addressing the Antibody Germline Bias and Its Effect on Language Models for Improved Antibody Design},
  author={Olsen, Tobias H and Moal, Iain H and Deane, Charlotte M},
  journal={bioRxiv},
  year={2024},
  doi={10.1101/2024.02.02.578678}
}
```

### Links

- **Paper (AbLang)**: [DOI: 10.1093/bioadv/vbac046](https://doi.org/10.1093/bioadv/vbac046)
- **Paper (AbLang2)**: [DOI: 10.1101/2024.02.02.578678](https://doi.org/10.1101/2024.02.02.578678)
- **Code**: [github.com/oxpig/AbLang2](https://github.com/oxpig/AbLang2)
- **PyPI**: [pypi.org/project/ablang2](https://pypi.org/project/ablang2/)

---

*See also: [MODEL.md](MODEL.md) for technical deep-dive | [BIOLOGY.md](BIOLOGY.md) for biological context*
