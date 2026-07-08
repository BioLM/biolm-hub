# Chai-1

> **One-line summary**: Multi-modal biomolecular structure prediction model capable of predicting 3D structures of proteins, DNA, RNA, ligands, glycans, and their complexes.

## Overview

Chai-1 is a multi-modal foundation model for molecular structure prediction developed by Chai Discovery. It predicts the joint 3D structure of complexes containing proteins, nucleic acids (DNA/RNA), small molecule ligands, and other biomolecules from their sequences.

Chai-1 achieves accuracy competitive with AlphaFold3 on structure prediction benchmarks while being fully open-source under the Apache-2.0 license. Its key innovation is the ability to handle heterogeneous molecular complexes in a single forward pass, combining diffusion-based structure generation with transformer-based sequence processing.

The primary use case is predicting the 3D atomic coordinates of biomolecular complexes, returned in mmCIF format. This is valuable for drug discovery (protein-ligand docking), understanding molecular interactions, and structural biology research.

## Architecture

| Property | Value |
|----------|-------|
| Architecture | Transformer + Diffusion |
| Input modalities | Sequence, SMILES, MSA |
| Input molecule types | Protein, DNA, RNA, Ligand, Complex |
| Task | Structure prediction |
| Output | 3D atomic coordinates (mmCIF) |
| Variants | Single variant (no size options) |

Chai-1 uses a trunk network with recycling iterations followed by a diffusion module that generates 3D coordinates. ESM embeddings can optionally be used to enrich the protein sequence representations.

## Model Variants

Single variant -- no size options.

## Capabilities & Limitations

**CAN be used for:**
- Predicting 3D structures of single-chain proteins (up to 1024 residues)
- Predicting structures of protein-protein complexes
- Predicting protein-DNA and protein-RNA complexes (nucleic acids up to 3072 bases)
- Predicting protein-ligand binding poses (ligands specified via SMILES, up to 128 characters)
- Multi-component complexes with up to 5 molecular entities
- Incorporating pre-computed MSA alignments (UniRef90, MGnify, small_bfd) for improved accuracy

**CANNOT be used for:**
- Protein sequences longer than 1024 residues
- DNA/RNA sequences longer than 3072 bases
- Ligand SMILES strings longer than 128 characters
- More than 5 molecular entities per complex
- Batch processing (batch size is fixed at 1)
- Dynamics or conformational ensembles (produces static structures)

**Other considerations:**
- Inference is stochastic: different seeds or diffusion samples produce different structure predictions
- The `num_diffn_samples` parameter controls how many candidate structures are generated (1-5)
- More trunk recycles and diffusion timesteps improve accuracy at the cost of longer inference time
- PAE and pLDDT confidence scores are currently disabled in the response due to large payload sizes

## Actions / Endpoints

### `fold`

Predicts the 3D structure of a biomolecular complex from input molecule sequences.

**Request Parameters:**

| Parameter | Type | Default | Range | Description |
|-----------|------|---------|-------|-------------|
| `params.num_trunk_recycles` | int | 3 | 1-10 | Number of trunk recycling iterations |
| `params.num_diffusion_timesteps` | int | 200 | 50-200 | Number of diffusion denoising steps |
| `params.num_diffn_samples` | int | 1 | 1-5 | Number of structure samples to generate |
| `params.use_esm_embeddings` | bool | true | - | Whether to use ESM protein embeddings |
| `params.seed` | int | 42 | - | Random seed for reproducibility |
| `items[].molecules[].name` | str | - | - | Name identifier for the molecule |
| `items[].molecules[].type` | enum | - | protein, DNA, RNA, ligand, polymer_hybrid, water, unknown | Molecule type |
| `items[].molecules[].sequence` | str | - | - | Amino acid, nucleotide, or SMILES sequence |
| `items[].molecules[].smiles` | str | - | - | SMILES string (alternative to sequence for ligands) |
| `items[].molecules[].alignment` | dict | - | - | Pre-computed MSA alignments (protein only; keys: mgnify, small_bfd, uniref90) |

**Response:**

```json
{
  "results": [
    [
      {
        "cif": "data_pred_model_0\n_entry.id pred_model_0\n..."
      }
    ]
  ]
}
```

The response contains a nested list: the outer list corresponds to input items, the inner list contains one result per diffusion sample. Each result includes:
- `cif`: Full mmCIF-format string containing the predicted 3D coordinates
- `pae`: Predicted Aligned Error matrix (currently disabled)
- `plddt`: Per-residue confidence scores (currently disabled)

## Usage Examples

```python
from models.chai1.schema import (
    Chai1Molecule,
    Chai1EntityType,
    Chai1FoldRequest,
    Chai1FoldRequestInput,
    Chai1FoldRequestParams,
)

# Predict structure of a protein-ligand complex
request = Chai1FoldRequest(
    params=Chai1FoldRequestParams(
        num_trunk_recycles=3,
        num_diffusion_timesteps=200,
        num_diffn_samples=1,
        seed=42,
    ),
    items=[
        Chai1FoldRequestInput(
            molecules=[
                Chai1Molecule(
                    name="target_protein",
                    type=Chai1EntityType.PROTEIN,
                    sequence="MKTVRQERLKSIVRILERSKEPVSG",
                ),
                Chai1Molecule(
                    name="drug_molecule",
                    type=Chai1EntityType.LIGAND,
                    smiles="CC(=O)Oc1ccccc1C(=O)O",
                ),
            ]
        )
    ],
)
```

