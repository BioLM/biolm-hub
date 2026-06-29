# Round-1 Review — `models/clean/` (CLEAN: Contrastive Learning-Enabled Enzyme ANnotation)

## Summary

CLEAN is a well-engineered wrapper: the app/config/schema/download plumbing matches the house
pattern closely (canonical `predict`/`encode` actions, `items`/`sequence`/`params` inputs, `results`
batch envelope, lazy fixtures, structured logging, methods-import-torch pattern, gpu-snapshot
container, build-order honored with `gdown` in `extra_pip_packages`). The inference code is careful
and defensive (shape validation, both pre-averaged and per-sequence 100.pt handling, deterministic
seeds). The knowledge-graph prose is rich and largely accurate.

**However there is one launch-gating 🔴 licensing defect that likely changes whether CLEAN can ship at
all:** the upstream CLEAN software is distributed under a **"Non-Exclusive Research Use License"**
(non-commercial / research-only), **not** BSD-3-Clause. This repo's `LICENSE`, `sources.yaml`, and
`README.md` all assert BSD-3-Clause and link a `.../blob/main/LICENSE` URL that 404s. This is a
misrepresentation of a restrictive upstream license and must be escalated to the model-inclusion
decision before launch. Beyond that, a handful of 🟠 convention/correctness items and minor 🟡 polish.

Verification performed this review:
- `gh api repos/tttianhao/CLEAN/git/trees/main` → root contains **only** `NON-EXCLUSIVE RESEARCH USE
  LICENSE FOR CLEAN SOFTWARE.pdf` (no `LICENSE` file).
- `gh api repos/tttianhao/CLEAN/contents/LICENSE` → **404** (the URL cited in our `sources.yaml` /
  `README.md` does not exist).
- `gh api repos/tttianhao/CLEAN/license` → **404** (GitHub does not detect a recognized OSI license).

---

## 🔴 Must-fix before launch

