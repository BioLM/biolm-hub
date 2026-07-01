# {Model Display Name}  --  Technical Details

<!-- Template instructions (delete this block when populating):
     This document provides a deep technical dive into the model's architecture,
     training, and performance. It complements README.md (API-focused) and
     BIOLOGY.md (biology-focused).

     TODO format (use consistently across all docs):
       <!-- TODO: [Action to take]  --  [Where to find the info] -->

     Primary sources: Use sources.yaml primary_papers and source_repos.
     Access paper content via:
       bm r2 cat r2://biolm-public/knowledge-base/models/{slug}/primary/papers-md/{paper}.md
     Or download locally:
       bm r2 download r2://biolm-public/knowledge-base/models/{slug}/ /tmp/kb/{slug}/

     Sections marked [OPTIONAL] should be INCLUDED if relevant and REMOVED
     (not left empty) if not applicable.
-->

## Architecture

### Model Type & Innovation

<!-- What kind of model is this? What is novel about it compared to prior work?
     Examples:
     - "Masked language model (BERT-style) trained on protein sequences"
     - "Diffusion-based generative model for 3D structure prediction"
     - "Graph neural network for inverse folding"

     Describe the key architectural innovation that distinguishes this model:
     - What problem does the architecture solve?
     - How does it differ from predecessors?
     - What are the key components? (e.g., Evoformer, Structure Module, etc.)
-->

### Parameters & Layers

<!-- Detailed architecture specifications.

     | Component | Details |
     |-----------|---------|
     | Architecture | e.g., Transformer encoder, 33 layers |
     | Parameters | e.g., 650M total (trainable: 648M) |
     | Hidden dimensions | e.g., 1280 |
     | Attention heads | e.g., 20 |
     | Feed-forward dimensions | e.g., 5120 |
     | Embedding dimensions | e.g., 1280 |
     | Vocabulary size | e.g., 33 tokens (20 AA + special tokens) |
     | Positional encoding | e.g., Rotary (RoPE) / Learned / Sinusoidal |
     | Normalization | e.g., Pre-LayerNorm / Post-LayerNorm |
     | Activation | e.g., GELU / SwiGLU / ReLU |

     For multi-variant models, show a comparison table across sizes.
-->

### Training Data

<!-- What data was the model trained on?

     | Property | Details |
     |----------|---------|
     | Dataset | e.g., UniRef50, BFD, PDB |
     | Size | e.g., 65M sequences, 15B residues |
     | Filtering | e.g., 50% sequence identity clustering |
     | Composition | e.g., 80% bacterial, 15% eukaryotic, 5% archaeal |
     | Temporal cutoff | e.g., Structures deposited before 2021-09-30 |
     | Negative sampling | e.g., Decoy structures from AlphaFold DB |

     Note any known biases in the training data:
     - Over/under-representation of certain organisms or protein families
     - Missing molecule types (e.g., no membrane proteins)
     - Data quality issues (e.g., low-resolution structures included)
-->

### Loss Function & Objective

<!-- What objective was the model trained with?

     Examples:
     - Masked language modeling (MLM): 15% random masking, cross-entropy loss
     - Denoising diffusion: noise schedule σ ∈ [0.01, 80], L2 reconstruction
     - Contrastive learning: InfoNCE loss with temperature τ=0.07
     - Multi-task: structure loss + auxiliary losses (distogram, masked token)

     Include mathematical formulation if it aids understanding:
     L = -Σ log P(x_masked | x_visible)
-->

### Tokenization / Input Processing

<!-- How are inputs preprocessed before entering the model?

     - Tokenizer type: character-level, BPE, SentencePiece, k-mer
     - Special tokens: [CLS], [EOS], [PAD], [MASK], [UNK]
     - Maximum sequence length and handling of longer sequences
     - Multi-chain handling (if applicable): concatenation, cross-attention
     - MSA processing (if applicable): depth, subsampling strategy
     - Structure input (if applicable): coordinate system, atom selection

     For models with unusual input processing (e.g., Evo's byte-level DNA
     tokenization), explain the rationale.
-->

## Performance & Benchmarks

### Published Benchmarks

<!-- Results directly from the model's paper.
     Separate by benchmark/task.

     #### Benchmark Name (e.g., CASP15, ProteinGym)

     | Model | Metric1 ↑ | Metric2 ↓ | Notes |
     |-------|-----------|-----------|-------|
     | **This Model** | **0.94** | **3.42** | - |
     | Baseline 1 | 0.81 | 3.62 | Prior SOTA |
     | Baseline 2 | 0.75 | 4.10 | - |

     Include:
     - Dataset size (n=)
     - Statistical significance / error bars (if reported)
     - Conditions (e.g., "single-sequence mode" vs "MSA mode")
-->

### BioLM Verification Results

<!-- Results from our own testing of the BioLM implementation.
     Should match or closely approximate published results.

     | Metric | Published | BioLM | Difference | Status |
     |--------|-----------|-------|------------|--------|
     | Accuracy | 0.94 | 0.93 | -0.01 | PASS |

     If results differ significantly, explain why (e.g., different
     preprocessing, floating point precision, library version differences).
-->

### Comparison to Alternatives

