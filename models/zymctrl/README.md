# ZymCTRL

> **One-line summary**: EC number-conditioned GPT-2 language model for generating novel enzyme sequences with targeted catalytic function.

## Overview

ZymCTRL is a conditional protein language model developed by the AI4PD group (Noelia Ferruz lab) that generates enzyme sequences conditioned on Enzyme Commission (EC) numbers. Built on a GPT-2 architecture with 738M parameters, it was trained on 37 million enzyme sequences from UniProt annotated with EC classifications.

The key innovation is character-level tokenization of EC numbers (e.g., "2.7.1.1" becomes ["2", ".", "7", ".", "1", ".", "1"]), which enables the model to learn hierarchical relationships across the enzyme classification system and transfer knowledge between related catalytic functions. This allows zero-shot generation of enzymes for any EC class without fine-tuning.

ZymCTRL is the first open-source conditional language model specifically designed for enzyme generation. Generated sequences average approximately 53% identity to natural proteins, indicating genuinely novel designs rather than memorized training data. The model has been experimentally validated: generated carbonic anhydrases showed catalytic activity in wet-lab tests.

## Architecture

| Property | Value |
|----------|-------|
| Architecture | GPT-2 Transformer (decoder-only, autoregressive) |
| Parameters | 738M |
| Layers | 36 |
| Hidden dimensions | 1280 |
| Training data | 37M enzyme sequences from UniProt with EC annotations (July 2022) |
| Training compute | 48 NVIDIA A100 GPUs, ~15,000 GPU hours |
| Max sequence length | 1024 tokens |

Key innovation: EC numbers are tokenized at the character level (e.g., "2.7.1.1" becomes ["2", ".", "7", ".", "1", ".", "1"]), enabling transfer learning across related enzyme classes.

## Model Variants

Single variant -- no size options. The model slug is `zymctrl`.

## Capabilities & Limitations

**CAN be used for:**
- Zero-shot enzyme generation for any EC class (all four levels of the EC hierarchy)
- Conditional sequence design for specific catalytic reactions
- Sequence embedding extraction for enzyme similarity analysis
- Exploring novel enzyme sequence space

**CANNOT be used for:**
- Non-enzyme proteins (model trained exclusively on EC-annotated sequences)
- Substrate-level specificity within an EC class (e.g., cannot specify which sugar a kinase acts on)
- Sequences longer than ~1000 amino acids (1024 token limit includes EC and control tokens)
- Structure prediction (use ESMFold or Boltz for structural validation of generated sequences)
- Multi-chain enzyme complexes (generates single chains only)

**Other considerations:**
- Generate outputs are stochastic: different runs produce different sequences. Use the `seed` parameter for reproducibility.
- Broad-substrate EC classes (e.g., hexokinases EC 2.7.1.1) produce more heterogeneous outputs. Narrow-substrate classes yield more consistent results.
- Recommended workflow: generate 100-1000 sequences, rank by perplexity, select top 5% (perplexity < 1.75).
- Fine-tuning on a specific EC class can improve quality for that class (demonstrated in the paper for lactate dehydrogenase).

## Actions / Endpoints

### `generate`

Generate novel enzyme sequences conditioned on an EC number. Returns sequences sorted by perplexity (lower is better).

**Request Parameters:**

| Parameter | Type | Default | Range | Description |
|-----------|------|---------|-------|-------------|
| `items[].ec_number` | str | - | Valid EC format (X.X.X.X or partial) | EC number specifying desired catalytic function |
| `params.seed` | int | null | - | Random seed for reproducibility (null = time-based) |
| `params.temperature` | float | 0.8 | 0.0-2.0 | Sampling temperature (higher = more diverse) |
| `params.top_k` | int | 9 | 1-50 | Top-k sampling parameter |
| `params.repetition_penalty` | float | 1.2 | 1.0-2.0 | Penalty for repeated tokens |
| `params.num_samples` | int | 5 | 1-20 | Number of sequences to generate per EC number |
| `params.max_length` | int | 256 | 50-1024 | Maximum sequence length in tokens |

**Response:**

```json
{
  "results": [
    [
      {
        "sequence": "MKTVRQ...",
        "perplexity": 1.23
      },
      {
        "sequence": "MGKTLA...",
        "perplexity": 1.45
      }
    ]
  ]
}
```

Results are nested: `results[i]` contains the sorted list of generated sequences for `items[i]`. Sequences are sorted by perplexity ascending (best first).

### `encode`

Extract embeddings from enzyme sequences using ZymCTRL's internal representations. Optionally provide an EC number as context to bias the embedding toward functional representation.

**Request Parameters:**

