# {Model Display Name}

> **Template/example model** — copy this directory as the starting point for a new model. The placeholder content below (`{Model Display Name}`, TODO blocks) is intentional.

<!-- Template instructions (delete this block when populating):
     This is the standardized README template for all BioLM models.
     Every section below should be populated for production models.
     If information is unavailable, keep the section header and add a TODO
     note explaining HOW to obtain the missing content.

     TODO format (use consistently across all docs):
       <!-- TODO: [Action to take]  --  [Where to find the info] -->
     Example:
       <!-- TODO: Extract architecture specs from paper Table 1  --  see sources.yaml primary_papers[0] -->

     References:
     - sources.yaml in this directory for paper/repo links
     - MODEL.md for deep technical details
     - BIOLOGY.md for biological context and applications

     Sections marked [OPTIONAL] should be INCLUDED if relevant to this model
     and REMOVED (not left empty) if not applicable.
-->

> **One-line summary**: Brief description of what this model does, its key capability, and primary molecule type.

## Overview

<!-- 1-3 paragraphs covering:
     - What the model is and who developed it
     - The key innovation or approach
     - Where it sits in the landscape (e.g., "first open-source model to...")
     - Primary use case
-->

## Architecture

<!-- Model architecture summary. Include:
     - Model type (transformer, diffusion, GNN, etc.)
     - Key parameters (number of layers, hidden dimensions, total params)
     - Training data summary (dataset name, size, composition)
     - Maximum input length / sequence constraints
     - For complex models, include an ASCII diagram or reference MODEL.md
       for detailed flowcharts

     Example format:
     | Property | Value |
     |----------|-------|
     | Architecture | Transformer encoder |
     | Parameters | 650M |
     | Layers | 33 |
     | Hidden dimensions | 1280 |
     | Training data | UniRef50 (65M sequences) |
     | Max sequence length | 1022 residues |
-->

## Model Variants

<!-- If the model has multiple sizes or configurations, list them here.
     If single-variant, state "Single variant  --  no size options."

     Example format:
     | Variant | Parameters | GPU | Use Case |
     |---------|-----------|-----|----------|
     | `esm2-8m` | 8M | None (CPU) | Fast prototyping |
     | `esm2-650m` | 650M | T4 | Production embeddings |
-->

## Capabilities & Limitations

**CAN be used for:**
<!-- Bullet list of supported use cases. Be specific about molecule types
     and tasks. Examples:
     - Generating per-residue embeddings for protein sequences
     - Zero-shot variant effect prediction via log-likelihood scoring
     - Protein-ligand binding affinity prediction
-->

**CANNOT be used for:**
<!-- Bullet list of explicitly unsupported use cases. This prevents misuse
     and sets expectations. Examples:
     - Sequences longer than 1022 residues
     - Non-canonical amino acids beyond X
     - Structure prediction (use ESMFold or Chai-1 instead)
-->

**Other considerations:**
<!-- Additional notes on behavior, caveats, or edge cases. Examples:
     - Stochastic outputs: confidence scores can vary 10-25% between runs
     - Batch size affects memory usage; reduce for long sequences
-->

## Actions / Endpoints

<!-- List each API action the model exposes. For each action, document:
     - Action name (e.g., `encode`, `predict`, `generate`)
     - Brief description of what it does
     - Request parameters with types, defaults, ranges
     - Response format

     Use the format below for each action.
-->

### `action_name`

Brief description of what this action does.

**Request Parameters:**

<!-- Column headers must be exactly: Parameter | Type | Default | Range | Description
     If range includes enumerated options, list them in Range column. -->
| Parameter | Type | Default | Range | Description |
|-----------|------|---------|-------|-------------|
| `param1` | str | - | - | Description |
| `param2` | int | 10 | 1-100 | Description |

**Response:**

```json
{
  "results": [
    {
      "field1": "description",
      "field2": 0.0
    }
  ]
}
```

## Usage Examples

<!-- Python code examples showing how to construct requests for each action.
     Use actual schema imports from this model's schema.py.
     Include at least one example per action.
-->

```python
# Example request
from models.{model_name}.schema import (
    ModelRequest,
    ModelParams,
    ModelRequestInput,
)

request = ModelRequest(
    params=ModelParams(...),
    items=[ModelRequestInput(...)],
)
```

## Performance & Benchmarks

### Published Results

<!-- Results from the model's paper. Include:
     - Dataset name and size
     - Metrics with values (use ↑ for higher-is-better, ↓ for lower-is-better)
     - Comparison to key alternatives
     - Error bars / confidence intervals if available

     Example format:
     | Model | Metric1 ↑ | Metric2 ↓ | Dataset |
     |-------|-----------|-----------|---------|
     | **This Model** | **0.94** | **3.42** | TestSet (n=3100) |
     | Alternative 1 | 0.81 | 3.62 | TestSet (n=3100) |
-->

### SOTA Status

