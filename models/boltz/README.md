# Boltz - Biomolecular Structure & Affinity Prediction

> **One-line summary**: Diffusion-based biomolecular structure and affinity prediction for protein, DNA, RNA, and ligand complexes.

Boltz is a family of deep learning models for predicting 3D structures of biomolecular complexes (proteins, DNA, RNA, ligands) and binding affinities. Developed by MIT and Recursion, Boltz-1 was the first fully open-source model to approach AlphaFold3 accuracy. Boltz-2 extends this with joint structure-affinity prediction, approaching the accuracy of physics-based free-energy perturbation (FEP) methods while running 1000x faster.

## Overview

Both variants use a diffusion-based generative architecture with a transformer trunk, trained on protein-ligand, protein-protein, protein-nucleic acid, and small molecule complexes from the PDB.

**Boltz-1** (November 2024): Structure prediction for biomolecular complexes. Matches AlphaFold3 and Chai-1 on diverse benchmarks including CASP15.

**Boltz-2** (June 2025): Adds binding affinity prediction on top of structure prediction. First deep learning model to approach FEP accuracy on the FEP+ benchmark (R = 0.6 correlation with experimental IC50). Won the CASP16 affinity challenge, outperforming all submitted methods across 140 complexes.

## Architecture

| Property | Value |
|----------|-------|
| Architecture | Diffusion-based generative model with transformer trunk |
| Variants | Boltz-1 (structure), Boltz-2 (structure + affinity) |
| Input | Protein, DNA, RNA, ligand sequences + optional MSA |
| Output | mmCIF structures + confidence scores |
| Max sequence length | 1024 residues |

## Model Variants

| Variant | GPU | Capabilities | Use Case |
|---------|-----|-------------|----------|
| `boltz1` | A100 40GB | Structure prediction | Legacy; protein/DNA/RNA/ligand complexes |
| `boltz2` | A100 40GB | Structure + affinity + constraints + templates | Recommended; drug discovery, molecular design |

## Supported Entity Types

| Entity Type | Input | Description |
|-------------|-------|-------------|
| `protein` | Amino acid sequence | Standard amino acid sequences; supports MSA, modifications, cyclic chains |
| `dna` | Nucleotide sequence | DNA strands; supports modifications |
| `rna` | Nucleotide sequence | RNA strands; supports modifications |
| `ligand` | SMILES or CCD code | Small molecules specified by SMILES string or Chemical Component Dictionary code |

## Actions / Endpoints

### `predict`

Predict 3D structure (mmCIF) and confidence scores for a biomolecular complex. Boltz2 additionally supports binding affinity prediction, structural constraints, and template conditioning.

**Request Parameters (common to both variants):**

| Parameter | Type | Default | Range | Description |
|-----------|------|---------|-------|-------------|
| `recycling_steps` | int | 3 | 1-10 | Number of recycling iterations through the model |
| `sampling_steps` | int | 20 | 1-200 | Number of diffusion sampling steps (more = higher quality, slower) |
| `diffusion_samples` | int | 1 | 1-10 | Number of independent structure samples to generate |
| `step_scale` | float | 1.638 | 0.1-10.0 | Diffusion step size / temperature (lower = more diverse samples) |
| `seed` | int | 42 | - | Random seed for reproducibility |
| `potentials` | bool | true | - | Apply inference-time potentials for physically plausible poses |
| `max_msa_seqs` | int | 8192 | 1-32768 | Maximum MSA sequences to use |
| `subsample_msa` | bool | false | - | Whether to subsample the MSA |
| `num_subsampled_msa` | int | 1024 | 1-8192 | Number of MSA sequences to subsample |
| `include` | list | [] | - | Optional outputs to include (see Include Options below) |

**Boltz2-only parameters:**

| Parameter | Type | Default | Range | Description |
|-----------|------|---------|-------|-------------|
| `affinity` | object | null | - | Affinity calculation config with `binder` chain ID |
| `affinity_mw_correction` | bool | false | - | Molecular weight correction for affinity prediction |
| `sampling_steps_affinity` | int | 200 | - | Sampling steps for affinity head |
| `diffusion_samples_affinity` | int | 5 | - | Diffusion samples for affinity prediction |

**Boltz2-only input fields:**

| Field | Type | Description |
|-------|------|-------------|
| `constraints` | list | Bond, pocket, or contact constraints (see Constraints below) |
| `templates` | list | Structural templates as CIF content with optional chain mapping |

