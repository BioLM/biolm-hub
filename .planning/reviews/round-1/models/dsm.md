# Review — `models/dsm/`

**Reviewer:** independent round-1 (rubric A–D)
**Verdict:** Plumbing is solid and conformant (layout complete, schema docs pass `check_schema_docs`,
canonical `r2_then_hf` acquisition, typed schema, lazy fixtures, shared-asset reuse). The **science layer
has a real correctness gap**: the `generate` action silently ignores three advertised parameters
(`max_length`, `top_k`, `top_p`), and the documented "empty string = unconditional" contract produces
empty output. Several documentation accuracy issues (stale `predict` action naming, wrong BibTeX, an
"autoregressive" claim that contradicts the model) round out the should-fix list.

Cross-checked against `models/esm2/` (full reference) and `models/dummy/` (template). Schema-doc CI guard
passes for DSM (`✓ schema docs OK`). All comparison.yaml model slugs resolve.

---

## 🔴 Must-fix

### 1. `generate` silently ignores `max_length`, `top_k`, and `top_p` (dead, advertised params)
- **Category:** Correctness / broken public contract
- **Location:** `models/dsm/app.py:557-662` (the three `_generate_*` methods); schema
  `models/dsm/schema.py:81-97`; README `models/dsm/README.md:62-65`
- **Detail:** All three private generators take `max_length`, `top_k`, `top_p` in their signatures
  (`app.py:561-564,600-601,633-636`) and `generate()` dutifully passes them in
  (`app.py:330,339-342,355-356,368-371`), but **none of them is ever forwarded to
  `self.model.mask_diffusion_generate(...)`** (only `step_divisor`, `temperature`, `remasking` are passed
  — `app.py:581-590, 615-624, 651-660`). The output length is therefore determined *solely* by the number
  of `<mask>` tokens in the input, and `top_k`/`top_p` have zero effect. Yet the schema and README
  document `max_length` as "Maximum length of the generated sequence", `top_k` as "Top-k sampling cutoff",
  and `top_p` as "Nucleus (top-p) sampling threshold". A caller who sets any of these gets no behavioral
  change — a broken contract.
- **Fix:** Either (a) forward the parameters into `mask_diffusion_generate` if the DSM library supports
  them, or (b) if discrete-diffusion sampling does not support `top_k`/`top_p` and length is intrinsically
  mask-driven, **remove `top_k`, `top_p`, and `max_length` from `DSMGenerateRequestParams`** and the README
  table, and document that generation length equals the number of `<mask>` tokens supplied. Do not ship
  knobs that do nothing.

---

## 🟠 Should-fix

### 2. Unconditional generation via empty string yields empty output; the contract is mislabeled
- **Category:** Correctness / documentation accuracy
- **Location:** `models/dsm/app.py:333-343`, `models/dsm/schema.py:123`, `models/dsm/README.md:108`,
  `models/dsm/fixture.py:47-66`
