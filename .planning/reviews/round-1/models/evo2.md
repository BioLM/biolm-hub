# Review — `models/evo2/`

**Reviewer:** independent launch-gating review (round 1)
**Date:** 2026-06-29

## Summary

Evo2 is a multi-domain autoregressive DNA model exposing three canonical actions (`encode`,
`log_prob`, `generate`). The layout is complete (all standard files + 5-file knowledge graph), the
schema is well-described and uniform with the house pattern, errors use the typed
`ValidationError400`/`UserError` taxonomy, logging is structured (no `print`), and the LICENSE +
NOTICE are correct and consistent with `sources.yaml` (Apache-2.0, proper attribution). The action
verbs and field names match the ratified set, and the docs are clear and accurate to the code in most
respects.

The problems cluster in the **plumbing**, which is exactly where the repo wants uniformity:

- The HuggingFace fallback in `download.py` cannot run in the build-time download layer because
  `huggingface_hub` is never installed there — every other HF-fallback model in the repo passes it
  explicitly. This breaks self-population on a cold/empty R2 bucket (the OSS deploy path).
- `download.py` hand-rolls ~140 lines that the canonical `r2_then_hf` helper already provides.
- The `log_prob` field description ("Pseudo-log-likelihood") is the masked-LM wording and is wrong
  for an autoregressive model (the glossary and the sibling `evo` model use the correct phrasing).
- `comparison.yaml` points its machine-readable `alternatives`/`complements` at a model slug (`nt`)
  that does not exist in `models/`.
- The snapshot NOTE comment directly contradicts the decorator config and the README.

None are science bugs; the inference math is sound. But several are convention/contract issues that
should be fixed before launch.

---

## 🔴 Must-fix

### 1. HF fallback unusable in the download layer — `huggingface_hub` not installed (build-order rule, A.7)
- **Category:** Acquisition / build-order
- **Location:** `models/evo2/app.py:57-62` (the `setup_download_layer(...)` call) + `models/evo2/download.py:110-127`
- **Detail:** `download.py` defines a HuggingFace fallback (`HfSourceConfig` / `AcquisitionStrategy.HUGGINGFACE_HUB`)
  that imports `huggingface_hub` when it runs. The download layer is built **before** the main
  dependency install, and `setup_download_layer`'s `base_packages` are only `boto3`, `pydantic`,
  `requests` (`models/commons/modal/downloader.py:77-81`) — `huggingface_hub` is not among them and
  evo2 passes **no** `extra_pip_packages`. Every other HF-fallback model passes it explicitly with a
  comment, e.g. `models/esm1b/app.py:35-41` and `models/e1/app.py:56-62`
  ("huggingface_hub needed in download layer for HF fallback when R2 cache is empty"). On a cold/empty
  R2 bucket the fallback fires and crashes with `ModuleNotFoundError: huggingface_hub`, breaking the
  ratified self-population guarantee (A.7) — the exact path an external OSS user hits when deploying
  against their own bucket. (On BioLM's pre-populated R2 the primary hits and the fallback never runs,
  which is why it "works" today — this is a latent break.)
- **Fix:** add `extra_pip_packages=["huggingface_hub==<pinned>"]` to the `setup_download_layer(...)`
  call (pin the same version used by the canonical helper / sibling models), matching the esm1b/e1
  pattern.

---

## 🟠 Should-fix

### 2. `log_prob` description is the masked-LM ("pseudo") wording, wrong for an autoregressive model
- **Category:** Field descriptions / correctness
- **Location:** `models/evo2/schema.py:211-214`
- **Detail:** The field reads `description="Pseudo-log-likelihood of the sequence under the model."`,
  but Evo2 is autoregressive and `app.py:265-272` computes the **exact joint** log-likelihood
  (`score_sequences(reduce_method="sum")` = sum of autoregressive conditionals). `tooling/field_glossary.yaml`
  explicitly distinguishes the two and reserves "Pseudo-log-likelihood…" for masked LMs, offering
  "Log-likelihood of the sequence under the model." for autoregressive models; the sibling DNA model
  `evo` (also autoregressive, same `score_sequences` call) correctly uses the non-pseudo wording
  (`models/evo/schema.py:125-126`). README/MODEL/BIOLOGY all correctly say "total log-probability" —
  the schema field is the lone inaccuracy. (Both strings pass `check_schema_docs`, so CI won't catch
  it.) The description was almost certainly copy-pasted from ESM2 (`models/esm2/schema.py:211`).