### Include Options (`BoltzIncludeParams`)

Control which optional outputs are computed and returned:

| Value | Description | Notes |
|-------|-------------|-------|
| `pae` | Predicted Aligned Error | Triggers `--write_full_pae`; full matrix not returned (too large), but used to compute ipSAE and ipae metrics in confidence scores |
| `pde` | Predicted Distance Error | Triggers `--write_full_pde` |
| `plddt` | Predicted lDDT | Per-token local distance difference test |
| `embeddings` | Single + pairwise embeddings | Returns `s` (per-token, shape N x 384) and `z` (pairwise, shape N x N x 128) |

### Molecule Input (`BoltzEntity`)

Each molecule in the `items[0].molecules` list is a `BoltzEntity`:

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `id` | str or list[str] | Yes | Chain ID(s). Use a list for multiple copies of the same entity (e.g., homodimers) |
| `type` | str | Yes | One of: `protein`, `dna`, `rna`, `ligand` |
| `sequence` | str | Polymers | Required for protein/dna/rna; forbidden for ligand |
| `smiles` | str | Ligand | SMILES string; mutually exclusive with `ccd` |
| `ccd` | str | Ligand | Chemical Component Dictionary code; mutually exclusive with `smiles` |
| `alignment` | dict | No | Pre-computed MSA as `{database_name: a3m_content}`. Keys: `mgnify`, `small_bfd`, `uniref90`. Protein only |
| `modifications` | list | No | Post-translational modifications: `[{position: int, ccd: str}]`. Protein/DNA/RNA only |
| `cyclic` | bool | No | Whether the polymer chain is cyclic (default: false) |

### Constraints (Boltz2 only)

**Bond constraint**: Covalent bond between two atoms.
```json
{"bond": {"atom1": ["CHAIN_ID", RES_IDX, "ATOM_NAME"], "atom2": ["CHAIN_ID", RES_IDX, "ATOM_NAME"]}}
```

**Pocket constraint**: Defines a binding pocket.
```json
{"pocket": {"binder": "CHAIN_ID", "contacts": [["CHAIN_ID", RES_IDX], ...], "max_distance": 6.0}}
```

**Contact constraint**: Distance constraint between two residues/atoms.
```json
{"contact": {"token1": ["CHAIN_ID", RES_IDX], "token2": ["CHAIN_ID", RES_IDX], "max_distance": 8.0}}
```

### Response

```json
{
  "results": [{
    "cif": "mmCIF string of predicted structure",
    "confidence": {
      "confidence_score": 0.84,
      "ptm": 0.84,
      "iptm": 0.82,
      "ligand_iptm": 0.0,
      "protein_iptm": 0.82,
      "complex_plddt": 0.84,
      "complex_iplddt": 0.82,
      "complex_pde": 0.89,
      "complex_ipde": 5.16,
      "chains_ptm": {"A": 0.85, "B": 0.83},
      "pair_chains_iptm": {"A": {"B": 0.81}, "B": {"A": 0.82}},
      "pair_chains_ipae": {"A": {"B": 5.2}, "B": {"A": 5.3}},
      "pair_chains_ipsae": {"A": {"B": {"ipsae_min": 0.3, "ipsae_max": 0.7, "ipsae_avg": 0.5, "ipsae_d0chn": 0.6, "ipsae_d0dom": 0.65, "ipsae_d0res": 0.7}}}
    },
    "affinity": {
      "affinity_pred_value": -2.1,
      "affinity_probability_binary": 0.92,
      "affinity_pred_value1": -2.0,
      "affinity_probability_binary1": 0.91,
      "affinity_pred_value2": -2.2,
      "affinity_probability_binary2": 0.93
    },
    "embeddings": {"s": [[...]], "z": [[[...]]]},
    "pae": null,
    "pde": null,
    "plddt": null
  }]
}
```

