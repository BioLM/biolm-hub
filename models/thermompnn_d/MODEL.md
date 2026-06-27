# ThermoMPNN-D -- Technical Details

## Architecture

### Model Type & Innovation

ThermoMPNN-D extends ThermoMPNN to predict stability changes (ddG) for both single and double (paired) mutations. The key innovation is the ability to model epistatic interactions between two simultaneous mutations -- something that additive models fundamentally cannot capture. The model uses two separate architectures:

1. **Single/Additive model**: Predicts ddG for individual mutations. In additive mode, double mutation effects are estimated by summing two single-mutation predictions.
2. **Epistatic model**: A specialized architecture that explicitly models pairwise interactions between two mutation sites, capturing non-additive (epistatic) effects.

### Parameters & Layers

| Component | Details |
|-----------|---------|
| Architecture | Message-passing neural network (GNN) with epistatic interaction module |
| Base model | ProteinMPNN (v_48_020) |
| Single checkpoint | ThermoMPNN-ens1.ckpt |
| Epistatic checkpoint | ThermoMPNN-D-ens1.ckpt |
| Input | PDB structure + mutations |
| Output | ddG in kcal/mol |
| Distance filtering | CA-CA distance threshold (default 5.0 Angstroms) |

### Training Data

<!-- TODO: Extract training dataset details from Dieckhaus & Kuhlman (2024) bioRxiv preprint -- requires PDF access -->

The model was trained on experimental stability measurements including both single and double mutation data, with the epistatic model specifically trained on paired mutation datasets.

### Loss Function & Objective

Regression loss for predicting ddG (change in Gibbs free energy of unfolding) in kcal/mol. The epistatic model additionally learns pairwise interaction terms between mutation sites.

### Tokenization / Input Processing

Input processing follows the same pattern as ThermoMPNN:

1. **PDB parsing**: Structure parsed using ThermoMPNN-D's `load_pdb` utility
2. **Chain selection**: Target chain extracted
3. **Distance matrix**: CA-CA distance matrix computed for filtering double mutations
4. **Mutation encoding**: Single format `WT{pos}MUT` (e.g., `A100V`); double format `WT1{pos1}MUT1:WT2{pos2}MUT2` (e.g., `A100V:B200L`)

## Performance & Benchmarks

### Published Benchmarks

<!-- TODO: Extract benchmark results from Dieckhaus & Kuhlman (2024) bioRxiv 2024.10.10.617658 -- requires PDF access -->

### BioLM Verification Results

Integration tests verify response format across all three modes (single, additive, epistatic), checking for mode-appropriate fields and numeric ddG values. Six test cases cover all modes with both targeted mutations and SSM scans.

### Comparison to Alternatives

| Model | Task | Modes | Advantage |
|-------|------|-------|-----------|
| **ThermoMPNN-D** | Single + double ddG | Single, additive, epistatic | Handles epistatic double mutations |
| ThermoMPNN | Single ddG only | Single | Simpler, lower resource usage |
| TemBERTure | Global Tm | Classification, regression | Sequence-only, no structure needed |

## Strengths & Limitations

### Pros

- Three prediction modes: single, additive, and epistatic
- Captures non-additive (epistatic) interactions between paired mutations
- Distance-based filtering reduces computational cost for double mutations
- Threshold-based filtering returns only mutations meeting ddG criteria
- Full SSM scan support for all three modes

### Cons

- Requires PDB structure input
- Loads two models (single + epistatic), requiring more memory (12 GB)
- Batch size limited to 1 PDB per request
- Epistatic SSM scans can be computationally expensive for large proteins
- Maximum sequence length of 1024 residues

### Known Failure Modes

- Very large proteins with many close-contact residue pairs can produce very large output sets in epistatic SSM mode
- Distance threshold filtering is based on CA-CA distance, which may not capture all relevant interactions
- Missing residues in PDB structures may affect predictions at nearby positions

## Implementation Details

### Inference Pipeline

```
Request --> Validate PDB + mutations + mode
  --> Write PDB to temp file
  --> Parse PDB (load_pdb)
  --> Select chain
  --> Route by mode:
      Single:    run_single_ssm --> format_output_single
      Additive:  run_single_ssm --> format_output_double (additive)
      Epistatic: run_epistatic_ssm (batched, distance-filtered)
  --> Apply threshold filter
  --> Format response with distances
  --> Cleanup temp files
```

### Memory & Compute Profile

| Resource | Value |
|----------|-------|
| GPU | T4 |
| Memory | 12 GB (loads 2 models) |
| CPU | 2 cores |

### Determinism & Reproducibility

- Torch manual seed: Yes (42)
- CUDA manual seed: Yes (42)
- Both models set to eval mode: Yes
- Inference under `torch.no_grad()`: Yes
- PyTorch Lightning load_from_checkpoint patched to default to CPU for Modal snapshot compatibility

### Caching Behavior

- Redis (Modal Dict) caching: Enabled via `BillingMixinSnap`
- R2 caching: Enabled via `BillingMixinSnap`

## Versions & Changelog

| Version | Date | Changes |
|---------|------|---------|
| v1 | 2024 | Initial implementation with single, additive, and epistatic modes |

---

*See also: [README.md](README.md) for API reference | [BIOLOGY.md](BIOLOGY.md) for biological context*
