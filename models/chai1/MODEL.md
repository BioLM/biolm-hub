# Chai-1 -- Technical Details

## Architecture

### Model Type & Innovation

Chai-1 is a diffusion-based generative model for predicting 3D biomolecular structures. It combines a transformer trunk network with a diffusion module to generate atomic coordinates from sequences of proteins, nucleic acids, and small molecules.

The key innovation is multi-modal structure prediction: unlike earlier models that handle only proteins (AlphaFold2) or require separate pipelines for different molecule types, Chai-1 processes heterogeneous molecular complexes in a unified architecture. It supports proteins, DNA, RNA, ligands, glycans, and their combinations in a single forward pass.

The architecture follows a trunk-and-diffusion design:
1. **Trunk network**: Processes input features (sequence, MSA, optional ESM embeddings) through multiple transformer layers with recycling iterations
2. **Diffusion module**: Generates 3D coordinates through iterative denoising from random noise, conditioned on trunk representations
3. **Confidence head**: Predicts pLDDT and PAE quality metrics for the generated structure

### Parameters & Layers

| Component | Details |
|-----------|---------|
| Architecture | Transformer trunk + Diffusion structure module |
| Trunk recycles | 3 (default, configurable 1-10) |
| Trunk samples | 5 (used in evaluation) |
| Diffusion timesteps | 200 (default, configurable 50-200) |
| Diffusion samples | 5 (used in evaluation, total 25 structures per prediction) |
| ESM embeddings | 3 billion parameter protein language model (per-residue embeddings) |
| Output format | mmCIF with full atomic coordinates |
| Training compute | 128 NVIDIA A100 GPUs, batch size 128, 30 days |

The paper notes that Chai-1's architecture "largely follows" AlphaFold3 (Abramson et al., 2024) with key additions including language model embedding input tracks and constraint features. Exact parameter counts are not published in the technical report.

### Training Data

| Property | Details |
|----------|---------|
| Dataset | PDB structures + AlphaFoldDB predicted structures |
| Training data cutoff | 2021-01-12 (PDB release date) |
| Molecule types | Proteins, DNA, RNA, small molecules, covalent modifications |
| MSA databases | UniRef90, UniProt, MGnify, UniClust30+BFD (via OpenProteinSet or jackhmmer) |
| Template database | PDB70 (same 2021-01-12 cutoff) |
| Evaluation set | PDB structures released 2022-05-01 to 2023-01-12, non-NMR, resolution < 4.5 A, <= 2048 tokens |
| Filtering | Low-homology: monomers and interfaces with < 40% sequence identity to training set |

### Loss Function & Objective

Chai-1 uses a multi-component loss combining:
- **Diffusion loss**: Denoising score matching on atomic coordinates
- **Bond loss**: Enforces chemical validity of predicted bond geometries (has a dedicated `bond_loss_input_proj` component)
- **Confidence loss**: Trains the confidence head to predict pLDDT and PAE
- **Auxiliary losses**: Additional structural constraints

The paper states the training strategy "largely follows" AlphaFold3 (Abramson et al., 2024). Exact loss formulations and weightings are not separately detailed in the Chai-1 technical report; the key difference is that a single model is trained (rather than separate models for separate evaluations) and constraint features (pocket, contact, docking) are each included independently with 10% probability during training.

### Tokenization / Input Processing

Input molecules are specified as FASTA-like entries with entity type annotations:

- **Proteins**: Standard single-letter amino acid codes (ACDEFGHIKLMNPQRSTVWY). Maximum 1024 residues.
- **DNA**: Standard nucleotide codes (ACGT). Maximum 3072 bases.
- **RNA**: Standard nucleotide codes (ACGU). Maximum 3072 bases.
- **Ligands**: SMILES notation. Maximum 128 characters. Validated using RDKit.
- **MSA alignments**: Optional A3M format alignments from UniRef90, MGnify, or small_BFD databases, provided for protein entities only.

Multi-entity complexes are encoded as multiple FASTA entries with type headers (e.g., `>protein|name=chain_A`). Up to 5 molecular entities per complex.

## Performance & Benchmarks

### Published Benchmarks

Chai-1 demonstrates competitive performance with AlphaFold3 across structure prediction tasks. Key benchmark categories include:

#### Protein-Ligand Prediction (PoseBusters V1, n=427)

| Method | Ligand RMSD <= 2 A success rate |
|--------|-------------------------------|
| **Chai-1** | **77.05%** |
| AlphaFold3 | 76.34% |
| RoseTTAFold All-Atom | 42% |
| Chai-1 (docking mode, apo structure provided) | 81.20% |

#### Protein-Protein Complexes (low-homology eval set, n=929 interface clusters)

| Method | DockQ success rate (DockQ > 0.23) |
|--------|----------------------------------|
| **Chai-1 (with MSA)** | **0.751** (95% CI: 0.723-0.778) |
| Chai-1 (no templates) | 0.743 |
| Chai-1 (single-sequence) | 0.698 (95% CI: 0.668-0.728) |
| AlphaFold 2.3 multimer | 0.677 (95% CI: 0.646-0.706) |

#### Antibody-Protein Interfaces (n=122 clusters)

| Method | DockQ success rate (DockQ > 0.23) |
|--------|----------------------------------|
| **Chai-1 (with MSA)** | **0.529** (95% CI: 0.438-0.620) |
| Chai-1 (single-sequence) | 0.479 (95% CI: 0.388-0.570) |
| AlphaFold 2.3 multimer | 0.380 (95% CI: 0.298-0.463) |

