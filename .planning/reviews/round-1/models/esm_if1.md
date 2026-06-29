# Review — `models/esm_if1/` (Round 1)

## Summary

ESM-IF1 is a single-variant, single-action (`generate`) inverse-folding model. The plumbing is largely
in good shape: it uses the canonical `r2_then_library` acquisition wrapper, self-populates R2, honors
the build-order rule (fair-esm listed in `setup_download_layer(extra_pip_packages=...)` because the
fallback imports `esm.pretrained` at build time), uses the GPU-snapshot `ModelMixinSnap` pattern, and
its glossary-pinned field descriptions (`seed`, `temperature`, `num_samples`) match
`tooling/field_glossary.yaml` verbatim. The 5-file knowledge graph is present and the LICENSE (MIT,
Meta) is consistent with `sources.yaml`. All `comparison.yaml` cross-references resolve to real models.

No 🔴 launch-blockers were found that are unique to this model. The notable issues are a handful of
convention deviations from the house pattern (esm2/dummy) and error-handling that doesn't use the
ratified `BioLMError` taxonomy: caller mistakes surface as 500s, a CUDA-OOM system fault is masked as a
successful empty response, the request `params` field is required despite a description that promises a
default, a response DTO subclasses `RequestModel`, there is dead scaffolding code, and the
`comparison.yaml`/`sources.yaml` carry slug-mismatch and `pending`/TODO residue.

---

## 🟠 should-fix

### 1. `params` is required but its description says it is optional
**category:** schema / public-contract · **location:** `models/esm_if1/schema.py:65-68`

`ESMIF1GenerateRequest.params` is declared `params: ESMIF1GenerateParams = Field(description="Optional
parameters controlling this action (defaults are used when omitted).")` — there is **no**
`default`/`default_factory`, so Pydantic treats `params` as **required**. A caller who omits `params`
(trusting the description) gets a validation error. The house reference does this correctly:
`models/esm2/schema.py:76-79` uses `Field(default_factory=ESM2EncodeRequestParams, ...)`. This is both a
description-vs-behavior contradiction and a cross-model inconsistency.

**fix:** add `default_factory=ESMIF1GenerateParams` to the `params` Field so omitting it yields the
documented defaults.

### 2. Bad input raises bare `NotImplementedError`/`ValueError` → 500 instead of typed `UserError`
**category:** errors (A5) · **location:** `models/esm_if1/app.py:162`, `models/esm_if1/_sample_sequences.py:133,138,147`

Caller-driven failures bypass the ratified taxonomy and surface as 5xx:
- `app.py:162` `raise NotImplementedError("Multichain backbone not supported yet.")` is triggered by the
  user setting `params.multichain_backbone=True`. `models/commons/core/error.py` defines
  `UnsupportedOptionError(UserError)` (code `user.unsupported_option`) precisely for "the caller
  requested an option the model doesn't support."
- `_sample_sequences.py:147` `raise ValueError(f"Chain {chain} not found in input data")` and `:138`
  `raise ValueError("No chains found in the input data.")` are user/data errors (bad `chain` or empty
  structure) that should be `ValidationError400` / `ResourceNotFoundError`.

The rubric (A5) explicitly bans bare `ValueError`/`Exception` for bad input; these all return 500 today.
(Relatedly, consider hiding `multichain_backbone` from the schema entirely until it is implemented,
rather than exposing a param whose only effect is an error.)

**fix:** raise `UnsupportedOptionError` for `multichain_backbone=True`; raise `ValidationError400`
(or `ResourceNotFoundError`) for the chain/empty-structure cases. Import from
`models.commons.core.error`.

### 3. CUDA-OOM is swallowed and returned as a successful empty result
**category:** errors / correctness (A5) · **location:** `models/esm_if1/app.py:187-198`

On `RuntimeError("CUDA out of memory")` the handler appends
`ESMIF1GenerateResponseSample(sequence="", recovery=0.0)` and continues. Because `batch_size == 1`, the
**entire** response becomes `{"results": [[{"sequence": "", "recovery": 0.0}]]}` returned with HTTP 200.
A genuine server/resource fault is thus masked as a valid design with an empty sequence — the caller
cannot distinguish OOM from "the model produced an empty sequence." The rubric requires system faults to
propagate/sanitize, not be caught-and-returned.

**fix:** after `empty_cache()`, raise `ModelExecutionError` (or re-raise) so the gateway returns a 5xx;
drop the synthetic empty sample.

### 4. Dead scaffolding in `_sample_sequences.py`
**category:** simplicity / 10x · **location:** `models/esm_if1/_sample_sequences.py:53-87` and `:90-106`

