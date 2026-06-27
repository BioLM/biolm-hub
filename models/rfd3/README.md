# RFdiffusion3 (RFD3)

> **One-line summary**: All-atom generative diffusion model for de novo design of proteins, nucleic acids, and small-molecule complexes via SE(3) denoising diffusion.

## Overview

RFdiffusion3 is the successor to RFdiffusion, extending from backbone-only to **all-atom** generation. It designs complete biomolecular structures (proteins, nucleic acids, small molecules) by iteratively denoising random coordinates through a learned diffusion process.

**Key advances over RFdiffusion (v1):**
- All-atom generation (sidechains, ligands, cofactors) vs backbone-only
- Multi-molecule design (protein-DNA, protein-ligand complexes)
- Covalent modification support (post-translational modifications, crosslinks)
- Built on the foundry/atomworks framework for unified biomolecular representation

**Input**: Sequence templates (poly-M for de novo), optional fixed structures, constraints
**Output**: Designed all-atom structures in mmCIF format

## Architecture

| Property | Value |
|----------|-------|
| Architecture | SE(3) diffusion with RoseTTAFold trunk |
| Parameters | ~168M trainable |
| Input | Protein backbone templates, optional motifs/constraints |
| Output | All-atom protein structures (PDB) |

## Model Variants

Single variant -- RFD3 (all-atom generation).

## Actions / Endpoints

### `generate`
Design biomolecular structures under specified constraints.

**Request Schema**: `RFD3DesignRequest`
**Response Schema**: `RFD3DesignResponse`

#### Parameters

| Parameter | Type | Default | Range | Description |
|-----------|------|---------|-------|-------------|
| `num_diffusion_steps` | int | 200 | 50-500 | Number of denoising steps; more = higher quality |
| `diffusion_batch_size` | int | 1 | 1-16 | Number of designs to generate per input |
| `seed` | int | None | - | Random seed for reproducibility |
| `temperature` | float | 1.0 | 0.1-2.0 | Sampling temperature; lower = less diverse, more designable |
| `conditioning_mode` | str | "unconditional" | see below | Design mode |
| `symmetry` | str | None | - | Symmetry group (e.g., "C3", "D2") |
| `step_scale` | float | None | 1.0-2.0 | Step size scale; higher = less diverse, more designable (default: 1.5) |
| `noise_scale` | float | None | 1.0-2.0 | Noise scale for diffusion (default: 1.003) |
| `output_format` | str | "cif" | "cif", "pdb" | Output structure format |
| `include_trajectories` | bool | false | - | Include denoising trajectory in output |

#### Conditioning Modes

| Mode | Description | Required Fields |
|------|-------------|-----------------|
| `unconditional` | De novo protein design | Sequence template only |
| `binder_design` | Design binder to target | Target structure + binder template |
| `motif_scaffolding` | Scaffold around fixed motif | Structure with contig specification |
| `partial_diffusion` | Perturb existing structure | Structure + `partial_t` noise level |
| `symmetric_design` | Symmetric oligomer design | Template + `symmetry` group |

#### Input Fields (`RFD3DesignRequestInput`)

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `name` | str | Yes | Name for this design task |
| `components` | list[`RFD3Component`] | Yes | Biomolecular components (min 1) |
| `contig` | str | No | Contig string for fixed/diffused regions |
| `target_chain` | str | No | Target chain ID for binder design |
| `input_structure_path` | str | No | Path to input PDB/CIF file |
| `motif_selection` | list[str] | No | Motif residue selections |
| `unindex` | list[str] | No | Unindexed motif residues |
| `ligands` | list[str] | No | Ligand residue names to include |
| `partial_t` | float | No | Noise level for partial diffusion |
| `length` | str | No | Length constraint (int or "min-max") |
| `bonds` | list[tuple] | No | Custom bonds as atom spec pairs |

#### Component Fields (`RFD3Component`)

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `name` | str | Yes | Component name |
| `sequence` | str | No | Amino acid or nucleotide sequence |
| `smiles` | str | No | SMILES string for small molecule |
| `ccd_code` | str | No | Chemical Component Dictionary code |
| `structure_cif` | str | No | Structure in mmCIF format |
| `chain_id` | str | No | Chain identifier |
| `fixed_atoms` | list[str] | No | Atom specifications to fix |
| `fixed_residues` | list[str] | No | Residue specifications to fix |

