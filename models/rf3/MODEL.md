# RosettaFold3 (RF3) -- Technical Details

## Architecture

### Model Type & Innovation

RosettaFold3 (RF3) is an all-atom biomolecular structure prediction network from the Baker Lab (RosettaCommons). It combines a Transformer-based trunk with a diffusion-based structure generation module, enabling prediction of protein structures, multi-component complexes (protein-protein, protein-DNA, protein-RNA, protein-ligand), and non-canonical modifications.

Key innovations include:
- Diffusion-based structure sampling that generates multiple diverse conformations
- Support for small molecule ligands via SMILES/CCD input alongside macromolecular sequences
- Template conditioning for partial structure information
- Early stopping based on pLDDT confidence to save compute on low-quality predictions
- Cuequivariance operations for efficient equivariant neural network computation on GPU

RF3 processes inputs through a trunk network with recycling (iterative refinement), then samples 3D coordinates via a learned diffusion process that denoises random coordinates into predicted structures.

### Parameters & Layers

| Component | Details |
|-----------|---------|
| Architecture | Transformer trunk + diffusion structure module |
| Trunk recycling | 2--20 recycles (default: 10) |
| Diffusion steps | 50--500 (default: 200) |
| Diffusion batch size | 1--10 (default: 5) output structures |
| Input modalities | Sequence, SMILES, MSA (A3M), structure (CIF/PDB/SDF) |
| Output format | mmCIF with confidence scores |
| Checkpoint | rf3_foundry_01_24_latest.ckpt (default) |
| Framework | PyTorch + Lightning + AtomWorks |

### Training Data

| Property | Details |
|----------|---------|
| Training structures | PDB (protein, nucleic acid, ligand complexes) |
| Sequence databases | UniRef90, MGnify, Small BFD (for MSA generation) |
| Ligand representations | CCD (Chemical Component Dictionary), SMILES |
| Training cutoff | 09/21 for benchmark checkpoint; 01/24 for latest |

### Loss Function & Objective

RF3 is trained with a combination of:
- Diffusion loss for structure denoising (noise-conditioned score matching)
- Auxiliary losses including pTM (predicted TM-score), pLDDT (predicted LDDT), and PAE (Predicted Aligned Error)
- Clash penalty for steric violations

### Tokenization / Input Processing

- **Protein input**: Amino acid sequences with optional MSA (A3M format)
- **DNA/RNA input**: Nucleotide sequences
- **Ligand input**: SMILES strings or CCD codes
- **Structure templates**: mmCIF, PDB, or SDF format (inline or file path)
- **MSA provision**: Direct A3M content, file path, or database alignment dictionary
- **Component specification**: Each input entity is a named component with type, sequence/structure, and optional chain ID
- **Bonds**: Custom covalent bonds can be specified between atoms
- **Internal format**: Inputs are converted to a JSON specification consumed by the RF3InferenceEngine

## Performance & Benchmarks

### Published Benchmarks

From Corley, Mathis et al., *bioRxiv* (2025):

RF3 is competitive with leading open-source biomolecular structure prediction models. It improves on several tasks including:

| Task | RF3 Performance | Notes |
|------|----------------|-------|
| Protein monomer folding | Competitive with AF2/AF3 | Single-chain proteins |
| Protein-protein complexes | Competitive | Multi-chain predictions |
| Protein-ligand docking | Improved chiral ligand handling | Better than RF2 for chirality |
| Fixed-backbone docking | Improved | Template-conditioned prediction |
| Cyclic peptides | Supported | Via `cyclic_chains` parameter |

### BioLM Verification Results

| Test Case | Input | Tolerance | Status |
|-----------|-------|-----------|--------|
| Simple protein fold | 95-residue single chain | rel_tol 1e-2, RMSD < 5A | PASS |
| Protein-ligand complex | Protein + ibuprofen SMILES | rel_tol 1e-2, RMSD < 5A | PASS |
| Multi-chain complex | Two protein chains | rel_tol 1e-2, RMSD < 5A | PASS |
| MSA-enhanced prediction | Protein + A3M MSA | rel_tol 1e-2, RMSD < 5A | PASS |

