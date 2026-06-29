# Review Round-1 — `models/deepviscosity/`

**Reviewer:** independent launch-gating review
**Verdict:** Solid, well-documented single-variant CPU model that broadly conforms to the house pattern
(canonical `predict` action, `heavy_chain`/`light_chain`/`items`/`params` field names, typed schema with
rendering field descriptions — `tooling/check_schema_docs.py` passes, unit tests pass 7/7). The science is
clear and the knowledge graph is rich and internally consistent (slug/display_name match config everywhere).

The launch blocker is a single internal-reference leak (`biolm-modal`) in `fixture.py`. Beyond that the main
should-fixes are about *plumbing uniformity*: the acquisition layer is hand-rolled (~180 lines) instead of the
commons `r2_then_archive` wrapper that was written explicitly to replace it, and runtime errors for predictable
bad input (a non-antibody sequence) escape as HTTP 500 with raw subprocess stderr instead of a typed
`UserError`. Several findings are systemic across the repo (noted as such for orchestrator de-dup).

---

## 🔴 Must-fix before launch

### 1. Internal-reference leak: `biolm-modal` bucket name in a shipped file
- **Category:** No internal leakage (Rubric C / A)
- **Location:** `models/deepviscosity/fixture.py:18`
- **Detail:** The comment reads
  `# Test input/output filenames (stored in R2 at r2://biolm-modal/test-data/deepviscosity/)`.
  `biolm-modal` is the internal repo/bucket name the rubric explicitly lists as a 🔴 leak in shipped files.
  It is doubly wrong: `test.py`/`fixture.py` actually use `r2_fixture_subdir="models"`, so the documented
  path (`test-data/...`) is also stale and contradicts the real storage layout. (Systemic: `boltz/fixture.py`,
  `boltz/test.py`, `esmstabp/download.py`, `dummy/sources.yaml`, `commons/storage/cache.py` carry the same
  string — recommend a repo-wide grep sweep before launch.)
- **Fix:** Remove the `r2://biolm-modal/...` reference; if a location hint is wanted, describe it generically
  (e.g. "stored in the model test-data bucket under `models/deepviscosity/`") without the internal bucket name.

---

## 🟠 Should-fix

### 2. Acquisition is hand-rolled instead of the canonical `r2_then_archive` wrapper
- **Category:** Acquisition / convention uniformity (Rubric A.7, B-modularity)
- **Location:** `models/deepviscosity/download.py` (243 lines; esp. `_find_repo_prefix`, `_extract_single_directory`,
  `_download_deepviscosity_archive`, `_extract_deepviscosity_files`, `_create_custom_fallback_config`)
