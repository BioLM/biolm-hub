# Workstreams — Detailed Task Breakdown

Each workstream is a self-contained unit of work for one git worktree + branch
(`git worktree add ../biolm-models-wt/<name> oss/<name>`). Dependencies are noted; run independent
workstreams in parallel. Stage refers to `00_MASTER_PLAN.md` §6 (note the 2026-06-24 re-stage:
**Stage 2 = global standardization**, **Stage 3 = per-model hardening**). Paths prefixed `INT:` are
in the internal repo (read `main` via the read-only worktree
`/Users/qamar/dev/biolm-modal-worktrees/oss-readonly-main`); unprefixed paths are in the new repo
(`/Users/qamar/dev/biolm-models`).

> **Re-plan note (2026-06-27):** the dependency graph is captured as an explicit **execution-wave
> schedule in `00_MASTER_PLAN.md` §7** — follow it. Two non-obvious constraints: (1) the Stage-2
> commons-touching workstreams (**W3a, W-acq, W6, W7, W17, W8-cache**) edit overlapping `commons/`
> files, so they are **serialized/coordinated, NOT free-parallel**; (2) per-model batches surface
> commons changes via `.planning/COMMONS_REQUESTS.md` for the **W3b** reconciliation pass.

---

## W1 — Repo bootstrap & OSS scaffolding · Stage 0
**Goal:** A clean public-repo skeleton that sets the quality bar from commit #1.
**Tasks:**
- Create top-level `README.md` (three-command quickstart up top), `LICENSE` (MIT or Apache-2.0),
  `CONTRIBUTING.md`, `CODE_OF_CONDUCT.md`, `SECURITY.md`, `PHILOSOPHY.md`, **`FUTURE_WORK.md`** (the
  public scoped-roadmap record), `pyproject.toml`, `Makefile` (`make style` **+ mypy**), `.gitignore`,
  `uv.lock`.
- Author `PHILOSOPHY.md` (agent-first method — master plan §4), `CONTRIBUTING.md` (house standards,
  including the Global Rules from `02`), and `FUTURE_WORK.md` fresh. Do **not** pull from the internal
  repo's untracked temp `.md` files or `ref/`.
- mkdocs skeleton (`mkdocs.yml`, `docs/`) and CI skeleton (lint + mypy + unit tests only at first).
- Confirm the **CLI command name** (provisional `bm`) and **Modal env name** (provisional
  `biolm-models`) — §10 open decisions.
**Acceptance:** `make style` + mypy pass on the skeleton; mkdocs builds; CI green on an empty PR.
**Depends on:** name decisions (mostly resolved).

## W2 — Curated extraction · Stage 1
**Goal:** Bring the in-scope code into the new repo without internal cruft.
**Tasks:**
- Copy `INT:models/<shippable>` (per matrix) + `INT:models/commons/` + `INT:models/dummy/` +
  `INT:cli/` + `INT:gateway/` into the new repo. **Exclude** `workflows/`, `finetune/`, all
  EXCLUDE models (incl. **`esm3`, `diamond`**), `gateway/analytics.py`, billing modules. (`esmc` 300M
  is **in scope** — include it, honoring its Cambrian-Open attribution terms; `esmfold2` is held out
  until its upstream PR merges into `biolm-modal` `main`.)
- Write an extraction script (idempotent) so the copy is reproducible as models are hardened.
- First secret/coupling sweep (full sweep is W-sec/Stage 1c).
**Acceptance:** repo tree contains only in-scope dirs; `ruff`/import check shows no references to
excluded modules from shipped code (beyond known commons coupling handled in W3a).
**Depends on:** W1; matrix approved.

## W3a — Commons decoupling & simplification · Stage 2 *(SERIALIZED head of the commons sequence — affects every model)*
**Goal:** `commons/` is a clean, dependency-light, simplified framework with no billing/auth/analytics.
**Tasks:**
- Remove billing mixins' metering/Django coupling; provide neutral base classes (keep the snapshot
  lifecycle, drop billing). Decide and document the public base-class API.
- Make **R2 optional**: graceful path when no R2 configured (download direct from HF/URL source).
- **Parameterize the bucket:** `INT:models/commons/util/config.py` → default `biolm-public`, override
  `BIOLM_R2_BUCKET`; keep `model-store`/`model-cache`/`test-data` prefixes.
