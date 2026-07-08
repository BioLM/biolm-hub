# MSA Transformer -- Technical Details

## Architecture

### Model Type & Innovation

The MSA Transformer is a **protein language model** that operates on Multiple Sequence Alignments (MSAs) rather than single sequences. Developed by Meta AI / FAIR, it is part of the ESM (Evolutionary Scale Modeling) suite.

The key innovation is **axial attention with tied row attention**. Standard transformers would require O(M * L^2) memory for an MSA of M sequences and L positions. The MSA Transformer decomposes attention into:
- **Row attention** (across positions within each sequence): Tied across all sequences in the MSA, reducing memory from O(M * L^2) to O(L^2)
- **Column attention** (across sequences at each position): Captures evolutionary covariation between sequences

Tying row attention serves a dual purpose: it reduces computational cost and it means the attention maps can be directly interpreted as contact predictions -- residue pairs that attend strongly to each other tend to be physically close in the 3D structure.

### Parameters & Layers

| Property | Value |
|----------|-------|
| Architecture | Axial Transformer with tied row attention |
| Total parameters | 100M |
| Layers | 12 |
| Embedding dimension | 768 |
| Attention heads | 12 |
| Pretrained model | `esm_msa1b_t12_100M_UR50S` |

### Training Data

| Property | Details |
|----------|---------|
| Dataset | UniRef50 / UniClust30 |
| Training set size | ~26 million MSAs |
| Average MSA depth | ~1,192 sequences per MSA |
| Sequence type | Protein (amino acid sequences) |

Known biases:
- Well-studied protein families with many homologs are over-represented
- Orphan proteins and recently evolved sequences are under-represented
- Prokaryotic proteins dominate due to sequencing bias

### Loss Function & Objective

Masked language modeling (MLM): a fraction of amino acid tokens are masked, and the model learns to predict the original residue from both the sequence context (row attention) and evolutionary context (column attention).

```
L = -sum_i log P(x_masked_i | x_visible, MSA_context)
```

This objective forces the model to learn both within-sequence grammar and between-sequence covariation patterns.

### Tokenization / Input Processing

| Property | Details |
|----------|---------|
| Tokenizer | ESM alphabet (character-level) |
| Input type | Multiple Sequence Alignment (list of aligned sequences) |
| Amino acid alphabet | 20 standard + extended AA + gap (-) + insert (.) |
| Special tokens | BOS, EOS |
| Max sequence length | 1,024 residues |
| Max MSA depth | 256 sequences |
| Min MSA depth | 2 sequences (first is query) |
| Batch size | 4 MSAs per request |

The first sequence in each MSA is treated as the query/reference sequence. All sequences must be pre-aligned to identical length.

## Performance & Benchmarks

### Published Benchmarks

From Rao et al. "MSA Transformer" (ICML 2021):

Key results:
- Unsupervised contact prediction achieves state-of-the-art among MSA-based methods at the time of publication
- Contact maps derived from tied row attention outperform previous attention-based methods (e.g., ESM-1b attention)
- Performance improves with MSA depth up to approximately 128 sequences, then plateaus

### BioLM Verification Results

| Test | Expected | Actual | Source | Status |
|------|----------|--------|--------|--------|
| Embedding dimension | 768 | 768 | Paper: "768 embedding size" | PASS |
| Number of layers | 12 | 12 | Paper: "12 layers" | PASS |
| Contact map symmetry | Symmetric | max_diff=1.49e-07 | APC correction produces symmetric maps | PASS |
| Proximity bias | Short > Long | Short=0.031, Long=0.006 | Expected from protein folding physics | PASS |
| Attention range | [0, 1] | [0.0009, 0.155] | Post-softmax values | PASS |
| Determinism | Identical runs | max_diff=0.0 | Seeded RNG | PASS |
| Covariation detection | >50th percentile | 89.4th percentile | Synthetic MSA with designed covariation | PASS |

7/7 verification tests passed.

### Comparison to Alternatives

