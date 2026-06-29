# Review — `models/antifold/`

**Reviewer:** independent round-1 (rubric A–D)
**Verdict:** Solid, launch-track model. No 🔴 blockers found: no secret/internal leakage, license present & permissive
(BSD-3-Clause) and consistent with `sources.yaml`, all 11 standard files present, actions are in the closed set
(`encode/generate/score/log_prob`), and the Pydantic request validators were verified to actually fire (no validation
bypass). The main issues are a schema-naming deviation that breaks cross-model uniformity (a dedicated
`nanobody_chain_id` field that is functionally redundant with `heavy_chain_id`-only), a doc-vs-code contradiction
(README claims a CUDA base image; the code uses CPU `debian_slim`), a stale `TODO` + under-populated section in
`BIOLOGY.md`, and several pieces of dead schema code. All are 🟠/🟡.

Cross-checks performed: imported `schema.py` and exercised the validators (no-chain → rejected, nanobody+heavy →
rejected, aliases accepted, `heavy`-only vs `nanobody`-only both yield identical `_custom_chain_mode=True`); grep for
`biolm-modal`/`.planning`/internal domains (none); compared plumbing against `models/esm2/` and `models/dummy/`;
confirmed `pending` `pdf_r2/md_r2` in `sources.yaml` is the house pattern (esm2 identical) — not flagged.

---

## 🟠 should-fix

### 1. Dedicated `nanobody_chain_id` field violates the ratified antibody-naming standard and is redundant
- **Category:** Schema field names / cross-model uniformity
- **Location:** `models/antifold/schema.py:158-162`; `models/antifold/app.py:182-188, 203-206`
- **Detail:** Rubric A.3 ratifies "nanobody = lone `heavy_chain` + single-domain tag, **no** `vhh`". AntiFold instead
  adds a separate biology-specific selector `nanobody_chain_id`. Worse, it is functionally a no-op duplicate: I
  verified that `AntiFoldPredictRequestParams(heavy_chain_id="A")` and `AntiFoldPredictRequestParams(nanobody_chain_id="A")`
  both produce `_custom_chain_mode=True`, and `_prepare_pdb_input` routes both into the same `Hchain` column
  (`h_chain_input = params.heavy_chain_id if not params.nanobody_chain_id else params.nanobody_chain_id`, with
  `Lchain=None` in both cases). So the field adds API surface and a bespoke biology name for zero behavioral
  difference, exactly the "biology lives in tags, not field names" anti-pattern the rubric calls out.
- **Fix:** Remove `nanobody_chain_id` (and its alias/validator branches). Nanobody = caller supplies only
  `heavy_chain_id`; the `NANOBODY`/single-domain tag (already in `config.py`) carries the biology. Update README/
  MODEL/BIOLOGY examples accordingly. If a back-compat alias is desired, accept `nanobody_chain`/`vhh` as a
  `validation_alias` of `heavy_chain_id` rather than a distinct field.

### 2. README claims a CUDA PyTorch base image, but the build uses CPU `debian_slim`
- **Category:** Docs vs. code correctness
- **Location:** `models/antifold/README.md:329` vs. `models/antifold/app.py:50, 63-67`
- **Detail:** Implementation Notes state: "Container image: Based on `pytorch/pytorch:2.3.1-cuda12.1-cudnn8-runtime`".
  The actual image is `modal.Image.debian_slim(python_version="3.11")` with the CPU-only torch wheel
  (`index_url=".../whl/cpu"`). The header comment in `app.py:49` even says "AntiFold is CPU-only (gpu=None) — use
  debian_slim instead of heavy CUDA base image". An outside contributor reading the README would be actively
  misled about the runtime.
- **Fix:** Replace the README base-image line with the real `debian_slim` + CPU-torch description.

### 3. `BIOLOGY.md` ships a stale `TODO` and an under-populated "Applied Use Cases" section
- **Category:** Knowledge graph (completeness / no template residue)
- **Location:** `models/antifold/BIOLOGY.md:59-63`
- **Detail:** The Applied Use Cases section is a single hand-wave plus `<!-- TODO: Add applied literature entries as
  they become available -- see sources.yaml applied_literature -->`. Rubric A.9 forbids stray `TODO`/template
  residue in shipped knowledge-graph files; the reference model `models/esm2/BIOLOGY.md` carries no such comment
  (only the `dummy` template does). The TODO is also factually stale: `sources.yaml:39-88` already contains five
  `applied_literature` entries (PLoS ONE 2025 benchmark, RFdiffusion, AbBiBench, nanoFOLD, GPCR), none of which are
  reflected in this section.
- **Fix:** Delete the TODO comment and write the Applied Use Cases section from the populated
  `sources.yaml applied_literature` entries.