- **Both response-cache tiers off by default** (modal.Dict + R2); opt-in via one flag
  (`BIOLM_CACHE_ENABLED`) + user-supplied bucket/dir.
- Strip Moesif/analytics; remove auth middleware hooks.
- **Simplify `EnhancedStringEnum`** (`INT:models/commons/model/pydantic.py:43-98`) → `class
  EnhancedStringEnum(_CastableEnumMixin, StrEnum)`; delete the dead metaclass/`__iter__`/redundant
  `__str__`; keep the pydantic-strict casting mixin (incl. v1 branch for `sadie`). ~83 subclasses keep
  the name — nothing breaks.
- **Define the `modal_class_name: str` field on `ModelFamily`** here (a commons change). The gateway
  routing swap + AST deletion + CI guard live in W8 (Stage 4); per-model *values* are set during W5.
**Acceptance:** a model deploys + runs using only `commons` with no billing/auth imports; bucket
override works; caching off unless enabled; the enum is trimmed; the `modal_class_name` field exists;
tests pass.
**Depends on:** W2. **Blocks:** W-acq, W6, W7, W17, W-slice, and all per-model batches (W5). **Head of
the serialized Stage-2 commons sequence** (W-acq rebases on it; W6/W7/W17 branch from post-W3a commons).

## W3b — Commons reconciliation pass · Stage 3 (post-fan-out) *(single owner for batched commons changes)*
**Goal:** Apply, in one reviewed pass, the commons changes that per-model batches surfaced (batches are
forbidden from editing `commons/` directly, to avoid 44 conflicting edits).
**Tasks:** read `.planning/COMMONS_REQUESTS.md` (rows: model · file:line · what · why); group, design,
and implement the changes once; re-run the affected models' tests; a fresh-context Opus reviewer signs
off (commons touches every model).
**Acceptance:** every `COMMONS_REQUESTS.md` item is resolved or explicitly deferred (with reason);
full test matrix green.
**Depends on:** all W5 batches. **Feeds:** W-launch.

## W4 — Public R2 bucket & data migration · Stage 1→7
**Goal:** Public read-only weights + test data for shipped models.
**Tasks:**
- `biolm-public` confirmed (exists + empty). Define access keys for maintainer writes (scoped key).
- **Population strategy = build-with-public-bucket:** for each shipped model, deploy/build with
  `biolm-public` selected so `download.py` fetches weights from the original source into the
  container and **caches them to R2** — this populates the bucket *and* exercises/validates the
  download+cache logic for correctness. Migrate `test-data/models/<slug>/...` similarly.
- Ship knowledge-graph **`.md` + `sources.yaml`** to public, **not** raw third-party PDFs (license).
**Acceptance:** `esm2` + `peptides` deploy from a credential-less clone pulling weights from public
R2; `bm r2 ls` (read-only) works anonymously.
**Depends on:** bucket confirmed (done). Incremental as models are hardened; final population at Stage 7.

## W-slice — Stage-1d vertical slices (contract proof + slice gate) · Stage 1d
**Goal:** Prove the end-to-end contract on a clean Modal account *before* the fan-out, exercising the
nasty build patterns early.
**Tasks:** deploy + test, from the new repo against public R2 with zero internal deps: **esm2** (GPU
pytorch), **peptides** (pure CPU), **and one conda/micromamba model** (`immunebuilder` or `mpnn`).
These are the **first writes to public R2** (cache-miss → fetch from source → cache to R2), so they
also smoke-test W4's population path. If the conda slice exposes commons gaps, fix them in **W3a** (not
here).
**Acceptance (GATE before Stage 3):** all three slices deploy + pass integration + deployment tests
from the new repo; a second (cache-hit) deploy serves weights straight from `biolm-public`.
**Depends on:** W3a (decoupled commons), W4 (bucket). **Blocks:** W5.

## W5 — Per-model hardening (batched fan-out) · Stage 3 *(the big parallel effort)*
**Goal:** Every shipped model meets house style and is green from the new repo.
**Tasks:** run the per-model checklist in `02_MODEL_INCLUSION_MATRIX.md` for each model, in the
suggested batches, **applying the locked Global Rules** (actions/schema/errors/logging) and **setting
`modal_class_name`**; **writer agent per batch + separate Opus reviewer agent** on the batch diff.
Per-model batches **never edit `commons/`** — append commons requests to `.planning/COMMONS_REQUESTS.md`
(→ W3b). Batches deploy with **scoped R2 write creds** (first deploy = cache-miss → fetch from source →
write to R2; population is a Stage-3 side effect, validated finally in Stage 7).
**Acceptance:** all `SHIP` models pass the checklist; CI green.
**Depends on:** W3a (commons), W4 (public R2), **W6 + W7 (global rules locked)**, **W12 (shared-asset
naming convention)**, W-acq + W17 (simplified framework merged), **W-slice (slice gate passed)**.

