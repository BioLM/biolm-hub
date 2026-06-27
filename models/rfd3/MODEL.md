# RFdiffusion3  --  Technical Details

## Architecture

### Model Type & Innovation

RFdiffusion3 (RFD3) is a **diffusion-based generative model** for de novo design of all-atom biomolecular structures. Unlike structure prediction models (AlphaFold, RoseTTAFold) that predict a single native structure from sequence, RFD3 is a design model that generates novel protein backbones and all-atom coordinates by iteratively denoising random 3D coordinates through a learned reverse diffusion process.

The key architectural innovations over the original RFdiffusion (Watson et al., Nature 2023):

- **All-atom generation**: RFdiffusion v1 generated backbone-only coordinates (N, CA, C, O); RFD3 generates complete all-atom structures including sidechains, ligands, and cofactors.
- **Multi-molecule design**: Unified handling of proteins, DNA, RNA, and small molecules within a single diffusion framework, enabling design of biomolecular complexes.
- **Covalent modification support**: Post-translational modifications, crosslinks, and custom bonds between components.
- **Built on the foundry/atomworks framework**: Uses the RosettaCommons foundry library for unified biomolecular representation and inference, replacing the original SE(3)-diffusion codebase.

The model backbone derives from the RoseTTAFold architecture, which uses a three-track neural network (1D sequence, 2D pairwise, 3D structure) with information flow between tracks. The diffusion process operates in SE(3) -- the group of 3D rotations and translations -- to respect the physical symmetries of molecular structures.

### Parameters & Layers

| Component | Details |
|-----------|---------|
| Architecture | RoseTTAFold-based three-track network + SE(3) diffusion |
| Checkpoint | `rfd3_latest.ckpt` (single checkpoint file) |
| Input representation | All-atom coordinates via atomworks framework |
| Output | All-atom 3D coordinates in mmCIF format |
| Positional encoding | Relative (inter-residue distances and orientations) |
| Diffusion type | SE(3) denoising diffusion |
| Noise schedule | Configurable via `noise_scale` (default: 1.003) |
| Step scale | Configurable via `step_scale` (default: 1.5) |
| Total parameters | **168M** trainable parameters (vs ~350M for AlphaFold3) |
| Diffusion module | Transformer-based U-Net: downsampling encoder, sparse transformer, upsampling decoder |
| Pairformer layers | 2 (reduced from 48 in AF3, greatly reducing computational cost) |
| Atom representation | 14 atoms per residue (4 backbone + 10 sidechain; virtual atoms on Cb for smaller sidechains) |
| Feature exchange | Sparse attention blocks between atomic and token features; cross-attention up-pool/down-pool |
| Conditioning | Classifier-free guidance (weighted average of conditional and unconditional forward passes) |

### Training Data

| Property | Details |
|----------|---------|
| Primary dataset | PDB (Protein Data Bank) |
| Structure types | Protein monomers, oligomers, protein-nucleic acid complexes, protein-ligand complexes |
| Representation | All-atom coordinates (not backbone-only) |
| Augmentation | SE(3) data augmentation (random rotations and translations) |
| Predecessor training | RFdiffusion v1 was trained on PDB structures deposited before 2021 |

**Known biases**: Training data is dominated by soluble globular proteins that crystallize well. Membrane proteins, intrinsically disordered regions, and rare post-translational modifications are under-represented. Design quality is highest for proteins resembling folds present in the PDB.

### Loss Function & Objective

RFD3 uses a **denoising score matching** objective. During training:

1. Ground-truth all-atom coordinates are corrupted with SE(3)-equivariant noise at a sampled timestep t.
2. The model learns to predict the noise (or equivalently, the denoised coordinates) given the noisy input.
3. The loss is the L2 distance between predicted and true denoised coordinates, summed over all atoms.

At inference, the model starts from pure noise and iteratively denoises over a configurable number of steps (default: 200) to produce a designed structure. The `step_scale` and `noise_scale` parameters control the trade-off between sample diversity and designability.

### Tokenization / Input Processing

- **Proteins**: Represented as poly-methionine templates (poly-M) for de novo design, or as full sequences with fixed regions for motif scaffolding.
- **DNA/RNA**: Nucleotide sequences, tokenized per base.
- **Ligands**: SMILES strings or CCD (Chemical Component Dictionary) codes.
- **Structure input**: mmCIF or PDB files for conditioning modes requiring existing structures (motif scaffolding, partial diffusion, binder design).
- **Maximum sequence length**: 2048 residues (enforced by `RFD3Params.max_sequence_len`).
- **Design specification**: Converted to a JSON format expected by the foundry inference engine, with keys specifying input structure, contig strings, fixed atoms, symmetry, and other constraints.

## Performance & Benchmarks

### Published Benchmarks

#### De Novo Protein Design (Self-Consistency)

Self-consistency TM score (scTM) measures whether the designed backbone can be recovered by predicting the structure of the designed sequence using an independent structure predictor (RF3 or AlphaFold2). Higher scTM indicates more designable structures.

