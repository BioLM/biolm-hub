# ESM-1b

> **One-line summary**: Legacy masked protein language model (650M parameters) from Meta AI/FAIR that produces sequence embeddings, masked-token predictions, and per-sequence log-probabilities for proteins up to 1022 residues. **Superseded by ESM-2 -- use ESM-2 for new work.**

## Overview

ESM-1b (Evolutionary Scale Modeling 1b) is a protein language model developed by Meta AI's Fundamental AI Research (FAIR) team (Rives et al., PNAS 2021). Trained with a masked language modeling objective on approximately 250 million protein sequences from UniRef50, it learns contextual representations of amino acids from evolutionary sequence data alone -- no structural supervision is required.

ESM-1b was the first large-scale protein language model to demonstrate that biological structure and function emerge from unsupervised learning on protein sequences. Its representations encode secondary structure, tertiary contacts, and remote homology at the fold level. This landmark finding directly motivated the development of ESM-2, ESMFold, and subsequent protein foundation models.

**Legacy status**: ESM-1b has been superseded by ESM-2 (Lin et al., 2023), which provides strictly better representations at the same parameter count through improved training. ESM-1b is retained in the catalog for backward compatibility and for reproducing results from published studies that specifically used this model.

## Architecture

| Property | Value |
|----------|-------|
| Architecture | Transformer encoder (BERT-style) |
| Parameters | 650M |
| Layers | 33 |
| Hidden dimensions | 1280 |
| Attention heads | 20 |
| Training objective | Masked language modeling (MLM) |
| Training data | UniRef50 (UR50/S) -- ~250M sequences |
| Max sequence length | 1022 residues |
| Vocabulary | 33 tokens (20 standard AA + special tokens) |
| License | MIT |

The model uses pre-activation layer normalization (differs from standard RoBERTa) and was trained with 15% masked language modeling objective.

## Model Variants

Single variant -- no size options. The sole deployment is the full 650M parameter model.

## Capabilities & Limitations

**CAN be used for:**
- Generating per-residue and mean-pooled sequence embeddings for downstream ML tasks
- Masked token prediction (fill-in-the-blank for protein sequences)
- Zero-shot variant effect prediction via pseudo-log-likelihood scoring (`log_prob`)
- Extracting attention maps for structural analysis
- Remote homology detection via embedding space similarity

**CANNOT be used for:**
- Sequences longer than 1022 residues (use ESM-2 for up to 2046)
- 3D structure prediction (use ESMFold or Chai-1)
- Sequence generation or design (encoder-only model)
- Non-protein molecules (DNA, RNA, small molecules)
- Multi-chain / protein complex modeling

**Other considerations:**
- Superseded by ESM-2 for most applications -- ESM-2-650M is recommended for new work
- Batch size is capped at 8 sequences per request
- GPU memory snapshots provide fast cold starts
- Deterministic outputs with seed=42

## Actions / Endpoints

### `encode`

Generates embeddings and optional auxiliary outputs (attentions, logits) for one or more protein sequences.

**Request Parameters:**

| Parameter | Type | Default | Range | Description |
|-----------|------|---------|-------|-------------|
| `items[].sequence` | str | *(required)* | 1-1022 characters | Amino acid sequence (standard + extended AA alphabet plus `-`) |
| `params.repr_layers` | list[int] | `[-1]` | -34 to 33 | Transformer layers to extract representations from. Negative indexing supported. |
| `params.include` | list[str] | `["mean"]` | `mean`, `per_token`, `bos`, `logits`, `attentions` | Output types to include |

**Response:**

```json
{
  "results": [
    {
      "sequence_index": 0,
      "embeddings": [{"layer": 33, "embedding": [0.012, -0.034, ...]}],
      "residue_embeddings": null,
      "bos_embeddings": null,
      "logits": null,
      "attentions": null,
      "vocab_tokens": null
    }
  ]
}
```

Fields are `null` (omitted from JSON) unless their corresponding `include` option is set.

### `predict`

Performs masked token prediction. Input sequences must contain one or more `<mask>` tokens. Returns per-position logits over the amino acid vocabulary.

