# CLEAN

> **One-line summary**: Predicts Enzyme Commission (EC) numbers from protein sequences using contrastive learning, with state-of-the-art accuracy on novel and understudied enzymes.

## Overview

CLEAN (Contrastive Learning for Enzyme ANnotation) is an enzyme function prediction model developed by Yu et al. (2023) and published in *Science*. It uses contrastive learning to create an embedding space where Euclidean distance between protein representations reflects functional similarity, enabling accurate EC number prediction without traditional sequence alignment.

The key innovation is replacing classification-based approaches with a learned distance metric. A frozen ESM-1b backbone produces sequence embeddings, and a lightweight projection network maps them to a 128-dimensional space trained with contrastive loss on SwissProt enzymes. At inference, sequences are compared against precomputed EC cluster centers, with a max-separation algorithm selecting confident predictions and a GMM ensemble providing calibrated confidence scores.

CLEAN dramatically outperforms BLASTp, DeepEC, and ProteInfer on novel enzyme annotation, achieving F1=0.760 on the New-392 benchmark compared to F1=0.117 for BLASTp.

## Architecture

| Property | Value |
|----------|-------|
| Backbone | ESM-1b (Transformer encoder, 33 layers) |
| Backbone parameters | 650M |
| Backbone hidden dimension | 1280 |
| Projection network | LayerNormNet (1280->512->512->128) |
| Projection parameters | ~920K |
| Output embedding dimension | 128 |
| Training data | SwissProt enzymes (~220K sequences, ~5,242 EC classes) |
| Training objective | Contrastive learning (triplet margin loss) |
| Max sequence length | 1022 residues |

See [MODEL.md](MODEL.md) for detailed architecture specifications.

## Model Variants

Single variant -- no size options. Uses the split100 pretrained weights (100% identity clustering of SwissProt enzymes).

## Capabilities & Limitations

**CAN be used for:**
- Predicting EC numbers for enzyme protein sequences with confidence scores
- Annotating novel or understudied enzymes with few known homologs
- Detecting enzyme promiscuity (multiple EC activities per enzyme)
- Extracting 128-dimensional functional embeddings for enzyme similarity search and clustering
- Batch processing of up to 10 sequences per request

**CANNOT be used for:**
- Sequences longer than 1022 amino acids (ESM-1b positional encoding constraint)
- EC numbers not present in the split100 training set (~5,242 classes covered)
- Non-enzyme protein classification (all inputs receive EC predictions regardless)
- GO term or pathway-level annotation (EC numbers only)
- Structure prediction or protein design

**Other considerations:**
- Non-enzyme proteins will receive low-confidence predictions assigned to the nearest EC cluster; there is no explicit "not an enzyme" output
- The max-separation algorithm typically returns 1-5 predictions per sequence by design
- Confidence scores are GMM-based and vary depending on the density of training examples for each EC class
- GPU required for inference (ESM-1b backbone)

## Actions / Endpoints

### `predict`

Predicts EC numbers for protein sequences with confidence scores.

**Request Parameters:**

| Parameter | Type | Default | Range | Description |
|-----------|------|---------|-------|-------------|
| `items[].sequence` | str | - | 1-1022 residues | Protein amino acid sequence |
| `params.max_predictions` | int | 10 | 1-20 | Maximum number of EC predictions per sequence |
| `params.min_confidence` | float | 0.05 | 0.0-1.0 | Minimum confidence threshold to include a prediction |

**Response:**

```json
{
  "results": [
    {
      "predictions": [
        {
          "ec_number": "3.5.2.6",
          "distance": 3.1234,
          "confidence": 0.9628
        }
      ]
    }
  ]
}
```

### `encode`

Extracts 128-dimensional CLEAN embeddings that capture enzyme functional similarity.

**Request Parameters:**

| Parameter | Type | Default | Range | Description |
|-----------|------|---------|-------|-------------|
| `items[].sequence` | str | - | 1-1022 residues | Protein amino acid sequence |

**Response:**

```json
{
  "results": [
    {
      "embedding": [0.123, -0.456, 0.789, "... (128 values)"]
    }
  ]
}
```

## Usage Examples

### Predict EC Numbers

```python
from models.clean.schema import (
    CLEANPredictRequest,
    CLEANPredictRequestItem,
    CLEANPredictRequestParams,
)

# Single sequence prediction
request = CLEANPredictRequest(
    params=CLEANPredictRequestParams(
        max_predictions=5,
        min_confidence=0.1,
    ),
    items=[
        CLEANPredictRequestItem(
            sequence="MSIQHFRVALIPFFAAFCLPVFAHPETLVKVKDAEDQLGARVGYIELDLNSGK..."
        ),
    ],
)
```

### Encode Sequences

```python
from models.clean.schema import (
    CLEANEncodeRequest,
    CLEANEncodeRequestItem,
)

# Extract functional embeddings
request = CLEANEncodeRequest(
    items=[
        CLEANEncodeRequestItem(
            sequence="MSIQHFRVALIPFFAAFCLPVFAHPETLVKVKDAEDQLGARVGYIELDLNSGK..."
        ),
    ],
)
```

## Performance & Benchmarks

### Published Results

#### EC Prediction -- New-392 (Novel Enzymes)