- **Fix:** change to `"Log-likelihood of the sequence under the model."` (already in the glossary's
  allowed list).

### 3. `comparison.yaml` references a non-existent model slug `nt`
- **Category:** Knowledge graph / cross-model consistency
- **Location:** `models/evo2/comparison.yaml:56` and `:67` (`model: "nt"` under `alternatives` and
  `complements`; also `dont_use_when` lines 43-44, 50)
- **Detail:** The file header (lines 5-8) states the requirement "All referenced model slugs must
  exist in models/", but there is no `nt` model in the repo (no `models/nt/`, no model with
  `base_model_slug = "nt"`). These are machine-readable selection-graph references, so they point at
  nothing. (esm2's comparison.yaml does not reference `nt`, so this isn't a shared placeholder.)
- **Fix:** remove the `nt` entries, or rename to the actual slug if/when the Nucleotide Transformer is
  ported (e.g. `nucleotide_transformer`); scrub the prose "use nt" recommendations to an existing
  model (e.g. `dnabert2`).

### 4. Snapshot NOTE comment contradicts the decorator config and the README
- **Category:** Correctness / documentation in code
- **Location:** `models/evo2/app.py:94-95` (NOTE) vs `app.py:98-104` (decorator) vs `app.py:117-154`
  (enter methods); README `models/evo2/README.md:233,241`
- **Detail:** The NOTE says "We do not use Modal GPU memory snapshots for this model (CPU-only
  two-phase instead). Reason: GPU snapshots fail to create (transformer_engine/flash-attn don't
  support it)." Yet the decorator sets `enable_memory_snapshot=True` **and**
  `experimental_options={"enable_gpu_snapshot": True}`. The enter methods implement the CPU two-phase
  pattern (`@modal.enter(snap=True)` loads on CPU, `@modal.enter(snap=False)` moves to GPU) — *not*
  the GPU-snapshot pattern the siblings use (`models/evo/app.py:95-98` and `models/esm2/app.py:89-118`
  load directly on GPU in `snap=True`). The README then claims "GPU snapshot enabled". So the code
  both disclaims and requests GPU snapshots. If the comment is accurate, `enable_gpu_snapshot=True`
  risks the snapshot-creation failure it warns about; if the code is correct, the comment + README are
  stale and misleading.
- **Fix:** reconcile. If GPU snapshot genuinely fails for this image, drop the
  `experimental_options={"enable_gpu_snapshot": True}` (keep `enable_memory_snapshot=True` for the CPU
  two-phase) and correct README:233/241. Otherwise delete the NOTE and load on GPU in `snap=True`
  like the siblings.

### 5. Bespoke ~140-line downloader duplicates the canonical `r2_then_hf`
- **Category:** Modularity / uniformity (plumbing, not science)
- **Location:** `models/evo2/download.py:37-175`
- **Detail:** `download_model_assets` hand-rolls the R2-primary + HF-fallback flow, including a manual
  `build_hf_snapshot_path` call and a nested-glob search for `models--{repo}/snapshots/*/{file}.pt`.
  `models.commons.storage.download_helpers.r2_then_hf` (download_helpers.py:390-460) already does all
  of this — it builds both configs, runs `download_with_fallback`, and resolves the HF snapshot path
  automatically (handling exactly the "nested HF cache structure" the docstring cites as the reason
  for the custom code). esm2 and ~12 other models use the canonical one-liners. This is precisely the
  plumbing divergence the repo's uniformity north star warns against, plus a maintenance burden.
- **Fix:** migrate to `r2_then_hf` (passing `hf_repo_id`/`hf_revision`/`allow_patterns`/`required_files`);
  keep only genuinely-needed custom bits (e.g. the per-variant `filter_func`) or, better, re-upload the
  weights in the standard layout so no custom path is needed.

---

## 🟡 Nits

### 6. Runtime default `[-1]` silently contradicts the documented schema default `[-2]`
- **Category:** Correctness / readability
- **Location:** `models/evo2/app.py:178` (`requested_layers = payload.params.embedding_layers or [-1]`)
- **Detail:** The schema default for `embedding_layers` is `[-2]` (`schema.py:54-57`) and the field has
  no `min_length`, so the `or [-1]` only triggers when a caller passes an explicit empty list — in
  which case it silently uses layer `-1`, a *different* layer than the documented default. Misleading
  and effectively dead.
