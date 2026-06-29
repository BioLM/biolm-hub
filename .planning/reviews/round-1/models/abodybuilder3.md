# Review — `models/abodybuilder3/` (Round 1)

## Summary

AbodyBuilder3 is a two-variant antibody Fv structure predictor (`plddt` CPU-only, `language`
L40S+ProtT5) exposing a single `fold` action. The plumbing is largely on-pattern with `esm2`:
`ModelFamily`/`ActionSchemaMap` config, snap-loaded `ModelMixinSnap` class, `modal_endpoint`
decorator, structured logging (no `print`), canonical antibody field names (`heavy_chain`/
`light_chain` with `H`/`L` aliases), a documented **custom** acquisition strategy that self-populates
R2, and — done correctly — `huggingface_hub` placed in the download layer because the ProtT5 fallback
imports it at build time (A7 build-order rule honored). LICENSE is Apache-2.0 ("Copyright 2024
Exscientia") and matches `sources.yaml`.

The issues are concentrated in (1) the **pLDDT output**, whose schema type, documented scale, and
"per-chain" framing contradict each other and likely contradict what `app.py` actually emits — the
`plddt=True` path appears untested and may raise a 500; (2) **required-field handling** — the two
chain fields are declared `str` but defaulted to `None`, so they are silently optional despite docs
saying "required", and omitting one degrades to a 500 instead of a 422; and (3) **duplication**
(`ABODYBUILDER3_VARIANT_RESOURCE_SPECS` defined twice, `seed_everything` copy-pasted with
immunebuilder) plus some doc/code drift and shipped `TODO` residue. No secrets or `biolm-modal`/
`.planning` leakage found.

---

## 🟠 Should-fix

### 1. pLDDT output: schema type vs. runtime likely mismatched; `plddt=True` path untested
- **Category:** Correctness / schema-runtime mismatch
- **Location:** `models/abodybuilder3/schema.py:123-126`, `models/abodybuilder3/app.py:236`
- **Detail:** `app.py` computes `result_dict["plddt"] = output["plddt"].squeeze(0).tolist()`. The model
  receives a single concatenated Fv (heavy+light) and AlphaFold-style structure modules emit
  per-residue pLDDT shaped `[batch, N_res]`; `squeeze(0).tolist()` on that yields a flat `list[float]`.
  But the schema declares `plddt: Optional[list[list[float]]]`. Constructing
  `AbodyBuilder3PredictResponseResult(plddt=<list[float]>)` would then fail Pydantic validation (a
  `float` is not coercible to `list[float]`), and since `fold()` re-raises inside the broad
  `except Exception`, a `plddt=True` request would return a 500. The single test case (`test.py`)
  exercises only one `fold` fixture, so this path may be uncovered. (If `output["plddt"]` is instead
  `[1, N, 1]` the type matches but is degenerate — confirm with one `plddt=True` run; if it returns a
  flat list this is effectively a 🔴 broken feature.)
- **Fix:** Run `plddt=True` once against the actual model, then set the response type to match
  (`list[float]` if flat) and add a deployment/integration test case with `params.plddt=True`.

### 2. pLDDT scale and "per-chain" documentation contradict the schema and the code
- **Category:** Docs accuracy / cross-file consistency
- **Location:** `models/abodybuilder3/README.md:66,73` vs `models/abodybuilder3/schema.py:125`,
  `models/abodybuilder3/BIOLOGY.md:35,115`
- **Detail:** README says pLDDT is "float scores (0--1 scale)" with example `[[0.85, 0.92, ...], ...]`,
  while `schema.py` and `BIOLOGY.md` say "0–100". At least one is wrong (pLDDT is conventionally
  0–100). README also states the output is "Nested list: one list per chain", but `app.py` never
  splits by chain — it operates on a single combined Fv tensor and `squeeze(0).tolist()`s it, so the
  per-chain framing (and the two-inner-list example) is inaccurate.
- **Fix:** Pick the true scale (almost certainly 0–100) and make `schema.py`, README prose, README
  JSON example, and `BIOLOGY.md` agree; drop the "one list per chain" description.

### 3. Required chain fields are silently optional (`Field(None)` on a non-`Optional[str]`)
- **Category:** Schema / public contract / error taxonomy
- **Location:** `models/abodybuilder3/schema.py:69-93`
- **Detail:** `heavy_chain`/`light_chain` are typed `str` (required) but given `Field(None, ...)`, whose
  first positional arg is the **default**, making both fields optional with default `None`. Pydantic
  does not validate defaults, so a request like `items:[{}]` passes schema validation, then
  `string_to_input(heavy=None, light=None)` raises inside `fold()` and is re-raised as a server error
  → 500 instead of a clean 422. The docs (`README.md:56-57`, `MODEL.md:18`) call both "required". The
  house pattern is `Field(..., min_length=1, ...)` for required fields (see `esm2/schema.py:67,95`),
  or `Optional[str]` + a `model_validator` enforcing the combination (see `immunebuilder/schema.py:53-`
  `93`).
- **Fix:** Use `Field(..., min_length=1, max_length=..., validation_alias=..., description=...)`
  (Ellipsis = required) for both chains so omission yields a 422.

### 4. `ABODYBUILDER3_VARIANT_RESOURCE_SPECS` defined twice (one copy is dead)
- **Category:** Duplication / dead code
- **Location:** `models/abodybuilder3/schema.py:41-48` and `models/abodybuilder3/config.py:30-37`
- **Detail:** The dict is defined identically in both files. Only the `config.py` copy is referenced
  (in `resource_function`, config.py:67); the `schema.py` copy is unused and only exists to justify the
  `ModalGPU, ModalResourceSpec` import in schema.py (schema.py:17). Two sources of truth for resource
  specs can drift (e.g. someone edits one variant's RAM in one file only).
- **Fix:** Delete the `schema.py` copy and its now-unused `ModalGPU, ModalResourceSpec` import; keep
  the single definition in `config.py`.

### 5. `seed_everything` copy-pasted across models instead of living in commons
- **Category:** Modularity / shared-logic duplication
- **Location:** `models/abodybuilder3/app.py:246-279` (also `models/immunebuilder/app.py:356`)
- **Detail:** A near-identical `seed_everything` method is duplicated in two model apps; the rubric
  requires shared logic to live in `commons`, not be copy-pasted. The two copies have already drifted
  (immunebuilder guards `torch.cuda.*` with `is_available()`; this copy calls
  `torch.cuda.manual_seed(seed)` unconditionally — harmless no-op on the CPU-only `plddt` variant, but
  evidence of divergence).
- **Fix:** Hoist a single `seed_everything` onto `ModelMixinSnap` (or a `commons` util) and call it
  from both models.

### 6. `comparison.yaml` references model slugs that don't exist in the catalog
- **Category:** Knowledge-graph consistency / dead links
- **Location:** `models/abodybuilder3/comparison.yaml:59` (`propermab`), `:65` (`ablef`)
- **Detail:** The `complements` block lists `model: "propermab"` and `model: "ablef"`, but neither
  `models/propermab/` nor `models/ablef/` exists in the repo. These structured `model:` slugs are
  machine-consumed (catalog / `bm serve`, W9), so they become dead cross-references.
- **Fix:** Remove the two entries, or replace with existing slugs, or gate them as planned/future once
  those models are ported.

### 7. Shipped `# TODO` in runtime code about which validator to use
- **Category:** Template/TODO residue in shipped code
- **Location:** `models/abodybuilder3/schema.py:73`
- **Detail:** `# TODO: check if extended or unambiguous should be validated` ships an unresolved
  question about input-validation correctness next to the live `validate_aa_extended` validator.
- **Fix:** Decide the correct alphabet for antibody chains, apply it, and remove the TODO.

### 8. README states Python 3.9 but the image builds 3.10
- **Category:** Docs/code drift
- **Location:** `models/abodybuilder3/README.md:160` vs `models/abodybuilder3/app.py:42`
- **Detail:** README "Implementation Notes" says
  `modal.Image.micromamba(python_version="3.9")`, but `app.py` (and `environment_gpu.yml`) use 3.10.
- **Fix:** Update README to `python_version="3.10"`.

### 9. Internal `qa` environment name in shipped usage comment (systemic)
- **Category:** Internal-reference leak (rubric C)
- **Location:** `models/abodybuilder3/app.py:287`
- **Detail:** The `__main__` usage comment says `# Force deploy to "qa" or "main" environment:`. The
  rubric flags the internal `qa` env name as a leak. This is **not** abodybuilder3-specific — it is
  copy-pasted into ~all model apps (biotite, ablang2, antifold, boltzgen, chai1, dsm, esm_if1, esm1b,
  esmfold, …). It is a non-functional comment, so I rate it 🟠 and note it belongs to a single global
  cleanup pass rather than a per-model fix.
- **Fix:** Repo-wide: drop the internal env name from the shared usage comment (or replace with a
  generic "target environment").

---

## 🟡 Nits

### 10. `TODO` HTML comments shipping in knowledge-graph docs
- **Category:** Template/TODO residue
- **Location:** `README.md:125`, `MODEL.md:55`, `BIOLOGY.md:53`
- **Detail:** Three `<!-- TODO: Add ... once PDF is available in R2 -->` comments ship in the public
  docs. (Note: the `pdf_r2: pending` / `md_r2: pending` entries in `sources.yaml` are the house
  convention — `esm2`/`dummy` use `pending` too — so those are **not** flagged.)
- **Fix:** Either fill in the numbers or remove the TODO comments before launch.

### 11. `_load_litabb3_checkpoint` uses the module global in the path but its param only for logging
- **Category:** Readability / fragility
- **Location:** `models/abodybuilder3/app.py:124-134`
- **Detail:** The method signature takes `model_type_name` but the checkpoint path interpolates the
  module-level global `model_type` (`f"{self.model_dir}/{model_type}-loss/..."`), while
  `model_type_name` is used only in log strings. They happen to always match at the call sites, but the
  split is confusing and could load the wrong checkpoint if the two ever diverge.
- **Fix:** Use `model_type_name` (the parameter) consistently in both the path and the logs.

### 12. `seed_everything` docstring is positioned after import statements (not a real docstring)
- **Category:** Style
- **Location:** `models/abodybuilder3/app.py:248-257`
- **Detail:** The `"""Set seed for reproducibility..."""` block appears after the `import` lines inside
  the function body, so it is a no-op string expression, not the function's `__doc__`. (Copied from
  immunebuilder.)
- **Fix:** Move the docstring to the first statement of the function.

### 13. `REQUIRED_FILES` is defined but never used
- **Category:** Dead code
- **Location:** `models/abodybuilder3/download.py:50-56`
- **Detail:** The list looks intended for marker-gated R2 validation but nothing references it.
- **Fix:** Wire it into the R2 marker/validation check or delete it.

### 14. Display name capitalization diverges from the published model name
- **Category:** Naming consistency
- **Location:** `models/abodybuilder3/schema.py:24` (`display_name = "AbodyBuilder3"`); mixed usage in
  `README.md`, `sources.yaml`
- **Detail:** The published/canonical name is "**ABodyBuilder3**" (capital B; see the paper title in
  `sources.yaml:18`). The repo standardizes on "AbodyBuilder3" (lowercase b), and the docs mix both
  forms. Cosmetic, but the public display name does not match the upstream name.
- **Fix:** Decide on one capitalization for the display name and apply it consistently (the slug
  `abodybuilder3` can stay as-is).

---

## Definition-of-Done notes (per rubric D)
- **Layout / config / actions:** Met. Standard files present; `ModelFamily` with `modal_class_name`,
  `action_schemas`, variants, tags; single `fold` action (correct verb for a folding model).
- **Acquisition (A7):** Met. Documented custom strategy (Zenodo tar + HF flat → one dir), R2 self-
  population enabled, and `huggingface_hub` correctly listed in `setup_download_layer(extra_pip_…)`
  for the build-time fallback import.
- **Licensing (A8):** Met. Per-model Apache-2.0 LICENSE ("Copyright 2024 Exscientia") consistent with
  `sources.yaml`.
- **Errors/logging (A5/A6):** Mostly met (structured logging, no `print`); but the optional-required
  chain bug (#3) routes a user error to a 500, an A5 gap.
- **Schema field names/descriptions (A3/A4):** Mostly met (canonical `heavy_chain`/`light_chain` +
  aliases, `items`, descriptions render via `Annotated[..., Field]`); pLDDT output (A4) is inaccurate
  (#1, #2).
- **Knowledge graph (A9):** Partially met — internally consistent slug/display_name, but dead cross-
  refs (#6) and shipped TODOs (#7, #10).
- **Tests (A10):** Partially met — lazy fixtures, no module-scope R2; but only one `fold` case and the
  `plddt=True` path appears uncovered (#1).

---

## Verification

Adversarial re-review of the 9 flagged findings. Verdict + one-line evidence each.

1. **pLDDT response type mismatched; plddt=True may 500 — REAL.** Upstream `compute_plddt` (loss.py:415-427) sums over the bin dim (`dim=-1`) → shape `[batch, N_res]` (2D); app.py:236 `output["plddt"].squeeze(0).tolist()` → flat `list[float]`, but schema.py:123 declares `Optional[list[list[float]]]`, so the `AbodyBuilder3PredictResponseResult(**result_dict)` (app.py:238) raises ValidationError inside the try, re-raised at app.py:242 → 500; the single test.py fixture exercises only the default (plddt=False) path.
2. **pLDDT scale & 'per-chain' docs contradict code — REAL.** Upstream `compute_plddt` returns `pred_lddt_ca * 100` (0-100); README.md:73 says "0--1 scale" and :66 shows `[[0.85, 0.92, ...]]` (0-1 values, both wrong) while schema.py:125 and BIOLOGY.md:35,115 correctly say 0-100; app.py:236 squeezes one combined Fv tensor and never splits by chain, so the "one list per chain" / two-inner-list framing is inaccurate.
3. **Required chain fields silently optional — REAL.** schema.py:69-93 type `heavy_chain`/`light_chain` as `str` but pass `Field(None, ...)` (first positional = default), making both default-None/optional; Pydantic skips validators on defaults, so `items:[{}]` validates, then `string_to_input(heavy=None, light=None)` (app.py:208) raises inside fold() → re-raised → 500 instead of 422. House pattern is `Field(..., min_length=1)` (esm2/schema.py:67).
4. **Resource-spec dict defined twice — REAL.** Identical `ABODYBUILDER3_VARIANT_RESOURCE_SPECS` in schema.py:41-48 and config.py:30-37; grep shows only config.py:67 references it, so the schema.py copy is dead and solely justifies the `ModalGPU, ModalResourceSpec` import at schema.py:17.
5. **seed_everything copy-pasted & drifted — REAL.** Near-identical method in app.py:246-279 and immunebuilder/app.py:356; immunebuilder guards `torch.cuda.*` with `if torch.cuda.is_available()` while this copy calls `torch.cuda.manual_seed(seed)` unconditionally (app.py:264) and additionally pulls in `pytorch_lightning` — confirmed duplication + drift; belongs in commons.
6. **comparison.yaml references missing slugs — REAL.** comparison.yaml:59 `model: "propermab"` and :65 `model: "ablef"`; `ls models/` shows neither dir exists (mpnn at :51 does exist and is not flagged), so both are dead machine-consumed cross-refs.
7. **Shipped TODO in runtime code — REAL.** schema.py:73 ships `# TODO: check if extended or unambiguous should be validated` adjacent to the live `validate_aa_extended` BeforeValidator.
8. **README says Python 3.9 but image builds 3.10 — REAL.** README.md:160 states `python_version="3.9"`; app.py:42 uses `python_version="3.10"` and environment_gpu.yml:11 pins `python=3.10`.
9. **Internal 'qa' env name in usage comment — REAL.** app.py:287 contains `# Force deploy to "qa" or "main" environment:`; the exact comment exists (and is copy-pasted from the internal reference). Non-functional/orange, but the factual claim holds.

**Summary: 9/9 REAL.** Findings 1 and 2 were upgraded from "likely/uncertain" to confirmed via the upstream Exscientia source at the pinned commit (`src/abodybuilder3/openfold/model/heads.py:47`, `.../utils/loss.py:415` `compute_plddt`): output["plddt"] is 2D `[batch, N_res]` on a 0-100 scale, so `squeeze(0).tolist()` is a flat `list[float]` (mismatches `list[list[float]]`) and the README's 0-1 / per-chain claims are wrong.
