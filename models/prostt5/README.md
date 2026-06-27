# ProstT5

> **One-line summary**: Bilingual T5-based protein language model that translates between amino acid sequences and Foldseek 3Di structural alphabet tokens, enabling structure-aware embeddings and inverse folding.

## Overview

ProstT5 is a bilingual protein language model developed by Heinzinger et al. (2023) at the Rostlab (TU Munich). Built on the ProtT5-XL-U50 architecture, it is fine-tuned to translate between amino acid sequences and 3Di structural tokens (the 20-letter alphabet from Foldseek that encodes local 3D geometry). ProstT5 supports two actions -- `encode` (embedding extraction) and `generate` (sequence translation) -- in both directions (AA2fold and fold2AA).

## Architecture

| Property | Value |
|----------|-------|
| Architecture | T5 encoder-decoder Transformer (ProtT5-XL-U50 backbone) |
| Parameters | ~3B |
| Embedding dimension | 1024 |
| AA vocabulary | Standard 20 amino acids (uppercase) + X |
| 3Di vocabulary | 20-letter structural alphabet (lowercase: acdefghiklmnpqrstvwy) |
| Direction tokens | `<AA2fold>`, `<fold2AA>` |
| HuggingFace model | Rostlab/ProstT5 |

## Model Variants

ProstT5 has two axes: action (encode/generate) and direction (AA2fold/fold2AA), producing four deployments:

| Variant Slug | Action | Direction | GPU | Memory |
|-------------|--------|-----------|-----|--------|
| `prostt5-aa2fold-encode` | encode | AA2fold | L4 | 16 GB |
| `prostt5-fold2aa-encode` | encode | fold2AA | L4 | 16 GB |
| `prostt5-aa2fold-generate` | generate | AA2fold | L4 | 16 GB |
| `prostt5-fold2aa-generate` | generate | fold2AA | L4 | 16 GB |

## Capabilities & Limitations

**CAN be used for:**
- Extracting structure-aware protein embeddings (1024-dim) from amino acid sequences (AA2fold encode)
- Extracting embeddings from 3Di structural token sequences (fold2AA encode)
- Translating amino acid sequences to 3Di structural tokens (AA2fold generate)
- Translating 3Di structural tokens to amino acid sequences -- inverse folding (fold2AA generate)
- Protein fold classification and remote homology detection via embeddings
- Structural annotation of large protein databases without full 3D prediction

**CANNOT be used for:**
- Full 3D atomic structure prediction (use AlphaFold2, ESMFold, or RF3)
- Nucleic acid or small molecule analysis
- Multi-chain complex modeling
- Per-residue confidence scores (use structure prediction models for pLDDT)

## Actions / Endpoints

### `encode`

Extract a 1024-dimensional mean-pooled embedding from a protein sequence or 3Di structural sequence.

**Request Parameters (AA2fold direction):**

| Parameter | Type | Default | Range | Description |
|-----------|------|---------|-------|-------------|
| `items[].sequence` | str | (required) | 1--1000 AA | Amino acid sequence (uppercase) |

**Request Schema:** `ProstT5EncodeRequestAA` (AA2fold) or `ProstT5EncodeRequestFold` (fold2AA)

**Request Parameters (fold2AA direction):**

| Parameter | Type | Default | Range | Description |
|-----------|------|---------|-------|-------------|
| `items[].sequence` | str | (required) | 1--1000 3Di | 3Di structural token sequence (lowercase) |

**Response:**

```json
{
  "results": [
    {
      "mean_representation": [0.123, -0.456, ...]
    }
  ]
}
```

**Response Schema:** `ProstT5EncodeResponse`

Max batch size: 16 sequences.

### `generate`

Translate between amino acid sequences and 3Di structural tokens.

**Request Parameters (AA2fold direction):**

