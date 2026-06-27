# ESMFold

> **One-line summary**: Single-sequence protein structure prediction model that uses the ESM-2 language model backbone to predict 3D atomic coordinates without requiring multiple sequence alignments.

## Overview

ESMFold is a protein structure prediction model developed by Meta AI's Fundamental AI Research (FAIR) team. It predicts full-atom 3D protein structures directly from amino acid sequences, bypassing the multiple sequence alignment (MSA) step that makes AlphaFold2 and similar methods slow. ESMFold achieves this by coupling the ESM-2 protein language model (3B parameters) with a folding module derived from AlphaFold2's architecture.

The key advantage of ESMFold is speed: predictions take seconds rather than minutes or hours, making it suitable for large-scale structural screening and rapid prototyping. While its accuracy is somewhat lower than MSA-dependent methods, it provides reliable predictions for most well-characterized protein families.

ESMFold is described in the same paper as ESM-2: Lin et al., "Evolutionary-scale prediction of atomic-level protein structure with a language model," *Science* (2023). The model shares the ESM-2 language model backbone with the ESM-2 embedding model available on this platform.

## Architecture

| Property | Value |
|----------|-------|
| Architecture | ESM-2 transformer encoder + AlphaFold2-derived folding trunk |
| Language model backbone | ESM-2 3B (36 layers, 2560 hidden dim) |
| Total parameters | ~3B |
| Training data | UniRef50 (language model) + PDB + AlphaFold2 distillation (folding trunk) |
| Max sequence length | 768 residues |
| Max chains | 4 (concatenated with `:` separator) |
| License | MIT |

See [MODEL.md](MODEL.md) for detailed architecture description.

## Model Variants

Single variant -- no size options. ESMFold uses the ESM-2 3B backbone exclusively.

## Capabilities & Limitations

**CAN be used for:**
- Predicting 3D protein structures from single amino acid sequences
- Multi-chain protein complex prediction (up to 4 chains, 768 residues total)
- Rapid structural screening of large protein sets
- Assessing fold confidence via pLDDT and pTM scores
- Quick structural validation of protein engineering candidates

**CANNOT be used for:**
- Protein-ligand complex prediction (use Boltz or Chai-1 instead)
- Nucleic acid structure prediction (use Boltz or Chai-1 instead)
- Sequences longer than 768 residues
- Complexes with more than 4 chains
- Generating protein embeddings (use ESM-2 `encode` action instead)
- Sequence design or generation

**Other considerations:**
- Accuracy is lower than MSA-dependent methods (AlphaFold2, Boltz) for most targets
- Performance degrades for proteins with few homologs in UniRef50
- The model uses GPU memory snapshots for fast cold starts
- Batch size is capped at 2 sequences per request
- CUDA out-of-memory errors for long sequences return empty results (pdb="", mean_plddt=0.0, ptm=0.0) rather than crashing

## Actions / Endpoints

### `predict`

Predicts the 3D structure of one or more protein sequences. Returns PDB-formatted coordinates with confidence scores.

**Request Parameters:**

| Parameter | Type | Default | Range | Description |
|-----------|------|---------|-------|-------------|
| `items[].sequence` | str | Required | 1-771 characters | Amino acid sequence. For multi-chain input, separate chains with `:` (up to 4 chains, 768 total residues + up to 3 separators). Standard and extended amino acid alphabet accepted. |

**Batch limits:**
- Maximum 2 items per request (`batch_size = 2`)

**Response:**

```json
{
  "results": [
    {
      "pdb": "ATOM      1  N   MET A   1      ...",
      "mean_plddt": 0.85,
      "ptm": 0.78
    }
  ]
}
```

| Field | Type | Description |
|-------|------|-------------|
| `pdb` | str | Full-atom 3D structure in PDB format |
| `mean_plddt` | float | Mean predicted Local Distance Difference Test score (0-1). Higher indicates more confident per-residue predictions. |
| `ptm` | float | Predicted TM-score (0-1). Higher indicates more confident overall fold topology. |

