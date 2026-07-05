# ProGen2

> **One-line summary**: Autoregressive protein language model from Salesforce Research that generates novel protein sequences and computes sequence log-likelihoods for fitness prediction.

## Overview

ProGen2 is a family of autoregressive protein language models developed by Salesforce Research. Based on the GPT-J architecture, ProGen2 is trained on large protein sequence databases to learn the statistical patterns of natural proteins and generate novel, biologically plausible sequences.

ProGen2 is available in four variants on the BioLM platform, each trained on different data: OAS (antibody-specialized), medium and large (general-purpose on UniRef90+BFD30), and BFD90 (metagenomic proteins). The model supports controllable generation via temperature and nucleus sampling parameters, and provides bidirectional log-likelihood scores for each generated sequence.

Published in *Cell Systems* (2023), ProGen2 demonstrates that autoregressive protein language models follow scaling laws similar to natural language models, with larger models producing more realistic protein sequences and better fitness predictions.

## Architecture

| Property | Value |
|----------|-------|
| Architecture | Transformer decoder (GPT-J-style, autoregressive) |
| Training objective | Causal language modeling (next-token prediction) |
| Training data | UniRef90, BFD90, OAS (variant-dependent) |
| Max sequence length | 512 residues (BioLM limit; model supports 2048) |
| Vocabulary | 32 tokens (ProGen2 custom amino-acid tokenizer) |
| Positional encoding | Rotary (RoPE) |
| License | BSD-3-Clause |

## Model Variants

| Variant | Parameters | Layers | Hidden Dim | GPU | Memory | Training Data | Use Case |
|---------|-----------|--------|------------|-----|--------|---------------|----------|
| `progen2-oas` | 151M | 12 | 1280 | None (CPU) | 8 GB | OAS (554M antibody seqs, clustered at 85% identity) | Antibody sequence generation |
| `progen2-medium` | 764M | 27 | 2560 | T4 | 8 GB | UniRef90 + BFD30 | General protein generation (default) |
| `progen2-large` | 2.7B | 32 | 4096 | T4 | 16 GB | UniRef90 + BFD30 | Higher-quality generation |
| `progen2-bfd90` | 2.7B | 32 | 4096 | T4 | 16 GB | UniRef90 + BFD90 (~2x UniRef90) | Metagenomic/diverse protein generation |

The default variant is **progen2-medium**.

Parameter counts confirmed from paper Table 1 (Nijkamp et al., 2023). Note: the paper specifies PROGEN2-medium as 27 layers (not 28) and 16 attention heads. The OAS variant shares the PROGEN2-small architecture (12 layers); medium shares the PROGEN2-base architecture.

## Capabilities & Limitations

**CAN be used for:**
- Generating novel protein sequences conditioned on an amino acid context (seed sequence)
- Scoring protein sequences via bidirectional log-likelihood (fitness prediction)
- Generating antibody variable region sequences (OAS variant)
- Producing diverse sequence libraries with controllable temperature and top-p sampling
- Extending partial protein sequences (context-conditioned completion)

**CANNOT be used for:**
- Structure prediction (use ESMFold or Chai-1 instead)
- Protein embeddings (use ESM-2 instead)
- Non-protein molecules (DNA, RNA, small molecules)
- Sequences longer than 512 residues
- Batch requests with more than 1 sequence per call

**Other considerations:**
- Generation is stochastic by default; set `seed` for reproducible outputs
- The `ll_sum` and `ll_mean` likelihood scores average forward and reverse passes for reduced positional bias
- Terminal tokens (`1` for N-terminal, `2` for C-terminal) are automatically handled and stripped from output
- The OAS variant should only be used for antibody sequences

## Actions / Endpoints

### `generate`

Generates one or more protein sequences conditioned on an input context sequence, with bidirectional log-likelihood scoring for each generated sample.

**Request Parameters:**

