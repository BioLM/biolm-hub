# Review — `models/progen2/`

**Reviewer:** independent round-1 (rubric A–D)
**Verdict:** Solid, well-documented model with a thoughtful custom downloader and a faithful vendored
implementation. The *plumbing* matches the house pattern closely. Launch is gated by one
must-fix (shipped `TODO` residue / internal-env leak in public docs) plus a cluster of should-fix
items: a documentation/factual error about the vocabulary, a `params`-required contract mismatch, a
`temperature=0.0` crash path, and a response DTO that inherits `RequestModel`.

The model implements exactly one canonical action (`generate`) with a uniform schema, a documented
custom acquisition strategy that self-populates the public bucket, a permissive BSD-3-Clause license
consistent with `sources.yaml`, and accurate bidirectional-likelihood docs that match
`external/likelihood_utils.py`. The five knowledge-graph files are internally consistent on
slug/display-name and rich in content.

---

## 🔴 Must-fix before launch

### 1. Shipped `TODO` placeholders in public docs (DoD/knowledge-graph completeness; two leak the internal `qa` env)
- **Category:** Knowledge graph / open-source readiness / DoD
- **Location:** `models/progen2/README.md:171,191,202`, `models/progen2/MODEL.md:228`,
  `models/progen2/BIOLOGY.md:59`
- **Detail:** Five visible `<!-- TODO ... -->` authoring notes ship in public-facing markdown. The
  knowledge-graph DoD (rubric A9) requires "no stray `TODO`/`pending`/template placeholders
  shipping." Two of them additionally reference the internal QA environment — `README.md:202` and
  `MODEL.md:228` both say *"profile on QA deployment"* — which the rubric flags as an internal-env
  (`qa`) leak (🔴 trigger). `BIOLOGY.md:59` is also **stale**: it says "Add applied literature
  entries to sources.yaml," but `sources.yaml` already contains a populated `applied_literature`
  block (lines 39–87).
- **Fix:** Delete all five `<!-- TODO -->` comments. Either fill in the real values (cold-start /
  latency / SOTA / verification-date) or remove the rows/sentences entirely; do not ship author
  instructions or references to the internal QA deployment in public docs.

---

## 🟠 Should-fix

### 2. Vocabulary size is factually wrong in the docs (50,400 vs. the real 32) and contradicts the repo's own `download.py`
- **Category:** Docs / correctness
- **Location:** `models/progen2/README.md:22`, `models/progen2/MODEL.md:28`,
  `models/progen2/MODEL.md:69`
