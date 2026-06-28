# Model Inclusion Matrix & Per-Model Hardening

Drives the Stage-3 per-model fan-out. License/actions/Docker-bucket from the 2026-06-21 investigation
+ the 2026-06-24 licensing deep-dive (`sources.yaml` is the authoritative license source). **Verify
`license.type` in each model's `sources.yaml` before shipping** — and note several `sources.yaml`
license strings are wrong (esp. esm3/esmc, see below) and must be corrected.

**Legend — Decision:** `SHIP` (clean MIT/Apache-2.0/BSD) · `SHIP-LATER` (will ship once an upstream
blocker clears) · `EXCLUDE` · `TEMPLATE`. **Docker bucket** (Stage-6 optional-split feasibility): Easy / Medium / Hard / TBD.
**★fold** = migrated from `predict` to the new `fold` action. **🧬ab** = antibody family →
schema-naming standardization. **Action changes (Stage 2, applied here already):** `predict`→`fold`
for ★fold; `predict_log_prob`→`log_prob` everywhere; `extract_features`→`predict` (propermab).

| Model | License | Decision | Actions | Docker | Notes |
|---|---|---|---|---|---|
| ablang2 | BSD-3 | SHIP | encode, predict, generate, log_prob | Easy | 🧬ab |
| ablef | Proprietary (BioLM) | EXCLUDE | predict, encode | — | internal model |
| abodybuilder3 | Apache-2.0 | SHIP | fold | Hard (conda) | 🧬ab ★fold |
| af2_nim | NIM | EXCLUDE | encode, predict, predict_from_msa, predict_multimer | Hard (NIM) | closed NVIDIA ECR — impossible to ship |
| antifold | BSD-3 | SHIP | encode, generate, score, log_prob | Medium | 🧬ab; normalize freeform `"score"`→enum |
| biolmtox2 | Proprietary (BioLM) | EXCLUDE | encode, predict | Easy | internal model |
| biotite | BSD-3 | SHIP | generate, predict | Easy | freeform misuse (generate=chain-extract, predict=RMSD) → relabel as utilities in Stage 3 |
| boltz | MIT | SHIP | fold | Easy | ★fold |
| boltzgen | MIT | SHIP | generate | Medium/Hard | structure design |
| camsol | Proprietary (reverse-eng) | EXCLUDE | predict | Easy | legally ambiguous |
| chai1 | Apache-2.0 | SHIP | fold | Hard (GPU build) | ★fold |
| clean | BSD-3 | SHIP | predict, encode | TBD | |
| deepviscosity | MIT | SHIP | predict | Hard (conda) | antibody viscosity |
| diamond | GPL-3.0 | **EXCLUDE** | predict | Medium | GPL binary is *subprocess-only* (mere aggregation → legally shippable), but **excluded to keep the repo cleanly permissive** + avoid GPL-binary redistribution overhead |
| dna_chisel | MIT | SHIP | encode | Easy | |
| dnabert2 | Apache-2.0 | SHIP | encode, log_prob | Easy/Medium | post-install triton uninstall |
| dsm | Apache-2.0 | SHIP | generate, encode, score | Medium | |
| dummy | MIT | **TEMPLATE** | predict | Easy | keep as the new-model template |
| e1 | Apache-2.0 | SHIP | encode, predict, log_prob | TBD | |
| esm_if1 | MIT | SHIP | generate | Easy | inverse folding = sequence design (keep `generate`) |
| esm1b | MIT | SHIP | encode, predict, log_prob | Easy | |
| esm1v | MIT | SHIP | predict | Easy | |
| **esm2** | MIT | SHIP | encode, predict, log_prob | Easy | **Stage-1d vertical-slice reference** |
| esm3 | **Cambrian Non-Commercial** (sources.yaml wrongly says "ESM Open Model License") | **EXCLUDE** | encode, predict, log_prob | Easy | only OPEN_SMALL variant ships in config, still non-commercial |
| esmc | **Cambrian Open (300M) / Non-Commercial (600M)** | **SHIP** | encode, predict, log_prob | Easy | **300M only** (drop 600M); user-approved 2026-06-27; honor Cambrian-Open "Built with ESM"/naming/attribution via per-model LICENSE; fix the wrong `license.type` string |
| esmfold | MIT | SHIP | fold | Easy | ★fold |
| esmfold2 | **MIT (Chan Zuckerberg Biohub)** | **SHIP-LATER** | fold | Hard (GPU) | ★fold; new model; add **only after** the upstream PR (`aqamar/add-esmfold2`) merges into `biolm-modal` `main`, then re-confirm weights license (incl. ESMC-6B backbone) |
| esmstabp | MIT | SHIP | predict | Easy | |
| evo | Apache-2.0 | SHIP | log_prob, generate | TBD | |
| evo2 | Apache-2.0 | SHIP | encode, log_prob, generate | Hard (GPU build) | |
| gemme | Academic | EXCLUDE | score | Medium | non-commercial |
| igbert | CC-BY-4.0 (Zenodo/Exscientia; matrix "MIT" was wrong) | SHIP | encode, generate, log_prob | TBD | 🧬ab; commercial-OK with attribution |
| igt5 | CC-BY-4.0 (Zenodo/Exscientia; matrix "MIT" was wrong) | SHIP | encode | TBD | 🧬ab; commercial-OK with attribution |
| immunebuilder | BSD-3 | SHIP | fold | Hard (conda) | 🧬ab ★fold |
| immunefold | Apache-2.0 | SHIP | fold | Hard (conda) | 🧬ab ★fold; TCR fields → `tcr_*`/`peptide`/`mhc` |
| mpnn | MIT | SHIP | generate | Medium (micromamba) | candidate hard vertical slice (Stage 1d) |
| msa_search_nim | NIM | EXCLUDE | encode, encode_paired | Hard (NIM) | closed NVIDIA ECR |
| msa_transformer | MIT | SHIP | encode | Easy | |
| nanobert | **CC-BY-NC-SA-4.0** (HF card `NaturalAntibody/nanoBERT`; matrix "MIT" was wrong — GitHub LICENSE 404s) | **EXCLUDE** | encode, generate, log_prob | TBD | 🧬ab; NonCommercial weights — **user-confirmed EXCLUDE 2026-06-28** (revisitable if NaturalAntibody grants a commercial license) |
| nt | CC-BY-NC-SA-4.0 | EXCLUDE | encode, log_prob | Easy | non-commercial |
| omni_dna | Apache-2.0 | SHIP | encode, log_prob | Easy | |
| peptides | Apache-2.0 | SHIP | encode | Easy | simplest CPU model — 2nd vertical slice |
| poet | CC-BY-NC-SA-4.0 | EXCLUDE | score, encode | Medium | non-commercial weights |
| pro1 | Apache-2.0 | SHIP | generate | TBD | license per HF model card (GitHub repo has no LICENSE file) — confirm during hardening |
| pro4s | CC-BY-NC-4.0 | EXCLUDE | predict | TBD | non-commercial |
| prody | MIT | SHIP | encode, predict | Easy | structure as input → stays `predict` |
| progen2 | BSD-3 | SHIP | generate | Medium | |
| propermab | **Non-Commercial / Academic-Only** (Regeneron `propermab/LICENSE.md`; matrix "MIT" was wrong) | **EXCLUDE** | predict | Hard (conda) | 🧬ab; NonCommercial weights (Regeneron Pharmaceuticals) — **EXCLUDE 2026-06-28** by the ratified NC criterion (same call as nanobert) |
| proteina_complexa | code Apache-2.0 / **weights NVIDIA Open Model License (REVOCABLE)** | **EXCLUDE** | generate | TBD | weights royalty-free + commercial but **revocable** (on litigation/guardrail-bypass) + attribution; **user-confirmed EXCLUDE 2026-06-27** (revisitable later) |
| prostt5 | MIT | SHIP | encode, generate | TBD | |
| rf3 | BSD-3 | SHIP | fold | Medium | ★fold |
| rfd3 | BSD-3 | SHIP | generate | Medium | structure design |
| sadie | MIT | SHIP | predict | Easy | 🧬ab |
| saprot | CC-BY-NC-SA-4.0 | EXCLUDE | score, encode | TBD | non-commercial |
| soluprot | Academic | EXCLUDE | predict | TBD | non-commercial |
| spurs | MIT | SHIP | predict | Easy | structure as input → stays `predict` |
| temberture | MIT | SHIP | encode, predict | Easy | |
| tempro | MIT | SHIP | predict | Easy | |
| thermompnn | MIT | SHIP | predict | Hard (conda) | |
| thermompnn_d | MIT | SHIP | predict | Hard (conda) | |
| zymctrl | Apache-2.0 | SHIP | generate, encode | TBD | |

