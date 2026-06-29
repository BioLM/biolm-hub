# Review — `models/spurs/` (Round 1)

## Summary

SPURS is a structure-aware ΔΔG (protein stability) predictor. The port is in good shape on the
mechanics that matter most: the layout is complete (app/config/schema/test/download + 5-file
knowledge graph + `_runtime.py`/`util.py`/`fixture.py`), it uses the canonical single action
`predict`, it self-populates weights via the canonical `r2_then_hf` wrapper, typed
`ValidationError400` is used for the one runtime input branch, logging goes through `get_logger`
with no `print`, and **all** request/response field descriptions render in `model_json_schema()`
(verified by loading the schema — the `Optional[Annotated[...]] = Field(...)` form here keeps the
`Field` at field level, so nothing is dropped). The plumbing matches `esm2`/`dummy` closely:
`ModelFamily` with `modal_class_name`, `action_schemas`, empty `variant_axes`, a single
`resource_function`; no explicit `naming_function` is needed (the commons default handles the
single-variant case).

No 🔴 issues found. The notable problems are documentation accuracy/placeholders, a latent
build-order gap inherited when re-using the ESM2 download layer, dead code in `util.py`, and a
handful of style/correctness nits. Details below.

---

## 🟠 Should-fix

### 1. Fabricated / self-contradictory SPURS acronym expansion
- **Category:** Docs accuracy (C, A.9)
- **Location:** `README.md:7`, `MODEL.md:6`
- **Detail:** Both files state *"SPURS (Structure Prediction Using Residue-level and Secondary
  structure information)"*. This is almost certainly hallucinated: the model predicts **stability
  (ΔΔG)**, not structure, so "Structure Prediction" is internally contradictory with the rest of
  the docs, and the upstream paper title ("Generalizable and scalable protein stability prediction
  with rewired protein generative models") does not support this expansion. Shipping a confidently
  wrong acronym in the first paragraph of public docs is misinformation.
- **Fix:** Verify the real expansion against the upstream README
  (`knowledge-base/models/spurs/primary/pages/gh-spurs-readme.md`). If SPURS has no documented
  expansion, drop the parenthetical and describe it plainly (e.g. "SPURS is a structure-aware
  protein stability (ΔΔG) predictor from the Luo Group").

### 2. TODO / `pending` placeholders shipping in the knowledge graph
- **Category:** Knowledge graph completeness (A.9)
- **Location:** `README.md:159`, `MODEL.md:32`, `MODEL.md:53`, `sources.yaml:24`
- **Detail:** Three `<!-- TODO: ... -->` comments (benchmark numbers, training datasets) remain in
  README/MODEL, and `sources.yaml` has `md_r2: pending`. The rubric explicitly bans stray
  `TODO`/`pending`/template residue in shipped files.
- **Fix:** Either fill in the benchmark/training-data sections from the paper, or remove the
  placeholder comments and state plainly that quantitative benchmarks are not reproduced here.
  Replace `md_r2: pending` with the real R2 key or drop the key.

### 3. Dead code in `util.py`
- **Category:** Simplicity / dead code (B)
- **Location:** `models/spurs/util.py:173` (`validate_sequence_compatibility`), and the
  `residue_mapping` machinery in `extract_sequence_from_structure` (`util.py:73-82`)
- **Detail:** `validate_sequence_compatibility` is never called anywhere in the repo. Its only
  conceivable consumer would use the `residue_mapping` returned by `extract_sequence_from_structure`
  — but that function's sole caller, `extract_sequence_for_validation`, discards the mapping
  (`sequence, _ = ...`). So both the function and the mapping it would consume are dead weight that
  the next reader must reason about.
- **Fix:** Delete `validate_sequence_compatibility`, and have `extract_sequence_from_structure`
  return only the sequence (collapse it into `extract_sequence_for_validation`), or document a
  concrete consumer.

### 4. ESM2 download layer drops the `fair-esm` build dependency (build-order gap)
- **Category:** Acquisition / build-order (A.7)
- **Location:** `app.py:47-52`
- **Detail:** SPURS reuses the ESM2 download layer to bake ESM2-650M weights. `esm2/app.py:47-56`
  passes the fair-esm GitHub zip in `setup_download_layer(extra_pip_packages=[...])` precisely so
  the `r2_then_library` fallback can `import esm` during the build. The SPURS copy of that layer
  omits `extra_pip_packages` entirely, so on an ESM2 **R2 cache miss** the download-layer build
  would fail to import `esm` (fair-esm is only installed later, `app.py:75`). It works today only
  because ESM2-650M is essentially always pre-populated in R2. The SPURS layer itself
  (`app.py:54-59`) correctly lists `huggingface_hub`, which makes the omission on the ESM2 layer the
  clear inconsistency.
- **Fix:** Add the same fair-esm package to the ESM2 `setup_download_layer(..., extra_pip_packages=[...])`
  call, matching `esm2/app.py`.

### 5. Input sequences logged at INFO (deviates from house pattern)
- **Category:** Logging (A.6) / cross-model consistency (C)
- **Location:** `app.py:185-194` (and the auto-calc echo at `app.py:255-257`)
- **Detail:** The variant-sequence branch logs `item.sequence[:50]` and `item.variant_sequence[:50]`
  at INFO. The rubric says never log full sequences; the truncation to 50 chars means short proteins
  (e.g. peptides) are still logged in full. `esm2`/`dummy` log no sequence content at all, so this is
  also a uniformity break.
- **Fix:** Log lengths/counts instead of residues (e.g. "WT len=%d, variant len=%d, %d mutations"),
  matching the other models.

---

## 🟡 Nits

### 6. `typing.Optional` instead of `X | None` (fails repo lint auto-fix)
- **Category:** Style / lint conformance (B)
- **Location:** `schema.py` (`pdb`, `cif`, `mutations`, `variant_sequence`, all response Optionals),
  `download.py` (`get_model_dir`, `download_model_assets` signatures)
- **Detail:** `ruff check models/spurs/` auto-fixes 13 occurrences, all `Optional[...]` →
  `X | None` (UP007). These files were evidently committed without `make style`; running the repo's
  own formatter changes them. Other ported models use `X | None`.
- **Fix:** Run `make style` / `ruff check --fix` on the model and commit the modernized annotations.

### 7. f-string in a logger call (inconsistent with lazy `%s`)
- **Category:** Style (A.6)
- **Location:** `app.py:253` — `logger.info(f"    → ΔΔG = {ddg_value:.3f} kcal/mol")`
- **Detail:** Every other log call in the file uses lazy `%s` formatting; this one uses an f-string.
- **Fix:** `logger.info("    → ΔΔG = %.3f kcal/mol", ddg_value)`.

### 8. `results.index(r)` in the summary log is O(n²) and position-wrong for equal results
- **Category:** Correctness (B, logging-only)
- **Location:** `app.py:269-273`
- **Detail:** `manual_mut_count = sum(1 for r in results if r.mutations and results.index(r) not in
  auto_calculated_items)` recovers each item's index via `list.index`, which returns the **first**
  equal element. Two equal Pydantic result objects yield a wrong index, so the summary count can be
  off. It is also O(n²). Only the log line is affected, not the response.
- **Fix:** `for idx, r in enumerate(results): ...` and test `idx not in auto_calculated_items`.

### 9. `return_full_dms=False` with no `variant_sequence` and no `mutations` silently returns full DMS
- **Category:** Correctness / contract (B)
- **Location:** `schema.py:154-262` (validator) + `app.py:179`
- **Detail:** The validator enforces "variant_sequence ⇒ return_full_dms=False" but not the reverse.
  A request with `return_full_dms=False`, `mutations=None`, `variant_sequence=None` passes
  validation; in `app.py` the auto-calc branch is skipped and it falls through to the full-matrix
  path — contradicting the documented meaning of `return_full_dms=False`
  (README.md:72, schema.py:101-109).
- **Fix:** In the model validator, reject `return_full_dms=False` unless `variant_sequence` or
  `mutations` is supplied, with a clear message.

### 10. Dangling cross-references to models not in the repo
- **Category:** Knowledge graph consistency / dead links (A.9, C)
- **Location:** `comparison.yaml` (`gemme`, `pro4s`) and `BIOLOGY.md:73`
- **Detail:** `comparison.yaml` references `model: gemme` and `model: pro4s`, and BIOLOGY.md
  discusses Pro4S, but neither model dir exists. (Note: this is a repo-wide pattern — `clean`,
  `thermompnn`, `thermompnn_d` also reference them — so it may resolve when those models land, but
  as shipped they are dead cross-links for a catalog UI.)
- **Fix:** Drop references to un-ported models, or gate the catalog cross-link rendering on existence.

### 11. Unsubstantiated / promotional specifics in `comparison.yaml`
- **Category:** Docs tone (C)
- **Location:** `comparison.yaml:7` ("experiments that cost $50K-$500K"), `:9` ("rigorous
  benchmarking")
- **Detail:** Specific dollar figures and "rigorous benchmarking" read as marketing and are not
  cited; the rest of the docs admit benchmarks are "pending".
- **Fix:** Remove the dollar range / soften to a factual statement, or cite a source.

### 12. MODEL.md changelog rows out of chronological order
- **Category:** Docs polish (C)
- **Location:** `MODEL.md:147-149`
- **Detail:** Rows are dated 2025-09-16, then **2026-01-12**, then **2025-09-24** — the 2026 entry
  precedes a 2025 entry.
- **Fix:** Sort rows chronologically.

### 13. Temp file can leak on the CIF error path
- **Category:** Correctness / resource hygiene (B)
- **Location:** `_runtime.py:259-282` (`_materialise_structure`, cif branch)
- **Detail:** `raw_path` (the temp `.cif`) is created, then `_load_structure`/biotite write happen
  outside any `try/finally`; if any of those raise, `raw_path` (and a freshly-mkstemp'd `.pdb`) are
  never unlinked. The PDB branch returns the temp path which `predict()` cleans up in its `finally`,
  but the CIF intermediates are not guarded.
- **Fix:** Wrap the conversion in `try/finally` and unlink `raw_path` (and the output path on error).

---

## Definition-of-Done audit (spurs-relevant items)
- **Layout / standard files:** Met — all required files present.
- **Canonical action set:** Met — single `predict`; correct verb for a property/stability predictor.
- **Field descriptions render:** Met — verified via `model_json_schema()`; shared concepts are
  model-specific (ddG) and not pinned in `field_glossary.yaml`, which is acceptable.
- **Typed errors / no print / structured logging:** Met (one f-string log nit, #7).
- **Acquisition self-populates via canonical wrapper:** Met for the SPURS layer (`r2_then_hf`,
  build-order honored); **partially met** for the reused ESM2 layer (#4).
- **Licensing:** Met — per-model MIT `LICENSE` (Copyright Luo Group, 2025) consistent with
  `sources.yaml` (`type: MIT`) and README.
- **Tests (integration + deployment, lazy fixtures):** Met — `TestSuite` generates both; R2 read is
  inside `generate()`, so importing `test.py`/`fixture.py` never touches R2.
- **Knowledge graph complete & internally consistent:** **Partially met** — slug/display_name match
  config, but TODO/`pending` placeholders (#2), a likely-fabricated acronym (#1), and dangling
  cross-refs (#10) remain.

---

## Verification

Adversarial re-check of the five high-severity findings against the live code. All five confirmed.

1. **Fabricated / self-contradictory SPURS acronym — REAL.** `README.md:7` and `MODEL.md:6` both
   read "SPURS (Structure Prediction Using Residue-level and Secondary structure information)" while
   the same paragraphs call it a "stability prediction model" (ΔΔG); `sources.yaml:16` paper title is
   "...protein stability prediction with rewired protein generative models" — "Structure Prediction"
   is unsupported and internally contradictory.
2. **TODO / `pending` placeholders — REAL.** Verbatim: `README.md:159` `<!-- TODO: Add specific
   benchmark numbers... -->`, `MODEL.md:32` `<!-- TODO: Document specific training datasets... -->`,
   `MODEL.md:53` `<!-- TODO: Extract specific benchmark numbers... -->`, `sources.yaml:24`
   `md_r2: pending`.
3. **Dead code `validate_sequence_compatibility` + unused `residue_mapping` — REAL.** grep shows
   `validate_sequence_compatibility` defined only at `util.py:173`, never called; the sole caller of
   `extract_sequence_from_structure` is `extract_sequence_for_validation` (`util.py:135`) which
   discards the mapping via `sequence, _ = ...`; `residue_mapping` (`util.py:80-82`) is consumed only
   by the dead function. Both are dead weight.
4. **ESM2 download layer omits fair-esm — REAL (latent).** `spurs/app.py:47-52` calls
   `setup_download_layer` for the ESM2 layer with no `extra_pip_packages`, whereas `esm2/app.py:47-56`
   passes the fair-esm zip specifically so the fallback can `import esm` at build time;
   `esm2/download.py:49` does `import esm` inside the `r2_then_library` `init_fn`, which
   `download_helpers.py:519` runs only on R2 cache miss (`download_with_fallback`). The SPURS layer
   (`app.py:54-59`) correctly lists `huggingface_hub`, confirming the omission is the inconsistency.
   Latent because ESM2-650M is effectively always pre-populated in R2.
5. **Input sequences logged at INFO — REAL.** `app.py:186-194` logs `item.sequence[:50]` and
   `item.variant_sequence[:50]` at INFO; rubric `RUBRIC.md:36` (and `02_MODEL_INCLUSION_MATRIX.md:123`)
   says never log full sequences; a 50-char truncation still logs short proteins/peptides in full, and
   `esm2`/`dummy` log no sequence content. (Minor caveat: `boltz/app.py:553` and `biotite/app.py:164`
   also log truncated sequences, so the violation is not unique to SPURS — but the rubric breach and
   the deviation from `esm2`/`dummy` are demonstrable.)