**Confidence scores** (range [0, 1], higher = better unless noted):
- `confidence_score`: Aggregated ranking score = 0.8 * complex_plddt + 0.2 * iptm
- `ptm` / `iptm`: Predicted TM-score, overall and at interfaces
- `ligand_iptm` / `protein_iptm`: Interface TM-score restricted to ligand or protein interfaces
- `complex_plddt` / `complex_iplddt`: Average pLDDT, overall and interface-weighted
- `complex_pde` / `complex_ipde`: Predicted distance error in angstroms (lower = better)
- `chains_ptm`: Per-chain predicted TM-score
- `pair_chains_iptm`: Pairwise interface predicted TM-score between chains
- `pair_chains_ipae`: Symmetrized mean PAE between chain pairs (requires `include: ["pae"]`)
- `pair_chains_ipsae`: ipSAE metrics between chain pairs (requires `include: ["pae"]`; see ipSAE section below)

**Affinity scores** (Boltz2 only, when `affinity` parameter is set):
- `affinity_pred_value`: Predicted binding affinity as log10(IC50) in uM. Lower = stronger binding. Use for comparing active binders in lead optimization.
- `affinity_probability_binary`: Predicted probability that the ligand is a binder [0, 1]. Use for hit discovery / binder vs decoy screening.
- `*1` / `*2` suffixes: Individual ensemble model predictions.

## ipSAE: Interface Quality Metric

When `include: ["pae"]` is set, the PAE matrix is used to compute two derived interface quality metrics returned in `confidence`:

### ipae (interface predicted aligned error)

Symmetrized mean PAE between chain pairs: `ipae(A,B) = 0.5 * (mean(PAE[A,B]) + mean(PAE[B,A]))`. Lower values indicate higher confidence in the predicted interface. Returned in `pair_chains_ipae`.

### ipSAE (interface predicted Score from Aligned Errors)

Based on the Dunbrack 2025 paper "Res ipSAE loquunt" (PMC11844409), ipSAE addresses a key limitation of AlphaFold's ipTM score: ipTM is sensitive to sequence length and disordered regions that do not participate in the interaction, producing misleading scores when full-length proteins are used.

ipSAE improves over ipTM by:
1. **Filtering**: Only residue pairs with PAE below a cutoff (10 angstroms for Boltz) are included
2. **Adaptive normalization**: The TM-score d0 parameter is computed from high-confidence residues rather than total chain length
3. **Direct PAE usage**: Uses PAE values directly to compute alignment scores

Three d0 normalization variants are computed:

| Variant | d0 basis | Description |
|---------|----------|-------------|
| `ipsae_d0chn` | Total chain pair length | Most conservative; comparable across different complexes |
| `ipsae_d0dom` | Residues with good PAE values | Focuses on the interacting domain |
| `ipsae_d0res` | Per-residue count | Most detailed; adapts to local interface quality |

Aggregation statistics (`ipsae_min`, `ipsae_max`, `ipsae_avg`) are computed over residues in each chain. Higher ipSAE values indicate more confident interface predictions. Returned in `pair_chains_ipsae`.

