# ThermoMPNN -- Technical Details

## Architecture

### Model Type & Innovation

ThermoMPNN is a graph neural network (GNN) for predicting changes in protein thermal stability (ddG) upon single-point mutations. It uses transfer learning from ProteinMPNN -- a message-passing neural network originally trained for protein sequence design -- and fine-tunes it for stability prediction. The key innovation is leveraging ProteinMPNN's learned structural representations to predict thermostability changes, achieving strong performance with relatively little stability-specific training data.

### Parameters & Layers

| Component | Details |
|-----------|---------|
| Architecture | Message-passing neural network (GNN) |
| Base model | ProteinMPNN (v_48_020) |
| Transfer learning head | 2 final layers, hidden dims [64, 32] |
| Light attention | Enabled |
| Subtract mutation | Enabled |
| Freeze base weights | Yes (ProteinMPNN backbone frozen) |
| Input | PDB structure (3D coordinates) |
| Output | ddG in kcal/mol |

### Training Data

From Dieckhaus et al. (2023): ThermoMPNN was trained on two complementary datasets. The **Megascale dataset** (Tsuboyama et al.) contains 272,712 single-point mutation ddG values across 298 proteins, derived from protease sensitivity experiments on small proteins (<75 residues). The **Fireprot dataset** was curated from FireProtDB, containing 3,438 mutations across 100 unique proteins with a wider distribution of protein sizes. Both datasets were clustered at 25% sequence identity using MMseqs2, with cross-referencing to ensure no homology overlap between train and test sets. The Megascale dataset was split approximately 80/10/10 (train/validation/test) by mutation count.

The model was trained on experimental stability measurements (ddG values) from mutation studies, using transfer learning from ProteinMPNN's protein design representations.

### Loss Function & Objective

Regression loss for predicting ddG (change in Gibbs free energy of unfolding) in kcal/mol upon single-point mutations.

### Tokenization / Input Processing

Input processing involves:

1. **PDB parsing**: Structure parsed using `alt_parse_PDB` from ProteinMPNN utilities
2. **Chain selection**: Target chain extracted (first chain if not specified)
3. **Feature extraction**: Backbone coordinates and residue identities extracted
4. **Mutation encoding**: Wild-type and mutant amino acids encoded using the 20-letter + X alphabet (ACDEFGHIKLMNPQRSTVWYX)
5. **Graph construction**: Structure represented as a k-nearest-neighbors graph of backbone atoms

## Performance & Benchmarks

### Published Benchmarks

From Dieckhaus et al. (2023):

| Dataset | Metric | ThermoMPNN | ProteinMPNN (naive) |
|---------|--------|-----------|-------------------|
| Megascale test | Spearman (SCC) | 0.725 +/- 0.003 | 0.487 +/- 0.006 |
| Fireprot test | Spearman (SCC) | 0.657 +/- 0.003 | 0.50 +/- 0.01 |
| Megascale test | Pearson (PCC) | 0.754 +/- 0.004 | -- |
| SSYM direct | Pearson (PCC) | 0.72 | -- |
| SSYM inverse | Pearson (PCC) | 0.60 | -- |
| S669 | Pearson (PCC) | 0.43 | -- |

ThermoMPNN outperformed Rosetta, RaSP, and PROSTATA on both Megascale and Fireprot datasets (PCC 0.04-0.05 higher than any other method). Transfer learning from pre-trained ProteinMPNN was critical: training from naive weights reduced Megascale SCC to 0.642 and Fireprot SCC to 0.50. The light attention module provided a small but consistent performance boost across both datasets.

### BioLM Verification Results

Integration tests use structural validation (checking response format, mutation fields, and numeric ddG values) rather than exact numerical matching, due to the structure-dependent nature of predictions.

### Comparison to Alternatives

| Model | Task | Input | Advantage |
|-------|------|-------|-----------|
| **ThermoMPNN** | Single mutation ddG | PDB structure | Fast, structure-aware single mutations |
| ThermoMPNN-D | Single + double mutation ddG | PDB structure | Handles epistatic double mutations |
| TemBERTure | Thermophilicity + Tm | Sequence only | No structure needed |

## Strengths & Limitations

### Pros

- Structure-aware: uses 3D backbone coordinates for predictions
- Transfer learning from ProteinMPNN provides strong structural representations
- Supports both targeted mutations and full site-saturation mutagenesis (SSM) scans
- Per-mutation ddG predictions (not just global stability)
- Fast inference on GPU

### Cons

- Requires PDB structure input (not sequence-only)
- Batch size limited to 1 PDB at a time
- Maximum sequence length of 1024 residues
- Single-point mutations only (use ThermoMPNN-D for double mutations)

### Known Failure Modes

- Missing residues in PDB (gaps) are flagged as "-" and handled, but may affect nearby predictions
- PDB files with non-standard formatting may fail during parsing
- Very large structures (beyond 1024 residues) may exceed GPU memory limits; 1024 residues is the recommended upper bound but is not enforced at the API level

## Implementation Details

### Inference Pipeline

```
Request --> Validate PDB + mutations
  --> Write PDB to temp file
  --> Parse PDB (alt_parse_PDB)
  --> Select chain
  --> Build mutation objects (0-indexed internally, 1-indexed in chain's modeled sequence externally)
  --> [GPU] Forward pass through ThermoMPNN
  --> Extract ddG predictions
  --> Format response (1-indexed positions within chain's modeled sequence)
  --> Cleanup temp files
```

### Memory & Compute Profile

| Resource | Value |
|----------|-------|
| GPU | T4 |
| Memory | 8 GB |
| CPU | 2 cores |

### Determinism & Reproducibility

- Torch manual seed: Yes (42)
- CUDA manual seed: Yes (42)
- Model set to eval mode: Yes
- Inference under `torch.no_grad()`: Yes

### Caching Behavior

Response caching is handled outside the model container and is not the responsibility of the inference code.

## Versions & Changelog

| Version | Date | Changes |
|---------|------|---------|
| v1 | 2024 | Initial implementation |

---

*See also: [README.md](README.md) for API reference | [BIOLOGY.md](BIOLOGY.md) for biological context*
