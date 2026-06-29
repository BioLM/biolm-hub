# AntiFold

> **One-line summary**: Antibody-specific inverse folding model that designs CDR and framework sequences conditioned on 3D backbone structure, supporting conventional antibodies and nanobodies.

## Overview

AntiFold is an inverse folding model for antibodies developed by Hoie et al. (2024) at the Oxford Protein Informatics Group (OPIG). It is built by fine-tuning ESM-IF1 on antibody-antigen structural data from the Structural Antibody Database (SAbDab), using IMGT numbering for consistent region identification.

Given a 3D antibody structure in PDB format, AntiFold predicts amino acid probabilities at each position, enabling structure-based sequence design for CDR optimization, humanization, and library generation. It supports conventional antibodies (VH/VL pairs), heavy-chain-only inputs, and nanobodies (VHH), with optional antigen chain context.

## Architecture

| Property | Value |
|----------|-------|
| Architecture | GNN encoder + autoregressive decoder (fine-tuned ESM-IF1) |
| Embedding dimensions | 512 |
| Training data | SAbDab antibody-antigen complexes (IMGT-numbered) |
| Input | PDB backbone coordinates (N, CA, C, O) |
| Output | Per-residue amino acid probabilities (20 standard amino acids) |

## Model Variants

Single variant -- no size options. The model slug is `antifold`.

## Capabilities & Limitations

**CAN be used for:**
- Designing CDR sequences conditioned on antibody backbone structure
- Generating large sequence libraries (up to 50,000 sequences per request) for experimental screening
- Computing structure-conditioned embeddings (mean or per-residue) for antibody structures
- Scoring how well a native sequence fits its observed structure
- Computing log-probabilities for sequence fitness assessment
- Targeting specific regions: individual CDRs (CDRH1, CDRL2, etc.), all CDRs, framework regions, or specific residue positions
- Working with conventional antibodies (VH/VL), heavy-chain-only, and nanobodies (VHH)
- Including antigen chain context for interface-aware design

**CANNOT be used for:**
- Sequence-only inputs (a 3D structure in PDB format is required)
- General protein inverse folding (use ESM-IF1 or ProteinMPNN instead)
- Constant region (Fc) engineering -- only variable domains are supported
- Structure prediction (use Boltz or ESMFold to generate structures first)
- Non-standard amino acids

**Other considerations:**
- The `generate` action is stochastic by default; provide a `seed` for reproducibility
- Generate batch size is limited to 1 PDB per request (encode/score/log_prob support up to 32)
- PDB structures should use IMGT-compatible numbering for correct region identification

## Actions / Endpoints

### `encode`

Extract structure-conditioned embeddings and/or logits from an antibody structure.

**Request Parameters:**

| Parameter | Type | Default | Range | Description |
|-----------|------|---------|-------|-------------|
| `params.heavy_chain_id` | str | None | PDB chain ID | Heavy chain (VH) or nanobody (VHH) chain identifier; for nanobody inputs omit `light_chain_id` |
| `params.light_chain_id` | str | None | PDB chain ID | Light chain (VL) identifier |
| `params.antigen_chain_id` | str | None | PDB chain ID | Optional antigen chain for context |
| `params.include` | list | `["mean"]` | `mean`, `residue`, `logits` | What to include in response |
| `items[].pdb` | str | (required) | Valid PDB string | PDB structure content |

**Response:**

```json
{
  "results": [
    {
      "embeddings": [0.1, -0.2, ...],
      "residue_embeddings": [[0.1, ...], ...],
      "logits": [[0.5, ...], ...],
      "pdb_posins": [1, 2, 3, ...],
      "pdb_chain": ["H", "H", ...],
      "pdb_res": ["E", "V", ...],
      "top_res": ["E", "V", ...],
      "perplexity": [1.2, 1.5, ...],
      "vocab": ["A", "C", "D", ...]
    }
  ]
}
```

Fields are conditionally included based on the `include` parameter. `mean` returns `embeddings` (512-dimensional vector). `residue` returns `residue_embeddings` (seq_len x 512 matrix). `logits` returns `logits`, `vocab`, `pdb_posins`, `pdb_chain`, `pdb_res`, `top_res`, and `perplexity`.

### `generate`

Sample new antibody sequences conditioned on backbone structure.

**Request Parameters:**

| Parameter | Type | Default | Range | Description |
|-----------|------|---------|-------|-------------|
| `params.heavy_chain_id` | str | None | PDB chain ID | Heavy chain (VH) or nanobody (VHH) chain identifier; for nanobody inputs omit `light_chain_id` |
| `params.light_chain_id` | str | None | PDB chain ID | Light chain (VL) identifier |
| `params.antigen_chain_id` | str | None | PDB chain ID | Optional antigen chain for context |
| `params.seed` | int | None | Any int | Random seed for reproducibility |
| `params.include` | list | None | `logprobs`, `logits` | Optional additional outputs |
| `params.num_seq_per_target` | int | 1 | 1-50,000 | Number of sequences to generate |
| `params.sampling_temp` | float | 0.2 | 0.0-4.0 | Sampling temperature (higher = more diverse) |
| `params.regions` | list | `["CDR1", "CDR2", "CDR3"]` | See regions table | Regions to redesign |
| `params.limit_expected_variation` | bool | false | - | Constrain to natural variation range |
| `params.exclude_heavy` | bool | false | - | Exclude heavy chain from sampling |
| `params.exclude_light` | bool | false | - | Exclude light chain from sampling |
| `items[].pdb` | str | (required) | Valid PDB string | PDB structure content |