`_sample_seq_multichain` and `_get_encoder_output` are never imported or called anywhere in the repo
(verified by grep; `app.py` imports only `_sample_seq_singlechain`). `_sample_seq_multichain` is leftover
for the unimplemented multichain path (which short-circuits with `NotImplementedError` before reaching
it), and `_get_encoder_output` is leftover from an `encode`-style action this model does not expose.
~50 lines of dead code that drift and confuse.

**fix:** delete both functions (and the now-unused imports they alone require, if any).

### 5. Response DTO subclasses `RequestModel` instead of `ResponseModel`
**category:** convention / schema · **location:** `models/esm_if1/schema.py:82`

`class ESMIF1GenerateResponseSample(RequestModel)` is a **response** object (nested in
`ESMIF1GenerateResponse.results`). Per `models/commons/model/pydantic.py`, `RequestModel` is
`strict=True, extra="forbid"` while `ResponseModel` is `strict=True, extra="ignore"`. Every analogous
nested response object in the reference uses `ResponseModel` (e.g. `ESM2PredictResponseResult`,
`ESM2LogProbResponseResult`). No runtime break today (the only producer passes explicit kwargs, and
`np.float64` from `np.mean` is a `float` subclass so strict accepts it), but it's the wrong base for a
response and an outlier across the catalog.

**fix:** change the base to `ResponseModel`.

### 6. `comparison.yaml` `model_slug` does not match the canonical slug
**category:** knowledge graph (A9) · **location:** `models/esm_if1/comparison.yaml:10`

`model_slug: "esm_if1"` (underscore) conflicts with `config.py` `base_model_slug = "esm-if1"`,
`sources.yaml` `model_slug: esm-if1`, and the docs. Across the repo, `comparison.yaml`/`sources.yaml`
use the public hyphenated slug (`esm2`, `mpnn`, `thermompnn-d`, `msa-transformer`, `dna-chisel`). This
one uses the Python-module form.

**fix:** set `model_slug: "esm-if1"`.

### 7. Knowledge-graph completeness: `pending` placeholders, `unknown2024.pdf`, and a TODO comment
**category:** knowledge graph (A9) · **location:** `models/esm_if1/sources.yaml:46-47,55-56,65,74-75,84-85`; `:64`; `models/esm_if1/BIOLOGY.md:60`

Multiple `applied_literature` entries carry `pdf_r2: pending` / `md_r2: pending`, one archive is named
`.../applied/papers/unknown2024.pdf` (the ProteinBench paper, arXiv 2409.06744 — name it properly), and
`BIOLOGY.md:60` ships a literal `<!-- TODO: Add specific applied literature entries from sources.yaml as
they are populated -->`. The rubric requires the knowledge graph to ship free of `TODO`/`pending`/
template residue.

**fix:** archive (or remove the entries until archived) so no `pending` remains; rename the
`unknown2024` PDF; resolve the `BIOLOGY.md` TODO (it has an "Applied Use Cases" section already — either
populate from `sources.yaml` or delete the comment).

---

## 🟡 nits

### 8. `comparison.yaml` carries generator/template header boilerplate
**category:** consistency · **location:** `models/esm_if1/comparison.yaml:1-9`

Lines 1-9 are a template header ("Generated as part of Phase 3.5 of the model-knowledge-base workflow",
plus the requirements checklist). The reference `models/esm2/comparison.yaml` has no such header — it
starts directly at `model_slug:`. The "Phase 3.5 … workflow" line references an internal authoring
process and reads as scaffolding in a shipped file.

**fix:** drop the header block to match the esm2 convention.

### 9. OOM error log is non-lazy, logs input bytes, and mislabels a PDB as "sequences"
**category:** logging (A6) · **location:** `models/esm_if1/app.py:190`

`logger.error(f"Failed (CUDA out of memory) on batch with sequences: {pdb_string[:500]}.")` uses an
f-string (the rest of the file correctly uses lazy `%s` args), dumps up to 500 chars of the input
structure into the log, and calls a PDB string "sequences." PDB coords aren't secret, but this is
inconsistent with the structured-logging convention and the "don't log raw input" guidance.

**fix:** `logger.error("Failed (CUDA out of memory) processing input structure.")` — drop the payload
slice and use a lazy message.

### 10. Params class naming deviates from the house pattern
**category:** naming · **location:** `models/esm_if1/schema.py:24`

`ESMIF1GenerateParams` vs the reference's `ESM2EncodeRequestParams` (`<Model><Action>RequestParams`).
Cosmetic, but uniform naming helps the "diff is the science, not the plumbing" goal.

### 11. Private fair-esm API used in the download fallback
**category:** robustness · **location:** `models/esm_if1/download.py:58`

`esm.pretrained._download_model_and_regression_data(ESM_IF1_MODEL_NAME)` calls a private (underscore)
function. It's well-justified and well-commented (the full loader needs `torch_geometric`/`biotite`/
`scipy` not present in the download layer), and fair-esm is pinned to a fixed commit, so the risk is
low. Noting for awareness only.

