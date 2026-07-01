# IgT5 -- Technical Details

## Architecture

### Model Type & Innovation

IgT5 is an antibody language model based on the T5 (Text-to-Text Transfer Transformer) encoder architecture. It is part of the same research effort as IgBERT, providing an alternative architectural approach to antibody representation learning. While IgBERT uses a BERT encoder, IgT5 uses the encoder component of T5 (`T5EncoderModel`), which employs relative position biases instead of absolute positional embeddings.

The key innovation of IgT5, shared with IgBERT, is the availability of both paired and unpaired variants trained at scale on antibody sequences. The paired variant processes concatenated heavy-light chain sequences with a `</s>` separator, while the unpaired variant processes individual chains.

IgT5 uses the T5 architecture from HuggingFace Transformers with a SentencePiece tokenizer, making it compatible with the broader Transformers ecosystem.

### Parameters & Layers

| Variant | Model ID | Input Type | Max Seq Length |
|---------|----------|------------|----------------|
| `igt5-paired` | IgT5 | Heavy + `</s>` + Light | 256 per chain |
| `igt5-unpaired` | IgT5_unpaired | Single chain | 512 |

| Property | Value |
|----------|-------|
| Architecture | T5 encoder (T5EncoderModel) |
| Training objective | Span corruption (T5 pre-training) |
| Tokenizer | T5Tokenizer (SentencePiece-based) |
| Positional encoding | Relative position biases |

### Training Data

| Property | Details |
|----------|---------|
| Dataset | Large-scale antibody sequences (Exscientia) |
| Composition | Antibody heavy and light chains |
| Pre-training base | T5 model fine-tuned on antibody data |

### Loss Function & Objective

T5-style span corruption objective adapted for antibody sequences. During pre-training, contiguous spans of tokens are replaced with sentinel tokens, and the model learns to reconstruct the original spans.

### Tokenization / Input Processing

| Property | Details |
|----------|---------|
| Tokenizer | T5Tokenizer (SentencePiece, case-sensitive) |
| Paired input | `H E A V Y </s> L I G H T` (space-separated residues) |
| Unpaired input | `S E Q U E N C E` (space-separated residues) |
| Special tokens | `</s>` (separator/end), `<pad>` |
| Max paired length | 256 residues per chain |
| Max unpaired length | 512 residues |
| Batch size | 8 sequences |

## Performance & Benchmarks

### Published Benchmarks

IgT5 is evaluated alongside IgBERT in the same paper, comparing BERT and T5 architectures for antibody representation learning.

Key findings from the paper (Kenlay et al. 2024, arXiv: 2403.17889):
- T5 encoder produces competitive or superior embeddings compared to BERT for some downstream tasks
- Relative position biases may better capture long-range dependencies in antibody sequences
- Both paired and unpaired variants benefit from large-scale training

### BioLM Verification Results

The BioLM implementation loads official pre-trained weights from HuggingFace via `T5EncoderModel.from_pretrained()`. Numerical verification is performed against golden reference outputs:

| Metric | Threshold | Status |
|--------|-----------|--------|
| Relative tolerance | 1e-4 | PASS |

Tests cover the encode action for both paired and unpaired variants.

### Comparison to Alternatives

| Model | Type | Key Advantage | Key Disadvantage |
|-------|------|---------------|------------------|
| **IgT5 (this)** | Antibody LM (T5) | Relative position biases, paired+unpaired | Encode only |
| IgBERT | Antibody LM (BERT) | Generate and log_prob actions | Absolute positions |
| AbLang2 | Antibody LM | Germline debiasing, multiple modes | Paired only |
| ESM-2 | General protein LM | Broad protein coverage | Not antibody-specialized |

### Error Bars & Confidence

IgT5 is deterministic when seeds are set. The same input produces the same output on the same hardware.

## Strengths & Limitations

### Pros

- T5 architecture with relative position biases
- Both paired and unpaired variants
- HuggingFace Transformers compatible
- GPU-accelerated inference on T4
- Mean-pooled and per-residue embedding outputs

### Cons

- Encode-only (no generate or log_prob actions)
- MIT per the HuggingFace model card; Zenodo lists CC-BY-4.0
- Smaller batch size (8 vs 32 for IgBERT) due to larger model footprint
- Higher memory requirements than IgBERT (16 GB vs 6 GB)

### Known Failure Modes

- **Mixed paired/unpaired requests**: All items in a batch must be the same type; mixed requests will raise an error
- **Very short sequences**: Sequences shorter than ~10 residues may produce low-quality embeddings
- **Non-antibody input**: The model expects immunoglobulin sequences

## Implementation Details

### Inference Pipeline

```
Request
  |-- 1. Validate sequences (alphabet, length, paired vs unpaired)
  |-- 2. Infer request type (_kind: paired or unpaired)
  |-- 3. Verify request type matches deployed model variant
  |-- 4. Format input:
  |     |-- Paired: "H E A V Y </s> L I G H T"
  |     |-- Unpaired: "S E Q U E N C E"
  |-- 5. Tokenize with T5Tokenizer (batch_encode_plus)
  |-- 6. Forward pass on GPU (torch.no_grad)
  |     |-- T5EncoderModel -> last_hidden_state
  |     |-- Mask special tokens
  |     |-- Mean pool or return per-residue
  |-- 7. Return IgT5EncodeResponse
```

### Memory & Compute Profile

| Variant | GPU | Memory | CPU |
|---------|-----|--------|-----|
| `igt5-paired` | T4 | 16 GB | 4 cores |
| `igt5-unpaired` | T4 | 16 GB | 4 cores |

### Determinism & Reproducibility

| Setting | Value |
|---------|-------|
| `torch.manual_seed` | 42 |
| `torch.cuda.manual_seed_all` | 42 |
| `torch.no_grad` | Yes (inference) |
| `model.eval()` | Yes |
| GPU memory snapshot | Enabled |

### Caching Behavior

Response caching is handled outside the model container by the serving layer.

## Versions & Changelog

| Version | Date | Changes |
|---------|------|---------|
| v1 | 2025-01-30 | Initial implementation with encode action |

---

*See also: [README.md](README.md) for API reference | [BIOLOGY.md](BIOLOGY.md) for biological context*
