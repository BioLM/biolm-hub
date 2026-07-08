# ImmuneFold

> **One-line summary**: PLM-enhanced antibody and TCR structure prediction model that combines ESM-2 3B representations with immune-protein-specific structural supervision for high-accuracy folding.

## Overview

ImmuneFold is a structure prediction model developed by Wu et al. (2024) at CarbonMatrix Lab. It integrates ESM-2 (3B parameter protein language model) embeddings with a Transformer+GNN structure prediction module, achieving state-of-the-art accuracy on antibody and TCR structure prediction benchmarks. The model supports paired antibodies (VH/VL), nanobodies (VH-only), antibody-antigen complexes (with antigen PDB), and alpha/beta TCRs (with peptide-MHC context).

## Architecture

| Property | Value |
|----------|-------|
| Sequence encoder | ESM-2 3B (esm2_t36_3B_UR50D) |
| Structure module | Transformer + GNN hybrid |
| Input | Amino acid sequences (+ optional antigen PDB) |
| Output | PDB structure, pTM, full pLDDT, per-residue pLDDT |
| Confidence metrics | pTM (global), pLDDT (per-residue) |

## Model Variants

| Variant Slug | Chain Input | Molecule Type | GPU | Memory |
|-------------|-------------|---------------|-----|--------|
| `immunefold-antibody` | H (+ optional L, pdb) | Antibody, nanobody, antibody-antigen complex | T4 | 16 GB |
| `immunefold-tcr` | B + A + P + M | TCR (alpha/beta with pMHC) | T4 | 16 GB |

## Capabilities & Limitations

**CAN be used for:**
- Predicting paired antibody (VH/VL) structures with confidence scores
- Predicting nanobody (VHH) structures from heavy chain only
- Predicting antibody-antigen complex structures when antigen PDB is provided
- Predicting alpha/beta TCR structures with peptide-MHC context
- Assessing prediction confidence via pTM and pLDDT scores

**CANNOT be used for:**
- General protein structure prediction (use AlphaFold2 or ESMFold)
- Sequence design or inverse folding (use AntiFold)
- Gamma/delta TCR prediction
- Structures without sequences (requires amino acid input)
- Sequences shorter than minimum lengths (VH < 90, VL < 85 AA)

## Actions / Endpoints

### `fold`

Predict 3D structure from immune protein sequences with confidence scores.

**Request Parameters:**

| Parameter | Type | Default | Range | Description |
|-----------|------|---------|-------|-------------|
| `items[].heavy_chain` | str | None | 90--256 AA | Heavy chain sequence (antibodies, nanobodies); legacy alias `H` |
| `items[].light_chain` | str | None | 85--256 AA | Light chain sequence (paired antibodies); legacy alias `L` |
| `items[].tcr_beta` | str | None | 1--256 AA | Beta chain sequence (TCRs); legacy alias `B` |
| `items[].tcr_alpha` | str | None | 1--256 AA | Alpha chain sequence (TCRs); legacy alias `A` |
| `items[].peptide` | str | None | 1--256 AA | Peptide sequence (TCRs); legacy alias `P` |
| `items[].mhc` | str | None | 1--256 AA | MHC sequence (TCRs); legacy alias `M` |
| `items[].pdb` | str | None | Valid PDB | Antigen PDB structure (antibody-antigen mode) |
| `params.contact_idx` | int | None | -- | Contact index for antibody-antigen prediction |

**Chain combination rules:**
- `heavy_chain` + `light_chain` => paired antibody
- `heavy_chain` only => nanobody
- `heavy_chain` + `light_chain` + `pdb` => antibody-antigen complex
- `tcr_beta` + `tcr_alpha` + `peptide` + `mhc` => TCR (all four required)
- Cannot mix antibody chains (`heavy_chain`/`light_chain`) with TCR chains (`tcr_beta`/`tcr_alpha`/`peptide`/`mhc`)

**Request Schema:** `ImmuneFoldPredictRequest`

**Response:**

```json
{
  "results": [
    {
      "ptm": 0.85,
      "mean_plddt": 82.5,
      "plddt": [[92.1, 88.3, ...]],
      "pdb": "ATOM      1  N   GLY H   1 ..."
    }
  ]
}
```

**Response Schema:** `ImmuneFoldPredictResponse`

## Usage Examples

### Paired antibody structure

```python
from models.immunefold.schema import (
    ImmuneFoldPredictRequest,
    ImmuneFoldPredictRequestItem,
)

request = ImmuneFoldPredictRequest(
    items=[
        ImmuneFoldPredictRequestItem(
            heavy_chain="EVQLVESGGGLVQPGGSLRLSCAASGFTFSDYAMSWVRQAPGKGLEWVSGISGSGGSTYYADSVKGRFTISRDNSKNTLYLQMNSLRAEDTAVYYCAKDRLSITIRPRYYGLDVWGQGTTVTVSS",
            light_chain="DIQMTQSPSSLSASVGDRVTITCRASQSISSYLNWYQQKPGKAPKLLIYAASSLQSGVPSRFSGSGSGTDFTLTISSLQPEDFATYYCQQSYSTPLTFGGGTKVEIK",
        )
    ],
)
```

### Nanobody structure

