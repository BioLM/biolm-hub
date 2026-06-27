# Investigation Findings — Internal `biolm-modal` (evidence base)

**Investigated:** 2026-06-21 · **Reference source:** `/Users/qamar/dev/biolm-modal` @ `main`
(read `main` via the detached read-only worktree `/Users/qamar/dev/biolm-modal-worktrees/oss-readonly-main`)

This is the consolidated technical evidence behind the master plan. Future agents should read
this instead of re-investigating. Every claim cites a path in the internal repo.

> **2026-06-24 deep-dive addendum.** A 10-agent read-only investigation refined several sections
> below (Dockerfile verdict §3, actions §4, gateway discovery §6, caching §7, testing §9) and added
> §11 (commons internals to simplify). Verdicts are inline; per-model licensing landed in
> `02_MODEL_INCLUSION_MATRIX.md`.

---

## 1. Repo map (top level)

- `models/` — 60 model dirs (on `main`) + `commons/` (framework) + `scripts/`.
- `gateway/` — FastAPI unified access point (+ `catalog/` web UI).
- `cli/` — `bm` Typer CLI (`main.py`, `deploy.py`, `r2.py`, `kb` subcommands).
- `workflows/`, `finetune/` (named `training/` on older branches) — **out of scope** (internal pipelines).
- `.github/workflows/` — `pr-checks.yml`, `main-deployment.yml`, `claude.yml`,
  `claude-code-review.yml`, `model-implementation.yml`.
- `.claude/skills/` — `model-implementation`, `model-knowledge-base`, `code-quality`,
  `pr-management`.
- Untracked planning artifacts: `ref/` (separate platform vision), `AUTO_MODEL_*.md`,
  `_AUTOMATED_MODEL_IMPLEMENTATION_SYSTEM.md`, `_SKILL_COORDINATION_README_STANDARDS.md`,
  `_other_prs/_JARNICKAE_FEEDBACK.md`.

---

## 2. Models & the knowledge graph

**60 model dirs** (on `main`; the 2026-06-21 investigation saw 58 — `pro1` + `proteina_complexa` were
added since), near-identical layout. Standard files: `app.py`, `config.py`, `schema.py`,
`test.py`, `fixture.py`, optional `download.py`, plus the **5 knowledge-graph files**:

| File | Role |
|---|---|
| `sources.yaml` | Machine-readable: `license` (type + url + notes), molecule types, tasks, primary papers (arXiv/DOI + R2 PDF/MD paths), source repos (GitHub + HF w/ commit hashes + R2 snapshots), applied literature |
| `comparison.yaml` | Machine-readable: strengths, weaknesses, `use_when`, `dont_use_when`, `alternatives` (model + when_better/when_worse) |
| `README.md` | API reference: actions, request/response schemas, usage |
| `MODEL.md` | Architecture, training data, loss, benchmarks, perf profile, caching, versioning |
| `BIOLOGY.md` | Molecule types, biological problems, applied use-cases w/ citations, glossary |

**License lives in `sources.yaml` → `license.type`** → the include/exclude filter is scriptable.
Models lacking `download.py` load weights at runtime / have no weights: `af2_nim`, `biotite`,
`camsol`, `dna_chisel`, `gemme`, `msa_search_nim`, `peptides`, `prody`, `sadie`. `dummy` is the
template (no fixture).

Full per-model license/decision table: `02_MODEL_INCLUSION_MATRIX.md`.

---

## 3. Modal image pattern & Dockerfile-extraction feasibility

Every `app.py` builds its image at module scope:
```
image = <base image: debian_slim | from_registry(pytorch...) | micromamba | from_aws_ecr(NIM)>
image = setup_download_layer(image, ...)          # OPTIONAL: runs a Python download fn IN the build
image = <.apt_install / .uv_pip_install / .pip_install / .run_commands chain>
image = setup_source_layer(MODEL_FAMILY.base_model_slug)(image)   # copies model source into image
```

`common_requirements` (base 7 pkgs): `biopython==1.84`, `boto3==1.35.78`, `cbor2==5.6.5`,
`modal==1.3.5`, `orjson==3.10.12`, `pydantic==2.11.7`, `redis>=5.1.1,<=6.2.0`.

