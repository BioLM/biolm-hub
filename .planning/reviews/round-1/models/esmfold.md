# Review — `models/esmfold/` (Round 1)

**Reviewer:** independent launch-gating review against `.planning/reviews/round-1/RUBRIC.md`
**Date:** 2026-06-29
**Verdict:** Solid plumbing that closely tracks the `esm2` house pattern, but ships with **one
launch-blocking correctness bug** (pLDDT scale: the schema and every doc declare `0–1`, the API
actually returns `0–100`) plus a cluster of documentation/uniformity gaps. The Modal image,
acquisition (`r2_then_library` + fair-esm in the download layer), config/`ModelFamily`, and test
wiring are all correct and idiomatic.

Cross-checks performed: fair-esm source (`esm/esmfold/v1/esmfold.py`), the internal read-only
reference (`oss-readonly-main/models/esmfold`), and sibling folding models (chai1, boltz, rf3,
immunefold, abodybuilder3) for field-name conventions; `esm2`/`dummy` for plumbing conventions.

---

## 🔴 Must-fix before launch

### 1. pLDDT is reported on a 0–100 scale but the schema and all docs declare 0–1
- **Category:** Correctness / schema-runtime mismatch (broken public contract)
- **Location:** `schema.py:64-65` (root); cascades to `README.md:76,87,94`, `comparison.yaml:9,31,59`,
  `BIOLOGY.md:12,37,47,108`, `MODEL.md:88,94`.
- **Detail:** fair-esm scales pLDDT by 100 before returning it
  (`esm/esmfold/v1/esmfold.py:253-255`, `plddt = categorical_lddt(...)` then `structure["plddt"] =
  100 * plddt`), and `output["mean_plddt"]` (`esmfold.py:334`) is derived from that 0–100 tensor.
  `app.py:164` returns it raw: `mean_plddt = float(outputs["mean_plddt"][idx].cpu())` — **no `/100`**.
  So the API returns values in `[0,100]`, but `schema.py:65` says *"Mean per-residue pLDDT confidence
  score (0–1)"*, the README example shows `"mean_plddt": 0.85`, and `comparison.yaml` instructs users
  to filter on `pLDDT > 0.7`. On the real output **every** prediction satisfies `> 0.7`, so that
  guidance silently misfilters automated pipelines. The internal reference confirms the true scale:
  its schema declares no range (`mean_plddt: float`) and its app returns the value raw exactly as here
  — the incorrect "(0–1)" claim was *introduced* during the OSS doc pass. `ptm` (a TM-score) genuinely
  is 0–1, so only the pLDDT fields are wrong.
- **Fix:** Correct the contract to 0–100 (do **not** divide in `app.py` — the golden R2 fixtures were
  generated from the 0–100 output, so dividing would break the tests). Specifically: `schema.py:65` →
  "Mean per-residue pLDDT confidence score (0–100) ..."; README example → `"mean_plddt": 85.0`;
  README confidence table (`README.md:94`) and `MODEL.md:88` → thresholds `>90 / 70–90 / 50–70 / <50`;
  `comparison.yaml:9,31,59` and `BIOLOGY.md:37` → `pLDDT > 70`; resolve `BIOLOGY.md:108`'s hedged
  "(0-1 or 0-100)". (The OOM sentinel `mean_plddt=0.0` at `app.py:182` remains a valid low value on
  the 0–100 scale — see finding 5.)

---

## 🟠 Should-fix

### 2. Public API doc names the action `predict`; the real action is `fold`
- **Category:** Docs / consistency (wrong endpoint in the API reference)
- **Location:** `README.md:57` (`### predict`); echoed in the `MODEL.md:193` changelog ("predict action").
- **Detail:** `config.py:43` registers only `ModelActions.FOLD` and `app.py:132` implements `fold`.
  The README "Actions / Endpoints" section documents the endpoint as `predict`, so a contributor or
  user following the README would call the wrong verb. The rubric is explicit that a folding model
  must `fold` and not overload `predict` — the code is correct; the docs contradict it.
- **Fix:** Rename the README section to `### fold` and update the surrounding prose; fix the
  `MODEL.md:193` changelog line to say "fold action".

### 3. Confidence field is `mean_plddt` (scalar) — every sibling folding model uses `plddt`
- **Category:** Cross-model uniformity (schema field naming — W5 territory)
- **Location:** `schema.py:64` (`mean_plddt: float`)
- **Detail:** The repo's north star is that the diff between two models is the science, not the
  plumbing. chai1 (`plddt: list[float]`), boltz (`plddt: list[float]`), rf3 (`plddt: list[float]`),
  immunefold (`plddt: list[list[float]]`) and abodybuilder3 (`plddt`) all expose the confidence as
  `plddt`; rubric §A.3 lists `plddt` as the canonical output field. esmfold both renames it
  (`mean_plddt`) and returns strictly less information (a single scalar) than its siblings, even
  though the per-residue array is available in `output["plddt"]` (and is already embedded in the PDB
  B-factor column). Note the genuine tension: a blind rename to `plddt: float` would collide *in type*
  with siblings' `plddt: list[float]`.
