# DeepViscosity -- Technical Details

## Architecture

### Model Type & Innovation

DeepViscosity is a two-stage ensemble deep learning pipeline for binary classification of monoclonal antibody (mAb) viscosity at high concentration (150 mg/mL). The key innovation is combining DeepSP-derived spatial property features with a large ensemble of simple neural networks to achieve robust viscosity classification without requiring expensive molecular dynamics simulations or experimental measurements.

**Stage 1 -- DeepSP CNN Feature Extraction**: Three 1D convolutional neural networks (Conv1D) predict 30 spatial aggregation propensity (SAP) and spatial charge map (SCM) features from IMGT-aligned, one-hot-encoded antibody Fv sequences. Each CNN predicts 10 features across antibody structural domains (CDR H1-H3, CDR L1-L3, combined CDR, Hv, Lv, Fv).

**Stage 2 -- Ensemble ANN Classification**: 102 independently trained artificial neural networks (ANNs) each predict the probability of high viscosity from the 30 scaled DeepSP features. The final prediction is the mean probability across the ensemble, thresholded at 0.5.

This approach differs from prior viscosity models (e.g., CamSol, TAP) by learning spatial features directly from sequence rather than relying on 3D structure calculations or hand-crafted descriptors.

### Parameters & Layers

**DeepSP CNN Models (3 models)**:

| Component | Details |
|-----------|---------|
| Architecture | Conv1D regression |
| Input shape | (272, 21) -- one-hot encoded aligned Fv |
| Models | SAPpos, SCMneg, SCMpos |
| Output per model | 10 spatial property values |
| Activation | ReLU (convolutional layers) |
| Loss function | Mean absolute error (MAE) |

**Ensemble ANN Models (102 models)**:

| Component | Details |
|-----------|---------|
| Architecture | Fully connected feedforward |
| Hidden layers | 4 (128 -> 64 -> 32 -> 16 neurons) |
| Activation | tanh |
| Input | 30 scaled DeepSP features |
| Output | 1 sigmoid probability |
| Training method | Leave-one-group-out (LOGO) cross-validation |
| Total ensemble models | 102 |

**Total parameter count**: Approximately 50K per ANN model, ~5.1M across all 102 ensemble models. CNN models are additional but smaller.

### Training Data

| Property | Details |
|----------|---------|
| Dataset | AstraZeneca proprietary mAb viscosity dataset |
| Size | 229 monoclonal antibodies |
| Measurements | Viscosity at 150 mg/mL in 20 mM histidine-HCl pH 6.0 |
| Class distribution | Low viscosity (<=20 cP) and high viscosity (>20 cP) |
| Split method | Leave-one-group-out (LOGO) cross-validation across 102 groups |
| External test sets | Lai_mAb_16 (n=16), Apgar_mAb_38 (n=38) |

**Known biases**:
- Training data is exclusively from AstraZeneca's mAb pipeline, which may over-represent certain antibody germline families
- All measurements at a single buffer condition (20 mM histidine-HCl pH 6.0)
- Binary classification threshold (20 cP) is specific to this dataset's distribution
- Only Fv (variable) regions are used; Fc region contributions to viscosity are not captured

### Loss Function & Objective

**Stage 1 (DeepSP CNNs)**: Mean absolute error (MAE) for regression of spatial property values:

```
L_CNN = (1/n) * sum(|y_true - y_pred|)
```

**Stage 2 (Ensemble ANNs)**: Binary cross-entropy for viscosity classification:

```
L_ANN = -(1/n) * sum(y*log(p) + (1-y)*log(1-p))
```

where y is the binary viscosity label (0=low, 1=high) and p is the predicted probability.

### Tokenization / Input Processing

