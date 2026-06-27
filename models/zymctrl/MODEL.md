# ZymCTRL -- Technical Details

## Architecture

### Model Type & Innovation

ZymCTRL is a conditional protein language model based on GPT-2 (decoder-only autoregressive transformer) that generates enzyme sequences conditioned on Enzyme Commission (EC) numbers. The key innovation is the use of EC numbers as control tags prepended to enzyme sequences during training, enabling zero-shot generation of enzymes for any catalytic function without fine-tuning.

Unlike general-purpose protein language models (e.g., ESM2, ProtGPT2) that generate unconditional protein sequences, ZymCTRL ties generation to a functional specification (the EC number). This is achieved through character-level tokenization of EC numbers (e.g., "2.7.1.1" becomes ["2", ".", "7", ".", "1", ".", "1"]), which enables the model to learn hierarchical relationships between enzyme classes and transfer knowledge across related EC categories.

The model builds on ProtGPT2 (Ferruz et al., 2022) by adding the EC conditioning mechanism. Where ProtGPT2 generates proteins from a learned general distribution, ZymCTRL generates enzymes from an EC-conditioned distribution.

### Parameters & Layers

| Component | Details |
|-----------|---------|
| Architecture | GPT-2 Transformer (decoder-only, autoregressive) |
| Parameters | 738M |
| Layers | 36 |
| Hidden dimensions | 1280 |
| Vocabulary | Character-level amino acid + EC digit tokens + special tokens |
| Positional encoding | Learned absolute positional embeddings |
| Maximum sequence length | 1024 tokens (block size) |
| Special tokens | `<sep>`, `<start>`, `<end>`, `<\|endoftext\|>`, `<pad>` |

### Training Data

| Property | Details |
|----------|---------|
| Dataset | UniProt enzyme sequences with EC annotations |
| Size | 37 million enzyme sequences |
| Snapshot date | July 2022 |
| Filtering | Sequences with validated EC number annotations from UniProt |
| EC coverage | All four levels of the EC hierarchy |
| Training format | `<ec_number><sep><start><amino_acid_sequence><end><\|endoftext\|>` |

Known biases:
- EC classes with more representatives in UniProt will have better generation quality
- Broad-substrate EC classes (e.g., hexokinases EC 2.7.1.1) produce more heterogeneous outputs, reflecting the diversity in the training data
- Under-represented or recently created EC classes may produce lower-quality sequences

### Loss Function & Objective

Standard autoregressive language modeling: next-token prediction with cross-entropy loss across the full sequence (EC tokens + separator + amino acid tokens).

L = -sum over t of log P(x_t | x_{<t})

The model learns the joint distribution P(sequence | EC number) through teacher forcing on the concatenated EC + sequence format. At inference time, perplexity computed on the amino acid tokens only (excluding EC/control tokens) serves as a quality metric, with lower perplexity indicating sequences more consistent with the learned enzyme distribution.

### Tokenization / Input Processing

- **Tokenizer type**: Character-level (each amino acid and EC digit is a separate token)
- **Training format**: `<ec_number><sep><start><sequence><end><|endoftext|>`
- **Special tokens**:
  - `<sep>` -- separates EC number from sequence
  - `<start>` -- marks beginning of amino acid sequence
  - `<end>` -- marks end of amino acid sequence
  - `<|endoftext|>` -- standard GPT-2 end-of-text token
  - `<pad>` -- padding token (vocabulary ID 0)
- **Maximum length**: 1024 tokens (includes EC number, separators, and sequence)
- **EC number encoding**: Character-level (e.g., "3.5.5.1" tokenized as individual characters), enabling transfer learning across the EC hierarchy

## Performance & Benchmarks

### Published Benchmarks

#### Enzyme Generation Quality (Paper Figure 1b)

The paper evaluates generated sequences using perplexity as a proxy for quality, where lower perplexity indicates sequences more consistent with the natural enzyme distribution.