- **Fix:** Surface to the W5 rename pass. Preferred: return the per-residue array as
  `plddt: list[float]` like siblings (keep `ptm`); if the scalar mean is intentionally the only
  output, name it `plddt` only with a Pydantic alias and reconcile the type story across the folding
  family. Whatever is chosen, do it the same way the other folders do it.

### 4. Pre-public residue: stray `TODO` placeholders + internal "QA" references in shipped files
- **Category:** Open-source readiness (rubric §9 no stray TODO; §C no internal env names)
- **Location:** `README.md:136,147,168`; `MODEL.md:28,38,83`; `BIOLOGY.md:59` (7 `<!-- TODO ... -->`
  comments). Internal-env references: `MODEL.md:83` ("on QA deployment") and `app.py:215-216`
  (`# Force deploy to "qa" or "main" environment:`).
- **Detail:** The 5-file knowledge graph ships seven authoring TODOs (extract benchmark numbers,
  verify SOTA, add CI date, etc.) and references the internal `qa` Modal environment. The rubric
  classes internal env names (`qa`) as a launch-blocking leak. Honesty note: this is **partly
  repo-wide** — `esm2` carries 3 of the same TODOs and the identical `app.py` "qa" deploy comment, so
  the `qa`/`--force-deploy` comment is a global cleanup (best handled once in W14, not per-model).
  esmfold has the largest TODO load of the files reviewed.
- **Fix:** Resolve or delete the 7 TODO comments before launch (fill the numbers or drop the rows);
  replace "QA deployment" wording with neutral phrasing; fold the `app.py` "qa" deploy comment into
  the repo-wide W14 internal-reference sweep.

### 5. CUDA-OOM is silently swallowed and returned as a well-formed "success"
- **Category:** Error handling / contract (rubric §A.5)
- **Location:** `app.py:174-186`
- **Detail:** On `RuntimeError("CUDA out of memory")` the handler logs an error, appends
  `ESMFoldPredictResponseResult(pdb="", mean_plddt=0.0, ptm=0.0)` for **every** sequence in the batch,
  and continues. The caller receives a 200 with a structurally valid result and cannot distinguish a
  hardware/OOM failure from a genuine empty/low-confidence prediction (`mean_plddt=0.0` is a legal
  value on the corrected 0–100 scale). This diverges from `esm2`, which catches and re-raises so the
  failure propagates as a typed error. It is documented in README/MODEL, but documentation does not
  make a fake success observable.
- **Fix:** Raise a typed `ServerError` (from `models.commons.core.error`) on OOM so the failure is
  visible, or add an explicit per-item error/status field instead of a sentinel empty PDB. At minimum
  do not present an OOM as an indistinguishable successful result.

---

## 🟡 Nits

### 6. Dead class attribute `batch_size`; magic batch-token constant
- **Category:** Simplicity / dead code
- **Location:** `app.py:91` (`batch_size = ESMFoldParams.batch_size`), `app.py:146`
  (`max_tokens_per_batch = 1024  # Adjust as needed`)
- **Detail:** `self.batch_size` is set but never read — batching uses the hardcoded
  `max_tokens_per_batch=1024`, and the request-size cap is already enforced by the schema
  (`items` `max_length=ESMFoldParams.batch_size`). The `# Adjust as needed` comment is non-actionable.
- **Fix:** Remove the unused `batch_size` attribute; promote `max_tokens_per_batch` to a named
  `ESMFoldParams` constant (or drop the comment) so the batching budget is discoverable.

### 7. `fold` docstring says "Performs prediction"
- **Category:** Readability
- **Location:** `app.py:137`
- **Detail:** The method is the `fold` action; the docstring's "Performs prediction using the ESMFold
  model" perpetuates the predict/fold confusion (finding 2).
- **Fix:** Reword to "Performs structure prediction (folding) using the ESMFold model."

### 8. MODEL.md changelog rows out of chronological order
- **Category:** Docs polish
- **Location:** `MODEL.md:193-195`
- **Detail:** Rows read 2024-11-06 → **2026-03-14 → 2024-12-23**; the last two are swapped.
- **Fix:** Reorder chronologically (2024-11-06, 2024-12-23, 2026-03-14).

---

## Confirmed correct (no action — checked and cleared)
- **Acquisition / build-order rule:** `download.py` uses `r2_then_library(library_name="esm",
  init_fn=_init_esmfold_weights, monitor_directories=["~/.cache/torch"])`, self-populating R2; the
  fallback imports `esm` at build time and fair-esm **is** listed in
  `setup_download_layer(extra_pip_packages=[...])` (`app.py:41-45`). The deliberate "download
  checkpoints without constructing ESMFold (avoids openfold in the download layer)" design is sound
  and well-commented.
