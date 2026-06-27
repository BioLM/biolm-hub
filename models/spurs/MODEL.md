# SPURS -- Technical Details

## Architecture

### Model Type & Innovation

SPURS (Structure Prediction Using Residue-level and Secondary structure information) is a structure-aware protein stability prediction model that predicts the change in free energy upon mutation (ddG). It combines ESM2-650M sequence embeddings with 3D structural features through a graph neural network architecture.

The model provides two inference modes: a single-mutation model (SPURS) for predicting individual point mutations and generating full deep mutational scanning (DMS) matrices, and a multi-mutation model (SPURSMulti) for predicting the combined effect of multiple simultaneous mutations.

### Parameters & Layers

| Component | Value |
|-----------|-------|
| Sequence encoder | ESM2-650M (cached locally) |
| Structure input | PDB/CIF parsed by biotite |
| Single model class | SPURS |
| Multi-mutation model class | SPURSMulti |
| Output dimension | 20 (one ddG value per canonical amino acid) |
| Amino acid alphabet | ACDEFGHIKLMNPQRSTVWY (canonical 20) |

The model loads SPURS weights from HuggingFace (`cyclization9/SPURS`) at a pinned revision for reproducibility.

### Training Data

| Property | Details |
|----------|---------|
| Source | Experimental ddG measurements from protein stability databases |
| Structure input | PDB structures for structural context |
| Sequence features | ESM2-650M embeddings |

<!-- TODO: Document specific training datasets (e.g., ProTherm, Megascale) and training set sizes from the SPURS paper/repository -->

### Loss Function & Objective

The model is trained to predict ddG values (change in folding free energy upon mutation) in kcal/mol. Negative ddG indicates stabilizing mutations; positive ddG indicates destabilizing mutations.

### Tokenization / Input Processing

| Property | Details |
|----------|---------|
| Sequence validation | 20 canonical amino acids |
| Max sequence length | 1024 residues |
| Structure input | PDB or CIF format |
| Structure parsing | biotite (CIF -> PDB conversion if needed) |
| Mutation format | `<WT><position><MT>` (1-indexed, e.g., "M3L") |
| Variant sequence | Optional auto-calculation of mutations from WT/variant alignment |

## Performance & Benchmarks

### Published Benchmarks

<!-- TODO: Extract specific benchmark numbers (Spearman correlation, RMSE on ProTherm/Megascale/S669) from SPURS paper or repository -->

### BioLM Verification Results

| Test Case | Tolerance | Status |
|-----------|-----------|--------|
| Single mutation ddG | rel_tol 1e-4 | PASS |
| Multi-mutation ddG + contributions | rel_tol 1e-4 | PASS |
| Full DMS matrix | rel_tol 1e-4 | PASS |
| Variant sequence auto-calculation | rel_tol 1e-4 | PASS |

### Comparison to Alternatives

| Model | Type | Key Advantage | Key Disadvantage |
|-------|------|---------------|------------------|
| **SPURS (this)** | Structure-aware GNN | Full DMS matrix in single pass, multi-mutation support | Requires 3D structure |
| RaSP | Structure-aware | Fast DMS generation | Different architecture |
| DDGun3D | Structure-aware | Established benchmark | Older approach |
| ESM-1v | Sequence-only | No structure needed | No structural context |
| GEMME | Evolutionary | MSA-based, interpretable | Requires MSA |

### Error Bars & Confidence

SPURS is deterministic when seeds are set. The same input produces the same output on the same hardware. Multi-mutation predictions use the SPURSMulti model for combined effects rather than simple additivity.

## Strengths & Limitations

### Pros

- Full saturation mutagenesis matrix in a single forward pass (20 ddG values per position)
- Multi-mutation support with per-mutation contribution breakdown
- Structure-aware -- incorporates 3D context for better accuracy
- Variant sequence auto-calculation from WT/variant alignment
- ESM2-650M embeddings cached locally for fast inference

### Cons

- Requires 3D structure input (PDB or CIF)
- Max sequence length 1024 residues
- Single chain analysis only
- Multi-mutation model is separate from single-mutation model
- GPU required (T4 with 16 GB VRAM)

### Known Failure Modes

- **Sequence/structure mismatch**: Providing a sequence that does not match the structure chain raises a `ValueError`
- **Invalid mutations**: Mutations referencing wrong wild-type residue or out-of-bounds position are caught at validation
- **No structure provided**: Both PDB and CIF missing triggers validation error
- **Empty mutation list**: Rejected with explicit error message guiding to full DMS or null

## Implementation Details

### Inference Pipeline

```
Request
  |-- 1. Validate sequence (canonical AA, max 1024 residues)
  |-- 2. Validate structure (PDB/CIF, chain_id)
  |-- 3. Validate mutations or variant_sequence
  |-- 4. Materialize structure to PDB file (convert CIF if needed)
  |-- 5. Parse PDB with SPURS parse_pdb
  |-- 6. Single-model forward pass -> ddG matrix [seq_len, 20]
  |-- 7a. If no mutations: return full DMS matrix
  |-- 7b. If single mutation: extract ddG from matrix
  |-- 7c. If multi-mutation: run multi-model for combined ddG
  |-- 8. Return SpursPredictResponse
```

### Memory & Compute Profile

| Component | Resource |
|-----------|----------|
| CPU | 4 cores |
| Memory | 16 GB RAM |
| GPU | T4 (16 GB VRAM) |
| Inference time (single protein) | ~1-3s (includes ESM2 embedding computation) |

### Determinism & Reproducibility

| Setting | Value |
|---------|-------|
| `torch.manual_seed` | 42 |
| `torch.cuda.manual_seed_all` | 42 |
| `seed_everything` | 42 (SPURS utility) |
| `torch.no_grad` | Yes (inference) |

### Caching Behavior

Response caching (Redis/R2 two-tier) is handled by the BioLM platform layer, not by the model container. GPU memory snapshots are enabled for fast cold starts.

## Versions & Changelog

| Version | Date | Changes |
|---------|------|---------|
| v1 | 2025-09-16 | Initial implementation with predict action (single, multi, full DMS) |
| v1 (updated) | 2026-01-12 | Added variant_sequence auto-calculation mode |
| v1 (updated) | 2025-09-24 | Added CIF support via biotite conversion |

---

*See also: [README.md](README.md) for API reference | [BIOLOGY.md](BIOLOGY.md) for biological context*
