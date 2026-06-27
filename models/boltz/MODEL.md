# Boltz  --  Technical Details

## Architecture

### Model Type & Innovation

Boltz is a diffusion-based generative model for predicting 3D structures of biomolecular complexes. It follows the AlphaFold3 paradigm of treating structure prediction as a generative modeling problem rather than a regression problem, using iterative denoising to produce atomic coordinates from noise.

The key architectural innovation is a transformer trunk that processes multi-modal molecular inputs (protein sequences, nucleotide sequences, small molecule graphs, and optionally MSA features) through a unified representation. The trunk produces single (per-token) and pairwise (token-pair) representations that condition a diffusion module responsible for generating 3D coordinates.

**Boltz-1** introduced the first fully open-source implementation approaching AlphaFold3 accuracy on diverse biomolecular complexes.

**Boltz-2** extends the trunk with an affinity prediction head  --  a second diffusion-based module that predicts binding free energy (as log10 IC50) from the same internal representations. This is the first deep learning model to approach the accuracy of physics-based free-energy perturbation (FEP) methods while running approximately 1000x faster. Boltz-2 also adds support for structural constraints (bond, pocket, contact) and template conditioning.

### Parameters & Layers

| Component | Boltz-1 | Boltz-2 |
|-----------|---------|---------|
| Architecture | Transformer trunk + diffusion module | Transformer trunk + diffusion module + affinity head |
| Checkpoint files | `boltz1_conf.ckpt`, `ccd.pkl` | `boltz2_conf.ckpt`, `boltz2_aff.ckpt`, `mols.tar` (~2 GB molecular component library) |
| Single embedding dim | 384 | 384 |
| Pairwise embedding dim | 128 | 128 |
| Positional encoding | Relative | Relative |
| Output format | mmCIF atomic coordinates | mmCIF atomic coordinates + affinity scores |

<!-- TODO: Extract exact layer count and total parameter count from the Boltz papers  --  not stated explicitly in the code or README -->

### Training Data

| Property | Details |
|----------|---------|
| Primary dataset | PDB (Protein Data Bank) |
| Complex types | Protein-ligand, protein-protein, protein-nucleic acid, small molecule complexes |
| Temporal cutoff | Structures deposited before the training cutoff (paper-specific; pre-CASP15 for Boltz-1) |
| Boltz-2 affinity data | Experimental binding affinity data (IC50/Kd) from ChEMBL and PDBBind, paired with structural complexes |
| MSA databases | UniRef90, MGnify, Small BFD (optional; model operates in single-sequence mode when MSA omitted) |

**Known biases**: Training is dominated by well-studied protein families that crystallize easily. Membrane proteins, intrinsically disordered regions, and rare post-translational modifications are under-represented. Affinity training data (Boltz-2) is biased toward drug-like small molecules with molecular weight under ~500 Da.

### Loss Function & Objective

**Structure prediction**: Denoising score matching loss  --  the model is trained to predict the noise added to ground-truth atomic coordinates at each diffusion step. The noise schedule and step scale parameter (default 1.638) control the trade-off between sample diversity and quality.

**Affinity prediction** (Boltz-2 only): Trained with a combined regression loss on log10(IC50) and a binary classification loss for binder/non-binder discrimination. The affinity head uses an ensemble of two models, with predictions averaged at inference time.

### Tokenization / Input Processing

- **Proteins**: Single-letter amino acid sequences, tokenized per residue. Optional MSA input in A3M format from UniRef90, MGnify, and/or Small BFD databases. When no MSA is provided, operates in single-sequence mode (`msa: empty`).
- **DNA/RNA**: Single-letter nucleotide sequences, tokenized per base.
- **Ligands**: SMILES strings or CCD (Chemical Component Dictionary) codes. Internally converted to molecular graphs. SMILES validated with RDKit before processing.
- **Multi-chain handling**: Each chain gets a unique ID. Multiple copies of the same entity (e.g., homodimers) are specified via list IDs. IDs are sanitized to 4-character alphabetic strings for Boltz CLI compatibility.
- **Maximum sequence length**: 1024 residues (enforced by `BoltzModelParams.max_sequence_len`).
- **Constraints** (Boltz-2): Bond, pocket, and contact constraints injected as structured YAML.
- **Templates** (Boltz-2): Structural templates provided as CIF content with optional chain mapping.