| Parameter | Type | Default | Range | Description |
|-----------|------|---------|-------|-------------|
| `items[].context` | str | *(required)* | 1-512 chars | Amino acid seed sequence (unambiguous AA alphabet) |
| `params.temperature` | float | 0.8 | >0.0-8.0 | Sampling temperature; lower = more conservative, higher = more diverse |
| `params.top_p` | float | 0.9 | 0.0-1.0 | Nucleus sampling threshold; 1.0 = no filtering |
| `params.num_samples` | int | 1 | 1-3 | Number of sequences to generate per input |
| `params.max_length` | int | 128 | 12-512 | Maximum total sequence length (context + generated) |
| `params.seed` | int or null | null | - | Random seed for reproducibility; null = time-based entropy |

**Response:**

```json
{
  "results": [
    [
      {
        "sequence": "MKTVRQERLKSIVRILERSKEPVSGAQ...",
        "ll_sum": -45.23,
        "ll_mean": -1.42
      }
    ]
  ]
}
```

Response fields:
- `results`: Outer list corresponds to input items (always length 1 due to batch_size=1). Inner list contains `num_samples` generated sequences.
- `sequence`: The full generated protein sequence (context + completion), with terminal tokens stripped.
- `ll_sum`: Sum of bidirectional log-likelihoods (forward + reverse, averaged). More negative = less likely.
- `ll_mean`: Mean of bidirectional log-likelihoods per position. More negative = less likely per residue.

## Usage Examples

```python
from models.progen2.schema import (
    ProGen2GenerateRequest,
    ProGen2GenerateRequestItem,
    ProGen2GenerateParams,
)

# Basic generation: extend a context sequence
request = ProGen2GenerateRequest(
    params=ProGen2GenerateParams(
        temperature=0.8,
        top_p=0.9,
        num_samples=2,
        max_length=128,
    ),
    items=[
        ProGen2GenerateRequestItem(context="MKTVRQERLKSIVRILERSKEPVSGAQ"),
    ],
)

# Reproducible generation with fixed seed
request_seeded = ProGen2GenerateRequest(
    params=ProGen2GenerateParams(
        temperature=0.7,
        top_p=0.95,
        num_samples=3,
        max_length=256,
        seed=42,
    ),
    items=[
        ProGen2GenerateRequestItem(context="MGSSHHHHHHSSGLVPRGSH"),
    ],
)
```

## Performance & Benchmarks

### Published Results

ProGen2 demonstrates scaling laws for protein language models, with perplexity decreasing log-linearly with model size:

#### Narrow Fitness Landscapes (Paper Table 3)

Average Spearman rho on narrow DMS experiments (primarily single-substitution), from Nijkamp et al. (2023):

| Model | Parameters | Avg Spearman rho |
|-------|-----------|-----------------|
| PROGEN2-small | 151M | 0.456 |
| **PROGEN2-base** | **764M** | **0.505** |
| PROGEN2-large | 2.7B | 0.485 |
| PROGEN2-xlarge | 6.4B | 0.476 |
| PROGEN2-ensemble | -- | 0.518 |

Performance peaks at 764M parameters, then decreases -- smaller models may better approximate the true fitness landscape by projecting the data distribution onto a more appropriate model class.

#### Perplexity (Paper Table 2)

| Model | Test-max90 (ppl) | Test-max50 (ppl) |
|-------|-----------------|-----------------|
| PROGEN2-small (151M) | 12.9 | 15.0 |
| PROGEN2-medium (764M) | 11.2 | 14.3 |
| PROGEN2-large (2.7B) | 11.1 | 14.4 |
| PROGEN2-xlarge (6.4B) | 9.9 | 13.9 |

Perplexity improves consistently with scale (unlike fitness prediction), confirming scaling laws for protein language models.

### SOTA Status

ProGen2 established strong baselines for autoregressive protein generation at time of publication (2023). For fitness prediction, masked language models (ESM-2, ESM-1v) and retrieval-augmented models (Tranception) generally outperform autoregressive models on standard benchmarks. For sequence generation quality, ProGen2 remains a competitive choice as of 2025.

## Implementation Verification

### Verification Method

