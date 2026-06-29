# Review — `models/immunebuilder/`

**Reviewer:** independent round-1 (rubric A–D)
**Verdict:** No launch-blocking (🔴) defects unique to this model. Plumbing conforms to the house
pattern: correct `fold` action, canonical `heavy_chain`/`light_chain`/`tcr_alpha`/`tcr_beta` field
names (identical to `immunefold`, with `H/L/A/B` aliases), nanobody = lone `heavy_chain` + NANOBODY
tag (no `vhh`), `results` batch wrapper, `pdb` output, BSD-3-Clause `LICENSE` consistent with
`sources.yaml`, R2-then-Zenodo acquisition that self-populates correctly. The issues below are
should-fix doc/code-quality items plus one systemic (repo-wide) leak.

I verified the one thing that *looked* like a real acquisition bug — the `download.py` key
`tcr2_model_N → file tcr_model_N` for `tcrbuilder2` — against the upstream source. It is **correct**:
`TCRBuilder2(use_TCRBuilder2_PLUS_weights=False)` reads on-disk files named `tcr2_model_N`, and
`=True` (used for `tcrbuilder2plus`) reads `tcr_model_N`. The download map matches both. No finding.

Schema descriptions all render in `model_json_schema()` (verified), and `RequestModel`'s
`strict=True, extra="forbid"` is correctly inherited despite the `populate_by_name=True` override
(verified). Field descriptions are accurate and contain no leaked sequences/secrets.

---

## 🟠 should-fix

### 1. Docs claim a 1 Å RMSD verification threshold; the test uses 1.5 Å
- **Category:** docs / correctness (rubric B, C)
- **Location:** `README.md:151,157-160`; `MODEL.md:81-84`; vs `test.py:21`
- **Detail:** README "Verification Method" says *"PDB RMSD threshold of 1 Angstrom"* and the
  verification tables in both README and MODEL.md state *"PDB RMSD < 1A"* for all four variants.
  The actual test config is `tolerances={"rel_tol": 1e-4, "pdb_rmsd_threshold": 1.5}`, with an
  inline comment explaining 1.5 Å is needed for platform/CUDA/OpenMM numeric drift. The shipped
  docs misstate the real acceptance criterion.
- **Fix:** Change the docs to `PDB RMSD < 1.5 Å` (three places) to match `test.py`, or reconcile to
  whatever threshold is actually enforced.

### 2. Shipping `TODO` placeholders in knowledge-graph and schema
- **Category:** knowledge graph / code hygiene (rubric A.9)
- **Location:** `schema.py:58`; `BIOLOGY.md:57`
- **Detail:** `schema.py:58` ships `# TODO: check if extended or unambiguous should be validated`
  on the `heavy_chain` validator — this is an unresolved correctness question about the input
  contract, not just a style note. `BIOLOGY.md:57` ships `<!-- TODO: Add specific applied
  literature citations as they become available -->`. Rubric A.9 explicitly forbids stray
  `TODO`/placeholder residue in shipped files.
- **Fix:** Resolve the validator question and delete the comment (extended is a reasonable choice —
  just commit to it). Remove the BIOLOGY.md TODO; the applied-literature citations already live in
  `sources.yaml`, so either inline them or drop the comment.

### 3. Internal "qa" environment named in shipped `app.py`
- **Category:** internal leakage (rubric C / 🔴-list item)
- **Location:** `app.py:394` (`# Force deploy to "qa" or "main" environment:`)
- **Detail:** The `__main__` usage docstring references the internal `qa` deploy environment, which
  the rubric lists as an internal-reference leak. **Systemic, not model-specific:** the identical
  comment ships in the reference model `esm2/app.py:484` and ~30 model `app.py` files. Flagging here
  for completeness; the real fix is a repo-wide sweep (owned by the commons/global reviewer), and
  ImmuneBuilder is not a deviation from the house pattern.
- **Fix:** Repo-wide: drop the `qa`/`main` environment hint from the `__main__` docstrings (or
  genericize to "your configured Modal environment") before going public.

### 4. `prebuild_immunebuilder_models()` is verbose and duplicates the load-dispatch logic
- **Category:** simplicity / duplication (rubric B)
- **Location:** `app.py:42-111` (prebuild) vs `app.py:160-203` (`_load_model_by_type`)
- **Detail:** The build-time prebuild function is ~70 lines that are mostly logging plus an
  if/elif model-type dispatch that is a near-copy of `_load_model_by_type`'s dispatch. The
  download layer (`setup_download_layer` → `download_model_assets`) already fetches+caches weights
  into the same `get_model_dir()` path before prebuild runs, so the prebuild's stated purpose
  ("pre-download … to avoid download during snapshot") is partly redundant — its real value is
  warm-instantiation. Compared with the lean `esm2/app.py` setup, this is a maintainability outlier
  and a place where the per-variant constructor mapping should be factored into one helper.
