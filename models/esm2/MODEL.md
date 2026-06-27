# ESM2  --  Technical Details

## Architecture

### Model Type & Innovation

ESM-2 is a masked protein language model based on the BERT (bidirectional transformer encoder) architecture. It is trained with a masked language modeling (MLM) objective: 15% of input tokens are randomly masked, and the model learns to predict the original amino acid at each masked position from the surrounding context.

The key innovation of ESM-2 over its predecessor ESM-1b is scaling. The authors systematically trained models from 8M to 15B parameters and demonstrated that representation quality improves log-linearly with model scale  --  larger models produce embeddings that better capture protein structure and function. ESM-2 at 650M parameters matches or exceeds the performance of MSA-based methods (e.g., MSA Transformer) using only single sequences as input, eliminating the costly multiple sequence alignment step.

ESM-2 uses a standard transformer encoder with pre-layer normalization, GELU activations, and learned positional embeddings. Unlike some newer protein language models, it does not use rotary position embeddings or structural supervision during training.

### Parameters & Layers

| Variant | Parameters | Layers | Hidden Dim | Attention Heads | Feed-Forward Dim | Embedding Dim |
|---------|-----------|--------|------------|-----------------|-------------------|---------------|
| esm2_t6_8M_UR50D | 8M | 6 | 320 | 20 | 1280 | 320 |
| esm2_t12_35M_UR50D | 35M | 12 | 480 | 20 | 1920 | 480 |
| esm2_t30_150M_UR50D | 150M | 30 | 640 | 20 | 2560 | 640 |
| esm2_t33_650M_UR50D | 650M | 33 | 1280 | 20 | 5120 | 1280 |
| esm2_t36_3B_UR50D | 3B | 36 | 2560 | 40 | 10240 | 2560 |

Common across all variants:

| Property | Value |
|----------|-------|
| Vocabulary size | 33 tokens (20 standard AA + special tokens) |
| Positional encoding | Learned |
| Normalization | Pre-LayerNorm |
| Activation | GELU |
| Max input length | 2048 tokens (including BOS + EOS) |

The attention head count is 20 for all variants except the 3B model which uses 40 heads. The feed-forward dimension is consistently 4x the hidden dimension across all variants. These values are confirmed from the ESM-2 model architecture (standard transformer encoder with 4x FFN expansion ratio).

### Training Data

| Property | Details |
|----------|---------|
| Dataset | UniRef50 (UR50/D) |
| Clustering | 50% sequence identity |
| Composition | Proteins from all domains of life (bacteria, archaea, eukaryota, viruses) |

ESM-2 was trained on approximately 65 million protein sequences from UniRef50 (UR50/D 2021_04 release). UniRef50 clusters UniProtKB sequences at 50% sequence identity and selects the longest sequence as the representative for each cluster. The training data encompasses hundreds of billions of amino acid residues across all domains of life.

Known biases in the training data:
- Bacterial proteins are over-represented relative to eukaryotic proteins in UniRef50
- Membrane proteins and intrinsically disordered regions are under-represented
- Very long proteins (>1022 residues) were cropped during training, so the model has limited exposure to full-length long proteins

### Loss Function & Objective

Masked language modeling (MLM) with cross-entropy loss:

```
L = -Sum_i log P(x_masked_i | x_visible)
```

During training, 15% of input tokens are randomly selected for masking. Of the selected positions:
- 80% are replaced with the `<mask>` token
- 10% are replaced with a random amino acid
- 10% are left unchanged

This is the standard BERT masking strategy applied to protein sequences.

### Tokenization / Input Processing

| Property | Details |
|----------|---------|
| Tokenizer | Character-level (one token per amino acid) |
| Special tokens | `<cls>` (BOS), `<eos>` (EOS), `<pad>`, `<mask>`, `<unk>` |
| BOS prepended | Yes |
| EOS appended | Yes |
| Extra tokens per sequence | 2 (BOS + EOS) |

The effective maximum sequence length is 2046 residues (2048 total minus 2 special tokens). In the BioLM implementation, `max_sequence_len` is set to 2048 in `ESM2Params`, which refers to the total token count including special tokens.

