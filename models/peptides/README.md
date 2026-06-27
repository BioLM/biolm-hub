# peptides

> **One-line summary**: CPU-based feature extraction for peptide and protein sequences, computing physicochemical properties, amino acid frequencies, and descriptor vectors using the `peptides` Python package.

## Overview

The peptides model is a lightweight, CPU-only utility that extracts a comprehensive set of numeric and vector features from amino acid sequences. It wraps the `peptides` Python package (a Python port of the R `Peptides` package) to compute physicochemical properties, amino acid composition, and a wide range of sequence-derived descriptors.

Unlike deep learning models on the platform, this is an algorithmic feature extractor -- it uses established physicochemical scales and mathematical formulas rather than learned parameters. This makes it deterministic, fast, and useful as a feature engineering step for downstream machine learning pipelines.

## Architecture

| Property | Value |
|----------|-------|
| Architecture | Algorithmic (no neural network) |
| Parameters | None (formula-based computation) |
| Input modality | Amino acid sequences |
| Input molecule | Peptides and proteins |
| Task | Feature extraction |
| Output | Dictionary of numeric and vector features |
| Max sequence length | 2048 residues |

## Model Variants

Single variant -- no size options.

## Capabilities & Limitations

**CAN be used for:**
- Computing physicochemical properties (molecular weight, isoelectric point, hydrophobicity, charge, etc.)
- Calculating amino acid composition and frequencies for any standard amino acid sequence
- Extracting descriptor vectors (BLOSUM indices, Kidera factors, Cruciani properties, Fasgai vectors, MS-WHIM scores, VHSE scales, and more)
- Computing per-residue profiles (hydrophobicity profile, hydrophobic moment profile, linker preference profile) when `vector` mode is enabled
- Batch processing up to 10 sequences per request
- Feature engineering for downstream ML models

**CANNOT be used for:**
- Sequences longer than 2048 residues
- Non-standard amino acids beyond the extended set
- Structure prediction or 3D coordinate generation
- Sequence similarity or homology search
- Protein function prediction (features must be used as input to separate models)

**Other considerations:**
- Fully deterministic: identical inputs always produce identical outputs
- Very fast inference (milliseconds per sequence) since there is no GPU computation
- Features are based on published physicochemical scales; accuracy depends on the quality of those scales for specific applications

## Actions / Endpoints

### `encode`

Computes physicochemical features for each input amino acid sequence.

**Request Parameters:**

| Parameter | Type | Default | Range | Description |
|-----------|------|---------|-------|-------------|
| `params.include` | list[str] | [] | `["vector"]` | Include `"vector"` to also compute per-residue vector features (profiles) |
| `items[].sequence` | str | - | 1-2048 chars | Amino acid sequence using extended amino acid alphabet |

**Response:**

```json
{
  "results": [
    {
      "features": {
        "aliphatic_index": 0.0,
        "boman": 1.23,
        "charge": -0.5,
        "hydrophobicity": 0.45,
        "hydrophobic_moment": 0.32,
        "instability_index": 40.1,
        "isoelectric_point": 5.5,
        "mass_shift": 0.0,
        "molecular_weight": 3200.5,
        "mz": 1601.25,
        "A_frequency": 0.1,
        "C_frequency": 0.0,
        "BLOSUM1": -0.12,
        "BLOSUM2": 0.34
      }
    }
  ]
}
```

The `features` dictionary contains:
- **Scalar physicochemical properties**: `aliphatic_index`, `boman`, `charge`, `hydrophobicity`, `hydrophobic_moment`, `instability_index`, `isoelectric_point`, `mass_shift`, `molecular_weight`, `mz`
- **Amino acid frequencies**: One `{AA}_frequency` entry per amino acid
- **Descriptors**: Flattened dictionary of BLOSUM indices, Kidera factors, Cruciani properties, Fasgai vectors, MS-WHIM scores, VHSE scales, and more
- **Vector features** (only when `"vector"` is in `params.include`): `hydrophobicity_profile`, `hydrophobic_moment_profile`, `linker_preference_profile` as arrays of per-residue values

## Usage Examples

```python
from models.peptides.schema import (
    PeptidesEncodeRequest,
    PeptidesEncodeRequestItem,
    PeptidesEncodeRequestParams,
    PeptidesEncodeIncludeOptions,
)

# Basic physicochemical features
request = PeptidesEncodeRequest(
    items=[
        PeptidesEncodeRequestItem(sequence="ACDEFGHIKLMNPQRSTVWY"),
    ],
)

# Include per-residue vector profiles
request_with_vectors = PeptidesEncodeRequest(
    params=PeptidesEncodeRequestParams(
        include=[PeptidesEncodeIncludeOptions.VECTOR],
    ),
    items=[
        PeptidesEncodeRequestItem(sequence="ACDEFGHIKLMNPQRSTVWY"),
        PeptidesEncodeRequestItem(sequence="MKTVRQERLKSIVRILERSKEPVSG"),
    ],
)
```

