# Round-1 Review — Commons Framework Architecture

**Dimension:** Commons framework architecture
**Scope:** `models/commons/` (model/, core/, data/, storage/, modal/, util/, testing/)
**Reviewer focus:** ModelFamily, decorators, Modal image helpers, base Pydantic, EnhancedStringEnum,
R2 storage/download. Modularity, abstraction, separation of concerns, dead code, 10x-simplicity, OSS-readiness.

## Summary

The commons layer is genuinely good in its core shape. The `ModelFamily` / `ResolvedVariant` engine is a
clean declarative core, the storage stack is well-layered (4 documented layers: `download_helpers` →
`acquisition` → `downloads`/`r2_utils` → `r2`) with a tidy blessed surface in `storage/__init__.py`, the
error taxonomy (`BioLMError`→`UserError`/`ServerError`) is coherent, and the Pydantic v1/v2 and
Python-3.10/3.12 compatibility shims are thoughtful. Serialization correctly enforces a JSON-native contract
across the Modal boundary. The abstractions mostly earn their keep.

The problems are concentrated in **OSS-readiness leakage** and **accumulated scaffolding**, not in core
correctness:

- A `biolm-modal` internal reference leaks in a shipped comment (and the comment is factually wrong).
- Internal-stack references (`training.*`, "the Django host", `training.xgboost.infer.app`) and internal
  Modal environment names (`qa`/`main`) are baked into shipped framework code/comments.
- A dead, **un-importable** file (`parquet_utils.py`, broken `from .utils import …`) ships in the package.
- The T20 print-ban — a W6 Definition-of-Done enforcement mechanism — is silently **not applied** to the
  whole `models/commons/testing/` directory because of an over-broad `**/test*.py` per-file-ignore glob.
- The acquisition engine and decorator carry deprecated/unused fields and `# FIXME`/`[Temporary]`/internal
  "Phase 2"/"W-acq" markers that won't make sense to outside contributors.

None of these are deep architectural faults; they are launch-gating cleanups. Highest priority: remove the
`biolm-modal` leak, delete or fix `parquet_utils.py`, and tighten the print-ban glob.

---

## Findings

### 🔴 must-fix

#### 1. `biolm-modal` internal reference leaks in a shipped comment (and is factually wrong)
- **Category:** OSS readiness / internal leakage
- **Location:** `models/commons/storage/cache.py:48`
- **Detail:** The docstring example reads
  `# e.g. r2://my-bucket/biolm-modal/model-cache/<slug>/<action>/f/2/b/<sha><ext>`. The rubric explicitly
  lists `biolm-modal` as a 🔴 internal-reference leak in shipped files. It is also **wrong**: the code two
  lines below (`build_r2_key_for_item`, lines 49-52) builds the key as
  `f"{r2_model_cache_dir}/{model_slug}/{model_action}/…"` with **no** `biolm-modal` segment. So the comment
  both leaks the internal repo name and misdescribes the actual key layout.
- **Fix:** Replace with the accurate example, dropping the internal segment, e.g.
  `# e.g. model-cache/<slug>/<action>/f/2/b/<sha>.jsonbin`.

### 🟠 should-fix

#### 2. `parquet_utils.py` is dead, un-importable, and uses a non-standard bucket env var
- **Category:** Dead code / correctness / OSS readiness
- **Location:** `models/commons/parquet_utils.py:9` (and whole file)
- **Detail:** Line 9 is `from .utils import (get_r2_client)`. There is **no** `models/commons/utils.py` or
  `models/commons/utils/` package (the R2 client lives in `models/commons/storage/r2.py`), so this module
  raises `ImportError` on import. `grep` confirms nothing in `models/`, `workflows/`, or `cli/` imports
  `parquet_utils` — it is pure dead code that nonetheless ships (git-tracked). It also reads
  `os.getenv("R2_BUCKET_NAME", "workflow-runs")` (line 13), diverging from the repo-wide
  `BIOLM_R2_BUCKET` / `biolm-public` convention in `util/config.py`, and imports `pandas`/`pyarrow` at module
  top (heavy deps) unguarded. It sits at the top level of `commons/` rather than under `storage/`, breaking
  the otherwise-clean layering.
