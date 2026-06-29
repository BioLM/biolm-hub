# ABodyBuilder3

> **One-line summary**: Antibody structure prediction model that predicts 3D Fv region coordinates from paired heavy/light chain sequences using a GNN architecture with optional ProtT5 language model embeddings.

## Overview

AbodyBuilder3 is an antibody structure prediction model developed by Exscientia (Kenlay et al. 2024). Given paired heavy (H) and light (L) chain amino acid sequences, it predicts the 3D atomic coordinates of the antibody Fv region and outputs a PDB structure file. It offers two model variants: a "language" variant that incorporates ProtT5 protein language model embeddings for higher accuracy, and a "plddt" variant that provides faster inference with confidence estimation.

## Architecture

| Property | Value |
|----------|-------|
| Architecture | Graph Neural Network (GNN) |
| Language variant | GNN + ProtT5 language model embeddings (GPU required) |
| pLDDT variant | GNN with confidence estimation (CPU-only) |
| Framework | PyTorch Lightning (LitABB3) |
| Input | Paired H and L chain amino acid sequences |
| Output | PDB structure string, optional pLDDT scores |

## Model Variants

| Variant | Slug | GPU | Description |
|---------|------|-----|-------------|
| language | `abodybuilder3-language` | L40S | Higher accuracy, uses ProtT5 embeddings |
| plddt | `abodybuilder3-plddt` | None (CPU) | Faster, lightweight with confidence scores |

## Capabilities & Limitations

**CAN be used for:**
- Predicting 3D Fv structures from paired heavy/light chain sequences
- Obtaining per-residue pLDDT confidence scores (via `params.plddt=true`)
- Generating PDB files for downstream structure-based analysis
- Batch processing up to 4 antibody sequence pairs per request
- Deterministic predictions with configurable random seed

**CANNOT be used for:**
- Single-chain inputs or nanobody (VHH) structure prediction
- Antibody-antigen complex structure prediction
- Constant region (Fc/CH/CL) structure prediction
- General protein structure prediction (antibody-specific only)
- Sequences containing non-standard amino acids

## Actions / Endpoints

### `fold`

Predict 3D structure of an antibody Fv region from paired sequences.

**Request Parameters:**

| Parameter | Type | Default | Range | Description |
|-----------|------|---------|-------|-------------|
| `params.plddt` | bool | false | true/false | Whether to include per-residue pLDDT scores |
| `params.seed` | int | 42 | Any int or null | Random seed for reproducibility |
| `items` | list[AbodyBuilder3PredictRequestItem] | (required) | 1--4 items | List of paired heavy/light chain sequences |
| `items[].heavy_chain` | str | (required) | 1--2048 chars | Heavy chain amino acid sequence (legacy alias: `H`) |
| `items[].light_chain` | str | (required) | 1--2048 chars | Light chain amino acid sequence (legacy alias: `L`) |

**Response:**

```json
{
  "results": [
    {
      "pdb": "ATOM      1  N   GLU H   1      ...",
      "plddt": [85.2, 92.1, 78.4, 88.3, ...]
    }
  ]
}
```

- `pdb`: Full PDB-format structure string with predicted atom coordinates
- `plddt`: Per-residue pLDDT confidence scores (only present when `params.plddt=true`). Flat list of floats (0--100 scale, higher is more confident), one value per residue of the combined Fv sequence (heavy chain followed by light chain)

## Usage Examples

### Predict antibody structure

```python
from models.abodybuilder3.schema import (
    AbodyBuilder3PredictRequest,
    AbodyBuilder3PredictRequestItem,
    AbodyBuilder3PredictRequestParams,
)

request = AbodyBuilder3PredictRequest(
    params=AbodyBuilder3PredictRequestParams(plddt=False, seed=42),
    items=[
        AbodyBuilder3PredictRequestItem(
            heavy_chain="EVQLVESGGGLVQPGGSLRLSCAASGFTFSSYAMSWVRQAPGKGLEWVSAISGSGGSTYYADSVKGRFTISRDNSKNTLYLQMNSLRAEDTAVYYCAR",
            light_chain="DIQMTQSPSSLSASVGDRVTITCRASQSISSYLNWYQQKPGKAPKLLIYAASSLQSGVPSRFSGSGSGTDFTLTISSLQPEDFATYYCQQSYSTPLT",
        )
    ],
)
```

### Predict structure with pLDDT confidence scores