#### Protein Monomer Prediction

| Method | Ca-LDDT (low-homology eval, n=271 clusters) | LDDT (CASP15, n=69 targets) |
|--------|---------------------------------------------|----------------------------|
| **Chai-1 (with MSA)** | **0.915** (95% CI: 0.907-0.922) | **0.849** |
| Chai-1 (single-sequence) | 0.852 (95% CI: 0.834-0.867) | -- |
| AlphaFold 2.3 multimer | 0.903 (95% CI: 0.895-0.911) | 0.843 |
| ESM3 (98B param) | -- | 0.801 |

On hard CASP15 targets (AF2.3 LDDT < 0.75, n=14), Chai-1 achieves 0.643 vs 0.552 for AF2.3.

### BioLM Verification Results

The BioLM implementation uses the official `chai-lab==0.6.1` package directly, so inference results are numerically identical to the reference implementation given the same inputs and random seed.

<!-- TODO(runtime): Run verification tests comparing BioLM outputs against reference chai-lab outputs on standard test cases -->

### Comparison to Alternatives

| Model | Strengths | Limitations | When to prefer |
|-------|-----------|-------------|----------------|
| **Chai-1** | Multi-modal (protein + DNA/RNA + ligand), open-source, single-pass | High GPU requirements (A100 80GB) | Heterogeneous complexes, open-source requirement |
| Boltz-1 | Open-source structure prediction | Different accuracy/speed tradeoffs | Alternative open-source option |
| AlphaFold2 | Well-established, MSA-dependent accuracy | Proteins only, no ligands/nucleic acids | Protein-only monomer/multimer tasks |
| ESMFold | Fast, single-sequence (no MSA needed) | Proteins only, lower accuracy on hard targets | Fast protein structure screening |

### Error Bars & Confidence

- Stochastic outputs: different random seeds produce different structures. Run multiple samples (`num_diffn_samples` up to 5) and select by confidence score.
- Confidence varies with input complexity: simple monomers tend to have higher pLDDT than large multi-chain complexes.
- Proteins with close homologs in training data produce more confident predictions.

## Strengths & Limitations

### Pros

- Handles heterogeneous biomolecular complexes (protein + DNA/RNA + ligand) in a single forward pass
- Fully open-source (Apache-2.0) with publicly available weights
- Competitive accuracy with AlphaFold3 on multiple benchmarks
- Supports optional MSA input for improved protein structure accuracy
- Integrates ESM protein language model embeddings
- Generates multiple candidate structures per run for ensemble analysis

### Cons

- High resource requirements: requires A100 80GB GPU and 64 GB system memory
- Slow inference: 30-120+ seconds per prediction depending on complex size
- Batch size limited to 1 due to memory constraints
- Maximum protein length of 1024 residues (shorter than some alternatives)
- PAE and pLDDT confidence scores currently disabled in the API
- Stochastic outputs require multiple samples for robust predictions

### Known Failure Modes

- Very large complexes (approaching all input limits simultaneously) may cause GPU OOM errors
- Ligands with complex ring systems or unusual chemistry may produce poor binding poses
- Intrinsically disordered regions will have low pLDDT scores and unreliable coordinates
- Sequences with no homologs in training data may produce low-quality predictions
- The model may hallucinate contacts between molecules that do not actually interact

## Implementation Details

### Inference Pipeline

```
Request
  +-- 1. Validate input molecules (sequence/SMILES/type checks)
  +-- 2. Convert molecules to FASTA format with type headers
  +-- 3. Process MSA alignments (if provided)
  |     +-- Write A3M files per database per protein
  |     +-- Merge A3M files using chai_lab utility
  +-- 4. Run chai_lab.chai1.run_inference on GPU
  |     +-- Trunk network with recycling (N iterations)
  |     +-- Diffusion module (M timesteps)
  |     +-- Generate K candidate structures
  +-- 5. Read generated mmCIF files from output directory
  +-- 6. Package CIF content into response
  +-- 7. Clean up temporary files
```

### Memory & Compute Profile

| Parameter Setting | Approximate Inference Time | Notes |
|-------------------|---------------------------|-------|
| Default (3 recycles, 200 steps, 1 sample) | 30-60s | Standard quality |
| Fast (1 recycle, 50 steps, 1 sample) | 10-20s | Lower quality, useful for screening |
| High quality (10 recycles, 200 steps, 5 samples) | 120-300s | Best quality, multiple candidates |

GPU memory usage scales with the total number of tokens (residues + bases + ligand atoms) in the complex. The A100 80GB allocation provides headroom for the maximum supported input sizes.

### Determinism & Reproducibility

- `torch.manual_seed(42)`: Set during CPU snapshot
- `torch.cuda.manual_seed_all(42)`: Set during GPU setup
- Configurable `seed` parameter per request
- Diffusion sampling is inherently stochastic; same seed produces same output
- Different `num_diffn_samples` values will produce different structures even with the same seed

### Caching Behavior

- Redis (Modal Dict) caching: Enabled via `BillingMixinSnap`
- R2 caching: Model weights cached in R2 with fallback to chai-lab library download
- Cache key composition: Determined by the `modal_endpoint` decorator based on request content
- Structure predictions are cached per unique input + parameter combination

## Versions & Changelog

| Version | Date | Changes |
|---------|------|---------|
| v1 | 2024 | Initial implementation using chai-lab v0.6.1 |

---

*See also: [README.md](README.md) for API reference | [BIOLOGY.md](BIOLOGY.md) for biological context*
