# DeepViscosity

> **One-line summary**: Ensemble deep learning model for classifying monoclonal antibody viscosity at high concentration (150 mg/mL) as low or high from VH/VL Fv sequences.

## Overview

DeepViscosity is a two-stage ensemble deep learning pipeline developed by Kalejaye et al. (mAbs, 2025) for predicting whether a monoclonal antibody will exhibit low (<=20 cP) or high (>20 cP) viscosity at therapeutic concentration. It uses DeepSP CNN models to extract 30 spatial property features from sequence, followed by 102 ensemble ANN classifiers.

The model addresses a critical bottleneck in biopharmaceutical development: identifying antibody candidates with viscosity liabilities before expensive experimental characterization. It is the first open-source, sequence-only viscosity classifier with built-in ensemble uncertainty estimates.

## Architecture

| Property | Value |
|----------|-------|
| Architecture | 3 Conv1D CNNs (feature extraction) + 102 ANN ensemble (classification) |
| Input | Paired VH + VL Fv sequences |
| Feature representation | (272, 21) one-hot encoded IMGT-aligned sequence |
| DeepSP features | 30 spatial properties (SAP_pos, SCM_neg, SCM_pos x 10 domains) |
| ANN hidden layers | 4 (128 -> 64 -> 32 -> 16, tanh activation) |
| Training data | 229 mAbs (AstraZeneca, 150 mg/mL, 20 mM histidine-HCl pH 6.0) |
| Max sequence length | 200 residues per chain |
| Min sequence length | 50 residues per chain |

See [MODEL.md](MODEL.md) for detailed architecture specifications.

## Model Variants

Single variant -- no size options. The model runs on CPU only (no GPU required).

## Capabilities & Limitations

**CAN be used for:**
- Early-stage screening of therapeutic antibody candidates for manufacturability
- Identifying high-viscosity mAbs before expensive formulation development
- Guiding antibody engineering to reduce viscosity via DeepSP feature analysis
- Batch prediction of up to 10 antibodies per request

**CANNOT be used for:**
- Continuous viscosity value prediction (binary classification only)
- Non-antibody proteins (requires ANARCI-alignable VH/VL sequences)
- Sequences longer than 200 residues or shorter than 50 residues per chain
- Predicting viscosity at concentrations other than 150 mg/mL
- Predicting viscosity in buffer conditions other than 20 mM histidine-HCl pH 6.0
- Nanobodies or single-domain antibodies (requires paired VH/VL)

**Other considerations:**
- Only predicts binary class (low/high), not continuous viscosity values
- Trained on mAbs at 150 mg/mL in 20mM histidine-HCl pH 6.0 buffer
- Does not capture effects of different isotypes (IgG1, IgG2, IgG4) or Fc region
- Performance may degrade for mAbs with high sequence homology (as seen with Apgar_mAb_38 test set)
- Requires valid antibody Fv sequences; will fail on non-antibody proteins

## Actions / Endpoints

### `predict`

Predict antibody viscosity class from paired VH/VL Fv sequences.

**Request Parameters:**

| Parameter | Type | Default | Range | Description |
|-----------|------|---------|-------|-------------|
| `items[].heavy_chain` | str | -- | 50-200 residues | Heavy chain variable region (VH) Fv sequence |
| `items[].light_chain` | str | -- | 50-200 residues | Light chain variable region (VL) Fv sequence |
| `params.include_deepsp_features` | bool | false | true/false | Include 30 DeepSP spatial property features in response |
| `items` | list | -- | 1-10 items | List of antibody items to predict |

**Response:**

```json
{
  "results": [
    {
      "viscosity_class": "low",
      "probability_mean": 0.234567,
      "probability_std": 0.089012,
      "is_high_viscosity": false,
      "deepsp_features": null
    }
  ]
}
```

| Field | Type | Description |
|-------|------|-------------|
| `viscosity_class` | str | "low" (<=20 cP) or "high" (>20 cP) |
| `probability_mean` | float | Mean predicted probability across 102 ensemble models (0-1) |
| `probability_std` | float | Standard deviation across ensemble (>=0) |
| `is_high_viscosity` | bool | True if probability_mean >= 0.5 |
| `deepsp_features` | dict or null | 30 named DeepSP features if requested, null otherwise |

## Usage Examples