## Performance & Benchmarks

### Published Benchmarks

#### CASP15 Targets (Boltz-1)

Boltz-1 matches AlphaFold3 and Chai-1 on diverse biomolecular complex prediction tasks from CASP15 benchmarks.

#### FEP+ Benchmark (Boltz-2)

| Model | Pearson R with experimental IC50 | Notes |
|-------|----------------------------------|-------|
| **Boltz-2** | **~0.6** | Deep learning, ~1000x faster than FEP |
| FEP+ (Schrodinger) | ~0.6-0.7 | Physics-based, gold standard, very expensive |

#### CASP16 Affinity Challenge (Boltz-2)

Boltz-2 won the CASP16 affinity challenge, outperforming all submitted methods across 140 complexes.

### BioLM Verification Results

<!-- TODO: Add BioLM internal benchmark results once systematic verification is completed -->

### Comparison to Alternatives

| Model | Structure | Affinity | Ligands | Constraints | When to prefer |
|-------|-----------|----------|---------|-------------|----------------|
| **Boltz-2** | Yes | Yes | SMILES + CCD | Yes | Drug discovery, affinity ranking, constrained docking |
| **Boltz-1** | Yes | No | SMILES + CCD | No | Legacy; use Boltz-2 instead |
| Chai-1 | Yes | No | SMILES + CCD | No | Alternative structure predictor |
| AlphaFold3 | Yes | No | Limited | No | Not open-source; Google-only access |
| ESMFold | Yes (single chain) | No | No | No | Fast single-chain prediction without MSA |

### Error Bars & Confidence

Boltz predictions are inherently stochastic due to the diffusion sampling process:

- **Structure confidence scores** (pTM, iptm, pLDDT): Typically vary 10-25% between runs with different seeds.
- **Affinity predictions**: Highly non-deterministic  --  can vary 80%+ between runs. The ensemble of two models (`*1`/`*2` suffixes) provides some variance estimation.
- **Confidence score formula**: `confidence_score = 0.8 * complex_plddt + 0.2 * iptm`
- The `step_scale` parameter (default 1.638) controls diversity: lower values produce more diverse but potentially lower-quality samples; higher values concentrate around the mode.

## Strengths & Limitations

### Pros

- Handles arbitrary biomolecular complexes: proteins, DNA, RNA, ligands, and combinations thereof
- Fully open-source (MIT license)  --  weights and code
- First DL model approaching FEP accuracy for binding affinity (Boltz-2)
- Pocket-constrained docking enables targeted binding site predictions
- Template conditioning allows leveraging known structural information
- Computes ipSAE interface quality metrics (Dunbrack 2025), which are more robust than ipTM for multi-chain complexes
- Supports post-translational modifications and cyclic chains

### Cons

- Batch size limited to 1 complex per request
- Maximum sequence length of 1024 residues
- No automatic MSA generation  --  MSAs must be pre-computed or omitted
- Single-sequence mode (no MSA) significantly reduces prediction accuracy
- Affinity predictions are only reliable for protein-ligand targets (not RNA/DNA targets)
- Ligand affinity reliability drops for molecules with more than ~56 heavy atoms (training limit)
- GPU memory intensive  --  requires A100 40GB

### Known Failure Modes

- **Silent failures**: The Boltz subprocess can exit with code 0 but produce no output files (upstream issue `github.com/jwohlwend/boltz/issues/167`). The BioLM implementation detects this and raises a `UserError`.
- **SMILES parse errors**: Invalid or difficult-to-kekulize SMILES strings cause silent failures in the subprocess. BioLM pre-validates with RDKit.
- **GPU OOM**: Very long sequences or high `diffusion_samples` can exceed 40GB VRAM, resulting in SIGKILL (signal 9). The implementation provides clear error messages for signal-based kills.
- **Featurization failures**: Unusual residues or unsupported molecule types can fail during the Boltz featurization step.
- **Timeout**: The subprocess has a hard 2-hour timeout (`_SUBPROCESS_TIMEOUT_SEC = 7200`). Long MSA searches or very high sampling steps can trigger this.

