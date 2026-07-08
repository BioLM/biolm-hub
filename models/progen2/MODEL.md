# ProGen2 -- Technical Details

## Architecture

### Model Type & Innovation

ProGen2 is an autoregressive protein language model based on the GPT-J architecture (decoder-only transformer). It is trained with a standard causal language modeling (next-token prediction) objective on large protein sequence databases, learning to generate protein sequences one amino acid at a time.

The key innovation of ProGen2 over its predecessor ProGen is systematic scaling. The authors trained models from ~151M to ~6.4B parameters across different protein datasets and demonstrated that larger models produce more realistic protein sequences and better fitness predictions. ProGen2 also introduced training on multiple dataset compositions (UniRef90, BFD90, and the OAS antibody database), allowing specialized variants for different protein families.

ProGen2 uses a GPT-J-style transformer decoder with rotary position embeddings (RoPE), GELU activation, and pre-layer normalization. The architecture supports autoregressive sampling with nucleus (top-p) filtering and temperature control for controllable protein generation.

### Parameters & Layers

| Variant | Parameters | Layers | Attention Heads | Rotary Dim | Hidden Dim | Context Length |
|---------|-----------|--------|-----------------|------------|------------|----------------|
| progen2-oas | 151M | 12 | 16 | 64 | 1280 | 2048 |
| progen2-medium | 764M | 27 | 16 | 96 | 2560 | 2048 |
| progen2-large | 2.7B | 32 | 32 | 80 | 4096 | 2048 |
| progen2-bfd90 | 2.7B | 32 | 32 | 80 | 4096 | 2048 |

Parameter counts and layer/head configurations are confirmed from paper Table 1 (Nijkamp et al., 2023). The paper also describes PROGEN2-small (151M, same architecture as OAS), PROGEN2-base (764M, same as medium but with 2048 context), and PROGEN2-xlarge (6.4B, 32 layers, 16 heads, head dim 256) which are not included in this catalog. The BioLM OAS variant uses a 2048 context length (matching PROGEN2-base) rather than the paper's 1024 for PROGEN2-small.

Common across all variants:

| Property | Value |
|----------|-------|
| Vocabulary size | 32 tokens (ProGen2 custom amino-acid tokenizer) |
| Positional encoding | Rotary (RoPE), dim varies by variant (64/96/80) |
| Normalization | Pre-LayerNorm |
| Activation | GELU (gelu_new) |
| Context length | 2048 tokens |

### Training Data

ProGen2 variants are trained on different protein sequence databases:

| Variant | Dataset | Size | Description |
|---------|---------|------|-------------|
| progen2-oas | OAS (Observed Antibody Space) | 554M sequences (after 85% identity clustering) | Unpaired antibody sequences from 80 immune repertoire sequencing studies, covering heavy and light chains from 6 species (human, mouse, rat, camel, rabbit, rhesus). Clustered at 85% identity using Linclust to reduce redundancy from the original 1.5B sequences. |
| progen2-medium | UniRef90 + BFD30 | UniRef90 cluster representatives + BFD30 (~1/3 size of UniRef90) | UniRef90 are cluster representative sequences from UniProtKB at 90% sequence identity. BFD30 is the Big Fantastic Database clustered at 30% identity, majority from metagenomic sources. |
| progen2-large | UniRef90 + BFD30 | Same as medium | Same training data as medium, with larger model capacity (2.7B vs 764M parameters). |
| progen2-bfd90 | UniRef90 + BFD90 | BFD90 (~2x size of UniRef90) | UniRef90 mixed with BFD90: representative sequences with at least 3 cluster members after clustering UniProtKB, Metaclust, SRC, and MERC at 90% identity. |

Training data details confirmed from Nijkamp et al. (2023), Section 3.2. All sequences are provided with N-terminal (`1`) and C-terminal (`2`) tokens, and each sequence is included in both forward and reverse orientations during training.

Known biases in the training data:
- OAS variant is specialized for antibodies and will underperform on non-antibody proteins
- BFD90 has strong bias toward bacterial and metagenomic proteins
- All variants under-represent eukaryotic membrane proteins relative to their biological importance
- Training data lacks non-natural amino acids and post-translational modifications

### Loss Function & Objective

Standard autoregressive language modeling with cross-entropy loss:

```
L = -Sum_i log P(x_i | x_1, ..., x_{i-1})
```

Each token is predicted conditioned on all previous tokens. No masking strategy is used -- this is purely left-to-right next-token prediction.

ProGen2 uses special terminal tokens: `1` for N-terminal (beginning of protein) and `2` for C-terminal (end of protein). During training, sequences are formatted as `1{sequence}2`.

### Tokenization / Input Processing

| Property | Details |
|----------|---------|
| Tokenizer | ProGen2 custom tokenizer (32 tokens: 20 standard amino acids + special/terminal tokens) |
| Special tokens | `1` (N-terminal/BOS), `2` (C-terminal/EOS), `<\|pad\|>` (padding) |
| N-terminal prepended | Yes (token `1`) |
| C-terminal appended | Yes (token `2`, for likelihood computation) |
| Maximum sequence length | 512 residues (BioLM implementation limit) |

