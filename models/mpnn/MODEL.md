# MPNN (ProteinMPNN / LigandMPNN)  --  Technical Details

## Architecture

### Model Type & Innovation

MPNN is a message-passing neural network (GNN) for **inverse folding**: given a protein backbone structure (3D coordinates), it designs amino acid sequences predicted to fold into that structure. This is the inverse of the protein folding problem (sequence to structure).

The key innovation of ProteinMPNN (Dauparas et al., Science 2022) over prior inverse folding methods is a **structured noise injection** during autoregressive decoding that prevents the model from copying the native sequence from spatial neighbors already decoded. This, combined with an encoder-decoder GNN architecture operating on k-nearest-neighbor graphs of backbone atoms, achieves dramatically higher experimental success rates than previous methods like Rosetta fixed-backbone design.

**LigandMPNN** extends ProteinMPNN to be aware of non-protein atoms --- ligands, nucleic acids, metals, water molecules, and non-standard residues --- by incorporating atomic context from HETATM records in the PDB input. Additional specialized variants handle membrane proteins through global or per-residue transmembrane labels.

**HyperMPNN** is a variant retrained with hypernetwork-based conditioning, using the same ProteinMPNN architecture but with different checkpoint weights tuned for improved sampling diversity.

### Parameters & Layers

| Component | Details |
|-----------|---------|
| Architecture | Message-passing GNN (encoder-decoder) |
| Node features | 128 dimensions |
| Edge features | 128 dimensions |
| Hidden dimensions | 128 |
| Encoder layers | 3 |
| Decoder layers | 3 |
| k-nearest neighbors | Checkpoint-dependent (stored in checkpoint) |
| Atom context (LigandMPNN) | Checkpoint-dependent (`atom_context_num` from checkpoint) |
| Atom context (other variants) | 1 |

**Side-Chain Packer (auxiliary model):**

| Component | Details |
|-----------|---------|
| Architecture | Packer GNN |
| Node/Edge features | 128 dimensions |
| Positional embeddings | 16 |
| Chain embeddings | 16 |
| RBF features | 16 |
| Encoder/Decoder layers | 3 each |
| Atom context | 16 |
| Number of mixture components | 3 |
| Top-k neighbors | 32 |

### Checkpoint Variants

| Variant | Checkpoint | Description |
|---------|------------|-------------|
| `protein` | `proteinmpnn_v_48_020.pt` | Standard ProteinMPNN for protein-only design |
| `ligand` | `ligandmpnn_v_32_010_25.pt` | Ligand-aware design (handles HETATM atoms) |
| `soluble` | `solublempnn_v_48_020.pt` | Optimized for soluble proteins |
| `global_label_membrane` | `global_label_membrane_mpnn_v_48_020.pt` | Membrane protein design with global label |
| `per_residue_label_membrane` | `per_residue_label_membrane_mpnn_v_48_020.pt` | Membrane design with per-residue labels |
| `hyper` | `v48_020_epoch300_hyper.pt` | HyperMPNN retrained variant (uses ProteinMPNN architecture) |
| `side_chain` | `ligandmpnn_sc_v_32_002_16.pt` | Side-chain packing model (loaded alongside all variants) |

### Training Data

| Property | Details |
|----------|---------|
| Dataset | Protein Data Bank (PDB) |
| Filtering | Clustered by structure similarity; high-resolution structures |
| Composition | Protein backbone structures with associated sequences |
| Additional (LigandMPNN) | Structures with bound ligands, nucleic acids, metals |
| Temporal cutoff | Pre-2022 PDB structures |

The model was trained to predict native sequences from backbone coordinates, learning the relationship between local structural environments and amino acid identity.

### Loss Function & Objective

The model is trained with **cross-entropy loss** on native sequence recovery --- predicting the identity of each residue given its structural context. The autoregressive decoder generates one residue at a time, conditioned on the backbone structure (from the encoder) and previously generated residues. Structured random noise is added to the decoding order to prevent the model from simply copying neighbors.

### Tokenization / Input Processing

- **Input**: PDB-format structure files containing backbone atom coordinates (N, CA, C, O)
- **Graph construction**: k-nearest-neighbor graph based on CA-CA distances
- **Node features**: Local coordinate frames derived from backbone geometry
- **Edge features**: Relative position and orientation between residue pairs
- **LigandMPNN additional**: Non-protein atom coordinates and types from HETATM records
- **Membrane variants**: Per-residue or global transmembrane labels (buried/interface/soluble)
- **Maximum sequence length**: 1024 residues (from `MPNNParams.max_sequence_len`)

## Performance & Benchmarks

### Published Benchmarks

From Dauparas et al. (Science, 2022):

| Method | Sequence Recovery (%) | Experimental Success Rate |
|--------|----------------------|--------------------------|
| **ProteinMPNN** | **~52%** | **~70-100% of designs express and fold** |
| Rosetta (fixed backbone) | ~33% | ~15-30% |
| StructGNN | ~40% | Not tested experimentally |

