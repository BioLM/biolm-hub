# ESM2

> **One-line summary**: Masked protein language model (BERT-style) from Meta AI/FAIR that produces sequence embeddings, masked-token predictions, and per-sequence log-probabilities for proteins up to 2048 residues.

## Overview

ESM-2 (Evolutionary Scale Modeling 2) is a protein language model developed by Meta AI's Fundamental AI Research (FAIR) team. It is trained with a masked language modeling objective on UniRef50, learning contextual representations of amino acids from evolutionary sequence data alone  --  no structural supervision is required during pre-training.

ESM-2 is the most widely-used model in this catalog and serves as the backbone for downstream models (e.g., ESMFold for structure prediction). Its embeddings capture rich evolutionary and biophysical information and have been shown to be competitive with or superior to alignment-based methods on many protein function prediction tasks.

The model is available in five size variants (8M to 3B parameters), allowing users to trade off between speed and representation quality depending on their use case.

## Architecture

| Property | Value |
|----------|-------|
| Architecture | Transformer encoder (BERT-style) |
| Training objective | Masked language modeling (MLM) |
| Training data | UniRef50 (UR50/D) |
| Max sequence length | 2048 amino-acid residues (BOS/EOS added internally) |
| Vocabulary | 33 tokens (20 standard AA + special tokens) |
| License | MIT |

## Model Variants

| Variant | Parameters | Layers | Hidden Dim | GPU | Memory | Use Case |
|---------|-----------|--------|------------|-----|--------|----------|
| `esm2-8m` | 8M | 6 | 320 | None (CPU) | 8 GB | Fast prototyping, large-scale screening |
| `esm2-35m` | 35M | 12 | 480 | None (CPU) | 8 GB | Lightweight embeddings |
| `esm2-150m` | 150M | 30 | 640 | T4 | 16 GB | Balanced speed/quality |
| `esm2-650m` | 650M | 33 | 1280 | T4 | 16 GB | **Production default**  --  best quality/cost tradeoff |
| `esm2-3b` | 3B | 36 | 2560 | L40S | 32 GB | Maximum representation quality |

The default variant is **esm2-650m**. This is the recommended choice for most production workloads.

## Capabilities & Limitations

**CAN be used for:**
- Generating per-residue and mean-pooled sequence embeddings for downstream ML tasks
- Masked token prediction (fill-in-the-blank for protein sequences)
- Zero-shot variant effect prediction via log-probability scoring (`log_prob`)
- Extracting attention maps and contact predictions
- Feature extraction for downstream classifiers (stability, function, localization)

**CANNOT be used for:**
- 3D structure prediction (use ESMFold or Chai-1 instead)
- Sequence generation or design (this is an encoder-only model)
- Non-protein molecules (DNA, RNA, small molecules)
- Multi-chain / protein complex modeling

**Other considerations:**
- Sequences longer than 2048 amino-acid residues are truncated (BOS/EOS are added internally)
- The model uses GPU memory snapshots for fast cold starts
- Batch size is capped at 8 sequences per request
- The 3B variant uses a reduced tokens-per-batch (1024 vs 4096) to fit in GPU memory

## Actions / Endpoints

### `encode`

Generates embeddings and optional auxiliary outputs (contacts, attentions, logits) for one or more protein sequences.

**Request Parameters:**

| Parameter | Type | Default | Range | Description |
|-----------|------|---------|-------|-------------|
| `items[].sequence` | str | *(required)* | - | Amino acid sequence (1-2048 characters, standard + extended AA alphabet plus `-`) |
| `params.repr_layers` | list[int] | `[-1]` | - | Transformer layers to extract representations from. Negative indexing supported. |
| `params.include` | list[str] | `["mean"]` | - | Output types: `mean`, `per_token`, `bos`, `contacts`, `logits`, `attentions` |

**Response:**

```json
{
  "results": [
    {
      "sequence_index": 0,
      "embeddings": [{"layer": 33, "embedding": [0.012, -0.034, ...]}]
    }
  ]
}
```

Optional fields (`residue_embeddings`, `bos_embeddings`, `contacts`, `logits`, `attentions`, `vocab_tokens`) are omitted from the response when their corresponding `include` option is not set.

### `predict`

Performs masked token prediction. Input sequences must contain one or more `<mask>` tokens. Returns per-position logits over the amino acid vocabulary.

**Request Parameters:**