The implementation prepends the `1` N-terminal token to the context sequence before sampling. For likelihood computation, both `1` (N-terminal) and `2` (C-terminal) tokens are added to frame the full sequence. The tokenizer is character-level for amino acids -- each standard amino acid maps to a single token.

## Performance & Benchmarks

### Published Benchmarks

#### Protein Fitness Prediction

ProGen2 log-likelihoods correlate with experimentally measured protein fitness:

#### Narrow Fitness Landscapes (Paper Table 3)

Zero-shot fitness prediction on narrow experimentally-measured fitness landscapes (primarily single-substitution DMS experiments). Average Spearman rho reported with baselines from Hesslow et al. (2022):

| Model | Avg Spearman rho | Notes |
|-------|-----------------|-------|
| **PROGEN2-small (151M)** | **0.456** | Outperforms much larger RITA-XL |
| **PROGEN2-base (764M)** | **0.505** | Best single PROGEN2 model on narrow landscapes |
| **PROGEN2-large (2.7B)** | **0.485** | Larger capacity does not always improve fitness prediction |
| **PROGEN2-xlarge (6.4B)** | **0.476** | Performance decreases with further scaling |
| **PROGEN2-ensemble** | **0.518** | Best overall ProGen2 result |
| RITA-XL | 0.443 | Order of magnitude larger than PROGEN2-small |
| EVE | 0.511 | Family-specific VAE |
| Tranception (no retrieval) | 0.447 | Autoregressive |
| Tranception (retrieval) | 0.503 | Autoregressive with MSA retrieval |
| MSA Transformer | 0.476 | Requires MSA input |
| ESM-1v (single) | 0.475 | Masked LM, single model |

Key finding: performance peaks at 764M parameters (PROGEN2-base) for narrow fitness landscapes, then decreases with scale -- likely because smaller models project the data distribution onto a model class closer to the true fitness landscape.

#### Wide Fitness Landscapes (Paper Table 4)

Zero-shot fitness prediction on wider experimental landscapes with higher edit distances:

| Dataset [Metric] | PROGEN2-small | PROGEN2-base | PROGEN2-large | PROGEN2-xlarge |
|-------------------|--------------|-------------|--------------|---------------|
| AAV [AUC] | 0.59 | 0.62 | 0.65 | 0.68 |
| GFP [AUC] | 0.51 | 0.64 | 0.84 | 0.84 |
| CM [AUC] | 0.68 | 0.72 | 0.66 | 0.64 |
| GB1 [top100avg] | 0.01 | 0.01 | 0.24 | 0.85 |

For wider landscapes, larger models show clear advantages, particularly for the GB1 low-homology epistatic landscape where the 6.4B model may exhibit emergent behavior.

#### Antibody-Specific Landscapes (Paper Table 5)

| Property | PROGEN2-small | PROGEN2-base | PROGEN2-large | PROGEN2-xlarge | PROGEN2-OAS |
|----------|--------------|-------------|--------------|---------------|-------------|
| Binding [avg rho] | 0.44 | 0.41 | 0.42 | 0.40 | 0.37 |
| General [avg rho] | 0.61 | 0.73 | 0.73 | 0.74 | 0.66 |

Notably, the OAS-trained model underperforms universal models on antibody fitness prediction, suggesting that redundancy-reduced immune repertoire sequences alone do not lead to better fitness prediction for antibodies.

#### Scaling Laws

Perplexity on held-out test sequences (paper Table 2). Lower perplexity indicates the model better captures the distribution of observed evolutionary sequences:

| Model | Parameters | Test-max90 (ppl) | Test-max50 (ppl) |
|-------|-----------|-----------------|-----------------|
| PROGEN2-small | 151M | 12.9 | 15.0 |
| PROGEN2-medium | 764M | 11.2 | 14.3 |
| PROGEN2-large | 2.7B | 11.1 | 14.4 |
| PROGEN2-xlarge | 6.4B | 9.9 | 13.9 |

Test-max90 and Test-max50 correspond to held-out clusters at 90% and 50% sequence identity respectively. Test-max50 is a harder, more out-of-distribution evaluation. Perplexity decreases consistently with model scale, confirming scaling laws hold for protein language models.

### BioLM Verification Results

The BioLM implementation uses official pre-trained weights from the Salesforce ProGen repository. Verification is performed using a custom validator that checks:

| Check | Criterion | Status |
|-------|-----------|--------|
| Sequence count | num_samples matches requested | PASS |
| Context preservation | Generated sequences start with input context | PASS |
| Length constraint | Generated sequences do not exceed max_length | PASS |

### Comparison to Alternatives

| Model | Type | Key Advantage | Key Disadvantage |
|-------|------|---------------|------------------|
| **ProGen2 (this)** | Autoregressive LM | True sequence generation with controllable sampling | No bidirectional context; fitness prediction less accurate than MLM models |
| ESM-2 | Masked LM | Better embeddings and fitness prediction | Cannot generate sequences |
| ProtGPT2 | Autoregressive LM | Simpler architecture | Smaller model, less diverse training data |
| ProGen (v1) | Conditional generation | Controllable generation with taxonomy tags | Superseded by ProGen2 |
| EvoDiff | Diffusion-based | Non-autoregressive generation | Slower sampling, newer/less benchmarked |