- **Detail:** The docs state "Vocabulary | 50,400 tokens (BPE tokenizer)" / "50,400 tokens (BPE
  tokenizer from GPT-J)". ProGen2's real vocabulary is **32** tokens (a small custom tokenizer, not
  GPT-J's 50,400-entry BPE). This is not a guess: `download.py:16-24` explicitly states the
  per-variant `config.json` "carries the correct ... `vocab_size` (32)" and that the 50,400 figure is
  the *wrong* GPT-J default that "would silently fall back ... and crash on a weight-shape mismatch."
  `external/likelihood_utils.py:155-156` confirms the small alphabet (amino-acid token ids 5..29).
  The 50,400 default lives only in `external/configuration_progen.py:32` and is overridden by the
  loaded checkpoint. README.md:75 even self-contradicts ("character-level ... each standard amino
  acid maps to a single token") while still printing 50,400.
- **Fix:** Replace "50,400 tokens (BPE tokenizer from GPT-J)" with the actual vocabulary size (32)
  and describe it as the ProGen2 custom tokenizer (amino-acid alphabet + terminal/special tokens),
  in both README.md and MODEL.md.

### 3. `params` is required despite a description that promises it is optional
- **Category:** Schema / correctness / consistency
- **Location:** `models/progen2/schema.py:80-82`
- **Detail:** `ProGen2GenerateRequest.params` has `Field(description="Optional parameters controlling
  this action (defaults are used when omitted).")` but **no `default`/`default_factory`**, so Pydantic
  marks it required and a request omitting `params` raises a 422 — directly contradicting the field's
  own description and the generated JSON-schema `required` list. The house reference does this
  correctly: `esm2/schema.py:76-79` uses `default_factory=ESM2EncodeRequestParams`.
- **Fix:** Add `default_factory=ProGen2GenerateParams` to the `params` field so omitting it applies
  the documented defaults.

### 4. `temperature` lower bound `ge=0.0` crashes on the sampling path
- **Category:** Correctness / schema-runtime mismatch
- **Location:** `models/progen2/schema.py:36-41` (bound) → `external/sample_utils.py:91-99`
  (`do_sample=True`); doc claim at `models/progen2/MODEL.md:192`
- **Detail:** The schema accepts `temperature=0.0`, but generation always runs with
  `do_sample=True`. In `transformers==4.36.2` a `TemperatureLogitsWarper` is added whenever
  `temperature != 1.0`, and it rejects `temperature <= 0`, so an exactly-zero temperature raises a
  `ValueError` deep in `model.generate()`. That is caught by `app.py:186-188` and re-raised as an
  uncaught system fault (HTTP 500) rather than a clean 422. Worse, `MODEL.md:192` documents
  `Temperature 0.0` as "greedy decoding," which never happens — it errors.
- **Fix:** Tighten the bound to `gt=0.0` (or a small floor such as `0.01`) so zero is rejected at
  validation as a clean `UserError`, and correct/remove the "Temperature 0.0 = greedy" line in
  MODEL.md.

### 5. Response item inherits `RequestModel` instead of `ResponseModel`
- **Category:** Schema / consistency
- **Location:** `models/progen2/schema.py:96` (`class ProGen2GenerateResponseGenerated(RequestModel)`)
- **Detail:** The per-sample outbound DTO inherits `RequestModel`, which carries
  `extra="forbid"` + `strict=True` (`commons/model/pydantic.py:30-36`). Every other model's primary
  result object inherits `ResponseModel` (e.g. `esm2/schema.py:191,209` →
  `ESM2PredictResponseResult(ResponseModel)`, `ESM2LogProbResponseResult(ResponseModel)`). There is
  no runtime failure today (the dict built at `app.py:204-213` has exactly the three expected keys),
  but applying request strictness to an outbound payload is a latent footgun (any future extra field
  would raise) and breaks cross-model uniformity for the response layer.
- **Fix:** Make `ProGen2GenerateResponseGenerated` inherit `ResponseModel`.

---

## 🟡 Nits

### 6. `comparison.yaml` ships authoring-workflow scaffolding in its header
- **Category:** Knowledge graph / consistency
- **Location:** `models/progen2/comparison.yaml:1-8`
- **Detail:** The header comment includes "Generated as part of Phase 3.5 of the
  model-knowledge-base workflow" plus a "Requirements:" authoring checklist. The reference model
  (`esm2/comparison.yaml:1-3`) carries only `model_slug`/`display_name`/`last_updated`. ~10 of 43
  models share this residue, so it is a known cleanup cluster rather than a progen2-only defect, but
  it is template/process residue and the "Phase 3.5 ... workflow" phrasing is internal-process noise.
- **Fix:** Trim the header to the minimal `esm2`-style comment (or drop it). Best handled as a
  batch across the ~10 affected models.

### 7. Test validator re-downloads the R2 `input.json` to recompute expectations
- **Category:** Tests / convention
- **Location:** `models/progen2/test.py:14-37` (`_validate_progen2_generate` calls
  `read_json_from_r2` on every invocation)
- **Detail:** The validator fetches the request payload back from R2 each run to recover
  `num_samples`/`context`/`max_length`. The newer house convention (`esm2/test.py:4,49`) prefers a
  programmatic fixture and shared assets (`commons.testing.shared_assets.STANDARD_PROTEIN`), which
  avoids the extra network round-trip and keeps the expected values in-process. Functionally correct
  here, just heavier and slightly off the shared-asset pattern (rubric A10).
- **Fix:** Pass the input as a programmatic fixture (e.g. `{"params": {...}, "items": [{"context":
  STANDARD_PROTEIN}]}`) and read the expected counts/bounds from that object instead of re-reading R2.

### 8. Internal `qa` env reference in the `__main__` usage docstring (repo-wide)
- **Category:** Open-source readiness
- **Location:** `models/progen2/app.py:224` (`# Force deploy to "qa" or "main" environment:`)
- **Detail:** References the internal `qa` Modal environment. This is **not** progen2-specific — the
  identical line appears in 30 models including the reference `esm2/app.py:484`. Noting it so the
  global cleanup (W14) catches it; do not treat as a progen2 deviation.
- **Fix:** Address repo-wide: drop or genericize the `"qa"`/`"main"` environment reference in the
  shared `__main__` docstring template.

### 9. `sources.yaml` provenance gaps (repo-wide pattern)
- **Category:** Knowledge graph / provenance
- **Location:** `models/progen2/sources.yaml:18` (`doi: ''`), `:35` (`commit: ''`), `:36`
  (`snapshot_r2: pending`)
- **Detail:** The primary paper's `doi` is empty even though the README BibTeX has it
  (`10.1016/j.cels.2023.10.002`); the GitHub `source_repos` entry has an empty `commit` and
  `snapshot_r2: pending`, so the vendored `external/` code is not pinned to an upstream commit. The
  empty-commit / pending-snapshot state is widespread (24+ models), so this is a low-priority
  house-wide backlog item, not a progen2-only miss — but the missing primary `doi` is a quick,
  progen2-local fix worth doing.
- **Fix:** Fill the primary-paper `doi`; pin the `salesforce/progen` commit used for the vendored
  `external/` snapshot and resolve `snapshot_r2` as part of the global provenance pass.

---

## Cross-checks that passed (for the record)
- **Action set:** single `generate` action — within the closed verb set and matches intent
  (`config.py:51-57`).
- **Bidirectional likelihood docs are accurate:** schema descriptions of `ll_sum`/`ll_mean`
  (`schema.py:100-105`) match `external/likelihood_utils.py:209-210` (0.5·(forward+reverse)); the
  "context prefix + terminal tokens stripped" claim matches `external/sample_utils.py:147-155`.
- **Acquisition:** documented custom strategy (`download.py`) self-populates the public R2 bucket,
  enforces the full variant set before caching to avoid poisoning the shared completion marker, and
  uses `requests` from the download base layer (no missing `extra_pip_packages`). HF-mirror rejection
  is justified and documented.
- **License:** per-model `LICENSE` (BSD-3-Clause, Salesforce 2022) is consistent with
  `sources.yaml:3-6`; attribution + GPT-J/Apache-2.0 note present.
- **Logging:** `get_logger` used; no `print` in runtime code (the `print` calls in `external/` are
  vendored and excluded from lint via `pyproject.toml` `external` excludes).
- **Field descriptions render:** all request/response fields use `Field(description=...)`; no field
  is hidden inside an `Optional[Annotated[...]]` wrapper that would drop the description.

---

## Verification

Adversarial re-check of the five flagged HIGH-severity findings against the actual source.

1. **Shipped TODO placeholders (two leak the QA env; one stale) — REAL.** All five `<!-- TODO -->`
   comments are present at the cited lines (`README.md:171,191,202`, `MODEL.md:228`, `BIOLOGY.md:59`,
   confirmed by grep). `README.md:202` and `MODEL.md:228` both read "profile on QA deployment"
   (the internal `qa` Modal env, cf. `app.py:224`). `BIOLOGY.md:59` is stale: it tells the author to
   add `applied_literature` to `sources.yaml`, but `sources.yaml:39-87` already has a populated
   `applied_literature` block (5 entries).

2. **Vocabulary size wrong (50,400 vs real 32) — REAL.** Docs print 50,400 at `README.md:21`
   ("BPE tokenizer") and `MODEL.md:28,69` ("BPE tokenizer from GPT-J"). The repo's own
   `download.py:16-24` states the correct `vocab_size` is 32 and that 50,400 is the wrong GPT-J
   default that would crash on a weight-shape mismatch; `external/likelihood_utils.py:155-156`
   confirms the small alphabet (token ids 5..29). 50,400 lives only as the overridden default in
   `external/configuration_progen.py:32`. The self-contradicting "character-level … single token"
   line is at `MODEL.md:75` (finding mis-cited it as README.md:75) — substance holds. Minor: README
   line is :21 not :22. Citation slips do not change the verdict.

3. **`params` required despite "optional" description — REAL.** `schema.py:80-82` declares
   `params: ProGen2GenerateParams = Field(description="Optional parameters … (defaults are used when
   omitted).")` with no `default`/`default_factory`, so Pydantic v2 marks it required → omitting
   `params` raises 422, contradicting its own description. House reference `esm2/schema.py:76-79` uses
   `default_factory=ESM2EncodeRequestParams`.

4. **temperature `ge=0.0` crashes the always-on `do_sample` path — REAL.** `schema.py:36-41` accepts
   `temperature=0.0`; `external/sample_utils.py:91-99` always calls `model.generate(..., do_sample=True,
   temperature=temp)`. In `transformers==4.36.2` (`app.py:51`), `_get_logits_warper` appends a
   `TemperatureLogitsWarper` whenever `temperature != 1.0`, and its `__init__` raises `ValueError`
   for `not (temperature > 0)` (its message literally says set `do_sample=False` for greedy) — so
   temp 0.0 raises inside `generate()`; `app.py:186-188` re-raises uncaught. `MODEL.md:192` wrongly
   documents temp 0.0 as greedy decoding, which never executes. (transformers not installed locally;
   behavior verified from the known 4.36.2 source, not a live run.)

5. **Response item inherits `RequestModel` instead of `ResponseModel` — REAL (latent).**
   `schema.py:96` `class ProGen2GenerateResponseGenerated(RequestModel)` pulls in `strict=True` +
   `extra="forbid"` (`commons/model/pydantic.py:30,36`); every other model's result object uses
   `ResponseModel` (`esm2/schema.py:191,209`). No failure today — the dict built at `app.py:204-213`
   has exactly the 3 expected keys with Python-native float/str values — so impact is a latent footgun
   + cross-model uniformity break, not a live bug. Demonstrable as flagged.