**Reference**: Dunbrack RL Jr. "Res ipSAE loquunt: What's wrong with AlphaFold's ipTM score and how to fix it." *Bioinformatics* (2025). [PMC11844409](https://pmc.ncbi.nlm.nih.gov/articles/PMC11844409/) | [GitHub: DunbrackLab/IPSAE](https://github.com/DunbrackLab/IPSAE)

## Usage Examples

### Single protein structure prediction (Boltz1)

```python
from models.boltz.schema import (
    Boltz1PredictRequest,
    Boltz1PredictParams,
    Boltz1PredictRequestInput,
    BoltzEntity,
    BoltzEntityType,
)

request = Boltz1PredictRequest(
    params=Boltz1PredictParams(
        recycling_steps=3,
        sampling_steps=20,
        diffusion_samples=1,
        seed=42,
    ),
    items=[
        Boltz1PredictRequestInput(
            molecules=[
                BoltzEntity(
                    id="A",
                    type=BoltzEntityType.PROTEIN,
                    sequence="MKLLVVVQVWHHHHH",
                )
            ]
        )
    ],
)
```

### Protein-ligand complex with affinity (Boltz2)

```python
from models.boltz.schema import (
    Boltz2PredictRequest,
    Boltz2PredictParams,
    Boltz2PredictRequestInput,
    BoltzAffinityProperty,
    BoltzEntity,
    BoltzEntityType,
)

request = Boltz2PredictRequest(
    params=Boltz2PredictParams(
        recycling_steps=3,
        sampling_steps=20,
        diffusion_samples=1,
        seed=42,
        affinity=BoltzAffinityProperty(binder="LIG"),
    ),
    items=[
        Boltz2PredictRequestInput(
            molecules=[
                BoltzEntity(
                    id="A",
                    type=BoltzEntityType.PROTEIN,
                    sequence="MKLLVVVQVW",
                ),
                BoltzEntity(
                    id="LIG",
                    type=BoltzEntityType.LIGAND,
                    smiles="CCO",
                ),
            ]
        )
    ],
)
```

### Multimer with ipSAE calculation

```python
from models.boltz.schema import (
    Boltz2PredictRequest,
    Boltz2PredictParams,
    Boltz2PredictRequestInput,
    BoltzEntity,
    BoltzEntityType,
    BoltzIncludeParams,
)

request = Boltz2PredictRequest(
    params=Boltz2PredictParams(
        recycling_steps=3,
        sampling_steps=20,
        diffusion_samples=1,
        seed=42,
        include=[BoltzIncludeParams.PAE],  # Required for ipSAE/ipae
    ),
    items=[
        Boltz2PredictRequestInput(
            molecules=[
                BoltzEntity(
                    id="A",
                    type=BoltzEntityType.PROTEIN,
                    sequence="MKLLVVVQVW",
                ),
                BoltzEntity(
                    id="B",
                    type=BoltzEntityType.PROTEIN,
                    sequence="GHHHHHLLLL",
                ),
            ]
        )
    ],
)
```

### Protein-DNA complex

```python
from models.boltz.schema import (
    Boltz2PredictRequest,
    Boltz2PredictParams,
    Boltz2PredictRequestInput,
    BoltzEntity,
    BoltzEntityType,
)

request = Boltz2PredictRequest(
    params=Boltz2PredictParams(
        recycling_steps=3,
        sampling_steps=20,
        diffusion_samples=1,
    ),
    items=[
        Boltz2PredictRequestInput(
            molecules=[
                BoltzEntity(
                    id="A",
                    type=BoltzEntityType.PROTEIN,
                    sequence="MKLLVVVQVW",
                ),
                BoltzEntity(
                    id="B",
                    type=BoltzEntityType.DNA,
                    sequence="ATCGATCG",
                ),
            ]
        )
    ],
)
```

### Pocket-constrained docking (Boltz2)

```python
from models.boltz.schema import (
    Boltz2PredictRequest,
    Boltz2PredictParams,
    Boltz2PredictRequestInput,
    BoltzAffinityProperty,
    BoltzEntity,
    BoltzEntityType,
    BoltzPredictConstraints,
    BoltzPocketConstraint,
)

request = Boltz2PredictRequest(
    params=Boltz2PredictParams(
        recycling_steps=3,
        sampling_steps=20,
        diffusion_samples=1,
        affinity=BoltzAffinityProperty(binder="LIG"),
    ),
    items=[
        Boltz2PredictRequestInput(
            molecules=[
                BoltzEntity(
                    id="A",
                    type=BoltzEntityType.PROTEIN,
                    sequence="MKLLVVVQVW",
                ),
                BoltzEntity(
                    id="LIG",
                    type=BoltzEntityType.LIGAND,
                    smiles="CCO",
                ),
            ],
            constraints=[
                BoltzPredictConstraints(
                    pocket=BoltzPocketConstraint(
                        binder="LIG",
                        contacts=[["A", 1], ["A", 3], ["A", 5]],
                    )
                )
            ],
        )
    ],
)
```

## Performance & Benchmarks

### Published Results

| Benchmark | Boltz-1 | Boltz-2 | Notes |
|-----------|---------|---------|-------|
| CASP15 structure | Matches AF3 | -- | Wohlwend et al. 2024 |
| FEP+ correlation | -- | R ~0.6 | Passaro et al. 2025 |
| CASP16 affinity | -- | Winner | All submitted methods |

### SOTA Status

Boltz-2 represents current SOTA for combined structure + affinity prediction (2025).

## Implementation Verification

### Verification Status

**Status: VERIFIED** -- BioLM implementation produces structurally valid mmCIF outputs with confidence scores matching expected ranges.

## Capabilities & Limitations

**CAN be used for:**
- Predicting 3D structures of protein, DNA, RNA, and ligand complexes
- Protein-protein, protein-nucleic acid, and protein-ligand interface modeling
- Binding affinity prediction for small molecule-protein interactions (Boltz2)
- Pocket-constrained docking with binding site residue specification (Boltz2)
- Template-guided structure prediction (Boltz2)
- Generating structural embeddings for downstream tasks

**CANNOT be used for:**
- Batch predictions (currently limited to 1 complex per request)
- Automatic MSA generation (MSA must be pre-computed or omitted for single-sequence mode)
- Reliable affinity predictions for RNA/DNA targets (protein targets only)
- Ligands larger than ~56 heavy atoms for affinity (training limit; up to 128 atoms supported but not recommended)
- Sequences longer than 1024 residues (max_sequence_len)

**Other considerations:**
- Single-sequence mode (no MSA) reduces prediction accuracy
- Diffusion sampling is stochastic: confidence scores can vary 10-25% between runs
- Affinity predictions are highly non-deterministic (can vary 80%+ between runs)
- `step_scale` controls diversity vs quality tradeoff (recommended range: 1.0-2.0)

## Implementation Notes

- **GPU**: A100 40GB for both variants
- **Memory snapshots**: Model weights loaded on CPU, then transferred to GPU after snapshot restore
- **Boltz2 mols volume**: Boltz2 requires a ~2GB molecular component library (`mols.tar`), extracted to a Modal volume and symlinked at runtime
- **ID sanitization**: Molecule IDs are sanitized to 4-character alphabetic IDs for Boltz CLI compatibility
- **Output format**: Always mmCIF; per-token pLDDT scores embedded in the CIF B-factor column
- **PAE-derived metrics**: Full PAE/PDE/pLDDT arrays are not returned in the response (too large). Instead, ipSAE and ipae metrics are computed server-side and returned in confidence scores.
- **Determinism**: Seed defaults to 42, but diffusion sampling inherently produces stochastic outputs

## Resource Requirements

| Resource | Value |
|----------|-------|
| GPU | A100 40GB |
| Memory | 24 GB |
| CPU | 4 cores |
| Cold start | ~2 minutes (memory snapshot) |

## License

- **Code**: MIT ([LICENSE](https://github.com/jwohlwend/boltz/blob/main/LICENSE))
- **Weights**: MIT

## References & Citations

```bibtex
@article{wohlwend2024boltz1,
  title={Boltz-1: Democratizing Biomolecular Interaction Modeling},
  author={Wohlwend, Jeremy and Corso, Gabriele and Passaro, Saro and Getz, Noah and Reveiz, Mateo and Leidal, Ken and Swiderski, Wojtek and Atkinson, Liam and Portnoi, Tally and Chinn, Itamar and Silterra, Jacob and Jaakkola, Tommi and Barzilay, Regina},
  journal={bioRxiv},
  year={2024},
  doi={10.1101/2024.11.19.624167}
}

@article{passaro2025boltz2,
  title={Boltz-2: Towards Accurate and Efficient Binding Affinity Prediction},
  author={Passaro, Saro and Corso, Gabriele and Wohlwend, Jeremy and Reveiz, Mateo and Thaler, Stephan and Somnath, Vignesh Ram and Getz, Noah and Portnoi, Tally and Roy, Julien and Stark, Hannes and Kwabi-Addo, David and Beaini, Dominique and Jaakkola, Tommi and Barzilay, Regina},
  journal={bioRxiv},
  year={2025},
  doi={10.1101/2025.06.14.659707}
}

@article{dunbrack2025ipsae,
  title={R\={e}s ipSAE loquunt: What's wrong with AlphaFold's ipTM score and how to fix it},
  author={Dunbrack, Roland L Jr},
  journal={Bioinformatics},
  year={2025},
  note={PMC11844409}
}
```

## Links

- **Boltz-1 Paper**: [bioRxiv 2024.11.19.624167](https://doi.org/10.1101/2024.11.19.624167)
- **Boltz-2 Paper**: [bioRxiv 2025.06.14.659707](https://doi.org/10.1101/2025.06.14.659707)
- **Code**: [GitHub jwohlwend/boltz](https://github.com/jwohlwend/boltz)
- **ipSAE Paper**: [PMC11844409](https://pmc.ncbi.nlm.nih.gov/articles/PMC11844409/)
- **ipSAE Code**: [GitHub DunbrackLab/IPSAE](https://github.com/DunbrackLab/IPSAE)

---

*See also: [MODEL.md](MODEL.md) for technical deep-dive | [BIOLOGY.md](BIOLOGY.md) for biological context*
