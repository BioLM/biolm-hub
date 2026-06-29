# Review — `models/chai1/`

**Reviewer:** independent launch-gating pass (round-1)
**Verdict:** Solid, structurally conformant. No 🔴 launch-blockers found. The model closely mirrors
the house multi-entity-folding pattern (rf3 / boltz): `Chai1AlignmentDatabase`, `Chai1EntityType`,
`Chai1Molecule`/`Chai1PredictRequestInput`, `dict[…AlignmentDatabase, str]` MSA input, `fold` action,
nested `results: list[list[...]]`. Plumbing is uniform with peers. The issues are: one acquisition
gap (ESM embedding weights not pre-cached), a LICENSE that still carries a "reviewer must verify"
note, a doc-vs-code dependency mismatch, an off-framework extra integration test, and the usual
documentation/dead-code residue. Several items below are **repo-wide** patterns (flagged so a global
reviewer can sweep them) rather than chai1-specific defects.

## Cross-checks performed
- Action verb (`fold`) matches intent and matches config (`ModelActions.FOLD`). ✓
- Schema field names (`alignment` dict, `cif`/`pae`/`plddt`, `items`/`params`, `results`) match the
  rf3/boltz house pattern, not a deviation. ✓
- `pae` description matches `tooling/field_glossary.yaml` verbatim string exactly. ✓
- Field descriptions are all at `Field(...)` level (not buried in `Optional[Annotated[...]]`), so they
  render in `model_json_schema()`. ✓
- slug/display_name consistent across config / sources.yaml / comparison.yaml (`chai1` / `Chai-1`). ✓
- sources.yaml license (Apache-2.0) consistent with the LICENSE file. ✓
- Build-order rule satisfied a different (valid) way: `chai-lab` is pip-installed *before*
  `setup_download_layer`, so the `r2_then_library` fallback can import it at build time. ✓
- No `biolm-modal` / `.planning` / internal-domain leakage. (One `qa` env-name comment — see Y8.)

---

## 🟠 Should-fix

### O1 — ESM embedding weights are not pre-cached; default inference downloads them at runtime
**category:** acquisition / cold-start reliability · **file:** `app.py:258`, `download.py:85,132-137`
`Chai1PredictRequestParams.use_esm_embeddings` defaults to **`True`**, and `app.py` passes it straight
into `run_inference`. But the build-time weight acquisition (`download.py::_init_chai1_weights`) calls
`run_inference(..., use_esm_embeddings=False)`, and `required_files` lists only
`models_v2/*.pt` + `conformers_v1.apkl`. So the ESM-2 (3B) embedding checkpoint chai-lab needs for the
*default* code path is never fetched into R2 at build — the first real request will pull it from
HuggingFace at inference time. This adds hidden cold-start latency/failure surface and defeats the
repo's "self-populate the public bucket" goal for this dependency.
**fix:** run the build-time `init_fn` with `use_esm_embeddings=True` (or otherwise pre-fetch the ESM
checkpoint) and add the ESM weight file(s) to `required_files`/`monitor_directories` so they cache to
R2. (Verify the exact path chai-lab uses for the ESM cache.)

### O2 — LICENSE still carries an unresolved "reviewer must verify" note + inferred copyright
**category:** licensing / DoD / open-source readiness · **file:** `LICENSE:175-182`
The file appends, after the Apache text: `Copyright (c) 2024 Chai Discovery, Inc.` plus a footer
"Note: Copyright holder … and year … inferred … **Reviewer should verify against the upstream LICENSE
file before public release.**" That is an open porting-phase action item shipping inside a public
LICENSE. The provenance footer (Upstream source / License URL) is fine to keep; the
inferred/"reviewer should verify" note is residue.
**fix:** verify the copyright line against chai-lab's upstream `LICENSE`, then delete the inferred-note
paragraph. Keep only the upstream-source provenance lines.

### O3 — README dependency table states `torch==2.3.1`, but the image base is PyTorch 2.6.0
**category:** docs vs code · **file:** `README.md:190`
The Resource Requirements table lists `Dependencies | chai-lab==0.6.1, torch==2.3.1, biopython==1.83`,
but `app.py:31` builds from `pytorch/pytorch:2.6.0-cuda12.4-cudnn9-runtime` (torch 2.6.0) and never
pins torch to 2.3.1. A contributor trying to reproduce the environment would be misled.
**fix:** change the stated torch version to 2.6.0 (or to whatever chai-lab 0.6.1 resolves to on that
base), or drop the explicit version.

