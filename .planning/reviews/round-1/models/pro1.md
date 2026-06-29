# Review — `models/pro1/` (Round 1)

**Reviewer verdict:** Solid, well-engineered port. The app/schema/config plumbing is clean, idiomatic,
and largely conformant to the house pattern (canonical `generate` action, glossary-exact param
descriptions, typed errors, structured logging, RNG-seeding, deterministic mutation-applier fallback,
snapshot-disable approach correctly mirroring `e1`). The blocking issues are documentation/license
hygiene rather than code correctness: a shipped LICENSE that still carries an internal "NOTE TO
MAINTAINERS / confirm before public release" block, a README that describes a memory-snapshot setup the
code explicitly disabled, a deprecated acquisition helper that pro1 is the named blocker for removing,
and a `params` field that is required despite being documented as optional.

Cross-checked against `models/esm2/` (reference), `models/dummy/` (template), `models/e1/`,
`models/evo/`, `models/progen2/`, `tooling/field_glossary.yaml`, and
`models/commons/storage/download_helpers.py`.

---

## 🔴 Must-fix before launch

### 1. LICENSE ships an internal "NOTE TO MAINTAINERS" + unconfirmed license/holder
- **Category:** Licensing / internal-leakage / DoD
- **Location:** `models/pro1/LICENSE:186-192`
- **Detail:** The public LICENSE ends with a "NOTE TO MAINTAINERS: The Pro-1 license above is a
  BEST-EFFORT attribution… Before public release, confirm the intended license, the copyright holder /
  year, and the Llama 3.1 base-model redistribution terms with the author (Michael Hla)." This is
  internal process content leaking into a shipped file **and** a self-admitted unresolved
  launch-gating task. Rubric A8 requires "no inferred holder/year left unflagged"; here the holder/year
  is effectively inferred (the Apache appendix has no `Copyright [yyyy] [name]` line; the upstream
  GitHub repo has no LICENSE file, only the HF card asserts Apache-2.0). The actual licensing *analysis*
  is sound (adapter Apache-2.0; Llama base correctly carved out in the NOTICE and never redistributed —
  see `download.py:99-104`), but the un-actioned maintainer note cannot ship.
- **Fix:** Before launch, confirm the license + copyright holder/year with the author; add a proper
  `Copyright 2025 Michael Hla` line; **delete the "NOTE TO MAINTAINERS" paragraph**. Keep the
  Apache-2.0 body and the NOTICE attribution block (those are correct and good).

---

## 🟠 Should-fix

### 2. Uses the deprecated `acquire_library_managed_model` (pro1 is the named removal blocker)
- **Category:** Acquisition / convention (A7)
- **Location:** `models/pro1/download.py:94-105`
- **Detail:** `download_helpers.py:149-152` marks `acquire_library_managed_model` **deprecated** —
  "retained only until `evo`/`pro1` migrate (Phase 2), after which it is removed." The canonical
  replacement `r2_then_library` (`download_helpers.py:463`) already exposes the exact
  `cache_to_r2=False` knob pro1 needs, and its docstring literally names pro1 as the use-case
  ("…cannot be redirected into `target_dir` (e.g. `evo`/`pro1`)"). esm2 uses `r2_then_library`. Staying
  on the deprecated wrapper keeps dead code alive and diverges pro1's plumbing from the house pattern.
- **Fix:** Migrate to `r2_then_library(base_model_slug=…, params_version=…, library_name="pro1",
  init_fn=init_fn, cache_to_r2=False)`. Drop `monitor_directories` (no longer read per the docstring).
  This also adds the R2-primary marker read that pro1 currently skips.

### 3. README describes a memory-snapshot setup the code explicitly disabled
- **Category:** Docs/correctness mismatch (B-correctness, C-docs)
- **Location:** `models/pro1/README.md:189` and `models/pro1/README.md:195` vs `models/pro1/app.py:263-268,282`
- **Detail:** README states "Cold start | ~60 s (snapshot restore)" and "Memory snapshot
  (`@modal.enter(snap=True)`) used for fast cold start — weights loaded once, LoRA applied at runtime."
  But `app.py:263-268` is an explicit NOTE that snapshots are **disabled** for Pro-1, the class uses a
  plain `@modal.enter()` (no `snap=True`, `app.py:282`), and the NOTE quantifies the trade-off as
  "slower cold start (~3 min vs ~30 s with snap)." The README's claims are simply wrong. (The code is
  correct and consistent with `e1/app.py:86-108`, which pro1 cites.)
- **Fix:** Update README to state snapshots are disabled (unsloth + bitsandbytes 4-bit not
  snapshot-compatible) and cold start is ~3 min. Also fix the stale `setup_model` docstring
  "(snapshotted)" at `app.py:284`.

### 4. `params` is required but documented (and treated elsewhere) as optional
- **Category:** Schema/contract (A4, B-correctness)
- **Location:** `models/pro1/schema.py:156-158`
- **Detail:** `params: Pro1GenerateParams = Field(description="Optional parameters controlling this
  action (defaults are used when omitted).")` has **no default**, so a client that omits `params`
  (taking the description at its word) gets a 422. esm2 (`schema.py:76-79`) and evo
  (`schema.py:107-108`) correctly use `default_factory`. (Note: progen2 `schema.py:79-81` shares the
  same defect, so this is a small systemic inconsistency worth fixing consistently.)
