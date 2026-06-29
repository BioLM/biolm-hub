# Cross-cutting review — Testing framework

**Dimension:** Testing framework (`models/commons/testing/`, `models/conftest.py`, pytest config in
`pyproject.toml`, and a broad sampling of `models/*/test.py` + `fixture.py`).
**Reviewer:** independent round-1 cross-cutting reviewer.
**Date:** 2026-06-29.

## Summary

The testing framework is, on the whole, a well-thought-out and genuinely uniform abstraction. The
`TestSuite` / `VariantTestMapping` / `ActionTestCase` data model cleanly expresses the
variant × action × input matrix, and `generate_tests_from_suite` (W17) correctly **returns** a
parametrized test function so every `models/<m>/test.py` is a first-class pytest collectible —
verified live: `pytest models/esm2/test.py --collect-only` returns 40 items, Modal-free, with
readable IDs, and there is no leftover `inspect.currentframe` injection. Fixture laziness (the A.10 /
W17 requirement) is consistently honored: every R2 read and network call I sampled
(`esm2/fixture.py`, `progen2/test.py`, `prostt5/test.py`, `prody/fixture.py`) sits **inside** a
function, never at module scope, and the patterns are documented in-code. The shared test-asset library
(W12) exists, is imported by ~10 models, and the `shared/`-prefixed R2 path mechanism is implemented
and unit-tested. All 44 model suites emit both `integration` and `deployment` tests. The print ban
(T20) is genuinely respected in runtime code: a T20 scan of all of `models/` reports **zero** hits.
Pinned ruff 0.6.9 and the framework's own unit tests (`test_comparator.py`, `test_shared_assets.py`,
12 tests) pass clean.

That said, I found one real **correctness bug in the shared comparator** that silently defeats the
`cosine_distance_threshold` tolerance used by ~15 models (it only passes today because golden outputs
are byte-reproduced), and a **dead branch in the runner** that means input fixtures are never validated
against the family schema in the common case — both of which matter precisely in the cross-hardware
OSS scenario the catalog is built for. The remaining findings are smaller: over-permissive default
validators, an over-broad lint-ignore glob, unused markers, and a missing unit-test layer for the
runner's pure helpers.

DoD check: **W17 (pytest-native collection) — MET** (return-and-assign, collect-only works, empty
suites surface as a skip rather than zero items). **W12 (shared assets) — MET** (≥1 asset reused by ≥2
models; naming convention locked in `shared_assets.py` docstring + CONTRIBUTING). Tiers/markers from
`04_TESTING_STRATEGY.md §1` are present but partly unwired (see 🟡 markers finding).

---

## Findings

### 🔴 must-fix

#### 1. `cosine_distance_threshold` is not the effective tolerance — the comparator re-gates it against `rel_tol`
**Category:** correctness · **Location:** `models/commons/testing/comparator.py:177-186` (and the
final gate `compare()` at `:48-50`).

`DictComparator.compare()` returns `self.max_diff <= self.rel_tol`. Every specialized comparator
*zeroes out* `diff` when its own criterion passes — PDB (`:289` `diff = 0.0 if rmsd < threshold`), MSA
(`:309`), generated-seq (`:375`) — so they clear the final `rel_tol` gate. The **cosine** path does
not: when `cos_dist <= cosine_distance_threshold` it sets `diff = cos_dist` (a non-zero value), which
is then re-tested against `rel_tol`. Net effect: the real pass criterion for embeddings is
`cos_dist <= rel_tol`, **not** `cos_dist <= cosine_distance_threshold`. The threshold only switches
`diff` between `cos_dist` and `1e10` — both of which fail the `rel_tol` gate.

Proven empirically (`DictComparator(rel_tol=1e-3, cosine_distance_threshold=0.02)` on vectors with
cosine distance 0.0014 — well inside 0.02 — returns **False** at `rel_tol` up to 1e-3; only passes
once `rel_tol >= 0.0014`). ~15 models set `tolerances={"rel_tol": 1e-4, "cosine_distance_threshold":
0.02}` (esm2, esm1b, esmc, e1, dsm, ablang2, antifold, msa_transformer, prostt5, temberture, zymctrl,
…) believing they grant 2% cosine slack; they actually grant 1e-4. `models/clean/test.py:44` sets
`{"cosine_distance_threshold": 0.02}` with no `rel_tol`, so its effective slack is the 1e-5 default —
~1400× tighter than declared. This is currently **masked** because goldens are byte-reproduced on the
same hardware (cos_dist ≈ 0), but `04_TESTING_STRATEGY.md §2` explicitly says non-deterministic models
must "rely on the suite's tolerances/validators … not exact-match." The moment a contributor
regenerates or runs on a different GPU/library version, these tests fail spuriously despite being well
within the intended tolerance.