```python
from models.deepviscosity.schema import (
    DeepViscosityPredictRequest,
    DeepViscosityPredictRequestItem,
    DeepViscosityPredictRequestParams,
)

# Single antibody prediction
request = DeepViscosityPredictRequest(
    items=[
        DeepViscosityPredictRequestItem(
            heavy_chain="EVQLVESGGGLVQPGRSLRLSCAASGFTFDDYAMHWVRQAPGKGLEWVSAITWNSGHIDYADSVEGRFTISRDNAKNSLYLQMNSLRAEDTAVYYCAKVSYLSTASSLDYWGQGTLVTVSS",
            light_chain="DIQMTQSPSSLSASVGDRVTITCRASQGIRNYLAWYQQKPGKAPKLLIYAASTLQSGVPSRFSGSGSGTDFTLTISSLQPEDVATYYCQRYNRAPYTFGQGTKVEIK",
        )
    ]
)

# With DeepSP features included
request_with_features = DeepViscosityPredictRequest(
    params=DeepViscosityPredictRequestParams(include_deepsp_features=True),
    items=[
        DeepViscosityPredictRequestItem(
            heavy_chain="EVQLVESGGGLVQPGRSLRLSCAASGFTFDDYAMHWVRQAPGKGLEWVSAITWNSGHIDYADSVEGRFTISRDNAKNSLYLQMNSLRAEDTAVYYCAKVSYLSTASSLDYWGQGTLVTVSS",
            light_chain="DIQMTQSPSSLSASVGDRVTITCRASQGIRNYLAWYQQKPGKAPKLLIYAASTLQSGVPSRFSGSGSGTDFTLTISSLQPEDVATYYCQRYNRAPYTFGQGTKVEIK",
        )
    ],
)

# Batch prediction (up to 10 antibodies)
batch_request = DeepViscosityPredictRequest(
    items=[
        DeepViscosityPredictRequestItem(
            heavy_chain="EVQLVESGGGLVQPGRSLRLSCAASGFTFDDYAMH...",
            light_chain="DIQMTQSPSSLSASVGDRVTITCRASQGIRNYLA...",
        ),
        DeepViscosityPredictRequestItem(
            heavy_chain="EVQLVESGGGLVQPGGSLRLSCAASGFTFSDSWIH...",
            light_chain="DIQMTQSPSSLSASVGDRVTITCRASQDVSTAVA...",
        ),
    ]
)
```

## Performance & Benchmarks

### Published Results

| Model | Accuracy | AUC | Dataset |
|-------|----------|-----|---------|
| **DeepViscosity (Ensemble)** | **85.2%** | **0.901** | LOGO CV (n=229) |
| **DeepViscosity (Ensemble)** | **87.5%** | -- | Lai_mAb_16 (n=16) |
| **DeepViscosity (Ensemble)** | **68.4%** | -- | Apgar_mAb_38 (n=38) |
| Single best ANN | 78.6% | 0.852 | LOGO CV (n=229) |
| Random Forest | 80.3% | 0.871 | LOGO CV (n=229) |

### SOTA Status

DeepViscosity is the first open-source ensemble deep learning model for antibody viscosity classification, published in mAbs (2025). As of March 2025, it represents the state of the art for sequence-only mAb viscosity prediction among publicly available tools.

## Implementation Verification

Verification approach: **Published Values** from the Lai_mAb_16 independent test set.

### Verification Method

Option C -- Baseline Comparison: Test sequences are drawn from the DeepViscosity_input.csv sample file (Lai_mAb_16 test set) provided in the original GitHub repository. Model outputs are verified against expected behavior from the paper: binary classification with probability in [0, 1], ensemble uncertainty, and optional DeepSP features.

### Test Cases

The `fixture.py` test sequences are from the DeepViscosity_input.csv sample file (Lai_mAb_16 test set):

| Sequence | Source | Description |
|----------|--------|-------------|
| mAb1 (TEST_VH_1/VL_1) | Lai et al. | Single antibody prediction |
| mAb2 (TEST_VH_2/VL_2) | Lai et al. | Batch prediction test |
| mAb3 (TEST_VH_3/VL_3) | Lai et al. | Batch prediction test |

### Expected Results

From the paper (Table 2):
- **Lai_mAb_16 test set**: 10 low viscosity, 6 high viscosity mAbs
- **Published accuracy**: 87.5% (14/16 correct, 2 misclassifications)
- **Expected behavior**: Model outputs binary class (low/high) with probability_mean in [0, 1]

### Verification Criteria

1. **Schema validation**: All 7 edge case tests pass
2. **Output format**: Results contain `viscosity_class`, `probability_mean`, `probability_std`, `is_high_viscosity`
3. **Probability bounds**: `probability_mean` in [0, 1], `probability_std` >= 0
4. **DeepSP features**: When `include_deepsp_features=True`, returns 30 named features matching `DEEPSP_FEATURE_NAMES`
5. **Determinism**: Same input produces identical output (seeds set to 42)

