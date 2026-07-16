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

<!-- BEGIN GENERATED CATALOG (tooling/gen_model_catalog.py — do not edit by hand) -->
## Models

**69 deployable models across 37 model families.** Each row is one deployable variant — everything you need to call it. When `bh serve` is running, invoke an action with `POST /api/v1/{endpoint-slug}/{action}`; to call the Modal class directly, use `modal.Cls.from_name("{modal-app}", ...)`. The **Actions** column lists the closed-set verbs the variant's family supports.

| Model | Base slug | Endpoint slug | Modal app | Actions | GPU |
|-------|-----------|---------------|-----------|---------|-----|
| [AbLang2](ablang2/) | `ablang2` | `ablang2` | `ablang2` | `encode`, `generate`, `log_prob`, `predict` | CPU |
| [ABodyBuilder3 language](abodybuilder3/) | `abodybuilder3` | `abodybuilder3-language` | `abodybuilder3-language` | `fold` | L40S |
| [ABodyBuilder3 plddt](abodybuilder3/) | `abodybuilder3` | `abodybuilder3-plddt` | `abodybuilder3-plddt` | `fold` | CPU |
| [AntiFold](antifold/) | `antifold` | `antifold` | `antifold` | `encode`, `generate`, `log_prob`, `score` | CPU |
| [Biotite](biotite/) | `biotite` | `biotite` | `biotite` | `generate`, `predict` | CPU |
| [BoltzGen](boltzgen/) | `boltzgen` | `boltzgen` | `boltzgen` | `generate` | A100 |
| [Chai-1](chai1/) | `chai1` | `chai1` | `chai1` | `fold` | A100-80GB |
| [ChemBERTa](chemberta/) | `chemberta` | `chemberta` | `chemberta` | `encode`, `log_prob` | CPU |
| [DeepViscosity](deepviscosity/) | `deepviscosity` | `deepviscosity` | `deepviscosity` | `predict` | CPU |
| [DNA-Chisel](dna_chisel/) | `dna-chisel` | `dna-chisel` | `dna-chisel` | `encode` | CPU |
| [DNABERT-2](dnabert2/) | `dnabert2` | `dnabert2` | `dnabert2` | `encode`, `log_prob` | T4 |
| [DSM 150m base](dsm/) | `dsm` | `dsm-150m-base` | `dsm-150m-base` | `encode`, `generate`, `score` | A10G |
| [DSM 650m base](dsm/) | `dsm` | `dsm-650m-base` | `dsm-650m-base` | `encode`, `generate`, `score` | A10G |
| [DSM 650m ppi](dsm/) | `dsm` | `dsm-650m-ppi` | `dsm-650m-ppi` | `encode`, `generate`, `score` | A10G |
| [E1 150m](e1/) | `e1` | `e1-150m` | `e1-150m` | `encode`, `log_prob`, `predict` | T4 |
| [E1 300m](e1/) | `e1` | `e1-300m` | `e1-300m` | `encode`, `log_prob`, `predict` | L4 |
| [E1 600m](e1/) | `e1` | `e1-600m` | `e1-600m` | `encode`, `log_prob`, `predict` | L4 |
| [ESM-1b](esm1b/) | `esm1b` | `esm1b` | `esm1b` | `encode`, `log_prob`, `predict` | T4 |
| [ESM1v n1](esm1v/) | `esm1v` | `esm1v-n1` | `esm1v-n1` | `predict` | CPU |
| [ESM1v n2](esm1v/) | `esm1v` | `esm1v-n2` | `esm1v-n2` | `predict` | CPU |
| [ESM1v n3](esm1v/) | `esm1v` | `esm1v-n3` | `esm1v-n3` | `predict` | CPU |
| [ESM1v n4](esm1v/) | `esm1v` | `esm1v-n4` | `esm1v-n4` | `predict` | CPU |
| [ESM1v n5](esm1v/) | `esm1v` | `esm1v-n5` | `esm1v-n5` | `predict` | CPU |
| [ESM1v all](esm1v/) | `esm1v` | `esm1v-all` | `esm1v-all` | `predict` | T4 |
| [ESM2 8m](esm2/) | `esm2` | `esm2-8m` | `esm2-8m` | `encode`, `log_prob`, `predict` | CPU |
| [ESM2 35m](esm2/) | `esm2` | `esm2-35m` | `esm2-35m` | `encode`, `log_prob`, `predict` | CPU |
| [ESM2 150m](esm2/) | `esm2` | `esm2-150m` | `esm2-150m` | `encode`, `log_prob`, `predict` | T4 |
| [ESM2 650m](esm2/) | `esm2` | `esm2-650m` | `esm2-650m` | `encode`, `log_prob`, `predict` | T4 |
| [ESM2 3b](esm2/) | `esm2` | `esm2-3b` | `esm2-3b` | `encode`, `log_prob`, `predict` | L40S |
| [ESM-IF1 Inverse Fold](esm_if1/) | `esm-if1` | `esm-if1` | `esm-if1` | `generate` | T4 |
| [ESM C 300m](esmc/) | `esmc` | `esmc-300m` | `esmc-300m` | `encode`, `log_prob`, `predict` | A10G |
| [ESMFold](esmfold/) | `esmfold` | `esmfold` | `esmfold` | `fold` | A10G |
| [Evo v1.5-8k](evo/) | `evo` | `evo-v1.5-8k` | `evo-v1.5-8k` | `generate`, `log_prob` | L4 |
| [Evo2 1b-base](evo2/) | `evo2` | `evo2-1b-base` | `evo2-1b-base` | `encode`, `generate`, `log_prob` | L4 |
| [IgBert paired](igbert/) | `igbert` | `igbert-paired` | `igbert-paired` | `encode`, `generate`, `log_prob` | T4 |
| [IgBert unpaired](igbert/) | `igbert` | `igbert-unpaired` | `igbert-unpaired` | `encode`, `generate`, `log_prob` | T4 |
| [IgT5 paired](igt5/) | `igt5` | `igt5-paired` | `igt5-paired` | `encode` | T4 |
| [IgT5 unpaired](igt5/) | `igt5` | `igt5-unpaired` | `igt5-unpaired` | `encode` | T4 |
| [ImmuneBuilder tcrbuilder2](immunebuilder/) | `immunebuilder` | `immunebuilder-tcrbuilder2` | `immunebuilder-tcrbuilder2` | `fold` | CPU |
| [ImmuneBuilder tcrbuilder2plus](immunebuilder/) | `immunebuilder` | `immunebuilder-tcrbuilder2plus` | `immunebuilder-tcrbuilder2plus` | `fold` | CPU |
| [ImmuneBuilder abodybuilder2](immunebuilder/) | `immunebuilder` | `immunebuilder-abodybuilder2` | `immunebuilder-abodybuilder2` | `fold` | CPU |
| [ImmuneBuilder nanobodybuilder2](immunebuilder/) | `immunebuilder` | `immunebuilder-nanobodybuilder2` | `immunebuilder-nanobodybuilder2` | `fold` | CPU |
| [ImmuneFold antibody](immunefold/) | `immunefold` | `immunefold-antibody` | `immunefold-antibody` | `fold` | T4 |
| [ImmuneFold tcr](immunefold/) | `immunefold` | `immunefold-tcr` | `immunefold-tcr` | `fold` | T4 |
| [MPNN protein](mpnn/) | `mpnn` | `protein-mpnn` | `protein-mpnn` | `generate` | CPU |
| [MPNN ligand](mpnn/) | `mpnn` | `ligand-mpnn` | `ligand-mpnn` | `generate` | CPU |
| [MPNN soluble](mpnn/) | `mpnn` | `soluble-mpnn` | `soluble-mpnn` | `generate` | CPU |
| [MPNN global_label_membrane](mpnn/) | `mpnn` | `global-label-membrane-mpnn` | `global-label-membrane-mpnn` | `generate` | CPU |
| [MPNN per_residue_label_membrane](mpnn/) | `mpnn` | `per-residue-label-membrane-mpnn` | `per-residue-label-membrane-mpnn` | `generate` | CPU |
| [MPNN hyper](mpnn/) | `mpnn` | `hyper-mpnn` | `hyper-mpnn` | `generate` | CPU |
| [MSA Transformer](msa_transformer/) | `msa-transformer` | `msa-transformer` | `msa-transformer` | `encode` | T4 |
| [Omni-DNA 1b](omni_dna/) | `omni-dna` | `omni-dna-1b` | `omni-dna-1b` | `encode`, `log_prob` | L4 |
| [ProDy](prody/) | `prody` | `prody` | `prody` | `encode`, `predict` | CPU |
| [ProGen2 oas](progen2/) | `progen2` | `progen2-oas` | `progen2-oas` | `generate` | CPU |
| [ProGen2 medium](progen2/) | `progen2` | `progen2-medium` | `progen2-medium` | `generate` | T4 |
| [ProGen2 large](progen2/) | `progen2` | `progen2-large` | `progen2-large` | `generate` | T4 |
| [ProGen2 bfd90](progen2/) | `progen2` | `progen2-bfd90` | `progen2-bfd90` | `generate` | T4 |
| [ProstT5 encode fold2AA](prostt5/) | `prostt5` | `prostt5-fold2aa-encode` | `prostt5-fold2aa-encode` | `encode`, `generate` | L4 |
| [ProstT5 encode AA2fold](prostt5/) | `prostt5` | `prostt5-aa2fold-encode` | `prostt5-aa2fold-encode` | `encode`, `generate` | L4 |
| [ProstT5 generate fold2AA](prostt5/) | `prostt5` | `prostt5-fold2aa-generate` | `prostt5-fold2aa-generate` | `encode`, `generate` | L4 |
| [ProstT5 generate AA2fold](prostt5/) | `prostt5` | `prostt5-aa2fold-generate` | `prostt5-aa2fold-generate` | `encode`, `generate` | L4 |
| [RosettaFold3](rf3/) | `rf3` | `rf3` | `rf3` | `fold` | A100 |
| [SADIE](sadie/) | `sadie` | `sadie` | `sadie` | `predict` | CPU |
| [SPURS](spurs/) | `spurs` | `spurs` | `spurs` | `predict` | T4 |
| [TemBERTure classifier](temberture/) | `temberture` | `temberture-classifier` | `temberture-classifier` | `encode`, `predict` | T4 |
| [TemBERTure regression](temberture/) | `temberture` | `temberture-regression` | `temberture-regression` | `encode`, `predict` | T4 |
| [ThermoMPNN](thermompnn/) | `thermompnn` | `thermompnn` | `thermompnn` | `predict` | T4 |
| [ThermoMPNN-D](thermompnn_d/) | `thermompnn-d` | `thermompnn-d` | `thermompnn-d` | `predict` | T4 |
| [ZymCTRL](zymctrl/) | `zymctrl` | `zymctrl` | `zymctrl` | `encode`, `generate` | T4 |
<!-- END GENERATED CATALOG -->

Plus [`dummy/`](dummy/) — the template for adding a model — and [`commons/`](commons/) — the shared
framework. Deploy any model with `bh deploy <name>` (see the root [`README.md`](../README.md)).
