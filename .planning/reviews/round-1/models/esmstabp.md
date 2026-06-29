# Review — `models/esmstabp/` (Round 1)

**Reviewer verdict:** Solid, well-documented model that follows the house plumbing closely
(`predict` action, `items`/`results`, `ModelMixin`, ESM2-endpoint embedding pattern shared with `tempro`).
The schema is clean and field descriptions render. The main launch-gating problem is a hardcoded internal
bucket name (`biolm-modal`) in the shipped training script that both leaks an internal reference **and**
breaks self-population against the public default bucket. Beyond that: the upstream paper title is cited
incorrectly across the knowledge graph (and the wrong title mis-describes the model), and the output field
name diverges from its sibling `tempro` for the identical quantity. Everything else is nits.

Cross-checked against `models/esm2/` (reference), `models/dummy/` (template), and `models/tempro/` (closest
sibling: also a Tm predictor that calls the ESM2 endpoint).

---

## 🔴 Must-fix before launch

### 1. `biolm-modal` hardcoded — internal-name leak + broken self-population
- **Category:** Acquisition / internal-reference leak / correctness
- **Location:** `models/esmstabp/_train.py:72` (and `:74`, `:307`); `models/esmstabp/download.py:8`
- **Detail:** `_train.py` hardcodes `R2_BUCKET = "biolm-modal"` and uploads the trained joblib files with
  `s3.put_object(Bucket=R2_BUCKET, ...)`. The runtime download path (`download.py` →
  `standard_r2_download` → commons) resolves the bucket from
  `models/commons/util/config.py:9`: `r2_bucket_name = os.getenv("BIOLM_R2_BUCKET", "biolm-public")`.
  Two problems:
  (a) `biolm-modal` is an internal name and the rubric flags it as a launch blocker in any shipped file —
  it appears in `_train.py` (documented as runnable via `modal run models/esmstabp/_train.py`) and in the
  `download.py:8` comment.
  (b) Functional: `_train.py` writes weights to `biolm-modal`, but the deployed container reads from the
  default `biolm-public`. A maintainer who follows the documented training flow uploads to a bucket the
  model never reads from, so self-population silently fails unless `BIOLM_R2_BUCKET=biolm-modal` is set —
  which contradicts the public default and the model's own README/MODEL.md (which say
  `r2://biolm-public/model-store/esmstabp/v1/`).
- **Fix:** Stop hardcoding the bucket. Import `r2_bucket_name` from `models.commons.util.config` (and ideally
  reuse the commons upload helper in `storage/downloads.py` rather than a raw `put_object`). Update the
  `download.py:8` comment to `r2://biolm-public/...`. This both removes the leak and makes upload/download
  agree on one bucket.

---

## 🟠 Should-fix

### 2. Upstream paper title is wrong across the knowledge graph (and mis-describes the model)
- **Category:** Knowledge graph accuracy / docs
- **Location:** `models/esmstabp/sources.yaml:16`; `models/esmstabp/README.md:291`, `:297` (BibTeX)
- **Detail:** All three cite the title *"ESMStabP: Leveraging protein language models for predicting protein
  stability changes upon single-point mutations."* The actual title for DOI `10.1101/2025.02.18.638450`
  (Ramos, Jernigan, Kilinc — Iowa State) is **"ESMStabP: A Regression Model for Protein Thermostability
  Prediction."** The cited (wrong) title describes a per-mutation ΔΔG predictor, which directly contradicts
  what this model does (absolute Tm regression) and what `comparison.yaml:15` itself lists as a weakness
  ("no per-mutation ddG resolution"). This ships publicly and will mislead users about both the paper and
  the model.
- **Fix:** Replace the title with "ESMStabP: A Regression Model for Protein Thermostability Prediction" in
  `sources.yaml`, the README References list, and the BibTeX `title=` field.