### O4 — `test_edge_case.py` is an off-framework, expensive integration test
**category:** tests / convention / cost-discipline · **file:** `test_edge_case.py:40-54`
This is a standalone `@pytest.mark.integration` test that bypasses the shared
`TestSuite`/`generate_tests_from_suite` machinery, hardcodes the `"Chai1Model"` class string and the
app name, and submits a **4-entity** complex (protein + protein-with-alignment + DNA + ligand) to a
deployed A100-80GB model on every integration run. It duplicates what `deployment_test_suite` already
covers (which deliberately uses a minimal 1-residue protein for cost control), but at much higher GPU
cost, and the hardcoded class name can silently drift from config. The house pattern keeps the extra
file as a *unit* test (cf. esm2 `test_schema_strictness.py`), not a second deployment caller.
**fix:** fold this case into `test.py`'s suite (as a deployment/integration `ActionTestCase`) or
delete it; if kept, shrink the input and derive the class name from `MODEL_FAMILY.modal_class_name`.

---

## 🟡 Nits / polish

### Y1 — `include` / `pae` / `plddt` are advertised in the public schema but permanently disabled
**file:** `schema.py:172-179`, `app.py:299-308`
`force_empty_include` always returns `[]`, so `Chai1ScoreOptions`, the `include` param, and the
response `pae`/`plddt` fields can never be populated; `app.py:299-308` are dead branches. A caller who
sends `include=["pae"]` gets silent discard rather than an error. It's documented in the field
description and README, so this is a wart, not a bug.
**fix:** either remove the disabled surface from the public schema until it's wired up, or have the
validator raise a `UserError` when a caller explicitly requests a disabled score (instead of silently
dropping it). At minimum, delete the now-dead `app.py:299-308` access paths.

### Y2 — Dead code: `ALLOWED_ENTITY_TYPES` is defined but never used
**file:** `schema.py:126-134`
The set duplicates the values already enforced by the `Chai1EntityType` enum and is referenced
nowhere. **fix:** delete it.

### Y3 — Bare `FileNotFoundError` instead of a typed error
**file:** `app.py:281`
A missing generated CIF is a system fault but is raised as a bare `FileNotFoundError`, bypassing the
`BioLMError` taxonomy used elsewhere in the file (`UserError`). **fix:** raise `ServerError` (or let it
propagate through the sanitizing boundary) rather than a bare builtin.

### Y4 — TODO / stale residue in shipped files
**file:** `app.py:232`, `schema.py:171`, `README.md:175`, `MODEL.md:112`, `BIOLOGY.md:61`
Runtime TODO comment `# TODO: check why just BFD is not allowed` (`app.py:232`), `# TODO: Disabled for
now …` (`schema.py:171`), and three `<!-- TODO … -->` markers in the knowledge-graph files. Note
`BIOLOGY.md:61` ("Add applied literature examples as they become available") is **stale** — sources.yaml
already lists six `applied_literature` entries that BIOLOGY.md's "Applied Use Cases" section never
summarizes. (TODO-in-MODEL/BIOLOGY is a repo-wide pattern; the stale BIOLOGY one is chai1-specific.)
**fix:** resolve/remove the TODOs; have BIOLOGY.md actually reflect the now-populated applied literature.

### Y5 — Docs label the action `predict`, but the deployed verb is `fold`
**file:** `README.md:56`, `MODEL.md` (action prose)
The "Actions / Endpoints" section is headed ```### `predict` ``` and described as "Predicts the 3D
structure…", but the action is `ModelActions.FOLD` and the Modal method is `fold`. This is **systemic**
across folding models (esmfold/rf3/boltz all document `### predict` for a `fold` action), so it's a
uniformity bug to fix repo-wide, not a chai1 regression.
**fix (global):** standardize folding-model README/MODEL action headers to `### fold`.

### Y6 — `smiles` field skips the ligand length cap; dual sequence/smiles path is confusing
**file:** `schema.py:59-66, 108-113`
A ligand supplied via the dedicated `smiles` field is only `validate_smiles`-checked, while a ligand
supplied through `sequence` (type=ligand) additionally enforces `max_ligand_len` (128). So the length
limit is bypassable via the `smiles` path. The two interchangeable ways to pass a ligand (and the
`sequence` description that says it may itself be "a SMILES sequence") are also a readability snag.
**fix:** apply the same `max_ligand_len` check in `validate_smiles_field`; consider documenting that
`smiles` is the preferred ligand path.

### Y7 — `comparison.yaml` references `af2_nim`, which is not a model in this repo
**file:** `comparison.yaml:49`
`alternatives:` lists `model: af2_nim`, but there is no `models/af2_nim/`. (Systemic — boltz, esmfold,
and rf3 comparison.yaml reference it too.) Dangling cross-references break catalog linking.
**fix (global):** either add the model, drop the reference, or point to the slug that does ship.

