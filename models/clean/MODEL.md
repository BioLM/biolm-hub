# CLEAN -- Technical Details

## Architecture

### Model Type & Innovation

CLEAN (Contrastive Learning for Enzyme ANnotation) replaces traditional enzyme classification approaches (sequence alignment, deep classification networks) with a contrastive learning framework. Instead of training a classifier over a fixed set of EC numbers, CLEAN learns a metric embedding space where Euclidean distance between protein embeddings reflects functional similarity.

The key innovation is the two-stage architecture: a frozen ESM-1b protein language model produces general-purpose sequence representations, and a lightweight projection network trained with contrastive loss maps these into a 128-dimensional space where enzymes sharing the same EC number cluster together. At inference time, new sequences are embedded and compared against precomputed EC cluster centers -- no retraining is needed when new EC classes are added to the database.

This design provides several advantages over classification-based methods:
- Handles EC classes with very few training examples (few-shot capability)
- Detects enzyme promiscuity (multiple EC annotations) via distance to multiple clusters
- Scales to new EC classes without architecture changes

### Parameters & Layers

| Component | Details |
|-----------|---------|
| Backbone | ESM-1b (33-layer Transformer encoder) |
| Backbone parameters | 650M |
| Backbone hidden dimension | 1280 |
| Backbone attention heads | 20 |
| Projection network | LayerNormNet (3-layer feedforward) |
| Projection architecture | Linear(1280->512) -> LayerNorm -> Dropout -> ReLU -> Linear(512->512) -> LayerNorm -> Dropout -> ReLU -> Linear(512->128) |
| Projection parameters | ~920K |
| Output embedding dimension | 128 |
| Dropout rate | 0.1 |
| Positional encoding | Learned (ESM-1b, max 1024 tokens) |
| Normalization | LayerNorm (projection network) |
| Activation | ReLU (projection network), GELU (ESM-1b backbone) |

### Training Data

| Property | Details |
|----------|---------|
| Dataset | SwissProt enzymes (split100 clustering) |
| Size | ~220,000 enzyme sequences |
| EC classes | ~5,242 distinct EC numbers |
| Clustering | 100% sequence identity (split100) |
| Composition | All domains of life, enzyme sequences only |
| Source | UniProtKB/Swiss-Prot reviewed entries |
| EC hierarchy | 4-level Enzyme Commission classification |

Known biases:
- Over-representation of well-studied organisms (E. coli, S. cerevisiae, H. sapiens)
- Under-representation of extremophile and environmental enzymes
- EC classes with many known members produce more reliable cluster centers
- Non-enzyme proteins are not represented in training data

### Loss Function & Objective

CLEAN uses a contrastive learning objective (triplet margin loss) where:
- **Positive pairs**: sequences with the same EC number are pulled together
- **Negative pairs**: sequences with different EC numbers are pushed apart

The loss encourages the 128-dimensional embedding space to encode functional similarity such that Euclidean distance between embeddings correlates with functional relatedness. Hard negative mining selects the most challenging negative pairs for efficient training.

### Tokenization / Input Processing

Input processing follows the ESM-1b pipeline:
- **Tokenizer**: Character-level over standard amino acid alphabet (20 canonical + special tokens)
- **Special tokens**: BOS (beginning of sequence) and EOS (end of sequence) added automatically
- **Maximum sequence length**: 1022 amino acids (1024 tokens including BOS/EOS, limited by ESM-1b positional embeddings)
- **Representation extraction**: Mean pooling over sequence positions (excluding BOS/EOS) from layer 33 (final layer) produces a 1280-dimensional vector per sequence
- **Extended alphabet**: Supports non-standard amino acids via the extended amino acid validator (X, U, B, Z, O, J mapped to standard residues)

## Performance & Benchmarks

### Published Benchmarks

#### EC Number Prediction (New-392 Dataset)