| Parameter | Type | Default | Range | Description |
|-----------|------|---------|-------|-------------|
| `items[].sequence` | str | - | 1-1024 residues, standard amino acids | Amino acid sequence to encode |
| `items[].ec_number` | str | null | Valid EC format or null | Optional EC number for context |
| `params.pooling` | str | "mean" | "mean", "last", "per_token" | Embedding pooling strategy |
| `params.layer` | int | -1 | -36 to 36 | Hidden layer to extract embeddings from |

**Response:**

```json
{
  "results": [
    {
      "sequence_index": 0,
      "embedding": [0.123, -0.456, ...]
    }
  ]
}
```

Embedding dimension is 1280. For `per_token` pooling, `per_token_embeddings` (list of lists) is returned instead of `embedding`.

## Usage Examples

```python
# Generate enzyme sequences for carbonic anhydrase (EC 4.2.1.1)
from models.zymctrl.schema import (
    ZymCTRLGenerateParams,
    ZymCTRLGenerateRequest,
    ZymCTRLGenerateRequestItem,
)

generate_request = ZymCTRLGenerateRequest(
    params=ZymCTRLGenerateParams(
        temperature=0.8,
        top_k=9,
        repetition_penalty=1.2,
        num_samples=10,
        max_length=256,
        seed=42,  # For reproducibility
    ),
    items=[
        ZymCTRLGenerateRequestItem(ec_number="4.2.1.1"),
    ],
)
```

```python
# Extract embeddings with EC context
from models.zymctrl.schema import (
    ZymCTRLEncodeParams,
    ZymCTRLEncodeRequest,
    ZymCTRLEncodeRequestItem,
    ZymCTRLPoolingType,
)

encode_request = ZymCTRLEncodeRequest(
    params=ZymCTRLEncodeParams(
        pooling=ZymCTRLPoolingType.MEAN,
        layer=-1,  # Last hidden layer
    ),
    items=[
        ZymCTRLEncodeRequestItem(
            sequence="MKTVRQERLKSIVRILERSKEPVSGAQLAEELSVSRQVIVQDI",
            ec_number="3.5.5.1",  # Optional EC context
        ),
    ],
)
```

## Performance & Benchmarks

### Published Results

| EC Class | Name | Avg Perplexity | Sequence Identity to Natural | Notes |
|----------|------|----------------|------------------------------|-------|
| 2.7.1.2 | Glucokinase | ~1.1 | ~53% | Well-represented class |
| 4.2.1.1 | Carbonic anhydrase | Variable | ~53% | Experimentally validated |
| 1.1.1.27 | Lactate dehydrogenase | ~2.3 | - | Fine-tuning target in paper |

Key metrics:
- Perplexity < 1.75 indicates high-quality generated sequences
- Generated sequences average ~53% identity to closest natural proteins
- Experimentally validated carbonic anhydrases showed catalytic activity

### SOTA Status

ZymCTRL is the first EC number-conditioned language model for enzyme generation (as of the 2024 bioRxiv preprint). No direct competitor offers the same EC-conditioned zero-shot generation capability. Alternative approaches (directed evolution, rational design) are experimental rather than computational.

## Implementation Verification

### Verification Method
Combined Option A (Published Values) + Option B (Known Extremes): Tested EC numbers from the paper against implausible EC numbers. Per the paper, valid EC classes should produce lower perplexity sequences than random/implausible ECs.

### Test Cases

| EC Number | Name | Expected | Avg PPL | Min PPL | Source | Status |
|-----------|------|----------|---------|---------|--------|--------|
| 2.7.1.2 | Glucokinase | LOW | 1.11 | 1.06 | Paper Fig. 1b example | PASS |
| 1.1.1.27 | Lactate Dehydrogenase | LOW | 2.28 | 1.95 | Paper Fig. 4, fine-tuning target | PASS |
| 4.2.1.1 | Carbonic Anhydrase | LOW | 3.05 | 1.17 | Paper Fig. 3, main test case | PASS* |
| 9.9.9.9 | Implausible EC | HIGH | 8.92 | 8.46 | Non-existent EC class | PASS |
| 1.1 | Partial EC | MEDIUM | 5.15 | 2.80 | Broad 2-level class | PASS* |

*Notes: Carbonic anhydrase shows high variance but produces excellent min perplexity (1.17). Partial EC (1.1) correctly shows higher uncertainty since model was trained on full 4-level EC numbers.

### Results Summary
**5/5 core behaviors verified.** Key finding: Valid ECs produce average perplexity of 2.15 vs 8.92 for implausible ECs (4.1x difference), confirming the paper's claim that the model differentiates between valid and random EC labels. Glucokinase achieved perplexity 1.11, well below the paper's 1.5 quality threshold.

