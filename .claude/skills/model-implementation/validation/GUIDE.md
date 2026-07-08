# Phase 3: Validation

## Purpose
Verify the implementation is correct before documentation and PR. Follow steps in the exact order below — skipping or reordering causes hard-to-debug failures.

---

## 3.1 `make check` — MANDATORY

`make check` runs style (`ruff` + `black` + hygiene hooks), mypy, the schema-doc check, the CI-script
tests, and the unit tests — the same checks as CI's main `checks` job.

```bash
make check
```

Fix every failure before proceeding. Never push with `make check` red.

> **Expected `make check` failure right after adding a model: a stale catalog.** `test-unit` includes
> `tooling/test_model_catalog.py::test_readme_catalog_is_fresh`, which fails because the committed
> catalog table in `models/README.md` doesn't yet list your new model (e.g. "36 models" → "37 models").
> This is a normal step, not a bug in your model — regenerate the catalog (see §3.1b) and re-run.

> **A red `make check` may be pre-existing and unrelated to your model.** Some unit tests exercise the
> whole catalog (the gateway catalog/discovery tests load *every* model family), so a failure can
> originate in another model or a stale baseline, not yours — and your own
> `python -m pytest models/<name>/test.py` won't surface it. Before assuming your model broke CI, diff
> against a clean baseline: stash or remove `models/<name>/` (or compare to `origin/main`) and re-run
> `make check` — if the same failure persists with your model absent, it's pre-existing. Fix your
> model's own failures; flag a pre-existing one separately rather than treating it as a blocker you
> introduced.

If you want to run the sub-checks individually:

```bash
make style              # ruff + black + hygiene hooks
make mypy               # static type checking (enforced)
make check-schema-docs  # every Field has a rendered description; shared fields match the glossary
make test-github-scripts  # unit tests for the CI change-detection scripts
make test-unit          # fast unit tests (no Modal, no R2)
```

> **Schema-doc gate.** `make check-schema-docs` runs **`tooling/check_schema_docs.py`** (CI-wired via
> `tooling/test_schema_docs.py`). It fails on any field lacking a *rendered* `Field(description=...)`,
> or a shared field whose wording drifts from **`tooling/field_glossary.yaml`** — so pre-check
> shared-field wording against the glossary before running it. The most common "no rendered
> description" cause is a `Field(description=...)` nested inside `Optional[Annotated[...]]`; move the
> `Field` to field level (see `implementation/GUIDE.md §2.1`).

---

## 3.1a `make docs` — the generated page must build

`make check` does **not** build the docs. CI runs a **separate `docs` job** (`mkdocs build
--strict`). Your model's page is *generated* from its `config.py` + knowledge-graph files by
`docs/gen_pages.py`, so a broken schema description, malformed YAML, or a bad cross-link can fail the
docs build even when `make check` is green.

```bash
make docs   # mkdocs build --strict — must be clean before you push
```

---

## 3.1b Regenerate the model catalog — `models/README.md`

Adding (or renaming/removing) a model makes the committed catalog table in `models/README.md` stale,
which fails the unit test `tooling/test_model_catalog.py::test_readme_catalog_is_fresh` — so `make
check` (via `test-unit`) stays **red** until you regenerate it:

```bash
python -m tooling.gen_model_catalog   # rewrites the generated table in models/README.md (idempotent)
```

Commit the regenerated `models/README.md`. Like `docs/gen_pages.py`, the generator is Modal-free (it
only imports model configs), so it needs no credentials; `python -m tooling.gen_model_catalog --check`
fails without writing if the catalog is stale.

---

## 3.2 Generate Fixtures — Before Running Integration Tests

For a deterministic model — the required validation path (`implementation/GUIDE.md §2.5`) — generate
its golden input + output first; only a genuinely non-deterministic model using a custom `validator=`
skips this. **Writing goldens requires R2 write credentials** — fixture *reads* work credential-less
over the public bucket URL, but *writes* go through the signed S3 API. Point the tooling at a bucket
you control and export credentials first:

```bash
export BIOLM_R2_BUCKET=<your-bucket>       # defaults to the read-only public bucket otherwise
export AWS_ACCESS_KEY_ID=<key>
export AWS_SECRET_ACCESS_KEY=<secret>
export R2_ENDPOINT=<your-r2-s3-endpoint>
python models/<name>/fixture.py
```

This runs the model against predefined inputs and writes both the inputs and the outputs to R2
(under `test-data/models/<slug>/`) as reference ("golden") values. The public `biolm-public` goldens
are a maintainer-populated artifact; a contributor generates their own into their own bucket. Without
this step, integration tests fail with "file not found" errors. If you haven't written `fixture.py`
yet, see **Phase 2 → `fixture.py`** in `implementation/GUIDE.md` and copy the template at
`models/dummy/fixture.py`.

**The golden output is the oracle.** Only regenerate when an output change is intentional, and say so in the PR.

---

## 3.3 Integration Tests — Optional Locally, Mandatory in CI

