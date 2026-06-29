# Review — `models/dna_chisel/`

**Target:** `models/dna_chisel/` (DNA-Chisel, single-variant, algorithmic DNA feature extractor)
**Reviewer:** independent round-1, graded against `.planning/reviews/round-1/RUBRIC.md` §A–D
**Reference baselines:** `models/esm2/` (house pattern), `models/dummy/` (template)

## Summary

DNA-Chisel is a clean, well-documented algorithmic (non-ML) model that wraps the Edinburgh Genome
Foundry DnaChisel library to compute 20 DNA features through a single `encode` action. The layout is
complete (all 4 code files + 5 knowledge-graph files + LICENSE), no internal leakage was found
(`biolm-modal`, `.planning`, `qa`, internal domains all absent), logging is structured (`get_logger`,
no `print`), the MIT LICENSE is correct and matches `sources.yaml`, and as an algorithmic model it
correctly has no `download.py`/weight-acquisition layer.

There is **one must-fix correctness bug**: setting `restriction_enzymes=None` — explicitly documented
as the way to "disable" the feature — crashes with an unhandled `TypeError` (→ HTTP 500) whenever the
restriction-site feature is in `include` (which it is by default). Beyond that, the model is the lone
outlier among 39 snapshot-enabled models in its base class, its schema classes are mis-named
`...Predict...` for an `encode` action, it carries a `SEQUENCE_OPTIMIZATION` tag the wrapper never
implements, `comparison.yaml` references a non-existent model slug (`nt`), and `MODEL.md` mis-describes
the CAI algorithm. The rest are documentation/polish nits.

---

## 🔴 Must-fix

### 1. `restriction_enzymes=None` crashes the endpoint (documented input → HTTP 500)
- **Category:** Correctness / broken public contract
- **Location:** `app.py:154-169` (`compute_restriction_site_count`) + `app.py:407-410`; field doc at `schema.py:79-82`
- **Detail:** `schema.py:81` documents the field as *"Set to None or an empty list to disable."* and the
  `before` validator (`schema.py:84-101`) explicitly returns `None` unchanged ("Allow disabling enzyme
  checking"). But `encode` only gates the call on membership in `include`, not on the enzyme list, and
  `include` defaults to **all 20 features** (`schema.py:71-74`), so `RESTRICTION_SITE_COUNT` is present
  by default. `compute_restriction_site_count` then does `for enzyme in enzymes:` with `enzymes=None`,
  raising `TypeError: 'NoneType' object is not iterable`. The decorator's catch-all
  (`decorator.py:454-462`) turns this into a 500 "Uncaught exception". So the documented "disable"
  path — reachable with **just** `restriction_enzymes=None` and default `include` — guarantees a 500.
  (Empty list `[]` works fine and returns `{}`; only `None` crashes, so the two documented disable
  values behave differently.)
- **Fix:** Treat `None` like `[]` at the call site or in the compute method, e.g. guard
  `restriction_enzymes = payload.params.restriction_enzymes or []` before the loop (and/or skip the
  feature entirely when the list is falsy). Add a test case for `restriction_enzymes=None`.

---

## 🟠 Should-fix

### 2. Lone deviation from `ModelMixinSnap` among all snapshot-enabled models
- **Category:** Convention / uniformity ("plumbing, not science")
- **Location:** `app.py:56` — `class DnaChiselModel(ModelMixin)`
- **Detail:** The model sets `enable_memory_snapshot=True` (`app.py:52`) and uses
  `@modal.enter(snap=True)`, but subclasses plain `ModelMixin`. Every other snapshot-enabled model in
  the repo (38 of them — esm2, dummy template, dnabert2, omni_dna, evo, …) subclasses `ModelMixinSnap`,
  which supplies the framework's snapshot-lifecycle hooks (`a_snapshot_enter`/`z_snapshot_enter` and
  `save_snapshot_uptime`, see `models/commons/model/base.py:39-59`). DNA-Chisel is the only outlier, so
  it silently skips the framework's snapshot bracketing — exactly the kind of plumbing divergence the
  repo's north star ("the diff between two models should be the science, not the plumbing") forbids.
- **Fix:** Change the base class to `ModelMixinSnap` (the existing `load_model`/`setup_model` enter
  methods can stay as-is).

### 3. Schema classes named `...Predict...` for an `encode` action
- **Category:** Naming convention / cross-model consistency
- **Location:** `schema.py:104-216` (`DnaChiselPredictRequest`, `DnaChiselPredictRequestItem`,
  `DnaChiselPredictRequestParams`, `DnaChiselPredictResponse`, `DnaChiselPredictResponseResult`);
  wired at `config.py:41-47` and used by `app.py:380-384`