**Request Parameters:**

| Parameter | Type | Default | Range | Description |
|-----------|------|---------|-------|-------------|
| `items[].sequence` | str | *(required)* | 1-1022 characters | Sequence with one or more `<mask>` tokens |

**Response:**

```json
{
  "results": [
    {
      "logits": [[0.1, -0.3, ...], ...],
      "sequence_tokens": ["M", "A", "<mask>", "K", ...],
      "vocab_tokens": ["L", "A", "G", "V", ...]
    }
  ]
}
```

`logits` shape is `[L, V]` where L is the sequence length (excluding BOS/EOS) and V is 20 (the 20 standard amino acid tokens in ESM vocabulary order).

### `log_prob`

Computes the total log-probability of an unmasked sequence under the ESM-1b model. This is the sum of log P(residue_i | context) across all canonical amino acid positions, useful for zero-shot variant effect prediction and sequence scoring.

**Request Parameters:**

| Parameter | Type | Default | Range | Description |
|-----------|------|---------|-------|-------------|
| `items[].sequence` | str | *(required)* | 1-1022 characters | Unmasked amino acid sequence |

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

More negative values indicate less likely sequences under the model. Compare wild-type vs mutant log-probabilities to score variant effects.

## Usage Examples

```python
# Encode -- get mean embeddings
from models.esm1b.schema import (
    ESM1bEncodeRequest,
    ESM1bEncodeRequestItem,
    ESM1bEncodeRequestParams,
)

encode_request = ESM1bEncodeRequest(
    params=ESM1bEncodeRequestParams(repr_layers=[-1], include=["mean"]),
    items=[
        ESM1bEncodeRequestItem(sequence="MKTAYIAKQRQISFVKSHFSRQLEERLGLIEVQAPILSRVGDGTQDNLSGAEKAV"),
    ],
)

# Predict -- masked token prediction
from models.esm1b.schema import ESM1bPredictRequest, ESM1bPredictRequestItem

predict_request = ESM1bPredictRequest(
    items=[
        ESM1bPredictRequestItem(sequence="MKTAYIAK<mask>RQISFVKSHFSRQLEERLGLIEVQAPILSRVGDGTQDNLSGAEKAV"),
    ],
)

# Predict log probability -- sequence scoring
from models.esm1b.schema import ESM1bLogProbRequest, ESM1bEncodeRequestItem

log_prob_request = ESM1bLogProbRequest(
    items=[
        ESM1bEncodeRequestItem(sequence="MKTAYIAKQRQISFVKSHFSRQLEERLGLIEVQAPILSRVGDGTQDNLSGAEKAV"),
    ],
)
```

## Performance & Benchmarks

### Published Results

ESM-1b was evaluated on secondary structure prediction, contact prediction, and remote homology detection (Rives et al., PNAS 2021). Key qualitative findings:

- Representations encode secondary structure at per-residue accuracy comparable to alignment-based methods
- Long-range contact prediction from attention weights demonstrates emergent structural knowledge
- Embedding-space similarity detects remote homology at the fold level
- The model's internal representations spontaneously organize to reflect tertiary structure

### SOTA Status

ESM-1b was state-of-the-art for single-sequence protein representation learning at its time of publication (2021). It has since been superseded by ESM-2 (2023), which provides improved representations at every model scale.

## Implementation Verification

### Verification Method

Known extremes (Option B): The BioLM implementation was verified against proteins with well-characterized biological properties. Log-probability scoring, embedding similarity, and masked prediction were tested on ubiquitin and hemoglobin -- proteins with thoroughly understood sequence-function relationships.

### Test Cases

| Test | Description | Expected | Result | Status |
|------|-------------|----------|--------|--------|
| Log-prob scoring | Real vs shuffled ubiquitin | Real > shuffled | -0.17 vs -36.74 | PASS |
| Embedding similarity | Human vs horse hemoglobin | >0.8 | 0.999 | PASS |
| Embedding dissimilarity | Ubiquitin vs hemoglobin | <0.95 | 0.889 | PASS |
| Masked prediction | Lys48 in ubiquitin | K (Lysine) | K (exact match) | PASS |