1. **ANARCI alignment**: VH and VL sequences are aligned to IMGT numbering using ANARCI with HMMER
2. **Fixed-length extraction**: 145 positions from heavy chain + 127 positions from light chain = 272 total positions. Positions not present in the alignment are filled with gap characters
3. **One-hot encoding**: Each position is encoded as a 21-dimensional vector (20 standard amino acids + gap), producing a (272, 21) matrix
4. **Sequence constraints**: VH/VL Fv regions must be 50-200 residues each

## Performance & Benchmarks

### Published Benchmarks

#### LOGO Cross-Validation (Training Set, n=229)

| Model | Accuracy | AUC | Dataset |
|-------|----------|-----|---------|
| **DeepViscosity (Ensemble)** | **85.2%** | **0.901** | LOGO CV (n=229) |
| Single best ANN | 78.6% | 0.852 | LOGO CV (n=229) |
| Random Forest (DeepSP features) | 80.3% | 0.871 | LOGO CV (n=229) |
| Logistic Regression (DeepSP features) | 76.4% | 0.841 | LOGO CV (n=229) |

#### Independent Test Sets

| Test Set | n | Accuracy | Misclassifications |
|----------|---|----------|-------------------|
| Lai_mAb_16 | 16 | 87.5% | 2/16 |
| Apgar_mAb_38 | 38 | 68.4% | 12/38 |
| Combined external | 54 | 74.1% | 14/54 |

The Apgar_mAb_38 performance drop is attributed to high sequence homology among mAbs in that set, which the model struggles with.

### BioLM Verification Results

| Metric | Published | BioLM | Difference | Status |
|--------|-----------|-------|------------|--------|
| Lai_mAb_16 accuracy | 87.5% | deferred | -- | deferred (requires deployment) |
| Output probability range | [0, 1] | [0, 1] | 0 | PASS |
| Ensemble size | 102 models | 102 models | 0 | PASS |
| DeepSP features | 30 features | 30 features | 0 | PASS |

### Comparison to Alternatives

There are no direct antibody viscosity prediction models currently on the BioLM platform. DeepViscosity occupies a unique niche.

| Model | Task | Metric | When to prefer |
|-------|------|--------|----------------|
| **DeepViscosity** | Viscosity classification | 87.5% accuracy (Lai test) | Screening mAb candidates for manufacturability |
| CamSol (not on BioLM) | Solubility prediction | Spearman rho ~0.5 vs viscosity | General protein solubility (not viscosity-specific) |
| TAP (not on BioLM) | Developability scoring | Correlated with viscosity | Broader developability assessment |

### Error Bars & Confidence

The 102-model ensemble provides built-in uncertainty quantification:

- **probability_std**: Standard deviation across ensemble predictions. Higher values indicate greater model disagreement and lower confidence
- Typical probability_std range: 0.05-0.25
- Predictions near the 0.5 threshold with high probability_std should be treated with caution
- The ensemble approach mitigates individual model overfitting but cannot account for systematic biases in the training data

## Strengths & Limitations

### Pros

- **Sequence-only input**: Requires only VH/VL Fv sequences, no 3D structure needed
- **Fast inference**: CPU-only, completes in seconds per antibody
- **Uncertainty quantification**: 102-model ensemble provides meaningful confidence estimates via probability_std
- **Spatial features available**: Optional DeepSP feature output enables downstream analysis of which regions drive viscosity
- **Reproducible**: Deterministic seeds ensure identical outputs for identical inputs

### Cons

- **Binary output only**: Classifies as low/high rather than predicting continuous viscosity values
- **Single buffer condition**: Trained on 20 mM histidine-HCl pH 6.0 at 150 mg/mL only
- **Small training set**: Only 229 mAbs, limiting generalization to diverse antibody families
- **No Fc contribution**: Uses only Fv region; cannot capture Fc-mediated viscosity effects
- **Isotype-agnostic**: Does not distinguish IgG1, IgG2, IgG4 subclass effects

### Known Failure Modes