| Model | Type | Key Advantage | Key Disadvantage |
|-------|------|---------------|------------------|
| **MSA Transformer (this)** | MSA-based protein LM | Captures evolutionary covariation; unsupervised contacts | Requires pre-computed MSA |
| ESM-2 | Single-sequence protein LM | No MSA needed; fast | Misses evolutionary covariation signal |
| ESM-1b | Single-sequence protein LM | Predecessor; still functional | Strictly worse than ESM-2 |
| AlphaFold2 | Structure prediction | Full 3D structure output | Much heavier; requires MSA + templates |

### Error Bars & Confidence

The model is deterministic when seeds are set (torch.manual_seed(42)). Contact maps are derived from attention weights via symmetrization and APC (Average Product Correction), which are deterministic operations.

Sources of variability:
- Different GPU architectures may produce floating-point differences within 1e-4
- Shallow MSAs (< 16 sequences) produce lower quality outputs

## Strengths & Limitations

### Pros

- Captures evolutionary covariation patterns that single-sequence models miss
- Unsupervised contact prediction from attention maps without separate training
- Relatively lightweight (100M parameters) compared to structure prediction models
- Rich output options: mean embeddings, per-token embeddings, row attentions, contacts
- Efficient tied row attention reduces memory complexity

### Cons

- Requires pre-computed MSA as input (does not perform sequence search)
- Performance degrades with very shallow MSAs (< 16 sequences)
- Not suitable for orphan proteins without detectable homologs
- Single-chain only -- no multi-chain or complex modeling
- Contact predictions are approximate (not a dedicated structure predictor)
- Max sequence length of 1,024 residues limits application to large proteins

### Known Failure Modes

- **Shallow MSAs** (< 16 sequences): Insufficient evolutionary signal leads to poor embeddings and unreliable contacts
- **Misaligned MSAs**: Sequences not properly aligned will produce incorrect attention patterns
- **Very long proteins** (> 1024 residues): Truncation removes C-terminal information
- **Orphan proteins**: Proteins without detectable homologs cannot leverage the MSA-based approach
- **Intrinsically disordered regions**: Contact predictions are unreliable for disordered regions

## Implementation Details

### Inference Pipeline

```
Request
  |-- 1. Validate MSA input:
  |     |-- All sequences same length
  |     |-- Characters in AA alphabet + gap (-) + insert (.)
  |     |-- Depth >= 2, <= 256
  |     |-- Length <= 1024
  |-- 2. Normalize repr_layers (convert negative to positive)
  |-- 3. For each MSA in batch:
  |     |-- Format as [(label, seq)] tuples
  |     |-- batch_converter -> tokens [1, M, L]
  |     |-- Forward pass on GPU:
  |     |     |-- need_head_weights if row_attention or contacts requested
  |     |     |-- return_contacts if contacts requested
  |     |-- Extract outputs per include options:
  |     |     |-- mean: query row representations averaged over positions
  |     |     |-- per_token: query row representations at each position
  |     |     |-- row_attention: tied row attention maps averaged over heads
  |     |     |-- contacts: symmetrized APC-corrected contact predictions
  |-- 4. Return MSATransformerEncodeResponse
```

### Memory & Compute Profile

| Property | Value |
|----------|-------|
| GPU | T4 (16 GB VRAM) |
| Memory | 16 GB system RAM |
| CPU | 4 cores |
| Timeout | 20 minutes |
| Model size on disk | ~400 MB |

Memory scales with MSA depth and sequence length. For deep MSAs (256 sequences) of long sequences (1024 residues), GPU memory usage approaches T4 limits.

### Determinism & Reproducibility

| Setting | Value |
|---------|-------|
| `torch.manual_seed` | 42 |
| `torch.cuda.manual_seed_all` | 42 |
| Model mode | eval() with torch.no_grad() |

All outputs are deterministic on the same hardware. Verified with max_diff=0.0 across repeated runs.

### Caching Behavior

- Response caching is handled outside the model container at the serving layer
- GPU memory snapshots enabled (`enable_memory_snapshot=True`, `enable_gpu_snapshot=True`)
- Cache key includes MSA sequences, params, and include options

## Versions & Changelog

| Version | Date | Changes |
|---------|------|---------|
| v1 | -- | Initial implementation with encode action supporting mean, per_token, row_attention, and contacts outputs |

---

*See also: [README.md](README.md) for API reference | [BIOLOGY.md](BIOLOGY.md) for biological context*