## W6 — Logging standardization · Stage 2
**Goal:** One structured logger across the repo; no `print`.
**Tasks:** add `get_logger(__name__)` + `configure_logging()` to `INT:models/commons/core/logging.py`
(stdlib `logging`, single `StreamHandler(stdout)`; keep `DebugLogger` for request-scoped capture);
enable ruff **`T20`** with per-file ignores (`scripts/`, CLI, tests, vendored `external/`); per-model
pass converting `print(`→`logger.*` in each `app.py`. **No structlog.**
**Acceptance:** zero `print` in runtime code (lint-enforced); consistent levels; logs visible via
Modal stdout capture.
**Depends on:** W3a. **Note:** also apply to the internal repo per user request (separate internal PR).

## W7 — Schema, actions & error standardization · Stage 2
**Goal:** Uniform, agent-legible schemas, action verbs, and error taxonomy — the Global Rules in `02`.
**Tasks:**
- **Actions:** add `FOLD` to `ModelActions`; **rename `PREDICT_LOG_PROB`→`LOG_PROB`**; **drop
  `EXTRACT_FEATURES`** (propermab→`predict`); migrate the 7 ★fold models `predict`→`fold`; normalize
  antifold's freeform `"score"`. Update gateway/catalog/tests + `non_cacheable_actions`.
- **Schemas (canonical field names):** `heavy_chain`/`light_chain` (nanobody/VHH = lone `heavy_chain`
  + `NANOBODY` tag — molecule type lives in the `InputMolecule` tag, **no `vhh`/`nanobody` field**);
  TCR `tcr_*`/`peptide`/`mhc`; PDB-chain selectors `*_id`; cross-family `sequence`/`sequences`/`msa`,
  `pdb`/`cif`, `smiles`+`ccd`, `name`, `params`+`items`; outputs `embeddings`/`logits`/`log_prob`/
  `score`/`plddt`. Use pydantic `populate_by_name` + `Field(alias=…)` for back-compat. (Entity-
  collection renaming for boltz/boltzgen/rf3 is High-complexity → optional/defer.)
- **Errors:** ship `BioLMError → UserError(+ValidationError400, UnsupportedOptionError,
  ResourceNotFoundError) / SystemError(+ModelExecutionError)` in `commons/core/error.py`; add a
  machine-readable string `code` to exceptions + `ErrorResponse`; extend `ERROR_MAP`. (Whether the
  **gateway** promotes body `status_code`→HTTP status is a **W8/gateway** decision — moved out of W7's
  blocking path so W7 can fully lock; default = keep current behavior.)
**Acceptance:** action verbs + schema field names + error types uniform across families; documented in
`CONTRIBUTING.md` + `02` Global Rules; gateway and tests updated; lint/CI check canonical action names.
**Depends on:** W3a. **Must land before the W5 fan-out** (so batches apply final conventions once).

## W8 — Gateway (two versions) + discovery fix · Stage 4
**Goal:** Ship `gateway.py` (~20 lines, no cache) + `gateway_with_cache.py` (both tiers, off by
default), with robust config-driven discovery.
**Tasks:**
- Extract routing core from `INT:gateway/app.py` (`generic_request_handler` + `ModelMapper`); strip
  auth/billing/analytics; parameterize domain (default Modal URL) and auth (default none).
- **Replace AST class-discovery** (`model_discovery.py:106-147`) with an explicit `modal_class_name:
  str` on `ModelFamily`; set it in every model `config.py`; delete `_discover_class_names()` + `import
  ast`. Add a CI guard asserting `config.modal_class_name` resolves to a `@biolm_model_class`-marked
  class in that model's `app.py`.
- Cached version: keep the (sound) batch partial-hit merge-by-index, but **remove the billing-coupled
  `computed_count`** and **de-dup the partial-payload closure** shared by `gateway/app.py` +
  `decorator.py`. Caching off by default behind `BIOLM_CACHE_ENABLED`.