- **Fix:** Extract the `model_type → constructor` mapping into a single shared function used by both
  prebuild and `_load_model_by_type`; trim the per-step `logger.info` timing noise.

---

## 🟡 nits

### 5. f-string logging deviates from the house lazy/%-style convention
- **Category:** consistency / logging (rubric A.6, W6)
- **Location:** `app.py:58,93,95,202,215,253,274,275` (8 `logger.*(f"...")` calls)
- **Detail:** Not a ruff violation (flake8-logging-format `G` is not in the `select` list), but the
  reference `esm2/app.py` uses 0 f-string logs (all `%`-style lazy interpolation), and the file
  itself mixes both styles. W6's structured-logging intent favors lazy `%` args.
- **Fix:** Convert the eight f-string log calls to `%`-style for consistency.

### 6. Misleading dead code in the `setup_model` exception handler
- **Category:** readability / dead code (rubric B)
- **Location:** `app.py:255-265`
- **Detail:** The handler logs *"Attempting to resolve by allowing ImmuneBuilder to download
  models…"* and then does **not** retry — it immediately logs the same error a second time and
  `raise e`. The "attempting to resolve" message is misleading and the error is double-logged.
- **Fix:** Drop the misleading message and the duplicate `logger.error`; keep a single
  `logger.error(..., exc_info=True)` then `raise`.

### 7. R2-cache detection glob double-nests the variant (wrong log label)
- **Category:** correctness (cosmetic) (rubric B)
- **Location:** `app.py:177` (`weights_dir.glob(f"{self.model_type}/*")`)
- **Detail:** `get_model_dir()` already returns the variant-scoped dir (`…/immunebuilder/v1/
  tcrbuilder2/`), so globbing `f"{self.model_type}/*"` looks for `…/tcrbuilder2/tcrbuilder2/*`,
  which never matches. The `source = "R2 cache" | "library remote"` label is therefore always
  wrong. Purely a log artifact — actual loading passes `weights_dir=model_dir` and works — but it
  makes the R2-vs-remote diagnostics untrustworthy.
- **Fix:** Use `any(weights_dir.iterdir())` (as `setup_model` already does at line 242) instead of
  the nested glob.

### 8. `seed_everything` docstring is misplaced; request-time `PYTHONHASHSEED` is a no-op
- **Category:** readability / correctness-lite (rubric B)
- **Location:** `app.py:356-382`
- **Detail:** The `"""…"""` block sits *after* the `import numpy`/`import torch` statements
  (lines 361-366), so it is a no-op string expression, not the function docstring. Setting
  `os.environ["PYTHONHASHSEED"]` per request (line 382) has no effect — it only matters before
  interpreter start. `self.torch` is assigned in `setup_model` (line 224) but never read (the
  method re-imports torch locally). Minor leftover: commented `# var_is_required=True` at
  `app.py:37`.
- **Fix:** Move the docstring to the first statement; drop the ineffective `PYTHONHASHSEED` line or
  document it as best-effort; remove the unused `self.torch` and the commented scaffolding line.

### 9. `params` uses a shared mutable default instead of `default_factory`
- **Category:** consistency (rubric A/B)
- **Location:** `schema.py:154-156` (`default=ImmuneBuilderPredictParams()`)
- **Detail:** The house pattern (`esm2/schema.py`) uses `default_factory=...`. Pydantic v2 copies
  the model default per-instance (verified: the two requests get distinct `params` objects), so
  there is no leak today — but the shared-instance default is a known anti-pattern and diverges
  from sibling models.
- **Fix:** `params: Optional[ImmuneBuilderPredictParams] = Field(default_factory=ImmuneBuilderPredictParams, …)`.

### 10. Knowledge-graph references models not present in the repo
- **Category:** docs / consistency (rubric C)
- **Location:** `comparison.yaml:52-63` (`propermab`, `nanobert`); also `MODEL.md`/`README.md`
- **Detail:** `complements:` lists `propermab` and `nanobert` with platform workflow phrasing
  ("ProperMAB's default internal pipeline", "use NanoBERT to score…"), but neither slug exists under
  `models/`. To an outside contributor these read as available platform integrations that aren't
  there.
