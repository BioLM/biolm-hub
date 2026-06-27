# NanoBERT -- Technical Details

## Architecture

### Model Type & Innovation

NanoBERT is a deep learning model specifically designed for nanobody (single-domain antibody / VHH) sequences. It is based on the RoBERTa architecture (`AutoModelForMaskedLM` with `RobertaTokenizer`), trained with a masked language modeling objective on nanobody sequences.

The key innovation of NanoBERT is its specialization for nanobodies rather than conventional paired antibodies. Nanobodies are single-domain antibodies derived from camelid heavy-chain-only antibodies (HCAbs) that lack a light chain. Their smaller size, higher stability, and unique CDR characteristics (particularly the elongated CDR-H3) make them distinct from conventional antibody variable domains, warranting a specialized language model.

NanoBERT enables gene-agnostic navigation of the nanobody mutational space, learning sequence patterns without relying on germline gene assignments. This allows it to capture functional properties that are independent of VHH germline identity.

### Parameters & Layers

| Property | Value |
|----------|-------|
| Architecture | RoBERTa (AutoModelForMaskedLM) |
| Training objective | Masked language modeling (MLM) |
| Tokenizer | RobertaTokenizer (character-level) |
| Max sequence length | 154 residues |
| Input type | Single nanobody (VHH) sequence |

<!-- TODO: Extract exact parameter count and hidden dimensions from the NanoBERT model checkpoint -- see sources.yaml source_repos[0] (https://github.com/NaturalAntibody/NanoBERT) -->

### Training Data

| Property | Details |
|----------|---------|
| Dataset | Nanobody sequences from published sources |
| Composition | Single-domain antibody (VHH) sequences |
| Species | Primarily camelid-derived nanobodies |

### Loss Function & Objective

Masked language modeling (MLM) with cross-entropy loss:

```
L = -Sum_i log P(x_masked_i | x_visible)
```

Standard RoBERTa-style masking applied to nanobody sequences. The model learns amino acid preferences at each position in the context of the full nanobody sequence.

### Tokenization / Input Processing

| Property | Details |
|----------|---------|
| Tokenizer | RobertaTokenizer (character-level) |
| Input format | Raw amino acid sequence (no spaces) |
| Special tokens | `<s>`, `</s>`, `<pad>`, `<mask>` |
| Vocabulary | 20 standard (unambiguous) amino acids |
| Max sequence length | 154 residues |
| Batch size | 32 sequences |

Input sequences are validated against the 20 unambiguous amino acids only (no extended alphabet). This is more restrictive than models that accept extended amino acid codes.

## Performance & Benchmarks

### Published Benchmarks

The NanoBERT paper evaluates the model on nanobody mutational landscape navigation and property prediction tasks.

<!-- TODO: Extract benchmark numbers from Table 1 of the NanoBERT paper for mutational landscape navigation -- see sources.yaml primary_papers[0] (DOI: 10.1093/bioinformatics/btae123) -->

Key findings from the paper:
- NanoBERT captures nanobody-specific sequence patterns better than general protein LMs
- Gene-agnostic approach allows the model to generalize across VHH germline families
- Effective for navigating the mutational space of nanobodies for design purposes

### BioLM Verification Results

The BioLM implementation loads official pre-trained weights via `AutoModelForMaskedLM.from_pretrained()`. Numerical verification is performed against golden reference outputs:

| Metric | Threshold | Status |
|--------|-----------|--------|
| Relative tolerance | 1e-4 | PASS |
| Cosine distance | < 0.02 | PASS |

Tests cover encode, generate, and predict_log_prob actions.

### Comparison to Alternatives

| Model | Type | Key Advantage | Key Disadvantage |
|-------|------|---------------|------------------|
| **NanoBERT (this)** | Nanobody LM | Specialized for VHH sequences | Nanobody-only, 154 residue limit |
| IgBERT (unpaired) | Antibody LM | Longer sequences, generate action | Not nanobody-specialized |
| AbLang2 | Antibody LM | Germline debiasing, paired chains | Requires paired sequences |
| ESM-2 | General protein LM | Broad protein coverage | Not nanobody-specialized |

### Error Bars & Confidence

NanoBERT is deterministic when seeds are set. The same input produces the same output on the same hardware.

## Strengths & Limitations

### Pros

- Purpose-built for nanobody/VHH sequences
- Gene-agnostic approach avoids germline bias
- CPU-only inference (no GPU required) -- very cost-effective
- Multiple output modes: mean embeddings, residue embeddings, logits
- Sequence restoration and log-probability scoring
- MIT licensed
- Lightweight (2 GB memory)

### Cons

- Nanobody-only -- not suitable for conventional antibodies or other proteins
- Short max sequence length (154 residues)
- Restricted to 20 unambiguous amino acids (no extended alphabet)
- Single model size (no variants)
- No paired chain support (nanobodies are single-domain by nature)

### Known Failure Modes

- **Conventional antibodies**: The model is trained on nanobodies; conventional VH/VL domains will produce degraded representations
- **Sequences > 154 residues**: Exceeds max length; will be rejected by validation
- **Non-standard amino acids**: Characters outside the 20 standard amino acids (B, J, O, U, X, Z) are rejected
- **Full-length HCAb sequences**: NanoBERT expects variable domain (VHH) sequences only, not full heavy-chain-only antibody sequences with constant domains

## Implementation Details

### Inference Pipeline

```
Request
  |-- 1. Validate sequences (unambiguous AA alphabet, length <= 154)
  |-- 2. Extract sequences from items
  |-- 3. Tokenize with RobertaTokenizer (batch_encode_plus)
  |-- 4. Forward pass (torch.no_grad)
  |     |-- Encode: hidden states -> mean pool / residue / logits
  |     |-- Generate: <mask> -> argmax over 20 canonical AAs
  |     |-- Log prob: log_softmax -> sum non-special positions
  |-- 5. Return typed response
```

### Memory & Compute Profile

| Property | Value |
|----------|-------|
| GPU | None (CPU only) |
| Memory | 2 GB |
| CPU | 2 cores |
| Batch size | 32 |

The model runs entirely on CPU, making it the most cost-effective antibody model on the platform.

### Determinism & Reproducibility

| Setting | Value |
|---------|-------|
| `torch.manual_seed` | 42 |
| `torch.cuda.manual_seed_all` | 42 (if GPU available) |
| `torch.no_grad` | Yes (inference) |
| `model.eval()` | Yes |

### Caching Behavior

NanoBERT inherits standard two-tier caching from `BillingMixinSnap`:
- **Redis (Modal Dict)**: Fast lookup, TTL-based expiration
- **R2**: Persistent storage for cached results

## Versions & Changelog

| Version | Date | Changes |
|---------|------|---------|
| v1 | 2025-03-19 | Initial implementation with encode, generate, predict_log_prob actions |

---

*See also: [README.md](README.md) for API reference | [BIOLOGY.md](BIOLOGY.md) for biological context*