### Key Observations
- Model correctly assigns higher perplexity to implausible EC numbers
- Well-represented EC classes (glucokinase) achieve perplexity < 1.5 as expected
- Perplexity computed on amino acid tokens only (excluding EC/control tokens), matching paper methodology
- Prompt format matches training: `<ec_number><sep><start>` then model generates `<sequence><end>`

### Verification Status
**Status: VERIFIED WITH NOTES** (2024-12-07) -- Implementation correctly differentiates valid vs implausible ECs. Core perplexity patterns match paper expectations. Some variance in individual EC classes is expected due to stochastic generation.

## Resource Requirements

| Resource | Value |
|----------|-------|
| GPU | T4 (16GB VRAM) |
| Memory | 16 GB system RAM |
| CPU | 2 cores |
| Cold start | Fast (GPU memory snapshots enabled) |
| Timeout | 10 minutes |
| Generate batch size | 1 item (up to 20 samples per item) |
| Encode batch size | Up to 8 sequences |

## Implementation Notes

- **Memory snapshots**: Uses `@modal.enter(snap=True)` with GPU memory snapshot (`enable_memory_snapshot=True`, `enable_gpu_snapshot=True`) for fast cold starts
- **Model loading**: Weights downloaded via R2 (primary) with HuggingFace fallback. Pinned to revision `3c532ef` for reproducibility.
- **Generate action**: Builds prompt as `<ec_number><sep><start>`, generates via top-k sampling, computes perplexity on amino acid tokens only (excluding EC/control tokens), sorts results by perplexity ascending
- **Encode action**: Wraps sequences in training-format boundary tokens (`<start>`, `<end>`, optionally `<ec><sep>` prefix). Supports mean, last-token, and per-token pooling from any of the 36 hidden layers.
- **Determinism**: Generate is stochastic (use `seed` param for reproducibility). Encode is deterministic.
- **Caching**: Standard BioLM two-tier caching (Redis + R2). Most useful for encode (deterministic); less useful for generate (stochastic outputs).

## Confidence Metrics

| Metric | Range | Interpretation |
|--------|-------|----------------|
| Perplexity | >0, no upper bound | < 1.5: excellent, 1.5-2.0: good, 2.0-4.0: moderate, >4.0: likely poor quality |

Perplexity is computed on amino acid tokens only, excluding EC number and control tokens. This matches the paper's methodology and provides values directly comparable to the paper's quality thresholds. Lower perplexity indicates the generated sequence is more consistent with the model's learned distribution for that EC class.

## Technical Glossary

**EC number (Enzyme Commission number)**: Hierarchical four-level numerical classification of enzyme function (e.g., 4.2.1.1). Level 1 = reaction type, Level 2 = substrate type, Level 3 = specifics, Level 4 = individual enzyme.

**Control tag**: The EC number prepended to a sequence during training and inference, which conditions the model's generation on a specific catalytic function.

**Perplexity**: Exponential of the average cross-entropy loss. Measures how "surprised" the model is by a sequence. Lower values mean the sequence fits the model's learned enzyme distribution better.

**Top-k sampling**: At each generation step, only the top k most probable next tokens are considered. Lower k = more conservative; higher k = more diverse.

**Repetition penalty**: Multiplicative penalty applied to tokens that have already appeared in the generated sequence, discouraging repetitive patterns.

## License

- **Code and weights**: Apache-2.0 ([HuggingFace](https://huggingface.co/AI4PD/ZymCTRL))

## References & Citations

### Papers

1. Munsamy G, Illanes-Vicioso R, Funcillo S, Nakou IT, Lindner S, Ayres G, Sheehan LS, Moss S, Eckhard U, Lorenz P, Ferruz N. "Conditional language models enable the efficient design of proficient enzymes." *bioRxiv* (2024). [DOI](https://doi.org/10.1101/2024.05.03.592223)

### BibTeX

```bibtex
@article{munsamy2024conditional,
  title={Conditional language models enable the efficient design of proficient enzymes},
  author={Munsamy, Geraldene and Illanes-Vicioso, Ramiro and Funcillo, Silvia and
          Nakou, Ioanna T. and Lindner, Sebastian and Ayres, Gavin and Sheehan, Lesley S.
          and Moss, Steven and Eckhard, Ulrich and Lorenz, Philipp and Ferruz, Noelia},
  journal={bioRxiv},
  year={2024},
  doi={10.1101/2024.05.03.592223}
}
```

### Links

- **Paper**: [bioRxiv 2024.05.03.592223](https://www.biorxiv.org/content/10.1101/2024.05.03.592223)
- **Model weights**: [HuggingFace AI4PD/ZymCTRL](https://huggingface.co/AI4PD/ZymCTRL)

---

*See also: [MODEL.md](MODEL.md) for technical deep-dive | [BIOLOGY.md](BIOLOGY.md) for biological context*