- **Fix:** `params: Pro1GenerateParams = Field(default_factory=Pro1GenerateParams, description=…)`.

### 5. Verification docs still carry TODO + "PENDING" placeholders; verification never run
- **Category:** Knowledge graph completeness (A9)
- **Location:** `models/pro1/README.md:174,178`, `models/pro1/MODEL.md:99`
- **Detail:** README ships `<!-- TODO: Run verification … -->` and "**PENDING** — awaiting initial
  deployment"; MODEL.md ships the same TODO under "BioLM Verification Results." Rubric A9 forbids stray
  TODO/pending shipping. This is partly the in-progress house state (esm2/dummy verification sections
  also carry TODOs), but pro1 is *more* incomplete: esm2 at least ships a populated verification
  test-case table, whereas pro1's status is wholly PENDING. The model also defines a concrete check
  ("verify K116E appears with a salt-bridge rationale") that is cheap to run once deployed.
- **Fix:** Run the FGF-1 K116E verification, fill in the result, and remove the TODO/PENDING markers
  (or sweep centrally in the W14 docs pass — flag this one as not-yet-done either way).

### 6. Internal `qa` env name leaks in the `__main__` usage docstring
- **Category:** Internal leakage (C)
- **Location:** `models/pro1/app.py:430`
- **Detail:** `# Force deploy to "qa" or "main" environment:` — `qa` is an internal env name the rubric
  (C) calls out explicitly. This is **repo-wide** (identical line at `esm2/app.py:484`; "QA deployment"
  also appears in esm2 README/MODEL TODOs), so it is house-pattern boilerplate rather than a pro1
  regression — but it still ships publicly and should be scrubbed centrally before launch.
- **Fix:** Reword to a generic "deploy to your target environment" across all models' `__main__`
  blocks; do not name internal environments in shipped files.

---

## 🟡 Nits / minor

### 7. `.planning` workstream code "W8" in a shipped comment
- **Category:** Internal leakage (C)
- **Location:** `models/pro1/config.py:78`
- **Detail:** `# The @biolm_model_class container class in app.py (gateway routing, W8).` — "W8" is a
  `.planning/03_WORKSTREAMS.md` workstream id. Systemic (identical at `esm2/config.py:57`), so fix
  centrally; flagged here for completeness. Fix: drop the "(…, W8)" suffix.

### 8. sources.yaml references the internal authoring skill
- **Category:** Internal leakage (C)
- **Location:** `models/pro1/sources.yaml:84-85`
- **Detail:** "The skill's minimum-5-entry target is documented as relaxed for this model pending
  broader academic uptake." References the internal `model-knowledge-base` authoring skill/process,
  which should not appear in a shipped manifest. Fix: reword to "Only one direct Pro-1 application
  exists; entries 2-4 are paradigm-adjacent" without referencing the authoring tooling.

### 9. `results` semantics differ from the house meaning (per-iteration vs per-input)
- **Category:** Consistency (A3/C)
- **Location:** `models/pro1/schema.py:205-207`, `models/pro1/app.py:347-422`
- **Detail:** Everywhere else `results` is "Per-input results, returned in the same order as the
  request items" (esm2/progen2). Here `items` is capped at exactly 1 and `results` holds one entry per
  *generation iteration*. Defensible given the single-protein constraint, but a consumer expecting
  per-input parity may be surprised. Fix: keep, but make the description explicit that each entry is one
  independent generation attempt for the single input protein (current wording is OK; just ensure docs
  emphasize it).

### 10. Extracted `modified_sequence` is not length-validated
- **Category:** Correctness/robustness (B)
- **Location:** `models/pro1/app.py:381-388`; field at `schema.py:196-199`
- **Detail:** After extraction only invalid-AA characters are checked; a stray `\boxed{M}` (regex
  `[A-Z]+`, min length 1 at `app.py:183`) would be accepted and returned as a 1-residue
  "modified_sequence." The response field has no `min_length`. The test validator enforces `>=10` but
  production does not. Fix: reject extractions that are implausibly short (e.g. `< 10` or
  `< 0.5*len(original)`) before assigning, mirroring the validator.

### 11. README usage example uses a fabricated Carbonic Anhydrase II sequence
- **Category:** Docs accuracy (C)
- **Location:** `models/pro1/README.md:122`
- **Detail:** `sequence="MASGSVTTDCSTEKGSAYFAPWAPAPGWKPYQCTG..."` is not the real human CA-II sequence
  (real N-terminus is `MSHHWGYG…`, used correctly in `fixture.py:30`) and ends with `...`, so it is not
  copy-paste runnable. Fix: use the real fragment from `fixture.py` or label it clearly as a truncated
  placeholder.

### 12. "Stochastic even with seed" docs vs "reproducible sampling" schema
- **Category:** Docs consistency (C)
- **Location:** `models/pro1/comparison.yaml:38` (and MODEL.md/README) vs `models/pro1/schema.py:149` +
  `app.py:336-342`