## Implementation Details

### Inference Pipeline

```
Request
  |-- 1. Validate batch size (must be 1)
  |-- 2. Validate SMILES with RDKit (pre-check)
  |-- 3. Construct YAML input
  |     |-- Sanitize molecule IDs to 4-char alphabetic
  |     |-- Combine A3M alignments from multiple databases
  |     |-- Write constraints, templates, affinity config
  |     \-- Write temporary files for MSA and template CIFs
  |-- 4. Build Boltz CLI command
  |     |-- boltz predict <yaml> --model {boltz1|boltz2}
  |     |-- Add sampling params, MSA params, optional flags
  |     \-- Always write PAE for ipSAE computation
  |-- 5. Execute subprocess with timeout (2 hours)
  |     |-- Stream stdout in real-time (background thread)
  |     |-- Drain stderr in background thread (prevent pipe deadlock)
  |     \-- Handle SIGKILL/SIGSEGV/SIGTERM with actionable messages
  |-- 6. Process results
  |     |-- Read mmCIF structure
  |     |-- Read confidence scores JSON
  |     |-- Compute ipSAE and ipae from PAE matrix (server-side)
  |     |-- Read affinity scores (Boltz-2, if requested)
  |     \-- Read embeddings NPZ (if requested)
  \-- 7. Cleanup temporary files
```

### Memory & Compute Profile

| Input | GPU | Memory (system) | Typical Inference Time | Notes |
|-------|-----|-----------------|------------------------|-------|
| Single protein (~100 residues) | A100 40GB | 24 GB system RAM | ~30-60s | Includes model initialization |
| Protein-ligand complex (~300 residues + small molecule) | A100 40GB | 24 GB system RAM | ~1-3 min | With default 20 sampling steps |
| Large multimer (~800 residues total) | A100 40GB | 24 GB system RAM | ~5-15 min | Attention scales O(n^2) |
| With high sampling (200 steps, 10 samples) | A100 40GB | 24 GB system RAM | ~30-120 min | Near timeout boundary |

The BioLM deployment allocates 4 CPU cores and 24 GB system memory alongside the A100 40GB GPU.

### Determinism & Reproducibility

- **Seed**: Configurable via `seed` parameter (default 42)
- **Inherently stochastic**: Diffusion sampling is non-deterministic by design. Even with the same seed, results can vary due to GPU floating-point non-determinism in CUDA kernels.
- **Confidence score variance**: 10-25% between runs
- **Affinity variance**: Up to 80%+ between runs  --  use multiple `diffusion_samples_affinity` (default 5) and the ensemble predictions for more robust estimates.

### Caching Behavior

- **Redis (Modal Dict) caching**: Response caching (Redis/R2 two-tier) is handled by the BioLM platform layer, not the model container. Responses are keyed by full request payload hash.
- **R2 caching**: Model weights cached on container via `setup_download_layer`.
- **Memory snapshots**: Model weights loaded on CPU during `snap=True` phase, transferred to GPU during `snap=False` phase. This reduces cold start time.
- **Boltz-2 mols volume**: The ~2 GB molecular component library (`mols.tar`) is extracted to a persistent Modal volume (`boltz2-mols-vol`) and symlinked into the model directory. This avoids re-extraction on every container restart.

## Versions & Changelog

| Version | Date | Changes |
|---------|------|---------|
| v1 (Boltz-1) | 2024-11 | Initial Boltz-1 implementation  --  structure prediction |
| v1 (Boltz-2) | 2025-06 | Boltz-2 added  --  affinity prediction, constraints, templates |
| v1 (hardening) | 2025 | Subprocess timeout, pipe deadlock fix, output file guards, SMILES pre-validation, ipSAE/ipae computation |

---

*See also: [README.md](README.md) for API reference | [BIOLOGY.md](BIOLOGY.md) for biological context*