- **Decide** whether the gateway promotes the model response's body `status_code` → HTTP status
  (today: 200 with the code in the body); document + implement the choice. (This is the decision moved
  out of W7 so W7 can lock.)
**Acceptance:** both gateways deploy; bare one routes to a deployed model with no caching/no source
parsing; cached one demonstrably caches when enabled; CI fails loudly on a missing/mismatched
`modal_class_name`.
**Depends on:** W3a, W7.

## W9 — Web app (catalog + serve) · Stage 4
**Goal:** Simple standalone app: catalog of models, run-inference UI, deployed = active / undeployed
= greyed-out.
**Tasks:** extract + simplify `INT:gateway/catalog/` (`generator.py`, templates, `static/`); add a
**deployment-status** check (query Modal for deployed apps) to grey out undeployed models; wire a
`bm serve` launcher (W10); ensure schema-driven forms still work for sequence/pdb/smiles/enum/nested.
**Acceptance:** `bm serve` opens a local catalog; deployed models are runnable, undeployed greyed-out.
**Depends on:** W3a, W8 (routing), W10 (CLI hook).

## W10 — CLI ergonomics · Stage 4
**Goal:** "git clone → `bm setup` → `bm deploy esm2` → inference" in three commands.
**Tasks:**
- Confirm the CLI command name (provisional `bm`).
- `bm setup`: detect Modal config (`MODAL_TOKEN_ID`/secret / `modal token new`); detect R2 config;
  print actionable setup guidance; non-zero exit with a friendly message if unconfigured.
- Keep `bm deploy` (variants); add `bm serve` (launch web app); add `bm cache` controls (off by
  default). Keep `bm r2` read-oriented for external users.
**Acceptance:** a fresh machine gets clear guidance from `bm setup`; the three-command quickstart works.
**Depends on:** W3a.

## W11 — CI/CD (maintainer-gated) · Stage 4
**Goal:** Build/deploy/test changed models, but only when a maintainer approves — so untrusted PRs
never trigger Modal. Modeled on the internal `.github/` workflows.
**Tasks:** adapt `INT:.github/workflows/pr-checks.yml`: keep `make style` + mypy + unit tests on every
PR (safe); move QA-deploy + integration/deployment jobs behind `pull_request_target` + a label
(`approved`) or `/deploy` comment from a maintainer allowlist (reuse the `claude.yml` comment-trigger
pattern). **Harden `pull_request_target`:** bind the approval to the exact tested commit (re-validate
on push), keep the workflow definition from base (never the PR head), never check out + execute
untrusted code with secrets in scope. Port `INT:.github/scripts/detect_models.py` (smart change
detection). Document the contributor flow.
**Acceptance:** an unapproved external PR runs only lint+mypy+unit; a maintainer label triggers the
full model deploy+test matrix; no secrets exposed to untrusted code.
**Depends on:** W2; public R2 (W4).

## W12 — Shared test-asset library · Stage 2–3
**Goal:** Reusable cross-model test inputs to cut duplication and standardize golden inputs.
**Tasks:** survey `INT:test-data/models/*` for common sequences; create `test-data/shared/`
(standard protein/DNA sequences, small benchmark sets) in public R2; refactor fixtures to reference
shared assets where sensible (path-templating already supports it).
**Acceptance:** ≥1 shared asset reused by ≥2 models; the **naming convention is locked into `02`
Global Rules in Stage 2** (W5 depends on it); only asset *population* is incremental.
**Depends on:** W4. Overlaps W5/W17.

## W13 — Skills · Stage 5
**Goal:** Ship the agent-first toolkit so the catalog self-extends.
**Tasks:** port `INT:.claude/skills/` (`model-implementation`, `model-knowledge-base`, `code-quality`,
`pr-management`); **resolve the README-standard conflict** between the two model skills — the
comprehensive `models/dummy/README.md` template wins; update `model-implementation/documentation/
GUIDE.md` (drop the "100 lines" rule + the ESM-2 inline example, add `sources.yaml` to its Phase 1);
de-internalize references (R2 paths, internal-only commands); teach the final Global Rules
(actions/schema/errors/logging).
**Acceptance:** a contributor agent can implement a new model end-to-end from the public skill and
produce house-style files + docs.
**Depends on:** W3a, W6, W7 (so the skill teaches the final conventions).

