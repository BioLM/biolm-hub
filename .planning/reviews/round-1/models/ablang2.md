# Review — `models/ablang2/`

**Reviewer:** independent round-1 (software + ML)
**Date:** 2026-06-29
**Verdict:** Not launch-ready as-is. No blockers in the strict 🔴 sense (no secret/license/internal
leak, default code paths work), but a cluster of 🟠 should-fix items around **schema uniformity and
the public contract** that, taken together, a maintainer may reasonably treat as launch-gating. The
plumbing is house-shaped (uses `ModelMixinSnap`, `biolm_model_class`, `modal_endpoint`,
`setup_download_layer` + `setup_source_layer`, `r2_then_library`, the `TestSuite`/`FixtureGenerator`
harness, typed `RequestModel`/`ResponseModel`, `get_logger`, no `print`). Input field names are
correct (`heavy_chain`/`light_chain` with `heavy`/`light` aliases — exactly the rubric A.3 antibody
convention). LICENSE is clean (BSD-3-Clause, correct holder, attribution present, matches
`sources.yaml`). No internal-reference leakage.

The issues are concentrated in `schema.py` / `app.py`: model-specific **output** field names
(`seqcoding`/`rescoding`/`likelihood`) that break cross-model uniformity, a published response schema
that doesn't match what `encode` actually returns, an `align` flag wired to the wrong mode, a large
amount of dead schema scaffolding, and a leftover TODO block that admits uncertainty about runtime
weight caching.

---

## 🟠 Should-fix

### 1. Embedding outputs use model-specific field names (`seqcoding` / `rescoding`) instead of the canonical `embeddings` / `per_token_embeddings`
- **Category:** Schema field names / cross-model uniformity (A.3)
- **Location:** `models/ablang2/schema.py:286-316` (`AbLang2RescodingResult.rescoding`,
  `AbLang2SeqcodingResult.seqcoding`); emitted in `models/ablang2/app.py:209,230,240`
- **Detail:** The rubric's north star is "the diff between any two models should be the science, not
  the plumbing," and A.3 says biology lives in tags, not field names — embedding outputs should be
  `embeddings` / `per_token_embeddings` / `residue_embeddings`. AbLang2 instead bakes the upstream
  jargon `seqcoding` (a pooled per-pair embedding) and `rescoding` (per-residue embeddings) into the
  response field names. A consumer that reads `embeddings` from ESM2/ESMC must special-case AbLang2.
  `field_glossary.yaml` pins `per_token_embeddings`/`residue_embeddings` for exactly this reason.
- **Fix:** Rename `seqcoding` → `embeddings` (single pooled vector) and `rescoding` →
  `per_token_embeddings` (or `residue_embeddings`), keeping `seqcoding`/`rescoding` as Pydantic
  `validation_alias`/`serialization_alias` for back-compat. Best done together with finding #2.

### 2. `encode` returns a `Union[...]` but `config.py` publishes only `AbLang2SeqcodingResponse` — the rescoding response shape is absent from the public schema
- **Category:** Public contract / correctness (A.1, B.Correctness)
- **Location:** `models/ablang2/config.py:57-60` (`response_schema=AbLang2SeqcodingResponse  #
  Primary response type`) vs `models/ablang2/app.py:178-247` (returns
  `Union[AbLang2SeqcodingResponse, AbLang2RescodingResponse]`)
- **Detail:** `action_schemas` is what the gateway publishes as the action's contract. For
  `include="rescoding"` the endpoint returns a different shape (`rescoding` matrices +
  `number_alignment`) that the published schema never describes. The inline comment "Primary
  response type" shows the author knows it's incomplete. Half of `encode`'s behavior is
  undocumented in the public API schema — verges on a broken-public-contract 🔴.
- **Fix:** Prefer the ESM2 pattern: a single `AbLang2EncodeResponse` whose result has optional
  `embeddings` and `per_token_embeddings` (+ `number_alignment`) fields, populated per `include`.
  This collapses #1 and #2 into one uniform, fully-published response model. (If two response types
  are truly required, the config/gateway must publish the union.)

### 3. `predict` output field is named `likelihood` but holds raw **logits**; name + description contradict what `app.py` computes
- **Category:** Schema field names + field descriptions (A.3, A.4) / correctness (B)
- **Location:** `models/ablang2/schema.py:322-325` (`likelihood: ... "Per-position amino-acid
  likelihood matrix"`) vs `models/ablang2/app.py:264-272` (`canonical_logits_matrix =
  logits_matrix[:, 1:21]` — unnormalized logits, no softmax)