- **Fix:** drop the `or [-1]` (the schema already supplies a default) or add `min_length=1` to the
  field so an empty list is rejected with a clear 422.

### 7. Unvalidated `mlp_layer` yields an opaque 500 on a bad value
- **Category:** Correctness / error handling
- **Location:** `models/evo2/schema.py:58-61`, `models/evo2/app.py:208-217,230`
- **Detail:** `mlp_layer` is an unbounded `int`. A value with no matching sublayer builds a layer name
  (`blocks.{N}.mlp.l{X}`) that the forward pass won't populate, so `emb_dict[layer_key]` at app.py:230
  raises `KeyError` → unhandled `ServerError` (500) instead of a typed `ValidationError400` (400).
  The param also exposes a StripedHyena-internal detail not present in the sibling `evo`/`esm2`
  encode APIs.
- **Fix:** validate `mlp_layer` against the known sublayers and raise `ValidationError400`, or drop it
  from the public surface and hard-code `l3`.

### 8. `comparison.yaml` ships a template/workflow-residue header
- **Category:** Knowledge graph / internal-reference residue
- **Location:** `models/evo2/comparison.yaml:1-8`
- **Detail:** Retains the scaffolding header ("Generated as part of Phase 3.5 of the
  model-knowledge-base workflow", requirement reminders). esm2's `comparison.yaml` has no such header
  (it starts at `model_slug:`), so this is both an internal-workflow reference and a cross-model
  inconsistency.
- **Fix:** strip lines 1-8 to match esm2.

### 9. Citation venue/ID inconsistency (bioRxiv vs arXiv)
- **Category:** Docs
- **Location:** `models/evo2/README.md:255,271`, BibTeX `:259-266`, `models/evo2/sources.yaml:18-21`
- **Detail:** The paper is labeled "bioRxiv (2025)" but the identifier `2503.11265` is presented as an
  arXiv ID (README "arXiv: 2503.11265"; sources.yaml puts it under `arxiv:`; BibTeX mixes
  `journal={bioRxiv}` with `eprint={2503.11265}`). It can't be both. (Low confidence on the correct
  canonical reference — the Evo2 preprint is on bioRxiv, with a 2025 Nature version also cited in
  sources.yaml.)
- **Fix:** verify and use one consistent venue+identifier across README/BibTeX/sources.yaml.

### 10. `get_build_gpu` return type hint is wrong
- **Category:** Readability / typing
- **Location:** `models/evo2/config.py:92-94`
- **Detail:** Annotated `-> str` but returns `EVO2_VARIANT_RESOURCE_SPECS[...].gpu`, a `ModalGPU` enum.
- **Fix:** annotate `-> ModalGPU` (or return `.value` if a string is actually wanted).

### 11. Residual `pending`/`TODO` placeholders and an internal `qa` env reference (systemic)
- **Category:** Knowledge graph completeness / internal-leakage
- **Location:** `models/evo2/sources.yaml:44` (`snapshot_r2: pending` on a **primary** HF source; also
  applied-lit `pending`s), `models/evo2/README.md:200`, `models/evo2/MODEL.md:41,69` (`<!-- TODO -->`),
  `models/evo2/app.py:325` (docstring "Force deploy in QA/prod")
- **Detail:** Per rubric A.9 these placeholders shouldn't ship; the rubric also lists the internal
  `qa` env under 🔴 leakage. However all of these are **systemic** — esm2 has the same applied-lit
  `pending`s, README/MODEL `TODO`s (even referencing "QA deployment"), and a `"qa" or "main"` deploy
  comment (`models/esm2/app.py:484`). So they're best resolved as a global W14 scrub rather than an
  evo2-specific defect, but flagging for the global reviewer. Note evo2's primary-source
  `snapshot_r2: pending` (line 44) is slightly worse than esm2 (whose primary sources are all
  populated).
- **Fix:** resolve placeholders before public launch; replace the `QA/prod` docstring with a
  neutral environment description; populate or remove the primary `snapshot_r2`.

---

## D. Definition-of-Done audit (model-scoped)

- **Layout / standard files (A.1):** Met — all files present; `config.py` defines a `ModelFamily` with
  `modal_class_name="Evo2Model"`, `action_schemas`, variant axis, tags.