**Totals (61 rows = 60 model dirs on `main` + the not-yet-on-disk `esmfold2`):** **43 SHIP** (incl.
`esmc` 300M, `pro1`) + **1 SHIP-LATER** (`esmfold2`) + **1 TEMPLATE** (`dummy`) + **16 EXCLUDE**
(`ablef`, `af2_nim`, `biolmtox2`, `camsol`, `diamond`, `esm3`, `gemme`, `msa_search_nim`, `nanobert`,
`nt`, `poet`, `pro4s`, `propermab`, `proteina_complexa`, `saprot`, `soluprot`).
**W5 license verification (2026-06-28) corrected the matrix:** `nanobert` (CC-BY-NC-SA-4.0) and
`propermab` (Regeneron NonCommercial) were wrongly listed MIT → now **EXCLUDED** (NonCommercial, same
criterion as esm3/nt/poet); `igbert`/`igt5` were wrongly listed MIT → corrected to **CC-BY-4.0** (still
SHIP, commercial-OK with attribution). Verify each model's `sources.yaml` license string against
upstream before launch (the matrix has been wrong on licenses repeatedly).

---

## Global Rules (locked in Stage 2 — apply verbatim in every per-model review)

These are the canonical, repo-wide standards. The Stage-2 global pass sets them once; the Stage-3
per-model fan-out only *applies* them. Keep this section authoritative and in sync with `CONTRIBUTING`.