**Supported regions:**

| Category | Values |
|----------|--------|
| All positions | `all`, `allH`, `allL` |
| All CDRs | `CDRH`, `CDRL` |
| All frameworks | `FWH`, `FWL` |
| Individual CDRs | `CDR1`/`CDRH1`/`CDRL1`, `CDR2`/`CDRH2`/`CDRL2`, `CDR3`/`CDRH3`/`CDRL3` |
| Individual frameworks | `FW1`/`FWH1`/`FWL1`, `FW2`/`FWH2`/`FWL2`, `FW3`/`FWH3`/`FWL3`, `FW4`/`FWH4`/`FWL4` |
| Specific positions | List of integer residue positions (1-indexed) |

**Response:**

```json
{
  "results": [
    {
      "sequences": [
        {
          "global_score": -1.23,
          "score": -0.98,
          "heavy_chain": "EVQLVESGGGLVQPGG...",
          "light_chain": "DIQMTQSPSSLSASV...",
          "temperature": 0.2,
          "mutations": 3,
          "seq_recovery": 0.97
        }
      ],
      "logprobs": [[...]],
      "logits": [[...]],
      "vocab": ["A", "C", "D", ...]
    }
  ]
}
```

### `score`

Score how well the native sequence fits the observed backbone structure.

**Request Parameters:**

| Parameter | Type | Default | Range | Description |
|-----------|------|---------|-------|-------------|
| `params.heavy_chain_id` | str | None | PDB chain ID | Heavy chain (VH) or nanobody (VHH) chain identifier; for nanobody inputs omit `light_chain_id` |
| `params.light_chain_id` | str | None | PDB chain ID | Light chain (VL) identifier |
| `params.antigen_chain_id` | str | None | PDB chain ID | Optional antigen chain for context |
| `items[].pdb` | str | (required) | Valid PDB string | PDB structure content |

**Response:**

```json
{
  "results": [
    {
      "global_score": -1.23,
      "heavy_chain": "EVQLVESGGGLVQPGG...",
      "light_chain": "DIQMTQSPSSLSASV..."
    }
  ]
}
```

### `log_prob`

Compute the total log-probability of each input structure's sequence given its backbone coordinates.

**Request Parameters:**

Same as `score` (uses `AntiFoldPredictRequest`).

**Response:**

```json
{
  "results": [
    {
      "log_prob": -145.67
    }
  ]
}
```

## Usage Examples

### Encode (extract embeddings)

```python
from models.antifold.schema import (
    AntiFoldEncodeRequest,
    AntiFoldEncodeRequestParams,
    AntiFoldBaseRequestItem,
    AntiFoldEncodeIncludeOptions,
)

request = AntiFoldEncodeRequest(
    params=AntiFoldEncodeRequestParams(
        heavy_chain_id="H",
        light_chain_id="L",
        include=[AntiFoldEncodeIncludeOptions.MEAN],
    ),
    items=[AntiFoldBaseRequestItem(pdb=pdb_string)],
)
```

### Generate (design new sequences)

```python
from models.antifold.schema import (
    AntiFoldGenerateRequest,
    AntiFoldGenerateRequestParams,
    AntiFoldBaseRequestItem,
    AntiFoldValidRegions,
)

request = AntiFoldGenerateRequest(
    params=AntiFoldGenerateRequestParams(
        heavy_chain_id="H",
        light_chain_id="L",
        num_seq_per_target=100,
        sampling_temp=0.2,
        regions=[AntiFoldValidRegions.CDRH3],
        seed=42,
    ),
    items=[AntiFoldBaseRequestItem(pdb=pdb_string)],
)
```

### Score (evaluate native sequence)

```python
from models.antifold.schema import (
    AntiFoldPredictRequest,
    AntiFoldPredictRequestParams,
    AntiFoldBaseRequestItem,
)

request = AntiFoldPredictRequest(
    params=AntiFoldPredictRequestParams(
        heavy_chain_id="H",
        light_chain_id="L",
    ),
    items=[AntiFoldBaseRequestItem(pdb=pdb_string)],
)
```

### Nanobody design

For nanobodies (VHH), supply only `heavy_chain_id` (no `light_chain_id`). The model automatically
uses single-domain mode.