| Parameter | Type | Default | Range | Description |
|-----------|------|---------|-------|-------------|
| `items[].sequence` | str | *(required)* | - | Sequence with `<mask>` tokens (1-2048 characters) |

**Response:**

```json
{
  "results": [
    {
      "logits": [[0.1, -0.3, ...], ...],
      "sequence_tokens": ["M", "A", "<mask>", "K", ...],
      "vocab_tokens": ["A", "R", "N", "D", ...]
    }
  ]
}
```

`logits` shape is `[L, 20]` where L is the sequence length (excluding BOS/EOS) and 20 is the standard amino acid vocabulary.

### `log_prob`

Computes the summed per-residue log-probability of an unmasked sequence under the ESM2 model using a single forward pass (not a masked pseudo-log-likelihood). This is the sum of log P(residue_i | full sequence) across all canonical positions, useful for zero-shot variant effect prediction and sequence scoring.

**Request Parameters:**

| Parameter | Type | Default | Range | Description |
|-----------|------|---------|-------|-------------|
| `items[].sequence` | str | *(required)* | - | Unmasked amino acid sequence (1-2048 characters) |

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
# Encode  --  get mean embeddings
from models.esm2.schema import (
    ESM2EncodeRequest,
    ESM2EncodeRequestItem,
    ESM2EncodeRequestParams,
)

encode_request = ESM2EncodeRequest(
    params=ESM2EncodeRequestParams(repr_layers=[-1], include=["mean"]),
    items=[
        ESM2EncodeRequestItem(sequence="MKTVRQERLKSIVRILERSKEPVSGAQLAEELSVSRQVIVQDIAYLRSLGYNIVATPRGYVLAGG"),
    ],
)

# Predict  --  masked token prediction
from models.esm2.schema import ESM2PredictRequest, ESM2PredictRequestItem

predict_request = ESM2PredictRequest(
    items=[
        ESM2PredictRequestItem(sequence="MKT<mask>RQERLKSIVRILERSKEPVSGAQ"),
    ],
)

# Predict log probability  --  sequence scoring
from models.esm2.schema import ESM2LogProbRequest, ESM2EncodeRequestItem

