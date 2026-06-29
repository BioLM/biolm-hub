# Review — `models/esmc/` (Round 1)

## Summary

ESM C (300M only) is a clean, well-structured port that closely follows the ESM2 house pattern:
three canonical actions (`encode` / `predict` / `log_prob`), correct schema field names and
glossary-pinned descriptions (`tooling/check_schema_docs.py` passes), shared test assets
(`STANDARD_PROTEIN`) with lazy fixtures, a proper per-model `LICENSE` that honours the
EvolutionaryScale Cambrian Open attribution obligations, and a thoughtful, accurate knowledge
graph. The numerics in all three actions are correct: I traced the BOS/EOS slicing, the canonical-AA
index map, and (against the local `esm` source) confirmed that `_detokenize` collapses `<mask>` →
`"_"` and strips BOS/EOS, so `predict`'s `sequence_tokens` stay 1:1 aligned with `logits`. No
internal-reference leakage (`biolm-modal` / `qa` / `.planning`) in any shipped file.

The one launch-gating issue is an acquisition build-order bug: the HuggingFace fallback's
`huggingface_hub` import is installed in the wrong image layer, so a cold-R2 (first/self-population)
deploy will fail to build. Everything else is a convention/polish item.

Reference points used: `models/esm2/` (house pattern, near-identical family) and `models/dummy/`
(template); `models/commons/modal/downloader.py` + `storage/download_helpers.py` (acquisition);
`tooling/field_glossary.yaml` (pinned descriptions).

---

## 🔴 Must-fix

### 1. `huggingface_hub` is installed in the runtime layer, not the download layer — cold-R2 self-population deploy fails to build
- **category:** Acquisition / build-order rule (Rubric A.7)
- **location:** `models/esmc/app.py:55-69`
- **detail:** `setup_download_layer(...)` runs the weight download *at image-build time* via
  `image.run_function(_run_download_with_params, ...)` (see `models/commons/modal/downloader.py:111`).
  On an R2 cache miss, `download_model_assets` → `r2_then_hf` → `_acquire_huggingface_hub` →
  `download_from_hf`, which does `from huggingface_hub import snapshot_download`
  (`models/commons/storage/downloads.py:457`). But the download layer only installs
  `boto3 / pydantic / requests` (`downloader.py:77-85`); esmc passes **no** `extra_pip_packages`,
  and `huggingface_hub==0.36.2` is instead added later in the main image layer
  (`app.py:66-69`), which executes *after* the download `run_function`. The base image
  `pytorch/pytorch:2.6.0-cuda12.4-cudnn9-runtime` does not ship `huggingface_hub`, and none of
  `boto3/pydantic/requests` pull it transitively. Result: the first-ever deploy (empty R2 = the
  self-population path the catalog depends on) raises `ModuleNotFoundError: huggingface_hub` and the
  build fails. Warm-cache redeploys are unaffected (the R2-primary read needs only path helpers), which
  is why this can hide. This is exactly the build-order rule the rubric calls out, and the house
  reference does it correctly: `models/esm2/app.py:47-56` passes its fallback's build-time import
  (`fair-esm`) via `setup_download_layer(extra_pip_packages=[...])`. The inline comment at
  `app.py:67-68` ("Required for HF fallback in download.py") is also misplaced — `download.py` runs in
  the download layer, not the runtime layer.
- **suggested fix:** Pass the fallback import to the download layer:
  `setup_download_layer(image, ..., extra_pip_packages=["huggingface_hub==0.36.2"])`. Keep a runtime
  `huggingface_hub` for `ESMC.from_pretrained` (it is also pulled transitively by `esm==3.1.3`), and
  fix/remove the misleading comment.

---

## 🟠 Should-fix