### 3. Output field name diverges from sibling `tempro` for the identical quantity
- **Category:** Cross-model uniformity (schema field names)
- **Location:** `models/esmstabp/schema.py:71` (`melting_temperature`) vs `models/tempro/schema.py:63` (`tm`)
- **Detail:** `tempro` and `esmstabp` both predict protein melting temperature via ESM2 embeddings and return
  it as a single float, with near-identical descriptions ("Predicted melting temperature (Tm) in …Celsius").
  `tempro` calls the field `tm`; `esmstabp` calls it `melting_temperature`. The repo's north star is that the
  diff between models is the science, not the plumbing — two Tm predictors should expose Tm under one name.
- **Fix:** Standardize on one (recommend `tm` to match the existing `tempro` contract) and, if renaming,
  keep a Pydantic alias per the field-name standard so the rename is non-breaking.

---

## 🟡 Nits

### 4. Model 4 feature count is off by one in docs/comments (1286 vs actual 1285)
- **Category:** Doc/code accuracy
- **Location:** `models/esmstabp/MODEL.md:39` & `:253`; `models/esmstabp/_train.py:32` & `:254`
- **Detail:** Model 4 = 1280-d embedding + 5 features (growth_temp, lysate, cell, thermophilic,
  nonThermophilic) = **1285**. `README.md:47` correctly says 1285, but MODEL.md and the `_train.py`
  comments say 1286. The code itself (`_train.py` `X4 = np.column_stack([...])`, and `app.py`
  `_prepare_features`) produces 1285 — only the comments/tables are wrong.
- **Fix:** Change the four "1286" occurrences to "1285".

### 5. Dead/misplaced class docstring
- **Category:** Readability
- **Location:** `models/esmstabp/app.py:78-82`
- **Detail:** The triple-quoted block sits *after* `app_username = modal.parameter(...)`, so it is a no-op
  string expression, not the class docstring (`ESMStabPModel.__doc__` is `None`).
- **Fix:** Move the docstring to the first line of the class body (above `app_username`).

### 6. `is_thermophilic` typed `Optional[bool] = None` but always populated
- **Category:** Schema correctness
- **Location:** `models/esmstabp/schema.py:75`
- **Detail:** `app.py:150` always sets `is_thermophilic=bool(tm_pred > 60.0)`; it is never `None`. Declaring it
  `Optional[bool]` with `default=None` advertises an optionality the endpoint never exercises.
- **Fix:** Make it a required `bool` (`is_thermophilic: bool = Field(..., description=...)`).

### 7. README states the wrong numpy version for the serving container
- **Category:** Docs
- **Location:** `models/esmstabp/README.md:242` ("numpy 1.23.5")
- **Detail:** `app.py:56` installs `numpy==1.26.4` in the serving image; the 1.23.5 pin is the *training*
  image (`_train.py:55`). The README's Implementation Notes therefore states the wrong runtime version.
- **Fix:** Correct README to `numpy 1.26.4`.

### 8. Bare `RuntimeError` for system faults instead of the typed taxonomy
- **Category:** Errors
- **Location:** `models/esmstabp/app.py:114`, `:141-144`, `:170`, `:175`
- **Detail:** W7 ratified `ServerError`/`ModelExecutionError` (subclasses of `BioLMError`, see
  `models/commons/core/error.py`). These are all system faults (RF weights missing, ESM2 endpoint down), so
  bare `RuntimeError` still propagates and is sanitized to 5xx — but it bypasses the stable `code`s the
  taxonomy provides. *Note:* this is a repo-wide pattern (`tempro`, `deepviscosity`, `temberture` all raise
  `RuntimeError` for the same situations), so esmstabp is at least consistent with its peers; fix is best done
  as a cross-model pass.
- **Fix:** Raise `ModelExecutionError`/`ServerError` for the ESM2-call and missing-weights paths.

### 9. Internal `qa` env name in a code comment
- **Category:** Possible internal leakage
- **Location:** `models/esmstabp/app.py:230` (`# Force deploy to "qa" or "main" environment:`)
- **Detail:** The rubric lists `qa` as an internal env name to scrub from shipped files. *Note:* the identical
  comment is in the reference model `models/esm2/app.py:484`, and `qa`/`main` are the real Modal environment
  names defined in `models/commons/util/config.py:82-83`, so this is a repo-wide convention rather than an
  esmstabp-specific leak — flag for the global docs/comment cleanup, not as a per-model blocker.