## W14 — Documentation site & DX · Stage 5
**Goal:** Docs as a feature.
**Tasks:** mkdocs site building in CI; per-model **FastAPI schema docs**; render the knowledge graph
(`MODEL.md`/`BIOLOGY.md`/`comparison.yaml`) into model pages; finalize `README` quickstart;
`PHILOSOPHY.md`, `CONTRIBUTING.md`, `FUTURE_WORK.md`. **Author the permanent public `CLAUDE.md`**
(agent-first contributor guide) containing **zero** references to the internal repo, the porting
process, or `.planning/`; then **delete the temporary bootstrap `CLAUDE.md`** at repo root. Verify the
quickstart on a clean machine.
**Acceptance:** docs site deploys; quickstart reproduced clean; every shipped model has a doc page;
the temporary bootstrap `CLAUDE.md` is gone, replaced by a clean public one.
**Depends on:** W5 (model docs), W7 (final schemas/actions), W10 (CLI commands).

## W15 — Off-Modal Dockerfile generation · Stage 6 *(OPTIONAL, in-scope; go/defer decided late)*
**Goal:** Produce a `Dockerfile` + `requirements.txt` per **eligible** model so models can run outside
Modal. This is the **final optional stage** — at this point we decide to ship it in v1 or move the
remainder to `FUTURE_WORK.md`.
**Eligibility (all three required):** (1) no `gpu=` on any build step (flash-attn/CUDA-extension
compilation needs Modal's build-time GPU, which has no `docker build` equivalent); (2) weights from a
public source (HF Hub or direct URL) — R2-only weights aren't accessible to external users; (3) base
is a standard public registry image (not NIM/private ECR). All NIM models are permanently out.
**Tasks:** `setup_source_layer`→`COPY`; `setup_download_layer`→`RUN python download.py` with BuildKit
`--mount=type=secret` for R2/HF creds; micromamba/conda builds → `mambaorg/micromamba` base. Generate
per eligible model; document the ineligible (GPU-build/NIM) tail in `FUTURE_WORK.md`.
**Acceptance (if pursued):** eligible models build + run off-Modal from a generated Dockerfile.
**Depends on:** W1 (Makefile/tooling), W3a (final commons layout).

> *(There is no W16 — numbering intentionally jumps W15→W17. The deferred Dockerfile-tail + benchmarks
> live in "Documented future work" below.)*

## W17 — Pytest-native test collection · Stage 2 *(before the W5 fan-out)*
**Goal:** Make all `models/*/test.py` first-class pytest collectibles so `python -m pytest
models/<m>/test.py --collect-only` works without running tests (IDE integration, CI targeting,
`pytest -k`).
**Root cause:** `generate_tests_from_suite` (`INT:models/commons/testing/runner.py:369-382`) injects
`test_*` into the caller's module globals via `inspect.currentframe().f_back`; empty parametrize lists
(Modal/R2 absent) silently collect zero tests.
**Tasks:** change `generate_tests_from_suite` to **return** the parametrized test function (remove
`inspect`); each `test.py` assigns it explicitly (`test_{slug}_{type} = generate_tests_from_suite(…)`)
— mechanical across ~60 files; add an empty-params skip/warn; add `models/conftest.py` for marker
registration; CI smoke-test `pytest --collect-only models/` fails on zero items.
**Acceptance:** `pytest models/esm2/test.py --collect-only` returns ≥1 item; no `inspect.currentframe`
in `runner.py`; all test files use the explicit-assignment pattern.
**Depends on:** W3a. **Overlaps/coordinate with** W5 (same test files).

## W-acq — Weight-acquisition simplification · Stage 2 *(serialized after W3a; land before W5)*
**Goal:** Cut ~600 LOC of dead/duplicated weight-acquisition code so every model inherits a simpler
download layer.
**Tasks:** delete `TargetedBypassDetector` (~190 LOC, `acquisition.py:55-241`; replace with a one-line
post-download assertion); delete `AcquisitionStrategy.CUSTOM` + `CustomSourceConfig` + helpers (~200
LOC, unused by any shipped model); deduplicate validation (one `verify_model_dir` pass per
acquisition); remove the legacy `R2Utils` re-export aliases from `download_helpers.py`; prune stale
docstring line-refs in `r2_utils.py`. Optional (separate commit): discriminated-union
`AcquisitionConfig`. **Before deleting:** grep `models/*/download.py` for `bypass_detected`/`CUSTOM`.
**Acceptance:** all SHIP-model tests pass unchanged; `acquisition.py` ≤950 LOC; `r2_utils.py` ≤600
LOC; `make style` passes.
**Depends on:** W3a — **rebase on it; W-acq and W3a edit the SAME files** (`acquisition.py`/
`download_helpers.py`/`downloads.py`), so they are **serialized, NOT parallel**. **Should land before W5.**

## W-sec — Secret & license hygiene · Stage 1c + pre-launch (Stage 7)
**Goal:** No secrets/internal identifiers/copyrighted assets in the public repo or bucket.
**Tasks:** automated secret scan (gitleaks/trufflehog) in CI + pre-launch; remove secret-name
constants (`django-modal`, `cloudflare-r2` naming), internal domains; confirm per-model LICENSE
attribution; **fix the wrong `license.type` strings** (esp. esm3/esmc); confirm public bucket holds no
raw third-party PDFs.
**Acceptance:** secret scan clean; license check passes; manual pre-launch review signed off.
**Depends on:** runs alongside W2/W3a; gates Stage 7.

## W-launch — Launch sequence (irreversible, ordered, gated) · Stage 7 *(the last workstream)*
**Goal:** A single owner for the destructive launch steps, executed in strict order.
**Tasks (each gated on the previous):**
1. Final R2 population completeness sweep (W4) + final security sign-off (W-sec).
2. W14 authors the clean public `CLAUDE.md` + deletes the bootstrap `CLAUDE.md`.
3. Delete `.planning/` (incl. `_*_SCRATCH.md`, `_REVIEW_FIXES_TODO.md`, `COMMONS_REQUESTS.md`).
4. Nuke git history up to launch (fresh root commit).
5. Flip repo public under the BioLM org; announce — **gated on marketing material ready (§10.6)**. If
   `esmfold2`'s upstream PR hasn't merged by here, record it in `FUTURE_WORK.md` rather than block.
**Acceptance:** public repo live; nothing references the internal repo / porting / `.planning/`; an
external user reproduces the quickstart.
**Depends on:** **everything** — W3b (reconciliation), W-sec, W14, W4.

---

## Documented future work (deferred — recorded publicly in `FUTURE_WORK.md`, not started in v1)
- **Benchmarks** (ProteinGym etc.), **self-improving skills**, **BuildKit** fast builds.
- The **off-Modal Dockerfile** tail (GPU-at-build / conda models) if W15 isn't fully shipped in v1.
- (Per user: recording deferred work openly sets a precedent so outside contributors can pick it up.)

---

## Definition of Done — the repo is launch-ready when:
- [ ] The W-slice gate passed (esm2 + peptides + a conda model) before the fan-out; all `SHIP` models then pass the per-model checklist and are green in CI from a clean clone.
- [ ] `git clone → bm setup → bm deploy esm2 → inference` works on a fresh machine in three commands.
- [ ] Bare + cached gateways ship; **both caching tiers off by default**; gateway discovery is config-driven (no AST).
- [ ] Web app serves the catalog with deployed/undeployed state.
- [ ] CI is maintainer-gated (`pull_request_target` hardened); unapproved PRs run only lint+mypy+unit.
- [ ] Public R2 serves weights + test data for all shipped models (populated by build-with-public-bucket); no raw third-party PDFs.
- [ ] Canonical actions (`predict/fold/encode/generate/score/log_prob`), schema fields, errors, and logging are enforced repo-wide; `EnhancedEnum` trimmed; `acquisition.py` simplified; tests pytest-collectable.
- [ ] Skills ship; README-standard conflict resolved; a contributor agent can add a model.
- [ ] Docs site builds; every model has a page; `PHILOSOPHY`/`CONTRIBUTING`/`SECURITY`/`LICENSE`/`FUTURE_WORK` present; mypy enforced.
- [ ] Licensing resolved: esm3/diamond excluded; **esmc-300M shipped with Cambrian-Open attribution honored**; esmfold2 either merged-upstream-and-shipped or recorded in `FUTURE_WORK.md`.
- [ ] No billing/auth/analytics/internal-domain references anywhere.
- [ ] Temporary bootstrap `CLAUDE.md` deleted and replaced by a clean public `CLAUDE.md` (no porting / internal-repo / `.planning/` references); `.planning/` (incl. all `_*_SCRATCH.md` / `_REVIEW_FIXES_TODO.md` / `COMMONS_REQUESTS.md`) removed; git history nuked — all owned by **W-launch**.