```python
from models.abodybuilder3.schema import (
    AbodyBuilder3PredictRequest,
    AbodyBuilder3PredictRequestItem,
    AbodyBuilder3PredictRequestParams,
)

request = AbodyBuilder3PredictRequest(
    params=AbodyBuilder3PredictRequestParams(plddt=True, seed=42),
    items=[
        AbodyBuilder3PredictRequestItem(
            heavy_chain="QVQLQQSGPGLVKPSQTLSLTCAISGDSVSSNSAAWNWIRQSPSRGLEWLGRTYYRSKWYNDYAVSVKSRITINPDTSKNQFSLQLNSVTPEDTAVYYCAR",
            light_chain="EIVLTQSPGTLSLSPGERATLSCRASQSVSSSYLAWYQQKPGQAPRLLIYGASSRATGIPDRFSGSGSGTDFTLTISRLEPEDFAVYYCQQYGSSPRT",
        )
    ],
)
```

## Performance & Benchmarks

### Published Results

From Kenlay et al., *Bioinformatics* (2024):

AbodyBuilder3 achieves improved and scalable antibody structure predictions compared to prior methods, with particular strengths in CDR loop modeling accuracy and inference speed.

See `sources.yaml` applied_literature for benchmark results from published comparisons, including per-CDR backbone RMSD reported in Dreyer et al. (mAbs, 2025).

### SOTA Status

AbodyBuilder3 represents a competitive method for antibody structure prediction as of 2024, offering a favorable accuracy/speed tradeoff compared to AlphaFold2-based approaches.

## Implementation Verification

### Verification Method

Option A -- Numerical Reproduction: outputs from the BioLM implementation are compared against golden outputs from the original AbodyBuilder3 codebase.

### Test Cases

| Input | Action | Tolerance | Status |
|-------|--------|-----------|--------|
| Standard antibody pair | fold | rel_tol 1e-3, cosine_distance < 0.02, PDB RMSD < 0.05 A | PASS |

### Verification Status

**Status: VERIFIED** -- Structure predictions match reference implementation within tolerance.

## Resource Requirements

| Resource | Language Variant | pLDDT Variant |
|----------|-----------------|---------------|
| GPU | L40S (48 GB VRAM) | None (CPU-only) |
| Memory | 12 GB | 8 GB |
| CPU | 4.0 cores | 2.0 cores |
| Batch size | 4 | 4 |
| Memory snapshot | Enabled (GPU snapshot) | Enabled |

## Implementation Notes

- **Memory snapshots**: Uses `@modal.enter(snap=True)` with GPU memory snapshot enabled (`enable_gpu_snapshot=True`) for fast cold starts. Models are loaded directly on GPU during snapshot.
- **Container image**: Uses `modal.Image.micromamba(python_version="3.10")` with OpenMM 8.1.1 from conda-forge and the AbodyBuilder3 repository cloned at commit `18e4058`.
- **External code**: The full AbodyBuilder3 repository is cloned and installed as an editable package (`pip install -e ".[dev]"`). The container's working directory is set to the cloned repo for relative imports.
- **Determinism**: Comprehensive seeding across Python random, NumPy, PyTorch, and PyTorch Lightning. cuDNN deterministic mode enabled with benchmarking disabled.
- **ProtT5 (language variant)**: The ProtT5 language model is loaded from local weights at `{model_dir}/prott5/` and produces per-residue embeddings that augment the GNN input.
- **Dependencies**: Managed via `environment_gpu.yml` (micromamba) and `pinned-versions.txt` (pip). Includes a workaround for charset_normalizer conda/pip conflict.

## License

- **License**: Apache-2.0 ([GitHub](https://github.com/Exscientia/abodybuilder3/blob/main/LICENSE))

## References & Citations

### Papers

1. Kenlay H, Dreyer FA, Krawczyk K, Sherborne B, Deane CM. "ABodyBuilder3: Improved and scalable antibody structure predictions." *Bioinformatics* (2024). [DOI: 10.1093/bioinformatics/btae576](https://doi.org/10.1093/bioinformatics/btae576)

### BibTeX

```bibtex
@article{kenlay2024abodybuilder3,
  title={ABodyBuilder3: Improved and scalable antibody structure predictions},
  author={Kenlay, Henry and Dreyer, Frédéric A and Krawczyk, Konrad and Sherborne, Bryn and Deane, Charlotte M},
  journal={Bioinformatics},
  year={2024},
  doi={10.1093/bioinformatics/btae576}
}
```

### Links

- **Paper**: [arXiv:2405.20863](https://arxiv.org/abs/2405.20863)
- **Code**: [GitHub Exscientia/abodybuilder3](https://github.com/Exscientia/abodybuilder3)

---

*See also: [MODEL.md](MODEL.md) for technical deep-dive | [BIOLOGY.md](BIOLOGY.md) for biological context*
