# DSM

> **One-line summary**: Masked diffusion protein language model for sequence generation (unconditional, masked infilling, conditional), embedding extraction, and log-probability scoring, with a PPI variant for interaction pair design.

## Overview

DSM is a novel Protein Language Model (pLM) developed by [Gleghorn Lab](https://www.gleghornlab.com/) and [Synthyra](https://synthyra.com/). It was trained with masked diffusion to enable both high-quality representation learning and generative protein design.

### Capabilities

- **Generate** (`generate`): Generate protein sequences via masked diffusion - supports unconditional generation (empty input), masked sequence filling (`<mask>` tokens), and conditional generation from a prefix
- **Encode** (`encode`): Extract embeddings (mean-pooled, per-residue, or CLS token) for similarity search, clustering, or downstream ML tasks
- **Score** (`score`): Calculate log probabilities and perplexity for sequence quality assessment, filtering, and confidence scoring

## Architecture

| Property | Value |
|----------|-------|
| Architecture | Transformer + masked diffusion |
| Training objective | Masked diffusion (iterative denoising) |
| Training data | omg_prot50 (base), STRING (PPI) |
| Max sequence length | 2048 tokens |

## Model Variants

| App Name | Parameters | Use Case |
|----------|-----------|----------|
| `dsm-150m-base` | 150M | Fast unconditional generation, testing |
| `dsm-650m-base` | 650M | General protein design (best balance) |
| `dsm-650m-ppi` | 650M | Binder/interface design (STRING-trained) |

- **Base** variants: Trained on omg_prot50 dataset for general protein generation
- **PPI** variant: Trained on STRING database for protein-protein interaction design

Variant axes: `MODEL_SIZE` (150m, 650m) x `VARIANT` (base, ppi). Excluded combinations: 150m-ppi, 3b-ppi, 3b-base (3B not yet released).

## Capabilities & Limitations

**CAN be used for:**
- Unconditional protein sequence generation
- Masked sequence infilling (fixing regions, generating others)
- Conditional sequence generation from prefix
- Protein-protein interaction pair design (PPI variant)
- Embedding extraction (mean-pooled, per-residue, CLS)
- Sequence quality scoring (log probability, perplexity)

**CANNOT be used for:**
- Structure-conditioned generation (sequence-only)
- Non-protein molecules
- Multi-chain complex design (except PPI dual sequences)

## Actions / Endpoints

### `generate`

**Request Parameters:**

| Parameter | Type | Default | Range | Description |
|-----------|------|---------|-------|-------------|
| `items[].sequence` | str | "" | 0-2048 | Input sequence: empty=unconditional (canvas of `max_length` masks), `<mask>` tokens=infilling, plain AA=conditional |
| `params.num_sequences` | int | 1 | 1-32 | Number of sequences to generate |
| `params.temperature` | float | 1.0 | 0.1-2.0 | Sampling temperature |
| `params.max_length` | int | None | 10-2048 | Canvas size (mask tokens) for unconditional generation; default 100; ignored for infilling/conditional modes |
| `params.step_divisor` | int | 100 | 1-1000 | Diffusion steps (lower=slower but better) |
| `params.remasking` | str | "random" | "low_confidence", "random", "low_logit", "dual" | Remasking strategy |
| `params.seed` | int | None | -- | Random seed (None=time-based) |

### `encode`

**Request Parameters:**

| Parameter | Type | Default | Range | Description |
|-----------|------|---------|-------|-------------|
| `items[].sequence` | str | *(required)* | 1-2048 AA | Protein sequence |
| `params.include` | list[str] | `["mean"]` | -- | Output types: `mean`, `per_residue`, `cls` |

### `score`

**Request Parameters:**

| Parameter | Type | Default | Range | Description |
|-----------|------|---------|-------|-------------|
| `items[].sequence` | str | *(required)* | 1-2048 AA | Protein sequence (canonical 20 AA) |

## Usage Examples

### Generate Sequences (Unconditional)

Pass an empty string and set `max_length` to control the number of residues generated.
The model creates a canvas of that many `<mask>` tokens and denoises them.

```python
from models.dsm.schema import (
    DSMGenerateRequest,
    DSMGenerateRequestItem,
    DSMGenerateRequestParams,
    DSMRemaskingStrategy,
)

request = DSMGenerateRequest(
    params=DSMGenerateRequestParams(
        num_sequences=5,
        temperature=1.0,
        max_length=100,  # Generate sequences of ~100 residues
        remasking=DSMRemaskingStrategy.RANDOM,
        seed=42,
    ),
    items=[
        DSMGenerateRequestItem(sequence=""),  # Empty triggers unconditional generation
    ],
)
```

### Generate Sequences (Masked Infilling)

```python
from models.dsm.schema import (
    DSMGenerateRequest,
    DSMGenerateRequestItem,
    DSMGenerateRequestParams,
)

request = DSMGenerateRequest(
    params=DSMGenerateRequestParams(num_sequences=3),
    items=[
        DSMGenerateRequestItem(
            sequence="MKTL<mask><mask><mask>VLGK",  # Fill in masked positions
        ),
    ],
)
```

### Encode Sequences

```python
from models.dsm.schema import (
    DSMEncodeRequest,
    DSMEncodeRequestItem,
    DSMEncodeRequestParams,
    DSMEncodeIncludeOptions,
)

request = DSMEncodeRequest(
    params=DSMEncodeRequestParams(
        include=[DSMEncodeIncludeOptions.MEAN, DSMEncodeIncludeOptions.CLS],
    ),
    items=[
        DSMEncodeRequestItem(sequence="MKTLLLTLVVVTLVL"),
    ],
)
```

### Score Sequences

```python
from models.dsm.schema import (
    DSMScoreRequest,
    DSMScoreRequestItem,
)

request = DSMScoreRequest(
    items=[
        DSMScoreRequestItem(sequence="MKTLLLTLVVVTLVL"),
    ],
)
```

## Performance & Benchmarks

### Model Sizes

| Model | Parameters | GPU | Memory | Inference Time |
|-------|-----------|-----|--------|----------------|
| DSM_150 | 150M | A10G | 16GB | ~500ms/seq |
| DSM_650 | 650M | A10G | 32GB | ~1-2s/seq |
| DSM_3B | 3B | A100 | 64GB | ~5-10s/seq (not yet released) |

### Endpoint Performance

- **Generate**: 1-5s per batch (depends on num_sequences)
- **Encode**: 100-200ms per sequence
- **Score**: 150-250ms per sequence

## Implementation Verification

Deploying the app and running tests:

```bash
# Deploy
python models/dsm/app.py --force-deploy

# Generate fixtures
python models/dsm/fixture.py

# Run tests
python -m pytest models/dsm/test.py -m integration -n auto --no-cov -v -s
```

## Resource Requirements

| Variant | GPU | Memory | CPU |
|---------|-----|--------|-----|
| `dsm-150m-base` | A10G | 16 GB | 4 cores |
| `dsm-650m-base` | A10G | 32 GB | 8 cores |
| `dsm-650m-ppi` | A10G | 32 GB | 8 cores |

## Implementation Notes

- **Memory snapshots**: Uses GPU memory snapshots for fast cold starts
- **DSM repository**: Cloned at pinned commit (`ca7b5c8c`) with submodules
- **ESM backbone**: Dynamic import from `/root/DSM/models/modeling_dsm.py`
- **PPI variant**: Uses `decode_dual_input` with `<eos>` separator for dual sequences
- **Caching**: Response caching is handled externally (e.g., by a caching proxy), not inside the model container.

## License

- **Code & Weights**: Apache-2.0 ([LICENSE](https://github.com/GleghornLab/DSM/blob/main/LICENSE))

## References & Citations

### BibTeX

```bibtex
@article{hallee2025dsm,
  title={Diffusion Sequence Models for Enhanced Protein Representation and Generation},
  author={Hallee, Logan and Rafailidis, Nikolaos and Bichara, David B. and Gleghorn, Jason P.},
  journal={arXiv preprint},
  eprint={2506.08293},
  year={2025}
}
```

### Links

- **Code**: [github.com/GleghornLab/DSM](https://github.com/GleghornLab/DSM)
- **Weights (150M)**: [huggingface.co/GleghornLab/DSM_150](https://huggingface.co/GleghornLab/DSM_150)
- **Weights (650M)**: [huggingface.co/GleghornLab/DSM_650](https://huggingface.co/GleghornLab/DSM_650)
- **Weights (PPI)**: [huggingface.co/Synthyra/DSM_ppi_full](https://huggingface.co/Synthyra/DSM_ppi_full)
- [Gleghorn Lab](https://www.gleghornlab.com/)
- [Synthyra](https://synthyra.com/)

---

*See also: [MODEL.md](MODEL.md) for technical deep-dive | [BIOLOGY.md](BIOLOGY.md) for biological context*