### Comparison to Alternatives

| Model | Strength | When to prefer |
|-------|----------|----------------|
| **RF3** | All-atom; ligands; templates; diffusion sampling | Multi-modal complexes; ligand binding; template-guided |
| AlphaFold2/3 | Well-validated; highest accuracy on many benchmarks | Maximum single-chain accuracy |
| Boltz | Open-source AF3-like | Similar use cases to RF3 |
| Chai-1 | Multi-modal structure prediction | Alternative to RF3/Boltz |
| ESMFold | Very fast; no MSA needed | Rapid screening; single chains |

## Strengths & Limitations

### Pros

- Supports diverse biomolecular inputs: proteins, DNA, RNA, ligands, and their complexes
- Diffusion-based sampling generates multiple diverse conformations per prediction
- Template conditioning allows incorporating partial structural knowledge
- Early stopping on low-confidence predictions saves compute
- Provides comprehensive confidence metrics (pTM, ipTM, pLDDT, PAE, ranking score)
- Supports cyclic peptides and non-canonical modifications
- MSA-enhanced predictions for higher accuracy when alignments are available

### Cons

- Requires A100 40GB GPU -- significant resource cost
- Longer runtime than single-pass methods (diffusion requires many steps)
- Large model checkpoint (~several GB)
- Batch size limited to 1 input item per request
- Maximum sequence length of 2048 residues
- Requires foundry package with specialized dependencies (cuequivariance)

### Known Failure Modes

- Very large complexes may exceed GPU memory
- Low-confidence predictions trigger early stopping (by design)
- Ligand predictions require valid SMILES or CCD codes
- MSA quality significantly affects prediction accuracy for proteins

## Implementation Details

### Inference Pipeline

```
Request
  |-- 1. Validate input components (sequences, SMILES, structures)
  |-- 2. Convert to RF3 input specification JSON
  |-- 3. Write MSA files if alignment provided
  |-- 4. Create RF3InferenceEngine with parameters
  |-- 5. Run diffusion-based inference
  |     |-- Trunk recycling (n_recycles iterations)
  |     |-- Diffusion sampling (num_steps denoising steps)
  |     |-- Generate diffusion_batch_size structures
  |-- 6. Check for early stopping (pLDDT threshold)
  |-- 7. Read output CIF files (may be gzipped)
  |-- 8. Read confidence JSON files
  |-- 9. Optionally read PAE and pLDDT arrays
  |-- 10. Return structures with confidence scores
```

### Memory & Compute Profile

| Resource | Value |
|----------|-------|
| GPU | A100 40GB |
| Memory | 64 GB RAM |
| CPU | 8.0 cores |
| Batch size | 1 |
| Max sequence length | 2048 |
| Max output structures | 10 (diffusion_batch_size) |

### Determinism & Reproducibility

| Setting | Value |
|---------|-------|
| Torch manual seed | Yes (42 at model load) |
| CUDA manual seed | Yes (42, if available) |
| User-specified seed | Supported via `seed` parameter (default: 42) |
| Diffusion sampling | Stochastic; seed controls randomness |

Different seeds produce different structural samples from the diffusion process. This is by design -- multiple samples enable exploration of conformational space.

### Caching Behavior

Response caching is available as an optional, off-by-default gateway feature (`BIOLM_CACHE_ENABLED`) -- see the gateway docs; it is not handled by the model container. Especially useful given the high compute cost of each prediction.

## Versions & Changelog

| Version | Date | Changes |
|---------|------|---------|
| v1 | 2025 | Initial implementation using foundry commit 6866d61 |

### Available Checkpoints

| Checkpoint | Filename | Use Case |
|------------|----------|----------|
| Latest (default) | rf3_foundry_01_24_latest.ckpt | Production use with bugfixes |
| Preprint | rf3_foundry_01_24_preprint.ckpt | Reproducing paper results |
| Benchmark | rf3_foundry_09_21_preprint.ckpt | Fair benchmarking (09/21 PDB cutoff) |

---

*See also: [README.md](README.md) for API reference | [BIOLOGY.md](BIOLOGY.md) for biological context*