- **High-homology sets**: Performance degrades significantly on antibody sets with high sequence identity (Apgar_mAb_38: 68.4% accuracy vs 87.5% on Lai_mAb_16)
- **Non-antibody input**: Sequences that cannot be aligned by ANARCI to IMGT numbering will cause a runtime error
- **Unusual CDR3 lengths**: Very long or very short CDR H3 loops that fall outside the IMGT position inclusion list may lose information
- **Buffer-dependent viscosity**: Antibodies whose viscosity is dominated by buffer/excipient interactions rather than Fv properties will be poorly predicted
- **Boundary cases**: Antibodies with true viscosity near 20 cP may be classified either way with high uncertainty

## Implementation Details

### Inference Pipeline

```
Request (VH + VL sequences)
  |-- 1. Validate input (Pydantic schema: 50-200 residues, unambiguous AA)
  |-- 2. ANARCI alignment (IMGT numbering, heavy + light)
  |-- 3. Fixed-length extraction (145 H + 127 L = 272 positions)
  |-- 4. One-hot encoding (272 x 21 matrix)
  |-- 5. [CPU] DeepSP CNN inference (3 models -> 30 spatial features)
  |-- 6. StandardScaler normalization (pre-trained on 229 samples)
  |-- 7. [CPU] Ensemble ANN inference (102 models -> 102 probabilities)
  |-- 8. Aggregate: mean probability, std, threshold at 0.5
  +-- 9. Format response (viscosity_class, probability_mean, probability_std)
```

### Memory & Compute Profile

| Component | Memory | Time (per antibody) |
|-----------|--------|-------------------|
| 3 DeepSP CNN models | ~50 MB | ~100 ms |
| 102 ANN ensemble models | ~200 MB | ~2 s |
| ANARCI alignment | ~100 MB | ~1 s |
| TensorFlow runtime overhead | ~1.5 GB | -- |
| **Total** | **~2 GB** | **~3 s** |

No GPU required. CPU-only inference on a single core.

### Determinism & Reproducibility

| Setting | Value |
|---------|-------|
| NumPy seed | 42 |
| TensorFlow seed | 42 |
| GPU/CUDA | Not used (CPU only) |
| TF_ENABLE_ONEDNN_OPTS | Disabled |

The model is fully deterministic: identical inputs produce identical outputs across runs.

### Caching Behavior

- **Cache key composition**: Determined by input sequences and params (include_deepsp_features flag)

Response caching (Redis/R2 two-tier) is handled by the BioLM platform layer, not by the model container.
- **Memory snapshots**: Enabled -- all 105 models (3 CNN + 102 ANN) are loaded during snapshot creation for fast cold starts

## Training Procedures

### Training Configuration

**DeepSP CNN Training** (upstream, not reproducible within BioLM):

| Hyperparameter | Value |
|----------------|-------|
| Optimizer | Adam |
| Loss | MAE |
| Training data | Structural properties from antibody 3D models |

**Ensemble ANN Training** (upstream, not reproducible within BioLM):

| Hyperparameter | Value |
|----------------|-------|
| Optimizer | Adam |
| Learning rate | 0.0001 |
| Hidden layers | 128 -> 64 -> 32 -> 16 |
| Activation | tanh |
| Output activation | sigmoid |
| Validation | Leave-one-group-out (102 folds) |
| Feature scaling | StandardScaler (trained on 229 samples, 30 features) |

### Cross-Validation Results

From the paper (LOGO CV on 229 mAbs):

| Metric | Value |
|--------|-------|
| Accuracy | 85.2% |
| AUC | 0.901 |
| Sensitivity | 0.83 |
| Specificity | 0.87 |

## Versions & Changelog

| Version | Date | Changes |
|---------|------|---------|
| v1 | 2025-03 | Initial implementation: 102 ANN ensemble + 3 DeepSP CNNs, ANARCI alignment, embedded scaler |

---

*See also: [README.md](README.md) for API reference | [BIOLOGY.md](BIOLOGY.md) for biological context*