| Model | scTM (mean) | Notes |
|-------|-------------|-------|
| **RFdiffusion3** | Higher than v1 | All-atom generation with improved designability |
| RFdiffusion v1 | Baseline | Backbone-only generation |

#### Approximate Benchmark Numbers (RFdiffusion v1 reference, Watson et al. Nature 2023)

| Metric | RFdiffusion v1 | RFD3 | Notes |
|--------|----------------|------|-------|
| Unconditional designability | ~70% of designs | **98%** (at least 1/8 MPNN seqs folds within 1.5 A RMSD by AF3) | Lengths 100-200; Butcher et al. 2025 |
| Unconditional diversity | -- | 41 clusters / 96 designs (TM-score 0.5 cutoff, lengths 100-250) | High fold diversity |
| PPI binder design (unique clusters) | 1.4 avg successful clusters/target | **8.2** avg successful clusters/target | 5 therapeutically relevant targets, 400 designs each |
| DNA binder design pass rate | N/A (no DNA support) | **8.67%** monomeric, **6.67%** dimeric (< 5 A DNA-aligned RMSD) | 3 DNA targets, 100 designs each |
| Small molecule binder design | N/A | Significantly outperforms RFdiffusionAA on all 4 benchmarked molecules | AF3 success: backbone RMSD <= 1.5 A, ligand RMSD <= 5 A, min PAE <= 1.5, ipTM >= 0.8 |
| AME enzyme benchmark | RFD2 baseline | **RFD3 outperforms on 37/41 cases (90%)**; 15% vs 4% passing for >4 residue islands | Measured by Chai/AF3 structure prediction |
| Experimental enzyme success | -- | 35/190 multi-turnover designs; best Kcat/Km = 3,557 | Cysteine hydrolase (Cys-His-Asp triad) |
| Experimental DNA binder | -- | 1/5 designs bound (EC50 = 5.89 +/- 2.15 uM) | Yeast surface display validation |
| Inference speed | Baseline | **~10x faster** than RFD1/RFD2 | Due to simplified architecture (sparse attention, lean Pairformer) |

#### Binder Design

RFD3 extends binder design to all-atom targets including proteins, DNA, RNA, and small molecules:

| Target Type | Capability | Notes |
|-------------|------------|-------|
| Protein | Full support | All-atom binder generation |
| DNA | Full support | New in RFD3 (not in v1) |
| RNA | Full support | New in RFD3 (not in v1) |
| Small molecule | Full support | Ligand cofolding with designed protein |

#### Motif Scaffolding

RFD3 scaffolds functional motifs with all-atom accuracy, preserving sidechain geometry of fixed residues while generating compatible surrounding structure.

### BioLM Verification Results

<!-- TODO(runtime): Add BioLM internal benchmark results once systematic verification is completed -->

### Comparison to Alternatives

| Model | Type | All-Atom | Multi-Molecule | Ligands | When to Prefer |
|-------|------|----------|----------------|---------|----------------|
| **RFdiffusion3** | Generative (design) | Yes | Yes | Yes | De novo design of all-atom biomolecular structures |
| RFdiffusion v1 | Generative (design) | No (backbone only) | No | No | Legacy; use RFD3 instead |
| Chroma | Generative (design) | No (backbone only) | No | No | Alternative backbone-only diffusion |
| ProteinMPNN | Inverse folding | N/A | N/A | Yes (LigandMPNN) | Sequence design for a given backbone |
| Boltz | Structure prediction | Yes | Yes | Yes | Predicting structure of known sequences |
| AlphaFold3 | Structure prediction | Yes | Yes | Yes | Predicting structure; not design |

### Error Bars & Confidence

RFD3 is a stochastic generative model. Each run with a different random seed produces a distinct designed structure:

- **Inter-seed variance**: Designs from different seeds can have substantially different folds and topologies, especially for unconditional design.
- **Designability variance**: Not all generated structures are equally designable. Typical workflows generate multiple candidates (via `diffusion_batch_size` or multiple seeds) and filter by self-consistency metrics.
- **Step count effect**: More diffusion steps (up to 500) generally produce higher-quality designs at the cost of longer compute time. Below 100 steps, quality degrades noticeably.
- **Temperature effect**: Lower temperature (< 1.0) produces less diverse but more designable structures. Higher temperature (> 1.0) increases diversity at the cost of quality.

## Strengths & Limitations

### Pros

- First all-atom diffusion model for biomolecular design -- generates complete structures including sidechains, ligands, and cofactors
- Multi-molecule design: proteins, DNA, RNA, and small molecules in a unified framework
- Multiple conditioning modes: unconditional, motif scaffolding, binder design, partial diffusion, symmetric design
- Supports covalent modifications and custom bonds between components
- High designability: outputs are typically confirmed by inverse folding (ProteinMPNN) and structure prediction (RF3/AF2)
- Fully open-source (BSD 3-Clause License)

### Cons