- **Actions closed set (A.2):** Met — `encode`/`log_prob`/`generate`, verbs match intent.
- **Schema field names (A.3):** Met — `items`/`sequence`/`params`, outputs under `results`,
  `embeddings`/`log_prob`/`generated`; `prompt` for the generate seed matches the sibling `evo`.
- **Field descriptions (A.4):** Partially met — all render, but the `log_prob` wording is inaccurate
  (Finding 2).
- **Errors (A.5):** Met — typed `ValidationError400`; no bare `ValueError`/print. Minor gap: unvalidated
  `mlp_layer` (Finding 7).
- **Logging (A.6):** Met — `get_logger`, structured, no `print`, no full-sequence/secret logging.
- **Acquisition (A.7):** **Not met** — build-order rule violated (Finding 1); custom downloader not
  using the canonical helper (Finding 5).
- **Licensing (A.8):** Met — Apache-2.0 LICENSE + NOTICE with attribution, consistent with sources.yaml.
- **Knowledge graph (A.9):** Partially met — broken `nt` reference (Finding 3), template header
  (Finding 8), residual placeholders (Finding 11).
- **Tests (A.10):** Met — `TestSuite` with integration + deployment cases; fixtures lazy-load via
  `fixture.py`; uses programmatic small inputs. (Minor: does not reuse the shared `STANDARD_*` assets
  the way esm2 does, but Evo2 needs DNA inputs and uses tiny literals — acceptable.)

## Verification

Adversarial re-check of the five HIGH-severity findings against the actual code.

- **Finding 1 — HF fallback unusable, `huggingface_hub` never installed: REAL.** `app.py:57-62`
  calls `setup_download_layer` with no `extra_pip_packages`; the download layer installs only
  `boto3/pydantic/requests` (`downloader.py:77-81`) and runs (via `run_function`) *before* the main
  pip block at `app.py:64-83`. The HF fallback (`download.py:119-127` → `acquisition.py:718` →
  `downloads.py:457 from huggingface_hub import snapshot_download`) needs the package; siblings
  `esm1b/app.py:41` and `e1/app.py:62` pass `huggingface_hub==0.26.0` with the exact "needed in
  download layer for HF fallback" comment. `common_requirements` (`config.py:22-29`) lacks it too.
- **Finding 2 — masked-LM "Pseudo-log-likelihood" wording on an autoregressive model: REAL.**
  `schema.py:213` says "Pseudo-log-likelihood…" but `app.py:265-272` computes the exact joint LL
  via `score_sequences(reduce_method="sum")`; `tooling/field_glossary.yaml:58-62` reserves "pseudo"
  for masked LMs, and the sibling `evo/schema.py:125-126` (same call) uses the correct
  "Log-likelihood of the sequence under the model."
- **Finding 3 — `comparison.yaml` references non-existent slug `nt`: REAL.** No `models/nt/` dir and
  no `base_model_slug = "nt"` anywhere; `comparison.yaml` cites `nt` at lines 43, 44, 50, 56, 67
  while the header (5-8) requires all slugs to exist in `models/`.
- **Finding 4 — snapshot NOTE contradicts decorator + README: REAL.** `app.py:94-95` disclaims GPU
  snapshots, yet `app.py:101-102` sets `enable_memory_snapshot=True` + `enable_gpu_snapshot=True`
  and `README.md:233,241` say "GPU snapshot enabled"; the enter methods (`app.py:117-154`) implement
  the CPU two-phase pattern, unlike the GPU-snapshot siblings (`evo/app.py:95-98`, `esm2`). Clear
  internal contradiction.
- **Finding 5 — bespoke downloader duplicates `r2_then_hf`: UNCERTAIN.** The hand-rolled flow in
  `download.py:37-175` does overlap with the canonical `r2_then_hf` (`download_helpers.py:390-460`),
  but the claim it "already does all of this" is overstated: `r2_then_hf` does NOT forward a
  `filter_func` (`download_helpers.py:427-433` omit it, so no per-variant R2 filtering like
  `evo2_filter_func`) and resolves the snapshot path *deterministically* via `build_hf_snapshot_path`
  rather than the wildcard-hash nested glob evo2 uses (`download.py:155-164`) for the manually
  uploaded R2 cache layout. Not a clean drop-in; whether the extra code is truly redundant depends
  on R2 layout specifics I cannot confirm here.