- **`torch.no_grad`:** `MODEL.md:176` claims no_grad inference; `ESMFold.infer` is decorated
  `@torch.no_grad()` (`esmfold.py:280`), so the claim holds even though `app.py` doesn't wrap it.
- **`ptm` 0–1:** correct (TM-score), `schema.py:67` description accurate.
- **Sequence length math:** `max_length = 768 + 4 - 1 = 771` matches "768 residues + up to 3
  separators" in README/MODEL; multimer-token validator wiring is correct.
- **License:** `LICENSE` (MIT, Meta) is consistent with `sources.yaml:3-6` and the README/MODEL
  license sections; attribution note present.
- **`pdf_r2: pending` / `md_r2: pending`** in `sources.yaml` applied-literature is the **house
  convention** (esm2 sources.yaml uses it identically) — not flagged.
- **Knowledge-graph identity:** `model_slug: esmfold` / `display_name: ESMFold` consistent across
  sources.yaml, comparison.yaml, and `config.py`/`schema.py`.
- **Config/test wiring:** `ModelFamily` (single variant, `FOLD` action, `modal_class_name`,
  resource/naming functions), `TestSuite` with integration + deployment cases, and lazy fixture
  filenames all match the house pattern.

## Definition-of-Done snapshot
- Layout / `ModelFamily` / closed-set action (`fold`): **met.**
- Acquisition self-populates via canonical wrapper + build-order: **met.**
- Errors typed / logging via `get_logger`, no `print`: **mostly met** (OOM path returns a fake
  success rather than a typed error — finding 5).
- Schema field descriptions render & are accurate: **NOT met** — pLDDT scale is wrong (finding 1) and
  field name diverges from siblings (finding 3).
- Knowledge graph complete, no placeholders/internal refs: **NOT met** — 7 TODOs + QA references
  (finding 4); README documents the wrong action (finding 2).

## Verification

Adversarial re-review of the 5 high-severity findings (re-read actual code + internal read-only
reference + fair-esm source + sibling schemas). All five confirmed.

1. **pLDDT 0–100 vs docs/schema 0–1 — REAL.** fair-esm scales by 100
   (`esm/esmfold/v1/esmfold.py:253-255` `structure["plddt"] = 100 * plddt`; esm1v copy literally
   comments "we predict plDDT between 0 and 1, scale to be between 0 and 100"), and `mean_plddt`
   is derived from that 0–100 tensor (`esmfold.py:334`). `app.py:164` returns it raw (no `/100`),
   yet `schema.py:65` says "(0–1)", and README:87,94 / comparison.yaml:9 / BIOLOGY.md:108 /
   MODEL.md:88 all assert 0–1 or a `pLDDT > 0.7` filter. Internal ref `schema.py` declares
   `mean_plddt: float` with NO range and app returns raw identically — the "(0–1)" claim is an
   OSS-doc-pass fabrication. `ptm` is genuinely 0–1.

2. **Docs name action `predict`; real action is `fold` — REAL.** `config.py:42` registers only
   `ModelActions.FOLD`; `app.py:132` is `def fold(`. README.md:57 header is `### `predict`` and
   MODEL.md:193 changelog says "predict action". Code correct, docs contradict it.

3. **`mean_plddt` (scalar) vs siblings' `plddt` (list) — REAL.** `schema.py:64` `mean_plddt: float`;
   chai1/boltz/rf3 `plddt: Optional[list[float]]`, immunefold/abodybuilder3 `plddt: list[list[float]]`.
   Verifiable cross-model inconsistency + less info exposed. Note: pre-existing design (internal ref
   also uses `mean_plddt: float`), and a blind rename to `plddt: float` would type-collide with siblings.

4. **7 TODOs + internal `qa` refs ship — REAL.** Exactly 7 `<!-- TODO -->` confirmed: README.md:136,147,168;
   MODEL.md:28,38,83; BIOLOGY.md:59. MODEL.md:83 says "on QA deployment"; app.py:215 `# Force deploy to
   "qa" or "main" environment:`. Honesty note holds: esm2 carries 3 of the same TODOs and the identical
   app.py:484 qa force-deploy comment, so the qa comment is repo-wide (best fixed once in W14).

5. **CUDA-OOM swallowed as well-formed success — REAL.** `app.py:174-186` catches
   `RuntimeError("CUDA out of memory")`, logs, appends `ESMFoldPredictResponseResult(pdb="",
   mean_plddt=0.0, ptm=0.0)` per sequence, and `continue`s → caller gets HTTP 200 with a valid result
   indistinguishable from a real low-confidence prediction. Diverges from esm2, whose encode/predict
   wrap the forward pass in `except Exception as e: logger.error(...); raise e` (esm2 app.py:165-167,
   189-191), propagating failures as typed errors.
