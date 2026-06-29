# Review — `models/esm1v/`

**Reviewer:** independent launch-gating review (round 1)
**Verdict:** Solid, working implementation with correct plumbing (acquisition, snapshotting, config, licensing). No 🔴 launch-blockers found. The notable issues are about **cross-model uniformity** — esm1v's `predict` contract diverges from its near-identical siblings esm1b and esm2 — plus a misleading sequence-length cap and a few documentation/residue gaps.

## Summary

esm1v wraps the 5-member Facebook ESM-1v ensemble (`facebook/esm1v_t33_650M_UR90S_{1..5}`) behind a single `predict` action, exposing 6 variants (`n1`–`n5`, `all`). The Modal plumbing is faithful to the house pattern (image build, `setup_download_layer`/`setup_source_layer`, `@biolm_model_class`/`ModelMixinSnap`, `r2_then_hf` self-population with `huggingface_hub` listed in `extra_pip_packages`, pinned deps, MIT `LICENSE` matching `sources.yaml`). The knowledge-graph slug/display_name are internally consistent (`esm1v` / `ESM1v` everywhere).

The headline issue: **esm1v.`predict` returns the raw HuggingFace `fill-mask` shape (`token`/`token_str`/`score`/`sequence`), while both in-repo siblings esm1b and esm2 return `logits`/`sequence_tokens`/`vocab_tokens` for the same `predict` verb.** esm1b is architecturally the same 650M/33-layer model as esm1v, yet the two expose completely different `predict` contracts — exactly the "diff should be science, not plumbing" failure the repo is trying to avoid.

---

## 🟠 should-fix

### 1. `predict` response shape & field names diverge from the house ESM masked-LM convention
- **Category:** Conformance / cross-model uniformity (Rubric A.3, C-consistency)
- **Location:** `models/esm1v/schema.py:68-96`, `models/esm1v/app.py:177-191`
- **Detail:** esm1v returns `ESM1vPredictResponseLabel{token, token_str, score, sequence}` — the verbatim output dict of `transformers` `pipeline("fill-mask")`. Both sibling models return a different, *mutually identical* shape for the same `predict` action: esm1b (`models/esm1b/schema.py:185-193`) and esm2 (`models/esm2/schema.py:191-200`) both expose `ESM*PredictResponseResult{logits, sequence_tokens, vocab_tokens}`. esm1v is the only one diverging. The field names `token`/`token_str`/`sequence` are HF-native (not in `tooling/field_glossary.yaml`), and `sequence` in the *response* means "full sequence with the mask filled," which collides semantically with the *request* `sequence` field. A caller cannot treat `/esm1v/predict` and `/esm1b/predict` uniformly despite the models being near-identical. This may be a deliberate "variant-scoring UX" choice, but it should be reconciled or explicitly justified.
- **Suggested fix:** Prefer aligning esm1v `predict` to the esm1b/esm2 `logits`+`vocab_tokens` shape so the only diff between the ESM masked-LM models is the weights. If the ranked-amino-acid shape is kept intentionally, rename fields toward repo conventions (e.g. `score` is fine; reconsider `token_str`/`sequence`) and document the deliberate divergence in MODEL.md.

### 2. Response element subclasses `RequestModel` (strict + `extra="forbid"`) and is validated from external library output
- **Category:** Correctness / robustness / convention (Rubric A.3, B-correctness)
- **Location:** `models/esm1v/schema.py:68` (`class ESM1vPredictResponseLabel(RequestModel)`), populated at `app.py:179-181` via `ESM1vPredictResponseLabel.model_validate(label)`
- **Detail:** `RequestModel` is `strict=True, extra="forbid"`. `ESM1vPredictResponseLabel` is a **response** element, but it is `model_validate`'d directly against the dict emitted by the `transformers` fill-mask pipeline. If a future `transformers` adds/renames a key in that dict, every prediction raises `ValidationError` → 500 at runtime. Response DTOs should be `ResponseModel` (`extra="ignore"`), which is exactly what the sibling esm1b uses for its nested response components (`models/esm1b/schema.py:124,131` — `class LayerEmbedding(ResponseModel)`). (Note esm2 uses `RequestModel` for *internally-built* nested embeddings; the difference here is that esm1v validates against **third-party** output.) The pinned `transformers==4.36.2` mitigates today, but the base class is semantically wrong.
- **Suggested fix:** Change `ESM1vPredictResponseLabel(RequestModel)` → `ESM1vPredictResponseLabel(ResponseModel)`.