### Actions (canonical enum)
`predict, fold, encode, generate, score, log_prob` — that's the whole set.
- `fold` = 3D-structure prediction (returns `pdb`/`cif` + confidence). `predict` = scalar/label
  property of a sequence/structure (structure may be *input*). `encode` = NN embeddings.
- `generate` = produce new sequences/structures (LM sampling, infilling, inverse folding, structure
  design) — **not** split into `design`. `score` = model-defined scalar fitness (umbrella; document
  per model). `log_prob` = uniform per-sequence pseudo-log-likelihood scalar (kept distinct from
  `score`).
- `extract_features` is **retired** (propermab→`predict`).

### Schema field names
- **Inputs (all families):** `sequence` / `sequences` / `msa`; `pdb` / `cif` (by format);
  `smiles` + `ccd`; `name`; wrappers `params` + `items` (batch).
- **Antibody:** `heavy_chain` / `light_chain`. **Nanobody/VHH = a lone `heavy_chain`** on a model
  tagged `NANOBODY` (the molecule distinction lives in the `InputMolecule` **tag**, not the field
  name — **no `vhh`/`nanobody` field anywhere**). **TCR** = `tcr_alpha`/`tcr_beta`/`tcr_gamma`/
  `tcr_delta`, `peptide`, `mhc`. **PDB chain selectors** (vs sequences) get an `_id` suffix
  (`heavy_chain_id`…).
- **Outputs:** `embeddings`, `logits`, `log_prob`, `score`, `sequence` (generated), `pdb`/`cif`,
  `plddt`/`ptm`/`pae`, wrapper `results`.
- Use pydantic `populate_by_name` + `Field(alias=…)` for back-compat during migration. (Entity-
  collection naming for boltz/boltzgen/rf3 — `molecules`/`entities`/`components` — is **High**
  complexity; optional/defer.)

### Logging
`from models.commons.core.logging import get_logger; logger = get_logger(__name__)` at module top.
**No `print()`** in runtime code (`app.py`, `commons/`, `gateway/`) — enforced by ruff `T20` (allowed
in `scripts/`, CLI, tests). Levels: `debug`=internals, `info`=lifecycle, `warning`=degraded,
`error`=failure (with `exc_info=True`). Never log full sequences/secrets (use `truncate_for_debug`).
Stdlib only — **no structlog**.

### Errors
Raise a `UserError` subclass (from `models.commons.core.error`) for caller mistakes — surfaced
verbatim with a stable machine-readable `code`. Hierarchy:
`BioLMError → UserError(+ValidationError400, UnsupportedOptionError, ResourceNotFoundError) /
ServerError(+ModelExecutionError)`. Let system errors propagate (sanitized to 5xx by the gateway).
**Never** raise bare `Exception`/`ValueError` for user input; never `print`+swallow.