### 2. `encode` silently drops out-of-range `repr_layers` (no typed error; diverges from esm2; docs say "clipped")
- **category:** Errors / cross-model consistency (Rubric A.5, C)
- **location:** `models/esmc/app.py:200-205` (and `MODEL.md:99`)
- **detail:** Requested layers are filtered with `if 0 <= pos_lyr < n_layers: layers_to_use.append(...)`
  and anything out of range is silently discarded. A request like `repr_layers=[0, 99]` returns only
  layer 0; `repr_layers=[99]` returns an **empty** `embeddings`/`per_token_embeddings` list with no
  error — a silent, incomplete-output contract violation. The house reference raises a typed error for
  the same condition (`models/esm2/app.py:244-248`, `ValidationError400`). esmc imports no error type at
  all. `MODEL.md:99` additionally mis-describes the behaviour as "silently clipped" (it is dropped, not
  clamped to the nearest valid layer).
- **suggested fix:** Validate `repr_layers` against the hidden-state count and raise the typed
  `ValidationError400` (import from `models.commons.core.error`) as esm2 does; correct the MODEL.md
  wording to match.

---

## 🟡 Nits

### 3. Wrong inline memory comment in resource spec
- **category:** Readability
- **location:** `models/esmc/config.py:41`
- **detail:** `memory=24 * 1024,  # 8 GB` — `24 * 1024` is 24 GB, and README/MODEL both correctly state
  24 GB. The `# 8 GB` comment is a copy-paste leftover.
- **suggested fix:** Change the comment to `# 24 GB`.

### 4. README citation/BibTeX uses a non-existent blog title
- **category:** Docs accuracy
- **location:** `models/esmc/README.md:284` and `:290` (also the `:3` one-line summary phrasing)
- **detail:** The References entry and BibTeX title read "ESM Cambrian: Next-generation protein
  representation models", but the actual EvolutionaryScale blog post (correctly captured in
  `sources.yaml:21`) is titled "ESM Cambrian: Revealing the mysteries of proteins with unsupervised
  learning". The citation title is paraphrased rather than real.
- **suggested fix:** Use the real blog title in the README reference and BibTeX so it matches
  `sources.yaml`.

### 5. Minor inference inefficiencies (redundant tokenize; per-residue lookups)
- **category:** Simplicity / efficiency
- **location:** `models/esmc/app.py:262-266` and `:316-321`
- **detail:** (a) `predict` calls `_forward_pass` (which already runs `self.model._tokenize`) and then
  re-tokenizes the same inputs (`app.py:265`) only to feed `_detokenize`. (b) `log_prob` does a Python
  per-residue loop calling `self.model.tokenizer.convert_tokens_to_ids(aa)` and
  `self.canonical_idxs.index(aa_idx)` for every position; since inputs are validated to be unambiguous
  AAs, a precomputed `{aa: column}` map (as esm2 builds at `models/esm2/app.py:451`) is simpler and
  avoids O(L) tokenizer/`list.index` calls. Both are minor (tokenize is cheap vs. the forward pass) and
  rely on `esm`'s private `_tokenize`/`_detokenize` — acceptable given the pinned `esm==3.1.3`.
- **suggested fix:** Optionally have `_forward_pass` also return the `input_ids` for reuse, and replace
  the log_prob loop's lookups with a precomputed residue→column dict.

### 6. Knowledge-graph placeholder residue and one likely factual slip
- **category:** Knowledge graph completeness (Rubric A.9)
- **location:** `models/esmc/sources.yaml:60` (+ `:29,30,34,55,64,73,83,94` `pending`/`unknown`),
  `MODEL.md:56`, `BIOLOGY.md:72`
- **detail:** `sources.yaml:60` says KaML-ESM "Trains ... using **ESM Cambrian 6B** embeddings" — there
  is no public ESM C 6B variant (only 300M/600M); this looks like a factual error to verify/correct.
  Separately, the file ships placeholder residue (`pdf_r2: pending`, `md_r2: pending`,
  `snapshot_r2: pending`, `commit: ''`, applied-paper filenames `unknown2025b.pdf`/`unknown2025c.pdf`),
  and `MODEL.md`/`BIOLOGY.md` ship `<!-- TODO ... -->` comments. The `pending`/`unknown`/TODO patterns
  are catalog-wide (present in esm2 and ~all 46 models), so this is low-severity here, but the launch
  DoD calls for no TODO/placeholder residue in shipped files — worth a sweep before public.