| Model | Precision | Recall | F1-max | Dataset |
|-------|-----------|--------|--------|---------|
| **CLEAN** | **0.781** | **0.741** | **0.760** | New-392 (n=392) |
| BLASTp | 0.167 | 0.090 | 0.117 | New-392 (n=392) |
| DeepEC | 0.130 | 0.048 | 0.070 | New-392 (n=392) |
| ProteInfer | 0.128 | 0.093 | 0.108 | New-392 (n=392) |
| CatFam | 0.041 | 0.015 | 0.022 | New-392 (n=392) |

New-392 contains enzymes deposited after the training data cutoff, testing true generalization.

#### EC Number Prediction (Price-149 Dataset)

| Model | Precision | Recall | F1-max | Dataset |
|-------|-----------|--------|--------|---------|
| **CLEAN** | **0.852** | **0.748** | **0.797** | Price-149 (n=149) |
| BLASTp | 0.725 | 0.430 | 0.540 | Price-149 (n=149) |
| CatFam | 0.619 | 0.300 | 0.404 | Price-149 (n=149) |
| ProteInfer | 0.417 | 0.268 | 0.326 | Price-149 (n=149) |
| DeepEC | 0.314 | 0.225 | 0.262 | Price-149 (n=149) |

Price-149 contains characterized enzymes from a directed evolution study (Price et al., 2018).

### BioLM Verification Results

Verification performed against 6 well-characterized enzymes with known EC numbers.

| Enzyme | Expected EC | BioLM Predicted EC | Confidence | Status |
|--------|-------------|-------------------|------------|--------|
| TEM-1 Beta-lactamase (P62593) | 3.5.2.6 | 3.5.2.6 | varies | PASS |
| ADH1 Yeast (P00330) | 1.1.1.1 | 1.1.1.1 | varies | PASS |
| Human Catalase (P04040) | 1.11.1.6 | 1.11.1.6 | varies | PASS |
| Chloroperoxidase (A7KH27) | 1.11.1.10 | 1.11.1.10 | 0.1155 | PASS |
| Stearoyl-CoA 9-desaturase (A8CF74) | 1.14.19.9 | 1.14.19.9 | 0.9547 | PASS |
| Flavin-dependent halogenase (Q8KLM0) | 1.14.19.56 | 1.14.19.56 | 0.6870 | PASS |

6/6 (100%) correct top-1 predictions.

### Comparison to Alternatives

| Model | Task | Metric | Value | When to prefer |
|-------|------|--------|-------|----------------|
| **CLEAN** | EC prediction | F1 (New-392) | 0.760 | Enzyme function annotation, few-shot EC classes |
| BLASTp | EC prediction | F1 (New-392) | 0.117 | When high-identity homologs exist in database |
| ESM-2 | Embedding | General embedding | N/A | General protein representation (not EC-specific) |
| ProteInfer | EC prediction | F1 (New-392) | 0.108 | Multi-label GO term prediction |

### Error Bars & Confidence

CLEAN provides GMM-based confidence scores for each prediction:
- An ensemble of Gaussian Mixture Models estimates the probability that a given distance corresponds to a true positive
- Confidence ranges from 0 to 1, with higher values indicating greater certainty
- Confidence varies with the density and separation of EC clusters in the embedding space
- Well-populated EC classes (many training examples) generally produce higher confidence scores
- EC classes with few training examples or overlapping functions produce lower confidence

Typical confidence distributions:
- High confidence (>0.8): EC classes with many distinct training sequences and clear functional separation
- Medium confidence (0.3-0.8): EC classes with moderate representation or partial functional overlap
- Low confidence (<0.3): Novel or under-represented EC classes, or non-enzyme proteins

## Strengths & Limitations

### Pros

- Dramatically outperforms BLASTp and deep learning baselines on novel enzyme annotation (6x higher F1 on New-392)
- No retraining required to add new EC classes -- just add cluster centers
- Handles few-shot EC classes where sequence alignment methods fail
- Max-separation algorithm provides automatic prediction cutoff without hyperparameter tuning
- 128-dim embeddings enable fast nearest-neighbor search for enzyme similarity
- GMM ensemble provides interpretable confidence estimates

### Cons

