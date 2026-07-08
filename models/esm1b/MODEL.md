# ESM-1b -- Technical Details

## Architecture

### Model Type & Innovation

ESM-1b is a masked protein language model based on the BERT (bidirectional transformer encoder) architecture. It was trained with a masked language modeling (MLM) objective on approximately 250 million protein sequences from UniRef50. The model learns contextual amino acid representations by predicting randomly masked tokens from surrounding sequence context.

ESM-1b was the first protein language model to demonstrate that unsupervised learning at evolutionary scale could produce representations encoding biological structure and function -- including secondary structure, tertiary contacts, and remote homology at the fold level -- without any structural supervision. This was a landmark finding: the geometry of protein structure emerges from patterns in evolutionary sequence data alone.

**Legacy status**: ESM-1b has been superseded by ESM-2 (Lin et al., 2023). ESM-2 at 650M parameters matches or exceeds ESM-1b on all evaluated tasks through improved training procedures and scaling. For new projects, ESM-2 is the recommended choice.

ESM-1b uses a transformer encoder with pre-activation layer normalization (differing from the standard RoBERTa post-LayerNorm convention), GELU activations, and learned positional embeddings.

### Parameters & Layers

| Component | Details |
|-----------|---------|
| Architecture | Transformer encoder, 33 layers |
| Parameters | 650M |
| Hidden dimensions | 1280 |
| Attention heads | 20 |
| Feed-forward dimensions | 5120 |
| Embedding dimensions | 1280 |
| Vocabulary size | 33 tokens (20 standard AA + special tokens) |
| Positional encoding | Learned |
| Normalization | Pre-LayerNorm |
| Activation | GELU |

Single variant only -- no size options.

### Training Data

| Property | Details |
|----------|---------|
| Dataset | UniRef50 (UR50/S) |
| Size | ~250 million sequences |
| Clustering | 50% sequence identity |
| Composition | Proteins from all domains of life (bacteria, archaea, eukaryota, viruses) |

Known biases in the training data:
- Bacterial proteins are over-represented relative to eukaryotic proteins in UniRef50
- Membrane proteins and intrinsically disordered regions are under-represented
- Very long proteins (>1022 residues) were not seen in full during training due to the sequence length limit

### Loss Function & Objective

Masked language modeling (MLM) with cross-entropy loss:

```
L = -Sum_i log P(x_masked_i | x_visible)
```

During training, 15% of input tokens are randomly masked. The model learns to predict the identity of the masked amino acid from the bidirectional sequence context. This is the standard BERT masking strategy applied to protein sequences.

### Tokenization / Input Processing

| Property | Details |
|----------|---------|
| Tokenizer | Character-level (one token per amino acid) |
| Special tokens | `<cls>` (BOS), `<eos>` (EOS), `<pad>`, `<mask>`, `<unk>` |
| BOS prepended | Yes |
| EOS appended | Yes |
| Extra tokens per sequence | 2 (BOS + EOS) |
| Max sequence length | 1022 residues (1024 tokens - 2 for BOS/EOS) |

Input sequences are validated against the extended amino acid alphabet (20 standard + B, J, O, U, X, Z) plus the `-` gap character for the `encode` action and the `<mask>` token for the `predict` action.

## Performance & Benchmarks

### Published Benchmarks

Key findings from the paper (Rives et al., PNAS 2021):

- Representations encode secondary structure at per-residue accuracy comparable to or better than alignment-based methods
- Long-range contact prediction (top-L precision) from attention weights demonstrated structural information is learned
- Remote homology detection at the fold level via embedding similarity
- Systematic scaling study showed that larger models (650M) significantly outperform smaller ones (from 6-layer to 34-layer models)

The paper demonstrated that the model's internal representations spontaneously organize to reflect tertiary structure: attention heads learn to attend to residues that are physically proximal in 3D space, despite never seeing structural data during training.

### BioLM Verification Results

The BioLM implementation uses official pre-trained weights from HuggingFace (`facebook/esm1b_t33_650M_UR50S`) loaded via `EsmForMaskedLM.from_pretrained()`. Numerical verification is performed against golden reference outputs:

| Metric | Threshold | Status |
|--------|-----------|--------|
| Relative tolerance | 1e-4 | PASS |
| Cosine distance | < 0.02 | PASS |

Additional biological verification:

