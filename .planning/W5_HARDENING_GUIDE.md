# W5 Per-Model Hardening Guide — authoritative procedure for every batch

> **Read this in full before touching any model.** It is the single source of truth for the Stage-3
> per-model fan-out (`.planning/03_WORKSTREAMS.md` W5). Every batch writer follows it verbatim so all
> 45 SHIP models come out identical in shape. The Global Rules in `02_MODEL_INCLUSION_MATRIX.md`
> remain the canonical spec; this guide turns them into concrete, file-by-file steps. Internal file —
> deleted before launch.

## 0. What is already done (do NOT redo)
The commons + global-rules phase is committed. Across the repo: commons is decoupled (no
billing/auth/analytics), `get_logger` exists and 989 `print`→`logger` conversions landed (ruff `T20`
enforced), the canonical action enum + `BioLMError→UserError/ServerError` taxonomy exist and all 46
models were migrated to the new commons API, and `generate_tests_from_suite` now returns-and-assigns
(W17). **So most models already use `get_logger`, `modal_endpoint`, `ModelMixinSnap`,
`biolm_model_class`, and canonical action verbs.** W5 is the per-model *finishing* pass, not a rewrite.

## 1. Reference models (copy their shape)
- **`models/esm2/`** — the canonical Easy-pytorch reference (encode/predict/log_prob, multi-variant).
- **`models/peptides/`** — the canonical pure-CPU reference (single action, single variant).
Match their import layout, decorator usage, logging, and config structure. When in doubt, mirror esm2.

## 2. T0 gate (run locally; the cheap, always-first validation)
The project **pins ruff 0.6.9 and black 24.10.0** (see `.pre-commit-config.yaml`). A newer bare `ruff`
on your PATH invents rules (e.g. `UP045`) the project ignores — **do not use it**. Run the pinned
versions via uv's ephemeral runner so no heavy ML install is needed:

```
uvx ruff@0.6.9 check --no-fix models/<model> [models/<model> ...]   # must report 0 errors
uvx black@24.10.0 --check models/<model> ...                        # must report unchanged
```
`models/` is currently 100% clean under pinned ruff — **keep it at zero**. (The 38 pre-existing ruff
errors in `gateway/` + `.planning/` are out of W5 scope: W8 strips the gateway, `.planning/` is
deleted at launch. Ignore them.)

**Collect-only / imports:** most heavy models import torch/esm/etc. that only exist in the Modal
image, so they **cannot import locally**. Only run `python -m pytest models/<m>/test.py --collect-only`
for dep-light models (peptides, dummy, dna_chisel, biotite, prody…). For heavy models, validate by
static reading + ruff + the lazy-fixture rule (§3.2) + Opus review. **mypy strict** is CI-gated (needs
the full env); reason about types statically, don't try to run it locally.

**No Modal deploys.** Validation is Modal-free (T0 + Opus review). Live deploy is batched into
Milestone A/B and only on the user's explicit go-ahead (`04_TESTING_STRATEGY.md` §0).

## 3. The per-model checklist (apply to every SHIP model)
Work one model at a time. For each, perform these concrete edits, then write a short change report.

### 3.1 `modal_class_name` (mechanical, all models)
In `models/<m>/app.py`, find the class decorated with `@biolm_model_class` (e.g. `class ESM2Model`).
In `models/<m>/config.py`, set that exact class name on the `ModelFamily(...)`:
```python
MODEL_FAMILY = ModelFamily(
    base_model_slug=...,
    modal_class_name="ESM2Model",   # <-- add: the @biolm_model_class class in app.py
    ...
)
```
This is the field W3a defined (`config.py:59`, defaults `None`). W8 wires gateway routing to it; we
only set the value here. If a model has multiple `@biolm_model_class` classes, set the one the gateway
routes to (the inference container class) and note it in the report.

### 3.2 Lazy fixtures (test collection must not touch R2/heavy imports)
`models/<m>/test.py` is collected by pytest. It imports `models/<m>/fixture.py`. **Neither file may do
a module-scope R2 read or heavy import at import time** — otherwise `--collect-only` fails without R2.
- Inspect `fixture.py`: any `read_json_from_r2(...)`, `standard_r2_download(...)`, R2 client calls, or
  `Model.model_validate(<data read from R2>)` at **module top level** (column 0) must move **inside**
  `generate()` (or a helper function). Keep only cheap constants (string path templates, filenames) at
  module level. esm2's `fixture.py` is the worked example to fix (its `read_json_from_r2` block at
  lines 18-29 → move into `generate()`).
- `test.py` must import only cheap symbols from `fixture.py` (path/template strings, the `test_suite`
  builder). The `TestSuite`/`generate_tests_from_suite` calls are already lazy by design (W17).