### Verification Commands

```bash
# Run schema validation tests (no Modal required)
uv run pytest models/deepviscosity/test_unit.py::TestDeepViscositySchemaValidation -v

# Run integration tests (requires Modal deployment)
uv run pytest models/deepviscosity/test.py -m integration -v -s

# Generate fixture outputs for verification
python models/deepviscosity/fixture.py
```

### Verification Status

**Status:** Schema validation tests pass (7/7). Numerical verification against the Lai_mAb_16 published results happens at deployment, when the model runs on GPU.

## Resource Requirements

| Resource | Value |
|----------|-------|
| GPU | None (CPU only) |
| Memory | 2048 MB |
| CPU | 1 core |
| Cold start | ~30 seconds (memory snapshot enabled) |
| Inference P50 | ~3 seconds per antibody |
| Dependencies | TensorFlow 2.11, ANARCI (bioconda), HMMER 3.3.2 |

## Implementation Notes

- Uses ANARCI for IMGT sequence numbering and alignment
- Memory snapshots enabled for fast cold starts (all 105 models loaded during snapshot)
- CPU-only inference (no GPU required)
- Ensemble predictions provide uncertainty estimate via standard deviation
- StandardScaler parameters embedded directly in code to avoid sklearn version compatibility issues
- Python 3.10 required for TensorFlow 2.11 compatibility
- Micromamba image used for bioconda package support (ANARCI, HMMER)
- Deterministic: numpy seed 42, tensorflow seed 42

## Confidence Metrics

| Metric | Range | Interpretation |
|--------|-------|----------------|
| probability_mean | 0-1 | <0.3: confident low viscosity; 0.3-0.7: uncertain; >0.7: confident high viscosity |
| probability_std | >=0 | <0.1: high ensemble agreement; 0.1-0.2: moderate; >0.2: low confidence |

Predictions with probability_mean near 0.5 and high probability_std should be validated experimentally.

## Technical Glossary

**Fv (Variable Fragment)**: The antigen-binding portion of an antibody, consisting of the VH and VL domains. This is the minimal unit required for antigen recognition.

**CDR (Complementarity-Determining Region)**: Hypervariable loops within VH/VL that form the antigen-binding surface. There are 3 CDRs per variable domain (CDR H1-H3, CDR L1-L3).

**IMGT Numbering**: A standardized residue numbering scheme for immunoglobulins maintained by the International ImMunoGeneTics information system. Enables comparison of antibodies with different sequence lengths.

**SAP (Spatial Aggregation Propensity)**: A measure of hydrophobic surface exposure calculated over antibody structural domains. Higher SAP_pos values indicate more exposed hydrophobic patches.

**SCM (Spatial Charge Map)**: A measure of surface charge distribution. SCM_neg and SCM_pos capture negative and positive charge patches, respectively.

**cP (centipoise)**: Unit of dynamic viscosity. Water at 20 C is ~1 cP. The 20 cP threshold represents a practical upper limit for subcutaneous injection through standard gauge needles.

## License

- **Code**: MIT ([LICENSE](https://github.com/Lailabcode/DeepViscosity/blob/main/LICENSE))
- **Weights**: MIT (included in repository)

## References & Citations

### Papers

1. Kalejaye LA, Chu J-M, Wu I-E et al. "Accelerating high-concentration monoclonal antibody development with large-scale viscosity data and ensemble deep learning." *mAbs* 17(1):2483944 (2025). [DOI](https://doi.org/10.1080/19420862.2025.2483944)

### BibTeX

```bibtex
@article{kalejaye2025deepviscosity,
  title={Accelerating high-concentration monoclonal antibody development with large-scale viscosity data and ensemble deep learning},
  author={Kalejaye, Lateefat A. and Chu, Jia-Min and Wu, I-En and others},
  journal={mAbs},
  volume={17},
  number={1},
  pages={2483944},
  year={2025},
  publisher={Taylor \& Francis},
  doi={10.1080/19420862.2025.2483944}
}
```

### Links

- **Paper**: [DOI 10.1080/19420862.2025.2483944](https://doi.org/10.1080/19420862.2025.2483944)
- **Code**: [GitHub Lailabcode/DeepViscosity](https://github.com/Lailabcode/DeepViscosity)

---

*See also: [MODEL.md](MODEL.md) for technical deep-dive | [BIOLOGY.md](BIOLOGY.md) for biological context*
