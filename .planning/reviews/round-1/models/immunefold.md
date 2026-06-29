# Review — `models/immunefold/` (Round 1)

## Summary

ImmuneFold is a well-structured port. The plumbing largely matches the house pattern: a
`ModelFamily` with `modal_class_name`, two variants on a single `MODEL_TYPE` axis, the canonical
`fold` action, typed `ValidationError400` (a `UserError`/`BioLMError` subclass) for caller mistakes,
`get_logger` (no `print`), `r2_then_urls` acquisition that self-populates R2 with the full asset set,
and a `TestSuite` with lazy fixtures. All request/response field descriptions **render** in
`model_json_schema()` (verified), and the `ptm` description matches `field_glossary.yaml` verbatim.
Antibody/TCR field names (`heavy_chain`/`light_chain`/`tcr_alpha`/`tcr_beta`) are consistent with the
sibling `immunebuilder` model, and nanobody = lone `heavy_chain` (no `vhh`), per standard.

No internal-reference leaks (`biolm-modal`, `qa`, `.planning`, internal domains) and no secrets were
found in shipped files. License is Apache-2.0, consistent with `sources.yaml`. No 🔴 must-fix
correctness/security/license-broken defects surfaced. The findings below are convention,
accuracy, and cleanup issues — several shared with the other antibody models (e.g. the excluded
`propermab` cross-reference).

---

## 🟠 Should-fix

### 1. The `device` config override is dead — the loader reads `cfg.gpu`, not `cfg.device`
- **Category:** Correctness / dead code
- **Location:** `app.py:184` (and the absent override in `fold`, `app.py:298-303`)
- **Detail:** `setup_model` builds the config with `overrides={... "device": str(self.device)}` and the
  comment says "Load directly on GPU device." But `external/inference.py` reads the device from
  `cfg.gpu` in every code path (`load` line 195, `predict_with_model` line 228, `predict` line 162) —
  `cfg.device` is never read. So the runtime-detected device (`get_torch_device()`) does not control
  placement; the model loads on whatever `gpu` the cloned Hydra YAML hard-codes. `fold()`'s overrides
  also never set `gpu`/`device`, so the same applies there. It works in production only because the
  YAML default already points at CUDA, but `self.device` is effectively logging-only and the override
  is misleading (and a latent bug if Modal ever allocates a different device or the YAML default
  changes).