### Shared test assets
Standard cross-model inputs live under `test-data/shared/` in public R2 with stable canonical names
(e.g. `shared/protein/<name>.fasta`, `shared/dna/<name>.fasta`, `shared/pdb/<name>.cif`). Per-model
fixtures reference these where a standard sequence suffices (the path-templating already supports it);
only model-specific inputs get a per-model fixture. This convention is **locked in Stage 2** so the
Stage-3 fan-out writes fixtures against it with no later refactor. (W12.)

---

## Per-model hardening checklist (Stage 3)

Run for every `SHIP` model. Don't mark the model done until all are checked. **Never edit
`models/commons/` here** — **surface** any commons change request by appending a row to
`.planning/COMMONS_REQUESTS.md` (model · file:line · what · why); the coordinator batches them into the
single reviewed commons-reconciliation pass (W3b).

- [ ] **License** verified in `sources.yaml` (fix wrong strings); per-model `LICENSE`/attribution file present.
- [ ] **Code review + simplification** against its reference model(s); note any intentional deviation.
- [ ] **Logging:** `get_logger(__name__)`; no `print`; correct levels. (Global Rules → Logging.)
- [ ] **Schema** conforms to the canonical field names (Global Rules → Schema); antibody/nanobody/TCR convention if 🧬ab.
- [ ] **Errors** use the `BioLMError`/`UserError` hierarchy + `code` (Global Rules → Errors); no bare exceptions to the user.
- [ ] **Actions** verbs canonical: `predict`→`fold` if ★fold; `predict_log_prob`→`log_prob`; `extract_features`→`predict` (propermab).
- [ ] **Discovery:** `modal_class_name` set in `config.py` (matches the `@biolm_model_class` class in `app.py`; CI-guarded — field defined in Stage 2, routing swap in W8).
- [ ] **Deps** pinned to exact versions; image builds cleanly from the new repo.
- [ ] **Deploy** to a clean Modal account from the new repo; weights pulled from public R2 (`biolm-public`).
- [ ] **Tests:** fixtures generated (reference `test-data/shared/` assets where standard — W12); **fixtures lazy-load — no module-scope R2 read / heavy import**, so `pytest models/<m>/test.py --collect-only` works without Modal/R2 (W17 follow-up); integration + deployment tests green; coverage ≥85%.
- [ ] **Knowledge graph** (`README.md`, `MODEL.md`, `BIOLOGY.md`, `comparison.yaml`, `sources.yaml`) accurate & complete.
- [ ] **No internal coupling** (billing/auth/Moesif/secret names/internal domains) anywhere in the model.
- [ ] **Reviewer agent** (Opus, fresh context) signed off on the batch diff.

---

## Suggested Stage-3 batches (5–8 models, grouped by shared deps/architecture)

Batching by architecture keeps each worktree's dependency context coherent. **All batches depend on
Stage-2 global rules + the simplified commons being merged first.** `esmfold2` is held out of the
batches until its upstream PR merges into `biolm-modal` `main`.

- **Batch A — ESM / protein LM (Easy, pytorch registry):** esm2, esm1b, esm1v, esm_if1, msa_transformer, esmfold, esmstabp, esmc (300M)
- **Batch B — DNA / genomic:** dnabert2, omni_dna, e1, evo, dna_chisel
- **Batch C — Antibody LMs:** ablang2, igbert, igt5, nanobert, sadie, antifold
- **Batch D — Antibody/structure (conda-heavy):** abodybuilder3, immunebuilder, immunefold, propermab
- **Batch E — Folding/structure (GPU/heavy):** boltz, chai1, rf3, rfd3, boltzgen
- **Batch F — Thermostability / property (conda + simple):** thermompnn, thermompnn_d, deepviscosity, temberture, tempro, spurs
- **Batch G — Generative / misc:** progen2, zymctrl, dsm, evo2, prostt5, pro1
- **Batch H — Simple CPU / utility:** peptides, biotite, prody, clean

> Schema standardization (W7) for 🧬ab models spans Batches C and D, and the ★fold migration spans
> Batches D and E — both are locked in Stage 2 **before** these batches run, so a batch never needs a
> second schema/action pass. The exact batch split may be **recomputed** once the Stage-2 framework
> changes land (master plan §7 re-plan note).