### Y8 — Internal `qa` environment name in the usage comment
**file:** `app.py:323`
`# Force deploy to "qa" or "main" environment:` names the internal `qa` env, which the rubric lists as
an internal-reference leak. This is **systemic** — it originates in `models/commons/modal/deployment.py`
(`help="Force deploy even if environment is 'qa' or 'main'"`, and the `("qa", "main")` guard) and is
copied into nearly every model's `__main__` block (including the esm2 reference). Flagging for a global
decision rather than as a chai1-only fix.
**fix (global):** decide whether `qa` should be referenced in shipped files; if not, sweep commons +
all `app.py` usage comments.

### Y9 — f-string in a logging call instead of lazy `%`-args
**file:** `app.py:128`
`logger.info(f"conformers_v1.apkl found ({…:.1f} MB)")` uses an eager f-string where the rest of the
file (and repo) uses lazy `%`-formatting (`logger.info("…", arg)`). Minor consistency nit.
**fix:** convert to `logger.info("conformers_v1.apkl found (%.1f MB)", size_mb)`.

---

## Definition-of-Done notes (W5 per-model hardening)
- Layout / config.py `ModelFamily`: **met.**
- Closed-set action (`fold`): **met.**
- Field names + descriptions render, glossary-consistent: **met.**
- Typed errors: **mostly met** (one bare `FileNotFoundError`, Y3).
- Structured logging, no `print`: **met** (one f-string style nit, Y9).
- Canonical acquisition + self-populating R2: **partially met** — ESM embedding weights gap (O1).
- Per-model LICENSE, permissive, consistent: **met but residue** — reviewer note (O2).
- Knowledge graph present/consistent: **met but residue** — stale/TODO markers (Y4), dangling
  `af2_nim` (Y7).
- TestSuite (integration + deployment), lazy fixtures: **met**, plus an off-framework extra (O4).

---

## Verification

Adversarial re-check of the four HIGH-severity findings against the actual source.

- **ESM embedding weights not pre-cached (O1) — REAL.** `schema.py:163-166` defaults
  `use_esm_embeddings=True`; `app.py:258` passes `params.use_esm_embeddings` straight into
  `run_inference`; build-time `_init_chai1_weights` runs with `use_esm_embeddings=False`
  (`download.py:85`); `required_files`/`monitor_directories` (`download.py:132-137,146`) list only
  `models_v2/*.pt` + `conformers_v1.apkl` + `~/.cache/chai` — no ESM-2 checkpoint or HF cache. The
  default production path therefore needs ESM weights that the build never fetches into R2. Confirmed.

- **LICENSE ships unresolved reviewer note + inferred copyright (O2) — REAL.** `LICENSE:175,180-182`
  literally contains `Copyright (c) 2024 Chai Discovery, Inc.` plus `Note: ... inferred ... Reviewer
  should verify against the upstream LICENSE file before public release.` — a porting-phase action
  item shipping inside a public LICENSE. Confirmed (the Upstream/License-URL lines 178-179 are fine).

- **README torch==2.3.1 vs image base 2.6.0 (O3) — REAL.** `README.md:190` lists
  `torch==2.3.1`, but `app.py:31` builds from `pytorch/pytorch:2.6.0-cuda12.4-cudnn9-runtime` and the
  `pip_install` block (`app.py:36-42`) never re-pins torch — so runtime torch is 2.6.0. Documentation
  contradicts the declared image. Confirmed.

- **test_edge_case.py off-framework, expensive integration test (O4) — REAL** (two minor wording
  nits). `test_edge_case.py:40` is `@pytest.mark.integration`; it bypasses
  `generate_tests_from_suite` (used by `test.py:96,101`) via `modal.Cls.from_name` + `.fold.remote`
  (lines 47-51); hardcodes class string `"Chai1Model"` (line 47) which can drift from
  `config.py:30 modal_class_name`; submits a 4-entity complex with `use_esm_embeddings=True`,
  `num_trunk_recycles=4`, `num_diffusion_timesteps=180` (lines 9-37) to the A100-80GB model
  (`config.py:22`) on every integration run. House pattern for extra tests is a cheap unit test (cf.
  `models/esm2/test_schema_strictness.py`). Nits: the *app name* is config-derived
  (`Chai1Params.base_model_slug`, line 44), not hardcoded; and it does not literally "duplicate"
  `deployment_test_suite` (which is `@deployment`, 1-residue, esm-off, `test.py:59-93`) — it is a
  separate, costlier integration case. Core claim holds.
