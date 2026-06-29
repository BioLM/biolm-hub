# Evo

> **One-line summary**: A 7B-parameter autoregressive DNA language model built on the StripedHyena architecture, capable of genome-scale sequence generation and log-probability scoring at single-nucleotide resolution.

## Overview

**Evo** is a DNA foundation model developed by the Arc Institute, Stanford, and Together AI. At 7 billion parameters, it is one of the largest language models trained specifically on DNA sequences. Evo uses the **StripedHyena** architecture  --  a hybrid of gated convolutions (Hyena operators) and multi-head attention  --  which achieves near-linear scaling with sequence length. This enables Evo to handle context lengths up to 131,072 nucleotides, far beyond what standard Transformers can process efficiently.

Evo is trained on the **OpenGenome** dataset, a large corpus of prokaryotic and phage genome sequences, using a standard autoregressive (next-token prediction) objective. This dual-purpose training yields both **generative** capability (producing novel DNA sequences) and **scoring** capability (evaluating how natural a given DNA sequence is under the model's learned distribution).

The model was published in *Science* (2024) and represents one of the first demonstrations of genome-scale DNA generation where the produced sequences encode proteins with plausible predicted structures.

## Architecture

| Property | Value |
|----------|-------|
| Architecture | StripedHyena (hybrid gated convolution + attention) |
| Parameters | ~7 billion |
| Tokenization | Byte-level (single nucleotide per token) |
| Vocabulary | A, C, G, T + special tokens |
| Training data | OpenGenome (~300B tokens, prokaryotic + phage genomes) |
| Training objective | Autoregressive next-token prediction |
| Max sequence length | 4,096 nt (BioLM API); 8,192 nt (model native, 8k variant) |

For detailed architecture information, see [MODEL.md](MODEL.md).

## Model Variants

| Variant | Slug | Context | GPU | Status |
|---------|------|---------|-----|--------|
| **Evo 1.5 8k Base** | `v1.5-8k` | 8,192 nt | L4 | Enabled |
| Evo 1 8k Base | `v1-8k` | 8,192 nt | L4 | Planned |
| Evo 1 131k Base | `v1-131k` | 131,072 nt | L4 | Planned |
| Evo 1 8k CRISPR | `v1-8k-crispr` | 8,192 nt | L4 | Planned |
| Evo 1 8k Transposon | `v1-8k-transposon` | 8,192 nt | L4 | Planned |

Currently, only the **Evo 1.5 8k Base** variant is enabled. Evo 1.5 was trained on approximately 50% more data than the original Evo 1 release.

## Capabilities & Limitations

**CAN be used for:**
- Generating novel DNA sequences from a seed prompt (autoregressive sampling with temperature, top-k, top-p control)
- Scoring DNA sequences via total log-probability under the autoregressive distribution
- Zero-shot variant effect assessment by comparing log-probabilities of wild-type vs. mutant sequences
- Evaluating how "natural-like" a synthetic DNA construct is
- Prokaryotic genome analysis, including coding regions, regulatory elements, and intergenic sequences

**CANNOT be used for:**
- Sequences containing ambiguous bases (N, R, Y, W, S, etc.)  --  only A, C, G, T accepted
- Sequences longer than 4,096 nucleotides (BioLM API limit)
- RNA sequences (U is not accepted; use RNA-specific models)
- Protein sequences (Evo operates on DNA only; use ESM2 or similar)
- Per-token embedding extraction (no `encode` endpoint is exposed)
- Eukaryotic-specific tasks (complex splicing, distal enhancer-promoter interactions)  --  training data is primarily prokaryotic

**Other considerations:**
- The `generate` action is stochastic by default. Provide an explicit `seed` parameter for reproducible outputs.
- Log-probability scores are summed over all positions, so longer sequences naturally have more negative total scores. Normalize by length for fair cross-length comparisons.
- Batch size is limited to 2 items per request.

## Actions / Endpoints

### `log_prob`

Computes the total log-probability of each DNA sequence under Evo's autoregressive distribution. Uses `evo.scoring.score_sequences()` with sum reduction over positions.

**Request Schema**: `EvoPredictLogProbRequest`

| Parameter | Type | Default | Range | Description |
|-----------|------|---------|-------|-------------|
| `items[].sequence` | str | (required) | 1-4096 nt | DNA sequence (A/C/G/T only) |

**Batch limit**: 1-2 items per request.

**Response Schema**: `EvoPredictLogProbResponse`

```json
{
  "results": [
    {
      "log_prob": -15.234
    }
  ]
}
```

The `log_prob` value is the sum of log-probabilities across all positions in the sequence. More negative values indicate less likely sequences.

### `generate`

Generates new DNA sequences from a prompt using autoregressive sampling. Returns the generated sequence and an average log-probability score.

**Request Schema**: `EvoGenerateRequest`

| Parameter | Type | Default | Range | Description |
|-----------|------|---------|-------|-------------|
| `items[].prompt` | str | (required) | 1-4096 nt | DNA seed sequence (A/C/G/T only) |
| `params.max_new_tokens` | int | 100 | 1-4096 | Number of tokens to generate |
| `params.temperature` | float | 0.0 | >= 0.0 | Sampling temperature (0.0 = greedy) |
| `params.top_k` | int | 1 | >= 1 | Top-k sampling parameter |
| `params.top_p` | float | 1.0 | 0.0-1.0 | Nucleus sampling parameter |
| `params.prepend_bos` | bool | false | - | Whether to prepend BOS token |
| `params.seed` | int or null | null | - | Random seed for reproducibility |

**Batch limit**: 1-2 items per request.

**Response Schema**: `EvoGenerateResponse`

```json
{
  "results": [
    {
      "generated": "ACGTACGTACGT...",
      "score": -0.523
    }
  ]
}
```

The `generated` field contains only the newly generated continuation (the prompt is NOT included). The `score` is an average log-probability reflecting the model's confidence in the generated sequence.

## Usage Examples

### Score DNA sequences

```python
from models.evo.schema import (
    EvoPredictLogProbRequest,
    EvoPredictLogProbRequestItem,
)

request = EvoPredictLogProbRequest(
    items=[
        EvoPredictLogProbRequestItem(sequence="ACGTACGTACGTACGT"),
        EvoPredictLogProbRequestItem(sequence="ATGATGATGATGATG"),
    ]
)
```

### Generate DNA sequences

```python
from models.evo.schema import (
    EvoGenerateRequest,
    EvoGenerateRequestItem,
    EvoGenerateRequestParams,
)

# Greedy generation (deterministic)
request = EvoGenerateRequest(
    params=EvoGenerateRequestParams(
        max_new_tokens=200,
        temperature=0.0,
        top_k=1,
    ),
    items=[
        EvoGenerateRequestItem(prompt="ATGAAAGCAATTTTCGTACTG"),
    ],
)

# Diverse generation with seed for reproducibility
request = EvoGenerateRequest(
    params=EvoGenerateRequestParams(
        max_new_tokens=500,
        temperature=0.7,
        top_k=50,
        top_p=0.95,
        seed=42,
    ),
    items=[
        EvoGenerateRequestItem(prompt="ATGAAAGCAATTTTCGTACTG"),
    ],
)
```

## Performance & Benchmarks

### Published Results

From Nguyen et al., *Science* (2024):

- **Zero-shot fitness prediction**: Evo log-probabilities correlate with experimental variant fitness across multiple prokaryotic gene datasets.
- **Gene essentiality**: Log-probability scores distinguish essential from non-essential genes in bacterial genomes.
- **Genome-scale generation**: Generated sequences encode proteins with plausible predicted structures (assessed via ESMFold), demonstrating that Evo learns higher-order genomic organization beyond nucleotide statistics.

#### Zero-Shot Fitness Prediction (ProteinGym & Prokaryotic DMS)

| Model | Task | Metric | Approximate Performance | Source |
|-------|------|--------|------------------------|--------|
| **Evo (7B)** | Zero-shot variant fitness | Spearman rho | Competitive with protein LMs on prokaryotic genes | Fig. 2, Nguyen et al. 2024 |
| **Evo (7B)** | Gene essentiality prediction | AUROC | Distinguishes essential vs. non-essential genes | Fig. 3, Nguyen et al. 2024 |
| **Evo (7B)** | Genome generation quality | ESMFold pTM | Generated proteins show plausible folds | Fig. 4, Nguyen et al. 2024 |

*Note: The above values are approximate summaries. Evo was the first DNA model evaluated at genome scale; direct numeric comparisons to protein-only models are not straightforward due to differing input modalities.*

### SOTA Status

Evo was the first model to demonstrate genome-scale DNA generation with structurally plausible encoded proteins, as published in *Science* (2024). It remains among the leading DNA foundation models for long-context genomic modeling.

## Implementation Verification

### Verification Method

Numerical reproduction (Option A): Integration tests compare model outputs against golden fixtures generated from the reference `evo-model` library running on the same Modal infrastructure.

### Test Cases

| Action | Input | Tolerance | Status |
|--------|-------|-----------|--------|
| `log_prob` | "ACGTAC", "ACGTACGTAC" | rel_tol=1e-4 | PASS |
| `generate` | Prompt "ACGT", 100 tokens | Generated sequence is valid DNA | PASS |

### Verification Status

**Status: VERIFIED**  --  Integration tests pass with golden fixture comparison. Log-probability outputs match within rel_tol=1e-4. Generated sequences are valid DNA strings.

## Resource Requirements

| Resource | Value |
|----------|-------|
| GPU | L4 |
| Memory | 8 GB |
| CPU | 4 cores |
| Cold start | Reduced via Modal GPU memory snapshot |
| Batch size | 2 items max per request |
| Dependencies | `evo-model==0.4`, `stripedhyena==0.2.2`, `flash-attn==2.5.5`, `torch==2.2.0` |

## Implementation Notes

- **Memory snapshots**: Uses `@modal.enter(snap=True)` with GPU snapshot enabled (`enable_memory_snapshot=True`, `enable_gpu_snapshot=True`). The model loads directly on GPU during snapshot creation.
- **Caching**: Response caching is handled outside the model container by the serving infrastructure.
- **No `@modal.enter(snap=False)`**: Unlike some models that move weights from CPU to GPU in a second enter phase, Evo loads directly on GPU during snapshot creation.
- **Container image**: Built from `pytorch/pytorch:2.2.0-cuda11.8-cudnn8-devel` with flash-attn compiled using `--no-build-isolation` (requires pre-installed torch).
- **Determinism**: `log_prob` is fully deterministic. `generate` is deterministic when a seed is provided; stochastic otherwise (time-based seed).
- **Download layer**: Model weights are downloaded via the unified `setup_download_layer` system with R2 caching and HuggingFace fallback.

## License

- **Code**: Apache-2.0 ([LICENSE](https://github.com/evo-design/evo/blob/main/LICENSE))
- **Weights**: Apache-2.0

## References & Citations

### Papers

1. Nguyen E, Poli M, Durrant MG, et al. "Sequence modeling and design from molecular to genome scale with Evo." *Science* (2024). [DOI](https://doi.org/10.1126/science.ado9336)

### BibTeX

```bibtex
@article{nguyen2024evo,
  title={Sequence modeling and design from molecular to genome scale with Evo},
  author={Nguyen, Eric and Poli, Michael and Durrant, Matthew G and Kang, Brian and Katrekar, Dhruva and Li, David B and Bartie, Liam J and Thomas, Armin W and King, Samuel H and Brixi, Garyk and Sullivan, Jeremy and Ng, Madelena Y and Lewis, Ashley and Lou, Aaron and Ermon, Stefano and Baccus, Stephen A and Hernandez-Boussard, Tina and R\'{e}, Christopher and Hsu, Patrick D and Hie, Brian L},
  journal={Science},
  year={2024},
  doi={10.1126/science.ado9336}
}
```

### Links

- **Paper**: [DOI:10.1126/science.ado9336](https://doi.org/10.1126/science.ado9336) | [bioRxiv:2024.02.27.582234](https://www.biorxiv.org/content/10.1101/2024.02.27.582234)
- **Code**: [github.com/evo-design/evo](https://github.com/evo-design/evo)
- **StripedHyena**: [github.com/togethercomputer/stripedhyena](https://github.com/togethercomputer/stripedhyena)
- **Model weights**: [HuggingFace togethercomputer](https://huggingface.co/togethercomputer)

---

*See also: [MODEL.md](MODEL.md) for technical deep-dive | [BIOLOGY.md](BIOLOGY.md) for biological context*