- **Detail:** Docs say outputs are "stochastic even with seed," but `app.py` seeds python/numpy/torch
  RNG and the glossary-exact `seed` description promises "reproducible sampling." CUDA kernel
  nondeterminism can justify the docs, but the claim and the schema promise should be reconciled. Fix:
  in docs, say "seed makes sampling reproducible modulo GPU kernel nondeterminism" rather than a flat
  "stochastic even with seed."

---

## Conformance / DoD quick audit

- **Layout (A1):** All standard + 5 knowledge-graph files present; `ModelFamily` well-formed. ✅
- **Action verb (A2):** `generate` — correct for a sequence-proposing model; closed-set. ✅
- **Schema field names (A3):** `items`/`params`/`sequence`/`seed`/`temperature`/`top_p`/`results` all
  house-standard; bespoke per-protein fields are genuinely model-specific (not biology-in-field-names).
  Minor `results` semantics note (#9). ✅ (mostly)
- **Field descriptions (A4):** All render (Field at field level in `Annotated`, or as default value for
  `X | None`); verbatim params match `field_glossary.yaml` exactly. `params` default issue (#4). ✅
- **Errors (A5):** `UserError` raised for the no-results caller-visible case; exceptions logged with
  `exc_info` and only the exception *type name* echoed — no internal detail leak. ✅
- **Logging (A6):** `get_logger`, no `print`, sensible levels; sequences only at DEBUG (token count),
  not full sequences at INFO. ✅
- **Acquisition (A7):** Functional but on the **deprecated** helper (#2); intentionally does NOT
  self-populate R2 (base = Llama, cannot redistribute; well documented). The Apache-2.0 adapter *could*
  be cached but is left HF-managed — acceptable, deploy-time HF dependency. ⚠️ partial.
- **Licensing (A8):** Apache-2.0 body + correct Llama carve-out NOTICE, but maintainer note + missing
  copyright line block it (#1). ❌ until resolved.
- **Knowledge graph (A9):** Internally consistent (slug `pro1`, display `Pro-1`, variants match
  config↔README↔sources). TODO/PENDING residue (#5), skill reference (#8). ⚠️ partial.
- **Tests (A10):** `TestSuite` with integration + deployment cases, lazy validator, structural-only
  (correct for stochastic output). Fixtures hardcode FGF-1/CA-II fragments rather than reusing the
  shared test-asset library — minor; these are model-specific fragments. ✅ (mostly)

## Verification

Adversarial re-check of the six HIGH-severity findings (each re-read against cited lines):

1. **LICENSE ships internal 'NOTE TO MAINTAINERS' + unconfirmed license/holder/year — REAL.**
   `models/pro1/LICENSE:186-192` literally contains the "NOTE TO MAINTAINERS … BEST-EFFORT
   attribution … Before public release, confirm the intended license, the copyright holder / year,
   and the Llama 3.1 base-model redistribution terms with the author (Michael Hla)." The carve-out
   logic is sound (`download.py:99-104` `cache_to_r2=False`), but the un-actioned internal note ships
   in a public file.

2. **Uses deprecated `acquire_library_managed_model` (pro1 is the named removal blocker) — REAL.**
   `download.py:94` calls `acquire_library_managed_model`; `download_helpers.py:149-152` marks it
   `.. deprecated::` "retained only until evo/pro1 migrate (Phase 2), after which it is removed."
   The replacement `r2_then_library` (`download_helpers.py:463-488`) exposes `cache_to_r2=False`
   and names evo/pro1 in its docstring (483-485). pro1 stays on the deprecated wrapper.

3. **README describes a memory-snapshot setup the code disabled — REAL.**
   `README.md:189` "Cold start | ~60 s (snapshot restore)" and `README.md:195` "Memory snapshot
   (`@modal.enter(snap=True)`) used for fast cold start" contradict `app.py:263-268` (explicit NOTE:
   snapshots disabled, "~3 min vs ~30 s with snap") and `app.py:282` (plain `@modal.enter()`, no
   `snap=True`). README is wrong; code is correct.

4. **`params` required but documented/treated-elsewhere as optional — REAL.**
   `schema.py:156-158` `params: Pro1GenerateParams = Field(description="Optional parameters …")` has
   no `default`/`default_factory`, so it is required (omission → 422). Contrast `esm2/schema.py:76-77`
   which uses `default_factory=ESM2EncodeRequestParams`. Systemic (progen2 same defect) but real here.

5. **Verification docs still carry TODO + PENDING placeholders — REAL.**
   `README.md:174` `<!-- TODO: Run verification … -->`, `README.md:178` "**PENDING** — awaiting
   initial deployment", and `MODEL.md:99` the same TODO under "BioLM Verification Results." All
   present as cited.

6. **Internal 'qa' env name leaks in `__main__` usage docstring — REAL.**
   `app.py:430` `# Force deploy to "qa" or "main" environment:` ships the internal `qa` env name.
   House-wide boilerplate (identical at `esm2/app.py:484`) rather than a pro1 regression, but it does
   ship publicly as cited.

All six findings verified REAL against the cited lines; none refuted.