- Restricted to EC numbers present in the split100 training set (~5,242 classes)
- ESM-1b backbone limits sequences to 1022 amino acids
- Requires GPU for inference due to ESM-1b forward pass
- Non-enzyme proteins receive meaningless predictions (closest EC cluster, low confidence)
- Confidence calibration depends on the GMM training distribution

### Known Failure Modes

- **Novel EC numbers**: Sequences belonging to EC classes not in the training set will be assigned the closest existing EC cluster, typically with low confidence
- **Non-enzyme proteins**: All sequences receive EC predictions regardless of whether they are enzymes; non-enzymes will typically show high distances and low confidence but no explicit "not an enzyme" output
- **Very short sequences**: Sequences under ~30 amino acids produce poor ESM-1b representations due to limited context
- **Multifunctional enzymes**: While CLEAN can detect promiscuity, the max-separation algorithm caps predictions at 5 EC numbers per sequence by design
- **Highly divergent enzymes**: Enzymes with no sequence similarity to training data may embed far from all clusters

## Implementation Details

### Inference Pipeline

```
Request
  |-- 1. Validate input sequences (amino acid alphabet, length <= 1022)
  |-- 2. Tokenize with ESM-1b alphabet (add BOS/EOS tokens)
  |-- 3. [GPU] ESM-1b forward pass (33 transformer layers)
  |     +-- Output: per-token embeddings (N x 1280)
  |-- 4. Mean-pool over sequence positions (excluding BOS/EOS)
  |-- 5. [GPU] CLEAN projection network (1280 -> 512 -> 512 -> 128)
  |-- 6. Compute Euclidean distances to all EC cluster centers
  |-- 7. Sort by distance, apply max-separation algorithm
  |-- 8. Compute GMM confidence for selected predictions
  +-- 9. Format response with EC numbers, distances, and confidences
```

For the `encode` action, steps 6-8 are skipped and the 128-dimensional embeddings from step 5 are returned directly.

### Memory & Compute Profile

| Component | GPU Memory | Notes |
|-----------|-----------|-------|
| ESM-1b model weights | ~2.5 GB | 650M parameters in FP32 |
| CLEAN projection network | ~4 MB | ~920K parameters |
| EC cluster centers | ~2.7 MB | 5,242 x 128 floats |
| GMM ensemble | ~1 MB | Serialized sklearn models |
| ESM-1b inference (batch=10, len=500) | ~3 GB | Attention memory scales O(n^2) |
| **Total (typical)** | **~6 GB** | Fits comfortably on T4 (16 GB) |

Inference time scales primarily with sequence length due to the ESM-1b attention mechanism.

### Determinism & Reproducibility

| Setting | Value |
|---------|-------|
| torch.manual_seed | 42 |
| CUDA manual seed | 42 |
| NumPy seed | 42 |
| cuDNN deterministic | True |
| cuDNN benchmark | Disabled |

The model is fully deterministic given identical inputs and hardware. All stochastic components (dropout) are disabled during inference via `model.eval()`.

### Caching Behavior

Response caching (Redis/R2 two-tier) is handled by the BioLM platform layer, not by the model container:

- **R2 caching**: Model weights and cluster centers cached to R2 for fast container builds
- **Cache key composition**: Determined by input sequences and action type
- **Cache invalidation**: Standard TTL-based invalidation at the platform layer

## Training Procedures

### Training Configuration

| Hyperparameter | Value |
|----------------|-------|
| Backbone | ESM-1b (frozen during training) |
| Optimizer | Adam |
| Loss function | Triplet margin loss (contrastive) |
| Training data split | split100 (100% identity clustering) |
| Embedding dimension | 128 |
| Hidden dimension | 512 |
| Dropout | 0.1 |
| Negative mining | Hard negatives |

Training is performed upstream by the original authors. The BioLM deployment uses the pretrained split100.pth weights directly.

## Versions & Changelog

| Version | Date | Changes |
|---------|------|---------|
| v1 | 2025-03 | Initial implementation with predict and encode actions |

---

*See also: [README.md](README.md) for API reference | [BIOLOGY.md](BIOLOGY.md) for biological context*
