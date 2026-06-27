# ESMStabP -- Technical Details

## Architecture

### Model Type & Innovation

ESMStabP is a two-stage protein thermostability prediction model that combines pre-trained protein language model embeddings with classical machine learning. The key innovation is leveraging ESM2-650M (layer 33) mean-pooled embeddings as fixed feature representations, then training Random Forest regressors on top -- bypassing the need for end-to-end fine-tuning or neural network prediction heads.

This approach contrasts with prior work (DeepSTABp, ProTstab2, TemBERTure) that either fine-tuned the language model directly or used multi-layer perceptron (MLP) prediction heads. The authors demonstrate that raw ESM2 embeddings fed directly into a Random Forest consistently outperform both LoRA fine-tuning of ESM2/ProtT5 and MLP-based prediction heads.

The model also introduces a metadata-aware model selection strategy: four separate Random Forest regressors are trained with different feature configurations (embedding-only, embedding+growth temperature, embedding+experimental condition, and all features combined). At inference time, the appropriate model is automatically selected based on which metadata fields the user provides.

### Parameters & Layers

ESMStabP consists of two components:

**Feature Extractor (ESM2-650M -- external, not loaded locally):**

| Component | Details |
|-----------|---------|
| Architecture | Transformer encoder, 33 layers |
| Parameters | 650M |
| Hidden dimensions | 1280 |
| Attention heads | 20 |
| Extraction layer | Layer 33 (final layer) |
| Pooling | Mean over sequence positions |
| Output | 1280-dimensional embedding vector |

**Prediction Head (Random Forest -- loaded locally):**

| Component | Details |
|-----------|---------|
| Algorithm | Random Forest Regressor (scikit-learn) |
| Estimators | 100 trees per model |
| Models | 4 variants with different feature sets |
| Model 1 features | 1280 (embedding only) |
| Model 2 features | 1283 (embedding + growth_temp + thermophilic + nonThermophilic) |
| Model 3 features | 1282 (embedding + lysate + cell) |
| Model 4 features | 1286 (embedding + growth_temp + lysate + cell + thermophilic + nonThermophilic) |
| Total disk size | ~4 x joblib files (lightweight) |

### Training Data