Input sequences are validated against the extended amino acid alphabet (20 standard + B, J, O, U, X, Z) plus the `-` gap character for the `encode` action and the `<mask>` token for the `predict` action.

## Performance & Benchmarks

### Published Benchmarks

#### Contact Prediction (Long-Range P@L)

Contact prediction accuracy improves log-linearly with model scale. The ESM-2 models achieve the following approximate long-range contact precision (P@L for contacts with sequence separation >= 24):

| Variant | Long-Range P@L (approx) |
|---------|------------------------|
| esm2_t6_8M | ~0.30 |
| esm2_t12_35M | ~0.40 |
| esm2_t30_150M | ~0.52 |
| esm2_t33_650M | ~0.57 |
| esm2_t36_3B | ~0.60 |

The 650M model matches the performance of MSA Transformer on contact prediction using only single sequences as input.

#### Structure Prediction (via ESMFold)

ESMFold, which uses ESM-2 as its language model backbone, achieves competitive structure prediction accuracy:

| Benchmark | ESMFold (ESM-2 15B backbone) | Notes |
|-----------|------------------------------|-------|
| CAMEO (2022) | Median LDDT ~0.73 | Single-sequence, no MSA |
| CASP14 free modeling | GDT-TS competitive with early AlphaFold2 single-sequence | Without templates or MSAs |

ESMFold produces structures in a single forward pass (~1-2 seconds) compared to minutes for AlphaFold2, making it suitable for proteome-scale structure prediction. The accuracy is lower than AlphaFold2 with MSAs but competitive for single-sequence methods.

#### Variant Effect Prediction

ESM-2 pseudo-log-likelihood scores correlate with experimentally measured protein fitness. On the ProteinGym DMS benchmarks, ESM-2 achieves approximately:

| Model | Avg Spearman rho (ProteinGym DMS) |
|-------|-----------------------------------|
| ESM-2 650M | ~0.42 |
| ESM-2 3B | ~0.43 |
| ESM-1v (5-model ensemble) | ~0.45 |

Key findings from the paper:
- Representation quality scales log-linearly with model size
- ESM-2 650M single-sequence performance matches MSA Transformer on contact prediction
- ESM-2 3B is the best single-sequence protein language model at time of publication

### BioLM Verification Results

The BioLM implementation uses official pre-trained weights loaded via `esm.pretrained.load_model_and_alphabet_hub()`. Numerical verification is performed against golden reference outputs:

| Metric | Threshold | Status |
|--------|-----------|--------|
| Relative tolerance | 1e-4 | PASS |
| Cosine distance | < 0.02 | PASS |

Tests cover all five variants (8m, 35m, 150m, 650m, 3b) across encode, predict, and log_prob actions.

### Comparison to Alternatives

| Model | Type | Key Advantage | Key Disadvantage |
|-------|------|---------------|------------------|
| **ESM-2 (this)** | Protein LM | Fast single-sequence inference, widely adopted | Encoder-only, no generation |
| ESM-1b | Protein LM | Predecessor, still functional | Strictly worse representations than ESM-2 at same scale |
| ProtTrans (ProtT5) | Protein LM | Encoder-decoder, generation possible | Larger compute footprint |
| SaProt | Structure-aware LM | Incorporates 3D structure tokens | Requires structure input (AlphaFold predicted or experimental) |
| ESM3 | Multimodal protein LM | Handles sequence + structure + function | Newer, less widely benchmarked |

### Error Bars & Confidence

ESM-2 is deterministic when seeds are set (as in the BioLM implementation). The same input will produce the same output on the same hardware.

Sources of variability across runs:
- Different GPU architectures may produce slightly different floating-point results (within 1e-4 relative tolerance)
- The `contacts` output is derived from attention weights and may show small numerical differences across hardware

## Strengths & Limitations

### Pros