- **Fix:** Delete `models/commons/parquet_utils.py`. If parquet-to-R2 is actually needed by a workflow,
  reintroduce it under `storage/` importing `get_r2_client` from `models.commons.storage.r2` and using
  `BIOLM_R2_BUCKET`.

#### 3. Hardcoded internal Modal environment names (`qa` / `main`) in shipped framework code
- **Category:** OSS readiness / internal leakage / duplication
- **Location:** `models/commons/util/config.py:82-84`, `models/commons/util/environment.py:41-48,121-148`,
  `models/commons/modal/deployment.py:41`
- **Detail:** `qa_environment_name = "qa"` / `prod_environment_name = "main"` and
  `deployed_environment_names = [qa, main]` hardcode BioLM's internal Modal environment naming into the
  framework; the rubric calls out the internal `qa` env explicitly as a leak. `deployment.py:41`
  additionally **re-hardcodes** the literal `("qa", "main")` instead of importing
  `deployed_environment_names`, so the same internal names appear twice. An outside contributor has no `qa`
  or `main` Modal environment, so this production-gating logic is meaningless to them.
- **Fix:** Make the production/deployed environment names configurable (e.g. an env var with a generic
  default), and have `deployment.py` consume `deployed_environment_names` rather than a duplicated literal.
  At minimum, document why these names exist and remove the duplication.

#### 4. Internal-stack references (`training.*`, "Django host") in shipped comments/docstrings
- **Category:** OSS readiness / internal leakage
- **Location:** `models/commons/data/serializer.py:126,169`; `models/commons/testing/config.py:77`
- **Detail:** `serializer.py:169` reads "available on the caller side (e.g. ``training.*`` on the Django
  host)" and `:126` references `training.xgboost.enums.TaskType`; `testing/config.py:77` documents
  `app_module` override values like `"training.xgboost.infer.app"`. These expose the private BioLM stack (an
  internal `training` package and a Django gateway) that has no presence in this OSS repo. (The more generic
  "gateway" mentions in `core/error.py` and `core/caching.py:309` are acceptable architectural language, but
  "Django host" and the `training.*` module paths are concrete internal references.)