### Verification Details

1. **Log-probability**: Real ubiquitin has 220x better per-AA log-probability than a shuffled version with identical amino acid composition, confirming the model captures evolutionary signal.

2. **Embeddings**: Similar proteins (human/horse hemoglobin alpha chains) cluster tightly (0.999 cosine similarity), while different protein families show lower similarity (0.889).

3. **Masked prediction**: The model correctly predicts Lysine (K) at position 48 of ubiquitin -- a biologically critical residue for ubiquitin chain formation. Top 3 predictions (K, R, Q) are all biologically reasonable (basic/polar amino acids).

### Verification Status

**Status: VERIFIED** (2025-12-07) -- All 4 biological test cases pass. Golden reference outputs verified with rel_tol=1e-4 and cosine_distance_threshold=0.02.

## Resource Requirements

| Resource | Value |
|----------|-------|
| GPU | T4 (16 GB VRAM) |
| Memory | 16 GB |
| CPU | 4 cores |
| Cold start | Fast (GPU memory snapshots enabled) |
| Batch size | 8 sequences max |

## Implementation Notes

- **Memory snapshots**: ESM-1b uses `@modal.enter(snap=True)` with GPU memory snapshots enabled (`enable_memory_snapshot=True`, `experimental_options={"enable_gpu_snapshot": True}`) for fast cold starts.
- **Determinism**: Seeds are set (`torch.manual_seed(42)`, `torch.cuda.manual_seed_all(42)`) for reproducible outputs.
- **Weight loading**: Weights are downloaded from R2 (with HuggingFace Hub fallback) and loaded via HuggingFace `EsmForMaskedLM.from_pretrained()`. HF revision pinned to `7b37824baec4d3658e1df7479222a7c79b465b76`.
- **Container image**: Built on `pytorch/pytorch:2.6.0-cuda12.4-cudnn9-runtime` with `transformers==4.36.2`, `safetensors==0.5.3`, `huggingface_hub==0.26.0`.
- **Tokenization**: Uses HuggingFace `EsmTokenizer` with padding and truncation. BOS and EOS tokens are automatically handled.
- **Logit filtering**: Raw logits are filtered to the 20 standard (canonical) amino acids for the `logits` and `predict` outputs.
- **Caching**: Response caching is handled by the serving infrastructure upstream of the model container.

## License

- **Code**: MIT ([LICENSE](https://github.com/facebookresearch/esm/blob/main/LICENSE))
- **Weights**: MIT (same license covers pre-trained weights)

## References & Citations

### Papers

1. Rives A, Meier J, Sercu T, Goyal S, Lin Z, Liu J, Guo D, Ott M, Zitnick CL, Ma J, Fergus R. "Biological structure and function emerge from scaling unsupervised learning to 250 million protein sequences." *Proceedings of the National Academy of Sciences* (2021). [DOI: 10.1073/pnas.2016239118](https://doi.org/10.1073/pnas.2016239118)

### BibTeX

```bibtex
@article{rives2021biological,
  title={Biological structure and function emerge from scaling unsupervised learning to 250 million protein sequences},
  author={Rives, Alexander and Meier, Joshua and Sercu, Tom and Goyal, Siddharth and Lin, Zeming and Liu, Jason and Guo, Demi and Ott, Myle and Zitnick, C Lawrence and Ma, Jerry and Fergus, Rob},
  journal={Proceedings of the National Academy of Sciences},
  volume={118},
  number={15},
  pages={e2016239118},
  year={2021},
  doi={10.1073/pnas.2016239118}
}
```

### Links

- **Paper**: [DOI: 10.1073/pnas.2016239118](https://doi.org/10.1073/pnas.2016239118)
- **Code**: [github.com/facebookresearch/esm](https://github.com/facebookresearch/esm)
- **Model weights**: [huggingface.co/facebook/esm1b_t33_650M_UR50S](https://huggingface.co/facebook/esm1b_t33_650M_UR50S)

---

*See also: [MODEL.md](MODEL.md) for technical deep-dive | [BIOLOGY.md](BIOLOGY.md) for biological context*