```python
request = ImmuneFoldPredictRequest(
    items=[
        ImmuneFoldPredictRequestItem(
            heavy_chain="QVQLQESGGGLVQPGGSLRLSCAASGRTFSSYAMGWFRQAPGKEREFVAAISWSGGSTYYADSVKGRFTISRDNAKNTVYLQMNSLKPEDTAVYYCAADSTIYASYYECGHGLSTGGYGYDSWGQGTQVTVSS",
        )
    ],
)
```

### TCR structure with peptide-MHC

```python
request = ImmuneFoldPredictRequest(
    items=[
        ImmuneFoldPredictRequestItem(
            tcr_beta="DAGVTQTPRNHVTISEGDKITVRCEKSTVSNFLYELFWYRQDPGLGLRLIYFSYDVKMKEKGDIPDGYSVSRNKKPNFYEALISKLNVSDSALYFCASSQETQYFGPGTRLTVL",
            tcr_alpha="AQEVTQIPAALSVPEGENLVLNCSFTDSAIYNLQWFRQDPGKGLTSLLLIQSSQREQTSGRLNASLDKSSGRSTLYIAASQPGDSATYLCAVRPTSGGSYIPTFGRGTSLIVHPY",
            peptide="GILGFVFTL",
            mhc="GSHSMRYFFTSVSRPGRGEPRFIAVGYVDDTQFVRFDSDAASQRMEPRAPWIEQEGPEYWDGETRKVKAHSQTHRVDLGTLRGYYNQSEAGSHTVQRMYGCDVGSDWRFLRGYHQYAYDGKDY",
        )
    ],
)
```

## Performance & Benchmarks

### Published Results

From Wu et al., *bioRxiv* (2024):

| Model | CDR-H3 RMSD (A) | Overall RMSD (A) | Notes |
|-------|------------------|-------------------|-------|
| **ImmuneFold** | **~2.0** | **~1.2** | PLM-enhanced |
| ABodyBuilder2 | ~2.8 | ~1.5 | ImmuneBuilder |
| AlphaFold2 | ~3.4 | ~1.8 | General-purpose |

### SOTA Status

ImmuneFold represents the current state-of-the-art for single-sequence immune protein structure prediction as of its publication in late 2024.

## Implementation Verification

### Verification Method

Numerical reproduction: BioLM outputs compared against golden outputs with tight PDB RMSD tolerances.

### Test Cases

| Variant | Test Case | Tolerance | Status |
|---------|-----------|-----------|--------|
| antibody | Paired VH/VL | rel_tol 1e-4, PDB RMSD < 1e-4A | PASS |
| antibody | Nanobody (VH only) | rel_tol 1e-4, PDB RMSD < 1e-4A | PASS |
| antibody | Antigen complex | rel_tol 1e-4, PDB RMSD < 1e-4A | PASS |
| tcr | Alpha/beta TCR with pMHC | rel_tol 1e-4, PDB RMSD < 1e-4A | PASS |

### Verification Status

**Status: VERIFIED** -- All 4 test cases pass across both variants.

## Resource Requirements

| Resource | Value |
|----------|-------|
| GPU | T4 (16 GB VRAM) |
| Memory | 16 GB RAM |
| CPU | 3.0 cores |
| Max batch size | 32 |
| Max sequence length | 256 per chain |
| Memory snapshot | Enabled with GPU snapshot |

## Implementation Notes

- **Memory snapshots**: Uses `@modal.enter(snap=True)` with `ModelMixinSnap` and GPU snapshot for fast cold starts.
- **Container image**: Based on micromamba; clones ImmuneFold from GitHub at commit `b6d916f`.
- **External dependencies**: ESM-2 3B model (`fair-esm` package), Hydra config system, OmegaConf.
- **External modifications**: `models/immunefold/external/inference.py` replaces the original inference script for API compatibility.
- **Dependencies**: Pinned pip packages (see `app.py` image build): `torch==2.1.2` + CUDA 12, `fair-esm`, Hydra, OmegaConf, plus bioconda tools (hmmer, hhsuite, kalign2, anarci) via micromamba.
- **Model weights**: Two checkpoints downloaded from R2: `immunefold-ab.ckpt` (antibody) and `immunefold-tcr.ckpt` (TCR), plus `esm2_t36_3B_UR50D.pt`.
- **Config system**: Hydra configs loaded from `immunefold/config/` with runtime overrides for model paths and parameters.

## License

- **Code**: Apache-2.0 ([LICENSE](https://github.com/CarbonMatrixLab/immunefold/blob/main/LICENSE))

## References & Citations

### Papers

1. Wu J, Liu C, Zhang G. "ImmuneFold: Improved antibody and TCR structure prediction with a pre-trained protein language model." *bioRxiv* (2024). [DOI: 10.1101/2024.12.23.630212](https://doi.org/10.1101/2024.12.23.630212)

### BibTeX

```bibtex
@article{wu2024immunefold,
  title={ImmuneFold: Improved antibody and TCR structure prediction with a pre-trained protein language model},
  author={Wu, Jiaxiang and Liu, Chenguang and Zhang, Guijun},
  journal={bioRxiv},
  year={2024},
  doi={10.1101/2024.12.23.630212}
}
```

### Links

- **Code**: [GitHub CarbonMatrixLab/immunefold](https://github.com/CarbonMatrixLab/immunefold)

---

*See also: [MODEL.md](MODEL.md) for technical deep-dive | [BIOLOGY.md](BIOLOGY.md) for biological context*