- **Detail:** The values are logits (the variable is literally `canonical_logits_matrix`; the README
  example shows negative values, which a likelihood/probability distribution cannot have). ESM2
  exposes the identical concept as the field `logits` with the glossary-pinned description
  "Per-position logits over the model vocabulary." Using `likelihood` here is both a uniformity
  break and an inaccurate description. README.md:96-119 / MODEL.md compound it by calling the output
  "per-position likelihood distributions over the 20 canonical amino acids."
- **Fix:** Rename the field `likelihood` → `logits` (keep `likelihood` as an alias), set the
  description to the glossary string, and update README/MODEL.md to say "per-position logits" rather
  than "likelihood distributions."

### 4. `align` is wired to the wrong mode and can raise a server error on the documented-safe path
- **Category:** Correctness + description-vs-code mismatch + error taxonomy (B, A.4, A.5)
- **Location:** `models/ablang2/app.py:194-220`; description at `models/ablang2/schema.py:142-145`
- **Detail:** Code: `align = payload.params.align if include == SEQCODING else False`, then seqcoding
  is called with `align=align` (user-controlled) while rescoding is hardcoded `align=False`. This is
  backwards: alignment is meaningful only for per-residue (rescoding) output, and the schema
  description even says "rescoding only." So (a) the one mode where `align` matters silently ignores
  it, and (b) for seqcoding a caller can set `align=True` (nothing validates it — the description
  only *says* "must remain false"), which reaches `self.model(mode="seqcoding", align=True)` and
  trips the un-installed ANARCI/pandas path → an unhandled library exception surfaced as a 500
  `ServerError` instead of a 4xx `UserError`.
- **Fix:** Until alignment is supported, either drop `align` from the public params or add a
  validator that rejects `align=True` with a typed `UserError`. When implemented, wire `align` to the
  rescoding branch (not seqcoding) so code and description agree.

### 5. Large amount of dead schema scaffolding (6 fully-unused classes + vestigial `params`)
- **Category:** Simplicity / "10x" (B)
- **Location:** `models/ablang2/schema.py:70-126,166-189,197-209`
- **Detail:** `AbLang2SeqcodingOptions`, `AbLang2SeqcodingParams`, `AbLang2SeqcodingRequest`,
  `AbLang2RescodingOptions`, `AbLang2RescodingParams`, `AbLang2RescodingRequest` have **zero**
  references anywhere in the repo (confirmed by grep) — they duplicate what `AbLang2EncodeRequest`
  already does. Additionally `AbLang2LikelihoodParams` (predict ignores `payload.params` entirely —
  see `app.py:251-274`) and `AbLang2RestoreParams.include` / `AbLang2RestoreOptions` (generate reads
  only `params.align`) are single-value enums that are never consumed. This is exactly the leftover
  scaffolding the simplicity criterion targets; it also bloats the importable public surface.
- **Fix:** Delete the six unused Seqcoding/Rescoding request-side classes. Drop the vestigial
  single-value `include` enums/params (predict takes only `items`, mirroring ESM2; generate keeps
  only `align`).

### 6. Leftover TODO block in shipped runtime code, including an unresolved weight-caching concern
- **Category:** Open-source readiness / cost-discipline (A.7, C)
- **Location:** `models/ablang2/app.py:40-42`
- **Detail:** Ships `# TODOs: * Add fix so that ablang2 uses weights at self.model_dir (it might
  currently be downloading it) * Add support for align=True ...`. The first item admits the author
  is unsure whether the container re-downloads weights at runtime instead of using the
  R2-cached/symlinked copy — directly relevant to the repo's Modal cost-discipline north star. The
  symlink machinery in `download.py` + the verification in `load_model` suggests it's actually fine,
  in which case the TODO is stale and must go; if it's a real risk it must be resolved before launch.
  Either way, an unfinished TODO referencing internal doubts shouldn't ship publicly.
- **Fix:** Confirm at runtime (via `modal app logs`) that no fresh download happens on cold start,
  then delete the TODO block. Track the ANARCI/`align` work as an issue, not an inline TODO.

---

## 🟡 Nits

### 7. `rescoding` typed `list[list[Union[float, str]]]` — the `str` is unjustified
- **Category:** Readability / typing (B)
- **Location:** `models/ablang2/schema.py:287-291`
- **Detail:** `app.py` always emits `…astype(float).tolist()`, so rows are always floats. The
  `Union[float, str]` (and the stray comment "embed-dims or tokens") widens the public type for no
  reachable code path and weakens client codegen.
- **Fix:** Use `list[list[float]]`.

### 8. Typos and low-signal comments in the `predict` path
- **Category:** Readability (B)
- **Location:** `models/ablang2/app.py:253` (`"Uses ablang2's "lilelihood" mode, which computs the
  logits"`)
