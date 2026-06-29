# Review — `models/biotite/`

**Reviewer:** independent round-1 (software + ML)
**Date:** 2026-06-29
**Verdict:** Not launch-ready. One license-compliance blocker (🔴), plus a handful of
should-fix convention/correctness items. The plumbing is mostly house-shaped (uses
`ModelMixinSnap`, `biolm_model_class`, `modal_endpoint`, `setup_source_layer`, the
`TestSuite`/`FixtureGenerator` harness, typed `RequestModel`/`ResponseModel`), and the
RMSD action lines up cleanly with the closest peer `prody` (`predict` + `rmsd` field). The
issues are around the chain-extraction action's field naming, error taxonomy, dead
scaffolding, and dependency hygiene.

Biotite is a **non-ML algorithmic utility** (no weights), so there is correctly **no
`download.py` / `setup_download_layer`** — it ships only `setup_source_layer`, exactly like
`dummy`. The acquisition rubric item (A.7) is therefore N/A, not a gap.

---

## 🔴 Must-fix before launch

### 1. Shipped `LICENSE` carries an unverified, paraphrased copyright line + a "confirm before release" meta-note
- **Category:** Licensing (A.8)
- **Location:** `models/biotite/LICENSE:3` and `:38-39`
- **Detail:** The copyright line reads `Copyright (c) 2017-2024, Patrick Kunzmann and the
  biotite-dev contributors`, and the file then admits *"(The copyright holder/year above are
  inferred from the upstream repository; confirm the exact line against the Biotite LICENSE
  before public release.)"*. BSD-3-Clause condition #1 requires **retaining the upstream
  copyright notice verbatim**; a paraphrased/inferred holder line is a compliance defect, and
  shipping a self-flagged "confirm before release" note in a public LICENSE is exactly the
  kind of unfinished due-diligence this launch gate exists to catch. This review *is* the
  pre-release check.
