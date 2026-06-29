# Review — `models/igbert/`

**Reviewer:** independent round-1 (software + ML)
**Date:** 2026-06-29
**Verdict:** Not launch-ready as-is. No strict 🔴 blocker that is unique to this model (LICENSE is
clean CC-BY-4.0 and matches `sources.yaml`; the default code paths work; schema validators, alias
handling, and `_kind` inference all verified to run correctly; every request/response field renders a
description in `model_json_schema()`). The plumbing is house-shaped: `ModelMixinSnap`,
`biolm_model_class`, `modal_endpoint`, `setup_download_layer(extra_pip_packages=["huggingface_hub..."])`
+ `setup_source_layer`, `r2_then_hf` self-population with pinned HF revisions, `parse_variant`,
typed `RequestModel`/`ResponseModel`, `get_logger`, no `print`. Input field names follow the rubric A.3
antibody convention (`heavy_chain`/`light_chain` with `heavy`/`light` aliases; `sequence` for unpaired),
and output field names/descriptions match the pinned `field_glossary.yaml` (`embeddings`,
`residue_embeddings`, `logits`, `log_prob`).

The issues cluster in two places: (1) a correctness/consistency gap where `generate` skips the
variant-mismatch guard that `encode`/`log_prob` enforce, plus `residue_embeddings`/`logits` outputs
that include special/pad token rows and are batch-padding-dependent; and (2) knowledge-graph polish —
shipped TODO placeholders, a wrong arXiv id, a wrong HF link, and a `display_name` that disagrees
across files.

---

## 🟠 Should-fix

### 1. `generate` is missing the variant-mismatch guard that `encode`/`log_prob` enforce
- **Category:** Correctness / cross-action consistency (B.Correctness, C.Consistency)
- **Location:** `models/igbert/app.py:256-360` (`generate`), vs the guard in
  `_pre_process_payload` `app.py:142-154` (called only at `:181` and `:373`)
- **Detail:** `encode` and `log_prob` both route through `_pre_process_payload`, which raises
  `ValidationError400` when an item's inferred `_kind` does not match the deployed `self.model_type`
  ("Mismatch detected: expected '…' but got '…'"). `generate` reads `item._kind` to *format* the
  input (`:267`, `:343`) but never checks it against `self.model_type`. A `paired` item sent to an
  `igbert-unpaired` deployment (or vice-versa) is therefore run silently on the wrong weights —
  the unpaired model is fed a `"heavy [SEP] light"` string, or the paired model a lone chain — and
  returns plausible-looking but meaningless residues with no error. This is exactly the failure the
  other two actions defend against.
- **Fix:** In `generate`, validate the variant before building inputs — either call
  `_pre_process_payload` for its side-effect check, or add the same
  `any(item._kind != self.model_type for item in payload.items)` → `ValidationError400` guard at the
  top of the method.

### 2. `residue_embeddings` and `logits` include special/pad-token rows and are batch-padding-dependent
- **Category:** Correctness / public-contract / cross-model uniformity (A.4, B.Correctness)
- **Location:** `models/igbert/app.py:220-246` (`_encode_forward`); compare `models/esm2/app.py:324-365`
- **Detail:** `residue_embeddings[idx].cpu().tolist()` (`:243`) and `all_logits[idx].cpu().tolist()`
  (`:246`) are emitted at the full *padded* length `T_pad` (the longest item in the batch). The
  returned matrices therefore (a) include rows for `[CLS]`, the inter-chain `[SEP]`, the trailing
  `[SEP]`, and `[PAD]` positions (special rows are zeroed for `residue_embeddings` but still present;
  `logits` rows are raw), and (b) change length depending on what else is co-batched — the *same*
  input yields a different-length output in a different batch. ESM2 deliberately slices
  `[1 : truncate_len + 1]` to return exactly L residue rows and also returns `vocab_tokens` so logits
  columns are interpretable. `field_glossary.yaml` pins `residue_embeddings` = "Per-residue embedding
  vectors", which the padded/special-inclusive output contradicts. Note the encode golden-fixture
  tests default to `include=["mean"]` (`schema.py:53-55`), so the `residue`/`logits` paths are likely
  unverified by the suite. (Mean pooling itself is correct — it divides by the non-special token count.)
