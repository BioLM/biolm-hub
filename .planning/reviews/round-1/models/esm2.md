# Review — `models/esm2/` (round 1)

## Summary

ESM2 is one of the most mature and important models in the catalog and it shows: the plumbing
(`config.py`, `download.py` with the `r2_then_library` + `extra_pip_packages` build-order fix,
`fixture.py`, lazy R2 reads in tests, the closed-set actions `encode`/`predict`/`log_prob`) is
exemplary and matches the house pattern closely. Schemas use the uniform field names
(`items`/`sequence`/`params`, `results`, `embeddings`/`logits`/`log_prob`) and descriptions render.

The problems are concentrated in (a) **documentation accuracy/consistency** — a factual error about
ESM-2's positional encoding, internally inconsistent citations with corrupted author names and two
disagreeing arXiv IDs, and a max-sequence-length story that contradicts the code; (b) a couple of
**code/description mismatches** — `log_prob` is labelled a "pseudo-log-likelihood" but is computed as a
single unmasked pass, the `attentions` output is mis-described and reduced oddly, and an inert
`json_schema_extra` serialization config; and (c) two **uniformity deviations** — a `sentence-transformers`
dependency no other model carries and never imports, and a `test_schema_strictness.py` file unique to this
model. No hard correctness bug on the primary `encode`/`predict` paths, and no high-confidence
launch-blocking secret leak that is unique to this model (the `qa`-env strings are a repo-wide template
pattern flagged below for the global sweep).

---

## 🔴 Must-fix

_None unique to this model with high confidence._ The internal `qa`-environment references that the
rubric classifies as launch-blocking are present here but are a repo-wide template pattern (see the
🟠 "Internal `qa` env reference" finding) — they should be removed in the global pre-launch sweep.

---

## 🟠 Should-fix

### 1. Unused heavyweight dependency `sentence-transformers` (unique to ESM2)
- **Category:** simplicity / dependency hygiene / uniformity
- **Location:** `models/esm2/app.py:64`
- **Detail:** The image installs `sentence-transformers==2.2.2`, but nothing in `models/esm2/`
  imports `sentence_transformers` (only `esm` and `torch` are used). ESM2 is the *only* model in the
  repo whose `app.py` pulls in `sentence-transformers`. It is an old pin that drags in a second copy
  of `transformers`/`huggingface_hub`, bloats the image, and risks dependency conflicts with the
  pinned `fair-esm`. It is almost certainly leftover scaffolding.
- **Fix:** Delete the `"sentence-transformers==2.2.2"` line from the `uv_pip_install` call. If a
  transitive consumer is later found to need it, add it with a comment explaining why.

### 2. `log_prob` is documented as a "pseudo-log-likelihood" but isn't one
- **Category:** correctness / field-description vs implementation
- **Location:** `models/esm2/schema.py:210-212`; `models/esm2/app.py:430-476`; `README.md:41,118-120`;
  `BIOLOGY.md:36-42`
- **Detail:** The response field says *"Pseudo-log-likelihood of the sequence under the model"* and the
  docs repeatedly call it a pseudo-log-likelihood. The implementation runs a **single unmasked forward
  pass** (`_encode_forward_pass(..., include=["logits"])`) and sums `log P(x_i | full sequence)` over
  positions. Because the model sees the true residue at every position, this is the naive / "wt-marginal"
  summed log-likelihood, **not** a pseudo-log-likelihood (PLL), which by definition masks each position
  one at a time and sums `log P(x_i | x_{\\i})`. The method's own docstring (`app.py:432`) correctly
  calls it "total log-probability of an unmasked sequence", so the public-facing label is the wrong one.
  This matters for users doing variant-effect scoring, where the distinction (masked-marginal vs
  unmasked) materially changes results.
- **Fix:** Rename the description to "Summed per-residue log-probability of the (unmasked) sequence
  under the model (single forward pass; not a masked pseudo-log-likelihood)." and align README/BIOLOGY
  wording. Or, if a true PLL is intended, change the algorithm to mask each position.