### 1. License is misrepresented — upstream CLEAN is research-use-only, not BSD-3-Clause
- **Category:** Licensing / open-source readiness
- **Location:** `models/clean/LICENSE:1-5,39-40`; `models/clean/sources.yaml:3-6`; `models/clean/README.md:234`
- **Detail:** The upstream repository `tttianhao/CLEAN` ships its license as
  `NON-EXCLUSIVE RESEARCH USE LICENSE FOR CLEAN SOFTWARE.pdf` (a non-commercial/research-only grant).
  There is **no** BSD-3-Clause `LICENSE` file — `https://github.com/tttianhao/CLEAN/blob/main/LICENSE`
  returns 404. Despite this, `models/clean/LICENSE` ships a verbatim **BSD 3-Clause** template with an
  **invented** copyright line ("Copyright (c) 2023, Tianhao Yu, … Huimin Zhao"), `sources.yaml` sets
  `license.type: BSD-3-Clause` with the dead URL, and `README.md` states "Code: BSD-3-Clause". The
  LICENSE file even carries a self-aware parenthetical ("inferred … confirm the exact line against the
  CLEAN LICENSE before public release") — the verification it asks for was never done, and the guess is
  wrong. This is both a broken public contract and a real legal-misrepresentation risk: a research-use
  license is **not** in the permitted permissive set (MIT/Apache/BSD/CC-BY) that the inclusion gate
  requires, and the CLEAN weights (`split100.pth`, `100.pt`, `gmm_ensumble.pkl`) pulled from the
  authors' Google Drive plus the `util.py` `LayerNormNet` ("Architecture from … tttianhao/CLEAN") are
  governed by that upstream license.
- **Suggested fix:** Escalate to the model-inclusion decision (`.planning/02_MODEL_INCLUSION_MATRIX.md`).
  Read the actual upstream license PDF and (a) if it is non-commercial/research-only, either **exclude
  CLEAN** from the permissive OSS catalog or ship it only with an accurate, prominent research-use
  license label and `notes` everywhere (`LICENSE`, `sources.yaml.license`, `README.md`); (b) replace the
  fabricated BSD-3-Clause `LICENSE` with the true upstream license text, the correct holder/year, and a
  correct, resolvable URL; (c) remove the editorial parenthetical from the shipped `LICENSE`. Do **not**
  launch with the BSD-3-Clause claim.

---

## 🟠 Should-fix

### 2. `split100.csv` fetched from an unpinned `main` branch — reproducibility/correctness risk
- **Category:** Acquisition / correctness
- **Location:** `models/clean/download.py:26-28`; `models/clean/sources.yaml:34`
- **Detail:** `GITHUB_SPLIT100_CSV_URL` points at `.../CLEAN/main/app/data/split100.csv` (mutable
  branch), and `sources.yaml` `source_repos[0].commit: ''` pins nothing. The EC→ID ordering in
  `split100.csv` must stay byte-aligned with the per-sequence embedding order in `100.pt`:
  `_build_cluster_center_tensor` (`app.py:204-215`) walks `ec_id_dict` insertion order and slices
  `100.pt` sequentially. If upstream ever re-orders or edits `split100.csv`, the fallback path will
  silently build **mis-aligned cluster centers** (wrong EC labels) with no error. This only bites on an
  R2 cache miss, making it a latent landmine.
- **Suggested fix:** Pin the GitHub raw URL to the same commit you record in `sources.yaml.commit`
  (e.g. `.../CLEAN/<sha>/app/data/split100.csv`), and fill `source_repos[0].commit` + `snapshot_r2`.

### 3. `max_predictions` advertises 1–20 but the algorithm hard-caps at 5
- **Category:** Schema / runtime mismatch (public contract)
- **Location:** `models/clean/schema.py:30-35`; `models/clean/app.py:353-364`; `models/clean/util.py:146-148`
- **Detail:** `CLEANPredictRequestParams.max_predictions` defaults to 10 with range `ge=1, le=20`, and
  the field reads "Maximum number of EC predictions to return per sequence." But `maximum_separation`
  resets its cutoff to 0 whenever the separation index is `>= 5`, so `predict` can never emit more than
  5 predictions: `range(min(cutoff_idx + 1, max_predictions))` is bounded by `cutoff_idx ∈ [0,4]`. Any
  `max_predictions` in 6–20 is dead, and a caller asking for 15 silently gets ≤5. The cap is documented
  in prose (README/comparison weaknesses) but the parameter surface contradicts it.
- **Suggested fix:** Either cap the field at `le=5` (matching the algorithm), or keep the wider range but
  make the description state explicitly that the max-separation algorithm caps results at 5 regardless
  of this value.

### 4. `comparison.yaml` recommends models that are not in this catalog
- **Category:** Knowledge graph / consistency / no-internal-leakage
- **Location:** `models/clean/comparison.yaml:43 (diamond), :46 (gemme), :57 (camsol)`
- **Detail:** `alternatives` lists `diamond` and `gemme`; `complements` lists `camsol`. None of these
  exist under `models/` (catalog has `esm2`, `boltz` which are valid, but not these three). These are
  dangling cross-model references — in the local catalog web app (`bm serve`) they point nowhere, and
  for an OSS reader they reference platform-only models that aren't shipped here.
- **Suggested fix:** Reference only models present in the OSS catalog, or drop the entries / clearly mark
  them as external (non-catalog) suggestions.

### 5. README states the wrong container base image
- **Category:** Docs accuracy
- **Location:** `models/clean/README.md:218`
- **Detail:** "Container image: Based on `pytorch/pytorch:2.0.1-cuda11.7-cudnn8-runtime`", but
  `app.py:35` builds from `pytorch/pytorch:2.6.0-cuda12.4-cudnn9-runtime`. Stale by two major torch /
  CUDA versions.
- **Suggested fix:** Update the README line to match `app.py` (2.6.0 / cuda12.4 / cudnn9).

---

## 🟡 Nits

### 6. `min_confidence` description overstates the guarantee
- **Category:** Field description accuracy
- **Location:** `models/clean/schema.py:36-41`; `models/clean/app.py:380-392`
- **Detail:** The field says "Minimum confidence threshold to include a prediction," but `predict`
  always returns at least one prediction even when its confidence is below the threshold (the
  "Ensure at least one prediction" fallback). Worth a half-sentence so callers don't assume an empty
  list is possible.
- **Suggested fix:** Append "(at least one prediction is always returned, even if below this threshold)".

### 7. README and MODEL.md verification tables disagree on which 6 enzymes were tested
- **Category:** Knowledge-graph internal consistency
- **Location:** `models/clean/README.md:188-198` vs `models/clean/MODEL.md:100-109`
- **Detail:** README's "Test Cases" table lists 6 halogenase-dataset enzymes (A7KH27, A8CF74, Q8KLM0,
  Q8GAQ9, W0W999, Q5SLF5); MODEL.md's "BioLM Verification Results" lists a different set (TEM-1, ADH,
  catalase + 3 halogenases). Both claim "VERIFIED / 6/6". A reader can't tell which set was actually
  run. Also README shows Q8GAQ9 with confidence `0.0051` (below the 0.05 default `min_confidence`) as a
  returned prediction without noting that's the always-return-one fallback.