- **Fix:** Strip special + pad positions per item before returning `residue_embeddings`/`logits`
  (use `special_tokens_mask == 0` to select real-residue rows), matching the ESM2 approach; consider
  adding a `vocab_tokens` field if raw logits ship. Add a fixture case exercising
  `include=["residue","logits"]`.

### 3. Shipped TODO placeholders in the knowledge-graph docs
- **Category:** Knowledge-graph completeness (A.9)
- **Location:** `models/igbert/README.md:220`; `models/igbert/MODEL.md:27`; `models/igbert/MODEL.md:67`
- **Detail:** A.9 requires no stray `TODO`/template placeholders in shipped files. Three HTML-comment
  TODOs remain: README "Extract benchmark numbers from Kenlay et al. 2024", MODEL "Confirm exact
  parameter count and hidden dimensions", and MODEL "Extract benchmark numbers from Table 1". They
  do not render but ship in the repo and signal incomplete docs (the "Published Results"/"Published
  Benchmarks" sections are effectively empty).
- **Fix:** Fill in the benchmark/parameter numbers from the paper + HF model card, or remove the
  empty sections and the TODO comments.

### 4. `MODEL.md` cites the wrong arXiv id (internally contradictory)
- **Category:** Documentation accuracy / internal consistency (A.9, C.Docs)
- **Location:** `models/igbert/MODEL.md:67` — "see sources.yaml primary_papers[0] (arXiv: 2310.16645)"
- **Detail:** The correct IgBERT paper is arXiv **2403.17889** (used in `sources.yaml:22`,
  `README.md:271,286`). `2310.16645` is a different paper, and the line even claims to reference
  `sources.yaml primary_papers[0]`, whose arxiv is `2403.17889` — so the citation is self-contradicting.
- **Fix:** Replace `2310.16645` with `2403.17889` (and resolve the TODO per finding #3).

### 5. `README.md` "Model weights (unpaired)" link points to the *paired* HF repo
- **Category:** Documentation / dead-or-wrong link (C.Docs)
- **Location:** `models/igbert/README.md:288`
- **Detail:** The unpaired bullet links to `huggingface.co/Exscientia/IgBert` (the paired repo). The
  unpaired variant lives at `Exscientia/IgBert_unpaired` (see `config.py:31-33`,
  `IGBERT_HF_REPO_MAP`). An outside contributor following the link lands on the wrong model.
- **Fix:** Point the unpaired link to `https://huggingface.co/Exscientia/IgBert_unpaired`.

### 6. `display_name` disagrees across files (`IgBert` vs `IgBERT`)
- **Category:** Knowledge-graph internal consistency (A.9)
- **Location:** `comparison.yaml:2` (`display_name: "IgBERT"`) vs `schema.py:30`
  (`display_name = "IgBert"`, consumed by `config.py`) and `sources.yaml:2` (`display_name: IgBert`)
- **Detail:** A.9 requires `display_name` to match config. The config/`sources.yaml` value is
  `IgBert` (matching the HuggingFace repo name), but `comparison.yaml` and the prose docs use
  `IgBERT`. The catalog (driven by `config.display_name`) would render "IgBert" while
  `comparison.yaml` says "IgBERT".
- **Fix:** Pick one canonical spelling and align all five knowledge-graph files + `config`/`schema`.
  (HF/paper use "IgBert"; if "IgBERT" is preferred for display, update `IgBertParams.display_name`
  and `sources.yaml` to match.)

### 7. Internal `qa` environment name referenced in a shipped docstring
- **Category:** Internal-reference leakage (C.No-internal-leakage)
- **Location:** `models/igbert/app.py:427` — `# Force deploy to "qa" or "main" environment:`
- **Detail:** The rubric lists the internal `qa` env among 🔴 internal-reference leaks for shipped
  files. Downgraded to 🟠 here because it is **systemic, not igbert-specific** — the identical line
  is in the `models/esm2/app.py:484` reference (and the `run_or_deploy_modal_app` `__main__` block is
  copy-pasted across the fleet). It should be scrubbed repo-wide, not just here; flag for the global
  reviewer.
- **Fix:** Reword the shared `__main__` usage docstring to drop the internal env name (e.g. "Force
  deploy to the target Modal environment:") in the common template that all models copy.

---

## 🟡 Nits

### 8. `log_prob` test hardcodes standard antibody sequences instead of a shared asset
- **Category:** Tests / shared-asset reuse (A.10)
- **Location:** `models/igbert/test.py:18-43` (`_create_paired_logprob_input`,
  `_create_unpaired_logprob_input`)
- **Detail:** A.10 and the `dummy/test.py:33-36` template say standard sequences should be imported
  from `models/commons/testing/shared_assets.py`, not hardcoded. The same heavy/light pair also
  appears in `igbert/README.md` and `igt5/README.md` (companion model), so it is a genuine
  cross-model "standard" input. `shared_assets.py` currently has only protein constants — no antibody
  asset exists yet, which is why this is a nit rather than a should-fix.
- **Fix:** Add `STANDARD_ANTIBODY_HEAVY` / `STANDARD_ANTIBODY_LIGHT` (and an unpaired chain) to
  `shared_assets.py` and import them in both `igbert` and `igt5` tests.

### 9. Leftover `# TODO` scaffolding comment for an unimplemented `predict()`
- **Category:** Simplicity / leftover scaffolding (B.Simplicity)
- **Location:** `models/igbert/app.py:252-254`
- **Detail:** A multi-line `# TODO: Implement predict() … See ESMC's predict()` block ships in
  runtime code. It documents an intentional future action, but bare TODOs in shipped source are the
  kind of scaffolding the rubric flags.
- **Fix:** Move to an issue/`REMAINING_WORK.md` entry, or delete; keep app.py TODO-free.

### 10. `_pre_process_payload` mismatch condition is redundant
- **Category:** Simplicity (B.Simplicity)
- **Location:** `models/igbert/app.py:142-154`
- **Detail:** `any(item._kind != self.model_type for item in payload.items)` already covers every
  mismatch (including `items[0]`); the following two-branch `or (...)` clause re-checks
  `request_kind` (= `items[0]._kind`) against `self.model_type` and can never be true when the `any`
  is false. Dead boolean logic.
- **Fix:** Reduce to `if any(item._kind != self.model_type for item in payload.items): raise …`.

### 11. Resource-spec constant uses non-house casing
- **Category:** Style / naming (B.Readability)
- **Location:** `models/igbert/config.py:42` (`IgBert_VARIANT_RESOURCE_SPECS`)
- **Detail:** Mixed-case module constant; the house pattern is ALL-CAPS
  (`ESM2_VARIANT_RESOURCE_SPECS`). Cosmetic uniformity only.
- **Fix:** Rename to `IGBERT_VARIANT_RESOURCE_SPECS`.

### 12. Knowledge-base PDF/MD filenames don't follow the `lastname+year` convention
- **Category:** Knowledge-graph naming (A.9)
- **Location:** `models/igbert/sources.yaml:31-32` (`…/primary/papers/h2023.pdf`, `…/papers-md/h2023.md`)
- **Detail:** The paper is Kenlay et al. **2024**, but the artifact is named `h2023` (wrong initial
  and wrong year). ESM2 uses `lin2023.pdf` (lastname+year). Inconsistent with the fleet convention.
- **Fix:** Rename the R2 artifacts + references to `kenlay2024.pdf` / `kenlay2024.md`.

---

## D. Definition-of-Done audit (igbert-scoped)
- **Standard layout (A.1):** MET — all of `app.py`, `config.py`, `schema.py`, `test.py`,
  `download.py`, `fixture.py`, and the 5-file knowledge graph + `LICENSE` present; `ModelFamily` with
  `modal_class_name`, `action_schemas`, `variant_axes`, `tags`.
- **Closed-set actions (A.2):** MET — `encode` / `generate` / `log_prob`; verbs match intent.
- **Schema field names + descriptions (A.3, A.4):** MET — antibody convention + aliases; all fields
  render descriptions (verified via `model_json_schema()`); pinned glossary fields match verbatim.
- **Errors / logging (A.5, A.6):** MET — typed `ValidationError400`, no bare `ValueError` for caller
  faults in app, `get_logger`, no `print`.
- **Acquisition (A.7):** MET — `r2_then_hf` self-population, pinned HF revisions,
  `huggingface_hub` correctly listed in `setup_download_layer(extra_pip_packages=...)` for the
  build-time fallback.
- **Licensing (A.8):** MET — per-model CC-BY-4.0 `LICENSE` present and consistent with `sources.yaml`;
  the HF-says-MIT-vs-Zenodo-CC-BY discrepancy is explicitly disclosed in `sources.yaml`/README.
- **Knowledge graph (A.9):** PARTIAL — present but with shipped TODOs (#3), a wrong arXiv (#4), a
  wrong HF link (#5), and `display_name` drift (#6).
- **Tests (A.10):** PARTIAL — `TestSuite` with integration + deployment cases, fixtures lazy-load (no
  module-scope R2/network); but log_prob inputs are hardcoded rather than shared (#8), and
  `residue`/`logits` encode paths appear unexercised (#2).

## Verification

Adversarial re-check of the seven HIGH/elevated findings (tried to refute each against the actual
source). All seven hold up with concrete evidence — none refuted.

1. **generate() missing variant-mismatch guard — REAL.** `_pre_process_payload`'s guard
   (`app.py:142-154`, raises `ValidationError400`) is invoked only by `encode` (`app.py:181`) and
   `log_prob` (`app.py:373`); `generate` (`app.py:256-360`) reads `item._kind` to shape input
   (`app.py:267,343`) but never compares it to `self.model_type` — a paired item runs silently on
   unpaired weights and vice-versa.

2. **residue_embeddings / logits are padded + special-inclusive and batch-dependent — REAL.**
   `app.py:243` and `:246` emit `[idx].tolist()` at full padded length `T_pad` (special rows zeroed
   for residue via `:225`, raw for logits); ESM2 by contrast slices `[i, 1:truncate_len+1]`
   (`esm2/app.py:328,363`) and returns `vocab_tokens` (`:365`). `field_glossary.yaml:46`
   ("Per-residue embedding vectors") is contradicted; encode `include` defaults to `['mean']`
   (`schema.py:53-55`), so residue/logits paths are plausibly unexercised by goldens.

3. **Shipped TODO placeholders — REAL.** `README.md:220`, `MODEL.md:27`, `MODEL.md:67` each contain
   live `<!-- TODO ... -->` comments leaving Published Results/Benchmarks effectively empty.

4. **MODEL.md cites wrong arXiv id (self-contradicting) — REAL.** `MODEL.md:67` says
   "primary_papers[0] (arXiv: 2310.16645)" but `sources.yaml:22` primary_papers[0] is `2403.17889`
   (also in `README.md:271,286`).

5. **README unpaired weights link points to the paired repo — REAL.** `README.md:288` link text
   reads `Exscientia/IgBert_unpaired` but the href is `https://huggingface.co/Exscientia/IgBert`
   (paired); the unpaired repo is `Exscientia/IgBert_unpaired` per `config.py:32`.

6. **display_name drift (IgBert vs IgBERT) — REAL.** `schema.py:30` and `sources.yaml:2` use
   `IgBert`; `comparison.yaml:2` uses `IgBERT`. Catalog renders config's `IgBert`.

7. **Internal "qa" env name in shipped __main__ docstring — REAL.** `app.py:427` contains
   `# Force deploy to "qa" or "main" environment:`; identical line confirmed in the fleet reference
   `esm2/app.py:484`, so the leak is systemic (copy-pasted `run_or_deploy_modal_app` block), as the
   finding notes.