## Performance & Benchmarks

### Published Results

The `peptides` package implements well-established physicochemical scales and indices from the biochemistry literature. These are not learned predictions but direct calculations from published amino acid property tables. Accuracy depends on the applicability of each scale to the specific use case.

Key feature categories and their sources:
- **Boman index**: Boman (2003) -- potential protein interaction index
- **Instability index**: Guruprasad et al. (1990) -- in vivo protein half-life predictor
- **BLOSUM indices**: Derived from BLOSUM substitution matrices
- **Kidera factors**: Kidera et al. (1985) -- 10 orthogonal factors from 188 physical properties
- **VHSE scales**: Mei et al. (2005) -- principal components of 18 hydrophobicity scales

### SOTA Status

Not applicable. This is a feature extraction utility, not a predictive model. The computed features are inputs for downstream analysis, not predictions themselves.

## Implementation Verification

### Verification Method

Option A (Numerical Reproduction): The BioLM implementation wraps the official `peptides==0.3.4` Python package. Feature values are computed by calling the library functions directly, with numpy float conversion for serialization. Results are numerically identical to calling the `peptides` library locally.

### Verification Status

**Status: VERIFIED** -- Direct wrapper around the published `peptides` library with no modifications to computation logic. Only serialization (numpy to Python float conversion) is applied to outputs.

## Resource Requirements

| Resource | Value |
|----------|-------|
| GPU | None (CPU only) |
| Memory | 1 GB |
| CPU | 0.125 cores |
| Cold start | ~5-10 seconds (memory snapshot enabled) |
| Inference P50 | <50ms |
| Dependencies | `peptides==0.3.4` |

## Implementation Notes

- **Memory snapshots**: Uses `@modal.enter(snap=True)` to import the `peptides` library. The `snap=False` phase is a no-op since there is no GPU setup.
- **Determinism**: Fully deterministic. All computations are formula-based with no random components.
- **Numpy conversion**: All numpy float values are explicitly converted to Python `float32` for JSON serialization compatibility.
- **Batch processing**: Processes up to 10 sequences per request. Each sequence is computed independently.
- **Feature flattening**: The `descriptors` dictionary is flattened into the top-level features dict. Amino acid frequencies are renamed with `_frequency` suffix.

## Technical Glossary

**Aliphatic index**: Relative volume occupied by aliphatic side chains (Ala, Val, Ile, Leu). Higher values indicate greater thermostability.

**Boman index**: Potential protein-protein interaction index based on solubility values of amino acid side chains. Higher values suggest greater binding potential.

**Instability index**: Predicts whether a protein is stable in vitro. Values below 40 suggest a stable protein.

**Isoelectric point (pI)**: pH at which the protein has no net electrical charge. Important for purification and solubility prediction.

**Kidera factors**: Ten orthogonal factors derived from 188 physicochemical properties of amino acids, capturing helix/bend preference, side chain size, extended structure preference, hydrophobicity, double-bend preference, partial specific volume, flat extended preference, occurrence in alpha region, pK-C, and surrounding hydrophobicity.

**VHSE scales**: Vectors of Hydrophobic, Steric, and Electronic properties derived from principal component analysis of 18 hydrophobicity scales, ## steric parameters, and electronic properties.

## License

- **Code**: Apache-2.0 ([LICENSE](https://github.com/dosorio/Peptides.py/blob/master/LICENSE))
- **Library**: Apache-2.0 (peptides Python package)

## References & Citations

### Papers

1. Osorio D, Rondon-Villarreal P, Torres R. "Peptides: A Package for Data Mining of Antimicrobial Peptides." *The R Journal* (2015). [DOI: 10.32614/RJ-2015-001](https://doi.org/10.32614/RJ-2015-001)

### BibTeX

```bibtex
@article{osorio2015peptides,
  title={Peptides: A Package for Data Mining of Antimicrobial Peptides},
  author={Osorio, Daniel and Rondon-Villarreal, Paola and Torres, Rodrigo},
  journal={The R Journal},
  volume={7},
  number={1},
  pages={4--14},
  year={2015},
  doi={10.32614/RJ-2015-001}
}
```

### Links

- **Paper**: [The R Journal](https://doi.org/10.32614/RJ-2015-001)
- **Code (Python)**: [GitHub dosorio/Peptides.py](https://github.com/dosorio/Peptides.py)
- **PyPI**: [peptides](https://pypi.org/project/peptides/)

---

*See also: [MODEL.md](MODEL.md) for technical deep-dive | [BIOLOGY.md](BIOLOGY.md) for biological context*