**Fix:** in `_compare_vectors`, when within threshold, record a *pass* (`diff = 0.0`) like the other
specialized comparators, so `cosine_distance_threshold` becomes the actual gate:
```python
if cos_dist <= self.cosine_distance_threshold:
    diff = 0.0
else:
    print(...); diff = self._inf_diff
```
Add a regression unit test asserting a within-threshold-but-above-`rel_tol` cosine distance passes.

---

### 🟠 should-fix

#### 2. Runner never validates inputs against the ModelFamily schema — the "default schema" branch is unreachable
**Category:** correctness / dead code · **Location:** `models/commons/testing/runner.py:139-149`.

`_load_and_validate_payload` documents three states (`:135-138`): `request_schema=None` → raw JSON,
`request_schema=Schema` → override, *unset* → ModelFamily default schema. But `ActionTestCase` defines
`request_schema: Optional[...] = None`, so `hasattr(case, "request_schema")` is **always** True and an
unset case is indistinguishable from an explicit `None`. The first `if` (`hasattr and is None`)
therefore swallows every unset case → "Sending raw JSON (no schema validation)", and the `else` branch
(ModelFamily default validation) is **dead** — confirmed by reproduction (`"request_schema" in
case.model_fields_set` is `False` while `case.request_schema is None`). Practically: integration tests
do **not** validate that fixtures conform to each model's request schema, removing a cheap layer that
would catch schema/fixture drift after the W5 field renames.

**Fix:** discriminate intent via `model_fields_set`:
```python
if "request_schema" not in case.model_fields_set:
    request_schema = action_schema.request_schema   # default
elif case.request_schema is None:
    request_schema = None                            # explicit "skip"
else:
    request_schema = case.request_schema             # override
```

#### 3. Default validators accept non-canonical batch keys (`sequences` / `data`) that no model uses
**Category:** consistency / weak abstraction · **Location:** `runner.py:40` (`_validate_log_prob`) and
`runner.py:258-271` (`_default_deployment_validator`).