- **suggested fix:** Verify the "6B" claim (likely 600M or a fine-tuned larger model) and fix it; resolve
  or strip the `pending`/`unknown`/TODO placeholders as part of the pre-launch knowledge-graph pass.

---

## Definition-of-Done notes
- **Layout / actions / schema names / field descriptions:** met. All standard files present;
  closed-set verbs (`encode/predict/log_prob`) match intent; field names uniform with esm2; descriptions
  render and match `field_glossary.yaml` (`check_schema_docs.py` → "schema docs OK").
- **Errors/logging:** mostly met — `get_logger`, no `print`, no catch-and-print; gap is the missing typed
  validation for out-of-range `repr_layers` (Finding 2).
- **Acquisition / self-population:** **not met** on cold R2 due to Finding 1 (build-order).
- **Licensing:** met — per-model `LICENSE` consistent with `sources.yaml`; Cambrian Open attribution
  obligations documented; the maintainer note honestly flags that it is a summary, not the full text.
- **Tests:** met — `TestSuite` with integration + deployment cases, lazy fixtures, shared `STANDARD_PROTEIN`.
- **No internal leakage:** met.

## Verification

Adversarial re-check of the two high-severity findings against the actual code.

- **Finding 1 — huggingface_hub installed in runtime layer, not download layer (cold-R2 deploy build fails): REAL.**
  Confirmed the full chain. `setup_download_layer` runs the weight download at image-BUILD time via
  `image.run_function(_run_download_with_params, ...)` (`models/commons/modal/downloader.py:111`), and that
  layer installs only `boto3/pydantic/requests` (`downloader.py:77-85`). `models/esmc/app.py:55-60` passes
  **no** `extra_pip_packages`; `huggingface_hub==0.36.2` is added only in the later runtime layer
  (`app.py:66-69`), which Modal builds *after* the download `run_function`. On an empty-R2 (self-population)
  deploy, `esmc/download.py:49` → `r2_then_hf` → `download_with_fallback` → `_acquire_huggingface_hub`
  (`acquisition.py:718-728`) → `download_from_hf` does `from huggingface_hub import snapshot_download`
  (`models/commons/storage/downloads.py:457`) at build time → `ModuleNotFoundError` (base pytorch image and
  boto3/pydantic/requests do not provide `huggingface_hub`). Decisive corroboration: **every other**
  `r2_then_hf` model (dsm, dnabert2, esm1b, esm1v, e1, igbert, igt5, prostt5, zymctrl, spurs, omni_dna)
  passes `huggingface_hub` via `extra_pip_packages` to `setup_download_layer`, with explicit comments (e.g.
  `esm1b/app.py:35` "needed in download layer for HF fallback when R2 cache is empty"); esmc is the lone
  outlier. The near-identical `e1` (same `huggingface_hub.constants` reload) correctly passes it to both
  layers (`e1/app.py:62` + `:74`). The `app.py:67-68` comment "Required for HF fallback in download.py" is
  also misplaced — download.py runs in the download layer, not the runtime layer.

- **Finding 2 — encode silently drops out-of-range repr_layers (no typed error; diverges from esm2; docs say "clipped"): REAL.**
  `models/esmc/app.py:202-205` filters with `if 0 <= pos_lyr < n_layers: layers_to_use.append(pos_lyr)`,
  silently discarding out-of-range entries; `repr_layers=[99]` yields `layers_to_use=[]` → an empty
  `embeddings`/`per_token_embeddings` list with no error. The schema does not bound the field
  (`schema.py:44-47`, `repr_layers: list[int]` with no range validator), so bad values reach the handler.
  The house reference raises a typed `ValidationError400` for the same condition
  (`models/esm2/app.py:244-248`), whereas esmc imports no error type at all (`app.py:1-36` has no
  `from models.commons.core.error import ...`). `MODEL.md:99` mis-describes the behavior as "silently
  clipped" — the code drops the entry, it does not clamp it to the valid range.