| Test | Description | Expected | Result | Status |
|------|-------------|----------|--------|--------|
| Log-prob scoring | Real vs shuffled ubiquitin | Real > shuffled | -0.17 vs -36.74 | PASS |
| Embedding similarity | Human vs horse hemoglobin | >0.8 | 0.999 | PASS |
| Embedding dissimilarity | Ubiquitin vs hemoglobin | <0.95 | 0.889 | PASS |
| Masked prediction | Lys48 in ubiquitin | K (Lysine) | K (exact match) | PASS |

### Comparison to Alternatives

| Model | Type | Key Advantage | Key Disadvantage |
|-------|------|---------------|------------------|
| **ESM-1b (this)** | Protein LM | Historical significance; well-characterized behavior | Superseded by ESM-2 at every scale |
| ESM-2 (650M) | Protein LM | Better representations at same parameter count; recommended successor | Same architecture class |
| ProtTrans (ProtT5) | Protein LM | Encoder-decoder, generation possible | Larger compute footprint |
| SaProt | Structure-aware LM | Incorporates 3D structure tokens | Requires structure input |
| ESM3 | Multimodal protein LM | Handles sequence + structure + function | Newer, less widely benchmarked |

**Recommendation**: Use ESM-2 instead of ESM-1b for all new work. ESM-1b is retained in the catalog for backward compatibility and for reproducing results from papers that specifically used ESM-1b.

## Strengths & Limitations

### Pros

- Historically important: first large-scale demonstration that protein LMs learn biological structure
- Well-characterized in published literature -- hundreds of downstream studies used ESM-1b
- Fast single-sequence inference, no MSA required
- MIT licensed with no restrictions
- Rich output options: embeddings, logits, attentions, log-probabilities

### Cons

- Superseded by ESM-2 for all tasks -- ESM-2 provides strictly better representations
- Encoder-only architecture cannot generate sequences
- Single-chain only -- no multi-chain or complex modeling
- Maximum 1022 residues (shorter than ESM-2's 2048 limit)
- No contact map extraction in BioLM implementation (ESM-2 provides this)

### Known Failure Modes

- **Very short sequences** (< 10 residues): Embeddings lack meaningful context; consider peptide-specific models
- **Poly-amino acid repeats** (e.g., poly-Q, poly-A): Repetitive sequences produce low-quality representations
- **Sequences near max length** (>1000 residues): Edge effects at the C-terminal boundary
- **Non-standard residues**: Characters outside the extended AA alphabet plus `-` are rejected by validation

## Implementation Details

### Inference Pipeline

```
Request
  |-- 1. Validate sequences (alphabet, length, batch size)
  |-- 2. Tokenize with HuggingFace EsmTokenizer (add BOS/EOS, pad)
  |-- 3. Forward pass on GPU (torch.no_grad)
  |     |-- Encoder: 33 transformer layers
  |     |-- Output: hidden_states, logits, attentions
  |-- 4. Post-process per include options:
  |     |-- mean: average per-token embeddings (excluding BOS/EOS)
  |     |-- per_token: return all token embeddings
  |     |-- bos: return BOS (CLS) token embedding
  |     |-- logits: slice to canonical AA vocab
  |     |-- attentions: average over layers and heads
  |-- 5. Return ESM1bEncodeResponse
```

For `predict`, the pipeline tokenizes sequences containing `<mask>` tokens, runs a forward pass, and returns per-position logits over the canonical amino acid vocabulary.

For `log_prob`, the pipeline calls `_encode_forward_pass` with `include=["logits"]`, then computes log-softmax and sums log P(residue_i) at each position for canonical amino acids.

### Memory & Compute Profile

| Property | Value |
|----------|-------|
| GPU | T4 (16 GB VRAM) |
| System memory | 16 GB |
| CPU | 4 cores |
| Batch size | 8 sequences |

Attention computation scales as O(n^2) with sequence length. For long sequences (>500 residues), GPU memory usage increases significantly.

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

Response caching is handled by the serving infrastructure upstream of the model container, not by the model itself:
- **Cache key**: Determined by the request payload (sequences, params, include options)

## Versions & Changelog

| Version | Date | Changes |
|---------|------|---------|
| v1 | 2025-12 | Initial implementation with encode, predict, and log_prob actions; biological verification against ubiquitin and hemoglobin test cases |

---

*See also: [README.md](README.md) for API reference | [BIOLOGY.md](BIOLOGY.md) for biological context*