- Known module-scope offenders to fix: **esm2, spurs** (grep each batch's `fixture.py` yourself).
- Any extra `test_*.py` files (e.g. `test_schema_strictness.py`, `test_unit.py`, `test_errors.py`)
  must also be import-clean and carry correct pytest markers (see §3.10).

### 3.3 Per-model `LICENSE` + attribution (all models)
Create `models/<m>/LICENSE` containing the **upstream license text** for the `license.type` declared
in `sources.yaml`, with the correct upstream copyright line (holder + year from the upstream repo/HF
card in `sources.yaml.source_repos`/`url`). Standard MIT/BSD-3/Apache-2.0 texts apply to most.
- **esmc** is special: Cambrian-Open (300M). The LICENSE/NOTICE must honor the **"Built with ESM"**
  attribution, naming, and attribution terms (user-ratified 2026-06-27). Also **fix the wrong
  `license.type` string** in `esmc/sources.yaml` (it must reflect Cambrian-Open, not a generic label).
- Verify every `sources.yaml` `license.type` matches the matrix in `02`; fix mismatches (the matrix
  flags esm3/esmc as historically wrong — esm3 is excluded, esmc ships).
- If the exact copyright holder/year is genuinely unknown, use the upstream project's standard
  attribution from its LICENSE URL and note the uncertainty in the report for the reviewer.

### 3.4 Logging (Global Rules → Logging)
`logger = get_logger(__name__)` at module top; levels correct (`debug` internals, `info` lifecycle,
`warning` degraded, `error` failures with `exc_info=True`). **No real `print()`** in `app.py`/runtime.
(Note: `print(...)` text **inside a subprocess shell-command string literal** — e.g. dsm/propermab
build-verify commands — is not a Python call and is fine; do not "fix" those.) Never log full
sequences/secrets — use `truncate_for_debug`.

### 3.5 Errors (Global Rules → Errors)
Caller-mistake paths raise a `UserError` subclass from `models.commons.core.error`
(`ValidationError400` / `UnsupportedOptionError` / `ResourceNotFoundError`) carrying its stable
`code`. Never raise bare `Exception`/`ValueError` for user input; never `print`+swallow. Let genuine
system/inference failures propagate (the `modal_endpoint` decorator + gateway sanitize them); wrapping
an inference failure in `ModelExecutionError` is allowed where it adds a clear code. The common
`try/except Exception as e: logger.error(...); raise` pattern around the forward pass is acceptable.

### 3.6 Actions (Global Rules → Actions)
Action verbs were migrated in W7 — **verify**, don't re-migrate. Canonical set:
`predict, fold, encode, generate, score, log_prob`. Confirm `config.py` `action_schemas` use
`ModelActions.*`. Catch residue: search the model's **docs** (`README.md`, `MODEL.md`, `BIOLOGY.md`,
`comparison.yaml`) for stale `predict_log_prob` / `extract_features` and rename to `log_prob` /
`predict` (≈20 models still reference the old names in prose — §3.9). **propermab**: `extract_features`
also survives in `fixture.py`/`test.py` and R2 test-data filenames — rename code refs to `predict`; if
the R2 golden filenames need renaming, **append a row to `COMMONS_REQUESTS.md`** (R2 test-data is
shared infra) rather than guessing.

### 3.7 Schema field names (Global Rules → Schema) — **the per-family judgment work**
Apply canonical field names with `populate_by_name=True` + `Field(alias=<old_name>)` for back-compat:
- **Antibody (🧬ab):** `heavy_chain` / `light_chain` (not `vh`/`vl`/`heavy`/`light`). **Nanobody/VHH**
  (nanobert): a **lone `heavy_chain`** on a model tagged `NANOBODY` — **no `vhh`/`nanobody` field**.
- **TCR (immunefold):** `tcr_alpha`/`tcr_beta`/`tcr_gamma`/`tcr_delta`, `peptide`, `mhc`.
- **PDB chain selectors** (vs raw sequences) take an `_id` suffix (`heavy_chain_id`…).
- **Cross-family inputs:** `sequence`/`sequences`/`msa`, `pdb`/`cif`, `smiles`+`ccd`, `name`, `params`,
  `items`. **Outputs:** `embeddings`, `logits`, `log_prob`, `score`, `sequence`, `pdb`/`cif`,
  `plddt`/`ptm`/`pae`, `results`.
- **Entity-collection naming** for boltz/boltzgen/rf3 (`molecules`/`entities`/`components`) is **High**
  complexity → **optional/defer** (leave as-is unless trivial; note in report).
Use Pydantic aliases so old field names keep working. Most non-antibody models already conform — only
rename where a field actually deviates.

**Pydantic v2 alias mechanics (apply consistently):** make the CANONICAL name the Python field and the
OLD name an input alias, e.g. `heavy_chain: ... = Field(validation_alias=AliasChoices("heavy_chain",
"heavy"))` (or `Field(alias="heavy")` + `model_config = ConfigDict(populate_by_name=True)`), so requests
using either name validate. Ensure OUTPUT serializes the canonical name. **Golden-fixture note:** R2
golden inputs use the OLD field names; input aliases keep them valid, so renaming **input** fields
shouldn't break integration tests — but any **output** field rename changes golden outputs → flag as
Modal-deferred (needs reviewed golden regen, not a blind one).