## Confidence Metrics

| Metric | Range | Interpretation |
|--------|-------|----------------|
| pLDDT (per-residue, reported as mean_plddt) | 0-1 | > 0.9: very high confidence; 0.7-0.9: confident; 0.5-0.7: low confidence; < 0.5: likely disordered or misfolded |
| pTM | 0-1 | > 0.8: high confidence in overall fold; 0.5-0.8: moderate confidence; < 0.5: fold topology may be incorrect |

## Usage Examples

```python
# Single-chain structure prediction
from models.esmfold.schema import (
    ESMFoldPredictRequest,
    ESMFoldPredictRequestItem,
)

single_chain_request = ESMFoldPredictRequest(
    items=[
        ESMFoldPredictRequestItem(
            sequence="MKTVRQERLKSIVRILERSKEPVSGAQLAEELSVSRQVIVQDIAYLRSLGYNIVATPRGYVLAGG"
        ),
    ],
)

# Multi-chain complex prediction (chains separated by ":")
multi_chain_request = ESMFoldPredictRequest(
    items=[
        ESMFoldPredictRequestItem(
            sequence="MKTVRQERLKSIVRILERSKEPVSGAQ:LAEELSVSRQVIVQDIAYLRSLGYN"
        ),
    ],
)
```

## Performance & Benchmarks

### Published Results

ESMFold was benchmarked on CAMEO targets and CASP14, comparing single-sequence prediction against MSA-dependent methods (Lin et al., Science 2023).

| Model | Method | Relative Accuracy | Speed |
|-------|--------|-------------------|-------|
| **ESMFold** | Single-sequence | Competitive for well-covered families | ~60x faster than AlphaFold2 |
| AlphaFold2 | MSA-based | Highest overall accuracy | Minutes to hours (MSA search) |
| RoseTTAFold | MSA-based | Similar to ESMFold on many targets | Minutes to hours (MSA search) |

<!-- TODO: Extract exact GDT-TS and TM-score benchmark numbers from paper Figures 3-4 and supplementary tables -- see sources.yaml primary_papers[0] -->

Key quantitative findings from the paper:
- ESMFold predictions with pLDDT > 0.7 have median TM-score > 0.8 relative to experimental structures
- For proteins with high evolutionary coverage in UniRef50, ESMFold approaches AlphaFold2 accuracy
- Accuracy drops significantly for orphan proteins with few detected homologs

### SOTA Status

ESMFold was state-of-the-art for single-sequence (MSA-free) protein structure prediction at time of publication (2023). As of 2025, newer methods (ESM3, Boltz-2 in single-sequence mode) may provide improved accuracy, though ESMFold remains the fastest option for pure protein structure prediction.

<!-- TODO: Verify current SOTA status against newer single-sequence structure predictors -- check CAMEO leaderboard -->

## Implementation Verification

### Verification Method

Numerical reproduction (Option A): The BioLM implementation loads official pre-trained weights via `esm.pretrained.esmfold_v1()` from the `facebookresearch/esm` repository. Test fixtures compare predicted PDB coordinates and confidence scores against golden reference outputs stored in R2.

### Test Cases

| Test Case | Input | Verification Metric | Threshold | Status |
|-----------|-------|-------------------|-----------|--------|
| Single-chain prediction | Single protein sequence | PDB RMSD | < 0.5 Angstroms | PASS |
| Single-chain prediction | Single protein sequence | mean_plddt, ptm relative tolerance | 1e-1 | PASS |
| Multi-chain prediction | Two chains separated by `:` | PDB RMSD | < 0.5 Angstroms | PASS |
| Multi-chain prediction | Two chains separated by `:` | mean_plddt, ptm relative tolerance | 1e-1 | PASS |

### Verification Status