- **Fix:** Confirm these are intended (real external tools or planned ports) and phrase them as
  external references, or remove until the slugs ship.

### 11. Input-driven ANARCI/predict failures surface as 500, not 400
- **Category:** error taxonomy (rubric A.5)
- **Location:** `app.py:350-352`
- **Detail:** `self.model.predict(...)` raises on sequences that pass the AA-extended validator but
  fail ANARCI numbering (a documented failure mode — `MODEL.md:116`). The blanket
  `except Exception: … raise e` propagates these as ServerError/500 even though they are caller
  input mistakes that rubric A.5 wants as `UserError`/400. Hard to classify reliably and consistent
  with `immunefold`, hence a nit — but worth a targeted catch.
- **Fix:** Catch the known ANARCI/numbering failure and re-raise as `ValidationError400` with a
  clear message; let genuine faults propagate.

---

## Definition-of-Done audit (selected)
- **Layout / 5-file KG:** all standard files + `sources/comparison/README/MODEL/BIOLOGY` present. ✅
- **Actions:** single `fold` (correct verb for structure prediction). ✅
- **Schema field names:** canonical, uniform with `immunefold`; nanobody = lone `heavy_chain`, no
  `vhh`; aliases preserved. ✅
- **Field descriptions render:** verified via `model_json_schema()`. ✅
- **Errors:** typed `ValidationError400` used for routing mismatch; gap on ANARCI input errors (nit
  #11). ◑
- **Logging:** `get_logger`, no `print`; f-string style inconsistency (nit #5). ◑
- **Acquisition:** canonical `r2_then_urls`, self-populates R2; filename mapping verified correct;
  no build-order issue (URL fallback imports no library). ✅
- **Licensing:** BSD-3-Clause `LICENSE` + attribution, consistent with `sources.yaml`. ✅
- **Knowledge graph:** accurate & internally consistent (slug/display_name match config); residual
  `TODO` (finding #2) and out-of-repo refs (#10). ◑
- **Tests:** `TestSuite` with integration + deployment cases, fixtures lazy (no module-scope R2).
  `fixture.py` has no `generate()` (manual fixtures) — common for fold models (immunefold, esmfold,
  abodybuilder3 do the same), so not flagged. ✅
- **Docs accuracy:** RMSD threshold mismatch (finding #1). ◑

---

## Verification

Adversarial re-check of the four HIGH-severity findings against the actual files.

- **Finding 1 (1 Å docs vs 1.5 Å test) — REAL.** Confirmed: `README.md:151` states "PDB RMSD threshold of 1 Angstrom" and tables `README.md:157-160` / `MODEL.md:81-84` list "PDB RMSD < 1A" for all four variants, while `test.py:21` sets `pdb_rmsd_threshold: 1.5` (comment at `test.py:20` justifies 1.5 Å for platform/CUDA/OpenMM drift). Docs misstate the enforced criterion.
- **Finding 2 (shipped TODO placeholders) — REAL.** Confirmed literal text: `schema.py:58` ships `# TODO: check if extended or unambiguous should be validated` on the `heavy_chain` validator, and `BIOLOGY.md:57` ships `<!-- TODO: Add specific applied literature citations as they become available -->`. Both are unresolved placeholders in shipped files.
- **Finding 3 ('qa' env in __main__ docstring) — REAL.** Confirmed `app.py:394` contains `# Force deploy to "qa" or "main" environment:`. Verified systemic per the finding's own caveat: `grep` shows the identical comment in 30 model `app.py` files including the reference `esm2/app.py:484`, so it is the house pattern, not an ImmuneBuilder deviation. Text is present; severity is mitigated by being repo-wide.
- **Finding 4 (verbose prebuild duplicates load-dispatch) — REAL.** Confirmed: `prebuild_immunebuilder_models()` spans `app.py:42-111` (~70 lines, mostly logging) with an if/elif model-type dispatch at `app.py:69-88` that mirrors `_load_model_by_type`'s dispatch at `app.py:188-199`. Redundancy claim also holds: `setup_download_layer` (`commons/modal/downloader.py:35`, step 6 `run_function(_run_download_with_params)`) already fetches+caches weights into `get_model_dir()` at `app.py:117` before prebuild runs at `app.py:136`, so prebuild's real value is warm-instantiation. Demonstrable, but a soft maintainability nit and the dispatch duplication is partly structural (build-time standalone function cannot call the instance method `_load_model_by_type`).