### 3. `attentions` output is mis-described and reduced oddly
- **Category:** correctness / description vs implementation
- **Location:** `models/esm2/app.py:366-376` (esp. comment at line 369); `models/esm2/schema.py:171-174`;
  `models/esm2/MODEL.md:196`
- **Detail:** `attentions[i]` has shape `(num_layers, num_heads, S, S)`. The code does
  `.mean(dim=1).mean(dim=1)` then slices `[:, 1:truncate_len+1]`: the first mean collapses **heads**,
  the second mean collapses the **query (row) axis**, leaving shape `(num_layers, key_positions)` — a
  per-layer vector of mean attention *received* per key, not an attention map. Yet the schema says
  *"averaged over attention heads"* (only), the in-code comment (line 369) says *"Averaging over layers
  and heads"* (it does neither over layers nor over queries-as-stated), and `MODEL.md:196` says
  "average over layers and heads". Three different stories, none matching the code; the resulting tensor
  is unlikely to be what a caller expects from "attentions".
- **Fix:** Decide the intended quantity (most likely an `(S, S)` map averaged over layers+heads) and make
  the code, the comment, the schema description, and MODEL.md agree. At minimum correct the descriptions
  to state exactly which axes are reduced and the output shape.

### 4. Max-sequence-length: docs contradict the code (and each other)
- **Category:** correctness / cross-file consistency
- **Location:** `models/esm2/schema.py:69,98` (`max_length=ESM2Params.max_sequence_len=2048`);
  `README.md:20,52`; `MODEL.md:31,75`; `BIOLOGY.md:7`; `comparison.yaml:17`
- **Detail:** The schema caps the **residue string** at 2048 characters; BOS/EOS are added afterwards,
  so the real limit is 2048 residues / ~2050 tokens. But README/MODEL/BIOLOGY all state that 2048 is the
  **total token count including BOS/EOS** (i.e. 2046 effective residues) — `MODEL.md:75` says it
  explicitly. Separately, `comparison.yaml:17` claims a *per-variant* limit (8M–650M = 1022 residues /
  1024 tokens, 3B = 2046) that appears nowhere in the code (all variants share `max_sequence_len=2048`)
  and is not true of a RoPE model. These three accounts are mutually inconsistent.
- **Fix:** State the limit once, matching the code: "max input = 2048 amino-acid residues; BOS/EOS are
  added internally." Remove the per-variant 1024/2048 claim in `comparison.yaml:17` (or move the real
  training crop-length nuance into MODEL.md as a separate note).

### 5. Factual error: ESM-2 positional encoding
- **Category:** docs accuracy
- **Location:** `models/esm2/MODEL.md:11-12,28`
- **Detail:** MODEL.md states ESM-2 *"uses ... learned positional embeddings"* and *"does not use rotary
  position embeddings"*, and the table lists `Positional encoding | Learned`. This is wrong: ESM-2's key
  architectural change from ESM-1b was replacing learned absolute positional embeddings with **rotary
  position embeddings (RoPE)**. (This is also what allows the uniform 2048-residue cap — there is no hard
  1024 positional limit — which further contradicts `comparison.yaml:17`.)
- **Fix:** Change to "rotary position embeddings (RoPE)" in both the prose and the table; drop the "does
  not use rotary" sentence.

### 6. Citations: corrupted author names + two disagreeing arXiv IDs
- **Category:** docs / dead-or-wrong links
- **Location:** `models/esm2/README.md:251-253,260,272`
- **Detail:** The author list and BibTeX contain corrupted names — "Smerity, Nikita" should be
  **Smetanin, Nikita**, and "Kabber, Ori" should be **Kabeli, Ori**. Two different arXiv IDs are cited
  for the same paper: line 253 says `arXiv: 2201.07338` while line 272 says `arXiv 2207.09423`; they
  disagree with each other and with `sources.yaml`, which (correctly) records the bioRxiv DOI
  `10.1101/2022.07.20.500902` and Science DOI `10.1126/science.ade2574`. The ESM-2 paper has no canonical
  arXiv version, so both IDs are misleading.