```python
# Protein-DNA complex with MSA alignment
request = Chai1FoldRequest(
    items=[
        Chai1FoldRequestInput(
            molecules=[
                Chai1Molecule(
                    name="transcription_factor",
                    type=Chai1EntityType.PROTEIN,
                    sequence="MKTVRQERLKSIVRILERSKEPVSG",
                    alignment={
                        "uniref90": ">query\nMKTVRQERLKSIVRILERSKEPVSG\n>hit1\nMKTVRQERLKSIVRILERSKEPVSG\n",
                    },
                ),
                Chai1Molecule(
                    name="dna_target",
                    type=Chai1EntityType.DNA,
                    sequence="ATCGATCGATCG",
                ),
            ]
        )
    ],
)
```

## Performance & Benchmarks

### Published Results

Chai-1 demonstrates competitive performance with AlphaFold3 across multiple structure prediction benchmarks, including protein monomer folding, protein-protein complexes, protein-nucleic acid complexes, and protein-ligand docking. Detailed benchmark comparisons are available in the Chai Discovery technical report.

### SOTA Status

Competitive with AlphaFold3 on multi-modal structure prediction benchmarks as of 2024. First fully open-source model to achieve this level of accuracy on heterogeneous biomolecular complex prediction.

## Implementation Verification

### Verification Method

Option A (Numerical Reproduction): The BioLM implementation wraps the official `chai-lab` Python package (v0.6.1) directly, calling `chai_lab.chai1.run_inference` with identical parameters. This ensures numerical equivalence with the reference implementation.

### Test Cases

Integration tests use golden output comparisons with RMSD thresholds (0.5 Å for single-protein,
3.5 Å for MSA-assisted) against reference outputs stored in R2. Deployment tests validate basic
response structure using a minimal 1-residue protein input.

### Verification Status

**Status: PARTIALLY VERIFIED** -- Implementation uses the official chai-lab library directly, ensuring functional equivalence. Quantitative benchmarking against known structures is pending.

## Resource Requirements

| Resource | Value |
|----------|-------|
| GPU | A100 80GB |
| Memory | 64 GB |
| CPU | 8 cores |
| Cold start | ~3-5 minutes (memory snapshot enabled) |
| Inference P50 | ~30-120 seconds (depends on complex size and parameters) |
| Dependencies | `chai-lab==0.6.1`, `torch==2.6.0`, `biopython==1.83` |

## Implementation Notes

- **Memory snapshots**: Uses `@modal.enter(snap=True)` to load the Chai1 environment and import `chai_lab` components on CPU. The `snap=False` phase sets up GPU device and CUDA seeds.
- **Weight management**: Model weights are downloaded via R2 with fallback to the chai-lab library's native download mechanism. Lock files are created to prevent redundant downloads.
- **Determinism**: Seeds are set for `torch.manual_seed(42)` and `torch.cuda.manual_seed_all(42)`, but diffusion sampling introduces stochasticity. Use the `seed` parameter to control reproducibility.
- **Batch size**: Fixed at 1 due to the complexity and memory requirements of structure prediction.
- **MSA handling**: Pre-computed MSA alignments are converted to A3M format files and merged using Chai1's internal `merge_a3m_in_directory` utility before inference.
- **Temporary files**: Inference uses temporary FASTA files and output directories that are cleaned up after each request.

## Confidence Metrics

| Metric | Range | Interpretation |
|--------|-------|----------------|
| pLDDT | 0-100 | Per-residue confidence. >90: high confidence, 70-90: moderate, <70: low confidence / disordered |
| PAE | 0-31.75 A | Predicted Aligned Error between residue pairs. Lower is better. <5 A indicates confident relative positioning |

Note: PAE and pLDDT scores are currently disabled in the API response due to large payload sizes. The `include` parameter is accepted but forced to an empty list.

## License

- **Code**: Apache-2.0 ([LICENSE](https://github.com/chaidiscovery/chai-lab/blob/main/LICENSE))
- **Weights**: Apache-2.0 (same license covers both code and model weights)

## References & Citations

### Papers

1. Chai Discovery. "Chai-1: Decoding the molecular interactions of life." *Chai Discovery Technical Report* (2024).

### BibTeX

```bibtex
@article{chaidiscovery2024chai1,
  title={Chai-1: Decoding the molecular interactions of life},
  author={{Chai Discovery}},
  year={2024}
}
```

### Links

- **Code**: [GitHub chaidiscovery/chai-lab](https://github.com/chaidiscovery/chai-lab)
- **Website**: [Chai Discovery](https://www.chaidiscovery.com/)

---

*See also: [MODEL.md](MODEL.md) for technical deep-dive | [BIOLOGY.md](BIOLOGY.md) for biological context*