### 3. `max_sequence_len = 512` is an arbitrary cap presented as a model limitation
- **Category:** Docs accuracy / correctness (Rubric B, C)
- **Location:** `models/esm1v/schema.py:25`; framed as inherent in `comparison.yaml:16`, `MODEL.md:51-52`, `BIOLOGY.md:11`, `README.md:188`
- **Detail:** ESM-1v shares ESM-1b's architecture (both `t33_650M`, ~1024-token context). The in-repo sibling esm1b sets `max_sequence_len = 1022  # 1024 tokens - 2 for BOS/EOS` (`models/esm1b/schema.py:26`). esm1v caps at 512 and the docs frame this as a model property — `comparison.yaml:16` even says *"Maximum sequence length of only 512 residues — shorter than ESM-1b (1022)"*, which is misleading since the two are the same architecture. This both misinforms users and silently rejects valid inputs in residues 513–1022 that the model can actually score.
- **Suggested fix:** Either raise `max_sequence_len` to the true architectural limit (1022, matching esm1b) or, if 512 is a deliberate deployment cap, state that explicitly in the docs ("BioLM caps inputs at 512 residues for this deployment") and drop the "shorter than ESM-1b" framing.

### 4. Internal Modal environment name `qa` leaked in usage docstring
- **Category:** Open-source readiness / internal leakage (Rubric C, A — red-eligible)
- **Location:** `models/esm1v/app.py:199` (`# Force deploy to "qa" or "main" environment:`)
- **Detail:** The rubric lists internal env names (`qa`) as a launch-gating leak. This is only a comment in the `__main__` usage block, and it is **systemic** (identical comment at `models/esm2/app.py:484`), so it is not an esm1v-specific deviation — but it should not ship in a public repo.
- **Suggested fix:** Repo-wide sweep: replace with a generic phrasing (e.g. `# Force deploy to the configured environment:`). Track as a cross-cutting cleanup, not just esm1v.