- **Detail:** The only action is `encode` (and `config.py:40` even comments "action name is encode, not
  predict"), yet every request/response class is named after `Predict`. The house pattern names schema
  classes after the action: esm2's encode action uses `ESM2EncodeRequest`/`ESM2EncodeResponse`
  (`models/esm2/schema.py:75-87,185-188`), reserving `...Predict...` for its actual `predict` action.
  Class names aren't part of the wire JSON, so renaming is safe.
- **Fix:** Rename to `DnaChiselEncodeRequest` / `…RequestItem` / `…RequestParams` /
  `DnaChiselEncodeResponse` / `…ResponseResult` and update `config.py`/`app.py` imports.

### 4. `SEQUENCE_OPTIMIZATION` tag overstates the deployed capability
- **Category:** Knowledge-graph / tag accuracy
- **Location:** `config.py:36` (`task=[Task.SEQUENCE_OPTIMIZATION, Task.FEATURE_EXTRACTION]`); echoed in
  `sources.yaml:12-13`
- **Detail:** The wrapper exposes only `encode` (feature extraction); it has **no** optimization/design
  endpoint. The model's own `comparison.yaml:26` lists as a weakness *"No generative capability — cannot
  design or optimize sequences; only evaluates existing sequences"*, and the README one-liner scopes it
  to "quality control and sequence characterization". Tagging the deployed model with
  `SEQUENCE_OPTIMIZATION` (which drives catalog/discovery) advertises a capability that isn't shipped.
  The upstream *library* optimizes, but this endpoint does not.
- **Fix:** Drop `Task.SEQUENCE_OPTIMIZATION` from `config.py` (keep `FEATURE_EXTRACTION`); align
  `sources.yaml` `tasks:` accordingly, or clearly scope the optimization claim to the upstream library.

### 5. `comparison.yaml` references a model slug that does not exist (`nt`)
- **Category:** Knowledge-graph consistency
- **Location:** `comparison.yaml:53` (`alternatives: - model: "nt"`) and `comparison.yaml:64`
  (`complements: - model: "nt"`)
- **Detail:** The file's own header (`comparison.yaml:8`) states *"All referenced model slugs must exist
  in models/"*. There is no `models/nt/` (nor `nucleotide_transformer`) in the repo. Notably,
  `comparison.yaml:55` itself flags `nt` as having a "non-commercial license", which is the likely reason
  it was excluded — making this a permanently dangling structured reference that catalog tooling cannot
  resolve. (The `dnabert2`/`evo`/`evo2` references are valid; only `nt` is missing.)
- **Fix:** Remove the `nt` entries from `alternatives`/`complements`, or replace with an existing DNA
  model (`dnabert2`, `omni_dna`, `evo2`). Prose mentions of "Nucleotide Transformer" in README/BIOLOGY
  are fine as long as no structured slug points to a non-existent model.

### 6. `MODEL.md` mis-describes the CAI algorithm; metric is a non-standard "naive CAI"
- **Category:** Docs/code mismatch + correctness of a reported metric
- **Location:** `MODEL.md:104` ("CAI: python_codon_tables lookup + **geometric mean**") vs
  `app.py:132` (`return float(self.np.mean(weights))` — arithmetic mean); schema desc `schema.py:135-137`
- **Detail:** The standard Codon Adaptation Index is the **geometric** mean of per-codon relative
  adaptiveness. `compute_cai` computes the **arithmetic** mean (`np.mean`), and its own docstring is
  honest about being "naive … return the average" — but `MODEL.md` claims geometric mean, and the schema
  description presents the value as plain "Codon Adaptation Index (CAI)". Users comparing against
  published CAI values will get systematically different numbers.
- **Fix:** Either correct `MODEL.md` to say arithmetic mean and add a "naive approximation, not the
  classical geometric-mean CAI" caveat to the `cai` field description, or change `compute_cai` to a true
  geometric mean (`exp(mean(log(weights)))` over non-zero weights) to match the documented/standard
  definition.

---

## 🟡 Nits

### 7. `comparison.yaml` `model_slug` uses underscore, mismatching config/sources
- **Category:** Slug consistency
- **Location:** `comparison.yaml:10` (`model_slug: "dna_chisel"`) vs `config.py:20`
  (`base_model_slug = "dna-chisel"`) and `sources.yaml:1` (`model_slug: dna-chisel`)
- **Detail:** Rubric A9 asks the slug to match config. `comparison.yaml` uses the directory name
  (underscore) rather than the public slug (hyphen). This is a repo-wide pattern (omni_dna, esm_if1 do
  the same) — but `thermompnn_d/comparison.yaml` correctly uses the hyphen form, showing the intended
  convention. Flagging here; likely worth a global sweep.
- **Fix:** Set `model_slug: "dna-chisel"` to match `config.py`/`sources.yaml`.

### 8. No upper bound on input sequence length on a 0.25-CPU / 1 GB container
- **Category:** Robustness
- **Location:** `schema.py:104-109` (`DnaChiselPredictRequestItem.sequence` has `min_length=1`, no
  `max_length`); `MODEL.md:38` ("Max length: No hard limit")
- **Detail:** Several features are super-linear (`compute_gc_content_std_dev` is O(n·window),
  `compute_hairpin_score` builds a `DnaOptimizationProblem`), and the container is provisioned at
  0.25 CPU / 1 GB (`config.py:19-23`). An unbounded sequence is a latency/OOM risk. esm2 bounds inputs
  with `max_length=ESM2Params.max_sequence_len`.
- **Fix:** Add a sane `max_length` (e.g. a `max_sequence_len` on `DnaChiselParams`) to fail oversized
  inputs as a 422 rather than risk a container timeout/OOM.

### 9. `sources.yaml` primary paper/repo artifacts unpopulated; one templated filename
- **Category:** Knowledge-graph completeness
- **Location:** `sources.yaml:24,26` (`pdf_r2: pending`, `md_r2: pending`), `:30-31`
  (`commit: ''`, `snapshot_r2: pending`), `:78` (`pdf_r2: .../unknown2025c.pdf`)
- **Detail:** esm2 populates `pdf_r2`/`md_r2`/`commit` for its **primary** paper and repo
  (`models/esm2/sources.yaml:29-49`), leaving `pending` only on applied-literature artifacts. DNA-Chisel
  leaves even the primary paper PDF/MD and the repo commit/snapshot as `pending`/empty. The one populated
  applied path uses a template-ish filename `unknown2025c.pdf` and an underscore path segment
  (`.../models/dna_chisel/...`) inconsistent with the hyphen slug.
- **Fix:** Populate primary-paper `pdf_r2`/`md_r2`, pin the source-repo `commit`, and rename/repath the
  `unknown2025c.pdf` artifact (or set it back to `pending` for consistency with the others).

### 10. README calls GC content a "Percentage" but it's a 0–1 fraction
- **Category:** Docs accuracy
- **Location:** `README.md:50` ("GC Content: Percentage of G and C nucleotides")
- **Detail:** `schema.py:131-133` and the README's own example (`README.md:97`, `0.556`) show GC content
  as a fraction in [0, 1], not a percentage.
- **Fix:** Reword to "Fraction of G and C nucleotides (0–1)".

### 11. Input validator rejects lowercase DNA, contradicting the "uppercased" doc claim
- **Category:** Docs/code consistency
- **Location:** `schema.py:107` (`BeforeValidator(validate_dna_unambiguous)`) →
  `models/commons/data/validator.py:53-58` (regex `^[ACTG]+$`, no `IGNORECASE`); vs `MODEL.md:36`
  ("Preprocessing | Uppercased before feature computation") and `app.py:388` (`item.sequence.upper()`)
- **Detail:** Lowercase input (`"atgc"`) fails validation (422) before reaching `encode`, so the
  `MODEL.md` claim that input is uppercased — implying lowercase is accepted — is misleading, and the
  `.upper()` in `app.py` is effectively dead for any input that passed validation.
- **Fix:** Either accept lowercase (use a case-insensitive validator and keep `.upper()`) or update
  `MODEL.md` to state that input must be uppercase A/C/G/T.

### 12. `encode` is a 75-line, 20-branch `if`-chain (`# noqa: C901`)
- **Category:** Simplicity / maintainability
- **Location:** `app.py:380-469`
- **Detail:** The 20 near-identical `if FEATURE in include: out.x = self.compute_x(...)` blocks require a
  `# noqa: C901` suppression and must be edited in lockstep with the enum and the response schema. A
  dispatch table keyed by `DnaChiselFeatureOptions` (value → bound compute fn, with flags for the few
  that need `species`/`enzymes`) would remove the suppression and the duplication.
- **Fix:** Replace the chain with a dict-driven dispatch loop over `payload.params.include`.

---

## D. Definition-of-Done audit (this model)

- **Standard layout (A1):** Met — `app.py`, `config.py`, `schema.py`, `test.py`, `fixture.py`, all 5
  knowledge-graph files, `LICENSE`, `__init__.py` present; `config.py` defines a `ModelFamily` with
  `modal_class_name`, `action_schemas`, tags, naming/resource functions.
- **Actions (A2):** Met — uses the closed-set verb `encode`; no invented verbs (but see finding #3 on
  schema-class naming).
- **Schema field names (A3):** Met — `items`/`params`/`sequence`/`results` per house convention.
- **Field descriptions (A4):** Met — every request/response field has a rendering `Field(description=…)`;
  no leaked sequences/secrets.
- **Errors (A5):** Partially met — validator `ValueError`s are the standard Pydantic pattern (mapped by
  the decorator), but finding #1 is an unhandled runtime `TypeError` on documented input.
- **Logging (A6):** Met — `get_logger`, no `print`, sensible levels, no full-sequence logging.
- **Acquisition (A7):** N/A and correct — algorithmic model, no weights, deps pinned in the image; no R2
  weight layer needed.
- **Licensing (A8):** Met — per-model MIT `LICENSE` with EGF attribution, consistent with `sources.yaml`.
- **Knowledge graph (A9):** Partially met — present and readable, but see findings #4 (overstated task),
  #5 (dangling `nt` slug), #6 (CAI mis-description), #7 (slug form), #9 (pending artifacts).
- **Tests (A10):** Met — `TestSuite` with integration + deployment cases, fixtures generated via
  `FixtureGenerator`, no module-scope R2/network. No shared DNA asset exists yet in
  `shared_assets.py` (proteins only), so the small hardcoded `"ATGCGTACG"` is acceptable. Recommend
  adding the `restriction_enzymes=None` regression case (finding #1).

## Verification

Adversarial re-check of the six HIGH-severity findings against the actual code (tried to refute each):

1. **restriction_enzymes=None crashes endpoint — REAL.** Confirmed end-to-end: schema.py:79-82 documents
   "Set to None or an empty list to disable" with default `["EcoRI","BsaI"]`; before-validator schema.py:89-90
   returns None unchanged; `include` defaults to ALL features (schema.py:71-74), so RESTRICTION_SITE_COUNT is
   gated in by default (app.py:407); compute_restriction_site_count does `for enzyme in enzymes` (app.py:160)
   → `TypeError: 'NoneType' object is not iterable` → decorator.py:454-462 "Uncaught exception" / 500. Empty
   list yields `{}` (loop no-ops), so the two documented disable values genuinely diverge.

2. **Lone non-ModelMixinSnap snapshot model — REAL (count off by one).** app.py:56 subclasses plain
   `ModelMixin` while app.py:52 sets `enable_memory_snapshot=True` and app.py:59 uses `@modal.enter(snap=True)`.
   Grep: 40 app.py files set the snapshot flag, 39 subclass `ModelMixinSnap`, and dna_chisel is the only
   exception — so it is the lone outlier (the "38 other" in the finding is actually 39). The skipped hooks
   (base.py:49-59) are documented no-ops, so functional impact is nil, but the uniformity divergence is real.

3. **Schema classes named ...Predict... for an encode action — REAL.** config.py:40 comment + ENCODE-only
   wiring (config.py:43-47) yet schema.py:104-216 names every class DnaChiselPredict*. House pattern confirmed
   against esm2: encode→ESM2EncodeRequest/Response (config.py:73-75), Predict reserved for the real predict
   action (config.py:78-80). Class names are not on the wire, so rename is safe.

4. **SEQUENCE_OPTIMIZATION tag overstates capability — REAL.** config.py:36 tags
   `Task.SEQUENCE_OPTIMIZATION`, echoed sources.yaml:12-13, but the only deployed action is encode
   (feature extraction); comparison.yaml:26 self-contradicts ("cannot design or optimize sequences; only
   evaluates existing sequences"). No optimization/design endpoint exists.

5. **comparison.yaml references non-existent slug `nt` — REAL.** Structured `model: "nt"` refs at
   comparison.yaml:53 and :64; header rule comparison.yaml:8 requires slugs to exist in models/; `ls models/`
   confirms no `nt` nor `nucleotide_transformer`. The other structured refs (dnabert2/evo/evo2) all resolve.

6. **MODEL.md mis-describes CAI as geometric mean — REAL.** MODEL.md:104 says "geometric mean"; app.py:132
   uses `np.mean` (arithmetic), and the docstring app.py:114-117 admits it is a "naive ... average". Standard
   CAI is the geometric mean of relative adaptiveness, so reported values differ systematically; schema.py:135-137
   presents the field as plain "CAI" with no caveat.
