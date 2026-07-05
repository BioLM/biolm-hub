# The catalog

Every model lives in `models/<name>/` with the **same layout, the same action verbs, and the same
request/response conventions** — so an agent that learns one model can use them all. This page is a
browseable index; the always-current, richly-rendered catalog is the docs site (`make docs`) and the
local web app (`bh serve`), whose per-model pages are generated from each model's config + knowledge
graph.

## What's in a model directory

| File | What |
|------|------|
| `config.py` | The `ModelFamily`: variants, action→schema map, resource specs, `modal_class_name`. |
| `schema.py` | Request/response Pydantic models (every field carries a `Field(description=...)`). |
| `app.py` | The Modal app + the action methods that run inference. |
| `download.py` | Weight acquisition (only if the model has weights) — an `r2_then_*` wrapper. |
| `test.py` | The `TestSuite` (golden fixtures + integration/deployment tests). |
| `README.md`, `MODEL.md`, `BIOLOGY.md`, `sources.yaml`, `comparison.yaml` | The knowledge graph. |

Start a new model by copying [`dummy/`](dummy/) (the template) and following
[`CONTRIBUTING.md`](../CONTRIBUTING.md). Shared framework code lives in [`commons/`](commons/).

## Action verbs (closed set)

Every endpoint uses one of: `predict`, `fold`, `encode`, `generate`, `score`, `log_prob`. The verb
matches intent (a folding model `fold`s; it doesn't overload `predict`), so the action tells you the
shape of the call across the whole catalog.

## Models (36)

| Model | Name | Actions | Variants |
|-------|------|---------|----------|
| [`ablang2`](ablang2/) | AbLang2 | `encode`, `generate`, `log_prob`, `predict` | 1 |
| [`abodybuilder3`](abodybuilder3/) | ABodyBuilder3 | `fold` | 2 |
| [`antifold`](antifold/) | AntiFold | `encode`, `generate`, `log_prob`, `score` | 1 |
| [`biotite`](biotite/) | Biotite | `generate`, `predict` | 1 |
| [`boltzgen`](boltzgen/) | BoltzGen | `generate` | 1 |
| [`chai1`](chai1/) | Chai-1 | `fold` | 1 |
| [`deepviscosity`](deepviscosity/) | DeepViscosity | `predict` | 1 |
| [`dna_chisel`](dna_chisel/) | DNA-Chisel | `encode` | 1 |
| [`dnabert2`](dnabert2/) | DNABERT-2 | `encode`, `log_prob` | 1 |
| [`dsm`](dsm/) | DSM | `encode`, `generate`, `score` | 3 |
| [`e1`](e1/) | E1 | `encode`, `log_prob`, `predict` | 3 |
| [`esm1b`](esm1b/) | ESM-1b | `encode`, `log_prob`, `predict` | 1 |
| [`esm1v`](esm1v/) | ESM1v | `predict` | 6 |
| [`esm2`](esm2/) | ESM2 | `encode`, `log_prob`, `predict` | 5 |
| [`esm_if1`](esm_if1/) | ESM-IF1 Inverse Fold | `generate` | 1 |
| [`esmc`](esmc/) | ESM C | `encode`, `log_prob`, `predict` | 1 |
| [`esmfold`](esmfold/) | ESMFold | `fold` | 1 |
| [`evo`](evo/) | Evo | `generate`, `log_prob` | 1 |
| [`evo2`](evo2/) | Evo2 | `encode`, `generate`, `log_prob` | 1 |
| [`igbert`](igbert/) | IgBert | `encode`, `generate`, `log_prob` | 2 |
| [`igt5`](igt5/) | IgT5 | `encode` | 2 |
| [`immunebuilder`](immunebuilder/) | ImmuneBuilder | `fold` | 4 |
| [`immunefold`](immunefold/) | ImmuneFold | `fold` | 2 |
| [`mpnn`](mpnn/) | MPNN | `generate` | 6 |
| [`msa_transformer`](msa_transformer/) | MSA Transformer | `encode` | 1 |
| [`omni_dna`](omni_dna/) | Omni-DNA | `encode`, `log_prob` | 1 |
| [`prody`](prody/) | ProDy | `encode`, `predict` | 1 |
| [`progen2`](progen2/) | ProGen2 | `generate` | 4 |
| [`prostt5`](prostt5/) | ProstT5 | `encode`, `generate` | 4 |
| [`rf3`](rf3/) | RosettaFold3 | `fold` | 1 |
| [`sadie`](sadie/) | SADIE | `predict` | 1 |
| [`spurs`](spurs/) | SPURS | `predict` | 1 |
| [`temberture`](temberture/) | TemBERTure | `encode`, `predict` | 2 |
| [`thermompnn`](thermompnn/) | ThermoMPNN | `predict` | 1 |
| [`thermompnn_d`](thermompnn_d/) | ThermoMPNN-D | `predict` | 1 |
| [`zymctrl`](zymctrl/) | ZymCTRL | `encode`, `generate` | 1 |

Plus [`dummy/`](dummy/) — the template for adding a model — and [`commons/`](commons/) — the shared
framework. Deploy any model with `bh deploy <name>` (see the root [`README.md`](../README.md)).