- **Fix:** Fix the two names, drop the invented arXiv IDs (link the bioRxiv DOI + Science DOI from
  `sources.yaml` instead), and make the README link block consistent with `sources.yaml`.

### 7. Inert `exclude_unset`/`exclude_none` config; docs say fields are "omitted"
- **Category:** correctness / misleading config + doc inconsistency
- **Location:** `models/esm2/schema.py:144-150`; `README.md:74-90`
- **Detail:** `ESM2EncodeResponseResult.model_config` puts `exclude_unset` / `exclude_none` inside
  `json_schema_extra`. Those are `model_dump()` keyword arguments, not Pydantic `ConfigDict` keys — placed
  under `json_schema_extra` they have **no effect on serialization** (they only get injected as stray
  keys into the emitted JSON Schema). The base `ResponseModel` is `ConfigDict(strict=True, extra="ignore")`
  and does not set `exclude_none` either, so unset optional fields are serialized as `null`. The README
  example (lines 74-88) indeed shows them present as `null`, yet line 90 claims "Fields are `null`
  (omitted from JSON)" and the code comments (147-149) claim None fields are excluded. The claim and the
  config are both inaccurate.
- **Fix:** Remove the inert `json_schema_extra` block and either (a) accept `null`-valued fields and fix
  the README to say so, or (b) if omission is desired, serialize the response with `exclude_none=True` at
  the endpoint/serializer layer and document that.