Key result: ProteinMPNN-designed proteins had substantially higher experimental success rates across a diverse set of de novo protein structures, with many designs confirmed by X-ray crystallography to match intended structures with sub-angstrom accuracy.

### Comparison to Alternatives

| Model | Approach | Strengths | When to Prefer |
|-------|----------|-----------|----------------|
| **ProteinMPNN** | GNN, autoregressive | Fast, high success rate, well-validated | General protein design |
| **LigandMPNN** | GNN with atomic context | Handles ligands, metals, nucleic acids | Protein-ligand complexes, enzyme design |
| ESM-IF | Transformer, inverse folding | Leverages ESM pretraining | When ESM embeddings are also needed |
| ProteinSolver | GNN | Earlier method | Generally prefer MPNN |

## Strengths & Limitations

### Pros

- Extremely well-validated experimentally --- many thousands of designs confirmed in the lab
- Fast inference: runs on CPU, no GPU required
- Supports diverse design scenarios: fixed residues, redesigned residues, symmetry constraints, homo-oligomer design
- LigandMPNN variant handles complex molecular environments (ligands, metals, DNA/RNA)
- Membrane-aware variants for transmembrane protein design
- Side-chain packing capability for complete all-atom models
- Stochastic sampling with temperature control enables diversity

### Cons

- Designs based on fixed backbone --- does not remodel backbone geometry
- Sequence recovery (~52%) means many positions differ from native; not all designs will fold
- No explicit modeling of long-range evolutionary constraints (unlike MSA-based methods)
- Side-chain packing is approximate; may benefit from downstream refinement (e.g., Rosetta relax)
- Maximum sequence length of 1024 residues

### Known Failure Modes

- Very small proteins (<30 residues) may have insufficient structural context for reliable design
- Highly flexible or disordered regions produce unreliable designs (model assumes fixed backbone)
- Unusual ligand types not represented in training data may not be properly handled by LigandMPNN
- Homo-oligomer mode assumes symmetric chains --- asymmetric complexes need manual residue specification

## Implementation Details

### Inference Pipeline

```
Request
  |-- 1. Validate PDB input and parameters against variant-specific schema
  |-- 2. Write PDB to temporary file (/tmp_pdbs/)
  |-- 3. Parse PDB: extract backbone, chain letters, residue indices, ligand atoms
  |-- 4. Build k-NN graph and featurize (encode structural features)
  |-- 5. Apply constraints: fixed residues, redesigned residues, chain masks, symmetry
  |-- 6. Apply biases: per-AA bias, per-residue bias, omit AAs
  |-- 7. Autoregressive sampling (batch_size sequences x number_of_batches)
  |     |-- Random decoding order with structured noise
  |     |-- Temperature-scaled softmax sampling
  |     |-- Symmetry-linked positions sampled together
  |-- 8. Score designs: overall confidence, ligand confidence, sequence recovery
  |-- 9. [Optional] Pack side chains with Packer model
  |-- 10. Write output PDB files with designed sequences
  |-- 11. Return: sequences, PDBs, confidence scores, log_probs, sampling_probs
```

### Memory & Compute Profile

| Property | Value |
|----------|-------|
| GPU | None (CPU-only inference) |
| Memory | 128 MB |
| CPU | 0.125 cores |
| Batch size limit | Up to 1000 sequences per batch |
| Max batches | Up to 48 batches per request |

The model is lightweight enough to run entirely on CPU, making it very cost-effective.

### Determinism & Reproducibility

- **User-provided seed**: When `seed` is specified in the request, all RNG sources are seeded (Python `random`, NumPy, PyTorch CPU, PyTorch CUDA) for reproducible results
- **Default behavior**: When no seed is provided, a time-based seed (`time.time_ns() % 2^32`) is used, producing different designs each call
- **Model loading**: `torch.manual_seed(42)` is set during CPU snapshot loading for consistent initialization
- **Note**: cuDNN benchmark mode is not explicitly disabled, so minor numerical differences may occur across different hardware

### Caching Behavior

- Response caching (Redis/R2 two-tier) is handled by the BioLM platform layer, not the model container
- Redis (Modal Dict) and R2 caching are available via the billing mixin
- Cache keys are composed from request parameters including PDB content and generation parameters
- Given the stochastic nature of sequence design, caching is most useful when a fixed seed is provided

## Versions & Changelog

| Version | Date | Changes |
|---------|------|---------|
| v1 | Initial | ProteinMPNN, LigandMPNN, SolubleMPNN, Membrane variants |
| v1 | Update | Added HyperMPNN variant with GitHub fallback download |
| v1 | Update | Side-chain packing support via Packer model |

---

*See also: [README.md](README.md) for API reference | [BIOLOGY.md](BIOLOGY.md) for biological context*
