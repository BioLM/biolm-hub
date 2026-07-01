# BoltzGen -- Technical Details

## Architecture

### Model Type & Innovation

BoltzGen is a **diffusion-based generative model** for de novo biomolecular binder design. Unlike structure prediction models (AlphaFold, Boltz) that predict a single native structure from sequence, BoltzGen is a design model that generates novel protein and peptide binders by sampling from the Boltzmann distribution of structures conditioned on a target.

The key architectural innovation is a unified pipeline that jointly generates backbone geometry and amino acid identity using a novel 14-atom geometry-based amino acid representation operating entirely in continuous coordinate space. This eliminates the traditional decoupling of backbone generation from sequence design, enabling joint training on both structure prediction and design tasks.

BoltzGen is built on the Boltz-2 codebase for its folding and affinity prediction stages, but adds a new diffusion model (BoltzGen1) specifically trained for generative design. The model was experimentally validated across eight wet-lab campaigns spanning 26 targets, with nanomolar binders found for 66% of novel targets.

### Parameters & Layers

BoltzGen orchestrates five distinct neural network checkpoints in a seven-stage pipeline:

| Checkpoint | File | Role | Source |
|-----------|------|------|--------|
| Design (diverse) | `boltzgen1_diverse.ckpt` | Backbone generation favoring structural diversity | `boltzgen/boltzgen-1` |
| Design (adherence) | `boltzgen1_adherence.ckpt` | Backbone generation favoring constraint adherence | `boltzgen/boltzgen-1` |
| Inverse folding | `boltzgen1_ifold.ckpt` | Sequence design from backbone (ProteinMPNN-class) | `boltzgen/boltzgen-1` |
| Folding | `boltz2_conf_final.ckpt` | Structure prediction for self-consistency QC | `boltzgen/boltzgen-1` |
| Affinity | `boltz2_aff.ckpt` | Binding affinity prediction | `boltzgen/boltzgen-1` |

| Property | Details |
|----------|---------|
| Architecture | SE(3)-equivariant diffusion (design) + transformer trunk (folding/affinity) |
| Amino acid representation | 14-atom geometry-based continuous coordinates |
| Input modalities | Protein sequence, SMILES, CIF/PDB structures |
| Output modalities | All-atom 3D structure (mmCIF) + designed sequence |
| Max sequence length | 2048 residues |
| Molecule dictionary | `mols.zip` from `boltzgen/inference-data` (CCD reference data) |

### Training Data

| Property | Details |
|----------|---------|
| Primary dataset | PDB (Protein Data Bank) |
| Design training | Structure prediction data + generative design objectives |
| Inverse folding | Sequence recovery on PDB structures |
| Folding (Boltz-2) | PDB complexes with temporal cutoff |
| Affinity (Boltz-2) | Experimental IC50/Kd from ChEMBL and PDBBind |
| Experimental validation | 8 wet-lab campaigns, 26 targets, nanobodies + peptides + protein binders |

**Known biases**: Training is dominated by soluble globular proteins. Membrane proteins, intrinsically disordered regions, and non-standard post-translational modifications are under-represented. The model performs best for targets with structural homologs in the PDB.

### Loss Function & Objective

**Design stage**: Denoising score matching loss -- the diffusion model learns to predict the noise added to ground-truth atomic coordinates. Two checkpoint variants trade off exploration vs. constraint satisfaction:
- **Diverse**: Optimized for structural diversity in generated candidates
- **Adherence**: Optimized for satisfying specified constraints (binding sites, secondary structure)

**Inverse folding stage**: Cross-entropy loss on amino acid identity conditioned on backbone geometry.

**Folding stage (Boltz-2)**: Standard structure prediction loss for self-consistency refolding.

**Affinity stage (Boltz-2)**: Combined regression loss on log10(IC50) and binary binder/non-binder classification loss.

### Tokenization / Input Processing

- **Proteins**: Single-letter amino acid sequences or length range specifications (e.g., `"80..120"` for de novo design). Fixed sequences for target chains, range expressions for designed chains.
- **Ligands**: SMILES strings or CCD (Chemical Component Dictionary) codes. Internally converted to molecular graphs using the molecule dictionary.
- **Structures**: CIF or PDB files for scaffold redesign and target specification. Chains selected via include/exclude selectors with optional residue index filtering.
- **Design masks**: Residue-level control over which positions are redesigned vs. fixed. Specified via `design` and `not_design` fields with chain and residue index selectors.
- **Constraints**: Bond constraints (cyclization, disulfides), contact constraints (distance limits), pocket constraints (binding site specification), and total length constraints.
- **Secondary structure**: Per-residue enforcement of helix, sheet, or loop at specified positions.

The request is converted to a YAML specification matching the BoltzGen CLI format, which drives the seven-stage subprocess pipeline.

## Performance & Benchmarks

### Published Benchmarks

