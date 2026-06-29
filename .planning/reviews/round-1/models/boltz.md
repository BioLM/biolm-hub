# Review — `models/boltz/` (Round 1)

**Reviewer:** independent launch-gating review
**Verdict:** NOT launch-ready. Two 🔴 must-fix items (a runtime dependency on an *excluded* internal
model exposed through the public schema, and `biolm-modal` internal references in shipped test files),
plus several 🟠 contract/accuracy issues.

## Summary

Boltz is an unusually large and ambitious model wrapper (two variants, affinity, constraints,
templates, server-side ipSAE/ipae, embeddings). The engineering quality of the subprocess handling
(pipe-deadlock avoidance, timeout, signal interpretation, silent-failure guards) and the pure-math
unit tests (`test_unit.py`) is genuinely good. The plumbing largely matches the house pattern
(`ModelMixinSnap`, `setup_download_layer`/`setup_source_layer`, `r2_then_urls`, `ModelActions.FOLD`,
`results`-wrapped batch output, `cif` output field matching chai1).

However, the model ships a **public `msa_search` feature whose entire implementation depends on
`msa_search_nim`, which is on the EXCLUDE list and is absent from this repo** — so the feature cannot
work and it leaks an internal/closed-NIM reference. The model docs even *claim* "no automatic MSA
generation," directly contradicting the schema. Separately, `pae`/`pde`/`plddt` response fields and
the `PLDDT`/`PDE` include options are dead (always `None` / no-ops) while their schema descriptions
imply they are returned. Shipped test files reference `r2://biolm-modal`. The LICENSE carries a
placeholder copyright holder and a "reviewer must verify" note.

---

## 🔴 Must-fix before launch

### 1. Public `msa_search` feature depends on the EXCLUDED `msa_search_nim` model (broken contract + internal-reference leak)
- **Category:** correctness / internal leakage / broken public contract
- **Location:** `models/boltz/schema.py:37-49,123-130`; `models/boltz/app.py:107-343`
- **Detail:** `schema.py` exposes `MSASearchMode` and the `msa_search` request param. `app.py`
  implements the whole integration: `_MSA_SEARCH_APP_NAMES = {FAST: "msa-search-nim-fast",
  STANDARD: "msa-search-nim"}` (app.py:130-133), `modal.Cls.from_name(nim_app_name,
  "MSASearchService")` (app.py:140), and `from models.msa_search_nim.schema import
  MSASearchEncodeRequest / MSAPairedEncodeRequest` (app.py:262,307). But `models/msa_search_nim` does
  **not exist** in this repo — it is explicitly EXCLUDED (`.planning/02_MODEL_INCLUSION_MATRIX.md:52`,
  "closed NVIDIA ECR"; `.planning/00_MASTER_PLAN.md:158`). Any request with `params.msa_search` set
  reaches `_generate_msa_for_entities` → `modal.Cls.from_name("msa-search-nim", …)` and then the
  lazy `import models.msa_search_nim.schema`, which raises `ModuleNotFoundError` / a missing-app
  error at runtime. So the field is a non-functional part of the public contract *and* it exposes a
  reference to a closed, internal-only NIM the OSS repo deliberately omits. chai1 (the closest
  sibling) exposes no such field.
- **Fix:** Remove the auto-MSA feature from the OSS surface: delete `MSASearchMode`, the `msa_search`
  field (schema.py), and the entire MSA-NIM integration block in app.py (`_MSA_DB_TO_BOLTZ`,
  `_MSA_SEARCH_APP_NAMES`, `_get_msa_search_cls`, `_get_msa_search_service`,
  `_extract_alignments_from_nim_result`, `_generate_msa_*`, and the call site at app.py:476-482).
  This also resolves finding #5 (docs already say "no automatic MSA"). If auto-MSA is genuinely
  wanted at launch, it must be rebuilt on an *included* MSA source, not the excluded NIM.

### 2. `biolm-modal` internal references in shipped files
- **Category:** internal leakage
- **Location:** `models/boltz/fixture.py:16`; `models/boltz/test.py:112,138`
- **Detail:** The rubric explicitly lists `biolm-modal` as a must-fix internal-reference leak.
  `fixture.py` docstring hardcodes `r2://biolm-modal/test-data/models/boltz/`, and `test.py` comments
  reference `r2://biolm-modal/test-data/models/boltz/boltz1/` and `…/boltz2/`. These ship publicly.
  (The functional paths correctly use the `r2_bucket_name` / `r2_test_data_dir` config vars; only the
  docstring/comments leak the literal bucket name.)