| EC Class | Name | Avg Perplexity | Quality |
|----------|------|----------------|---------|
| 2.7.1.2 | Glucokinase | ~1.1 | Excellent |
| 4.2.1.1 | Carbonic anhydrase | Variable (best ~1.2) | Good |
| 1.1.1.27 | Lactate dehydrogenase | ~2.3 | Good |

Key finding: Generated sequences average approximately 53% sequence identity to natural proteins, indicating the model produces genuinely novel sequences rather than memorizing training data.

#### Experimental Validation (Paper Figures 3-4)

- **Carbonic anhydrase (EC 4.2.1.1)**: Generated enzymes were experimentally validated, confirming catalytic activity
- **Lactate dehydrogenase (EC 1.1.1.27)**: Fine-tuning on this EC class improved generation quality

### BioLM Verification Results

| Test Case | Expected | BioLM Result | Status |
|-----------|----------|--------------|--------|
| Glucokinase (2.7.1.2) perplexity | LOW (<1.5) | 1.11 avg, 1.06 min | PASS |
| LDH (1.1.1.27) perplexity | LOW | 2.28 avg, 1.95 min | PASS |
| Carbonic anhydrase (4.2.1.1) perplexity | LOW | 3.05 avg, 1.17 min | PASS |
| Implausible EC (9.9.9.9) perplexity | HIGH | 8.92 avg, 8.46 min | PASS |
| Partial EC (1.1) perplexity | MEDIUM | 5.15 avg, 2.80 min | PASS |

Valid ECs produce average perplexity of 2.15 vs 8.92 for implausible ECs (4.1x difference), confirming the model differentiates between valid and random EC labels.

### Comparison to Alternatives

| Model | Task | Conditioning | When to Prefer |
|-------|------|-------------|----------------|
| **ZymCTRL** | Enzyme generation | EC number | Need enzymes for specific catalytic function |
| ProtGPT2 | General protein generation | None (unconditional) | Need general proteins, not necessarily enzymes |
| ESM2 | Embeddings / scoring | None | Need variant effect prediction, not generation |
| ProGen2 | Protein generation | Taxonomy + function tags | Need broader conditioning beyond EC numbers |

### Error Bars & Confidence

ZymCTRL generation is stochastic. Key variance characteristics:

- **Perplexity variance**: Within an EC class, generated sequences show a range of perplexities. Well-represented classes (e.g., glucokinase) show tighter distributions; under-represented classes show wider variance.
- **Recommended workflow**: Generate 100-1000 sequences, rank by perplexity, select top 5% (perplexity < 1.75 threshold).
- **Seed control**: The implementation supports explicit seeds for reproducibility. Without a seed, time-based entropy is used for diversity.

## Strengths & Limitations

### Pros

- Zero-shot enzyme generation for any EC class without fine-tuning
- EC number conditioning enables targeted catalytic function design
- Character-level EC tokenization enables transfer learning across enzyme hierarchy
- Perplexity provides a built-in quality metric for ranking generated sequences
- Experimentally validated: generated carbonic anhydrases showed catalytic activity
- Produces genuinely novel sequences (~53% identity to natural proteins)
- Embedding extraction (encode action) enables downstream enzyme similarity analysis

### Cons

- Sequence-only model: no structural awareness or binding site specificity
- No substrate specificity control within an EC class (e.g., cannot specify which sugar a kinase should phosphorylate)
- Broad-substrate EC classes produce heterogeneous outputs
- Maximum 1024 tokens limits generation of very long enzymes
- Perplexity is a proxy for quality, not a direct measure of catalytic activity
- Requires post-generation filtering and experimental validation

### Known Failure Modes

- **Non-existent EC numbers** (e.g., 9.9.9.9): Model generates sequences but with very high perplexity (>8), indicating poor quality. The model does not reject invalid EC numbers.
- **Partial EC numbers** (e.g., "1.1" instead of "1.1.1.1"): Generates sequences but with higher uncertainty (perplexity ~5), since the model was trained predominantly on full 4-level EC numbers.
- **Under-represented EC classes**: EC categories with few training examples produce lower-quality sequences with higher perplexity variance.
- **Repetition**: Without sufficient repetition penalty, the model can fall into repetitive amino acid patterns.