**Status: VERIFIED** -- Integration tests pass for both single-chain and multi-chain predictions with PDB RMSD < 0.5 Angstroms and numerical tolerances of rel_tol=1e-1.

<!-- TODO: Add verification date from most recent CI run -- check GitHub Actions history -->

## Resource Requirements

| Resource | Value |
|----------|-------|
| GPU | A10G (24 GB VRAM) |
| Memory | 16 GB system RAM |
| CPU | 4 cores |
| Cold start | Fast (GPU memory snapshots enabled) |
| Dependencies | PyTorch 2.0.1, fair-esm, OpenFold |

## Implementation Notes

- **Memory snapshots**: ESMFold uses `@modal.enter(snap=True)` with GPU memory snapshots enabled (`enable_memory_snapshot=True`, `experimental_options={"enable_gpu_snapshot": True}`) for fast cold starts. The model is loaded and moved to GPU during the snapshot phase.
- **Determinism**: Seeds are set (`torch.manual_seed(42)`, `torch.cuda.manual_seed_all(42)`) for reproducible outputs.
- **Weight loading**: Weights are downloaded from R2 (with fallback) via the declarative download system and loaded using `esm.pretrained.esmfold_v1()`. The Torch Hub cache directory is set to the model download path.
- **Chunk size**: Set to 768 (`ESMFoldParams.max_sequence_len`) for memory-efficient attention computation.
- **Recycling**: Fixed at 4 recycles (`num_recycles=4`) per prediction for accuracy/speed balance.
- **Batching**: Sequences are batched by total token count (max 1024 tokens per batch) to optimize GPU utilization while staying within memory limits.
- **OOM handling**: CUDA out-of-memory errors during inference are caught and return empty results (`pdb=""`, `mean_plddt=0.0`, `ptm=0.0`) for the affected batch, allowing the remaining batches to complete.
- **Caching**: Inherits standard Redis/R2 two-tier caching from `BillingMixinSnap`.
- **Container image**: Built from `pytorch/pytorch:2.0.1-cuda11.7-cudnn8-runtime` with OpenFold installed from source (requires `--no-build-isolation` for setup.py that imports torch).

## License

- **Code**: MIT ([LICENSE](https://github.com/facebookresearch/esm/blob/main/LICENSE))
- **Weights**: MIT (same license covers pre-trained weights)

## References & Citations

### Papers

1. Lin Z, Akin H, Rao R, Hie B, Zhu Z, Lu W, Smetanin N, Verkuil R, Kabeli O, Shmueli Y, dos Santos Costa A, Fazel-Zarandi M, Sercu T, Candido S, Rives A. "Evolutionary-scale prediction of atomic-level protein structure with a language model." *Science* (2023). [DOI: 10.1126/science.ade2574](https://doi.org/10.1126/science.ade2574)

### BibTeX

```bibtex
@article{lin2023evolutionary,
  title={Evolutionary-scale prediction of atomic-level protein structure with a language model},
  author={Lin, Zeming and Akin, Halil and Rao, Roshan and Hie, Brian and Zhu, Zhongkai and Lu, Wenting and Smetanin, Nikita and Verkuil, Robert and Kabeli, Ori and Shmueli, Yaniv and dos Santos Costa, Allan and Fazel-Zarandi, Maryam and Sercu, Tom and Candido, Salvatore and Rives, Alexander},
  journal={Science},
  volume={379},
  number={6637},
  pages={1123--1130},
  year={2023},
  doi={10.1126/science.ade2574}
}
```

### Links

- **Paper**: [arXiv 2207.09423](https://arxiv.org/abs/2207.09423)
- **Code**: [github.com/facebookresearch/esm](https://github.com/facebookresearch/esm)
- **Model weights**: Loaded via `esm.pretrained.esmfold_v1()` from the ESM library

---

*See also: [MODEL.md](MODEL.md) for technical deep-dive | [BIOLOGY.md](BIOLOGY.md) for biological context*