**Concrete Batch C/D map (scouted — verify against each `schema.py` before editing):**
- `ablang2`, `igbert`, `igt5` — input fields `heavy`→`heavy_chain`, `light`→`light_chain` (alias the
  old names). igbert/igt5 also accept a lone `sequence` (unpaired) — keep it.
- `nanobert` — nanobody model: input becomes a **lone `heavy_chain`** on a `NANOBODY`-tagged model; no
  `vhh`/`nanobody`/`light` field. (Inspect its current single-sequence field and rename/tag.)
- `antifold` — its `heavy_chain`/`light_chain`/`nanobody_chain`/`antigen_chain` are **PDB chain
  SELECTORS**, not sequences → add the `_id` suffix: `heavy_chain_id`/`light_chain_id`/`antigen_chain_id`
  (nanobody selector per the NANOBODY convention). Also normalize antifold's freeform `"score"` action.
- `immunefold` — TCR: chain inputs → `tcr_alpha`/`tcr_beta`/`tcr_gamma`/`tcr_delta`, `peptide`, `mhc`.
- `immunebuilder` — has nanobody mode (`H`→nanobody): lone `heavy_chain` + `NANOBODY` tag.
- `sadie` — `allowed_chain` is a chain-TYPE selector list, NOT heavy/light sequences → leave as-is.
- `propermab` — `VH_charge`/`VL_charge` are output FEATURE names, not input fields → leave; its action is
  `extract_features`→`predict` (already done in code; clean fixture/test/README + R2 test-data via
  COMMONS_REQUESTS).

### 3.8 Deps pinned + image hygiene
In `app.py`, every `uv_pip_install`/`pip_install`/conda dep must be **pinned to an exact version**
(`==`), matching upstream. No floating versions. Image base should be a concrete tag (esm2 uses
`pytorch/pytorch:2.6.0-cuda12.4-cudnn9-runtime`). Don't change working build logic — just pin/verify.

### 3.9 Knowledge graph accuracy
`README.md`, `MODEL.md`, `BIOLOGY.md`, `comparison.yaml`, `sources.yaml` must be accurate and contain
**no internal coupling** (no billing/auth/Moesif, internal domains like `*.biolm.ai`, secret names
like `django-modal`, or `.planning`/internal-repo references). Update stale action names (§3.6). Keep
prose truthful to the code.
- **Stale `BillingMixin`/`BillingMixinSnap` doc refs (repo-wide, ~50 files):** the W2 doc copy left
  caching sections claiming the model "inherits caching from `BillingMixinSnap`". Billing is gone; the
  base classes are `ModelMixin`/`ModelMixinSnap` (no caching — just health/snapshot hooks). **Reframe**
  the caching prose as platform-layer behavior, do not delete the section. Canonical wording (match
  Batch A verbatim): _"Response caching (Redis/R2 two-tier) is handled by the BioLM platform layer, not
  the model container."_ For a `### Caching Behavior` section keep the Redis/R2/Cache-key bullets but
  change the lead-in to: _"Response caching (Redis/R2 two-tier) is handled by the BioLM platform layer,
  not by the model container:"_. Grep each model dir for `BillingMixin` and leave zero refs.

### 3.10 Final per-model checks
- No internal coupling anywhere in the model dir (grep `biolm.ai`, `django-modal`, `moesif`, `billing`,
  `Moesif`, internal secret names).
- Extra `test_*.py` files carry correct markers; pure-pydantic validation tests should **not** be
  marked `integration` (they need no Modal) — mark them so they run in T1, or leave unmarked.
- Re-run the T0 gate (§2) on the model; it must be clean.

## 4. Commons is OFF-LIMITS
Never edit `models/commons/`. If a model needs a commons change, **append a row to
`.planning/COMMONS_REQUESTS.md`** (`model | file:line | what | why | status`) and code around it /
leave a `# TODO(W3b)` note. The coordinator reconciles all requests in one reviewed pass (W3b).

## 5. Output each batch must produce
1. The edits above, model by model.
2. A **per-model change report**: what changed, what was already compliant, any schema aliases added,
   any LICENSE attribution decisions, any `COMMONS_REQUESTS.md` rows added, and anything that can only
   be confirmed by a live Modal deploy (flag as "Modal-deferred").
3. T0 (pinned ruff + black) clean on every touched model.

## 6. Progress ledger
After a batch is committed, tick its models in the `02` per-model checklist and note status here:

| Batch | Models | Status |
|---|---|---|
| A | esm2, esm1b, esm1v, esm_if1, msa_transformer, esmfold, esmstabp, esmc | pending |
| B | dnabert2, omni_dna, e1, evo, dna_chisel | pending |
| C | ablang2, igbert, igt5, nanobert, sadie, antifold | pending |
| D | abodybuilder3, immunebuilder, immunefold, propermab | pending |
| E | boltz, chai1, rf3, rfd3, boltzgen | pending |
| F | thermompnn, thermompnn_d, deepviscosity, temberture, tempro, spurs | pending |
| G | progen2, zymctrl, dsm, evo2, prostt5, pro1 | pending |
| H | peptides, biotite, prody, clean | pending |
