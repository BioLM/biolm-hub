# ProDy

> **One-line summary**: Physics-based protein structure analysis tool computing non-covalent interactions (hydrogen bonds, salt bridges, hydrophobic contacts, pi-stacking, cation-pi) and RMSD between structures.

## Overview

ProDy integration for computing protein-protein interactions and structural comparisons using ProDy's InSty module.

This model provides two actions:

1. **Encode (InSty)**: Computes protein-protein interactions including hydrogen bonds, salt bridges, hydrophobic interactions, pi-stacking, and cation-pi interactions
2. **Predict (RMSD)**: Calculates root mean square deviation (RMSD) between two protein structures

## Architecture

| Property | Value |
|----------|-------|
| Architecture | Algorithmic (physics-based cutoffs, no learned weights) |
| Task | Interaction detection, RMSD calculation |
| Input | PDB or CIF structure |
| Output | Interaction lists + counts (encode), RMSD value (predict) |
| GPU | None (CPU-only) |

## Model Variants

ProDy is a single-variant model with no variant axes. All requests are served by a single deployment (`prody`).

## Capabilities & Limitations

**CAN be used for:**
- Computing non-covalent interactions within a single protein chain (intra-chain)
- Computing interactions between multiple protein chains (inter-chain)
- Detecting hydrogen bonds, salt bridges, hydrophobic contacts, pi-stacking, cation-pi, repulsive ionic interactions
- Calculating RMSD between two protein structures with structural or sequence alignment
- Adding missing hydrogen atoms via PDBFixer or OpenBabel before analysis

**CANNOT be used for:**
- Non-protein chains (DNA, RNA, ligands are not supported)
- Structures with fewer than 5 residues (insufficient for meaningful interaction analysis)
- Thread-safe parallel processing (ProDy C extensions are not thread-safe; batch processing is sequential)
- Fully deterministic hydrogen bond counts (may vary by +/-1 between runs due to borderline detection at cutoff thresholds)

**Other considerations:**
- Core interactions (salt bridges, hydrophobic) are fully deterministic
- CIF files are automatically converted to PDB format before processing

## Actions / Endpoints

### `encode` (InSty Interactions)

Computes interactions using ProDy's `Interactions` class with `calcProteinInteractions()`:

- **Hydrogen Bonds**: Distance and angle cutoffs (typically 2.7-3.4 Angstrom)
- **Salt Bridges**: Ionic interactions between charged residues (typically 3.3-3.5 Angstrom)
- **Hydrophobic Interactions**: Non-polar residue contacts (typically 3.4-4.5 Angstrom)
- **Pi Stacking**: Aromatic ring interactions
- **Cation-Pi**: Interactions between cations and aromatic rings
- **Repulsive Ionic**: Repulsive interactions between like charges

Supports single-chain analysis (intra-chain) and multi-chain analysis (intra + inter-chain interactions). Hydrogen atoms are added before calculation using PDBFixer (default) or OpenBabel.

**Request Parameters:**

| Parameter | Type | Default | Range | Description |
|-----------|------|---------|-------|-------------|
| `items[].pdb` | str | None | -- | PDB format structure |
| `items[].cif` | str | None | -- | CIF format structure |
| `items[].chain_ids` | list[str] | None | -- | Chains to analyze (None = all) |
| `items[].chain_pairs` | list[tuple] | None | -- | Chain pairs for inter-chain analysis |
| `params.add_hydrogens` | bool | False | -- | Add missing hydrogens before calculation |
| `params.hydrogen_method` | str | "pdbfixer" | "pdbfixer" or "openbabel" | Method for hydrogen addition |
| `params.compute_all_interactions` | bool | True | -- | Compute all interaction types |
| `params.return_interaction_matrix` | bool | False | -- | Return interaction matrix |
| `params.return_energy_matrix` | bool | False | -- | Return energy matrix |
| `params.return_frequent_interactors` | bool | False | -- | Return frequent interactors |
| `params.frequent_interactors_min_contacts` | int | 1 | >=1 | Minimum contacts for frequent interactors |

### `predict` (RMSD)