### 4. Dead schema code: three defined-but-unused classes
- **Category:** Simplicity / dead code
- **Location:** `models/antifold/schema.py:322` (`AntiFoldGenerateRequestItem`), `:431`
  (`AntiFoldGenerateResponseResultInput`), `:476` (`AntiFoldGenerateResponseResultSequences`)
- **Detail:** Repo-wide grep shows each class is referenced only at its own definition. `AntiFoldGenerateRequest`
  uses `AntiFoldBaseRequestItem` (not `AntiFoldGenerateRequestItem`, which is a byte-identical copy of the base
  item). `AntiFoldGenerateResponseResult.sequences` is typed `list[AntiFoldGenerateResponseResultSamples]`, so the
  `...Sequences` wrapper (with a `samples` field) and the `...Input` class are never instantiated. This is
  confusing scaffolding in a ~580-line schema and obscures the real response shape.
- **Fix:** Delete the three unused classes; have `AntiFoldGenerateRequest` reference `AntiFoldBaseRequestItem`
  explicitly (it already does).

---

## 🟡 nits

### 5. CPU-only model logs/docstrings say "directly on GPU"
- **Category:** Readability / log accuracy
- **Location:** `models/antifold/app.py:119, 125, 143-144, 148, 159`
- **Detail:** `setup_model` docstring and several `logger.info` strings say "Load model directly on GPU for GPU
  memory snapshot", but this model is `gpu=None` and `get_torch_device()` returns CPU. The wording is copy-pasted
  from the GPU template and contradicts the file's own `app.py:49` comment.
- **Fix:** Reword to "directly on `%s`" using `self.device` (already done for the load line at 142-146; apply to the
  rest).

### 6. `score` method docstring is wrong ("Inverse Fold the input pdb str")
- **Category:** Docs vs. code
- **Location:** `models/antifold/app.py:367-368`
- **Detail:** The `score` action scores how well the native sequence fits the backbone (`sample_n=0, score=True`);
  it does not generate/inverse-fold. The docstring is copied from `generate`.
- **Fix:** Describe scoring of the native sequence and the returned `global_score`.

### 7. Dead "set-then-raise" in the chain validator
- **Category:** Simplicity / dead code
- **Location:** `models/antifold/schema.py:190-195`
- **Detail:** In the `nanobody and (heavy or light)` branch, `instance._custom_chain_mode = True` is assigned on the
  line immediately before `raise ValueError(...)`, so the assignment can never be observed.
- **Fix:** Drop the assignment; just raise.

### 8. LICENSE link points to `blob/master`, while README/sources point to `blob/main`
- **Category:** Consistency / dead-link risk
- **Location:** `models/antifold/LICENSE:38` (`.../blob/master/LICENSE`) vs. `README.md:338` and `sources.yaml:5`
  (`.../blob/main/LICENSE`)
- **Detail:** Three files disagree on the upstream branch; one of the two URLs will rot.
- **Fix:** Point all three at the branch that actually resolves on `github.com/oxpig/AntiFold`.

### 9. `test_distinct_generate.py` diverges from the `TestSuite` pattern
- **Category:** Tests / consistency
- **Location:** `models/antifold/test_distinct_generate.py`
- **Detail:** Unlike `test.py` (which uses `TestSuite`/`generate_tests_from_suite` with R2 fixtures), this file
  hand-rolls `app.run()` + `model.generate.remote()`, hardcodes a synthetic 10-residue poly-peptide PDB inline, and
  its docstrings reference an internal "RNG seed fix" dev narrative. It does add real coverage (determinism /
  diversity) that the suite's count-only validator lacks, so keep it — but it should be folded into the shared
  harness or at least not read as porting scaffolding. Low priority.
- **Fix:** Migrate the diversity/reproducibility assertions into a `TestSuite` validator or a clearly-scoped extra
  test; drop the dev-narrative wording.

### 10. Patched BSD-3 source files carry no copyright header (low confidence)
- **Category:** Licensing / attribution
- **Location:** `models/antifold/external/main.py`, `models/antifold/external/antiscripts.py`
- **Detail:** These are modified redistributions of upstream BSD-3 source; clause 1 asks source redistributions to
  retain the copyright notice. The co-located `models/antifold/LICENSE` (which reproduces the upstream copyright and
  an attribution note) likely satisfies this, and upstream itself ships these files headerless — so this is a
  nicety, not a blocker.
- **Fix:** Optionally add a one-line "Modified from oxpig/AntiFold @ c306ae6 — BSD-3-Clause, see ../LICENSE" header
  to each patched file.