- **Suggested fix:** Make the two tables consistent (same enzyme set), and add a one-line note that
  sub-threshold confidences appear only via the at-least-one fallback.

### 8. `sources.yaml` primary-source fields incomplete
- **Category:** Knowledge-graph completeness
- **Location:** `models/clean/sources.yaml:28-29,36`
- **Detail:** `primary_papers[0].md_r2: pending`, `primary_papers[0].arxiv: ''`, and
  `source_repos[0].snapshot_r2: pending`. `pending`/`''` are accepted sentinels in this repo (cf. esm2
  applied_literature), so this is not blocking, but esm2's *primary* paper has a real `md_r2`; CLEAN's
  does not. The bioRxiv DOI could populate `arxiv`.
- **Suggested fix:** Convert/upload the primary paper markdown and snapshot, and put the bioRxiv DOI in
  `arxiv`, before public release (ties into finding #2 for the commit/snapshot).

### 9. Bespoke custom download where commons now offers a consolidating helper
- **Category:** Consistency / simplicity
- **Location:** `models/clean/download.py:222-250` (CustomSourceConfig)
- **Detail:** `download_helpers.r2_then_archive` explicitly names `clean` in its docstring as a model
  whose "download zip → unzip subtree" logic it was built to absorb. CLEAN can't fully adopt it because
  the weights live on Google Drive (gdown's confirmation flow ≠ a plain archive URL), so the custom path
  is defensible — but the split100.csv half is a plain GitHub raw file that the canonical wrappers cover.
  Either reconcile (use a canonical wrapper for the CSV, keep custom only for the gdrive zip) or update
  the `r2_then_archive` docstring so it stops claiming `clean`.
- **Suggested fix:** Low priority; pick one of the two to keep the "plumbing is identical across models"
  invariant honest.

### 10. R2-primary read config re-enables caching
- **Category:** Minor convention deviation
- **Location:** `models/clean/download.py:207-219` (`enable_r2_cache=True` on the R2_ONLY primary)
- **Detail:** The commons fallback wrappers build their R2-primary with `enable_r2_cache=False`
  ("reading, not writing", `download_helpers._build_r2_primary`). CLEAN's hand-rolled primary sets it
  `True`, so a cache hit re-uploads what it just read. Harmless but inconsistent.
- **Suggested fix:** Set `enable_r2_cache=False` on the primary read config.

### 11. `pickle.load` + `weights_only=False` on a Google-Drive-sourced artifact
- **Category:** Security (low confidence)
- **Location:** `models/clean/app.py:118-122,144-148,155-156`
- **Detail:** Checkpoints and `gmm_ensumble.pkl` are loaded with `weights_only=False` / `pickle.load`.
  The comment justifies it as "Trusted: checkpoints from R2 model store," which holds once R2 is
  populated — but the **fallback** path materializes those bytes from the authors' Google Drive, an
  external source, so the trust boundary is weaker on first populate. Consistent with house practice for
  trusted upstreams, hence only a nit.
- **Suggested fix:** Optional: record and verify a content hash of the gdrive zip in
  `_download_clean_assets` / `_extract_clean_files` before the first R2 cache write.

---

## Definition-of-Done snapshot (this model)
- Layout / standard files: **met** (all of app/config/schema/test/download/fixture/util + 5-file KG + LICENSE present).
- Actions from closed set: **met** (`predict`, `encode`).
- Schema field names + rendered descriptions: **met** (uniform `items`/`sequence`/`params`/`results`; all `Field(description=...)` render; singular `embedding` matches esm2 `LayerEmbedding`).
- Errors / logging: **met** (load-time integrity uses `RuntimeError`; runtime user errors handled by Pydantic validators; `get_logger`, no `print`).
- Acquisition self-populate + build-order: **met** (R2-then-custom self-populates; `gdown` in `extra_pip_packages`), but see #2 (unpinned source) and #9/#10 (consistency).
- Licensing: **NOT met — 🔴 (finding #1)**.
- Knowledge graph consistent/complete: **partially met** (slug/display_name consistent; but #4 dangling refs, #7 inconsistent tables, #8 pending primary artifacts).
- Tests lazy-load + reuse shared assets: **met** (lazy fixtures; enzyme-specific sequences are appropriately model-local — the shared library only has generic proteins, unsuitable for EC tests).
- No internal leakage (`biolm-modal`/`qa`/`.planning`): **met** (clean grep).

## Verification

Adversarial re-check of the five HIGH-severity findings against the actual files. All five confirmed REAL.

1. **License misrepresented — REAL.** `gh api repos/tttianhao/CLEAN/license` and `.../contents/LICENSE` both return 404; the repo root tree contains only `NON-EXCLUSIVE RESEARCH USE LICENSE FOR CLEAN SOFTWARE.pdf` (research-use-only), no BSD file. Yet `models/clean/LICENSE:1-4` ships a verbatim BSD-3-Clause template with an invented copyright line and itself admits at `:39-40` the holder/year are "inferred ... confirm ... before public release"; `sources.yaml:4-5` sets `type: BSD-3-Clause` with the dead `/blob/main/LICENSE` URL; `README.md:234` states "Code: BSD-3-Clause". Research-use is outside the permitted permissive set — misrepresentation confirmed.
2. **split100.csv from unpinned `main` — REAL.** `download.py:27` URL targets `.../CLEAN/main/app/data/split100.csv` (mutable branch); `sources.yaml:34` `commit: ''`. `app.py:130` builds `ec_list` from `split100.csv` insertion order and `app.py:205-215` slices `100.pt` (separately pinned Google Drive file, `download.py:22`) sequentially in that order. The only guards (`app.py:177` shape, `:189`/`:193` count checks) validate counts, not row order, and no content hash is computed (`_extract_clean_files` checks existence/non-empty only) — an upstream reorder of equal length silently mis-aligns EC labels on a cache miss.
3. **max_predictions 1-20 but hard-capped at 5 — REAL.** `schema.py:30-34` default 10, `ge=1,le=20`, "Maximum number of EC predictions to return". `util.py:146-148` resets `max_sep_i` to 0 when `>=5`, so `maximum_separation` returns a value in {0,1,2,3,4}. `app.py:364` iterates `range(min(cutoff_idx+1, max_predictions))` → at most 5; values 6-20 are dead.
4. **comparison.yaml dangling refs — REAL.** `comparison.yaml:43` (diamond), `:46` (gemme), `:57` (camsol) are absent from `models/` (verified `ABSENT`); only the also-referenced `esm2`/`boltz` exist.
5. **README wrong base image — REAL.** `README.md:218` says `pytorch/pytorch:2.0.1-cuda11.7-cudnn8-runtime`; `app.py:35` builds `from_registry("pytorch/pytorch:2.6.0-cuda12.4-cudnn9-runtime")` — stale by two major torch/CUDA versions.