- **Fix:** Decide repo-wide whether environment names belong in public comments; if not, scrub here and in
  `esm2`.

---

## Notes / things that are fine (cross-checked, not findings)
- **Acquisition:** R2-only via `standard_r2_download` is justified — the RF weights are custom-trained with no
  public HF/library/URL source, and `_train.py` documents the (custom) build path. `setup_download_layer` is
  wired correctly; no build-order issue (no library fallback that imports at build time).
- **`pending` placeholders** in `sources.yaml` (`md_r2`, `snapshot_r2`, applied-lit `pdf_r2`) match the
  house convention — `esm2`, `tempro`, `deepviscosity` all carry `pending`; the primary `pdf_r2` is filled.
- **License:** per-model MIT `LICENSE` present, matches `sources.yaml:4`, and the maintainer note about the
  best-effort copyright holder/year is appropriately flagged (upstream ships no LICENSE).
- **Feature ordering** between `_train.py` (column_stack order) and `app.py:_prepare_features` matches for all
  4 RF variants; the derived thermophilic/nonThermophilic flags (growth_temp > 60 / < 30) are consistent with
  the two-column dataset encoding.
- **Logging:** uses `get_logger`, no `print` in runtime code; `_train.py`'s prints are explicitly exempted in
  `pyproject.toml:160` (`"models/esmstabp/_train.py" = ["T20"]`).
- **Tests/fixtures:** `TestSuite` with integration + deployment cases, one per RF variant; fixtures reuse the
  shared `STANDARD_PROTEIN_STABILITY` asset; no module-scope R2/network.

---

## Verification

Adversarial re-check of the three HIGH-severity findings against the actual files (and the live paper record).

- **Finding 1 — `biolm-modal` hardcoded (internal-name leak + wrong-bucket self-population): REAL.**
  `_train.py:72` literally sets `R2_BUCKET = "biolm-modal"`, consumed at `:307` (`s3.put_object(Bucket=R2_BUCKET, ...)`)
  and embedded in the returned path string at `:309`; `download.py:8` repeats `r2://biolm-modal/...` in a comment.
  The runtime read path resolves the bucket from `commons/util/config.py:9` (`r2_bucket_name = os.getenv("BIOLM_R2_BUCKET", "biolm-public")`),
  imported and used by `commons/storage/downloads.py:42` — so by default reads come from `biolm-public`. Docs
  (`MODEL.md:261`, `README.md:243`/`:257`) all say `biolm-public`. Both sub-claims hold: internal name leaks into a
  shipped runnable script, and train-uploads-to-`biolm-modal` vs runtime-reads-`biolm-public` is a genuine mismatch.

- **Finding 2 — Upstream paper title cited wrong: REAL.**
  DOI 10.1101/2025.02.18.638450 (PMC11870573, bioRxiv v1; Ramos, Jernigan, Kilinc, Iowa State) is titled
  *"ESMStabP: A Regression Model for Protein Thermostability Prediction"* (verified via bioRxiv/PMC). The repo cites
  *"...Leveraging protein language models for predicting protein stability changes upon single-point mutations"* at
  `sources.yaml:16`, `README.md:291`, and `README.md:297` (BibTeX). The fabricated title also implies a per-mutation
  ddG predictor, directly contradicting `comparison.yaml:15` ("no per-mutation ddG resolution"). Confirmed wrong.

- **Finding 3 — Output field name diverges from sibling tempro for Tm: REAL (low-severity consistency nit).**
  `esmstabp/schema.py:71` exposes `melting_temperature: float` ("Predicted melting temperature (Tm) in Celsius");
  `tempro/schema.py:63` exposes `tm: float` for the same quantity. The divergence is concretely demonstrable. Caveat:
  there is no enforced cross-model field-naming contract (e.g. `temberture/schema.py:138` folds Tm into a shared
  `predictions` field), so this is a naming-consistency cleanup, not a correctness bug — but the cited divergence is real.