- **Detail:** This file re-implements, by hand, exactly the "download GitHub zip → strip repo root → extract
  subtrees → cache to R2" flow. The commons helper `r2_then_archive` (`models/commons/storage/download_helpers.py:574`)
  already does all of this, and its own docstring names the offenders:
  *"This replaces the hand-rolled 'download zip → unzip subtree' logic that several models
  (tempro/**deepviscosity**/temberture/clean) carry inline."* `_find_repo_prefix` duplicates
  `detect_archive_root_prefix`; `_extract_single_directory` duplicates `extract_archive_subtree`;
  the zip fetch duplicates `download_archive`. This is the repo's north-star inversion — the plumbing differs
  from the other models for no scientific reason. (esm2's `download.py` is 87 lines using `r2_then_library`.)
- **Fix:** Replace the body of `download_model_assets` with a single `r2_then_archive(...)` call:
  `archive_url=DEEPVISCOSITY_ZIP_URL`,
  `extract_subtrees={"DeepViscosity_ANN_ensemble_models/": "DeepViscosity_ANN_ensemble_models",
  "DeepSP_CNN_model/": "DeepSP_CNN_model"}`,
  `required_files=[...]` for post-extract validation. Delete the bespoke helpers. Keep the `PINNED_COMMIT`
  constant and the "scaler embedded, not downloaded" note.

### 3. Predictable bad input raises `RuntimeError`/`ValueError` → HTTP 500 + raw stderr (not a typed `UserError`)
- **Category:** Errors (Rubric A.5)
- **Location:** `models/deepviscosity/util.py:261-268` (ANARCI heavy fail), `:290-293` (light fail),
  `:299-310` (missing/empty CSV), `:377-380` (`one_hot_encode` length mismatch); surfaced via
  `models/deepviscosity/app.py` `predict`.
- **Detail:** The docs explicitly warn the model "will fail on non-antibody proteins" — a *predictable user
  mistake*. But a valid-amino-acid yet non-antibody sequence passes the Pydantic `validate_aa_unambiguous`
  gate and then fails inside ANARCI, raising bare `RuntimeError`. `RuntimeError`/`ValueError` are **not** in
  the decorator's `ERROR_MAP` (`models/commons/core/decorator.py:417-430`), so they fall through to the
  generic handler and return `status_code=500, detail="Uncaught exception: ANARCI heavy chain alignment
  failed: <e.stderr.decode()>"`. That is (a) the wrong contract — a caller mistake should be 4xx, not 5xx —
  and (b) a minor info leak (raw subprocess stderr, incl. temp paths, is echoed to the API caller).
- **Fix:** Raise `ValidationError400`/`UserError` (from `models.commons.core.error`) for ANARCI alignment
  failures and the empty/zero-row CSV cases with a clean message
  (e.g. "Could not IMGT-align the heavy chain; ensure it is an antibody variable-region (Fv) sequence."),
  without echoing raw stderr. Reserve `ServerError`/`ModelExecutionError` for genuine internal invariants —
  e.g. the DeepSP feature-count mismatch (`app.py:214`) and `one_hot_encode` length mismatch, which are
  server-side bugs, not caller input.

### 4. README verification command targets a test class that isn't in `test.py`
- **Category:** Docs accuracy (Rubric C)
- **Location:** `models/deepviscosity/README.md:190`
- **Detail:** `uv run pytest models/deepviscosity/test.py::TestDeepViscositySchemaValidation -v`. That class
  lives in `test_unit.py` (`test_unit.py:18`); `test.py:76` even notes it was moved there. The documented
  command collects nothing and fails — a broken example for an outside contributor.
- **Fix:** Point the command at `models/deepviscosity/test_unit.py::TestDeepViscositySchemaValidation`.

### 5. `sources.yaml` records an empty commit while the code pins a real one
- **Category:** Knowledge graph accuracy/consistency (Rubric A.9)
- **Location:** `models/deepviscosity/sources.yaml:30` (`commit: ''`) vs `download.py:20`
  (`PINNED_COMMIT = "2d22a5bfd3905ca508fe675fd212d2d431876517"`)
- **Detail:** The source-of-truth metadata says the upstream commit is unknown, but `download.py` pins it
  exactly. For a reproducibility-focused catalog these must agree. (Related, systemic: `snapshot_r2: pending`,
  `md_r2: pending`, and multiple `pdf_r2: pending` placeholders ship in this file — see nit #8.)
- **Fix:** Set `source_repos[0].commit` to `2d22a5bfd3905ca508fe675fd212d2d431876517`.

---

## 🟡 Nits / polish

### 6. Output schema encodes one decision three ways; `viscosity_class` is a free `str`
- **Category:** Schema simplicity (Rubric B)
- **Location:** `models/deepviscosity/schema.py:111-129`
- **Detail:** `viscosity_class` ("low"/"high"), `is_high_viscosity` (bool), and `probability_mean` (≥0.5) all
  encode the same thresholded decision; the README documents all three. `viscosity_class` is typed as bare
  `str`, so the closed value set isn't expressed in the schema.
- **Fix:** Type it as `Literal["low", "high"]` (or an `EnhancedStringEnum`, matching esm2's option enums).
  Consider dropping `is_high_viscosity` as derivable, or keep it but note the redundancy is intentional.

### 7. `comparison.yaml` lists non-catalog models as first-class `model:` refs
- **Category:** Knowledge-graph consistency (Rubric A.9 / C)
- **Location:** `models/deepviscosity/comparison.yaml:38,41,49,55` (`camsol`, `soluprot`, `biolmtox2`)
- **Detail:** `alternatives`/`complements` reference `model: camsol`, `model: soluprot`, `model: biolmtox2`,
  none of which exist under `models/`. The prose (README/MODEL/BIOLOGY) even calls CamSol/SoluProt
  "not on BioLM", so the YAML contradicts the prose. **Systemic** — esm2's `comparison.yaml` likewise refs
  `biolmtox2`/`saprot`/`poet` which aren't ported — so this is a catalog-wide forward-reference policy
  question, not deepviscosity-specific. Flagging for the global reviewer; the local nit is the prose/YAML
  mismatch (camsol simultaneously "not on BioLM" and an `alternatives` entry).
- **Fix:** Either gate cross-refs to shipped slugs, or adopt a convention for "planned/external" refs and apply
  it uniformly; at minimum reconcile the camsol/soluprot "not on BioLM" prose with their YAML listing.

### 8. Shipping `TODO`/`PENDING` verification residue
- **Category:** Knowledge-graph completeness / DoD (Rubric A.9 / D)
- **Location:** `models/deepviscosity/MODEL.md:114` (`<!-- TODO: Run full Lai_mAb_16 validation ... -->`),
  `MODEL.md:106-113` ("Pending" rows), `README.md:199-201` ("PARTIALLY VERIFIED ... pending deployment")
- **Detail:** Honest, but a TODO comment and "pending" verification tables ship publicly. **Systemic** —
  many models' MODEL.md carry TODOs and `pending` knowledge-graph fields. The DoD "implementation verified
  against published values" is only *partially* met here (numerical Lai_mAb_16 check deferred to deployment).
- **Fix:** Complete the Lai_mAb_16 numerical verification during Milestone-A/B deploys and replace the TODO
  and "Pending"/"PARTIALLY VERIFIED" rows with actual numbers; or strip the internal TODO comment.

### 9. 126-line embedded `StandardScaler` literal needs manual re-extraction on weight bumps
- **Category:** Maintainability (Rubric B)
- **Location:** `models/deepviscosity/util.py:27-126` (`SCALER_PARAMS`)
- **Detail:** Embedding `mean_/var_/scale_` to dodge sklearn-version pickle drift is a reasonable, documented
  choice, but it silently couples a derived artifact to `PINNED_COMMIT`: bumping the commit (retrain) requires
  hand re-extracting these arrays, with no automated check that they still match upstream.
- **Fix:** Add a short note in `download.py`/`util.py` (near `PINNED_COMMIT`) cross-linking the two, or a tiny
  offline regeneration script, so the coupling is enforceable rather than tribal knowledge.

### 10. Minor runtime/style polish
- **Category:** Simplicity (Rubric B)
- **Location:** `models/deepviscosity/app.py:140-143`, `:237`
- **Detail:** (a) Ensemble models are `model.compile(optimizer=Adam(...), metrics=["accuracy"])` though the
  container only ever calls `.predict()` — the optimizer/metrics are dead work for an inference-only path.
  (b) `# Force deploy to QA or main:` references the internal `qa` env; **systemic and present in the
  reference model** (`esm2/app.py:484` has the identical comment), so this is a commons/global cleanup, not a
  deepviscosity-specific defect — noted only so it isn't missed in the global sweep.
- **Fix:** Drop the optimizer from the ensemble compile (or skip compile entirely for inference); handle the
  "qa" comment globally with esm2/dummy.

---

## Definition-of-Done audit (Section D)
- **Layout / standard files:** MET — all of `app.py/config.py/schema.py/test.py/download.py` + 5-file knowledge
  graph + `LICENSE` + `fixture.py` + `test_unit.py` present; `config.py` defines a proper `ModelFamily`.
- **Canonical action:** MET — single `predict` (a classifier; no invented verb).
- **Schema field names + rendering descriptions:** MET — `heavy_chain`/`light_chain`/`items`/`params`,
  results under `results`; `tooling/check_schema_docs.py` passes (44 models incl. this one).
- **Errors:** PARTIALLY MET — typed taxonomy not used for ANARCI/preprocess failures (finding #3).
- **Logging:** MET — `get_logger`, no `print`, no full-sequence logging.
- **Acquisition (self-populating, canonical wrapper):** PARTIALLY MET — self-populates R2
  (`enable_r2_cache=True`) but via a hand-rolled CUSTOM strategy instead of `r2_then_archive` (finding #2).
- **Licensing:** MET — per-model MIT `LICENSE` consistent with `sources.yaml`; holder/year plausible
  (first author / paper year).
- **Knowledge graph:** PARTIALLY MET — internally consistent and rich, but ships `pending`/TODO residue and an
  empty `commit` (findings #5, #8) and non-catalog cross-refs (#7).
- **Tests:** MET — `TestSuite` with 3 integration+deployment cases (single/batch/with-features); fixtures are
  string filenames (lazy, no module-scope R2/network); unit tests pass 7/7. (Numerical verification against
  published Lai_mAb_16 still deferred — see #8.)
- **No internal leakage:** NOT MET — `biolm-modal` in `fixture.py` (finding #1).

## Verification

Adversarial re-check of the five HIGH-severity findings (verdict + concrete evidence):

1. **Internal-reference leak `biolm-modal` in shipped file — REAL.** `fixture.py:18` literally reads
   `# ...stored in R2 at r2://biolm-modal/test-data/deepviscosity/`; `biolm-modal` is the internal repo/bucket
   name (per bootstrap CLAUDE.md). Doubly wrong: `fixture.py:43` and `test.py:23` set `r2_fixture_subdir="models"`,
   so the documented `test-data/...` path is also stale.

2. **Hand-rolled acquisition instead of canonical `r2_then_archive` — REAL.** `download.py` (243 lines) reimplements
   the zip→strip-root→extract-subtree→cache flow via `_find_repo_prefix` (download.py:73), `_extract_single_directory`
   (download.py:85), `_extract_deepviscosity_files` (download.py:127). The commons wrapper `r2_then_archive`
   (download_helpers.py:574) does exactly this and its docstring (download_helpers.py:595-596) names
   "tempro/deepviscosity/temberture/clean" verbatim as the offenders to replace.

3. **Predictable bad input → HTTP 500 + raw stderr leak — REAL.** README:40,51 warn the model "will fail on
   non-antibody proteins"; a valid-AA non-antibody passes `validate_aa_unambiguous` (schema.py:71,81), reaches
   `align_and_encode` (app.py:174, unguarded), and ANARCI raises bare `RuntimeError(... {e.stderr.decode()})`
   (util.py:262-264,291-293). `RuntimeError`/`ValueError` are absent from `ERROR_MAP` (decorator.py:417-430), so
   it falls through to decorator.py:455-456 → `status_code=500`, `detail="Uncaught exception: ..."`, surfaced
   verbatim via `_error_response` `detail=str(detail_msg)` (decorator.py:517) with no redaction.

4. **README verification command targets a non-existent class — REAL.** README.md:190 runs
   `pytest models/deepviscosity/test.py::TestDeepViscositySchemaValidation`; that class lives in `test_unit.py:18`,
   and `test.py:76` itself states the unit tests "have been moved to test_unit.py". `test.py` defines no such class,
   so the documented command collects nothing.

5. **sources.yaml empty commit vs. real pinned commit in code — REAL.** `sources.yaml:30` has `commit: ''` while
   `download.py:20` pins `PINNED_COMMIT = "2d22a5bfd3905ca508fe675fd212d2d431876517"`. Metadata source-of-truth
   contradicts the code for a reproducibility-focused catalog; related `snapshot_r2: pending` (sources.yaml:31),
   `md_r2: pending` (sources.yaml:25), and several `pdf_r2: pending` placeholders also ship.

All five findings confirmed REAL against the current tree.
