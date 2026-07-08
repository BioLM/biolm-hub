# IgBERT -- Technical Details

## Architecture

### Model Type & Innovation

IgBERT is an antibody language model based on the BERT (bidirectional transformer encoder) architecture. It is initialized from a general protein language model and then fine-tuned on antibody sequences, allowing it to benefit from broad protein knowledge while specializing for immunoglobulin sequence understanding.

The key innovation of IgBERT is the availability of both paired and unpaired variants. The paired variant (`IgBert`) processes concatenated heavy-light chain sequences with a `[SEP]` separator, learning cross-chain dependencies. The unpaired variant (`IgBert_unpaired`) processes individual chains, enabling analysis when only single-chain sequences are available. Both variants are trained at scale using the Exscientia antibody dataset.

IgBERT uses the standard BERT architecture with `BertForMaskedLM` from HuggingFace Transformers, making it compatible with the broader Transformers ecosystem for fine-tuning and transfer learning.

### Parameters & Layers

| Variant | Model ID | Input Type | Max Seq Length |
|---------|----------|------------|----------------|
| `igbert-paired` | IgBert | Heavy + `[SEP]` + Light | 256 per chain |
| `igbert-unpaired` | IgBert_unpaired | Single chain | 512 |

| Property | Value |
|----------|-------|
| Architecture | BERT (BertForMaskedLM) |
| Training objective | Masked language modeling (MLM) |
| Tokenizer | BertTokenizer (character-level, case-sensitive) |
| Embedding dimension | 768 (BERT-base) |

### Training Data

| Property | Details |
|----------|---------|
| Dataset | Large-scale antibody sequences (Exscientia) |
| Composition | Antibody heavy and light chains |
| Pre-training base | General protein language model (fine-tuned) |

### Loss Function & Objective

Masked language modeling (MLM) with cross-entropy loss:

```
L = -Sum_i log P(x_masked_i | x_visible)
```

Standard BERT masking strategy applied to antibody sequences. For the paired variant, the model sees both chains simultaneously, learning cross-chain contextual dependencies.

### Tokenization / Input Processing

| Property | Details |
|----------|---------|
| Tokenizer | BertTokenizer (case-sensitive, character-level for amino acids) |
| Paired input | `H E A V Y [SEP] L I G H T` (space-separated residues) |
| Unpaired input | `S E Q U E N C E` (space-separated residues) |
| Special tokens | `[CLS]`, `[SEP]`, `[PAD]`, `[MASK]` |
| Max paired length | 256 residues per chain |
| Max unpaired length | 512 residues |
| Batch size | 32 sequences |

The tokenizer operates at the character level with spaces between amino acids, allowing each residue to be an individual token.

## Performance & Benchmarks

### Published Benchmarks

The IgBERT paper (arXiv: 2403.17889) evaluates paired and unpaired models on antibody-specific tasks including binding affinity prediction and CDR embedding quality. Key findings from the paper:
- Paired models capture heavy-light chain co-evolution signals
- Fine-tuning from general protein LMs improves antibody representation quality
- Scale of training data matters for antibody language model performance

### BioLM Verification Results

The BioLM implementation loads official pre-trained weights from HuggingFace via `BertForMaskedLM.from_pretrained()`. Numerical verification is performed against golden reference outputs:

| Metric | Threshold | Status |
|--------|-----------|--------|
| Relative tolerance | 1e-4 | PASS |

Tests cover encode, generate, and log_prob actions for both paired and unpaired variants.

### Comparison to Alternatives

| Model | Type | Key Advantage | Key Disadvantage |
|-------|------|---------------|------------------|
| **IgBERT (this)** | Antibody LM | Paired + unpaired variants, HuggingFace compatible | No germline debiasing |
| AbLang2 | Antibody LM | Germline-debiased representations | Paired only, requires custom library |
| IgT5 | Antibody LM | T5 encoder, same paper | Encode only, no generate or log_prob |
| ESM-2 | General protein LM | Broad protein coverage, multiple sizes | Not antibody-specialized |

### Error Bars & Confidence

IgBERT is deterministic when seeds are set. The same input produces the same output on the same hardware.

Sources of variability:
- Different GPU architectures may produce slightly different floating-point results (within 1e-4 relative tolerance)

## Strengths & Limitations

### Pros

- Both paired and unpaired variants available
- HuggingFace Transformers compatible (easy to fine-tune)
- GPU-accelerated inference on T4
- Multiple output modes: mean embeddings, residue embeddings, logits
- Sequence restoration (generate) supported for both paired and unpaired
- Log-probability scoring for variant assessment

### Cons

- Paired and unpaired are separate deployments (cannot mix in one request)
- No germline debiasing (unlike AbLang2)
- MIT per the HuggingFace model card; Zenodo lists CC-BY-4.0
- Single model size only (no size variants)

### Known Failure Modes

- **Mixed paired/unpaired requests**: All items in a batch must be the same type (paired or unpaired); mixed requests will raise an error
- **Very short sequences**: Sequences shorter than ~10 residues may produce low-quality embeddings
- **Non-antibody input**: The model expects immunoglobulin sequences; non-antibody input will produce degraded representations

## Implementation Details

### Inference Pipeline

```
Request
  |-- 1. Validate sequences (alphabet, length, paired vs unpaired)
  |-- 2. Infer request type (_kind: paired or unpaired)
  |-- 3. Verify request type matches deployed model variant
  |-- 4. Format input:
  |     |-- Paired: "H E A V Y [SEP] L I G H T"
  |     |-- Unpaired: "S E Q U E N C E"
  |-- 5. Tokenize with BertTokenizer (batch_encode_plus)
  |-- 6. Forward pass on GPU (torch.no_grad)
  |     |-- Encode: hidden states -> mean pool / residue / logits
  |     |-- Generate: [MASK] -> argmax over canonical AAs
  |     |-- Log prob: log_softmax -> sum non-special positions
  |-- 7. Return typed response
```

### Memory & Compute Profile

| Variant | GPU | Memory | CPU |
|---------|-----|--------|-----|
| `igbert-paired` | T4 | 6 GB | 3 cores |
| `igbert-unpaired` | T4 | 6 GB | 3 cores |

### Determinism & Reproducibility

| Setting | Value |
|---------|-------|
| `torch.manual_seed` | 42 |
| `torch.cuda.manual_seed_all` | 42 |
| `torch.no_grad` | Yes (inference) |
| `model.eval()` | Yes |
| GPU memory snapshot | Enabled |

### Caching Behavior

Response caching is handled outside the model container at the serving layer. The model container itself is stateless with respect to caching.

## Versions & Changelog

| Version | Date | Changes |
|---------|------|---------|
| v1 | 2025-01-30 | Initial implementation with encode, generate, log_prob actions |

---

*See also: [README.md](README.md) for API reference | [BIOLOGY.md](BIOLOGY.md) for biological context*