**The two "hard blockers" — 2026-06-24 verdict:**
- `setup_download_layer` (`models/commons/modal/downloader.py`) uses `image.run_function(...)` to
  run Python in the build, fetching weights from R2/HF via Modal secrets (no GPU/Volume needed).
  **CONDITIONAL YES** → maps to `RUN python download.py` with **Docker BuildKit build-secrets**
  (`--mount=type=secret`) for R2/HF creds. Models with a public HF/URL fallback are self-serve;
  `R2_ONLY` models have no public upstream so external users can't fetch them.
- `setup_source_layer` copies the model's Python source as a final layer. **TRIVIAL YES** → a plain
  Dockerfile `COPY`.

**Difficulty buckets** (the remaining pip/run_commands chains):
- **Easy** (pure pip on standard base): `peptides`, `biotite`, `dna_chisel`, `prody`, `esm2`,
  `esm1b`, `esm1v`, `esm_if1`, `esmfold`, `msa_transformer`, `dnabert2`, `omni_dna`, `boltz`,
  `esmstabp`, `temberture`, `tempro`, `spurs`, `sadie`, `biolmtox2`(excl), `nt`(excl), `esm3`(excl), `esmc`(ship — 300M).
- **Medium** (`run_commands` w/ git clone, patches, binary downloads): `antifold`, `rf3`, `rfd3`,
  `boltzgen`, `dsm`, `progen2`, `mpnn`, `diamond`(excl), `gemme`(excl), `poet`(excl).
- **Hard** (micromamba/conda solver, GPU-at-build, `run_function` prebuild hooks, NIM): `abodybuilder3`,
  `immunebuilder`, `immunefold`, `propermab`, `deepviscosity`, `thermompnn`, `thermompnn_d` (conda);
  `evo2`, `chai1` (GPU required during build); `af2_nim`, `msa_search_nim` (closed NIM — **cannot be
  Dockerfiled at all**, also excluded for license).

→ **Verdict:** Dockerfile split is feasible for the Easy/Medium majority (~60–70%), impossible for
the GPU-at-build tail (`gpu=` on pip/run_commands for flash-attn/CUDA — no standard `docker build`
equivalent) and for NIM (private ECR). So it's an **optional final in-scope stage** (master plan
Stage 6 / W15), shipped per-model by eligibility (no GPU-build; public weights; standard base
image), with a go/defer decision made late and the ineligible tail recorded in `FUTURE_WORK.md`.

---

## 4. Model actions

Canonical enum (`models/commons/model/schema.py` → `ModelActions`):
`PREDICT, ENCODE, GENERATE, PREDICT_LOG_PROB, SCORE, EXTRACT_FEATURES`.

Declared per model in `config.py` via `ModelFamily.action_schemas` (list of `ActionSchemaMap(name,
request_schema, response_schema)`), enforced at runtime by `@modal_endpoint(app_name=...)` +
`@modal.method()` on each action method in `app.py`.

`ActionSchemaMap.name` is a plain `str`, so non-canonical names exist: `af2_nim` →
`predict_from_msa`/`predict_multimer`, `msa_search_nim` → `encode_paired` (both excluded for
license, so the drift mostly disappears after filtering). **`fold` is the notable missing verb** —
fold models (`boltz`, `chai1`, `esmfold`, `abodybuilder3`, `rf3`, `immunefold`, `immunebuilder`)
currently expose `predict`. Action frequency across 58: `encode`~30, `predict`~27,
`predict_log_prob`~17, `generate`~15, `score`~4, `extract_features`~1 (`propermab`).

**2026-06-24 verdict + decisions.** The enum is **not enforced at runtime** — actions dispatch as
plain strings via `getattr(instance, action)` (`gateway/app.py:522`); `ActionSchemaMap.name` is typed
`str` (`config.py:32`); the enum's only runtime consumers are `non_cacheable_actions={GENERATE}`
(`caching.py:24`) + one test. So changing it is cheap (per model: rename the `app.py` method +
`ActionSchemaMap.name` + public `/{action}` slug + fixtures). **Canonical OSS action set:**
`predict, fold, encode, generate, score, log_prob`.
- **Add `FOLD`** — 7 models migrate `predict`→`fold`: `esmfold, boltz, chai1, abodybuilder3, rf3,
  immunefold, immunebuilder`. (`prody`/`spurs`/`biotite` take structure as *input* → stay `predict`.)
- **Rename `predict_log_prob`→`log_prob`** (the `predict_` prefix wrongly implies a flavor of
  predict; ~13 models). Kept **distinct from `score`**: `log_prob` is a uniform per-sequence
  pseudo-log-likelihood scalar; `score` is a model-defined umbrella scalar (after NC exclusions:
  ~dsm + antifold). Normalize antifold's freeform `"score"` string to the enum member.
