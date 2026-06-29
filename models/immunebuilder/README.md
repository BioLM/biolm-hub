# ImmuneBuilder

> **One-line summary**: Ensemble of EGNN-based deep learning models for predicting 3D structures of antibodies, nanobodies, and T-cell receptors from sequence alone.

## Overview

ImmuneBuilder is a structure prediction framework developed by Abanades et al. (2023) at the Oxford Protein Informatics Group (OPIG). It comprises four specialized sub-models -- ABodyBuilder2 (paired antibody), NanoBodyBuilder2 (single-domain nanobody), TCRBuilder2 (alpha/beta TCR), and TCRBuilder2Plus (improved TCR) -- each trained on curated immune protein structural databases using equivariant graph neural networks (EGNNs).

Given amino acid sequences for the appropriate chain pair, ImmuneBuilder predicts full-atom 3D structures in PDB format. No MSA or template structure is required. Structures are refined via OpenMM energy minimization for physically realistic geometries.

## Architecture

| Property | Value |
|----------|-------|
| Architecture | Equivariant Graph Neural Network (EGNN) ensemble (4 models per variant) |
| Training data | SAbDab (antibodies/nanobodies), STCRDab (TCRs) |
| Input | Amino acid sequences (single-letter code) |
| Output | PDB-format 3D atomic coordinates |
| Post-processing | OpenMM AMBER force field energy minimization |

## Model Variants

| Variant Slug | Chain Input | Molecule Type | GPU | Memory |
|-------------|-------------|---------------|-----|--------|
| `immunebuilder-abodybuilder2` | H + L | Antibody (VH/VL) | None | 8 GB |
| `immunebuilder-nanobodybuilder2` | H only | Nanobody (VHH) | None | 8 GB |
| `immunebuilder-tcrbuilder2` | A + B | TCR (alpha/beta) | None | 8 GB |
| `immunebuilder-tcrbuilder2plus` | A + B | TCR (alpha/beta, improved) | None | 8 GB |

All variants run on CPU only (no GPU required).

## Capabilities & Limitations

**CAN be used for:**
- Predicting 3D structures of antibodies from paired VH/VL sequences
- Predicting nanobody (VHH) structures from heavy chain sequence only
- Predicting alpha/beta TCR structures from paired alpha and beta chain sequences
- Providing input structures for downstream tools (ProperMAB, AntiFold, docking)

**CANNOT be used for:**
- General protein structure prediction (use AlphaFold2 or ESMFold)
- Antibody-antigen complex prediction (use ImmuneFold with antigen PDB)
- Gamma/delta TCR prediction
- Constant region (Fc) structure prediction
- Sequence design or inverse folding (use AntiFold)

## Actions / Endpoints

### `fold`

Predict 3D structure from immune protein sequences.

**Request Parameters:**

| Parameter | Type | Default | Range | Description |
|-----------|------|---------|-------|-------------|
| `items[].heavy_chain` | str | None | 1--2048 AA | Heavy chain sequence (antibodies, nanobodies); legacy alias `H` |
| `items[].light_chain` | str | None | 1--2048 AA | Light chain sequence (antibodies); legacy alias `L` |
| `items[].tcr_alpha` | str | None | 1--2048 AA | Alpha chain sequence (TCRs); legacy alias `A` |
| `items[].tcr_beta` | str | None | 1--2048 AA | Beta chain sequence (TCRs); legacy alias `B` |
| `params.seed` | int | 42 | >= 0 | Random seed for reproducibility |

**Chain combination rules:**
- `heavy_chain` + `light_chain` => ABodyBuilder2 (antibody)
- `heavy_chain` only => NanoBodyBuilder2 (nanobody)
- `tcr_alpha` + `tcr_beta` => TCRBuilder2 / TCRBuilder2Plus (TCR)
- Cannot mix antibody chains (`heavy_chain`/`light_chain`) with TCR chains (`tcr_alpha`/`tcr_beta`)

**Request Schema:** `ImmuneBuilderPredictRequest`

**Response:**

```json
{
  "results": [
    {
      "pdb": "ATOM      1  N   GLY H   1 ..."
    }
  ]
}
```

**Response Schema:** `ImmuneBuilderPredictResponse`

## Usage Examples

### Antibody structure prediction

```python
from models.immunebuilder.schema import (
    ImmuneBuilderPredictRequest,
    ImmuneBuilderPredictRequestItem,
    ImmuneBuilderPredictParams,
)

request = ImmuneBuilderPredictRequest(
    items=[
        ImmuneBuilderPredictRequestItem(
            heavy_chain="EVQLVESGGGLVQPGGSLRLSCAASGFTFSDYAMSWVRQAPGKGLEWVSGISGSGGSTYYADSVKGRFTISRDNSKNTLYLQMNSLRAEDTAVYYCAKDRLSITIRPRYYGLDVWGQGTTVTVSS",
            light_chain="DIQMTQSPSSLSASVGDRVTITCRASQSISSYLNWYQQKPGKAPKLLIYAASSLQSGVPSRFSGSGSGTDFTLTISSLQPEDFATYYCQQSYSTPLTFGGGTKVEIK",
        )
    ],
    params=ImmuneBuilderPredictParams(seed=42),
)
```

### Nanobody structure prediction