- **Detail:** "lilelihood" → "likelihood", "computs" → "computes". (The `log_prob` body also leans on
  the library-private `self.model._predict_logits` at `app.py:314`; fragile but works — worth a note
  that it depends on an undocumented internal API.)
- **Fix:** Fix the typos; consider a one-line comment that `_predict_logits` is a private upstream
  API and may break across `ablang2` versions (currently pinned `==0.2.1`, which mitigates it).

### 9. `log_prob` test re-hardcodes the antibody pair instead of importing it from `fixture.py`
- **Category:** Tests / DRY (A.10)
- **Location:** `models/ablang2/test.py:55-64` vs `models/ablang2/fixture.py:47-50`
- **Detail:** The same heavy/light pair (`QVQLVQSGGQ…` / `DIQMTQSPSS…`) is written out independently
  in both files; they can drift. There is no shared *antibody* asset in
  `models/commons/testing/shared_assets.py` (only protein constants), so a local constant is
  acceptable — but it should be defined once. (Otherwise the test harness usage is correct: integration
  + deployment suites, lazy fixtures, `_validate_log_prob`.)
- **Fix:** Define the canonical test pair once (e.g. export `SEQ_1` from `fixture.py`) and import it
  in `test.py`; or add a `shared/antibody/standard.json` asset if other antibody models will reuse it.

### 10. `sources.yaml` lists the predecessor **AbLang** paper as the first `primary_papers` entry
- **Category:** Knowledge graph (A.9)
- **Location:** `models/ablang2/sources.yaml:19-43`
- **Detail:** For a model named AbLang2, the AbLang2 paper (2024, `10.1101/2024.02.02.578678`) is the
  primary reference; AbLang (2022) is a predecessor and is listed first. (The `pending`/empty
  `arxiv`/`commit` fields are the repo-wide convention for un-uploaded R2 assets — same count as
  esm2 — so not flagged.)
- **Fix:** List the AbLang2 paper first; keep AbLang as a secondary/predecessor reference.

---

## D. Definition-of-Done audit (per-model items)

- **Layout (A.1):** MET — all standard files + 5-file knowledge graph present; `config.py` defines a
  `ModelFamily` with `modal_class_name`, `action_schemas`, tags, single-variant naming.
- **Actions (A.2):** MET — `encode/predict/generate/log_prob`, all from the closed set; no invented
  verbs. (Minor: `predict` returns whole-sequence logits without requiring masks, unlike ESM2's
  masked `predict`; within the allowed set, not flagged.)
- **Schema field names (A.3):** PARTIAL — inputs canonical (`heavy_chain`/`light_chain` + aliases);
  **outputs not** (`seqcoding`/`rescoding`/`likelihood` — findings #1, #3).
- **Field descriptions (A.4):** PARTIAL — every field renders a description (no `Optional[Annotated]`
  drop-outs), but two are inaccurate (#3 likelihood-vs-logits, #4 align "rescoding only").
- **Errors (A.5):** PARTIAL — relies on validators + the decorator; no bare exceptions for bad input,
  but the `align=True` seqcoding path yields a 500 instead of a typed `UserError` (#4).
- **Logging (A.6):** MET — `get_logger`, no `print`, no full sequences/secrets logged.
- **Acquisition (A.7):** MET (with caveat) — `r2_then_library`, self-populates R2, build-order
  honored (`ablang2` pre-installed before `setup_download_layer`, a valid alternative to
  `extra_pip_packages`); but the stale weight-caching TODO (#6) should be resolved/removed.
- **Licensing (A.8):** MET — BSD-3-Clause, correct holder/attribution, consistent with `sources.yaml`.
- **Knowledge graph (A.9):** MET (minor) — 5 files, internally consistent (`ablang2`/`AbLang2`
  everywhere), no template/TODO residue in the Markdown; only nit #10. (KG references some
  license-EXCLUDED models — nanobert/ablef/propermab — but esm2 does the same; the graph describes
  the broader BioLM platform catalog, so not flagged.)
- **Tests (A.10):** MET (minor) — integration + deployment suites, lazy fixtures, shared
  `_validate_log_prob`; only the small duplication nit #9.

---

## Verification

Adversarial re-check of externally-supplied HIGH-severity findings against the actual code/files.

- **Finding "test" (location `a:1`, detail "d") — REFUTED.** Placeholder/test stub, not a real
  finding: no file named `a` exists anywhere in the repo (`find . -name a` returns nothing), so
  `a:1` cites nothing; title "test" and detail "d" describe no demonstrable behavior in any
  `models/ablang2/` source. Nothing to confirm in the code.