### 5. `BIOLOGY.md` "Applied Use Cases" is an empty TODO placeholder despite populated `sources.yaml`
- **Category:** Knowledge graph completeness (Rubric A.9, C-docs)
- **Location:** `models/esm1v/BIOLOGY.md:51-53` (`<!-- TODO: Add specific applied literature entries from sources.yaml as they are populated -->`)
- **Detail:** `sources.yaml` already lists **five** applied-literature entries (genome-wide variant effect prediction, VariPred, DMS fine-tuning, ESM-Scan, Rep2Mut-V2), but the BIOLOGY.md section meant to summarize them ships a literal author-facing TODO comment and no content. (esm2 has analogous TODOs in MODEL.md/README.md, so the residue is systemic, but esm1v's case is worse because the source data to fill it already exists.)
- **Suggested fix:** Summarize the 5 `applied_literature` entries from `sources.yaml` into the Applied Use Cases section and delete the TODO comment.

### 6. Missing schema-strictness unit tests for the single-mask contract
- **Category:** Tests (Rubric A.10, B)
- **Location:** `models/esm1v/test.py` (no `test_schema_strictness.py`)
- **Detail:** esm1v's defining input constraint is **exactly one** `<mask>` (`SingleOccurrenceOf`, `schema.py:44`) — stricter than esm2/esm1b's "one or more." Yet there is no unit test asserting that zero masks and two masks are rejected and one mask is accepted. esm2 ships `models/esm2/test_schema_strictness.py` covering exactly this class of behavior. The only esm1v tests are the generated integration/deployment suites, which require R2 fixtures + a live container.
- **Suggested fix:** Add `models/esm1v/test_schema_strictness.py` asserting: 1 mask passes; 0 masks and 2 masks raise `ValidationError`; non-AA chars rejected; type mismatch rejected.

---

## 🟡 nits

### 7. All inline RAM comments in `config.py` are wrong
- **Category:** Readability / correctness of comments
- **Location:** `models/esm1v/config.py:44-60`
- **Detail:** `memory=8 * 1024` is annotated `# 2GB RAM` (it is 8 GB) for n1–n5, and `memory=28 * 1024` is annotated `# 16GB RAM` (it is 28 GB) for `all`. The README/MODEL.md resource tables correctly say 8 GB / 28 GB, so only the code comments are wrong (copy-paste drift; esm2's equivalent comments are correct).
- **Suggested fix:** Fix the comments to `# 8GB RAM` (n1–n5) and `# 28GB RAM` (all), or drop them.

### 8. MODEL.md / output tag call the output "logits"; it is actually probabilities
- **Category:** Docs accuracy / schema-runtime consistency
- **Location:** `models/esm1v/MODEL.md:21,51`; `config.py:75` (`output_modality=[OutputModality.LOGITS]`)
- **Detail:** The actual response field is `score` = "Model probability for this amino acid" (`schema.py:75-77`), and README correctly says "amino acid probabilities." MODEL.md's "Output | Per-position logits over 20 standard amino acids" and the `LOGITS` output-modality tag contradict that. (`LOGITS` may be the closest available tag, but the prose should match the code.)
- **Suggested fix:** Change MODEL.md "logits" → "probabilities/scores"; if a probability-flavored output-modality tag exists, prefer it.

### 9. Spearman headline number inconsistent across docs
- **Category:** Docs consistency
- **Location:** `models/esm1v/comparison.yaml:6` (`~0.45`) vs `README.md:149` / `MODEL.md:63` (`0.47`)
- **Detail:** comparison.yaml uses ~0.45 throughout while README/MODEL.md cite the paper's 0.47 (41-DMS avg). Pick one source-of-truth number.
- **Suggested fix:** Standardize on the paper value (0.47, 41 DMS) or clearly mark 0.45 as a rounded/benchmark-specific figure.

### 10. `download.get_model_id` uses `.strip("n")` instead of a prefix-strip
- **Category:** Robustness nit
- **Location:** `models/esm1v/download.py:25`
- **Detail:** `model_number.strip("n")` strips all leading/trailing `n`. It happens to be correct for the constrained enum values (`n1`–`n5`), but `.removeprefix("n")` expresses the intent and is not fragile to unexpected input.
- **Suggested fix:** `model_number_clean = model_number.removeprefix("n")`.

### 11. `sources.yaml` ships `pending` placeholders and an `unknown2024b` filename
- **Category:** Knowledge-graph residue (systemic)
- **Location:** `models/esm1v/sources.yaml:35,49-50,58-59,67-68,76-77,85-86`
- **Detail:** Many `*_r2: pending` values and `commit: ''`, plus `pdf_r2: .../unknown2024b.pdf` (author not identified). esm2's sources.yaml has the same `pending` pattern (12 occurrences), so this is a repo-wide acquisition-completeness gap rather than an esm1v defect, but it is residue per Rubric A.9.
- **Suggested fix:** Backfill the R2 artifact paths (or drop the keys) before public launch as a cross-cutting task; give `unknown2024b` a real citation key.

---

## Definition-of-Done audit (esm1v scope)
- **Standard layout / 5-file KG present:** met (app/config/schema/test/download + sources/comparison/README/MODEL/BIOLOGY + LICENSE).
- **Closed-set action / verb matches intent:** met (`predict`).
- **Self-populating weights via canonical wrapper:** met (`r2_then_hf`, build-order rule honored with `huggingface_hub` in `extra_pip_packages`).
- **Typed errors / no print / structured logging:** met (no `print`; `get_logger`; no full-sequence logging). Generic `except Exception: log; raise e` matches esm2.
- **License present, permissive, consistent:** met (MIT, matches `sources.yaml`, Meta attribution included).
- **Field descriptions render:** met (all `Field(description=...)` at field level on non-Optional types).
- **Uniform schema field names across families:** **partially met** — see 🟠 #1.
- **No stray TODO/pending/placeholder in shipped KG:** **partially met** — see 🟠 #5, 🟡 #11.
- **No internal leakage:** **partially met** — `qa` comment (🟠 #4); no `biolm-modal`/`.planning`/internal-domain refs found.
- **Tests (integration + deployment, lazy fixtures):** met for generated suites; **gap** in unit-level strictness tests (🟠 #6).

---

## Verification

Adversarial re-check of the six HIGH-severity findings against current source. Each was re-read and an attempt made to refute it; all six survived with concrete file:line evidence.

1. **predict response shape diverges from house ESM masked-LM convention — REAL.** `schema.py:68-80` defines `ESM1vPredictResponseLabel{token,token_str,score,sequence}` (the verbatim HF fill-mask dict, populated at `app.py:179`), whereas `esm1b/schema.py:185-194` and `esm2/schema.py:191-200` both expose `{logits,sequence_tokens,vocab_tokens}` for the same `predict` verb; `token`/`token_str`/`score`/`sequence` are absent from `tooling/field_glossary.yaml`, and response `sequence` (schema.py:78) collides with request `sequence` (schema.py:41). Divergence is real; partly reflects fill-mask vs raw-logits computation, but the contract inconsistency is demonstrable.

2. **Response element subclasses strict `RequestModel` and is validated from external lib output — REAL.** `ESM1vPredictResponseLabel(RequestModel)` (schema.py:68); `RequestModel` is `strict=True, extra="forbid"` (commons/model/pydantic.py:30,36); it is `model_validate`'d against the transformers fill-mask dict at `app.py:179`. esm1b uses `ResponseModel` (extra=ignore) for nested response DTOs (esm1b/schema.py:124,131), so the comparison holds. (Note: esm2's nested DTOs also wrongly subclass `RequestModel` at esm2/schema.py:129,136 — same latent issue, but the finding's esm1b comparison is correct.) Pin `transformers==4.36.2` (app.py:58) only masks it.

3. **max_sequence_len=512 is an arbitrary cap framed as a model property — REAL.** esm1v sets `max_sequence_len = 512` (schema.py:25) while same-architecture sibling esm1b sets `1022  # 1024 tokens - 2 for BOS/EOS` (esm1b/schema.py:26); both are `*_t33_650M` (sources.yaml:38 = `esm1v_t33_650M_UR90S`), ~1024-token context. comparison.yaml:16 ("only 512 residues — shorter than ESM-1b (1022)"), MODEL.md:51, BIOLOGY.md:11, README.md:188 all present 512 as a model limit; the cap silently rejects valid 513–1022 inputs.

4. **Internal env name 'qa' leaked in usage docstring — REAL.** `app.py:199` reads `# Force deploy to "qa" or "main" environment:`; identical at esm2/app.py:484 (systemic, comment-only) — still a demonstrable public-launch leak in esm1v.

5. **BIOLOGY.md 'Applied Use Cases' ships an empty TODO placeholder despite populated sources.yaml — REAL.** `BIOLOGY.md:53` ships the literal `<!-- TODO: Add specific applied literature entries from sources.yaml as they are populated -->` (only a generic intro sentence at line 51, no specific entries) while sources.yaml:41-86 already lists five applied-literature entries (genome-wide VEP, VariPred, DMS fine-tuning, ESM-Scan, Rep2Mut-V2).

6. **Missing schema-strictness unit tests for the single-mask contract — REAL.** esm1v's distinguishing constraint is `SingleOccurrenceOf(single_token="<mask>")` (schema.py:44) — stricter than esm1b/esm2's `SingleOrMoreOccurrencesOf` (esm1b/schema.py:86, esm2/schema.py:94). The esm1v dir has no `test_schema_strictness.py` (only generated integration/deployment `test.py`, lines 29/32, needing R2 fixtures + live container), whereas esm2 ships `test_schema_strictness.py`. No unit asserts zero/two masks rejected and exactly one accepted.

**Summary: 6 real, 0 refuted, 0 uncertain.**