Integration tests require a Modal account and R2 access. Running the full local integration *suite* (coverage ≥85%) is OPTIONAL for local development — CI runs it automatically once a maintainer applies the `deploy-approved` label. This is separate from the §3.5 dev deploy + one live inference call, which **is** required before the PR if you have Modal credentials.

If you have a Modal account, run locally with:

```bash
# Single model
python -m pytest models/<name>/test.py -m integration -n auto --no-cov -v -s

# Both integration and deployment tests
python -m pytest models/<name>/test.py -n auto --no-cov -v -s
```

Requirements:
- All tests pass
- Coverage ≥85% on testable code
- Both integration and deployment test types configured in `test.py`

If coverage is below 85%, add test cases for:
- All actions
- Edge cases (empty input, max-length sequences, invalid characters)
- Error paths (bad input, OOM)

Check coverage with:
```bash
pytest models/<name>/test.py --cov=models/<name> --cov-report=term -m integration
```

---

## 3.4 Local Image Build — Recommended (a fast pre-check before the §3.5 dev deploy)

Building the image locally catches dependency and path errors before CI:

```bash
python models/<name>/app.py
```

This builds the Modal container locally, loads the model, and validates basic inference. Much faster to debug here than in a CI failure.

---

## 3.5 Deploy to Dev Environment — Required (credential-less carve-out below)

If you have a Modal account, a dev deploy plus **at least one live inference smoke call** is
**REQUIRED** before the PR — build errors and load/inference failures that never surface in the
Modal-free checks show up only here:

```bash
MODAL_ENVIRONMENT=biolm-hub-dev bh deploy <name> --force
# then call the live endpoint at least once with a real payload and confirm a sane response
```

**Credential-less carve-out.** The repo supports contributors with no Modal account (deploys run
under `BIOLM_SKIP_MODAL_SECRETS=1`, reading public weights anonymously). If you have a Modal account,
a dev deploy + one live call is REQUIRED before the PR. Credential-less contributors must **state in
the PR that deploy is unverified**; a maintainer then completes it via the `deploy-approved` CI gate.

Either way, the full deploy + integration + deployment test matrix re-runs in CI once a maintainer
approves and applies the `deploy-approved` label — CI deploys to `biolm-hub-dev` and runs the full
test suite against the reviewed commit.

> **Note:** The `deploy-approved` label pins the run to the commit it was added on. Pushing new
> commits does **not** re-trigger a deploy (there is no `synchronize` trigger) and does **not**
> auto-remove the label; to deploy your latest push a maintainer must **manually remove and re-add** it
> (after re-review). Ping a maintainer after your last push.

---

## Validation Checklist

- [ ] `make check` passes (style + mypy + schema-doc check + CI-script tests + unit tests)
- [ ] `make docs` passes (mkdocs --strict — the generated model page builds)
- [ ] `models/README.md` catalog regenerated (`python -m tooling.gen_model_catalog`) and committed
- [ ] All dependencies pinned to exact versions
- [ ] Seeds set (torch, numpy, random, CUDA) — deterministic outputs (**stochastic/torch models only**; deterministic CPU/algorithmic tools need none)
- [ ] `UserError` used for bad-input paths
- [ ] Golden input + output generated (`python models/<name>/fixture.py`) and loaded by an integration test — required for deterministic models; custom-validator-only permitted solely for non-deterministic models, with justification
- [ ] Coverage ≥85%
- [ ] Both integration and deployment test types configured
- [ ] With Modal credentials: `biolm-hub-dev` deploy + at least one live inference call succeeded (credential-less contributors: PR states deploy unverified — see §3.5)
- [ ] No modifications to `models/commons/`

---

## Common Issues

**Tests fail with "file not found"**
You forgot to generate fixtures. Run `python models/<name>/fixture.py` first.

**`Module not found`**
Ensure `models/<name>/__init__.py` exists.

**Coverage below 85%**
Add test cases for edge cases and error paths. Test every action.

**Non-deterministic outputs**
Set all seeds in `move_to_gpu` (or your `@modal.enter(snap=False)` method): `torch`, `numpy`, `random`, and `torch.cuda`.

**GPU OOM**
Reduce batch size, or upgrade the resource spec in `config.py`.

**Image build fails locally**
Check `app.py` image build — wrong dependency version or missing system package.

**Strict mypy `[no-untyped-call]` from a new dependency**
If your model adds a dependency that is *installed in the repo venv* (a real project dep — e.g.
`biopython`), strict mypy follows it and flags every call into its untyped API as
`[no-untyped-call]`. See `resources/common_issues.md` for the fix (annotate the object `Any`, or
`# type: ignore[no-untyped-call]` with a reason). Deps that live **only** in the Modal image (not
installed locally, e.g. `dnachisel`/`primer3`) don't trip this — `ignore_missing_imports` makes them
`Any`.

## Gate

Before Phase 4:
- `make check` green; `make docs` green; unit tests pass; coverage ≥85%.
- Golden input + golden output recorded in R2 and loaded by an integration test (custom-validator-only permitted solely for non-deterministic models, with justification).
- With Modal credentials, a `biolm-hub-dev` deploy plus at least one live inference call succeeded (credential-less contributors state in the PR that deploy is unverified — see §3.5).