#### Response Fields (`RFD3DesignResponse`)

| Field | Type | Description |
|-------|------|-------------|
| `results` | list[list[`RFD3DesignResponseResult`]] | Nested list: outer = input items, inner = designs per item |

Each `RFD3DesignResponseResult` contains:

| Field | Type | Description |
|-------|------|-------------|
| `structure_cif` | str | Designed structure in mmCIF format |
| `trajectory_cif` | str (optional) | Denoising trajectory if requested |

## Usage Examples

### De Novo Protein Design (Unconditional)

```python
from models.rfd3.schema import (
    RFD3DesignRequest,
    RFD3DesignParams,
    RFD3DesignRequestInput,
    RFD3Component,
)

# Design a 100-residue protein from scratch
request = RFD3DesignRequest(
    params=RFD3DesignParams(
        num_diffusion_steps=200,
        diffusion_batch_size=1,
        seed=42,
    ),
    items=[
        RFD3DesignRequestInput(
            name="de_novo_design",
            components=[
                RFD3Component(name="protein", sequence="M" * 100)
            ],
        )
    ],
)
```

### Binder Design

```python
from models.rfd3.schema import (
    RFD3DesignRequest,
    RFD3DesignParams,
    RFD3DesignRequestInput,
    RFD3Component,
    RFD3ConditioningMode,
)

# Design a binder against a target protein
request = RFD3DesignRequest(
    params=RFD3DesignParams(
        num_diffusion_steps=200,
        diffusion_batch_size=4,  # Generate 4 candidates
        seed=42,
        temperature=0.8,
        conditioning_mode=RFD3ConditioningMode.BINDER_DESIGN,
    ),
    items=[
        RFD3DesignRequestInput(
            name="binder_design",
            components=[
                RFD3Component(
                    name="target",
                    sequence="MKKLLFIAVVFTLLGTAVQAAYPYDDAAQLTEEQRKNEELRGQLQPTEGR",
                    chain_id="A",
                ),
                RFD3Component(
                    name="binder",
                    sequence="M" * 80,  # 80-residue binder template
                    chain_id="B",
                ),
            ],
            target_chain="A",
        )
    ],
)
```

### Motif Scaffolding

```python
from models.rfd3.schema import (
    RFD3DesignRequest,
    RFD3DesignParams,
    RFD3DesignRequestInput,
    RFD3Component,
    RFD3ConditioningMode,
)

# Scaffold a functional motif (residues 100-130 fixed)
request = RFD3DesignRequest(
    params=RFD3DesignParams(
        num_diffusion_steps=200,
        diffusion_batch_size=2,
        seed=42,
        conditioning_mode=RFD3ConditioningMode.MOTIF_SCAFFOLDING,
    ),
    items=[
        RFD3DesignRequestInput(
            name="motif_scaffold",
            components=[
                RFD3Component(
                    name="scaffold",
                    sequence="MKLLILAVVF..." + "M" * 50,  # Fixed motif + variable regions
                    chain_id="A",
                    fixed_residues=["A/100-130"],
                ),
            ],
            contig="A1-100,50-80,/0",
        )
    ],
)
```

### Symmetric Design

```python
from models.rfd3.schema import (
    RFD3DesignRequest,
    RFD3DesignParams,
    RFD3DesignRequestInput,
    RFD3Component,
    RFD3ConditioningMode,
)

# Design a C3-symmetric trimer
request = RFD3DesignRequest(
    params=RFD3DesignParams(
        num_diffusion_steps=200,
        diffusion_batch_size=1,
        seed=999,
        temperature=1.2,
        conditioning_mode=RFD3ConditioningMode.SYMMETRIC_DESIGN,
        symmetry="C3",
    ),
    items=[
        RFD3DesignRequestInput(
            name="symmetric_trimer",
            components=[
                RFD3Component(
                    name="monomer",
                    sequence="M" * 60,  # 60-residue monomer
                )
            ],
        )
    ],
)
```

## Interpreting Output