- **Fix:** Replace the literal `r2://biolm-modal/...` strings with the abstract test-data location
  (e.g. "the configured R2 test-data bucket under `test-data/models/boltz/`") or drop the explicit
  bucket prefix.

---

## 🟠 Should-fix

### 3. `boltz1` deployed app advertises the Boltz2 schema (per-variant schema/runtime mismatch)
- **Category:** correctness / public contract / consistency
- **Location:** `models/boltz/config.py:58-64` (registers `BoltzPredictRequest`/`BoltzPredictResponse`)
  with `schema.py:640` (`BoltzPredictRequest = Boltz2PredictRequest`)
- **Detail:** `config.MODEL_FAMILY.action_schemas` is a single static list and registers the Boltz2
  request/response for *both* variants. The runtime method, by contrast, validates against a
  per-variant type (`app.py:67-70`, `BoltzPredictRequestType = Boltz1PredictRequest` for boltz1).
  Because `RequestModel` is `extra="forbid"` (`commons/model/pydantic.py:30`), the boltz1 app
  advertises Boltz2-only fields (`affinity`, `affinity_mw_correction`, `sampling_steps_affinity`,
  `diffusion_samples_affinity`, `constraints`, `templates`) that the boltz1 runtime will reject. A
  caller trusting the published boltz1 schema will get validation errors. (Other multi-variant
  models like esm2 don't hit this because size variants share one schema; boltz1 vs boltz2 genuinely
  differ.)
- **Fix:** Make the registered action schema variant-aware (select Boltz1 vs Boltz2 request/response
  in `config.py` based on `MODEL_VERSION`, mirroring app.py's `BoltzPredictRequestType`), or collapse
  to a single schema where Boltz1-invalid fields are validated/rejected with a clear message.

### 4. `pae` / `pde` / `plddt` response fields and `PLDDT`/`PDE` include options are dead; descriptions contradict behavior
- **Category:** correctness / field descriptions
- **Location:** `models/boltz/schema.py:53-57,795-809`; `models/boltz/app.py:639-662,941-958`
- **Detail:** In `_process_results`, `pae`, `pde`, `plddt` are hard-set to `None` and the extraction
  code is commented out (app.py:946-958); `BoltzIncludeParams.PLDDT` is never handled in
  `_add_optional_parameters` (app.py:639-662). So those three response fields are *always* `None`
  and the `plddt`/`pde` include options are no-ops (requesting `pde` even runs `--write_full_pde`,
  writes the file, then never reads it). Yet the schema advertises them as returned — e.g. the `pde`
  field says *"present when `include=["pde"]` is set"* (schema.py:803-809) which is never true, and
  `plddt` is described as a returned per-residue score (schema.py:795-798). The README/MODEL.md
  *prose* honestly explains the arrays aren't returned, but the machine-readable schema does not.
- **Fix:** Remove the dead `pae`/`pde`/`plddt` response fields and the `PLDDT`/`PDE` enum members
  (PAE info is already surfaced via `pair_chains_ipae`/`pair_chains_ipsae`), or implement them. At
  minimum, correct the field descriptions to state they are not returned.

### 5. Docs contradict the schema on automatic MSA / `msa_search` undocumented
- **Category:** documentation gap / consistency
- **Location:** `models/boltz/MODEL.md:114`; `models/boltz/README.md:431` vs `models/boltz/schema.py:123-130`
- **Detail:** MODEL.md states "No automatic MSA generation — MSAs must be pre-computed or omitted"
  and README lists "Automatic MSA generation" under CANNOT, while the schema exposes a working-looking
  `msa_search` param. The README request-parameter table (README.md:49-60) never documents
  `msa_search` at all. Net: a public field that the docs say doesn't exist.
- **Fix:** Removing the feature per finding #1 makes the docs correct. (If the feature is kept, it
  must be documented and the "no automatic MSA" claims removed.)

