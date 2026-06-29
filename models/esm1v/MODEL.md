# ESM1v -- Technical Details

## Architecture

### Model Type & Innovation

ESM1v is a protein language model from Meta AI (Meier et al. 2021) specifically designed for zero-shot prediction of the effects of mutations on protein function. The key innovation is training an ensemble of five independently initialized ESM-1b-scale models on UniRef90, then using the masked marginal probability at mutation sites to predict functional effects without any task-specific fine-tuning.

The model uses a standard Transformer encoder (BERT-style) architecture with masked language modeling (MLM). For variant effect prediction, the target residue position is masked, and the model predicts the probability distribution over all 20 amino acids at that position. The log-likelihood ratio between the mutant and wild-type amino acid serves as a zero-shot fitness score.

### Parameters & Layers

| Component | Details |
|-----------|---------|
| Architecture | Transformer encoder (BERT-style) |
| Parameters per model | 650M |
| Ensemble size | 5 models (n1--n5), each independently initialized |
| Layers | 33 Transformer layers |
| Training objective | Masked Language Modeling (MLM) |
| Input | Protein sequence with `<mask>` token at position of interest |
| Output | Per-position amino acid probabilities over 20 standard amino acids |

### Training Data

| Property | Details |
|----------|---------|
| Training dataset | UniRef90 (UR90) |
| Dataset size | ~98M unique protein sequences |
| Training approach | Standard MLM with 15% masking rate |
| Ensemble strategy | 5 independent training runs with different random seeds |

### Loss Function & Objective

ESM1v is trained with standard Masked Language Modeling (MLM) cross-entropy loss:

```
L = -sum_i log P(aa_i | context_with_mask_at_i)
```

For variant effect prediction at inference time, the model masks the target position and computes the log-likelihood of each possible amino acid at that position. The score for a mutation X->Y at position i is:

```
score(X->Y, i) = log P(Y | context_masked_at_i) - log P(X | context_masked_at_i)
```

### Tokenization / Input Processing

- **Input format**: Amino acid sequence string with exactly one `<mask>` token at the position of interest
- **Validation**: Extended amino acid alphabet plus `<mask>` special token
- **Single mask requirement**: Exactly one `<mask>` token must be present in each sequence
- **Maximum length**: 1022 residues (1024 tokens - 2 for BOS/EOS; matches ESM-1b's architectural limit)
- **Tokenization**: Uses the ESM tokenizer from HuggingFace Transformers (`EsmTokenizer`)
- **Inference**: HuggingFace `fill-mask` pipeline, filtered to 20 standard amino acids only

## Performance & Benchmarks

### Published Benchmarks

From Meier et al., *NeurIPS* (2021):

| Model | Spearman rho (DMS average) ↑ | Method |
|-------|----------------------------|--------|
| **ESM1v (5-model avg)** | **0.47** | Zero-shot (no task-specific training) |
| ESM-1b | 0.43 | Zero-shot |
| EVmutation | 0.42 | MSA-based (requires alignment) |
| DeepSequence | 0.41 | VAE, MSA-based |
| Random | 0.00 | Baseline |

Evaluated across 41 deep mutational scanning (DMS) datasets.

### BioLM Verification Results

| Variant | Action | Tolerance | Status |
|---------|--------|-----------|--------|
| n1 | predict | rel_tol 1e-4 | PASS |
| n2 | predict | rel_tol 1e-4 | PASS |
| n3 | predict | rel_tol 1e-4 | PASS |
| n4 | predict | rel_tol 1e-4 | PASS |
| n5 | predict | rel_tol 1e-4 | PASS |
| all | predict | rel_tol 1e-4 | PASS |

### Comparison to Alternatives

| Model | Strength | When to prefer |
|-------|----------|----------------|
| **ESM1v** | Zero-shot variant effect prediction, ensemble | Single-site mutation effect prediction |
| ESM2 | Newer architecture, embeddings, multiple sizes | General protein representation, embeddings |
| ESMC | Latest generation, better embeddings | General protein tasks, embeddings |
| GEMME | Evolutionary coupling-based | When MSA is available and relevant |
| PoET | Generative model, MSA-conditioned | When MSA-conditioned scoring is desired |

## Strengths & Limitations

### Pros

- Zero-shot variant effect prediction without any task-specific training data
- Ensemble of 5 models reduces prediction variance
- "all" variant loads all 5 models for ensemble predictions in a single request
- Individual models (n1--n5) available for faster single-model inference
- Well-validated across 41 DMS datasets

### Cons

- Limited to single-site mutations (one `<mask>` per sequence)
- Maximum sequence length of 1022 residues
- Does not capture epistatic effects between multiple mutations
- CPU-based inference for individual models (GPU only for "all" variant)
- Returns probabilities at masked positions, not directly interpretable absolute fitness scores

### Known Failure Modes

- Sequences near or exceeding 1022 residues may be truncated
- Multi-site mutations require separate queries per position
- Proteins with few homologs in UniRef90 may have less reliable predictions
- Active site residues under strong functional selection may not be well-predicted by sequence-only models

## Implementation Details

### Inference Pipeline

```
Request
  |-- 1. Validate sequence (extended AA + <mask>, exactly one mask)
  |-- 2. For each model in pipeline:
  |     |-- 2a. Run HuggingFace fill-mask pipeline
  |     |-- 2b. Filter to 20 standard amino acids
  |     |-- 2c. Sort by score (descending)
  |-- 3a. [individual variant] Return sorted predictions
  |-- 3b. [all variant] Return dict mapping each model to its predictions
```

### Memory & Compute Profile

| Resource | Individual (n1--n5) | All |
|----------|-------------------|-----|
| GPU | None (CPU-only) | T4 |
| Memory | 8 GB RAM | 28 GB RAM |
| CPU | 2.0 cores | 4.0 cores |
| Models loaded | 1 | 5 |

### Determinism & Reproducibility

| Setting | Value |
|---------|-------|
| Torch manual seed | Yes (42 at model load) |
| CUDA manual seed | Yes (42, if available) |
| Deterministic outputs | Yes (predict is deterministic given same input) |

### Caching Behavior

Model weights are cached in R2 and loaded from the container image snapshot on warm starts. Response-level caching is not performed in the model container; operators may layer a cache in front of the endpoint if desired.

## Versions & Changelog

| Version | Date | Changes |
|---------|------|---------|
| v1 | 2024 | Initial implementation with predict action, all 6 variants |

---

*See also: [README.md](README.md) for API reference | [BIOLOGY.md](BIOLOGY.md) for biological context*