log_prob_request = ESM2LogProbRequest(
    items=[
        ESM2EncodeRequestItem(sequence="MKTVRQERLKSIVRILERSKEPVSGAQLAEELSVSRQVIVQDIAYLRSLGYNIVATPRGYVLAGG"),
    ],
)
```

## Performance & Benchmarks

### Published Results

ESM-2 was evaluated on contact prediction, structure prediction (via ESMFold), and representation quality across model scales.

Key published results from the ESM-2 paper (Lin et al., Science 2023):

- **Contact prediction**: Long-range P@L scales log-linearly with model size. ESM-2 650M (~0.57 P@L) matches MSA Transformer using only single sequences.
- **Structure prediction**: ESMFold (built on ESM-2 15B) achieves median LDDT ~0.73 on CAMEO, producing structures in a single forward pass without MSAs.
- **Variant effect prediction**: ESM-2 650M achieves ~0.42 average Spearman rho on ProteinGym DMS benchmarks for zero-shot fitness prediction.
- **Scaling**: Representation quality improves log-linearly from 8M to 15B parameters, with no sign of saturation at the largest scale.

### SOTA Status

ESM-2 established state-of-the-art for single-sequence protein structure prediction (via ESMFold) at the time of publication. For embedding quality and variant effect prediction, it remains a strong baseline as of 2025, though newer models (e.g., ESM3, SaProt) may outperform it on specific benchmarks.

As of 2025, ESM-2 remains a strong baseline for single-sequence protein representation but has been surpassed on some benchmarks by newer structure-aware models (SaProt, ESM3) and retrieval-augmented methods (Tranception). It remains the most widely-used protein language model due to its simplicity, speed, and broad applicability.

## Implementation Verification

### Verification Method

Numerical reproduction (Option A): The BioLM implementation loads official pre-trained weights from the `facebookresearch/esm` repository via `esm.pretrained.load_model_and_alphabet_hub()`. Test fixtures compare outputs against golden reference outputs stored in R2 with relative tolerance of 1e-4 and cosine distance threshold of 0.02.

### Test Cases

The test suite covers all three actions across all five variants:

| Test Case | Action | Input | Verification |
|-----------|--------|-------|--------------|
| Single sequence encode | `encode` | 1 protein sequence | Cosine similarity to golden output |
| Multiple sequence encode | `encode` | Multiple sequences with params | Cosine similarity to golden output |
| Masked prediction | `predict` | Sequence with `<mask>` tokens | Logit comparison to golden output |
| Log probability | `log_prob` | Unmasked sequence | Validates output is negative finite float |

### Verification Status

**Status: Integration tests pass for all variants (8m, 35m, 150m, 650m, 3b)** with tolerances of rel_tol=1e-4 and cosine_distance_threshold=0.02.

## Resource Requirements

| Variant | GPU | Memory | CPU |
|---------|-----|--------|-----|
| `esm2-8m` | None (CPU) | 8 GB | 2 cores |
| `esm2-35m` | None (CPU) | 8 GB | 2 cores |
| `esm2-150m` | T4 | 16 GB | 4 cores |
| `esm2-650m` | T4 | 16 GB | 4 cores |
| `esm2-3b` | L40S (48 GB VRAM) | 32 GB | 4 cores |


## Implementation Notes

- **Memory snapshots**: ESM2 uses `@modal.enter(snap=True)` with GPU memory snapshots enabled (`enable_memory_snapshot=True`, `enable_gpu_snapshot=True`) for fast cold starts.
- **Determinism**: Seeds are set (`torch.manual_seed(42)`, `torch.cuda.manual_seed_all(42)`) for reproducible outputs.
- **Weight loading**: Weights are downloaded from R2 (with fallback) via the declarative download system and loaded using `esm.pretrained.load_model_and_alphabet_hub()`.
- **Tokenization**: Uses the built-in ESM alphabet and `FastaBatchedDataset` for efficient batching. BOS and EOS tokens are automatically prepended/appended.
- **Logit slicing**: Raw logits are sliced `[4:-9]` to remove special tokens and return only the 20 standard amino acid positions.
- **Tokens per batch**: The 3B model uses 1024 tokens per batch (vs 4096 for smaller variants) to fit within L40S GPU memory.
- **Caching**: Response caching is handled by the serving infrastructure, not the model container.

## License

- **Code**: MIT ([LICENSE](https://github.com/facebookresearch/esm/blob/main/LICENSE))
- **Weights**: MIT (same license covers pre-trained weights)

## References & Citations

### Papers

1. Lin Z, Akin H, Rao R, Hie B, Zhu Z, Lu W, Smetanin N, Verkuil R, Kabeli O, Shmueli Y, dos Santos Costa A, Fazel-Zarandi M, Sercu T, Candido S, Rives A. "Evolutionary-scale prediction of atomic-level protein structure with a language model." *Science* (2023). [DOI: 10.1126/science.ade2574](https://doi.org/10.1126/science.ade2574)

2. Lin Z, Akin H, Rao R, Hie B, Zhu Z, Lu W, Smetanin N, Verkuil R, Kabeli O, Shmueli Y, dos Santos Costa A, Fazel-Zarandi M, Sercu T, Candido S, Rives A. "Language models of protein sequences at the scale of evolution enable accurate structure prediction." *bioRxiv* (2022). [DOI: 10.1101/2022.07.20.500902](https://doi.org/10.1101/2022.07.20.500902)

### BibTeX

```bibtex
@article{lin2023evolutionary,
  title={Evolutionary-scale prediction of atomic-level protein structure with a language model},
  author={Lin, Zeming and Akin, Halil and Rao, Roshan and Hie, Brian and Zhu, Zhongkai and Lu, Wenting and Smetanin, Nikita and Verkuil, Robert and Kabeli, Ori and Shmueli, Yaniv and dos Santos Costa, Allan and Fazel-Zarandi, Maryam and Sercu, Tom and Candido, Sal and Rives, Alexander},
  journal={Science},
  volume={379},
  number={6637},
  pages={1123--1130},
  year={2023},
  doi={10.1126/science.ade2574}
}
```

### Links

- **Paper (Science)**: [DOI: 10.1126/science.ade2574](https://doi.org/10.1126/science.ade2574)
- **Preprint (bioRxiv)**: [DOI: 10.1101/2022.07.20.500902](https://doi.org/10.1101/2022.07.20.500902)
- **Code**: [github.com/facebookresearch/esm](https://github.com/facebookresearch/esm)
- **Model weights**: [huggingface.co/facebook/esm2_t33_650M_UR50D](https://huggingface.co/facebook/esm2_t33_650M_UR50D)

---

*See also: [MODEL.md](MODEL.md) for technical deep-dive | [BIOLOGY.md](BIOLOGY.md) for biological context*