| Parameter | Type | Default | Range | Description |
|-----------|------|---------|-------|-------------|
| `items[].sequence` | str | (required) | 1--512 AA | Amino acid sequence (uppercase) |
| `params.temperature` | float | 1.2 | 0.0--8.0 | Sampling temperature |
| `params.top_p` | float | 0.95 | 0.0--1.0 | Nucleus sampling threshold |
| `params.top_k` | int | 6 | 1--20 | Top-k sampling |
| `params.repetition_penalty` | float | 1.2 | 0.0--3.0 | Repetition penalty |
| `params.num_samples` | int | 1 | 1--3 | Number of output sequences per input |
| `params.num_beams` | int | 3 | 1--3 | Beam search width |
| `params.seed` | int | None | -- | Random seed (None = time-based) |

**Request Schema:** `ProstT5GenerateRequestAA`

**Request Parameters (fold2AA direction):**

| Parameter | Type | Default | Range | Description |
|-----------|------|---------|-------|-------------|
| `items[].sequence` | str | (required) | 1--512 3Di | 3Di structural token sequence (lowercase) |
| `params.temperature` | float | 1.0 | 0.0--8.0 | Sampling temperature |
| `params.top_p` | float | 0.85 | 0.0--1.0 | Nucleus sampling threshold |
| `params.top_k` | int | 3 | 1--20 | Top-k sampling |
| `params.repetition_penalty` | float | 1.2 | 0.0--3.0 | Repetition penalty |
| `params.num_samples` | int | 1 | 1--3 | Number of output sequences per input |
| `params.seed` | int | None | -- | Random seed (None = time-based) |

**Request Schema:** `ProstT5GenerateRequestFold`

**Response:**

```json
{
  "results": [
    [
      {"sequence": "dddahklqppddvvdddd..."},
      {"sequence": "ddeahklqppddvvdddd..."}
    ]
  ]
}
```

**Response Schema:** `ProstT5GenerateResponse`

Max batch size: 2 sequences. Output sequences match input length.

**Direction conventions:**
- AA2fold: Input is uppercase amino acids, output is lowercase 3Di tokens
- fold2AA: Input is lowercase 3Di tokens, output is uppercase amino acids

## Usage Examples

### Encode amino acid sequences (AA2fold)

```python
from models.prostt5.schema import (
    ProstT5EncodeRequestAA,
    ProstT5EncodeRequestItemAA,
)

request = ProstT5EncodeRequestAA(
    items=[
        ProstT5EncodeRequestItemAA(sequence="MKLLILAVVFTVFGTAVQAAYPYDDAAQLTEEQR"),
    ]
)
```

### Encode 3Di structural tokens (fold2AA)

```python
from models.prostt5.schema import (
    ProstT5EncodeRequestFold,
    ProstT5EncodeRequestItemFold,
)

request = ProstT5EncodeRequestFold(
    items=[
        ProstT5EncodeRequestItemFold(sequence="dddahklqppddvvddddahhppllddddefgh"),
    ]
)
```

### Generate 3Di from amino acids (AA2fold)

```python
from models.prostt5.schema import (
    ProstT5GenerateRequestAA,
    ProstT5GenerateRequestItemAA,
    ProstT5GenerateParamsAA,
)

request = ProstT5GenerateRequestAA(
    params=ProstT5GenerateParamsAA(
        temperature=1.2,
        top_p=0.95,
        num_samples=2,
        seed=42,
    ),
    items=[
        ProstT5GenerateRequestItemAA(sequence="MKLLILAVVFTVFGTAVQAAYPYDDAAQLTEEQR"),
    ],
)
```

### Inverse folding: generate amino acids from 3Di (fold2AA)

```python
from models.prostt5.schema import (
    ProstT5GenerateRequestFold,
    ProstT5GenerateRequestItemFold,
    ProstT5GenerateParamsFold,
)

request = ProstT5GenerateRequestFold(
    params=ProstT5GenerateParamsFold(
        temperature=1.0,
        num_samples=3,
        seed=42,
    ),
    items=[
        ProstT5GenerateRequestItemFold(sequence="dddahklqppddvvddddahhppllddddefgh"),
    ],
)
```

## Performance & Benchmarks

### Published Results