Baseline comparison (Option C): The BioLM implementation uses official pre-trained weights from the Salesforce ProGen repository. A custom validator checks that generated sequences satisfy structural constraints (context preservation, length limits, correct sample count) rather than exact numerical reproduction, since generation is stochastic.

### Test Cases

| Test Case | Input | Verification Criterion | Status |
|-----------|-------|----------------------|--------|
| Sample count | Context sequence, num_samples=N | Exactly N sequences returned | PASS |
| Context preservation | Context "MKTV..." | All generated sequences start with context | PASS |
| Length constraint | max_length=128 | No sequence exceeds 128 residues | PASS |

### Verification Status

**Status: VERIFIED** -- Integration tests pass for all variants (oas, medium, large, bfd90) using structural validation of generated outputs.

## Resource Requirements

| Variant | GPU | Memory | CPU | Cold Start |
|---------|-----|--------|-----|------------|
| `progen2-oas` | None (CPU) | 8 GB | 2 cores | ~30s |
| `progen2-medium` | T4 | 8 GB | 2 cores | ~60s |
| `progen2-large` | T4 | 16 GB | 4 cores | ~90s |
| `progen2-bfd90` | T4 | 16 GB | 4 cores | ~90s |

## Implementation Notes

- **Memory snapshots**: ProGen2 uses `@modal.enter(snap=True)` with GPU memory snapshots enabled (`enable_memory_snapshot=True`, `enable_gpu_snapshot=True`) for fast cold starts. Model weights are loaded directly onto the GPU during snapshot creation.
- **Determinism**: Random seeds are set across all RNG sources (torch, numpy, random, CUDA) per request. Users can provide a `seed` parameter for reproducible generation; without it, time-based entropy is used.
- **Terminal tokens**: The implementation prepends `1` (N-terminal) before sampling and adds both `1` and `2` (C-terminal) for likelihood computation, following the original ProGen2 convention.
- **Bidirectional likelihood**: Log-likelihoods are computed as the average of forward (left-to-right) and reverse (right-to-left) passes, reducing positional bias inherent in autoregressive models.
- **Sequence truncation**: Generated sequences are truncated at the first occurrence of terminal tokens (`1` or `2`), and these tokens are stripped from the output.
- **External code**: The `external/` directory contains model architecture code adapted from the Salesforce ProGen repository (GPT-J-based `ProGenForCausalLM`), tokenizer utilities, and sampling/likelihood functions.
- **Weight loading**: Weights are downloaded from R2 via the declarative download system. Each variant's checkpoint is stored under `biolm-hub/model-weights/models/progen2/v1/checkpoints/progen2_{variant}/`, with a shared `tokenizer.json`.
- **Caching**: Response caching is handled outside the model container by the serving infrastructure. Note that stochastic generation means cached results are returned for identical requests, which may not be desirable -- use different seeds for fresh samples.

## License

- **Code**: BSD-3-Clause ([LICENSE](https://github.com/salesforce/progen/blob/main/LICENSE))
- **Model architecture**: Based on GPT-J (Apache-2.0)
- **Weights**: Released by Salesforce under BSD-3-Clause

## References & Citations

### Papers

1. Nijkamp E, Ruffolo JA, Weinstein EN, Naik N, Madani A. "ProGen2: Exploring the Boundaries of Protein Language Models." *Cell Systems* (2023). [arXiv: 2206.13517](https://arxiv.org/abs/2206.13517)

### BibTeX

```bibtex
@article{nijkamp2023progen2,
  title={ProGen2: Exploring the Boundaries of Protein Language Models},
  author={Nijkamp, Erik and Ruffolo, Jeffrey A. and Weinstein, Eli N. and Naik, Nikhil and Madani, Ali},
  journal={Cell Systems},
  year={2023},
  doi={10.1016/j.cels.2023.10.002}
}
```

### Links

- **Paper**: [arXiv 2206.13517](https://arxiv.org/abs/2206.13517)
- **Code**: [github.com/salesforce/progen](https://github.com/salesforce/progen)

---

*See also: [MODEL.md](MODEL.md) for technical deep-dive | [BIOLOGY.md](BIOLOGY.md) for biological context*