- Batch size limited to 1 design task per request (use `diffusion_batch_size` for multiple designs of the same input)
- Maximum sequence length of 2048 residues
- GPU memory intensive: requires A100 40GB (uses `low_memory_mode` optimizations)
- Generative model: outputs require downstream validation (ProteinMPNN + structure prediction)
- No guarantee of experimental success -- designs must be validated in the laboratory
- Inference is slow compared to prediction models (minutes per design at 200 steps)

### Known Failure Modes

- **Very short sequences** (< 30 residues): Insufficient structural context for reliable design; backbone-only methods may be better.
- **Very long sequences** (> 1000 residues): GPU memory usage scales with sequence length; may require `low_memory_mode` and reduced `diffusion_batch_size`.
- **Membrane proteins**: Training data under-represents membrane-embedded structures; designs may not be stable in lipid bilayers.
- **Disordered regions**: The model generates a single conformation; intrinsically disordered regions cannot be meaningfully designed.
- **Ligand design**: RFD3 designs protein structure around a fixed ligand, but does not design the ligand itself.
- **Checkpoint availability**: The foundry CLI (`foundry install rfd3`) must be accessible during image build or R2 cache must be populated.

## Implementation Details

### Inference Pipeline

```
Request
  |-- 1. Validate request parameters and input components
  |-- 2. Process input structure (if provided)
  |     |-- Write structure_cif to temp file
  |     |-- Validate file extension (.pdb, .cif, .mmcif)
  |     \-- Copy to temp directory
  |-- 3. Create design specification JSON
  |     |-- Map conditioning mode to foundry format
  |     |-- Handle contig strings, fixed atoms/residues
  |     |-- Set symmetry, ligands, unindexed motifs
  |     \-- Calculate length from components if not explicit
  |-- 4. Initialize RFD3InferenceEngine
  |     |-- Load checkpoint (rfd3_latest.ckpt)
  |     |-- Configure diffusion steps, temperature, batch size
  |     |-- Enable low_memory_mode for GPU efficiency
  |     \-- Set advanced sampling params (step_scale, noise_scale)
  |-- 5. Run inference (diffusion denoising)
  |-- 6. Process outputs
  |     |-- Handle list output (direct results) or dict (in-memory mode)
  |     |-- If outputs written to disk: search for .cif.gz / .cif files
  |     |-- Decompress gzipped CIF files
  |     \-- Optionally collect denoising trajectories
  \-- 7. Return RFD3DesignResponse with structure_cif per design
```

### Memory & Compute Profile

| Input | GPU | Memory (system) | Typical Inference Time | Notes |
|-------|-----|-----------------|------------------------|-------|
| 100-residue unconditional | A100 40GB | 64 GB | ~2-5 min | 200 diffusion steps |
| 200-residue unconditional | A100 40GB | 64 GB | ~5-10 min | 200 diffusion steps |
| Binder design (~150 residues) | A100 40GB | 64 GB | ~5-15 min | Depends on target size |
| Symmetric trimer (C3) | A100 40GB | 64 GB | ~10-20 min | 3x monomer computation |
| High steps (500 steps) | A100 40GB | 64 GB | ~2-3x above | Linear scaling with steps |

The BioLM deployment allocates 8 CPU cores and 64 GB system memory alongside the A100 40GB GPU. `low_memory_mode` is enabled to reduce GPU memory via chunked P_LL computation.

### Determinism & Reproducibility

- **User-provided seed**: When `seed` is specified in the request, the RNG is seeded for reproducible designs.
- **Model loading**: `torch.manual_seed(42)` and `torch.cuda.manual_seed_all(42)` are set during snapshot loading.
- **Inherently stochastic**: Diffusion sampling is non-deterministic by design. Even with the same seed, minor numerical differences may occur due to GPU floating-point non-determinism in CUDA kernels.
- **cuDNN deterministic mode**: Not explicitly set. For maximum reproducibility, use the same seed across runs on the same hardware.

### Caching Behavior

- **Redis (Modal Dict) caching**: Enabled via `BillingMixinSnap` -- caches responses keyed by full request payload hash.
- **R2 caching**: Model weights cached in R2 (`model-store/rfd3/v1/`). First container builds download via foundry CLI, then cache to R2 for subsequent builds.
- **Memory snapshots**: GPU memory snapshot enabled (`enable_memory_snapshot=True`, `enable_gpu_snapshot=True`). Model loaded to GPU during `snap=True` phase; snapshot restores GPU state on container restart.
- **Runtime R2 caching**: If R2 cache was not populated during image build, the model caches the checkpoint to R2 at runtime after first successful load (`_cache_to_r2_if_needed`).

## Versions & Changelog

| Version | Date | Changes |
|---------|------|---------|
| v1 | 2025 | Initial RFdiffusion3 implementation on foundry framework (commit `6866d61`) |

---

*See also: [README.md](README.md) for API reference | [BIOLOGY.md](BIOLOGY.md) for biological context*