Both default validators accept `["results", "sequences", "data"]`. All 44 models wrap batch output
under the canonical `results` (grep confirms no model uses top-level `sequences`/`data` as a batch
key — `antifold`'s `sequences` is nested inside a result item). These two legacy keys are dead, and
worse, they make the *one shared enforcement point* for the response contract over-permissive: a model
that wrongly returned `data` instead of `results` would pass the deployment smoke test. This
undermines the repo's stated north star (uniformity; outputs batch under `results`). 19 of 44 model
suites rely on this default deployment validator (no per-case validator).

**Fix:** validate against `results` only (the ratified key); drop `sequences`/`data`, or, if a
genuine exception exists, document it. Same in the `FixtureGenerator` "valid response" check
(`fixture.py:100`).

#### 4. The runner's pure, Modal-free helpers have no unit tests
**Category:** test coverage gap · **Location:** `runner.py:313-364`
(`_variant_matches_mapping_filter`, `_is_case_valid_for_test_type`, `_generate_test_id`,
`_collect_test_params`, `_resolve_app_module_name`).

These functions drive *every* model's test collection (matrix expansion, IDs, validity filtering) and
are pure string/dict logic that runs without Modal or R2 — exactly the kind of thing T1 should cover.
Only `comparator.py` and `shared_assets.py`/`_fixture_r2_path` have unit tests. Given the framework
generates the entire suite, a silent regression here (e.g. an ID collision or a mapping-filter change)
would be invisible until a Modal milestone. The empty-suite skip (`_create_empty_suite_test`) is a nice
safety net but is itself untested.

**Fix:** add `models/commons/testing/test_runner.py` covering matrix expansion across a multi-variant
fake `TestSuite`, test-id generation (single vs multi-variant, templated vs programmatic input),
`_is_case_valid_for_test_type` per tier, and the empty-suite → skip path.

---

### 🟡 nits

#### 5. Over-broad T20 ignore glob exempts the whole `testing/` directory
**Location:** `pyproject.toml:156` (`"**/test*.py" = ["T20"]`).

ruff's glob `*` matches `/`, so `**/test*.py` matches *every* file under any `test*`-named directory —
including `models/commons/testing/runner.py`, `fixture.py`, `comparator.py`,
`multientity_comparator.py` (none of which are named `test*.py`). Confirmed: those four files contain
13/13/19/8 `print()` calls yet T20 reports "All checks passed". This is benign today (they are test
infra, and pytest captures stdout), but it is *accidental* and fragile: any genuinely-runtime module
placed under a `test*`-named dir silently loses the print ban that W6 added. **Fix:** tighten to
`"**/test_*.py"` + `"**/test.py"` and add `"models/commons/testing/**" = ["T20"]` explicitly so the
intent is visible. (Note: these files also use `print` rather than `get_logger`; acceptable for a
pytest `-s` runner, but worth a one-line acknowledgment given the structured-logging house rule.)

#### 6. Three registered markers are applied to zero tests
**Location:** `pyproject.toml:107-114`, `models/conftest.py:10-17`.

`e2e`, `live_modal`, `no_parallel` are registered but never applied to any test (grep: 0 usages).
`e2e`/`live_modal` at least appear in the canonical T1 deselect command
(`04_TESTING_STRATEGY.md §1`), so `not e2e and not live_modal` is a forward-looking no-op;
`no_parallel` appears nowhere. They imply coverage that doesn't exist. **Fix:** wire them up or trim to
the three that are real (`integration`, `deployment`, `slow`).

#### 7. Marker registry is duplicated and hand-synced
**Location:** `pyproject.toml:107-114` vs `models/conftest.py:10-17`.

The marker list/descriptions are maintained in two places (the conftest docstring explains why — to
support single-file runs without the root config). They currently match, but nothing enforces that.
**Fix:** acceptable as-is, but consider deriving one from the other (or a shared constant) to prevent
drift.

#### 8. `_is_case_valid_for_test_type` is typed `-> bool` but returns a non-bool
**Location:** `runner.py:322-330`. Returns `case.expected_output_fixture or case.validator` — a
`str` / `Callable` / `None`. Works via truthiness but violates the annotation. **Fix:** wrap in
`bool(...)`.

#### 9. Dead/commented debug code in the comparator
**Location:** `comparator.py:175`, `:255-256` (commented-out `print` debug lines). Minor cleanup;
remove or convert to a `verbose` flag like `MultiEntitymmCIFComparator` already has.

#### 10. Forward-compat: the `UP007` ignore won't cover `Optional[...]` once ruff is bumped past 0.7
**Location:** `pyproject.toml:146-149`. Under the pinned ruff 0.6.9 everything is clean, but in ruff
≥0.7 the `Optional[X] → X | None` rewrite split out of `UP007` into **UP045** (not ignored). On a ruff
upgrade, `ruff --fix` will rewrite every `Optional[...]` in the testing modules (and elsewhere),
contradicting the stated "keep Optional/Union spelling stable" intent. **Fix:** add `"UP045"` to
`ignore` when upgrading ruff. (Low confidence / version-dependent — flagged only because the comment
states an intent the future toolchain will silently break.)

---

## What's good (no action needed)
- W17 collection: return-and-assign, `--collect-only` works Modal-free, empty suite → observable skip.
- Fixture laziness is consistently correct across the sampled models (R2/network inside functions).
- Shared-asset library (W12) is real, used, and unit-tested; the `shared/` R2 path resolver is clean.
- `dummy/test.py` is a good canonical template and even documents the shared-asset usage in a comment.
- Retry logic in `execute_integration_test_case` is reasonable for Modal infra flakiness.
- All 44 model suites uniformly emit `integration` + `deployment` tests via the same generator.

---

## Verification

Adversarial re-check of the four high-severity findings (tried to refute each; all confirmed against
the actual code).

- **cosine_distance_threshold re-gated against rel_tol** — **REAL**. `comparator.py:178` sets
  `diff = cos_dist` (non-zero) on pass, unlike every other path which zeroes diff (PDB :289, MSA :309,
  gen-seq :375, pdb_seq :257, multientity :222); the final gate `max_diff <= rel_tol` at :50 then
  re-gates it. Reproduced: cos_dist=0.0007 → `rel_tol=1e-4,cos_thresh=0.02` returns False,
  `rel_tol=0.02` returns True. Effective slack = min(rel_tol, cos_thresh) = rel_tol. Currently masked
  by byte-reproduced goldens (cos_dist≈0) but the declared 2%/default-1e-5 slack is illusory.
- **Default-schema validation branch unreachable** — **REAL**. `config.py:44` declares
  `request_schema: Optional[type[BaseModel]] = None`, so for an unset case `hasattr(...)` is True and
  `request_schema is None` is True → first `if` at `runner.py:139` always wins; the `else`
  (ModelFamily default validation, :144-149) is dead. Reproduced: unset case has
  `'request_schema' in model_fields_set == False` yet `case.request_schema is None`, so the hasattr/None
  test cannot distinguish "unset" from "explicit None".
- **Default validators accept non-canonical batch keys** — **REAL**. `runner.py:40`, `runner.py:258`,
  `fixture.py:100` all accept `["results","sequences","data"]`. Action methods return top-level
  `results` only: biotite `generate` → `BiotiteExtractChainsResponse(results=...)` (the `{"sequences":..}`
  at app.py:210 is an internal helper consumed at :106, not a response key); antifold's `sequences` is
  nested in a result item under `results_list` (app.py:326,45). `sequences`/`data` are dead top-level
  keys, so the shared response-contract check is over-permissive.
- **Pure Modal-free runner helpers have no unit tests** — **REAL**. Only `test_comparator.py` and
  `test_shared_assets.py` exist under `models/commons/testing/`; no test file references
  `_variant_matches_mapping_filter`/`_is_case_valid_for_test_type`/`_generate_test_id`/
  `_collect_test_params`/`_resolve_app_module_name` (runner.py:313-364). They are exercised only
  indirectly at suite import-time, not by dedicated T1 unit tests.