```python
from models.antifold.schema import (
    AntiFoldGenerateRequest,
    AntiFoldGenerateRequestParams,
    AntiFoldBaseRequestItem,
    AntiFoldValidRegions,
)

request = AntiFoldGenerateRequest(
    params=AntiFoldGenerateRequestParams(
        heavy_chain_id="A",  # VHH chain; omit light_chain_id for nanobody mode
        num_seq_per_target=50,
        sampling_temp=0.3,
        regions=[AntiFoldValidRegions.CDR1, AntiFoldValidRegions.CDR2, AntiFoldValidRegions.CDR3],
    ),
    items=[AntiFoldBaseRequestItem(pdb=nanobody_pdb_string)],
)
```

## Performance & Benchmarks

### Published Results

From Hoie et al., *Bioinformatics* (2024):

| Model | CDR-H3 Recovery ↑ | Overall Recovery ↑ | Dataset |
|-------|-------------------|-------------------|---------|
| **AntiFold** | **~38%** | **~45%** | SAbDab test set |
| ESM-IF1 | ~28% | ~38% | SAbDab test set |
| ProteinMPNN | ~30% | ~40% | SAbDab test set |

### SOTA Status

AntiFold represents the state-of-the-art for antibody-specific inverse folding as of its publication in 2024. It is the first model to fine-tune a general inverse folding model specifically for antibody structures with IMGT-aware region targeting.

## Implementation Verification

### Verification Method

Option A -- Numerical Reproduction: outputs from the BioLM implementation are compared against golden outputs generated from the original AntiFold codebase on identical PDB inputs.

### Test Cases

| Input | Action | Tolerance | Status |
|-------|--------|-----------|--------|
| PDB 3HFM (antibody) | encode | cosine_distance < 0.02, rel_tol 3e-4 | PASS |
| PDB 8OI2 IMGT (antibody) | encode | cosine_distance < 0.02, rel_tol 3e-4 | PASS |
| PDB 3HFM | log_prob | rel_tol 1e-4 | PASS |
| PDB 3HFM | score | rel_tol 1e-4 | PASS |
| PDB 3HFM | generate | Sequence count match | PASS |
| PDB 8OI2 IMGT | generate | Sequence count match | PASS |
| PDB 6Y1L IMGT | generate | Sequence count match | PASS |

### Verification Status

**Status: VERIFIED** -- All 7 test cases pass across 4 actions.

## Resource Requirements

| Resource | Value |
|----------|-------|
| GPU | None (CPU-only) |
| Memory | 2 GB |
| CPU | 1.0 cores |
| Cold start | Fast (CPU model with memory snapshot) |
| Memory snapshot | Enabled (`enable_memory_snapshot=True`, `enable_gpu_snapshot=True`) |

## Implementation Notes

- **Memory snapshots**: Uses `@modal.enter(snap=True)` with `ModelMixinSnap` for fast cold starts. Despite being a CPU model, GPU snapshot is enabled in the configuration.
- **Container image**: `modal.Image.debian_slim(python_version="3.11")` with CPU-only PyTorch 2.3.1 (index `https://download.pytorch.org/whl/cpu`). AntiFold is CPU-only, so no CUDA base image is needed. AntiFold source is cloned from GitHub at commit `c306ae6`.
- **External modifications**: Two files from the original AntiFold repository (`main.py` and `antiscripts.py`) are replaced with modified versions in `models/antifold/external/` for API compatibility.
- **Temporary files**: PDB strings are written to temporary files in `/tmp_pdbs/` during inference and cleaned up after each request.
- **Determinism**: Model weights loaded with seed 42. The `generate` action uses time-based seeding by default for diversity, or a user-provided seed for reproducibility.
- **Dependencies**: `torch==2.3.1`, `torch_geometric==2.4.0`, `biopython==1.83`, `biotite==0.38`, `numpy==1.26.*`, `pandas==2.*`.
- **Model weights**: Downloaded from R2 storage via the standard download layer (`params_version="v1"`).

## License

- **Code**: BSD-3-Clause ([LICENSE](https://github.com/oxpig/AntiFold/blob/main/LICENSE))

## References & Citations

### Papers

1. Hoie MH, Hummer AM, Olsen TH, Nielsen M, Deane CM. "AntiFold: Improved antibody structure-based design using inverse folding." *Bioinformatics* (2024). [DOI: 10.1093/bioinformatics/btae403](https://doi.org/10.1093/bioinformatics/btae403)

### BibTeX

```bibtex
@article{hoie2024antifold,
  title={AntiFold: Improved antibody structure-based design using inverse folding},
  author={Hoie, Magnus Haraldson and Hummer, Alissa M and Olsen, Tobias H and Nielsen, Morten and Deane, Charlotte M},
  journal={Bioinformatics},
  year={2024},
  doi={10.1093/bioinformatics/btae403}
}
```

### Links

- **Paper**: [arXiv:2405.03370](https://arxiv.org/abs/2405.03370)
- **Code**: [GitHub oxpig/AntiFold](https://github.com/oxpig/AntiFold)

---

*See also: [MODEL.md](MODEL.md) for technical deep-dive | [BIOLOGY.md](BIOLOGY.md) for biological context*