- **Drop `extract_features`** — only `propermab` used it; it returns 34 engineered biophysical
  descriptors (not NN embeddings → not `encode`) → re-home to `predict`.
- **Keep `generate` unified** (don't split into `design`): the sequence/structure boundary is blurry
  (mpnn/rfd3/boltzgen emit both; inverse-folding is structure→sequence). Differentiate via schema.
- **`biotite` freeform misuse** (worst agent-legibility offender in the SHIP set): its `generate`
  extracts chains and its `predict` computes RMSD — structural *utilities* mislabeled; fix per-model
  in Stage 3. After NIM filtering, no other freeform action names survive.

---

## 5. CLI (`cli/`)

Typer app (`cli/main.py`): `bm r2` (ls/cp/cat/du/rm/download-outputs), `bm kb`
(status/validate/sources/matrix/missing), `bm deploy`, `bm help`.
- `bm deploy` (`cli/deploy.py`): loads `models/<m>/config.py:MODEL_FAMILY`, resolves variants
  (`--variant KEY=value`, default = all), then `subprocess.run([python, models/<m>/app.py,
  --force-deploy?], env=variant_env_vars)`.
- **Gap:** no check that Modal is configured (`MODAL_TOKEN_ID`/`MODAL_TOKEN_SECRET` / `modal token
  new`). `models/commons/util/environment.py:get_environment_name()` reads the Modal env but does
  not validate setup. **Open-source needs a `bm setup`/pre-flight check with guidance.**
- No `bm serve` (catalog web app launcher) and no `bm cache` controls yet.

---

## 6. Gateway (`gateway/`)

`gateway/app.py` (~620 lines): FastAPI behind `@modal.asgi_app()`; dynamically generates
`POST /api/v3/{model_slug}/{action}` endpoints for every variant×action; routes via
`generic_request_handler` → `compute_remotely` which does
`modal.Cls.from_name(slug, class_name)` then `getattr(instance, action).remote.aio(payload=...,
_skip_validation=True, _skip_cache=True)`.

- **`ModelMapper`** (`gateway/model_discovery.py`): scans `models/*/config.py` for `MODEL_FAMILY`,
  builds variant map + action registry. **Class names are currently discovered by AST-parsing each
  `app.py` for the `@biolm_model_class` decorator (`model_discovery.py:106-147`) — fragile and
  redundant** (the test runner already finds the class by import marker, `runner.py:90-92`; the AST
  matcher only handles a bare decorator name, so a rename/alias silently drops the model to a 404).
  **OSS fix (W8):** drop the AST scan and add an explicit `modal_class_name: str` to `ModelFamily`
  (the config the gateway already imports — it *can't* import `app.py` due to heavy top-level deps),
  with a CI guard asserting it resolves to a `@biolm_model_class`-marked class. Trivial (~10 lines
  removed, one field per model). Keeps routing 100% config-driven.
- **Caching** is already modular and gateway-independent (see §7), so producing a bare
  `gateway.py` (~20 lines, no cache) + `gateway_with_cache.py` is **Easy/Moderate**.
- **Internal coupling to strip:** Moesif analytics (`gateway/analytics.py`), Django-auth + billing
  middleware, hardcoded secret names + domains in `gateway/config.py`
  (`django_modal_secret_name = "django-modal"`; domain map `dev-aq.biolm.ai`/`modbackend-qa…`/
  `modbackend-prod…`). Parameterize: domain optional (default Modal-assigned URL); auth optional
  (default none).
- **Web catalog already exists:** `gateway/catalog/` — `generator.py` introspects each route's
  Pydantic schema; `templates/catalog.html` + `model.html`; `static/script.js` builds dynamic
  request forms (special handling for sequence/pdb/smiles fields, enums, nested models). **Missing:
  deployed/undeployed (greyed-out) state** — infra supports adding it. Currently coupled to live
  Modal discovery (no offline/static mode).

---

## 7. R2 storage & caching

**Config (`models/commons/util/config.py`) — hardcoded:**
```
r2_bucket_name = "biolm-modal"      # ← parameterize: default "biolm-public" + BIOLM_R2_BUCKET override
r2_model_store_dir = "model-store"  # logical prefix, fine as-is
r2_model_cache_dir = "model-cache"  # logical prefix, fine as-is
r2_test_data_dir   = "test-data"    # logical prefix, fine as-is
```
**Client (`models/commons/storage/r2.py`):** boto3 S3 client from env (`AWS_ACCESS_KEY_ID`,
`AWS_SECRET_ACCESS_KEY`, `AWS_REGION`, `R2_ENDPOINT`); in containers these env vars are injected by
the Modal secret `cloudflare-r2`.

**Weight acquisition** (`models/commons/storage/acquisition.py`, `download_helpers.py`): strategies
`R2_ONLY`, `HUGGINGFACE_HUB`, `LIBRARY_MANAGED`, `DIRECT_URLS` (+ a dead `CUSTOM`) — check R2 first,
fall back to source, re-cache to R2. **This subsystem is ~4025 LOC and bloated** (~600 LOC of dead
code: a `TargetedBypassDetector` that only prints, the unused `CUSTOM` strategy, duplicate
validation, legacy re-export aliases). Flagged for a standalone simplification workstream — **W-acq**
(see §11 and `03_WORKSTREAMS.md`).

**1:1 R2↔filesystem mapping** (`downloads.py:get_model_dir_util`, `r2_utils.py:
get_r2_prefix_from_target_dir`): local `/model-store/<slug>/<version>/<variant>/file` ↔ R2 key
`model-store/<slug>/<version>/<variant>/file`. Atomic upload/restore via `.r2_manifest.json`
(sha256 per file) + `.r2_cache_complete` marker (`r2_utils.py`).

**Two-tier response cache:**
- Tier 1: `modal.Dict` per model (`models/commons/core/caching.py:get_model_cache`,
  `"model-cache-{slug}"`), ephemeral.
- Tier 2: R2 gzip (`models/commons/storage/cache.py`), key
  `model-cache/<slug>/<action>/<a>/<b>/<c>/<sha256>.jsonbin` (gzip if ≥2KB). Per-item SHA256 key
  over `slug:action` + sorted-key item JSON + params. `non_cacheable_actions = {GENERATE}`.

**2026-06-24 caching verdict.** Caching is cleanly decoupled from auth/analytics. There is **no
global on/off flag today** — `_skip_cache`/`_skip_validation` default `False` (`decorator.py:174-175`),
cache invoked at `decorator.py:332`. The gateway **batch partial-cache-hit merge-by-index is sound,
not spaghetti**; the real smells are (a) the partial-payload closure is **duplicated** across
`gateway/app.py` + `decorator.py`, and (b) a **billing-coupled `computed_count`** leaks into the
return. **OSS decision (user-ratified):** ship **both** tiers (modal.Dict + R2) **off by default**
behind one opt-in flag (e.g. `BIOLM_CACHE_ENABLED`) + user-supplied bucket/dir; remove
`computed_count`; de-dup the closure. (See W8.)

---

## 8. CI/CD (`.github/workflows/`)

- **`pr-checks.yml`** triggers on **every PR** (`pull_request: paths: ['**']`). Stages: branch
  up-to-date + `make style`; unit tests (markers excluded: integration/deployment/slow/e2e/pubsub/
  live_modal); **model detection** (`.github/scripts/detect_models.py` — commons change ⇒ all
  models; `--smart` uses `analyze_commons_dependencies.py` to narrow); **QA deploy + integration
  tests** (matrix over changed models: `uv run bm deploy <m> --force`, then `@pytest.mark.integration`);
  **deployment tests** (`@pytest.mark.deployment`) against live endpoints; PR summary.
- **`main-deployment.yml`**: push to `main` → production deploy per changed model (no approval gate).
- **`claude.yml`**: comment-triggered (`@claude` on issue/PR) Claude Code agent with a restricted
  toolset (make/uv/python/git/gh/`bm r2 ls|cat|cp`/pre-commit; no arbitrary bash, no modal deploy,
  no R2 delete) — **this is the pattern to adapt for a maintainer approval gate.**
- **`model-implementation.yml`**: stub for the separate auto-implementation effort.

**OSS change needed:** gate the model-deploying jobs behind maintainer approval — `pull_request_target`
+ label (`approved`/`/deploy` comment) so untrusted PRs don't trigger Modal. Keep unit tests on every
PR (no external resources, safe).

---

## 9. Testing infra (`models/commons/testing/`)

`TestSuite(model_family, variant_test_mappings)` → `VariantTestMapping(variant_config, test_cases)`
→ `ActionTestCase(action_name, input_fixture, expected_output_fixture, tolerances, validator, ...)`.
`generate_tests_from_suite(suite, test_type="integration"|"deployment")` emits pytest tests.
`runner.py:execute_integration_test_case` loads input + golden output from R2, runs `.remote()` with
retry (2 attempts; retryable: image-build/timeout/empty), compares with tolerances/validator.
`fixture.py:FixtureGenerator` writes programmatic inputs + golden outputs to
`test-data/models/<slug>/`.

**Shared test assets:** today, assets are per-model (`test-data/models/<slug>/`); minimal reuse
(e.g., `soluprot` duplicates a test sequence). **OSS opportunity:** a shared library at
`test-data/shared/` (standard protein/DNA sequences, benchmark sets) — the path-templating already
supports referencing shared assets.

**Collection gap (→ W17, 2026-06-24).** `generate_tests_from_suite` injects `test_*` functions into
the caller's module globals via `inspect.currentframe().f_back` (`runner.py:369-382`). The names DO
match `test_*` and run at import, so pytest *can* collect them — but in practice collection silently
yields **zero** tests when `_collect_test_params` is empty (Modal/R2 config absent → an empty
`parametrize`, no warning). Each `models/<m>/test.py` carries explicit run-commands at the bottom and
no `__main__` guard, so the de-facto workflow is "run the file explicitly." **Fix:** make the
function *return* the parametrized test; each `test.py` assigns it explicitly
(`test_{slug}_{type} = generate_tests_from_suite(...)`); drop `inspect`; add an empty-params
skip/warn; add `models/conftest.py` for marker registration; CI `pytest --collect-only models/` fails
on zero items. Mechanical across ~60 files; no behavior change. Tracked as **W17**.

---

## 10. Existing artifacts (what's in / out of scope)

- **Untracked root `.md` files** (`AUTO_MODEL_*`, `_AUTOMATED_MODEL_IMPLEMENTATION_SYSTEM.md`,
  `_SKILL_COORDINATION_README_STANDARDS.md`, `BIOLM_MODEL_AGENT_PROMPTS.md`, etc.) and the **`ref/`**
  directory are temporary artifacts for **unrelated internal side-projects** — **out of scope;
  ignore them.** (They are untracked for a reason.)
- **In scope:** the four checked-in **`.claude/skills/`** — `model-implementation`,
  `model-knowledge-base`, `code-quality`, `pr-management`. Ship them. One fix first: the two model
  skills disagree on the README standard (model-implementation wants a ~100-line minimal README;
  model-knowledge-base wants the comprehensive `models/dummy/README.md` template). Resolve in favor
  of the comprehensive template before shipping (see W13 in `03_WORKSTREAMS.md`).

---

## 11. Commons internals flagged for simplification (2026-06-24)

These are "don't ship something over-engineered publicly" findings from the deep-dive:

- **`EnhancedStringEnum`** (`models/commons/model/pydantic.py:43-98`; metaclass `EnhancedEnumMeta` +
  `_CastableEnumMixin`; ~83 subclasses across ~46 files; Python target `>=3.12`). **Overkill.** The one
  load-bearing feature is the mixin that casts raw `str`→enum for **strict** pydantic models
  (`RequestModel` is `strict=True`). Everything else is free from stdlib `StrEnum` on 3.12 — and the
  class-level `__iter__` is **dead code** (never runs; `EnumMeta` drives iteration). **Fix:** collapse
  to `class EnhancedStringEnum(_CastableEnumMixin, StrEnum)`; delete the metaclass, `__iter__`,
  redundant `__str__`; keep the casting mixin (incl. its narrow pydantic-v1 branch used only by
  `sadie`). Nothing breaks. (W3a.)

- **Weight-acquisition subsystem** (`storage/acquisition.py` ~1520 LOC + `r2_utils.py` ~725 +
  `downloads.py` ~726 + `download_helpers.py` ~644 + `r2.py` ~139 + `modal/downloader.py` ~271 ≈ 4025
  LOC). Cut ~600 LOC of dead/duplicated code: `TargetedBypassDetector` (~190, only prints, flag never
  read), the unused `CUSTOM` strategy + `CustomSourceConfig` (~200), duplicate validation passes,
  legacy `R2Utils` re-export aliases, stale docstring line-refs. Standalone workstream **W-acq**;
  land before the Stage-3 fan-out. Grep `models/*/download.py` for `bypass_detected`/`CUSTOM` before
  deleting.

- **Gateway class-discovery AST scan** — see §6 (replace with explicit `modal_class_name`; W8).

- **`generate_tests_from_suite` frame injection** — see §9 (return-and-assign; W17).