### Error Bars & Confidence

ProGen2 is inherently stochastic -- sampling uses temperature and top-p nucleus filtering, producing different outputs on each call (unless a fixed seed is provided). The log-likelihood scores (ll_sum, ll_mean) are deterministic for a given sequence and model.

Sources of variability:
- **Sampling**: Different random seeds produce different generated sequences. Typical diversity across samples is high -- sequences may share only the context prefix.
- **Likelihood averaging**: The implementation averages forward (left-to-right) and reverse (right-to-left) log-likelihoods to reduce directional bias. This bidirectional averaging is a deliberate design choice from the original code.
- **GPU precision**: Small numerical differences in likelihoods may occur across GPU architectures.

## Strengths & Limitations

### Pros

- True protein sequence generation -- can design novel proteins from scratch or extend existing sequences
- Multiple training data variants allow specialization (antibodies via OAS, general proteins via BFD90)
- Controllable generation via temperature, top-p, and seed parameters
- Log-likelihood scoring enables fitness prediction and sequence ranking
- Bidirectional likelihood averaging (forward + reverse) reduces positional bias
- BSD-3-Clause license allows commercial use

### Cons

- Autoregressive generation is inherently sequential -- no parallel token generation
- Fitness prediction accuracy is generally below masked language models (ESM-2) on standard benchmarks
- No structural awareness -- generated sequences may not fold into stable structures
- Maximum 512 residues in BioLM implementation (model supports 2048 but capped for safety)
- Batch size limited to 1 item per request
- OAS variant is narrowly specialized; other variants may underperform on antibodies

### Known Failure Modes

- **Very short contexts** (< 5 residues): Generation may produce highly diverse and potentially non-biological sequences due to insufficient conditioning
- **Very low temperature** (approaching 0.0): Schema requires temperature > 0.0; near-zero values can produce repetitive sequences (poly-amino acid tracts)
- **High temperature** (> 2.0): Generated sequences become increasingly random and biologically implausible
- **Context outside training distribution**: Sequences with non-standard amino acids or unusual compositions may produce poor completions
- **Long generation lengths**: Quality degrades as generated length increases beyond ~200-300 residues, especially without a strong context signal

## Implementation Details

### Inference Pipeline

```
Request
  |-- 1. Validate sequences (AA alphabet, length, batch size)
  |-- 2. Set random seeds (user-provided or time-based entropy)
  |-- 3. Prepend N-terminal token "1" to context
  |-- 4. Autoregressive sampling on GPU
  |     |-- Tokenize context with the ProGen2 custom amino-acid tokenizer
  |     |-- model.generate() with temperature + top-p
  |     |-- Decode token IDs back to amino acid sequences
  |-- 5. Truncate at terminal tokens ("1" or "2")
  |-- 6. Strip terminal tokens from generated sequences
  |-- 7. Compute bidirectional log-likelihoods
  |     |-- Forward: log P(1{seq}2)
  |     |-- Reverse: log P(reversed(1{seq}2))
  |     |-- Average: 0.5 * (forward + reverse)
  |-- 8. Return ProGen2GenerateResponse with sequences + likelihoods
```

### Memory & Compute Profile

| Variant | GPU | GPU Memory (approx) | Inference Time (128 tokens) |
|---------|-----|--------------------|-----------------------------|
| oas | None (CPU) | CPU only, ~2 GB RAM | ~2-5s |
| medium | T4 | ~4 GB VRAM | ~1-3s |
| large | T4 | ~10 GB VRAM | ~3-8s |
| bfd90 | T4 | ~10 GB VRAM | ~3-8s |


Autoregressive generation scales linearly with output length (O(n) forward passes, each O(n) with KV-cache).

### Determinism & Reproducibility

| Setting | Value |
|---------|-------|
| `torch.manual_seed` | User seed or `time.time_ns() % 2^32` |
| `torch.cuda.manual_seed_all` | Same as above |
| `numpy.random.seed` | Same as above |
| `random.seed` | Same as above |
| cuDNN deterministic | Not explicitly set |
| cuDNN benchmark | Not explicitly disabled |

The model produces reproducible outputs when the same seed is provided. Without a seed, each call produces different sequences using time-based entropy.

### Caching Behavior

Response caching is handled outside the model container by the serving infrastructure:
- **Cache key**: Determined by the request payload (context, params, model variant)
- **Note**: Due to stochastic generation, caching is most useful when seeds are fixed. Without a seed, identical requests will return cached results from the first call rather than fresh samples.

## Versions & Changelog

| Version | Date | Changes |
|---------|------|---------|
| v1 | 2025-01-15 | Initial implementation with generate action for oas, medium, large, bfd90 variants |
| v1 (updated) | 2026-03-14 | Migrated to declarative download system and source layer setup |

---

*See also: [README.md](README.md) for API reference | [BIOLOGY.md](BIOLOGY.md) for biological context*