- **Fix:** Open the upstream `LICENSE.rst`
  (https://github.com/biotite-dev/biotite/blob/main/LICENSE.rst), copy its exact copyright
  line (upstream uses "the Biotite contributors") verbatim, and delete the parenthetical
  note at `:38-39`.

---

## 🟠 Should-fix

### 2. `pdb_string` deviates from the house `pdb` input field name
- **Category:** Schema field-name uniformity (A.3)
- **Location:** `models/biotite/schema.py:34` (`BiotiteExtractChainsRequestItem.pdb_string`)
- **Detail:** Every other PDB-consuming model uses the field name `pdb` (and `cif`):
  `antifold`, `esm_if1`, `prody`, `immunefold`, `boltzgen`, plus PDB outputs in `esmfold` /
  `abodybuilder3` / `immunebuilder`. The RMSD action's `pdb_a`/`pdb_b` (schema.py:69,74)
  correctly match `prody`, but `pdb_string` is a one-off. This is precisely the "the diff
  between two models should be the science, not the plumbing" violation.
- **Fix:** Rename `pdb_string` → `pdb`; keep a Pydantic alias (`Field(..., alias="pdb_string")`
  / `validation_alias`) so existing callers don't break (the rubric's "renames keep a Pydantic
  alias" rule).

### 3. Dead/misleading error path: `if rmsd < 0` can never be true
- **Category:** Correctness / dead code (B, A.5)
- **Location:** `models/biotite/app.py:256-259`
- **Detail:** `_compute_rmsd_between_structures` either returns `float(rmsd)` (RMSD is a
  non-negative metric) or **raises** on every failure path — it never returns a negative
  sentinel. So the `if rmsd < 0: raise ModelExecutionError(...)` guard in `predict` is dead
  code left over from an older return-sentinel design. It misleads maintainers into thinking
  `-1`-style sentinels are part of the contract.
- **Fix:** Delete the `if rmsd < 0` block; just append the `BiotiteRMSDResponseResult(rmsd=rmsd)`.

### 4. `generate` reports internal failures as `400` user errors
- **Category:** Error taxonomy (A.5)
- **Location:** `models/biotite/app.py:211-213` (broad `except Exception: ... return None`)
  feeding `app.py:99-102` (raise `ValidationError400("...chains not found in PDB structure")`)
- **Detail:** `_extract_chains_from_pdb` wraps the whole body in `except Exception: return
  None`, so a genuine internal/parse fault (a biotite bug, an unexpected structure edge case)
  is funnelled to the same `None` return as the legitimate "requested chain ID absent" case
  (app.py:126-129). `generate` then raises `ValidationError400` ("chains not found"),
  mislabelling a server fault as the caller's mistake. The rubric wants caller mistakes →
  `UserError`/`ValidationError400` and system faults → propagate/`ServerError`.
- **Fix:** Narrow the handling — return `None` only for the genuine "missing/empty chains"
  case (which you already detect explicitly), and let unexpected exceptions propagate (they'll
  be sanitized to a `ServerError` by `modal_endpoint`), or re-raise them as `ModelExecutionError`.

### 5. Dependency hygiene: unused `pandas`, README/code version mismatch, unverified pins
- **Category:** Simplicity + doc/code consistency (B, C)
- **Location:** `models/biotite/app.py:32-36` vs `models/biotite/README.md:189`
- **Detail:** (a) `pandas==3.0.1` is installed in the image but **never imported** anywhere in
  the model (grep of `models/biotite/` shows zero `import pandas`/`pd.`); it's an unused
  dependency that bloats the image. (b) README's resource table claims
  `numpy>=1.21.0, pandas>=1.3.0`, contradicting the exact pins `numpy==2.4.3` /
  `pandas==3.0.1` in `app.py` and the repo's "pin exact versions" rule. (c) Those pins should
  be confirmed to exist and to be compatible with `biotite==1.3.0` (numpy 2.4 / pandas 3.0 are
  aggressive majors).
- **Fix:** Drop `pandas` from the image unless a transitive need is documented; align the
  README line to the exact pins; verify `biotite==1.3.0` resolves against the chosen
  numpy/pandas versions in a clean build.

### 6. RMSD `chain_ids` uses an untyped dict with magic `"a"`/`"b"` keys
- **Category:** Weak abstraction / cross-model inconsistency (B, C)
- **Location:** `models/biotite/schema.py:79-85` + runtime check `app.py:295-296`
- **Detail:** `chain_ids: dict[str, list[str]]` with required magic keys `"a"`/`"b"` is
  validated only at runtime (raising `ValidationError400` deep inside `_compute_rmsd...`). The
  direct structural-comparison peer `prody` uses explicit, schema-typed `chain_a` / `chain_b`
  fields (prody/schema.py:324,338), which is self-documenting and rejects bad shapes at schema
  time. The loose dict makes the OpenAPI schema unhelpful and diverges from the peer.
- **Fix:** Replace with explicit `chain_a: list[str]` / `chain_b: list[str]` fields (matching
  `prody`), or a small typed sub-model; enforce equal length with a validator instead of a
  runtime check.

---

## 🟡 Nits / polish

### 7. `generate` verb for deterministic chain extraction is a semantic stretch
- **Category:** Action naming (A.2)
- **Location:** `models/biotite/config.py:49`, `app.py:88-90`
- **Detail:** Chain extraction produces derived sequences/sub-structures, not ML-generated
  content. The team clearly knows this — MODEL.md and README each spend a paragraph justifying
  the verb. It's within the closed set and documented, so it's a judgment call, but the closest
  peer (`prody`) routes "analyse a structure → return derived data" through `encode`. Consider
  aligning to `encode`, or keep `generate` and leave the documented note. Either way, no
  invented verb — fine to leave, flagged for the global consistency pass.

### 8. Empty `*RequestParams` models + nullable `params` add dead public-API surface
- **Category:** Simplicity / scaffolding (B)
- **Location:** `models/biotite/schema.py:27-30, 62-65` (both bodies are `pass`) and the
  `params: ... | None = Field(default=None, ...)` on lines 48-51 / 89-92
- **Detail:** Both params models are empty, so the public schema exposes a `params` object that
  can only ever be `null`/`{}`. `dummy` and `esm2`'s `predict`/`log_prob` simply omit `params`
  entirely. Descriptions do render correctly (verified via `model_json_schema()`), so this is
  not an A.4 violation — just needless surface.
- **Fix:** Drop the `params` field and the empty params classes until a real parameter exists.

### 9. f-string logging + verbose PDB-content debug logging diverge from house style
- **Category:** Logging convention (A.6, C)
- **Location:** `models/biotite/app.py` — 28 `logger.<lvl>(f"...")` calls (e.g. 85, 116, 128,
  198, 274-282, 312-313)
- **Detail:** The house style (`esm2`, `dummy`, commons) uses lazy `%`-formatting
  (`logger.info("...", x)`); biotite mostly uses eager f-strings. `G` (flake8-logging-format)
  is **not** in the ruff `select` list, so CI won't catch it, but it's a uniformity deviation.
  The RMSD path also logs user PDB previews (`pdb_a[:200]`, `pdb_a[:50]`) and coordinate
  counts at debug/error level — truncated, low-risk, but noisy.
- **Fix:** Convert log calls to lazy `%` args; trim the chatty debug previews.

### 10. Empty `setup_model` enter-hook + non-standard loader name
- **Category:** Dead scaffolding / naming consistency (B)
- **Location:** `models/biotite/app.py:60-76`
- **Detail:** There are two `@modal.enter` hooks: `load_model(snap=True)` does the work and
  `setup_model(snap=False)` is an empty `pass`. The empty `snap=False` hook is dead
  scaffolding, and the house convention names the snapshot loader `setup_model`
  (`esm2`/`dummy`), so biotite both renames the loader (`load_model`) and leaves an empty
  `setup_model`. Confusing.
- **Fix:** Delete the empty `setup_model`; rename `load_model` → `setup_model` for consistency.

### 11. `BiotiteParams.max_sequence_len = 2048` is dead config
- **Category:** Dead code (B)
- **Location:** `models/biotite/schema.py:21`
- **Detail:** Biotite consumes PDB structures, not sequences; `max_sequence_len` is never
  referenced. It's copied from a sequence-model `ModelParams`. (`batch_size = 8` *is* used.)
- **Fix:** Remove the unused `max_sequence_len`.

### 12. `sources.yaml` knowledge-graph completeness gaps
- **Category:** Knowledge graph (A.9)
- **Location:** `models/biotite/sources.yaml:28` (`md_r2: "pending"`), `:34`
  (`snapshot_r2: "pending"` + `commit: ""`), `:54/:73/:91` (`pdf_r2: "pending"`)
- **Detail:** The **primary** paper's `md_r2` and the **primary** source repo's
  `snapshot_r2`/`commit` are unpopulated, unlike `esm2` whose primary entries are fully
  captured. The applied-literature `pdf_r2: pending` placeholders are a repo-wide pattern
  (43 models carry "pending"), so lower priority — but biotite's *primary*-source gaps are
  worth closing.
- **Fix:** Populate the primary paper markdown + repo snapshot/commit, or drop the empty keys.

### 13. "qa"/"main" Modal env name in the `__main__` usage docstring
- **Category:** Internal reference (C) — repo-wide, not biotite-specific
- **Location:** `models/biotite/app.py:404`
- **Detail:** `# Force deploy to "qa" or "main" environment:` names internal Modal deploy
  environments. This is inherited boilerplate present in 30 model `app.py` files (including the
  reference `esm2`) and driven by `commons/modal/deployment.py`, so it's a global-reviewer
  decision, not a biotite defect. Flagging per rubric C; fix once, centrally, if these env
  names are deemed internal.

---

## Definition-of-Done audit (per `.planning/03_WORKSTREAMS.md`)
- **Layout (A.1):** MET — all standard files + 5-file knowledge graph present; `config.py`
  defines a proper `ModelFamily`. (`fixture.py` is the house fixture generator, matching `esm2`.)
- **Actions (A.2):** PARTIAL — closed-set verbs only; `predict`→RMSD matches `prody`;
  `generate`→chain-extraction is a documented stretch (nit #7).
- **Schema field names (A.3):** PARTIAL — `pdb_string` should be `pdb` (#2); `rmsd`/`pdb_a`/
  `pdb_b`/`results`/`items` all match peers.
- **Field descriptions (A.4):** MET — verified every request/response field's description
  renders in `model_json_schema()`, including the nullable `params`.
- **Errors (A.5):** PARTIAL — uses typed `ValidationError400`/`ModelExecutionError`, but
  `generate` misclassifies internal faults as 400 (#4) and has dead error code (#3).
- **Logging (A.6):** PARTIAL — `get_logger`, no `print`; but f-string style + chatty PDB
  previews (#9).
- **Acquisition (A.7):** N/A — no weights; correctly source-layer-only (like `dummy`).
- **Licensing (A.8):** NOT MET — unverified/paraphrased copyright + self-flagged note (#1, 🔴).
- **Knowledge graph (A.9):** PARTIAL — internally consistent (slug/display_name match config),
  no TODO/internal leakage, but primary-source `pending` gaps (#12).
- **Tests (A.10):** MET (with caveat) — `TestSuite` with integration + deployment cases,
  lazy fixtures, no module-scope R2/network. PDB test inputs are hand-written minimal
  structures; there is **no shared PDB asset** in `commons/testing/shared_assets.py` yet (only
  protein-sequence constants), so hardcoding here is acceptable — but a `shared/pdb/...` asset
  would be the cleaner long-term home.

## Verification

- **LICENSE has unverified copyright + confirm-before-release note** — **REAL.** `models/biotite/LICENSE:38-39` literally ships a self-flagged "(...inferred from the upstream repository; confirm the exact line against the Biotite LICENSE before public release.)" TODO in the public LICENSE, and `:3` ("Copyright (c) 2017-2024, Patrick Kunzmann and the biotite-dev contributors") is demonstrably non-verbatim vs. the actual upstream Biotite LICENSE.rst (v1.5.0 and v1.6.0), which reads "Copyright 2017, The Biotite contributors" — so BSD-3-Clause's required verbatim notice retention is not satisfied.