| Property | Details |
|----------|---------|
| Dataset | Combined from DeepStabP, DeepTM, and TemBERTure datasets |
| Source | [GitHub: marcusramos2024/ESMStabP](https://github.com/marcusramos2024/ESMStabP/blob/main/Dataset%20Assembly/Dataset.csv) |
| Labels | Experimental melting temperatures (Tm) from thermo-proteome profiling (TPP) mass spectrometry |
| Balancing | Non-thermophilic proteins randomly downsampled to match thermophilic count |
| Split | 80/20 train/test with 5-fold cross-validation |
| Columns | Protein, sequence, growth_temp, lysate, cell, label_tm, thermophilic, nonThermophilic |

**Known biases:**
- Dataset skewed toward thermophilic organisms before balancing
- Experimental Tm values derived primarily from TPP mass spectrometry (may differ from DSC/DSF measurements)
- Limited representation of extremely thermostable proteins (Tm > 100 degrees C)
- Predominantly bacterial and archaeal proteins

### Loss Function & Objective

The Random Forest regressor optimizes the mean squared error (MSE) criterion at each split during tree construction. The final prediction is the average of all 100 trees' predictions:

```
Tm_predicted = (1/100) * sum(tree_i(features))
```

No explicit loss function is minimized during inference -- the model is non-parametric. During training, each decision tree minimizes variance reduction (MSE) at each node split.

### Tokenization / Input Processing

Input processing occurs in two stages:

1. **ESM2 tokenization** (handled by the `esm2-650m` endpoint):
   - Character-level tokenization: each amino acid maps to one token
   - Special tokens: `<cls>` (position 0), `<eos>` (final position)
   - Vocabulary: 33 tokens (20 standard AA + special tokens)
   - Maximum sequence length: 1022 residues (positions 1-1022, excluding special tokens)
   - Supported alphabet: standard amino acids plus extended characters (B, J, O, U, X, Z, `-`)

2. **Feature assembly** (handled by ESMStabP):
   - Mean-pool ESM2 layer 33 representations over sequence positions (excluding special tokens)
   - Optionally append metadata features: growth_temp (int), lysate/cell flags (binary), thermophilic/nonThermophilic flags (derived from growth_temp > 60 or < 30)
   - Select appropriate RF model (1-4) based on available metadata

## Performance & Benchmarks

### Published Benchmarks

#### Balanced Dataset (Primary Evaluation)

| Model | R-squared | PCC | MAE (degrees C) | RMSE (degrees C) |
|-------|-----------|-----|------------------|-------------------|
| **ESMStabP** | **0.94** | **0.92** | **3.42** | **4.13** |
| DeepSTABp | 0.81 | 0.88 | 3.62 | 4.32 |
| ProTstab2 | 0.51 | 0.68 | 4.95 | 6.31 |

#### Unbalanced Dataset

| Model | R-squared | PCC | MAE (degrees C) | RMSE (degrees C) |
|-------|-----------|-----|------------------|-------------------|
| **ESMStabP** | **0.95** | **0.97** | **2.79** | - |

### BioLM Verification Results

Verified against 10 proteins with experimentally measured Tm values from published literature (ProThermDB, UniProt, PubMed), spanning hyperthermophilic to psychrophilic organisms.

| Metric | Without growth_temp | With growth_temp |
|--------|---------------------|------------------|
| MAE | 30.6 degrees C | 24.8 degrees C |
| RMSE | 45.8 degrees C | 40.4 degrees C |
| Biological checks passed | 1/4 | 3/4 |

Higher MAE versus the paper's 3.4 degrees C is expected: the validation proteins are deliberately out-of-distribution, and Rubredoxin's extreme ~200 degrees C Tm is an outlier well beyond the training distribution. Importantly, the correct stability ranking is preserved: Hyperthermophilic (83.6 degrees C predicted) > Thermostable (65.9 degrees C) > Psychrophilic (56.5 degrees C).

### Comparison to Alternatives

ESMStabP is the only dedicated thermostability prediction model on the BioLM platform. For related tasks:

| Model | Task | When to prefer |
|-------|------|----------------|
| **ESMStabP** | Tm prediction (regression) | Direct melting temperature estimation |
| ESM2-650M | General protein embeddings | When you need embeddings for downstream custom models |
| CamSol | Solubility prediction | When solubility (not thermal stability) is the target |

### Error Bars & Confidence

From 5-fold cross-validation during training:

| Model | Mean R-squared | Std |
|-------|----------------|-----|
| 1.joblib (embedding only) | 0.929 | +/-0.009 |
| 2.joblib (+ growth_temp) | 0.954 | +/-0.002 |
| 3.joblib (+ condition) | 0.935 | +/-0.010 |
| 4.joblib (all features) | 0.955 | +/-0.002 |

The model provides point estimates only -- no prediction intervals or uncertainty quantification. Users should expect approximately +/-3-4 degrees C MAE for in-distribution proteins. Performance degrades for proteins far from the training distribution (extreme thermophiles, disordered proteins).

## Strengths & Limitations

### Pros

- Extremely lightweight inference: CPU-only Random Forest, no GPU required for the prediction head
- Fast cold start: no large model weights to load (ESM2 runs on separate endpoint)
- Metadata-aware: providing growth temperature substantially improves accuracy (R-squared from 0.929 to 0.954)
- State-of-the-art accuracy on balanced Tm prediction benchmarks
- Modular architecture: ESM2 embeddings are reusable for other downstream tasks
- Fully reproducible training pipeline included

### Cons

- Depends on external `esm2-650m` endpoint (latency includes network round-trip)
- Point estimates only (no uncertainty quantification)
- Context-blind: ignores pH, cofactors, salt concentration, oligomeric state
- ~3-4 degrees C MAE limits use in high-precision applications
- Training distribution bias toward thermophilic organisms

### Known Failure Modes

- **Hyperthermophilic proteins (Tm > 100 degrees C)**: Systematically underestimated due to sparse training data in this range. Rubredoxin (~200 degrees C experimental) predicted at ~83 degrees C.
- **Intrinsically disordered proteins**: ESM2 embeddings may not capture unfolding behavior meaningfully for proteins that lack stable tertiary structure.
- **Very short peptides**: Sequences under ~20 residues produce embeddings dominated by noise; Tm predictions unreliable.
- **Membrane proteins in detergent**: Experimental Tm strongly depends on detergent type, which is not modeled.
- **Multi-domain proteins**: Mean-pooled embedding averages over all domains; if domains have very different stabilities, the prediction reflects neither accurately.

## Implementation Details

### Inference Pipeline

```
Request
  |-- 1. Validate input (sequence length, amino acid alphabet, optional metadata)
  |-- 2. Batch all sequences into a single ESM2 encode request
  |-- 3. [Remote RPC] Call esm2-650m endpoint for layer 33 mean embeddings
  |-- 4. For each sequence:
  |     |-- a. Select RF model (1-4) based on available metadata
  |     |-- b. Assemble feature vector (embedding + metadata features)
  |     |-- c. Run RF .predict() on CPU
  |     |-- d. Derive is_thermophilic flag (Tm > 60 degrees C)
  |-- 5. Return list of (melting_temperature, is_thermophilic) results
```

### Memory & Compute Profile

| Component | Resource | Notes |
|-----------|----------|-------|
| RF models (4x joblib) | ~50-100 MB RAM total | Loaded once at startup |
| ESM2 embeddings | 0 GB local | Computed on remote esm2-650m endpoint |
| Feature assembly | Negligible | NumPy array operations |
| RF inference | ~1-10ms per sequence | CPU-only, parallelized across trees |

The dominant latency is the ESM2 embedding extraction via remote RPC, not the local RF inference. Batch requests amortize the RPC overhead.

| Batch Size | Approximate Total Latency | Notes |
|------------|---------------------------|-------|
| 1 sequence | ~500ms-2s | Dominated by ESM2 RPC |
| 8 sequences (max) | ~1-5s | Single batched ESM2 call |

### Determinism & Reproducibility

| Setting | Value |
|---------|-------|
| NumPy seed | 42 (set at model load) |
| Torch seed (training) | 42 |
| CUDA seed (training) | 42 |
| RF random_state | 42 (set during training) |
| Deterministic at inference | Yes -- RF is deterministic given fixed model weights |

The model is fully deterministic at inference time. Random Forest prediction is a deterministic tree traversal. The only potential source of variation is floating-point differences in ESM2 embeddings across hardware, which are typically negligible.

### Caching Behavior

- **Redis caching**: Provided by the BioLM platform layer (standard platform caching)
- **R2 caching**: Provided by the BioLM platform layer
- **Cache key**: Composed from action name + serialized request payload (sequence + metadata)
- **Cache invalidation**: Standard platform TTL-based expiry

## Training Procedures

### Training Configuration

| Hyperparameter | Value |
|----------------|-------|
| Algorithm | Random Forest Regressor (scikit-learn) |
| n_estimators | 100 |
| random_state | 42 |
| n_jobs | -1 (all available cores) |
| All other RF params | scikit-learn defaults (max_depth=None, min_samples_split=2, etc.) |
| ESM2 model | esm2_t33_650M_UR50D |
| Embedding layer | 33 |
| Embedding pooling | Mean over sequence positions |

### Training Pipeline

```bash
# Run training (uses GPU for ESM2 embedding extraction, ~30-60 minutes)
modal run models/esmstabp/_train.py
```

Steps:
1. Fetch dataset from GitHub (marcusramos2024/ESMStabP)
2. Balance dataset by downsampling non-thermophilic proteins
3. Extract ESM2 layer 33 mean embeddings for all sequences (GPU)
4. Train 4 Random Forest models with different feature configurations
5. Upload trained joblib files to R2

### Cross-Validation Results (5-fold)

| Model | Description | Features | Mean R-squared | Std |
|-------|-------------|----------|----------------|-----|
| 1.joblib | Embedding only | 1280 | 0.929 | +/-0.009 |
| 2.joblib | + growth_temp + flags | 1283 | 0.954 | +/-0.002 |
| 3.joblib | + lysate/cell | 1282 | 0.935 | +/-0.010 |
| 4.joblib | All features | 1286 | 0.955 | +/-0.002 |

These results closely match the published paper's R-squared of 0.94-0.95.

### Reproducibility

- **Training command**: `modal run models/esmstabp/_train.py`
- **Training data source**: [GitHub Dataset.csv](https://github.com/marcusramos2024/ESMStabP/blob/main/Dataset%20Assembly/Dataset.csv)
- **Artifact storage**: `r2://biolm-modal/model-store/esmstabp/v1/`
- **Artifacts**: `1.joblib`, `2.joblib`, `3.joblib`, `4.joblib`

## Versions & Changelog

| Version | Date | Changes |
|---------|------|---------|
| v1 | 2025 | Initial implementation: 4 RF models, ESM2-650M embeddings via remote endpoint, CPU-only inference |

---

*See also: [README.md](README.md) for API reference | [BIOLOGY.md](BIOLOGY.md) for biological context*