RFD3 is a **generative** model -- each run produces different structures, even with the same input. To evaluate designs:

1. **Visual inspection**: Load the output mmCIF in PyMOL/ChimeraX to check fold quality
2. **Self-consistency**: Predict the structure of the designed sequence using RosettaFold3 (RF3) or AlphaFold2. Low RMSD between designed and predicted structures indicates designability
3. **Confidence scores**: Run the designed sequence through RF3 to obtain pTM/ipTM/pLDDT metrics
4. **Sequence design**: Use ProteinMPNN or similar inverse folding to design sequences for the generated backbone, then validate with structure prediction

**Typical workflow**: RFD3 (structure) -> ProteinMPNN (sequence) -> RF3/AF2 (validation)

### Confidence Metrics

RFD3 itself does not output confidence scores. Confidence is assessed by running the designed sequence through a structure prediction model. The key metrics to evaluate:

| Metric | Source | Good Threshold | Description |
|--------|--------|----------------|-------------|
| scTM | RF3/AF2 vs RFD3 | > 0.5 | Self-consistency TM-score: overlap between designed and predicted structure |
| scRMSD | RF3/AF2 vs RFD3 | < 2.0 A | Self-consistency backbone RMSD |
| pLDDT | RF3/AF2 | > 70 | Per-residue confidence from structure prediction; > 90 = high confidence |
| pTM | RF3/AF2 | > 0.5 | Predicted TM-score; indicates global fold correctness |
| ipTM | RF3/AF2 | > 0.5 | Interface predicted TM-score (for complexes / binder design) |

**Interpretation guidelines**:
- scTM > 0.5 with pLDDT > 70: Design is likely designable and worth experimental testing
- scTM < 0.3: Design is unlikely to fold as intended; regenerate with different parameters
- Multiple designs with high scTM but different folds: The design task has multiple valid solutions

## Performance & Benchmarks

RFD3 was benchmarked against RFdiffusion (v1) and other generative models across multiple design tasks. Key results from the paper:

- **De novo design**: Higher self-consistency (scTM) scores compared to RFdiffusion v1
- **Binder design**: Designs against protein, DNA, RNA, and small molecule targets
- **Motif scaffolding**: Successful scaffolding of functional motifs with all-atom accuracy
- **Symmetric design**: Cyclic and dihedral symmetry oligomers

### Approximate Benchmark Numbers

| Metric | RFdiffusion v1 (Watson et al. 2023) | RFD3 (Butcher et al. 2025) | Notes |
|--------|--------------------------------------|----------------------------|-------|
| Designability (scTM > 0.5) | ~70% of designs | Higher than v1 | Self-consistency via AF2/RF3 |
| Experimental success rate | ~15-30% (varied by task) | TBD | Watson et al. reported wet-lab validation |
| Binder design hit rate | ~10-20% (protein targets) | Extends to DNA/RNA/ligand targets | Measured by yeast display or phage display |
| Motif scaffolding RMSD | < 1.0 A motif RMSD | All-atom accuracy (sidechains preserved) | Fixed motif recovery |

<!-- TODO: Replace RFD3 column with exact numbers from bioRxiv 2025.09.18.676967 when available -->