### 6. LICENSE has a placeholder copyright holder and an unresolved "reviewer must verify" note
- **Category:** licensing / DoD
- **Location:** `models/boltz/LICENSE:3,23-28`
- **Detail:** Copyright reads "Copyright (c) 2024 Boltz Contributors" — a generic placeholder; the
  upstream Boltz `LICENSE` attributes specific holders (Jeremy Wohlwend et al.). The file also ships
  a footer: "Copyright holder and year (2024) inferred … Reviewer should verify against the upstream
  LICENSE file before public release." Rubric A8 requires the per-model LICENSE be accurate and any
  inferred holder/year resolved, not shipped with a self-flagged TODO. (Compare esm2's LICENSE,
  which carries the correct "Meta Platforms, Inc." holder and a clean attribution footer.)
- **Fix:** Copy the exact copyright line from the upstream `jwohlwend/boltz` LICENSE and delete the
  "reviewer should verify" note block.

### 7. `MODEL.md` ships TODO placeholders and an internal-benchmark reference
- **Category:** knowledge-graph completeness / internal phrasing
- **Location:** `models/boltz/MODEL.md:26,77`
- **Detail:** Two HTML-comment TODOs ship: `<!-- TODO: Extract exact layer count and total parameter
  count … -->` (line 26) and `<!-- TODO: Add BioLM internal benchmark results once systematic
  verification is completed -->` (line 77). Rubric A9 forbids stray TODO/template residue in shipped
  knowledge-graph files; the second also references internal benchmarking work.
- **Fix:** Resolve or remove the TODOs (either fill in the layer/param counts from the papers or drop
  the placeholder; drop the internal-benchmark TODO).

---

## 🟡 Nits

### 8. Dead code: `BoltzChainScores`
- **Location:** `models/boltz/schema.py:647-655`
- **Detail:** `BoltzChainScores` is defined but never imported or referenced anywhere; its fields
  (`ptm`, `pair_chains_iptm`) duplicate fields already in `BoltzConfidenceScores`.
- **Fix:** Delete it.

### 9. `sources.yaml` source repo not pinned
- **Location:** `models/boltz/sources.yaml:53-58` (and `md_r2: pending` at lines 68,76,84,93,102,111)
- **Detail:** `source_repos[0]` has `commit: ''` and `snapshot_r2: pending`. esm2 pins both
  (`commit: 2b369911…`, real `snapshot_r2`). `pending` md_r2 in applied_literature appears to match
  house style (esm2 also has it), so the main gap is the unpinned primary repo snapshot/commit.
- **Fix:** Pin the boltz upstream commit and populate `snapshot_r2`.

### 10. `comparison.yaml` references the excluded `af2_nim`
- **Location:** `models/boltz/comparison.yaml:54-56`
- **Detail:** `alternatives` lists `model: af2_nim`, which is excluded from the OSS repo (NIM). Other
  referenced slugs (`chai1`, `rf3`, `esmfold`, `mpnn`, `esm2`, `rfd3`, `thermompnn`) all exist. This
  is a dead cross-reference in the knowledge graph.
- **Fix:** Drop the `af2_nim` alternative or replace it with an included model.

### 11. `download.py` docstring inaccurately says "without fallback mechanisms"
- **Location:** `models/boltz/download.py:51-53`
- **Detail:** The docstring claims the standard R2 pattern "for models that only need R2 storage
  without fallback mechanisms," but the function uses `r2_then_urls`, which *does* fall back to the
  HuggingFace `boltz-community` URLs on an R2 miss (and caches back to R2).
- **Fix:** Correct the docstring to describe the R2-then-URLs fallback.

### 12. README documents the action as `predict`, but the action is `fold` (repo-wide)
- **Location:** `models/boltz/README.md:43`
- **Detail:** Config registers `ModelActions.FOLD` and the endpoint method is `fold`, but the README
  heading is `### predict`. NOTE: this is **not boltz-specific** — chai1 (`README.md:56`) and esmfold
  (`README.md:57`) do the same, so boltz is consistent with its siblings. Best handled as a global
  fix across all fold models rather than as a boltz blocker.
- **Fix:** Rename the action heading to `### fold` across the fold-model READMEs (global).

---