#### Experimental Validation (Stark et al. bioRxiv 2025)

BoltzGen was validated in eight wet-lab design campaigns across 26 targets:

| Metric | Value | Notes |
|--------|-------|-------|
| Targets with nanomolar binders | 66% (6/9 novel targets) | 15 nanobody and protein binder designs tested |
| Target types | Nanobodies, disulfide peptides, protein binders | Across diverse modalities |
| Campaigns | 8 wet-lab campaigns | Including yeast display, phage display |

#### Self-Consistency Metrics

Self-consistency measures whether designed structures can be recovered by refolding the designed sequence with Boltz-2 (an independent structure predictor). This is the standard quality metric for generative structure models.

| Metric | Approximate Range | Notes |
|--------|-------------------|-------|
| scRMSD (design vs. refolded) | Designs passing filtering typically < 2.0 A | Lower is better; threshold set by `refolding_rmsd_threshold` |
| scTM (design vs. refolded) | Passing designs typically > 0.7 | Higher is better |
| ipTM (Boltz-2 affinity) | Varies by protocol and target | Interface quality of designed complex |
| pLDDT | Varies; higher = more confident local structure | Per-residue confidence from Boltz-2 refolding |

The pipeline's filtering stage (stage 7) applies hard filters on these self-consistency metrics plus diversity-aware ranking to select the top `budget` designs from `num_designs` candidates.

#### BioLM Test Suite Metrics

The BioLM implementation validates the following properties on each design:

| Metric | Criterion | Notes |
|--------|-----------|-------|
| CIF parseability | Valid mmCIF (gemmi) | Structure must be parseable |
| Sequence validity | All standard amino acids (ACDEFGHIKLMNPQRSTVWY) | No non-standard residues in designed chain |
| Metrics populated | Non-empty dict with numeric values | Pipeline produces quality metrics |
| Design diversity | >= 2 unique sequences out of 3 designs | Generative model produces diverse candidates |

### BioLM Verification Results

Five test cases validated across all four BoltzGen protocols during initial development (2026-02-17):

| Test Case | Protocol | Target | Status |
|-----------|----------|--------|--------|
| `protein_small_molecule_chorismite` | protein-small_molecule | TSA ligand | PASS |
| `nanobody_7eow_simple` | nanobody-anything | PDB 7EOW | PASS |
| `cyclic_hiv_9d3d` | peptide-anything | PDB 9D3D | PASS |
| `streptavidin_cyclic` | peptide-anything | Streptavidin 1MK5 | PASS |
| `hard_target_1g13nano` | nanobody-anything | PDB 1G13 | PASS |

Two test cases are enabled in CI (`protein_small_molecule_chorismite`, `nanobody_7eow_simple`). The remaining three were validated but are disabled to reduce GPU cost (~20-40 minutes of A100 time each).

### Comparison to Alternatives

| Model | Type | All-Atom | Multi-Molecule | Joint Seq+Struct | When to Prefer |
|-------|------|----------|----------------|------------------|----------------|
| **BoltzGen** | Generative (design) | Yes | Yes | Yes | De novo binder design with end-to-end pipeline |
| RFdiffusion3 | Generative (design) | Yes | Yes | No (backbone only, needs MPNN) | Unconditional design, motif scaffolding, symmetric design |
| ProteinMPNN | Inverse folding | N/A | N/A | N/A (seq only) | Sequence design for a given backbone |
| Boltz-2 | Structure prediction | Yes | Yes | No | Predicting structure of known sequences; affinity ranking |
| AlphaFold3 | Structure prediction | Yes | Yes | No | Structure prediction; not design |

### Error Bars & Confidence

BoltzGen is a stochastic generative model. Each run produces different designs:

- **Inter-run variance**: Designs from different runs have distinct sequences and structures by design. The `num_designs` parameter controls how many candidates are generated, and `budget` controls how many survive diversity-aware filtering.
- **Self-consistency variance**: scRMSD and scTM scores vary per design. The filtering stage removes low-quality designs (high scRMSD, low affinity).
- **Protocol-dependent quality**: Different protocols (protein-anything, peptide-anything, nanobody-anything, protein-small_molecule) use different internal parameters (diffusion batch size, step scale, noise scale) tuned for each modality.
- **Alpha parameter**: Controls the trade-off between quality (alpha=0.0) and diversity (alpha=1.0) in the final ranking step.

## Strengths & Limitations

### Pros

- End-to-end binder design pipeline: structure generation, sequence design, refolding validation, affinity prediction, and diversity-aware filtering in a single workflow
- Joint structure+sequence generation via 14-atom continuous representation -- no separate backbone/sequence design steps needed
- Experimentally validated: nanomolar binders for 66% of novel targets across multiple modalities
- Supports diverse design modalities: de novo proteins, cyclic peptides, nanobody CDR redesign, small molecule pocket design
- Rich constraint language: binding sites, secondary structure, cyclization, disulfide bonds, total length bounds
- Built on Boltz-2 for state-of-the-art refolding and affinity evaluation