### 12. `# Force deploy to "qa" or "main" environment:` comment (repo-wide, not esm_if1-specific)
**category:** internal leakage (C) · **location:** `models/esm_if1/app.py:208`

The rubric lists the internal `qa` env name as a 🔴 leak. However, "qa"/"main" are the real deployment
environment names baked into `models/commons/modal/deployment.py` (`get_environment_name()`, the
`--force-deploy` help text), and this exact comment appears verbatim in all 30 model `app.py` files
including the reference `models/esm2/app.py:484`. So this is **not** an esm_if1 deviation — it conforms
to the house template. Flagging for the global reviewer to decide whether the deployment-env naming
should be scrubbed catalog-wide before launch, rather than as a per-model fix.

---

## Definition-of-Done notes
- **Acquisition (W-acq / A7):** met — `r2_then_library` + self-populating R2 + build-order rule honored
  and documented.
- **Actions/taxonomy (W7):** partially met — action verb (`generate`) is correct and from the closed
  set, but the `UserError`/`ServerError` error taxonomy is **not** applied to this model's input/fault
  paths (findings #2, #3).
- **Logging (W6):** mostly met — `get_logger`, no `print`; one non-lazy/error-payload log (#9).
- **Field-doc consistency (A4):** met — pinned fields match the glossary verbatim; all fields render.
- **Per-model hardening (W5):** partially met — schema/error/dead-code items above suggest the W5 pass
  for this model is incomplete.

## Verification

Adversarial re-check of the seven HIGH-severity findings against the actual source.

1. **params required but description promises a default — REAL.** `schema.py:66-68` declares `params: ESMIF1GenerateParams = Field(description="...defaults are used when omitted.")` with no `default`/`default_factory`, so Pydantic v2 treats it as required; reference `esm2/schema.py:76-79` uses `default_factory=ESM2EncodeRequestParams`. Description-vs-behavior contradiction + cross-model inconsistency confirmed.
2. **Caller mistakes raise bare NotImplementedError/ValueError → 500 — REAL.** `app.py:162` raises bare `NotImplementedError` (not in `decorator.py` `ERROR_MAP`); `_sample_sequences.py:138,147` raise builtin `ValueError` (not pydantic `ValidationError`, the only mapped one). All fall through `_handle_errors` to the generic 500 branch (`decorator.py:454-462`), bypassing `UnsupportedOptionError`/`ValidationError400` in `error.py:38-47`.
3. **CUDA-OOM swallowed as successful empty result — REAL.** `app.py:187-198` catches `RuntimeError("CUDA out of memory")`, appends `ESMIF1GenerateResponseSample(sequence="", recovery=0.0)` and continues; with `batch_size=1` the whole response is one empty sample at HTTP 200, indistinguishable from a real empty output.
4. **Dead scaffolding functions — REAL.** `grep` confirms `_sample_seq_multichain` (`_sample_sequences.py:53`) and `_get_encoder_output` (:90) appear only at their definitions — no importers/callers; `app.py:140` imports only `_sample_seq_singlechain`. ~50 dead lines.
5. **Response DTO subclasses RequestModel — REAL.** `schema.py:82` `class ESMIF1GenerateResponseSample(RequestModel)` is nested in the response (`results: list[list[...]]`, :91/:95); every analogous esm2 nested result (`ESM2EncodeResponseResult`/`ESM2PredictResponseResult`/`ESM2LogProbResponseResult`, schema.py:143/191/209) uses `ResponseModel`. Wrong base + catalog outlier; no runtime break (built via explicit kwargs; np.float64 ⊂ float passes strict).
6. **comparison.yaml model_slug mismatch — REAL (one supporting claim overstated).** `comparison.yaml:10` `model_slug: "esm_if1"` (underscore) conflicts with `sources.yaml:1 esm-if1` and `config`/`ESMIF1Params.base_model_slug = "esm-if1"` — the canonical public slug is hyphenated. NOTE: the finding implies this is unique, but `dna_chisel/comparison.yaml` has the identical underscore-vs-hyphen mismatch, so esm_if1 is not the sole offender; the cited mismatch itself is nonetheless real and verifiable.
7. **Knowledge-graph residue (pending/unknown2024.pdf/TODO) — REAL.** `sources.yaml` carries `pdf_r2/md_r2: pending` at :46-47, :55-56, :65, :74-75, :84-85; `:64` archives the ProteinBench paper (arXiv 2409.06744, matching :58) as `applied/papers/unknown2024.pdf`; `BIOLOGY.md:60` ships the literal `<!-- TODO: Add specific applied literature entries... -->`. All confirmed verbatim.