## Implementation Details

### Inference Pipeline

#### Generate Action

```
Request (EC number + generation params)
  |-- 1. Validate EC number format (X.X.X.X or partial)
  |-- 2. Set random seeds (user-provided or time-based)
  |-- 3. Build prompt: "<ec_number><sep><start>"
  |-- 4. Tokenize prompt
  |-- 5. [GPU] Autoregressive generation (top-k sampling)
  |     |-- temperature, top_k, repetition_penalty control
  |     |-- Generate up to max_length tokens per sample
  |     |-- num_samples independent generations
  |-- 6. For each sample:
  |     |-- Calculate perplexity on amino acid tokens only
  |     |-- Decode and remove special tokens
  |-- 7. Sort by perplexity (ascending)
  |-- 8. Return sorted results
```

#### Encode Action

```
Request (sequence + optional EC number + pooling params)
  |-- 1. Validate amino acid sequence
  |-- 2. Format with training tokens:
  |     |-- With EC: "<ec><sep><start><sequence><end>"
  |     |-- Without EC: "<start><sequence><end>"
  |-- 3. Tokenize with padding and attention mask
  |-- 4. [GPU] Forward pass with output_hidden_states=True
  |-- 5. Extract hidden states from specified layer (default: last)
  |-- 6. Pool embeddings:
  |     |-- mean: average over non-padding positions
  |     |-- last: final non-padding token
  |     |-- per_token: all non-padding token embeddings
  |-- 7. Return embeddings
```

### Memory & Compute Profile

| Configuration | GPU | Memory | Notes |
|---------------|-----|--------|-------|
| Model weights | T4 (16GB) | ~3 GB VRAM | 738M params in FP32 |
| Generation (1 sample, 256 tokens) | T4 | ~4 GB VRAM | Sequential autoregressive |
| Generation (20 samples, 1024 tokens) | T4 | ~6 GB VRAM | Max batch |
| Encoding (8 sequences, mean pooling) | T4 | ~5 GB VRAM | Max encode batch |

Resource allocation: 2 CPU cores, 16 GB system RAM, T4 GPU, 10-minute timeout.

### Determinism & Reproducibility

| Setting | Value |
|---------|-------|
| Torch manual seed | Yes (user-provided or time-based) |
| CUDA manual seed | Yes (`torch.cuda.manual_seed_all`) |
| NumPy seed | Yes |
| Python random seed | Yes |
| cuDNN deterministic | Not explicitly set |
| cuDNN benchmark | Not explicitly set |

- **Generate action**: Stochastic by design (sampling-based). Reproducible with explicit `seed` parameter.
- **Encode action**: Deterministic for the same input (no sampling involved).

### Caching Behavior

- **Redis (Modal Dict) caching**: Handled by BillingMixinSnap framework
- **R2 caching**: Standard BioLM two-tier caching
- **Cache key**: Based on full request payload (EC number, params, sequence)
- **Generate action**: Caching is less useful due to stochastic outputs (same EC + different seed = different results)
- **Encode action**: Caching is effective since outputs are deterministic

## Training Procedures

Training was performed by the original authors (AI4PD group) and is not reproducible within BioLM.

| Hyperparameter | Value |
|----------------|-------|
| Base model | GPT-2 architecture (trained from scratch) |
| Hardware | 48 NVIDIA A100 GPUs |
| Training time | ~15,000 GPU hours |
| Training data | 37M enzyme sequences from UniProt (July 2022) |
| Block size | 1024 tokens |
| Objective | Autoregressive language modeling (next-token prediction) |

## Versions & Changelog

| Version | Date | Changes |
|---------|------|---------|
| v1 | 2024-12 | Initial implementation with generate and encode actions |

---

*See also: [README.md](README.md) for API reference | [BIOLOGY.md](BIOLOGY.md) for biological context*
