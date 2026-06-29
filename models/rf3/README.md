# RosettaFold3 (RF3)

> **One-line summary**: All-atom biomolecular structure prediction network using transformer + diffusion architecture, capable of predicting protein, DNA, RNA, and ligand complexes with confidence scoring.

## Overview

RosettaFold3 is an all-atom biomolecular structure prediction network competitive with leading open-source models. It improves on tasks such as prediction of chiral ligands and fixed-backbone or fixed-conformer docking.

This implementation wraps the RosettaFold3 model from the [RosettaCommons/foundry](https://github.com/RosettaCommons/foundry) repository into a Modal app following the BioLM patterns. RF3 can:

- Predict protein structures with or without MSAs
- Predict multi-component complexes (protein-protein, protein-DNA, protein-RNA, protein-ligand)
- Handle non-canonical amino acids and covalent modifications
- Template portions of structures while folding others
- Predict chiral small molecules accurately
- Early-stop low-confidence predictions to save compute

## Architecture

| Property | Value |
|----------|-------|
| Architecture | Transformer + Diffusion |
| Training objective | All-atom structure prediction |
| Input modalities | Sequence, Structure, SMILES, MSA |
| Input molecules | Protein, DNA, RNA, Ligand, Complex |
| Output | Predicted 3D structure (mmCIF format) |
| Max sequence length | 2048 tokens |

### Model Files

- `__init__.py` - Package initialization
- `app.py` - Main Modal app with RF3 inference engine
- `schema.py` - Pydantic request/response schemas
- `config.py` - Model family configuration
- `download.py` - Model weight download logic
- `fixture.py` - Test fixture generator
- `test.py` - Model tests

### Available Checkpoints

The "latest" checkpoint is used by default (most recent release with bugfixes). The upstream IPD server also hosts `preprint` and `benchmark` checkpoint variants, but only the `latest` checkpoint is exposed through this API.

## Model Variants

RF3 is a single-variant model with no variant axes. All requests are served by a single deployment (`rf3`). Multiple checkpoints exist (latest, preprint, benchmark) but the latest checkpoint is used by default.

## Capabilities & Limitations

**CAN be used for:**
- Protein structure prediction (single chain or multi-chain)
- Protein-protein, protein-DNA, protein-RNA, and protein-ligand complex prediction
- Templated folding (fixing portions of a structure)
- Chiral small molecule prediction
- MSA-enhanced structure prediction
- Multi-sample diffusion batching with confidence ranking

**CANNOT be used for:**
- Sequences longer than 2048 residues
- Real-time interactive folding (diffusion sampling is computationally expensive)
- Training or fine-tuning (inference only)

**Other considerations:**
- MSAs significantly improve prediction quality for proteins
- Early stopping can save 10-20x compute for low-confidence predictions
- Output structures are returned in mmCIF format (may be gzipped)
- Multiple samples from the diffusion batch are ranked by confidence

## Actions / Endpoints

### `fold`

Predicts all-atom biomolecular structures from sequences, SMILES strings, and/or template structures.

**Request Parameters:**

| Parameter | Type | Default | Range | Description |
|-----------|------|---------|-------|-------------|
| `items[].name` | str | *(required)* | -- | Name for this prediction task |
| `items[].components[].name` | str | *(required)* | -- | Component name |
| `items[].components[].type` | str | *(required)* | "protein", "DNA", "RNA", "ligand" | Entity type |
| `items[].components[].sequence` | str | None | -- | Sequence string (for protein/DNA/RNA) |
| `items[].components[].smiles` | str | None | -- | SMILES string (for ligands) |
| `items[].components[].ccd_code` | str | None | -- | Chemical Component Dictionary code |
| `items[].components[].structure_cif` | str | None | -- | Template structure in mmCIF format |
| `items[].components[].chain_id` | str | None | -- | Chain identifier |
| `items[].components[].msa_content` | str | None | -- | MSA content in A3M format |
| `items[].bonds` | list | None | -- | Custom bonds as pairs of atom specifications |
| `params.n_recycles` | int | 10 | 0-20 | Number of trunk recycles |
| `params.num_steps` | int | 200 | 50-500 | Number of diffusion sampling steps |
| `params.diffusion_batch_size` | int | 5 | 1-10 | Number of output structures to generate |
| `params.seed` | int | 42 | -- | Random seed for reproducibility |
| `params.template_selection` | list[str] | None | -- | Atom selections for token-level templates |
| `params.ground_truth_conformer_selection` | list[str] | None | -- | Atom selections for ground truth conformers |
| `params.cyclic_chains` | list[str] | None | -- | List of chain IDs to cyclize |
| `params.early_stopping_plddt_threshold` | float | 0.5 | 0.0-1.0 | pLDDT threshold for early stopping |
| `params.one_model_per_file` | bool | False | -- | Save each model to separate file |
| `params.annotate_b_factor_with_plddt` | bool | False | -- | Annotate B-factor column with pLDDT |
| `params.include_pae` | bool | False | -- | Include Predicted Aligned Error matrix |
| `params.include_plddt` | bool | True | -- | Include per-residue pLDDT scores |

**Response:**

| Field | Type | Description |
|-------|------|-------------|
| `results[][]` | list[list] | Nested results: [batch][diffusion_samples] |
| `results[][].structure_cif` | str | Predicted structure in mmCIF format |
| `results[][].confidence.ptm` | float | Predicted TM-score (0-1) |
| `results[][].confidence.iptm` | float | Interface predicted TM-score (multi-chain) |
| `results[][].confidence.ranking_score` | float | Overall ranking score |
| `results[][].confidence.has_clash` | bool | Whether structure has clashes |
| `results[][].confidence.plddt` | list[float] | Per-residue pLDDT scores (0-100) |
| `results[][].confidence.pae` | list[list[float]] | Predicted Aligned Error matrix (optional) |
| `results[][].early_stopped` | bool | Whether prediction was early-stopped |
| `results[][].sample_idx` | int | Sample index within diffusion batch |

## Usage Examples

### Simple Protein Folding

```python
from models.rf3.schema import (
    RF3PredictRequest,
    RF3PredictRequestInput,
    RF3PredictParams,
    RF3Component,
    RF3EntityType,
)

request = RF3PredictRequest(
    params=RF3PredictParams(
        n_recycles=10,
        num_steps=200,
        diffusion_batch_size=5,
    ),
    items=[
        RF3PredictRequestInput(
            name="simple_fold",
            components=[
                RF3Component(
                    name="protein",
                    type=RF3EntityType.PROTEIN,
                    sequence="MKLLISC...",
                    chain_id="A",
                )
            ],
        )
    ],
)
```

### Protein with MSA

```python
from models.rf3.schema import (
    RF3PredictRequest,
    RF3PredictRequestInput,
    RF3PredictParams,
    RF3Component,
    RF3EntityType,
)

request = RF3PredictRequest(
    params=RF3PredictParams(
        n_recycles=10,
        include_plddt=True,
    ),
    items=[
        RF3PredictRequestInput(
            name="with_msa",
            components=[
                RF3Component(
                    name="protein",
                    type=RF3EntityType.PROTEIN,
                    sequence="MKLLIS...",
                    chain_id="A",
                    msa_content=">seq1\nMKLLIS...\n>seq2\nMKLLVS...",
                )
            ],
        )
    ],
)
```

### Protein-Ligand Complex

```python
from models.rf3.schema import (
    RF3PredictRequest,
    RF3PredictRequestInput,
    RF3PredictParams,
    RF3Component,
    RF3EntityType,
)

request = RF3PredictRequest(
    params=RF3PredictParams(
        diffusion_batch_size=5,
        ground_truth_conformer_selection=["B"],
    ),
    items=[
        RF3PredictRequestInput(
            name="protein_ligand",
            components=[
                RF3Component(
                    name="protein",
                    type=RF3EntityType.PROTEIN,
                    sequence="MKLLIS...",
                    chain_id="A",
                ),
                RF3Component(
                    name="ligand",
                    type=RF3EntityType.LIGAND,
                    smiles="CC(=O)OC1=CC=CC=C1C(=O)O",  # Aspirin
                    chain_id="B",
                ),
            ],
        )
    ],
)
```

### Templated Folding

```python
from models.rf3.schema import (
    RF3PredictRequest,
    RF3PredictRequestInput,
    RF3PredictParams,
    RF3Component,
    RF3EntityType,
)

request = RF3PredictRequest(
    params=RF3PredictParams(
        template_selection=["A/*/1-50"],
        n_recycles=10,
    ),
    items=[
        RF3PredictRequestInput(
            name="templated_fold",
            components=[
                RF3Component(
                    name="protein",
                    type=RF3EntityType.PROTEIN,
                    sequence="MKLLIS...",
                    structure_cif="...",
                    chain_id="A",
                )
            ],
        )
    ],
)
```

## Performance & Benchmarks

### Endpoint Performance

- **Fold**: Depends on sequence length, diffusion steps, and batch size
- **Max sequence length**: 2048 residues

### Model Parameters

- `n_recycles`: 0-20 (default: 10) - Number of trunk recycles
- `num_steps`: 50-500 (default: 200) - Diffusion sampling steps
- `diffusion_batch_size`: 1-10 (default: 5) - Number of output structures
- `early_stopping_plddt_threshold`: 0.0-1.0 (default: 0.5) - Early stop threshold

## Implementation Verification

Deploying the app and running tests:

```bash
# Deploy
python models/rf3/app.py --force-deploy

# Generate fixtures
python models/rf3/fixture.py

# Run tests
python models/rf3/test.py
```

## Resource Requirements

| Variant | GPU | Memory | CPU |
|---------|-----|--------|-----|
| `rf3` | A100 40GB | 64 GB | 8 cores |

## Implementation Notes

- The model requires the foundry package with atomworks dependencies
- Checkpoint files should be downloaded to R2 storage before deployment
- MSAs significantly improve prediction quality for proteins
- Early stopping can save 10-20x compute for low-confidence predictions
- Output structures are returned in mmCIF format (may be gzipped)
- Multiple samples from the diffusion batch are ranked by confidence

### Confidence Metrics

RF3 provides several confidence metrics:

- **pTM**: Predicted TM-score (0-1, higher is better)
- **ipTM**: Interface predicted TM-score for multi-chain predictions
- **ranking_score**: Overall ranking score (0.8 * ipTM + 0.2 * pTM - 100 * has_clash)
- **has_clash**: Boolean indicating if chains are clashing
- **pLDDT**: Per-residue confidence scores (0-100)
- **PAE**: Predicted Aligned Error matrix (optional, disabled by default for size)

## License

- **RosettaFold3 / Foundry**: BSD 3-Clause License ([LICENSE](https://github.com/RosettaCommons/foundry))

## References & Citations

### BibTeX

```bibtex
@article{corley2025accelerating,
  title={Accelerating biomolecular modeling with atomworks and rf3},
  author={Corley, Nathaniel and Mathis, Simon and ...},
  journal={bioRxiv},
  year={2025}
}
```

### Links

- **Paper**: [Accelerating Biomolecular Modeling with AtomWorks and RF3](https://doi.org/10.1101/2025.08.14.670328)
- **Code**: [RosettaCommons/foundry](https://github.com/RosettaCommons/foundry)

---

*See also: [MODEL.md](MODEL.md) for technical deep-dive | [BIOLOGY.md](BIOLOGY.md) for biological context*