Calculates RMSD using ProDy's `calcRMSD()` with chain matching:

- **Structural alignment** (default): Matches chains by structure
- **Sequence alignment**: Uses `matchChains()` with `pwalign=True` for homologous sequences
- Automatically selects CA atoms for comparison

**Request Parameters:**

| Parameter | Type | Default | Range | Description |
|-----------|------|---------|-------|-------------|
| `items[].pdb_a` / `cif_a` | str | *(required)* | -- | First structure |
| `items[].chain_a` | str or list | *(required)* | -- | Chain(s) from first structure |
| `items[].pdb_b` / `cif_b` | str | *(required)* | -- | Second structure |
| `items[].chain_b` | str or list | *(required)* | -- | Chain(s) from second structure |
| `params.alignment_method` | str | "structural" | "structural" or "sequence" | Alignment method |

## Usage Examples

### Encode (Interaction Analysis)

```python
from models.prody.schema import (
    ProDyEncodeRequest,
    ProDyEncodeRequestItem,
    ProDyEncodeRequestParams,
    HydrogenMethod,
)

request = ProDyEncodeRequest(
    params=ProDyEncodeRequestParams(
        add_hydrogens=True,
        hydrogen_method=HydrogenMethod.OPENBABEL,
    ),
    items=[
        ProDyEncodeRequestItem(
            cif=cif_string,
            chain_ids=["A", "B"],
            chain_pairs=[("A", "B")],
        )
    ],
)
```

### Predict (RMSD)

```python
from models.prody.schema import (
    ProDyPredictRequest,
    ProDyPredictRequestItem,
    ProDyPredictRequestParams,
    AlignmentMethod,
)

request = ProDyPredictRequest(
    params=ProDyPredictRequestParams(
        alignment_method=AlignmentMethod.SEQUENCE,
    ),
    items=[
        ProDyPredictRequestItem(
            cif_a=structure_a_cif,
            chain_a="A",
            cif_b=structure_b_cif,
            chain_b="A",
        )
    ],
)
```

## Performance & Benchmarks

- **Encode**: Interaction analysis time depends on structure size and number of chains; sequential processing due to ProDy C extension thread-safety constraints
- **Predict**: RMSD calculation is fast for typical protein structures
- **Hydrogen bond detection**: Borderline cases at cutoff thresholds may cause +/-1 variation between runs
- **Core interactions**: Salt bridges and hydrophobic contacts are fully deterministic

## Implementation Verification

Deploying the app and running tests:

```bash
# Deploy
python models/prody/app.py --force-deploy

# Generate fixtures
python models/prody/fixture.py

# Run tests
make test MODEL=prody
```

## Resource Requirements

| Variant | GPU | Memory | CPU |
|---------|-----|--------|-----|
| `prody` | None (CPU-only) | 16 GB | 4 cores |

## Implementation Notes

- **CPU-only**: No GPU required (4 cores, 16GB memory)
- **Determinism**: Seeds set for reproducibility; hydrogen bonds may vary +/-1
- **Memory snapshots disabled**: Ensures fresh code execution on each container start
- **Hydrogen methods**: PDBFixer (default, more accurate) or OpenBabel (faster)
- **CIF conversion**: CIF files are automatically converted to PDB format before processing
- **Batch size**: Up to 8 items per request

## License

- **ProDy**: MIT ([LICENSE](https://github.com/prody/ProDy/blob/main/LICENSE.rst))

## References & Citations

### Papers

1. Bakan A, Meireles LM, Bahar I. "ProDy: Protein Dynamics Inferred from Theory and Experiments." *Bioinformatics* (2011). [DOI: 10.1093/bioinformatics/btr168](https://doi.org/10.1093/bioinformatics/btr168)

### Links

- [ProDy Documentation](http://prody.csb.pitt.edu/)
- [OpenBabel](https://openbabel.org/)
- [PDBFixer](https://github.com/openmm/pdbfixer)

---

*See also: [MODEL.md](MODEL.md) for technical deep-dive | [BIOLOGY.md](BIOLOGY.md) for biological context*