### 11. Model-call failures are not logged in `app.py` (minor inconsistency with esm2)
- **Category:** Logging / consistency
- **Location:** `models/antifold/app.py:211-446`
- **Detail:** `models/esm2/app.py` wraps each forward pass in `try/except` that `logger.error(..., exc_info=True)`
  before re-raising; AntiFold lets exceptions propagate straight to the `modal_endpoint` decorator. Behavior is
  fine (decorator sanitizes to 5xx), but operators lose the per-model error log line. Low priority.
- **Fix:** Optionally mirror esm2's log-and-reraise around the model utility calls.

---

## Definition-of-Done snapshot (A-section conformance)
- Layout / `ModelFamily` config: **met** (all standard files + extras `fixture.py`, `external/`, `download.py`).
- Actions in closed set / verbs match intent: **met** (`encode/generate/score/log_prob`; inverse folding → `generate`).
- Schema field names uniform: **partial** — `pdb`, `heavy_chain`/`light_chain` (with aliases) good; `nanobody_chain_id`
  deviates (finding 1).
- Field descriptions render: **met** (verified `Annotated[..., Field]` and direct `Field` usage; no `Optional[Annotated]`
  nesting that would drop descriptions).
- Errors typed: **met** (schema correctly raises `ValueError` inside Pydantic validators so they map to 422; not a
  bare-ValueError-in-runtime case).
- Logging: **met** (`get_logger`, no `print`), modulo the "on GPU" wording (finding 5) and finding 11.
- Acquisition canonical & self-populating: **met** (`download.py` uses `r2_then_urls`, caches back to R2).
- Licensing: **met** (BSD-3 LICENSE, consistent with `sources.yaml`; minor link drift, finding 8).
- Knowledge graph present/consistent: **partial** — slug/display_name consistent everywhere; `BIOLOGY.md` TODO +
  under-population (finding 3).
- Tests (integration + deployment, lazy fixtures): **met** (suite covers all 4 actions; finding 9 is a consistency nit).

## Verification

Adversarial re-review of the four HIGH-severity findings (re-read actual code; tried to refute each):

1. **`nanobody_chain_id` violates A.3 & is a behavioral no-op** — **REAL**. RUBRIC.md:29 ratifies
   "nanobody = lone `heavy_chain` + single-domain tag, no `vhh`" and A.3:27 "biology lives in tags, not
   field names". `schema.py:158-162` adds a biology-named selector `nanobody_chain_id`. Traced both paths:
   `heavy_chain_id='A'` (schema.py:203-204) and `nanobody_chain_id='A'` (schema.py:205-206) both set
   `_custom_chain_mode=True`, and `app.py:184-196` routes both into `Hchain` with `Lchain=None` → identical
   `input_df`. Confirmed redundant + standard-violating.

2. **README claims CUDA base image; build is CPU debian_slim** — **REAL**. README.md:329 states
   "Based on `pytorch/pytorch:2.3.1-cuda12.1-cudnn8-runtime`", but `app.py:50` is
   `modal.Image.debian_slim(python_version="3.11")` with CPU torch wheel `index_url=.../whl/cpu`
   (app.py:63-67), and app.py:49 comment explicitly says "use debian_slim instead of heavy CUDA base image".
   README is actively misleading.

3. **BIOLOGY.md stale TODO + under-populated Applied Use Cases** — **REAL**. `BIOLOGY.md:63` ships
   `<!-- TODO: Add applied literature entries ... -->` under a one-sentence hand-wave section (lines 59-61),
   violating A.9 (RUBRIC.md:43 "no stray TODO ... shipping"). `esm2/BIOLOGY.md` has no such comment (grep:
   only the `## Applied Use Cases` header). `sources.yaml:39-88` already lists 5 applied_literature entries
   (PLoS ONE benchmark, RFdiffusion, GPCR, AbBiBench, nanoFOLD) — none reflected in the section. Stale + thin.

4. **Three defined-but-unused schema classes** — **REAL**. Repo-wide grep (.py/.md/.json) shows
   `AntiFoldGenerateRequestItem` (schema.py:322), `AntiFoldGenerateResponseResultInput` (schema.py:431), and
   `AntiFoldGenerateResponseResultSequences` (schema.py:476) each referenced ONLY at their own definition.
   `AntiFoldGenerateRequest.items` uses `AntiFoldBaseRequestItem` (schema.py:339); diff confirms the ...RequestItem
   body is byte-identical to the base. `AntiFoldGenerateResponseResult.sequences` is typed
   `list[AntiFoldGenerateResponseResultSamples]` (schema.py:499), so the ...Sequences wrapper is never
   instantiated. Dead scaffolding (rubric B "Simplicity / 10x").

**Verdict: all 4 findings REAL.**