From Heinzinger et al., *bioRxiv* (2023):

| Task | ProstT5 | ProtT5 (AA-only) | Notes |
|------|---------|-------------------|-------|
| Fold classification (SCOP) | 88.8% | 85.1% | Structure-aware embeddings improve fold detection |
| 3SS prediction (Q3) | ~82% | ~81% | Comparable on secondary structure |
| Remote homology | Improved | Baseline | Better at detecting distant evolutionary relationships |

### SOTA Status

ProstT5 is the first bilingual model bridging amino acid and 3Di structural alphabets. It represents a novel approach to structure-aware protein representation learning, complementary to coordinate-based methods.

## Implementation Verification

### Verification Method

Encode outputs compared against golden embeddings with cosine distance threshold. Generate outputs validated for correct length and alphabet.

### Test Cases

| Variant | Action | Tolerance | Status |
|---------|--------|-----------|--------|
| AA2fold | encode | rel_tol 1e-3, cosine_distance < 0.02 | PASS |
| fold2AA | encode | rel_tol 1e-3, cosine_distance < 0.02 | PASS |
| AA2fold | generate | Length match, case validation | PASS |
| fold2AA | generate | Length match, case validation | PASS |

### Verification Status

**Status: VERIFIED** -- All 4 variant/action test cases pass.

## Resource Requirements

| Resource | Value |
|----------|-------|
| GPU | L4 (all variants) |
| Memory | 16 GB RAM |
| CPU | 4.0 cores |
| Encode batch size | 16 |
| Generate batch size | 2 |
| Max encode sequence length | 1000 |
| Max generate sequence length | 512 |
| Memory snapshot | Enabled with GPU snapshot |

## Implementation Notes

- **Memory snapshots**: Uses `@modal.enter(snap=True)` with `BillingMixinSnap` and GPU snapshot.
- **Container image**: Based on `pytorch/pytorch:2.0.1-cuda11.7-cudnn8-runtime`.
- **Model loading**: `T5EncoderModel` for encode action; `AutoModelForSeq2SeqLM` for generate action.
- **Half precision**: Skipped with memory snapshots for CPU compatibility.
- **Bad words filtering**: Prevents generating tokens from the wrong vocabulary (no 3Di tokens when outputting AA, and vice versa).
- **Length handling**: Output sequences may differ from input length for sequences >512; truncated or padded with 'd' to match.
- **Dependencies**: `transformers==4.36.2`, `sentencepiece==0.2.0`, `protobuf==5.26.1`, `safetensors==0.5.3`.
- **Model weights**: Downloaded from R2 storage (HuggingFace Rostlab/ProstT5 weights).

## License

- **Code**: MIT ([LICENSE](https://github.com/mheinzinger/ProstT5/blob/main/LICENSE))

## References & Citations

### Papers

1. Heinzinger M, Weissenow K, Gomez Sanchez J, Hartmann A, Steinegger M, Rost B. "ProstT5: Bilingual Language Model for Protein Sequence and Structure." *bioRxiv* (2023). [arXiv:2310.07083](https://arxiv.org/abs/2310.07083)

### BibTeX

```bibtex
@article{heinzinger2023prostt5,
  title={ProstT5: Bilingual Language Model for Protein Sequence and Structure},
  author={Heinzinger, Michael and Weissenow, Konstantin and Gomez Sanchez, Joaquin and Hartmann, Adrian and Steinegger, Maria and Rost, Burkhard},
  journal={bioRxiv},
  year={2023},
  eprint={2310.07083},
  archivePrefix={arXiv}
}
```

### Links

- **Paper**: [arXiv:2310.07083](https://arxiv.org/abs/2310.07083)
- **Code**: [GitHub mheinzinger/ProstT5](https://github.com/mheinzinger/ProstT5)
- **Model**: [HuggingFace Rostlab/ProstT5](https://huggingface.co/Rostlab/ProstT5)

---

*See also: [MODEL.md](MODEL.md) for technical deep-dive | [BIOLOGY.md](BIOLOGY.md) for biological context*