- **Fix:** Override the key the loader actually consumes: `overrides["gpu"] = str(self.device)` in both
  `setup_model` and `fold` (or drop the dead `device` override and document that placement comes from
  the YAML's `gpu`).

### 2. `ptm` is described as pure pTM but returns a blended ipTM score for multi-chain inputs
- **Category:** Field-description accuracy / cross-model consistency
- **Location:** `schema.py:234-235` vs `external/inference.py:106-116`
- **Detail:** `_compute_ptm(..., chain_id=batch["chain_id"], interface=True)` returns
  `0.8 * iptm + 0.2 * ptm` whenever `chain_id` is multi-chain. The dominant ImmuneFold inputs *are*
  multi-chain (paired VH/VL antibody, four-chain TCR-pMHC), so the value returned in the common case is
  an ipTM-weighted blend, not the pure pTM the field description claims ("Predicted TM-score (pTM) for
  the overall structure (0–1)."). Compare `models/boltz/schema.py:700`, where the equivalent blended
  score is named/described explicitly as `(0.8 × complex_plddt + 0.2 × iptm)`.
- **Fix:** Either describe the blend in the `ptm` field description (note it becomes
  `0.8·ipTM + 0.2·pTM` for multi-chain complexes), or surface a separate `iptm` field and keep `ptm`
  pure, matching the boltz/rf3 convention.

### 3. Knowledge graph references `propermab`, which is EXCLUDED from the public catalog
- **Category:** Knowledge-graph consistency
- **Location:** `comparison.yaml:28,55-57`; `BIOLOGY.md:54,67`
- **Detail:** `comparison.yaml` lists `propermab` as a structured `complements` entry (`- model:
  "propermab"`) and both files describe a "ProperMAB feature extraction" workflow. Per
  `.planning/02_MODEL_INCLUSION_MATRIX.md:63`, propermab was **EXCLUDED (2026-06-28)** as
  NonCommercial/Academic-Only (Regeneron) and will not ship. The `model: "propermab"` slug therefore
  dangles — no such model exists in `models/`. (This is systemic: `ablang2`, `abodybuilder3`, and
  `immunebuilder` comparison.yaml files reference it too — worth a global sweep.)
- **Fix:** Remove the `propermab` `complements` entry and the ProperMAB workflow prose, or replace with
  an included model (e.g. `antifold`, which is already present). Verify every `model:` slug in
  `comparison.yaml` resolves to a shipped `models/<slug>/`.

### 4. Dead, contradictory `environment.yml` unique to this model
- **Category:** Cleanup / consistency
- **Location:** `environment.yml` (whole file); referenced only in prose at `README.md:186`
- **Detail:** `immunefold` is the **only** model in the repo carrying an `environment.yml`; no code, CI,
  or Makefile references it. Worse, it actively contradicts the real build: it pins
  `pytorch::pytorch=1.12.*` and `cudatoolkit==11.3`, but `app.py:60-61` explicitly comments that the
  conda env's torch 1.12 is *not* what runs and installs `torch==2.1.2` + CUDA 12 via `uv_pip_install`.
  `README.md:186` ("Dependencies: Pinned to specific conda environment (`environment.yml`)") perpetuates
  the false impression that this file drives the build.
- **Fix:** Delete `environment.yml` and update `README.md:186` to describe the actual Modal image build
  (micromamba bioconda tools + pinned pip installs).

### 5. `max_unpaired_sequence_len = 512` is unused; README's "512 unpaired" limit is not enforced
- **Category:** Dead code / doc-code mismatch
- **Location:** `schema.py:32`; `README.md:177`, `MODEL.md` (Memory & Compute table)
- **Detail:** `ImmuneFoldParams.max_unpaired_sequence_len = 512` is never referenced (unlike `igbert`/
  `igt5`, which actually use the same attribute). Every chain field caps at `max_sequence_len = 256`,
  including a lone (unpaired) `heavy_chain` for nanobodies. `README.md:177` advertises "Max sequence
  length | 256 per chain (512 unpaired)", a limit the schema never applies — a >256-residue nanobody is
  rejected despite the docs.
- **Fix:** Either enforce `max_unpaired_sequence_len` on the lone-`heavy_chain` path, or delete the
  unused param and correct the README to say a flat 256 per chain.

### 6. Inferred copyright unresolved + internal "NOTE TO MAINTAINERS" ships in the public LICENSE
- **Category:** Licensing / launch readiness
- **Location:** `LICENSE:196-202`
- **Detail:** The LICENSE appendix copyright ("Copyright 2024 CarbonMatrix Lab") is inferred — the
  bundled `NOTE TO MAINTAINERS -- COPYRIGHT HOLDER INFERRED` block states the upstream LICENSE left the
  holder/year as the unfilled placeholder and says to "confirm the exact copyright attribution with the
  upstream authors before public release." Per rubric A8 the inference is at least *flagged* (good), but
  it remains an unresolved launch item, and shipping an internal maintainer-process note inside a public
  LICENSE file is undesirable.
- **Fix:** Confirm the holder/year with the upstream authors, then replace the inferred line with the
  confirmed attribution and remove the `NOTE TO MAINTAINERS` block from the shipped LICENSE.

### 7. `BIOLOGY.md` ships a TODO placeholder comment
- **Category:** Knowledge-graph completeness
- **Location:** `BIOLOGY.md:56`
- **Detail:** `<!-- TODO: Add specific applied literature citations from post-publication studies -->`
  is exactly the kind of stray `TODO` placeholder rubric A9 forbids in shipped knowledge-graph files.
- **Fix:** Remove the comment (and add the applied-lit citations if/when available, or just drop it
  since `sources.yaml` already has `applied_literature: []`).

---

## 🟡 Nits

### 8. Redundant boolean in `_pre_process_payload`
- **Location:** `app.py:211-224`
- **Detail:** `request_kind = payload.items[0]._kind`, so the OR-ed clause
  `(request_kind == ANTIBODY and self.model_type != ANTIBODY) or (request_kind == TCR and ...)` is fully
  subsumed by the preceding `any(item._kind != self.model_type for item in payload.items)`. If all items
  match the variant, both branches are false; if any differs, `any()` already triggers. The clause adds
  nothing.
- **Fix:** Reduce to `if any(item._kind != self.model_type for item in payload.items): raise ValidationError400(...)`.

### 9. Shadowing the `type` builtin
- **Location:** `app.py:308, 313, 319` (`type = "nb"` / `"ab"` / `"tcr"`)
- **Detail:** Rebinds the builtin `type`; ruff `A001`-class smell.
- **Fix:** Rename to `mol_type` (and update `overrides["type"] = mol_type`).

### 10. `full_plddt` diverges from `esmfold`'s `mean_plddt` for the same concept
- **Location:** `schema.py:237`
- **Detail:** Both are the masked mean of per-residue pLDDT, but `esmfold` calls it `mean_plddt` while
  ImmuneFold uses upstream jargon `full_plddt`. The glossary intentionally does not pin pLDDT field
  names, so this is allowed — but the repo's north star is uniformity, and `mean_plddt` is clearer.
  (Note also: ImmuneFold pLDDT is 0–100 while esmfold's is 0–1 — both documented, just different scales.)
- **Fix:** Consider renaming to `mean_plddt` (keep a Pydantic alias for back-compat).

### 11. Docstring typos and `raise e`
- **Location:** `app.py:277, 280` (stray leading `"` on the Parameters/Returns lines); `app.py:359`
- **Detail:** The `fold` docstring has stray leading double-quotes (`"payload ...`, `"ImmuneFoldPredictResponse:`).
  Separately, `raise e` (line 359) rewrites the traceback; bare `raise` preserves it.
- **Fix:** Remove the stray quotes; change `raise e` to `raise`.

### 12. LICENSE NOTICE URL branch (`ImmuneFold`) disagrees with `sources.yaml`/`README` (`main`)
- **Location:** `LICENSE:192` (`/blob/ImmuneFold/LICENSE`) vs `sources.yaml:5` and `README.md:192` (`/blob/main/LICENSE`)
- **Detail:** Two different branch refs for the same upstream LICENSE; at least one is likely a dead link.
- **Fix:** Pick the branch/commit that actually resolves (ideally the pinned commit
  `b6d916fc…`) and use it consistently.

### 13. Primary paper `pdf_r2`/`md_r2` are `pending`, `arxiv` empty
- **Location:** `sources.yaml:22-30`
- **Detail:** Sibling models (`esm2`, `esmfold`) archive their *primary* paper PDF/MD; here the primary
  paper is `pending` (documented: bioRxiv blocks programmatic download) with an empty `arxiv`. The repo
  snapshot is present, so this is a KG-completeness gap rather than a leak.
- **Fix:** Archive the bioRxiv PDF/MD via the browser-based path and fill `pdf_r2`/`md_r2`, or document
  the gap as intentional in the W-acq tracking.

### 14. Robustness smells: stack-trace string matching and global `logging.basicConfig`
- **Location:** `app.py:236-243` (`_handle_domain_numbering_error`); `app.py:174`
- **Detail:** Classifying user-vs-server errors by grepping the traceback string
  (`"base_dataset.py"`, `"make_domain"`, …) is fragile to upstream refactors — defensible as a pragmatic
  way to turn opaque assertions into 400s, but brittle. Separately, `logging.basicConfig(level=INFO)`
  inside `setup_model` mutates global logging from model code.
- **Fix:** If feasible, catch the specific upstream exception type or check a sentinel attribute instead
  of substring-matching; move/remove the `basicConfig` call (the repo standard is `get_logger`).

---

## Definition-of-Done audit (per-model, W5)
- **Layout / 5-file KG / config ModelFamily:** Met (all standard files + `download.py` present;
  `config.py` defines `MODEL_FAMILY` with `modal_class_name`, `action_schemas`, variants, tags).
- **Actions canonical:** Met — `fold` (a folding model that folds, not `predict`).
- **Schema field names uniform + aliases:** Met — `heavy_chain`/`light_chain`/`tcr_*`, single-letter
  legacy aliases via `AliasChoices`, batch under `items`/`results`.
- **Field descriptions render + glossary match:** Met (verified via `model_json_schema()`); `ptm`
  matches glossary. One accuracy caveat (finding #2).
- **Errors typed:** Met — `ValidationError400` (`UserError`→`BioLMError`); system faults re-raised.
- **Logging:** Met — `get_logger`, no `print`. Minor `basicConfig` nit (#14).
- **Acquisition:** Met — `r2_then_urls`, self-populates R2 with the full asset set;
  `download_model_assets` convention honored; no build-time library import → no `extra_pip_packages`
  needed.
- **Licensing:** Partially met — Apache-2.0 consistent, but inferred copyright unresolved and a
  maintainer note ships in LICENSE (#6); branch URL inconsistency (#12).
- **Knowledge graph consistent/complete:** Partially met — slug/display_name consistent, but TODO
  placeholder (#7), excluded-`propermab` ref (#3), and `pending` primary paper (#13).
- **Tests:** Met — `TestSuite` with integration + deployment cases; fixtures are R2 filename constants
  (no module-scope R2/network).

## Verification

Adversarial re-check of the 7 HIGH-severity findings against the actual source. All verdicts: **real**.

1. **`device` override dead (loader reads `cfg.gpu`)** — **real.** `app.py:184` sets override
   `"device": str(self.device)`, but `external/inference.py` reads device only via `cfg.gpu` in all
   three paths (`load`:195, `predict_with_model`:228, `predict`:162); `cfg.device` is never read.
   `fold()` overrides (`app.py:298-303`) set no `gpu`/`device`. No code maps `device`→`gpu`. Placement
   comes from the YAML `gpu` default, not the runtime `get_torch_device()` — latent device-placement bug.

2. **`ptm` field claims pure pTM, returns blended ipTM for multi-chain** — **real.**
   `inference.py:110-112` returns `0.8*iptm + 0.2*ptm` whenever `interface and chain_id is not None`;
   called with `interface=True, chain_id=batch['chain_id']` (lines 122-123, 134-135). Dominant inputs are
   multi-chain (paired VH/VL, 4-chain TCR-pMHC), so the common-case value is a blend, contradicting
   `schema.py:234-235` ("Predicted TM-score (pTM) for the overall structure").

3. **KG references excluded `propermab`** — **real.** `comparison.yaml:55-57` has structured
   `- model: "propermab"` complements entry; line 28 and `BIOLOGY.md:54,67` describe ProperMAB.
   `02_MODEL_INCLUSION_MATRIX.md` propermab row = **EXCLUDE 2026-06-28** (Non-Commercial/Regeneron);
   `models/propermab/` does not exist (confirmed). Systemic — also dangling in immunebuilder,
   abodybuilder3, ablang2 comparison.yaml.

4. **Dead, contradictory `environment.yml`** — **real.** `find` confirms immunefold is the only model
   with an `environment.yml`; repo-wide grep shows it is referenced only in prose at `README.md:186`
   (no build/CI/Makefile). It pins `pytorch=1.12.*` / `cudatoolkit==11.3.*` (lines 21,11), while
   `app.py:60-61,71` explicitly install `torch==2.1.2` + CUDA 12 and comment the conda torch 1.12 is NOT
   what runs. README:186 perpetuates the false impression.

5. **`max_unpaired_sequence_len = 512` unused; README's 512-unpaired limit unenforced** — **real.**
   `schema.py:32` defines it but grep shows it is never referenced in immunefold (igbert:86,168 /
   igt5:83 do use theirs). Every chain field caps at `max_sequence_len=256` (e.g. line 73), including the
   lone nanobody `heavy_chain`. `README.md:177` advertises "256 per chain (512 unpaired)" — never applied.

6. **Inferred copyright unresolved + internal maintainer note in public LICENSE** — **real.**
   `LICENSE:196-202` ships the "NOTE TO MAINTAINERS -- COPYRIGHT HOLDER INFERRED" block stating the
   holder/year were inferred and to "confirm ... before public release." Verifiably present in the
   shippable LICENSE; unresolved launch item.

7. **BIOLOGY.md TODO placeholder** — **real.** `BIOLOGY.md:56` is exactly
   `<!-- TODO: Add specific applied literature citations from post-publication studies -->`.