- Fast inference: single forward pass, no MSA computation needed
- Excellent general-purpose protein representations
- Wide adoption means extensive downstream benchmarking
- MIT licensed with no restrictions
- Multiple size variants allow speed/quality tradeoff
- Rich output options: embeddings, contacts, logits, attentions

### Cons

- Encoder-only architecture cannot generate or design sequences
- Single-chain only  --  no explicit multi-chain or complex modeling
- Representation quality plateaus relative to newer structure-aware models (e.g., SaProt)
- Contact prediction from attention weights is approximate (not a dedicated contact predictor)
- No explicit handling of post-translational modifications

### Known Failure Modes

- **Very short sequences** (< 10 residues): Embeddings may lack meaningful context; consider peptide-specific models
- **Poly-amino acid repeats** (e.g., poly-Q, poly-A): The model has seen these in training but representations are low-quality
- **Non-standard residues**: Characters outside the extended AA alphabet plus `-` are rejected by validation
- **Truncation boundary effects**: Sequences at exactly the max length may have edge effects at the C-terminal region

## Implementation Details

### Inference Pipeline

```
Request
  |-- 1. Validate sequences (alphabet, length, batch size)
  |-- 2. Tokenize with ESM alphabet (add BOS/EOS)
  |-- 3. Batch with FastaBatchedDataset (toks_per_batch limit)
  |-- 4. Forward pass on GPU (torch.no_grad)
  |     |-- Encoder: N transformer layers
  |     |-- Output: representations, logits, contacts, attentions
  |-- 5. Post-process per include options:
  |     |-- mean: average per-token embeddings (excluding BOS/EOS)
  |     |-- per_token: return all token embeddings
  |     |-- bos: return BOS (CLS) token embedding
  |     |-- contacts: return predicted contact map
  |     |-- logits: slice to 20 AA vocab [4:-9]
  |     |-- attentions: average over layers and heads
  |-- 6. Sort results by sequence_index
  |-- 7. Return ESM2EncodeResponse
```

For `log_prob`, the pipeline calls `_encode_forward_pass` with `include=["logits"]`, then computes log-softmax and sums log P(residue_i) at each position.

### Memory & Compute Profile

| Variant | tokens_per_batch | GPU Memory (approx) |
|---------|-----------------|-------------------|
| 8m | 4096 | CPU only |
| 35m | 4096 | CPU only |
| 150m | 4096 | ~4 GB VRAM |
| 650m | 4096 | ~8 GB VRAM |
| 3b | 1024 | ~24 GB VRAM |

Attention computation scales as O(n^2) with sequence length. For the 650M model on a T4 (16 GB VRAM), batches of long sequences (>1000 residues) may need smaller batch sizes.

<!-- TODO: Measure actual GPU memory usage and latency at various sequence lengths  --  profile on QA deployment -->

### Determinism & Reproducibility

| Setting | Value |
|---------|-------|
| `torch.manual_seed` | 42 |
| `torch.cuda.manual_seed_all` | 42 |
| `torch.no_grad` | Yes (inference) |
| cuDNN deterministic | Not explicitly set |
| cuDNN benchmark | Not explicitly disabled |

The model produces reproducible outputs on the same GPU architecture. Small numerical differences (within 1e-4) may occur across different GPU types due to floating-point operation ordering.

### Caching Behavior

Response caching (Redis/R2 two-tier) is handled by the BioLM platform layer, not by the model container:
- **Redis (Modal Dict)**: Fast lookup, TTL-based expiration
- **R2**: Persistent storage for cached results
- **Cache key**: Determined by the request payload (sequences, params, include options, model variant)

## Versions & Changelog

| Version | Date | Changes |
|---------|------|---------|
| v1 | 2024-10-23 | Initial implementation with encode and predict actions |
| v1 (updated) | 2025-01-20 | Added `log_prob` action for zero-shot variant scoring |
| v1 (updated) | 2025-09-14 | Added 3B variant with L40S GPU support |
| v1 (updated) | 2026-03-14 | Migrated to declarative download system and source layer setup |

---

*See also: [README.md](README.md) for API reference | [BIOLOGY.md](BIOLOGY.md) for biological context*