- **Detail:** The schema says `sequence` "empty = unconditional generation" and the README's first example
  passes `DSMGenerateRequestItem(sequence="")`. But the empty-string branch routes to
  `_generate_unconditional`, which tokenizes `""` → `[BOS, EOS]` with no mask tokens to denoise; with
  `max_length` ignored (finding #1) `mask_diffusion_generate` has nothing to fill and returns an empty
  sequence (whose `_calculate_log_prob` then returns `log_prob=0.0, perplexity=1.0`). True unconditional
  generation in DSM requires a canvas of `<mask>` tokens — which is exactly what the fixture sends
  (`sequence="<mask>" * 50`, `fixture.py:60`), but that input contains `<mask>` so it is actually routed to
  `_generate_mask_fill`, **not** `_generate_unconditional`. So the empty-string path is effectively dead
  and the test never exercises it; the integration validator (`test.py:44-46`, `len(sequence) > 0`) would
  fail if it ever did.
- **Fix:** Make the documented unconditional contract real: when `sequence` is empty, synthesize a
  `<mask>*N` canvas of length `max_length` (after implementing #1) before calling
  `mask_diffusion_generate`. Update README/schema so "unconditional" and the fixture agree on a single
  mechanism.

### 3. Stale `predict` action naming in shipped docs/comments
- **Category:** Convention / docs (consistency)
- **Location:** `models/dsm/README.md:11`, `models/dsm/config.py:75`
- **Detail:** README states "**Generate** (`predict`): …" and config carries the comment
  "`# - Actions: predict (generate), encode, score`". The actual action is `generate`
  (`config.py:99-103`, `ModelActions.GENERATE`); there is no `predict` endpoint on this model. A user
  reading the README parenthetical could call the wrong verb. (encode/score parentheticals are correct.)
- **Fix:** Change the README parenthetical to `(generate)` and rewrite the config comment to
  "Actions: generate, encode, score".

### 4. MODEL.md describes the scoring as "autoregressive", contradicting the model and the code
- **Category:** Documentation accuracy
- **Location:** `models/dsm/MODEL.md:139`
- **Detail:** The score pipeline lists step 4 as "Sum autoregressive log probabilities." DSM is a
  **bidirectional** ESM-2/discrete-diffusion model, not autoregressive — `app.py:497-500` explicitly
  documents this ("DSM uses a bidirectional ESM-2 backbone (discrete diffusion, not autoregressive), so we
  sum a position-aligned pseudo-log-likelihood"). MODEL.md elsewhere correctly contrasts DSM *against*
  autoregressive models, so this line is internally inconsistent and technically wrong.
- **Fix:** Replace with "Sum the position-aligned pseudo-log-probabilities (bidirectional, non-AR)".

### 5. README BibTeX is wrong (title, authors, year) and year drifts vs other files
- **Category:** Documentation accuracy / attribution
- **Location:** `models/dsm/README.md:222-229`; also `models/dsm/BIOLOGY.md:69`
- **Detail:** The BibTeX entry reads `@article{dsm2024, title={DSM: Diffusion Models for Protein Sequence
  Generation}, author={Gleghorn Lab and Synthyra}, year={2024}}`. The real citation (per
  `sources.yaml:17-29` and the NOTICE in `LICENSE:173-180`) is *"Diffusion Sequence Models for Enhanced
  Protein Representation and Generation"*, by Logan Hallee, Nikolaos Rafailidis, David B. Bichara, Jason P.
  Gleghorn, **arXiv:2506.08293, 2025**. The title, author list, and year are all incorrect and the arXiv id
  is missing. BIOLOGY.md:69 likewise calls DSM "a recent model (2024)" while sources/MODEL.md say 2025.
- **Fix:** Replace the BibTeX with the correct title/authors/`eprint=2506.08293`/`year=2025`; change
  BIOLOGY.md "(2024)" to "(2025)".

### 6. README test instructions use `make test`, contradicting the documented convention
- **Category:** Documentation / consistency
- **Location:** `models/dsm/README.md:195`
- **Detail:** README's verification block says `make test MODEL=dsm`. The repo convention (and `test.py`'s
  own usage footer, `test.py:152-154`) is to run tests via explicit
  `python -m pytest models/dsm/test.py -m integration …`. DSM is the **only** model README using
  `make test` (esm2/dummy READMEs do not).
- **Fix:** Replace with the explicit `python -m pytest models/dsm/test.py …` invocation, matching the
  `test.py` footer and the rest of the repo.

---

## 🟡 Nits

### 7. Per-residue / CLS embedding field names diverge from the rest of the fleet
- **Category:** Cross-model consistency
- **Location:** `models/dsm/schema.py:259-266`
- **Detail:** DSM names the per-residue output `per_residue_embeddings` and the CLS output
  `cls_embeddings`. ESM2 uses `per_token_embeddings` and `bos_embeddings` for the same concepts, and the
  glossary (`tooling/field_glossary.yaml`) pins `per_token_embeddings`/`residue_embeddings` (not
  `per_residue_embeddings`) and `sequence_index`. This is a third spelling for "per-residue" across the
  fleet. (Passes the CI guard because those names aren't in `verbatim`, but it hurts uniformity.)
- **Fix:** Prefer `per_token_embeddings` (or `residue_embeddings`) and `bos_embeddings` to match ESM2, or
  add the chosen names to the glossary deliberately.

### 8. `_generate_*` return-type annotations are wrong
- **Category:** Readability / correctness (typing)
- **Location:** `models/dsm/app.py:565, 602, 637`
- **Detail:** All three private generators are annotated `-> list[str]` but actually return
  `list[dict[str, str | None]]` (they delegate to `_decode_sequences`, `app.py:515-517`, and the caller at
  `app.py:376-378` treats each element as a dict with `["sequence"]`/`["sequence2"]`). No runtime effect,
  but the annotations mislead.
- **Fix:** Change to `-> list[dict[str, str | None]]`.

### 9. `json_schema_extra` `exclude_unset`/`exclude_none` are no-ops with a misleading comment
- **Category:** Correctness (minor) / cleanliness
- **Location:** `models/dsm/schema.py:244-250`
- **Detail:** The `model_config["json_schema_extra"]` carries `exclude_unset`/`exclude_none` with comments
  claiming they "Exclude unset/None fields from JSON output." Those keys are serialization options for
  `model_dump(...)`, not JSON-schema metadata — placing them in `json_schema_extra` just injects inert keys
  into the emitted schema and does **not** drop `None` fields from responses. (Copied verbatim from
  `esm2/schema.py:144-150`, so it is a shared/inherited wart, not DSM-specific.)
- **Fix:** Drop the inert keys, or apply exclusion at serialization time (`response_model_exclude_none` /
  `.model_dump(exclude_none=True)`), and fix the comments. Best handled as a commons-wide cleanup.

### 10. Docs advertise a DSM-3B variant with concrete latencies though 3B is never deployable
- **Category:** Documentation accuracy
- **Location:** `models/dsm/README.md:171-181`, `models/dsm/MODEL.md:13-17,146-150`
- **Detail:** `config.py:131-136` excludes all 3B combos (3B "not yet released"), yet README's "Model
  Sizes" and "Endpoint Performance" tables and MODEL.md's parameter/compute tables list DSM-3B with
  specific GPU/VRAM/latency figures (`~5-10s/seq`, etc.). The per-variant latency numbers across the docs
  are also unverified estimates.
- **Fix:** Mark 3B clearly as "not yet released / illustrative", or drop the 3B rows; qualify the latency
  figures as estimates.

### 11. `sources.yaml` GitHub `commit` is empty though the build pins a specific commit
- **Category:** Consistency (low; systemic)
- **Location:** `models/dsm/sources.yaml:34-35`
- **Detail:** `commit: ''` and `snapshot_r2: pending`, while `app.py:109` pins
  `DSM_REPO_COMMIT = "ca7b5c8c4a6a50517d6d7f41026886e9812e04e4"`. The known commit could fill the empty
  field. Note `snapshot_r2: pending` + empty `commit` is the **house pattern** (≈42/44 models incl. esm2),
  so this is a repo-wide ledger item, not a DSM regression — flagging only because DSM actually has the
  commit handy.
- **Fix:** Populate `commit: ca7b5c8c4a6a50517d6d7f41026886e9812e04e4`; resolve `snapshot_r2` in the
  global sources pass.

### 12. Internal `qa` environment name appears in the shipped `__main__` docstring
- **Category:** Open-source readiness (internal reference; systemic)
- **Location:** `models/dsm/app.py:677`
- **Detail:** The usage docstring says `# Force deploy to "qa" or "main" environment:`. The rubric lists the
  internal `qa` env as an internal-reference leak. This is **identical to the reference model**
  (`esm2/app.py:484`) and appears fleet-wide, so it is a systemic cleanup, not DSM-specific.
- **Fix:** Address repo-wide in a global pass (drop the `qa` mention or genericize to "your Modal
  environment").

### 13. `preview=True` in generation may emit denoising progress to stdout
- **Category:** Logging / cleanliness (low confidence)
- **Location:** `models/dsm/app.py:587, 621, 657`
- **Detail:** Every `mask_diffusion_generate` call passes `preview=True` ("Always show preview"). In DSM's
  library this typically prints intermediate denoised sequences to stdout — noise in a server context and
  arguably in tension with the structured-logging-only rule (the print originates in the third-party lib,
  not our code, so low severity/confidence). It also adds per-step overhead.
- **Fix:** Set `preview=False` for production inference unless there is a reason to keep it.

### 14. Unused `DSMParams.batch_size = 8`
- **Category:** Cleanliness
- **Location:** `models/dsm/schema.py:49`
- **Detail:** DSM batches via `generate_batch_size` (1) and `encode_batch_size` (16); `batch_size = 8`
  (copied from the esm2 template where it *is* used) appears unused in DSM's schema/app.
- **Fix:** Remove if confirmed unused, or wire it where intended.

---

## D. Definition-of-Done audit (DSM-relevant items)

- **Standard layout (app/config/schema/test/download + 5-file KG + LICENSE):** MET — all present.
- **Closed-set actions, verb matches intent:** MET — `generate`/`encode`/`score` are all in the closed set
  and appropriate (no invented verbs).
- **Field descriptions render in `model_json_schema()`:** MET — `check_schema_docs` passes; manual schema
  walk found no missing descriptions. (But three rendered descriptions are inaccurate — finding #1.)
- **Typed errors, no bare ValueError on user input, no catch-and-print:** MET — input validation is in the
  Pydantic schema; the `ValueError`/`RuntimeError` in `setup_model`/`download.py` are config/build faults,
  not user-input handling.
- **Structured logging, no `print`:** MET in our code (`get_logger`); see #13 for library-side stdout.
- **Canonical acquisition + self-population + build-order rule:** MET — `download.py` uses `r2_then_hf`;
  `setup_download_layer(..., extra_pip_packages=["huggingface_hub==0.36.0"])` honors the build-order rule.
- **Licensing consistent with sources.yaml:** MET — per-model Apache-2.0 `LICENSE` with a proper NOTICE;
  matches `sources.yaml` and the upstream repo.
- **Tests: TestSuite + integration + deployment, lazy fixtures, shared assets:** MET — `test.py` builds
  both tiers; `fixture.py` reuses `STANDARD_PROTEIN`; no module-scope R2/network.
- **Knowledge graph accurate/consistent/placeholder-free:** PARTIALLY MET — slugs/display names are
  consistent and there are no TODO markers, but accuracy defects exist (findings #4, #5, #10) and
  `snapshot_r2: pending` (#11, systemic).
- **Generate action behaves as documented:** NOT MET — findings #1 and #2 (ignored params; broken
  unconditional contract).

---

## Verification

Adversarial re-check of the six HIGH-severity findings (each re-read against current source):

1. **generate ignores max_length/top_k/top_p** — **REAL.** `_generate_unconditional/_generate_mask_fill/_generate_conditional` (app.py:557-662) accept the params but the three `mask_diffusion_generate(...)` calls (app.py:581-590, 615-624, 651-660) pass only `step_divisor`, `temperature`, `remasking`; schema.py:81-97 and README.md:62-65 advertise all three as functional. Confirmed dead/advertised params.
2. **Empty-string unconditional yields empty output; contract mislabeled** — **REAL.** Empty routes to `_generate_unconditional` (app.py:333-343); schema.py:123 + README.md:108 label `""` as unconditional, yet the "unconditional" fixture sends `"<mask>"*50` (fixture.py:59-61) which contains `<mask>` so it routes to `_generate_mask_fill` (app.py:344). `_calculate_log_prob("")` returns 0.0/1.0 (loop `range(1,1)` is empty, app.py:503-511); validator requires `len(sequence)>0` (test.py:44-46), so the empty path is dead/untested. (Empty-output claim is inference about external `mask_diffusion_generate`, but the contract-mislabel + dead-path is directly verifiable.)
3. **Stale `predict` action naming** — **REAL.** README.md:11 "**Generate** (`predict`)" and config.py:75 "# - Actions: predict (generate), encode, score"; actual action is `ModelActions.GENERATE` (config.py:99-103). No predict endpoint exists.
4. **MODEL.md "autoregressive" scoring** — **REAL.** MODEL.md:139 "Sum autoregressive log probabilities" contradicts app.py:497-500 ("bidirectional ESM-2 backbone (discrete diffusion, not autoregressive)") and MODEL.md:7 itself ("Unlike autoregressive models … DSM uses an iterative denoising process").
5. **Wrong BibTeX title/authors/year** — **REAL.** README.md:223-228 `@article{dsm2024, title={DSM: Diffusion Models for Protein Sequence Generation}, author={Gleghorn Lab and Synthyra}, year={2024}}` vs sources.yaml:18-29 (correct title "Diffusion Sequence Models for Enhanced Protein Representation and Generation", authors Hallee/Rafailidis/Bichara/Gleghorn, arXiv:2506.08293, 2025) and LICENSE NOTICE (arXiv:2506.08293, 2025). BIOLOGY.md:69 also says "(2024)" while MODEL.md says 2025. arXiv id missing.
6. **README `make test`, against convention** — **REAL** (with one inaccurate sub-claim). README.md:195 `make test MODEL=dsm` contradicts test.py:152-154 footer (`pytest models/dsm/test.py -m integration …`) and the repo convention (explicit `python -m pytest models/<model>/test.py`). NOTE: the finding's parenthetical "DSM is the only model README using `make test`" is FALSE — `models/prody/README.md:167` also uses `make test MODEL=prody`. Core finding stands; the "only model" claim does not.