<!-- Is this model state-of-the-art? On which benchmarks?
     When was this last verified? Include date.
     e.g., "SOTA for protein Tm prediction as of Feb 2025 (bioRxiv 2025.02.18.638450)"
-->

## Resource Requirements

| Resource | Value |
|----------|-------|
| GPU | None / T4 / L4 / A10G / L40S / A100 40GB / A100 80GB / H100 |
| Memory | e.g., 4GB |
| CPU | e.g., 2 cores |
| Cold start | e.g., ~30 seconds |
| Inference P50 | e.g., ~200ms |
| Dependencies | e.g., Requires `esm2-650m` endpoint deployed |

## Implementation Notes

<!-- Technical details specific to the Modal deployment:
     - Memory snapshots: Does this model use @modal.enter(snap=True)?
     - Caching: commons two-tier cache (in-container modal.Dict + R2), opt-in via BIOLM_CACHE_ENABLED (off by default)
     - Determinism: Seeds set? Reproducible outputs?
     - External dependencies: Calls to other Modal endpoints?
     - Container architecture: Special image layers or volumes?
     - Known quirks or workarounds
-->

## [OPTIONAL] Training

<!-- Include this section if:
     - The model has trainable components within BioLM (e.g., a regression or
       classification head trained on top of frozen embeddings)
     - Training/fine-tuning procedures are documented and reproducible
     - Training results (cross-validation, loss curves) are available

     Cover:
     - Training command (e.g., `modal run models/<example-model>/_train.py`)
     - Dataset source and preprocessing
     - Training results (e.g., 5-fold CV metrics)
     - Where trained artifacts are stored (e.g., R2 biolm-hub/model-weights/models path)

     If training is purely upstream (done by original authors, not reproducible
     within BioLM), document this in MODEL.md Training Data section instead.
-->

## [OPTIONAL] Confidence Metrics

<!-- Include this section if the model outputs confidence/quality scores that
     need interpretation (e.g., pLDDT, pTM, PAE, ipSAE for structure models;
     prediction intervals for property models).

     For each metric:
     - Name and abbreviation
     - What it measures
     - Value range and interpretation (what's "good"?)
     - When to use this metric vs others

     Example (structure prediction):
     | Metric | Range | Interpretation |
     |--------|-------|----------------|
     | pLDDT | 0-100 | >90: high confidence, 70-90: moderate, <70: low |
     | pTM | 0-1 | >0.8: confident fold, <0.5: likely incorrect |
-->

## [OPTIONAL] Technical Glossary

<!-- Include this section if the model uses domain-specific terminology that
     users may not be familiar with (e.g., AlphaFold2's Evoformer, recycling,
     MSA concepts; or CamSol's intrinsic vs corrected solubility).

     Format:
     **Term**: Definition. Context for why it matters.
-->

## [OPTIONAL] Calibration

<!-- Include this section if the model has tunable parameters, normalization
     constants, or calibration procedures that affect output interpretation.

     Cover:
     - What can be calibrated and why
     - Default calibration values
     - How to recalibrate (command or procedure)
     - Impact of calibration on outputs
-->

## [OPTIONAL] Implementation Disclaimer

<!-- Include this section if:
     - This is a reverse-engineered or non-official implementation
     - The implementation differs from the original in significant ways
     - There are known accuracy gaps vs the original

     Be transparent about:
     - What was reverse-engineered vs officially provided
     - Known differences from the original implementation
     - Impact on accuracy or functionality
-->

## License

<!-- License information. Must match sources.yaml license field.
     Include:
     - License type (SPDX identifier)
     - What is covered (code, weights, data separately if different)
     - Link to license file
     - Any restrictions (non-commercial, academic only, etc.)

     Example:
     - **Code**: MIT ([LICENSE](https://github.com/org/repo/blob/main/LICENSE))
     - **Weights**: CC-BY-NC-4.0 (non-commercial use only)

     For reverse-engineered or proprietary implementations:
     - **Code**: Proprietary (reverse-engineered from published literature)
     - **Notes**: Not affiliated with or endorsed by original authors
-->

## References & Citations

<!-- List all references. Include BibTeX for the primary paper(s).
     Link to GitHub, HuggingFace, and any other relevant resources.
     Keep in sync with sources.yaml primary_papers and source_repos.
-->

### Papers

1. Author A et al. "Paper title." *Venue* (Year). [DOI](https://doi.org/...)

### BibTeX

```bibtex
@article{key,
  title={Paper title},
  author={Author},
  journal={Venue},
  year={Year},
  doi={DOI}
}
```

### Links

- **Paper**: [arXiv/bioRxiv link](URL)
- **Code**: [GitHub org/repo](URL)
- **Model weights**: [HuggingFace org/model](URL)

---

*See also: [MODEL.md](MODEL.md) for technical deep-dive | [BIOLOGY.md](BIOLOGY.md) for biological context*