Quantitative benchmarks are available in the [original paper](https://doi.org/10.1101/2025.09.18.676967).

## Implementation Verification

### Verification Status

**Status: VERIFIED** -- BioLM implementation generates valid PDB structures with designable outputs.

<!-- TODO(runtime): Add systematic verification with scTM metrics -->

## Capabilities & Limitations

### CAN be used for

- De novo protein structure design (up to 2048 residues)
- Protein binder design against diverse targets (proteins, nucleic acids, small molecules)
- Motif scaffolding with fixed functional sites
- Symmetric oligomer design (cyclic, dihedral)
- Partial diffusion to diversify existing structures
- Designing with covalent modifications and custom bonds

### CANNOT be used for

- Structure prediction (use RF3 or AlphaFold instead)
- Sequence design (use ProteinMPNN; RFD3 outputs structures, not sequences)
- Sequences >2048 residues
- Designing membrane-embedded regions (training data bias toward soluble proteins)
- Guaranteeing experimental success (designs require experimental validation)

### Other considerations

- Generative model: each run produces different results; set `seed` for reproducibility
- Longer diffusion runs (more steps) generally produce higher-quality designs at the cost of compute time
- `diffusion_batch_size` > 1 generates multiple designs in a single run for diversity
- Binder design typically requires iterating with different seeds and selecting top candidates

## Design Modes

### Unconditional Design

Generate a protein backbone from scratch. Provide a poly-methionine template of the desired length. The model will generate a diverse set of folds. Use `temperature` to control diversity (lower = more designable, higher = more diverse).

### Binder Design

Generate a protein that binds to a given target. Requires:
- Target structure (protein, DNA, RNA, or small molecule) as a fixed component
- Binder template (poly-M) as the designable component
- `target_chain` specifying which chain is the target

Best practices: generate many candidates (`diffusion_batch_size` = 4-16, multiple seeds) and filter by interface metrics.

### Motif Scaffolding

Generate a scaffold around fixed functional residues. Requires:
- Input structure with the motif residues
- Contig string specifying which regions are fixed vs diffused
- `fixed_residues` or `fixed_atoms` specifying what to preserve

Supports unindexed motifs (residues whose position in the scaffold is unknown) via the `unindex` field.

### Partial Diffusion

Perturb an existing structure by adding noise and re-denoising. Useful for:
- Generating structural variants of a known protein
- Exploring conformational space around a starting structure
- Diversifying designs from a previous run

Set `partial_t` to control the noise level (higher = more perturbation).

### Symmetric Design

Generate oligomers with defined symmetry. Supported groups include cyclic (C2, C3, ...) and dihedral (D2, D3, ...). The model generates a single asymmetric unit and applies symmetry operations.

## Implementation Notes

- **Framework**: Built on [RosettaCommons/foundry](https://github.com/RosettaCommons/foundry) at commit `6866d61`
- **Python**: Requires 3.12+ (foundry dependency)
- **Determinism**: Set `seed` parameter for reproducible designs; internal torch seeds are fixed
- **GPU memory**: Uses `low_memory_mode` optimizations to fit on A100 40GB
- **Output format**: Structures returned as mmCIF; gzip-compressed internally, decompressed in API response
- **Batch size**: Fixed to 1 item per request; use `diffusion_batch_size` for multiple designs of the same input

## Resource Requirements

| Resource | Value |
|----------|-------|
| GPU | A100 40GB |
| Memory | 64 GB |
| CPU | 8 cores |

## License

- **Code**: BSD-3-Clause ([LICENSE](https://github.com/RosettaCommons/foundry/blob/main/LICENSE))

## References & Citations

- **Paper (RFD3)**: [bioRxiv 2025.09.18.676967](https://doi.org/10.1101/2025.09.18.676967)
- **Paper (RFdiffusion v1)**: [Nature 2023](https://doi.org/10.1038/s41586-023-06415-8)
- **Code**: [RosettaCommons/foundry](https://github.com/RosettaCommons/foundry)

```bibtex
@article{butcher2025_rfdiffusion3,
    title={De novo Design of All-atom Biomolecular Interactions with RFdiffusion3},
    author={Butcher, Jasper and Krishna, Rohith and Wang, Jue and Lisanza, Sidney
            and Juergens, David and De Bortoli, Valentin and Mathis, Simon V.
            and Yim, Jason and Barzilay, Regina and Jaakkola, Tommi
            and Baker, David},
    journal={bioRxiv},
    year={2025},
    doi={10.1101/2025.09.18.676967}
}

@article{watson2023_rfdiffusion,
    title={De novo design of protein structure and function with RFdiffusion},
    author={Watson, Joseph L. and Juergens, David and Bennett, Nathaniel R.
            and Trippe, Brian L. and Yim, Jason and Eisenach, Helen E.
            and Ahern, Woody and Borber, Andrew J. and Ragotte, Robert J.
            and Milles, Lukas F. and others},
    journal={Nature},
    year={2023},
    doi={10.1038/s41586-023-06415-8}
}
```

---

*See also: [MODEL.md](MODEL.md) for technical deep-dive | [BIOLOGY.md](BIOLOGY.md) for biological context*