<!-- How does this model compare to alternatives available on the BioLM platform?

     | Model | Task | Metric | Value | When to prefer |
     |-------|------|--------|-------|----------------|
     | **This Model** | Embedding | Spearman ρ | 0.68 | General proteins |
     | ESM2-650M | Embedding | Spearman ρ | 0.65 | Faster inference |
     | SaProt | Embedding | Spearman ρ | 0.72 | When structure available |

     This helps users choose between models on the platform.
-->

### [OPTIONAL] Error Bars & Confidence

<!-- Include if the model provides uncertainty estimates, cross-validation variance,
     or has stochastic outputs. Omit for deterministic models with no uncertainty
     quantification.

     Quantify the uncertainty in the model's predictions.

     - Standard deviation across random seeds
     - Confidence intervals from cross-validation
     - Known failure modes and their frequency
     - How confidence varies with input characteristics
       (e.g., sequence length, similarity to training data)
-->

## Strengths & Limitations

### Pros

<!-- Bullet list of the model's key advantages:
     - Speed, accuracy, generalization, etc.
     - Unique capabilities not available in alternatives
     - Robustness properties (e.g., "tolerates gaps in MSA")
-->

### Cons

<!-- Bullet list of known weaknesses:
     - Accuracy limitations on specific subtasks
     - Computational cost relative to simpler alternatives
     - Known biases from training data
-->

### Known Failure Modes

<!-- Specific scenarios where the model fails or produces unreliable results:
     - Input types that cause silent failures (e.g., all-glycine sequences)
     - Edge cases in sequence length, composition, or domain
     - Numerical instability conditions
     - Out-of-distribution detection (or lack thereof)
-->

## Implementation Details

### Inference Pipeline

<!-- Step-by-step description of how a request is processed.
     For complex models, include an ASCII flowchart:

     ```
     Request → Validate → Tokenize → [GPU] Forward Pass → Post-process → Response
                                          ↓
                                    Confidence scores
     ```

     For multi-step pipelines (e.g., MSA search → embedding → prediction):

     ```
     Request
       ├── 1. Validate input sequences
       ├── 2. Tokenize with {tokenizer}
       ├── 3. Forward pass on {GPU}
       │     ├── Encoder: 33 transformer layers
       │     └── Output: per-token embeddings (N × 1280)
       ├── 4. Pool embeddings (mean over sequence)
       ├── 5. Apply prediction head
       └── 6. Format response
     ```
-->

### Memory & Compute Profile

<!-- Resource usage characteristics:

     | Input Size | GPU Memory | Inference Time | Batch Size |
     |------------|------------|----------------|------------|
     | 100 residues | 2.1 GB | 45ms | 32 |
     | 500 residues | 4.8 GB | 180ms | 8 |
     | 1000 residues | 12.3 GB | 520ms | 2 |

     Note any non-linear scaling behaviors (e.g., attention is O(n²)).
-->

### Determinism & Reproducibility

<!-- Is the model deterministic? What seeds are set?

     - Torch manual seed: Yes/No
     - CUDA manual seed: Yes/No
     - NumPy seed: Yes/No
     - cuDNN deterministic: Yes/No
     - cuDNN benchmark: Disabled/Enabled

     If stochastic, describe the source of non-determinism and its magnitude.
-->

### Caching Behavior

<!-- How does caching work for this model?

     Response caching is provided by the commons two-tier cache (an in-container
     modal.Dict backed by R2 object storage). It is opt-in and off by default,
     toggled via the BIOLM_CACHE_ENABLED environment variable.

     - Cache enabled: Yes/No (and under which BIOLM_CACHE_ENABLED setting)
     - Cache key composition: What inputs determine the cache key?
     - Cache invalidation: When are cached results invalidated?
-->

## [OPTIONAL] Training Procedures

<!-- Include this section ONLY when:
     (a) The model has a reproducible training pipeline within BioLM (e.g., _train.py), OR
     (b) The paper provides specific hyperparameters not covered in the Training Data subsection.
     Do NOT include if training is entirely upstream and only dataset composition is documented.

     ### Training Configuration

     | Hyperparameter | Value |
     |----------------|-------|
     | Optimizer | Adam / AdamW |
     | Learning rate | e.g., 1e-4 |
     | Batch size | e.g., 1024 |
     | Epochs | e.g., 100 |
     | Warmup steps | e.g., 10000 |
     | Weight decay | e.g., 0.01 |
     | Gradient clipping | e.g., 1.0 |

     ### Cross-Validation Results (if applicable)

     | Fold | Metric1 | Metric2 |
     |------|---------|---------|
     | 1    | 0.93    | 3.51    |
     | ...  | ...     | ...     |
     | Mean | 0.94    | 3.42    |
     | Std  | ±0.01   | ±0.15   |

     ### Reproducibility

     - Training command: `modal run models/MODEL/_train.py`
     - Training data source: URL or R2 path
     - Artifact storage: `r2://biolm-public/biolm-hub/model-weights/models/{slug}/v1/`
-->

## Versions & Changelog

<!-- Track significant changes to the BioLM implementation.

     | Version | Date | Changes |
     |---------|------|---------|
     | v1.0 | 2024-01-15 | Initial implementation |
     | v1.1 | 2024-03-20 | Added batch processing, fixed memory leak |
-->

---

*See also: [README.md](README.md) for API reference | [BIOLOGY.md](BIOLOGY.md) for biological context*