- **Fix:** Rewrite these comments to describe the behavior generically (e.g. "any caller whose process lacks
  the producing class's module") and replace the `training.xgboost.*` examples with an in-repo example.

#### 5. Over-broad `**/test*.py` per-file-ignore silently disables the T20 print-ban for all of `commons/testing/`
- **Category:** Tooling / DoD enforcement / consistency
- **Location:** `pyproject.toml:156` (`"**/test*.py" = ["T20"]`); affected runtime-infra files:
  `models/commons/testing/fixture.py`, `runner.py`, `comparator.py`, `multientity_comparator.py`
- **Detail:** Ruff compiles per-file-ignore globs so `*` crosses path separators, so `**/test*.py` matches
  **any file inside a directory whose name starts with `test`**, not just pytest `test_*.py` modules. I
  verified this empirically: `ruff check models/commons/testing/fixture.py --select T201` reports
  "All checks passed!" under the project config but **13 errors** under `--isolated`; a probe file
  `models/commons/testdir_probe/_probe.py` (basename does not start with "test") is likewise exempted. The
  result: `fixture.py`/`runner.py`/`comparator.py`/`multientity_comparator.py` use `print()` heavily and are
  never flagged, even though they are imported library modules under `commons/`, not pytest test files. This
  quietly undercuts the W6 DoD ("zero `print` in runtime code (lint-enforced)"; the intended ignore scope
  per `.planning/03_WORKSTREAMS.md:127` was "scripts/, CLI, tests, vendored external/").
- **Fix:** Tighten the glob to match only pytest modules — e.g. `"**/test_*.py"` and `"**/test.py"` (drop
  the catch-all `test*.py`). Then either convert the now-flagged `commons/testing/*` prints to `get_logger`
  output or add an explicit, intentional `"models/commons/testing/**" = ["T20"]` ignore if print is the
  deliberate choice for test-harness diagnostics.

#### 6. `modal_endpoint` decorator ships suppressed-complexity FIXMEs and a `[Temporary]` SDK hack
- **Category:** Readability / maintainability / internal coupling
- **Location:** `models/commons/core/decorator.py:29,33,68-69,88-89` (3× `# FIXME(noqa: C901)`) and
  `:91-100` (`### ------- [Temporary] Return payload schema logic for Python SDK -------`)
- **Detail:** The central abstraction of the runtime carries three repeated `# FIXME(noqa: C901): Refactor
  to reduce complexity below the linter's threshold` markers and a block flagged `[Temporary]` that exists
  to serve the internal BioLM "Python SDK" via a magic `_return_payload_schema` kwarg. Shipping a public
  framework's most important decorator with "FIXME: too complex" and "[Temporary]" annotations is a bad look
  and a maintenance smell; the SDK coupling references an artifact outside this repo.
- **Fix:** Either complete the promised refactor (the function already delegates to well-named helpers, so
  the wrapper itself can likely drop below the C901 threshold) or remove the FIXMEs and document the
  complexity as intentional. Re-frame the `_return_payload_schema` block as a generic "schema introspection"
  feature rather than an SDK-specific `[Temporary]` hack.

#### 7. Dead/legacy surface in the acquisition engine with internal "Phase 2"/"W-acq" provenance
- **Category:** Dead code / 10x-simplicity / internal leakage
- **Location:** `models/commons/storage/acquisition.py:118-119` (`monitor_directories` unread),
  `:181-182` (`AcquisitionResult.bypass_detected` / `bypass_locations`),
  `models/commons/storage/download_helpers.py:137-212` (`acquire_library_managed_model`, marked deprecated)
- **Detail:** Several config/result fields are explicitly "accepted-but-unread" or set to constant
  `False`/`[]` because "the bypass detector … was removed (W-acq)" and are "retained … until the Phase 2
  per-model migration." `acquire_library_managed_model` is `.. deprecated::` in favor of `r2_then_library`
  but still ships. These comments reference internal workstream IDs (`W-acq`, "Phase 2") meaningless to OSS
  contributors, and the unused fields are scaffolding that doesn't earn its keep.
- **Fix:** Before launch, finish the migration: drop `bypass_detected`/`bypass_locations` and
  `monitor_directories`, remove the deprecated `acquire_library_managed_model` wrapper (update the ~5 callers
  to `r2_then_library`), and strip `W-acq`/"Phase 2" references from any comment that survives.

#### 8. Cache cacheability heuristic hardcodes stale, pre-rename field names (`heavy`/`light`)
- **Category:** Correctness / cross-model consistency
- **Location:** `models/commons/core/caching.py:75` (`INPUT_FIELDS = {"sequence","id","heavy","light","nucleotide_sequence"}`)
- **Detail:** `_result_item_is_cacheable` treats any non-input field as a real output. Its input-field
  allowlist uses `heavy`/`light`/`nucleotide_sequence`, but the ratified schema field names are
  `heavy_chain`/`light_chain` (confirmed in `models/ablang2/schema.py`, `models/igbert/schema.py`) and
  `sequence(s)`. For antibody models, an echoed `heavy_chain`/`light_chain` would be misclassified as output,
  so a null/error item could be wrongly judged "cacheable" and poison the cache. Impact is currently latent
  because response caching is OFF by default (`BIOLM_CACHE_ENABLED` unset), but the allowlist directly
  contradicts the ratified schema standard.
- **Fix:** Update `INPUT_FIELDS` to the canonical names (`sequence`, `sequences`, `heavy_chain`,
  `light_chain`, `nucleotide_sequence`, `id`), or — better — derive the input fields from the request schema
  rather than maintaining a hand-kept list that drifts from the schemas.

### 🟡 nits

#### 9. Inconsistent public-surface curation across submodules
- **Category:** Consistency / API design
- **Location:** `models/commons/storage/__init__.py` vs empty `core/`, `data/`, `util/`, `modal/`,
  `testing/` `__init__.py`
- **Detail:** Only `storage` curates an `__all__` blessed surface; every other submodule has an empty
  `__init__.py`, so models import deep paths (`models.commons.core.error`, `models.commons.model.config`,
  etc.). This is workable but inconsistent — there is no single discoverable `commons` API for new
  contributors.
- **Fix:** Optionally curate `core`/`model` exports the way `storage` does, or document that deep imports are
  the intended convention.

#### 10. Two enum base patterns coexist
- **Category:** Consistency
- **Location:** `models/commons/model/tag.py:13-85` (plain `str, Enum`) vs
  `models/commons/model/schema.py:11-29` (`EnhancedStringEnum`)
- **Detail:** Tag taxonomy enums subclass `str, Enum` while `ModelActions`/`ModalGPU` use
  `EnhancedStringEnum`. The difference (castable-in-strict-models, value-`in` membership) is real, but a
  reader has to know which pattern applies where. Tags are only validated inside config-time `ModelTags`
  (non-strict `BaseModel`), so it works, but the dual pattern is a small inconsistency.
- **Fix:** Either standardize on `EnhancedStringEnum` for all controlled vocabularies, or add a one-line
  comment in `tag.py` explaining why plain `Enum` is sufficient there.

#### 11. Pervasive emoji in runtime log messages
- **Category:** Readability / OSS professionalism
- **Location:** `models/commons/storage/acquisition.py`, `downloads.py`, `r2_utils.py` (and others) —
  `logger.info("🚀 …")`, `"📥 …"`, `"✅ …"`, etc., throughout
- **Detail:** Runtime logging is heavily emoji-decorated. It is consistent and harmless, but for an
  OSS-facing framework, dozens of emoji per module in `logger.*` output is noisy and can render poorly in
  some log aggregators.
- **Fix:** Optional — tone down to plain structured messages, or keep if intentional (low priority).

#### 12. Stale decorator name in docstring
- **Category:** Docs accuracy
- **Location:** `models/commons/core/decorator.py:435`
- **Detail:** `_handle_errors` docstring says "the biolm_modal_function decorator," but the decorator is
  named `modal_endpoint`. Leftover from a prior name.
- **Fix:** s/biolm_modal_function/modal_endpoint/.

#### 13. `deployment.py` shells out to `make clean`
- **Category:** Coupling / robustness
- **Location:** `models/commons/modal/deployment.py:90-98`
- **Detail:** The framework deploy helper runs `subprocess.run(["make", "clean"], …)` before `app.deploy()`,
  coupling a library function to a Makefile target in the process cwd. It is guarded (warns and continues on
  failure), but a framework function invoking `make` is surprising and breaks if invoked outside the repo
  root.
- **Fix:** Move the clean step into the caller/Makefile/CI, or make it opt-in via a parameter rather than an
  implicit side effect of the deploy helper.

---

## Definition-of-Done notes (this dimension)

- **W6 (structured logging; no `print`, lint-enforced):** *Partially met.* Runtime/inference commons modules
  use `get_logger`, but the T20 ban is silently bypassed for all of `models/commons/testing/` via the
  over-broad `**/test*.py` glob (Finding 5). Tighten the glob to restore the guarantee.
- **W7 (error taxonomy):** *Met.* `BioLMError`→`UserError`/`ServerError` with stable dotted `code`s and a
  clean `ERROR_MAP` ordering (specific subclasses before base) in `core/error.py` + `core/decorator.py`.
- **No-internal-leakage (launch gate):** *Not met.* `biolm-modal` comment (Finding 1, 🔴), internal env
  names `qa`/`main` (Finding 3), and `training.*`/"Django host" references (Finding 4) must be scrubbed
  before the repo goes public.
- **Modularity / 10x-simplicity:** *Mostly met* with cleanup owed — dead `parquet_utils.py` (Finding 2),
  deprecated/unused acquisition surface (Finding 7), and decorator FIXMEs (Finding 6).

## Verification

Adversarial re-check of each flagged finding against the actual code (verdict + one-line reasoning).

1. **`biolm-modal` leak in `cache.py:48` comment — REAL.** Line 48 literally reads `# e.g. r2://my-bucket/biolm-modal/model-cache/...`; the key built at `cache.py:49-52` uses `r2_model_cache_dir` which is `"model-cache"` (`util/config.py:11`) with NO `biolm-modal` segment, so the comment both leaks the internal repo name and misdescribes the layout. (Function is actually `build_r2_key_for_item`, a harmless mislabel in the finding.)
2. **`parquet_utils.py` dead/un-importable/non-standard bucket — REAL.** `parquet_utils.py:9` does `from .utils import get_r2_client`, but there is no `models/commons/utils.py` or `utils/` package (only `util/` singular; `get_r2_client` lives in `storage/r2.py:57`) → ImportError on import; grep finds zero importers in `models/`/`workflows/`/`cli/`; `parquet_utils.py:13` uses `R2_BUCKET_NAME`/`"workflow-runs"` vs the repo convention `BIOLM_R2_BUCKET`/`"biolm-public"` (`util/config.py:9`); pandas/pyarrow imported unguarded at top; file is git-tracked and sits at commons top level, not under `storage/`.
3. **Hardcoded `qa`/`main` Modal env names — REAL.** `util/config.py:82-84` hardcodes `qa_environment_name="qa"`/`prod_environment_name="main"`/`deployed_environment_names`; consumed in `util/environment.py:9-10,133,148`; and `modal/deployment.py:41` re-hardcodes the literal `("qa", "main")` instead of importing `deployed_environment_names`, so the names appear twice.
4. **Internal-stack refs (`training.*`, "Django host") — REAL.** `data/serializer.py:126` references `training.xgboost.enums.TaskType` and `:169` reads "``training.*`` on the Django host"; `testing/config.py:77` documents `app_module` value `"training.xgboost.infer.app"`. Concrete private-stack references with no presence in this OSS repo.
5. **Over-broad `**/test*.py` T20 ignore — REAL (empirically verified).** Under project config `ruff check models/commons/testing/fixture.py --select T201` → "All checks passed"; under `--isolated` → 13 errors, proving the per-file-ignore exempts it. A probe `models/commons/testdir_probe/_probe.py` (basename not starting with `test`) was also exempted, confirming `*` crosses path separators so the glob matches any file under a dir starting with `test`. fixture.py/runner.py/comparator.py/multientity_comparator.py all use `print()` and are imported library modules, not pytest tests.
6. **decorator FIXMEs + [Temporary] SDK hack — REAL.** `core/decorator.py:33,69,89` each carry `# FIXME(noqa: C901): Refactor to reduce complexity...`; `:91-100` is the `### [Temporary] Return payload schema logic for Python SDK` block serving the internal SDK via the `_return_payload_schema` kwarg. All ship in the central runtime decorator.
7. **Dead/legacy acquisition surface w/ W-acq/Phase 2 provenance — REAL.** `storage/acquisition.py:115-119` `monitor_directories` is accepted-but-unread, comment cites "removed (W-acq)" and "Phase 2 per-model migration"; `:181-182` `bypass_detected=False`/`bypass_locations=[]` are constant scaffolding; `storage/download_helpers.py:137-152` `acquire_library_managed_model` is `.. deprecated::` in favor of `r2_then_library` (references "Phase 2") yet still ships. Internal workstream IDs are meaningless to OSS contributors.
8. **Cacheability allowlist uses stale `heavy`/`light` — REAL.** `core/caching.py:75` `INPUT_FIELDS = {"sequence","id","heavy","light","nucleotide_sequence"}`, but the ratified schema fields are `heavy_chain`/`light_chain` (`models/ablang2/schema.py:43,54`, `models/igbert/schema.py:63,73`; old `heavy`/`light` only as `validation_alias`). An echoed `heavy_chain`/`light_chain` would be misclassified as output. Impact latent (response caching off by default), but the allowlist contradicts the ratified standard.

**Summary: 8/8 findings REAL.** Every cited fact was reproduced in the current code; none could be refuted.
