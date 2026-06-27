# NanoBERT

> **One-line summary**: RoBERTa-based language model specialized for nanobody (VHH) sequences that produces embeddings, masked residue predictions, and log-probability scores for single-domain antibodies up to 154 residues.

## Overview

NanoBERT is a deep learning model for gene-agnostic navigation of the nanobody mutational space, developed by Giovanoudi and Vaisman. It is based on the RoBERTa architecture and trained with a masked language modeling objective on nanobody (VHH) sequences -- the single-domain variable fragments of camelid heavy-chain-only antibodies.

NanoBERT is the only nanobody-specialized language model on the BioLM platform. Its gene-agnostic design learns sequence patterns without relying on germline gene assignments, enabling it to capture functional properties that are independent of VHH germline identity. The model is lightweight (CPU-only, 2 GB memory) and suitable for high-throughput nanobody screening and design.

## Architecture

| Property | Value |
|----------|-------|
| Architecture | RoBERTa (AutoModelForMaskedLM) |
| Training objective | Masked language modeling (MLM) |
| Training data | Nanobody (VHH) sequences |
| Max sequence length | 154 residues |
| Tokenizer | RobertaTokenizer (character-level) |
| Vocabulary | 20 standard amino acids only |
| License | MIT |

## Model Variants

NanoBERT is a single-variant model with no size options.

| Variant | GPU | Memory | CPU | Use Case |
|---------|-----|--------|-----|----------|
| `nanobert` | None (CPU) | 2 GB | 2 cores | All nanobody embedding and scoring tasks |

## Capabilities & Limitations

**CAN be used for:**
- Generating mean-pooled, per-residue, or logit embeddings for nanobody sequences
- Masked residue prediction (sequence completion with `*` placeholders)
- Zero-shot nanobody sequence scoring via log-probability (`predict_log_prob`)
- Navigating the nanobody mutational landscape for design and engineering

**CANNOT be used for:**
- Conventional paired antibodies (use AbLang2 or IgBERT)
- Non-nanobody proteins (use ESM-2)
- Sequences longer than 154 residues
- Non-standard amino acids (B, J, O, U, X, Z are not accepted)
- 3D structure prediction
- Antibody numbering and annotation (use SADIE)

**Other considerations:**
- Runs on CPU only -- no GPU required, very cost-effective
- Batch size capped at 32 sequences per request
- Only accepts the 20 unambiguous amino acids

## Actions / Endpoints

### `encode`

Generates embeddings for nanobody sequences. Supports mean-pooled embeddings, per-residue embeddings, and raw logits.

**Request Parameters:**

| Parameter | Type | Default | Range | Description |
|-----------|------|---------|-------|-------------|
| `items[].sequence` | str | *(required)* | 1--154 chars | Nanobody amino acid sequence (20 standard AAs only) |
| `params.include` | list[str] | `["mean"]` | `mean`, `residue`, `logits` | Output types to include |

**Response:**

```json
{
  "results": [
    {
      "embeddings": [0.012, -0.034, ...],
      "residue_embeddings": null,
      "logits": null
    }
  ]
}
```

Fields are `null` (omitted from JSON) unless their corresponding `include` option is set.

**Schema classes**: `NanoBERTEncodeRequest` -> `NanoBERTEncodeResponse`

### `generate`

Restores missing residues marked with `*` by predicting the most likely canonical amino acid at each masked position.

**Request Parameters:**

| Parameter | Type | Default | Range | Description |
|-----------|------|---------|-------|-------------|
| `items[].sequence` | str | *(required)* | 1--154 chars | Nanobody sequence with `*` at unknown positions |

At least one `*` must be present in each sequence.

**Response:**

```json
{
  "results": [
    {
      "sequence": "QVQLVQSGAEVKKPGASVKVSC..."
    }
  ]
}
```

**Schema classes**: `NanoBERTGenerateRequest` -> `NanoBERTGenerateResponse`

### `predict_log_prob`

Computes the total log-probability of nanobody sequences under the NanoBERT model by summing log P(residue_i | context) at each non-special-token position.

**Request Parameters:**

| Parameter | Type | Default | Range | Description |
|-----------|------|---------|-------|-------------|
| `items[].sequence` | str | *(required)* | 1--154 chars | Nanobody amino acid sequence |

**Response:**

```json
{
  "results": [
    {
      "log_prob": -142.85
    }
  ]
}
```

More negative values indicate less likely sequences. Compare wild-type vs mutant log-probabilities to score variant effects.

**Schema classes**: `NanoBERTLogProbRequest` -> `NanoBERTLogProbResponse`

## Usage Examples