| Model | Precision | Recall | F1-max | Dataset |
|-------|-----------|--------|--------|---------|
| **CLEAN** | **0.781** | **0.741** | **0.760** | New-392 (n=392) |
| BLASTp | 0.167 | 0.090 | 0.117 | New-392 (n=392) |
| DeepEC | 0.130 | 0.048 | 0.070 | New-392 (n=392) |
| ProteInfer | 0.128 | 0.093 | 0.108 | New-392 (n=392) |
| CatFam | 0.041 | 0.015 | 0.022 | New-392 (n=392) |

#### EC Prediction -- Price-149 (Directed Evolution Enzymes)

| Model | Precision | Recall | F1-max | Dataset |
|-------|-----------|--------|--------|---------|
| **CLEAN** | **0.852** | **0.748** | **0.797** | Price-149 (n=149) |
| BLASTp | 0.725 | 0.430 | 0.540 | Price-149 (n=149) |
| CatFam | 0.619 | 0.300 | 0.404 | Price-149 (n=149) |
| ProteInfer | 0.417 | 0.268 | 0.326 | Price-149 (n=149) |
| DeepEC | 0.314 | 0.225 | 0.262 | Price-149 (n=149) |

### SOTA Status

CLEAN was state-of-the-art for EC number prediction at time of publication (Science, 2023). It remains a leading contrastive-learning-based method for enzyme annotation as of early 2025.

## Implementation Verification

### Verification Method

Option B -- Known Extremes: Tested against well-characterized enzymes with experimentally determined EC numbers from UniProt and published literature. Verified that the model correctly predicts the known EC number as the top prediction.

### Test Cases

Tested against 6 well-characterized enzymes from the halogenase dataset with known EC numbers from UniProt/literature:

| Protein | Description | Expected EC | Predicted EC | Confidence |
|---------|-------------|-------------|--------------|------------|
| A7KH27 | Chloroperoxidase | 1.11.1.10 | 1.11.1.10 | 0.1155 |
| A8CF74 | Stearoyl-CoA 9-desaturase | 1.14.19.9 | 1.14.19.9 | 0.9547 |
| Q8KLM0 | Flavin-dependent halogenase | 1.14.19.56 | 1.14.19.56 | 0.6870 |
| Q8GAQ9 | Tryptophan 7-halogenase | 1.14.20.15 | 1.14.20.15 | 0.0051 |
| W0W999 | Dimethylallyl-tryptophan synthase | 2.5.1.63 | 2.5.1.63 | 0.9987 |
| Q5SLF5 | 2-haloacid dehalogenase | 3.13.1.8 | 3.13.1.8 | 0.9628 |

### Verification Status

**Status: VERIFIED** -- All 6 test cases produce correct top-1 EC predictions. Confidence scores vary based on GMM ensemble calibration and distance to cluster centers, which is expected behavior.

## Resource Requirements

| Resource | Value |
|----------|-------|
| GPU | T4 (16 GB VRAM) |
| Memory | 16 GB RAM |
| CPU | 4 cores |
| Cold start | ~2-3 minutes (with memory snapshot) |
| Dependencies | ESM-1b, scikit-learn, pandas, numpy |

## Implementation Notes

- **Memory snapshots**: Uses `@modal.enter(snap=True)` to snapshot model weights on CPU, then restores on GPU for fast cold starts
- **Caching**: Redis/R2 caching via BillingMixinSnap integration
- **Determinism**: All seeds set (torch=42, numpy=42, CUDA=42, cuDNN deterministic=True, cuDNN benchmark=False)
- **Container image**: Based on `pytorch/pytorch:2.0.1-cuda11.7-cudnn8-runtime`
- **Download strategy**: R2 cache primary, Google Drive + GitHub fallback for initial download
- **Cluster centers**: Precomputed from split100 embeddings and stored as a tensor for efficient batch distance computation
- **GMM ensemble**: Serialized scikit-learn GMMs loaded from `gmm_ensumble.pkl` (note: original authors' typo in filename preserved)

## Confidence Metrics

| Metric | Range | Interpretation |
|--------|-------|----------------|
| `confidence` | 0.0-1.0 | GMM-based probability of true positive; >0.8 high confidence, 0.3-0.8 moderate, <0.3 low |
| `distance` | 0.0+ | Euclidean distance to EC cluster center; lower = more similar to known enzymes of that class |

Confidence and distance are inversely correlated: smaller distances generally produce higher confidence scores. The GMM ensemble was trained on the distribution of true-positive and false-positive distances from the training set.

## License

- **Code**: BSD-3-Clause ([LICENSE](https://github.com/tttianhao/CLEAN/blob/main/LICENSE))

## References & Citations

### Papers

1. Yu T, Cui H, Li JC, Luo Y, Jiang G, Zhao H. "Enzyme function prediction using contrastive learning." *Science* 379(6639):1358-1363 (2023). [DOI](https://doi.org/10.1126/science.adf2465)

### BibTeX

```bibtex
@article{doi:10.1126/science.adf2465,
  author = {Tianhao Yu and Haiyang Cui and Jianan Canal Li and Yunan Luo and Guangde Jiang and Huimin Zhao},
  title = {Enzyme function prediction using contrastive learning},
  journal = {Science},
  volume = {379},
  number = {6639},
  pages = {1358-1363},
  year = {2023},
  doi = {10.1126/science.adf2465}
}
```

### Links

- **Paper**: https://www.science.org/doi/10.1126/science.adf2465
- **Code**: [GitHub tttianhao/CLEAN](https://github.com/tttianhao/CLEAN)

---

*See also: [MODEL.md](MODEL.md) for technical deep-dive | [BIOLOGY.md](BIOLOGY.md) for biological context*