## Definition-of-Done notes
- Per-model LICENSE present but inaccurate/self-flagged (finding #6) — DoD not fully met.
- 5-file knowledge graph present; internally consistent on slug/display_name (`boltz` / `Boltz`), but
  has TODO residue (#7), a dead cross-ref (#10), and an unpinned source snapshot (#9).
- No `print` (T20 clean), structured `get_logger` used throughout, typed `UserError` for caller
  mistakes — these DoD items are met.
- Tests: `TestSuite` with integration + deployment cases; `test_unit.py` covers ipSAE math with no
  network/R2 at module scope (good). Internal bucket leak in test/fixture files (#2) is the gating
  test-layer issue.

---

## Verification

Adversarial re-check of the seven HIGH-severity findings against the actual files. Each was
re-read and an attempt made to refute it; all seven are concretely demonstrable, none refuted.

1. **`msa_search` depends on excluded `msa_search_nim` — REAL.** `models/msa_search_nim/` does not
   exist and is explicitly EXCLUDED (`.planning/02_MODEL_INCLUSION_MATRIX.md:52`,
   `.planning/00_MASTER_PLAN.md:158`); schema.py:37-49,123-130 exposes the param, and app.py:130-133/140
   plus the lazy `from models.msa_search_nim.schema import ...` (app.py:262,307) ship an internal-NIM
   reference the rubric (`RUBRIC.md:9,59`) lists as a 🔴 must-fix leak. Caveat: the runtime path is
   wrapped in try/except (`_generate_msa_for_entities`, app.py:215-251) and degrades to empty MSA
   rather than hard-crashing, so "fails at runtime (ModuleNotFoundError)" slightly overstates — but the
   field is non-functional and the closed-NIM reference leak is real.

2. **`biolm-modal` in shipped test files — REAL.** Literal `r2://biolm-modal/...` confirmed at
   fixture.py:16 and test.py:112,138; rubric lists `biolm-modal` as a 🔴 internal-reference leak.

3. **boltz1 advertises Boltz2 schema — REAL.** config.py:58-64 statically registers
   `BoltzPredictRequest` (=`Boltz2PredictRequest`, schema.py:640) for BOTH variants, while runtime
   fold() validates `BoltzPredictRequestType` (=`Boltz1PredictRequest` for boltz1, app.py:67-70,444)
   under `extra="forbid"` (commons/model/pydantic.py:30,50). The static `action_schemas` contract is
   consumed by `tooling/check_schema_docs.py:64-65` and catalog/docs, so it diverges from the
   per-variant runtime type. (Nuance: the runtime `_return_payload_schema` path in decorator.py:85,96
   does return the correct per-variant schema; the mismatch is in the static config-level registration.)

4. **pae/pde/plddt fields + PLDDT/PDE includes dead — REAL.** _process_results hard-sets pae/pde/plddt
   to None with extraction commented out (app.py:941-958); `_add_optional_parameters` handles
   PAE/PDE/EMBEDDINGS but never PLDDT (app.py:639-662); PDE include runs `--write_full_pde`
   (app.py:650-652) yet the file is never read. Schema still advertises pde as "present when
   include=[\"pde\"] is set" (schema.py:803-809, never true) and plddt as a returned score
   (schema.py:795-798). README (line 449) / MODEL.md prose are honest; the machine-readable schema is not.

5. **Docs deny automatic MSA while schema exposes `msa_search` — REAL.** MODEL.md:114 and README:431
   list automatic MSA under CANNOT, but schema.py:123-130 exposes a working-looking `msa_search` param
   that is absent from the README parameter table (README.md:49-60). Same root cause as #1.

6. **LICENSE placeholder holder + unresolved reviewer note — REAL.** LICENSE:3 reads "Copyright (c)
   2024 Boltz Contributors"; the actual upstream jwohlwend/boltz LICENSE reads "Copyright (c) 2024
   Jeremy Wohlwend, Gabriele Corso, Saro Passaro" (verified against the upstream raw LICENSE), so the
   holder is inaccurate and MIT attribution is not honored. The footer (LICENSE:26-28) "Reviewer should
   verify ... before public release" is an unresolved pre-launch TODO. (Note: RUBRIC A8 permits a
   *flagged* inferred holder/year, but here the holder is actually wrong, not merely flagged.)

7. **MODEL.md TODO placeholders incl. internal-benchmark ref — REAL.** Two HTML-comment TODOs ship:
   MODEL.md:26 (layer/param count) and MODEL.md:77 ("Add BioLM internal benchmark results once
   systematic verification is completed"); RUBRIC A9 (`RUBRIC.md:43`) forbids stray TODO/template
   residue in shipped knowledge-graph files, and line 77 also leaks internal benchmarking work.