```python
# Encode -- get mean embeddings for nanobody sequences
from models.nanobert.schema import (
    NanoBERTEncodeRequest,
    NanoBERTEncodeRequestItem,
    NanoBERTEncodeRequestParams,
)

encode_request = NanoBERTEncodeRequest(
    params=NanoBERTEncodeRequestParams(include=["mean"]),
    items=[
        NanoBERTEncodeRequestItem(
            sequence="QVQLVQSGAEVKKPGASVKVSCKVSGYTSPTTIHWVRQAPGKGLEWMGGISPYRGDTIYAQKFQGRVTMTEDTSTDTAYMELSSLKSEDTAVYYCARDGYSSGYYGMDVWGQGTTVTVSS",
        ),
    ],
)

# Generate -- restore missing residues
from models.nanobert.schema import NanoBERTGenerateRequest, NanoBERTGenerateRequestItem

generate_request = NanoBERTGenerateRequest(
    items=[
        NanoBERTGenerateRequestItem(
            sequence="QVQLVQSG*EVKKPGASVKVSCKVSGYTSPTTI*WVRQAPGKGLEWMG*ISPYRGDTIYAQKFQG",
        ),
    ],
)

# Predict log probability -- sequence scoring
from models.nanobert.schema import NanoBERTLogProbRequest, NanoBERTEncodeRequestItem

log_prob_request = NanoBERTLogProbRequest(
    items=[
        NanoBERTEncodeRequestItem(
            sequence="QVQLVQSGAEVKKPGASVKVSCKVSGYTSPTTIHWVRQAPGKGLEWMGGISPYRGDTIYAQKFQGRVTMTEDTSTDTAYMELSSLKSEDTAVYYCARDGYSSGYYGMDVWGQGTTVTVSS",
        ),
    ],
)
```

## Performance & Benchmarks

### Published Results

NanoBERT was evaluated on nanobody mutational landscape navigation and property prediction tasks.

<!-- TODO: Extract benchmark numbers from Giovanoudi & Vaisman 2024 -- see sources.yaml primary_papers[0] (DOI: 10.1093/bioinformatics/btae123) -->

### SOTA Status

NanoBERT is the primary nanobody-specialized language model. It demonstrates improved nanobody representation quality compared to general protein language models for VHH-specific tasks.

## Implementation Verification

### Verification Method

Numerical reproduction: The BioLM implementation loads official pre-trained weights via `AutoModelForMaskedLM.from_pretrained()` and `RobertaTokenizer.from_pretrained()`. Test fixtures compare outputs against golden reference outputs stored in R2.

### Test Cases

| Test Case | Action | Input | Verification |
|-----------|--------|-------|--------------|
| Mean embedding | `encode` | Nanobody sequences | Cosine distance < 0.02 |
| Sequence restoration | `generate` | Sequence with `*` masks | Exact match to golden output |
| Log probability | `predict_log_prob` | Nanobody sequences | Validates negative finite float |

### Verification Status

**Status: VERIFIED** -- Integration tests pass with tolerances of rel_tol=1e-4 and cosine_distance_threshold=0.02.

## Resource Requirements

| Variant | GPU | Memory | CPU |
|---------|-----|--------|-----|
| `nanobert` | None (CPU) | 2 GB | 2 cores |

## Implementation Notes

- **Memory snapshots**: NanoBERT uses `@modal.enter(snap=True)` with GPU memory snapshot settings for consistency, though the model runs on CPU.
- **Determinism**: Seeds are set (`torch.manual_seed(42)`, `torch.cuda.manual_seed_all(42)`) for reproducible outputs.
- **Weight loading**: Weights are downloaded from R2 and loaded via HuggingFace `AutoModelForMaskedLM.from_pretrained()`.
- **Dependencies**: `transformers==4.48.1`, `safetensors==0.5.3`, `sentencepiece==0.2.0`
- **Amino acid restriction**: Only the 20 unambiguous canonical amino acids are accepted; the extended alphabet (B, J, O, U, X, Z) is not supported.
- **Caching**: Inherits standard Redis/R2 two-tier caching from `BillingMixinSnap`.

## License

- **Code**: MIT ([LICENSE](https://github.com/NaturalAntibody/NanoBERT/blob/main/LICENSE))
- **Weights**: MIT (same license)

## References & Citations

### Papers

1. Giovanoudi A, Vaisman A. "NanoBERT: A deep learning model for gene agnostic navigation of the nanobody mutational space." *Bioinformatics* (2024). [DOI: 10.1093/bioinformatics/btae123](https://doi.org/10.1093/bioinformatics/btae123)

### BibTeX

```bibtex
@article{giovanoudi2024nanobert,
  title={NanoBERT: A deep learning model for gene agnostic navigation of the nanobody mutational space},
  author={Giovanoudi, Anastasia and Vaisman, Adi},
  journal={Bioinformatics},
  year={2024},
  doi={10.1093/bioinformatics/btae123}
}
```

### Links

- **Paper**: [DOI: 10.1093/bioinformatics/btae123](https://doi.org/10.1093/bioinformatics/btae123)
- **Code**: [github.com/NaturalAntibody/NanoBERT](https://github.com/NaturalAntibody/NanoBERT)

---

*See also: [MODEL.md](MODEL.md) for technical deep-dive | [BIOLOGY.md](BIOLOGY.md) for biological context*