```python
request = ImmuneBuilderPredictRequest(
    items=[
        ImmuneBuilderPredictRequestItem(
            heavy_chain="QVQLQESGGGLVQPGGSLRLSCAASGRTFSSYAMGWFRQAPGKEREFVAAISWSGGSTYYADSVKGRFTISRDNAKNTVYLQMNSLKPEDTAVYYCAADSTIYASYYECGHGLSTGGYGYDSWGQGTQVTVSS",
        )
    ],
)
```

### TCR structure prediction

```python
request = ImmuneBuilderPredictRequest(
    items=[
        ImmuneBuilderPredictRequestItem(
            tcr_alpha="AQEVTQIPAALSVPEGENLVLNCSFTDSAIYNLQWFRQDPGKGLTSLLLIQSSQREQTSGRLNASLDKSSGRSTLYIAASQPGDSATYLCAVRPTSGGSYIPTFGRGTSLIVHPY",
            tcr_beta="DAGVTQTPRNHVTISEGDKITVRCEKSTVSNFLYELFWYRQDPGLGLRLIYFSYDVKMKEKGDIPDGYSVSRNKKPNFYEALISKLNVSDSALYFCASSQETQYFGPGTRLTVL",
        )
    ],
)
```

## Performance & Benchmarks

### Published Results

From Abanades et al., *Communications Biology* (2023):

| Model | CDR-H3 RMSD (A) | Overall RMSD (A) | Dataset |
|-------|------------------|-------------------|---------|
| **ABodyBuilder2** | **2.81** | **~1.5** | SAbDab test set |
| AlphaFold2 | 3.42 | ~1.8 | SAbDab test set |

### SOTA Status

ImmuneBuilder represented the state-of-the-art for single-sequence immune protein structure prediction at its publication in 2023. ImmuneFold (2024) has since achieved improved accuracy using protein language model pre-training.

## Implementation Verification

### Verification Method

Numerical reproduction: outputs compared against golden outputs on identical inputs, with PDB RMSD threshold of 1.5 Angstroms (to accommodate platform/CUDA/OpenMM numeric drift).

### Test Cases

| Variant | Action | Tolerance | Status |
|---------|--------|-----------|--------|
| abodybuilder2 | fold | rel_tol 1e-4, PDB RMSD < 1.5 Å | PASS |
| nanobodybuilder2 | fold | rel_tol 1e-4, PDB RMSD < 1.5 Å | PASS |
| tcrbuilder2 | fold | rel_tol 1e-4, PDB RMSD < 1.5 Å | PASS |
| tcrbuilder2plus | fold | rel_tol 1e-4, PDB RMSD < 1.5 Å | PASS |

### Verification Status

**Status: VERIFIED** -- All 4 variant test cases pass.

## Resource Requirements

| Resource | Value |
|----------|-------|
| GPU | None (CPU-only for all variants) |
| Memory | 8 GB per variant |
| CPU | 2.0 cores per variant |
| Max batch size | 8 |
| Max sequence length | 2048 residues per chain |
| Memory snapshot | Enabled |

## Implementation Notes

- **Memory snapshots**: Uses `@modal.enter(snap=True)` with `ModelMixinSnap` for fast cold starts.
- **Container image**: Based on micromamba with Python 3.12, includes OpenMM, pdbfixer, HMMER 3.3.2, ANARCI, and BioPython via conda-forge.
- **Model weights**: Downloaded from R2 storage with Zenodo fallback. Each variant has 4 ensemble weight files.
- **Dependencies**: `ImmuneBuilder==1.2`, `anarci==2026.2.13.2`, OpenMM (conda-forge), HMMER 3.3.2 (bioconda).
- **Determinism**: Full seed control across Python random, NumPy, PyTorch, and cuDNN. Default seed is 42.

## License

- **Code**: BSD-3-Clause ([LICENSE](https://github.com/oxpig/ImmuneBuilder/blob/main/LICENSE))

## References & Citations

### Papers

1. Abanades B, Wong WK, Boyles F, Georges G, Bujotzek A, Deane CM. "ImmuneBuilder: Deep-Learning models for predicting the structures of immune proteins." *Communications Biology* 6, 575 (2023). [DOI: 10.1038/s42003-023-04927-7](https://doi.org/10.1038/s42003-023-04927-7)

### BibTeX

```bibtex
@article{abanades2023immunebuilder,
  title={ImmuneBuilder: Deep-Learning models for predicting the structures of immune proteins},
  author={Abanades, Brennan and Wong, Wing Ki and Boyles, Fergus and Georges, Guy and Bujotzek, Alexander and Deane, Charlotte M},
  journal={Communications Biology},
  volume={6},
  pages={575},
  year={2023},
  doi={10.1038/s42003-023-04927-7}
}
```

### Links

- **Paper**: [arXiv:2301.08423](https://arxiv.org/abs/2301.08423)
- **Code**: [GitHub oxpig/ImmuneBuilder](https://github.com/oxpig/ImmuneBuilder)
- **PyPI**: [ImmuneBuilder](https://pypi.org/project/ImmuneBuilder/)

---

*See also: [MODEL.md](MODEL.md) for technical deep-dive | [BIOLOGY.md](BIOLOGY.md) for biological context*