### Cons

- Long inference time: full pipeline takes 10-60 minutes per design campaign on A100 40GB
- Batch size limited to 1 design specification per request
- Maximum sequence length of 2048 residues
- Requires A100 40GB GPU with 64GB system RAM
- No membrane protein support (trained on soluble complexes)
- No multi-state design or allosteric mechanisms
- Computational predictions require wet-lab validation -- no guarantee of experimental success

### Known Failure Modes

- **Water molecules in CIF**: Water atoms in input structure files cause SASA calculation failures in the analysis stage. Input structures should be stripped of water molecules.
- **Incorrect CDR region indices**: Nanobody scaffold redesign requires precise residue index specification matching the PDB numbering. Incorrect indices produce meaningless designs.
- **Short peptide designs**: Very short peptides (< 8 residues) may not have sufficient structural context for reliable design.
- **Subprocess timeout**: Individual pipeline runs have a 1-hour timeout. Very large `num_designs` values with complex targets can exceed this limit.
- **CIF writer IndexError**: Upstream bug when chains are filtered (patched in BioLM build -- see Bug Fixes in README.md).
- **Design mask all-False**: Upstream bug in exclude handler (patched in BioLM build -- see Bug Fixes in README.md).

## Implementation Details

### Inference Pipeline

```
Request (BoltzGenDesignRequest)
  |-- 1. Validate request (Pydantic schema)
  |-- 2. Convert to YAML specification
  |     |-- Map entities (protein, ligand, file) to boltzgen format
  |     |-- Write structure files (CIF/PDB) to temp directory
  |     |-- Set design masks, constraints, secondary structure
  |     \-- Configure protocol-specific parameters
  |-- 3. Build CLI command (python -m boltzgen)
  |     |-- Set protocol, num_designs, budget
  |     |-- Configure checkpoint paths (diverse/adherence, ifold, folding, affinity)
  |     |-- Set pipeline steps (7-stage default or user-specified subset)
  |     \-- Set diffusion parameters (step_scale, noise_scale, batch_size)
  |-- 4. Execute subprocess with timeout (1 hour)
  |-- 5. Process output directory
  |     |-- Find top-ranked CIF files (sorted by pipeline scoring)
  |     |-- Extract amino acid sequence from each CIF (gemmi)
  |     |-- Parse metrics CSV for quality scores
  |     |-- Optionally create base64-encoded zip of full output
  |     \-- Build BoltzGenDesignResult per design
  \-- 6. Return BoltzGenDesignResponse
```

### Memory & Compute Profile

| Input | GPU | Memory (system) | Typical Time | Notes |
|-------|-----|-----------------|--------------|-------|
| Simple protein-ligand (num_designs=3, budget=2) | A100 40GB | 64 GB | ~10-20 min | Minimal test configuration |
| Nanobody redesign (num_designs=3, budget=2) | A100 40GB | 64 GB | ~20-40 min | File entity + scaffold processing |
| Production campaign (num_designs=500, budget=100) | A100 40GB | 64 GB | ~2-8 hours | Full design campaign (max per-request limit) |
| Cyclic peptide (num_designs=3, budget=2) | A100 40GB | 64 GB | ~15-30 min | With cyclization constraints |

The BioLM deployment allocates 8 CPU cores and 64 GB system memory alongside the A100 40GB GPU. 24-hour maximum timeout accommodates large design campaigns.

### Determinism & Reproducibility

- **Inherently stochastic**: BoltzGen is a generative model -- different runs produce different designs by design.
- **No fixed seed**: The pipeline does not expose a global seed parameter. Stochasticity comes from the diffusion sampling process.
- **Test validation**: Tests validate structural properties (CIF parseability, valid sequences, metric presence, design diversity) rather than exact output comparison.
- **Diversity guarantee**: The filtering stage explicitly optimizes for sequence diversity among high-quality candidates.

### Caching Behavior

- **Response caching**: Due to the stochastic nature of generative design, cache hits are meaningful only for identical requests (same entities, same parameters).
- **R2 caching**: Model checkpoints cached in R2 (`biolm-hub/model-weights/models/boltzgen/v1/`). HuggingFace fallback for first container builds.
- **Memory snapshots**: `enable_memory_snapshot=True` for faster cold starts. GPU snapshots disabled (`enable_gpu_snapshot: False`) due to the large combined model size.
- **Molecule dictionary**: `mols.zip` extracted once during container setup and persisted for the container lifetime.

## Versions & Changelog

| Version | Date | Changes |
|---------|------|---------|
| v1 | 2026-02 | Initial BoltzGen implementation -- 7-stage pipeline, 4 protocols, 5 validated test cases |

---

*See also: [README.md](README.md) for API reference | [BIOLOGY.md](BIOLOGY.md) for biological context*