### 8. `test_schema_strictness.py` exists only for ESM2
- **Category:** consistency / uniformity (the repo's north star)
- **Location:** `models/esm2/test_schema_strictness.py`
- **Detail:** ESM2 is the **only** model in the repo with a `test_schema_strictness.py`. The tests are
  fine in themselves, but a per-model test file no other model has is exactly the "plumbing differs
  between models" deviation the project is trying to avoid. It also overlaps the standard `test.py` /
  shared testing harness.
- **Fix:** Either fold these strictness assertions into the shared testing layer (`models/commons/testing`)
  so every model gets them, or remove the file. Don't keep a one-off here.

### 9. Internal `qa` environment reference in shipped files (repo-wide template)
- **Category:** internal leakage
- **Location:** `models/esm2/README.md:230`; `models/esm2/MODEL.md:215`; `models/esm2/app.py:484`
- **Detail:** Two doc TODOs reference "QA deployment" and the `__main__` docstring references the
  `"qa"` Modal environment. The rubric classifies internal `qa`-env references as launch-blocking (🔴).
  Downgraded to 🟠 here only because the `app.py` `"qa"` comment is identical across 30 models (template)
  and the doc "QA deployment" string appears in 5 models — i.e. this is a global template issue, not an
  ESM2 defect. Still must not ship publicly.
- **Fix:** Hand to the global pre-launch sweep: strip `qa` from the `__main__` deploy comment template and
  delete the QA-referencing TODO comments (see also 🟡 below).

---

## 🟡 Nits

### 10. Template `<!-- TODO -->` residue and a "VERIFIED" overclaim
- **Category:** docs polish
- **Location:** `README.md:216,218,230`; `MODEL.md:215`
- **Detail:** Three `<!-- TODO -->` comments (cold-start/latency benchmarks, verification date) remain.
  They derive from the `models/dummy` template and appear in many models, so this is partly a house-wide
  cleanup, but they reference internal CI/QA (see finding 9). Relatedly, `README.md:216` asserts
  "Status: VERIFIED — Integration tests pass for all variants" while the immediately following TODO admits
  the verification date is unknown and the OSS live deploys are still pending per project status — the
  claim is stronger than the evidence.
- **Fix:** Remove the TODO comments before launch and soften "VERIFIED" to reflect what has actually been
  run in this repo (or fill in the real verification date once Milestone A/B deploys land).

### 11. Response sub-models inherit `RequestModel`
- **Category:** readability / convention
- **Location:** `models/esm2/schema.py:129,136` (`LayerEmbedding`, `LayerPerTokenEmbeddings`)
- **Detail:** These are response components but subclass `RequestModel` (`strict=True, extra="forbid"`)
  rather than `ResponseModel` (`extra="ignore"`). Harmless today but semantically backwards and a
  consistency smell.
- **Fix:** Base them on `ResponseModel`.

### 12. `default_factory=partial(list, [...])` is an unusual idiom
- **Category:** readability
- **Location:** `models/esm2/schema.py:52-59`
- **Detail:** `default_factory=partial(list, [-1])` works (each call copies the list) but `lambda: [-1]`
  / `lambda: [ESM2EncodeIncludeOptions.MEAN]` is clearer and more idiomatic.
- **Fix:** Replace with a `lambda` factory.

### 13. `logits` description says "model vocabulary" but output is sliced to 20 AA
- **Category:** field-description precision
- **Location:** `models/esm2/schema.py:175-178,191-193`
- **Detail:** Both `logits` fields are described as "Per-position logits over the model vocabulary", but
  the code slices `[4:-9]` to the 20 standard amino acids and ships `vocab_tokens` alongside. README:116
  clarifies `[L, 20]`, so this is minor, but the field text is slightly misleading on its own.
- **Fix:** Say "logits over the 20 standard amino acids (column order given by `vocab_tokens`)."

### 14. `pending` placeholders in `sources.yaml` (house-wide, noted only)
- **Category:** knowledge-graph completeness
- **Location:** `models/esm2/sources.yaml:62-107` (`pdf_r2: pending` / `md_r2: pending`)
- **Detail:** Applied-literature R2 paths are `pending`. This is consistent with most models in the repo
  (not an ESM2-specific defect), so flagged only for the global decision on whether `pending` is an
  acceptable shipped placeholder for un-ingested applied literature.
- **Fix:** Global call — either ingest the PDFs/MDs or drop the `*_r2` keys for un-ingested entries.

---

## Definition-of-Done notes
- **Standard layout / 5-file knowledge graph:** present and complete (slug `esm2` / display `ESM2`
  consistent across `config.py`, `sources.yaml`, `comparison.yaml`).
- **Closed-set actions:** `encode` / `predict` / `log_prob` — all valid; verbs match intent.
- **Acquisition:** canonical `r2_then_library` with the build-order fix correctly applied
  (`fair-esm` listed in `setup_download_layer(extra_pip_packages=...)` because the fallback imports `esm`
  at build time) — exemplary; self-populates R2.
- **Errors/logging:** typed `ValidationError400` for out-of-range layers; `get_logger`, no `print`. Good.
- **Tests:** `TestSuite` with integration + deployment cases; fixtures lazy-load from R2 in
  `_build_fixture_generation_suite` (no module-scope R2); reuses `STANDARD_PROTEIN`. Good.
- **Open items blocking a clean DoD:** docs accuracy (findings 2-7), the dead dependency (1), the
  non-uniform test file (8), and the internal `qa` references (9) should be resolved before launch.
</content>

## Verification

Adversarial re-check of the 9 flagged findings against the actual code/files (2026-06-29):

1. **Unused sentence-transformers — REAL.** `models/esm2/app.py:64` installs `sentence-transformers==2.2.2`; repo-wide grep finds zero `sentence_transformers` imports anywhere and the string appears only in `esm2/app.py`. Dead, esm2-unique dependency. Confirmed.
2. **log_prob mislabeled "Pseudo-log-likelihood" — REAL.** `schema.py:211` says "Pseudo-log-likelihood", but `app.py:444-449` calls `_encode_forward_pass(include=["logits"])` — a single UNMASKED forward pass — then sums `log P(x_i | full seq)`. That is wt-marginal/naive scoring, not PLL (which masks each position). The method docstring `app.py:432` ("total log-probability of an unmasked sequence") is the correct description, so the schema label is wrong.
3. **attentions mis-described/odd reduction — REAL.** `app.py:370-375`: `attentions[i]` is (L,H,S,S); `.mean(dim=1)` drops heads -> (L,S,S); second `.mean(dim=1)` drops the query axis -> (L,S); `[:,1:trunc+1]` slices keys -> (L, key_positions). Layers are NOT averaged. Yet `schema.py:173` says "averaged over attention heads" (only), `app.py:369` comment says "Averaging over layers and heads", `MODEL.md:196` says "average over layers and heads". Three accounts, none matches the code. Confirmed.
4. **Max-seq-length docs contradict code & each other — REAL.** `schema.py:69,98` cap the residue STRING at `max_sequence_len=2048`; BOS/EOS added after (`app.py:238`), so the real residue cap is 2048 (~2050 tokens). `README.md:20,52` and `MODEL.md:31,75` say 2048 is the TOTAL token count incl BOS/EOS (=2046 residues; MODEL.md:75 explicit). `comparison.yaml:17` claims per-variant 1022/2046-residue limits that exist nowhere in code — `config.py`/`ESM2Params.max_sequence_len` is a single 2048 for all variants. Three inconsistent accounts. Confirmed.
5. **Positional encoding "Learned"/"not rotary" — REAL (factual error).** `MODEL.md:11,28` state learned positional embeddings and "does not use rotary position embeddings". ESM-2's defining change from ESM-1b is exactly the switch to rotary embeddings (RoPE; `use_rotary_embeddings=True` in fair-esm's ESM2). The doc is wrong; this also rationalizes the uniform 2048 cap (no hard 1024 limit), reinforcing finding 4.
6. **Corrupted authors + disagreeing arXiv IDs — REAL.** `README.md:251,252,260` print "Smerity, Nikita" (should be Smetanin) and "Kabber, Ori" (should be Kabeli). `README.md:253` cites arXiv 2201.07338 while `README.md:272` cites arXiv 2207.09423 for the same paper; `sources.yaml:18-22,32-35` records only bioRxiv 10.1101/2022.07.20.500902 + Science 10.1126/science.ade2574 (no arXiv). Internal inconsistency confirmed.
7. **Inert config / docs-omitted claim — UNCERTAIN (mixed).** TRUE half: `schema.py:144-150` puts `exclude_unset`/`exclude_none` under `json_schema_extra`; these are `model_dump()` kwargs, not ConfigDict keys, so they do nothing for serialization and only leak as stray JSON-schema keys — genuinely dead/misplaced config. REFUTED half: the finding's claim that unset fields "serialize as null" is wrong — the actual response path `serialize_model` (decorator.py:228,523; serializer.py:187) calls `model_dump(exclude_none=True)`, so None fields ARE omitted on the wire, making README:90 "omitted from JSON" effectively correct (the example showing them as `null` is the inconsistent part). Net: inert-config is real, the serialization-behavior reasoning is refuted.
8. **test_schema_strictness.py only in esm2 — REAL (factually true, low severity).** `find models -name test_schema_strictness.py` returns exactly one file (`models/esm2/`). Per-model file no other model has; consistency/plumbing-deviation claim is accurate (the tests themselves are valid).
9. **Internal qa references in shipped files — REAL (references present; severity is the only debate).** `README.md:230` ("run benchmarks against QA deployment"), `MODEL.md:215` ("profile on QA deployment"), `app.py:484` ('Force deploy to "qa" or "main" environment'). The "QA deployment" doc string spans esm2/progen2/esmfold and the app.py 'qa' comment spans ~30 models (template), so it is a repo-wide template issue, not esm2-specific — but the cited strings do exist and must not ship publicly.
