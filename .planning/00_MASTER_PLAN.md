# Master Plan — Open-Sourcing the BioLM Model Catalog

**Status:** Stage 0 (Planning) · **Created:** 2026-06-21 · **Updated:** 2026-06-27 · **Owner:** Ahmad Qamar (BioLM)
**Working dir:** `/Users/qamar/dev/biolm-models/` (separate git repo; internal repo untouched)
**Source repo:** `/Users/qamar/dev/biolm-modal` @ `main` (read-only reference; a detached read-only
worktree at `main` lives at `/Users/qamar/dev/biolm-modal-worktrees/oss-readonly-main`)

> This is the north-star document. It defines *what* we are building, *why*, the quality bar,
> the staged roadmap, and how parallel agents execute it. Detailed tasks live in
> `03_WORKSTREAMS.md`; per-model decisions in `02_MODEL_INCLUSION_MATRIX.md`; the evidence base
> in `01_INVESTIGATION_FINDINGS.md`.

> **2026-06-24 update:** a 10-agent read-only investigation fan-out resolved the open technical
> questions (licensing, actions, schemas, caching, gateway discovery, acquisition, testing,
> logging/errors, the `EnhancedEnum` class, Dockerfile feasibility). Their verdicts are folded in
> below and into `01–03`. User-ratified decisions: diamond **excluded**, esm3 **excluded**, esmc
> **300M-only (ship — honor attribution)**, esmfold2 **ship-later**, response caching **both tiers off by
> default**, `predict_log_prob` **renamed `log_prob`**.

---

## 1. Vision & thesis

Open-source a **clean, standardized, agent-first catalog of open biological ML models that
deploy on Modal with a couple of commands**, as BioLM's flagship public project.

**Why now.** Implementing a bio-ML model used to be a moat — scientist code is dependency hell,
undocumented, fragile. Coding agents have commoditized that work: a biologist can now ask an
agent to implement a model on Modal end-to-end. So the per-model implementation is no longer a
competitive advantage. The advantage that *remains* — and that this repo provides — is **not
making everyone reinvent the wheel**: ready-to-run, uniformly structured, documented,
deploy-anywhere bio-models that an agent (or human) can pull off the shelf and run.

**Strategic payoff.** (1) Foster a contributor community that adds models via agents →
diversification. (2) Brand-building flagship under the BioLM org → funnel to the
professional-services / protein-design business. (3) A public, standardized substrate that
*our own* agents and customers' agents can target.

**Design center: agent-first.** Every choice optimizes for an LLM/agent consumer — obvious
action verbs (`fold`, `score`), uniform schemas, machine-readable per-model knowledge graph,
one-command ergonomics, and a polished "implement a new model" skill so the catalog is
self-extending.

---

## 2. Scope

### In scope (what we open-source)
- **`models/`** — the curated, license-cleared subset (~45 shippable; see `02_MODEL_INCLUSION_MATRIX.md`).
- **The per-model knowledge graph** — `sources.yaml`, `comparison.yaml`, `README.md`, `MODEL.md`,
  `BIOLOGY.md`. This qualitative layer (when-to-use, training data, loss, benchmarks, biology
  modeled, license, alternatives) is a core differentiator and ships with each model.
- **`models/commons/`** — the framework (config, decorators, Modal helpers, R2 storage/download,
  testing) — **decoupled** from billing/Django-auth/analytics, and **simplified** (see W-acq, the
  `EnhancedEnum` trim, and the gateway-discovery fix).
- **`cli/`** — the `bm` tool (provisional name — `bm` now reads "biolm-**m**odels"; §8/§10), polished
  for ease-of-use (setup check, deploy, serve, cache controls).
- **`gateway/`** — shipped in two forms: a minimal `gateway.py` (~20 lines, no caching) and
  `gateway_with_cache.py` (both response-cache tiers — modal.Dict + R2 — **off by default**, one
  opt-in flag).
- **A simple web app** — catalog of deployable models with run-inference UI (extract + simplify
  the existing `gateway/catalog/`); deployed = active, undeployed = greyed-out.
- **R2 model + test-asset infrastructure** — public read-only BioLM bucket (`biolm-public`) as
  default; users can point at their own bucket. The 1:1 R2↔container directory mapping is preserved.
  Response caching is a separate opt-in (off by default; user supplies a bucket/dir to enable it).
- **CI/CD** — build/deploy/test a changed model, **gated behind maintainer approval** (so untrusted
  external PRs don't trigger expensive Modal jobs); modeled on the internal `.github/` workflows.
- **Claude skills** — `model-implementation`, `model-knowledge-base`, `code-quality`,
  `pr-management` (the self-extension toolkit).
- **OSS scaffolding** — `README`, `CONTRIBUTING`, `PHILOSOPHY`, `SECURITY`, `LICENSE`, `CODE_OF_CONDUCT`,
  `FUTURE_WORK.md` (the public, scoped future-work record — see below), mkdocs site, quickstart.

### Optional, in-scope final stage (decide go/defer late — NOT deferred from the outset)
- **Off-Modal `Dockerfile` + `requirements.txt` generation** (per-model split out of `app.py`).
  Feasibility is now characterized (investigation §3): the source-copy layer is a trivial `COPY`;
  the download layer maps to `RUN python download.py` with BuildKit build-secrets; conda models need
  a micromamba base; **GPU-at-build models have no standard `docker build` equivalent and NIM models
  are impossible.** So this ships per-model by eligibility, as the **final optional stage of v1** —
  we decide near the end whether to include it in the initial release or defer it. (See Stage 6 and
  W15.)

### Out of scope (stays internal / excluded)
- **Billing, usage metering, Moesif analytics, Django auth** — strip entirely from commons/gateway.
- **`workflows/`** (multi-model pipelines), **`finetune/`/`training/`**, the internal platform-vision
  in `ref/` (the 9-primitive "BioLM System Proposal" — a *separate* internal effort), and the
  `AUTO_MODEL_*` automated-implementation pipeline (a *separate* internal effort on another branch).
- **Non-commercial / NIM / proprietary models** — see exclusion list in the matrix.
- **Internal secrets, domains, secret names** (`django-modal`, `dev-aq.biolm.ai`, etc.).

### Documented future work (deferred, but recorded publicly for contributors)
Deferred items are **documented in a public `FUTURE_WORK.md`** (not hidden) so the repo sets a
precedent of openly-scoped roadmap that outside contributors can pick up:
- Biological-data **benchmarks** (ProteinGym etc.), **self-improving skills**, **BuildKit** fast
  builds, and the **off-Modal Dockerfile** tail (GPU-at-build / conda models) if not shipped in v1.

---

## 3. Repo name

Requirements: instantly legible ("you know what's inside from the name"), lives in the **BioLM
GitHub org** (brand association is a deliberate goal), avoid `biolm-core`. Must read well as
"a standardized, deployable catalog of open bio-models on Modal, built for agents."

**Chosen: `biolm-models`** (we are working in `/Users/qamar/dev/biolm-models/`). May still be
revisited before public launch, so don't hard-code it anywhere painful to rename. Alternates
discussed: `biolm-zoo` ("model zoo" framing) and `biolm-catalog` (catalog/serving framing).
Conflicts avoided: `biomodels` (EBI systems-biology DB), `biomodal` (a sequencing company).

**Still to brainstorm (§10):** the **CLI command name** (provisional `bm`), the **Modal environment
name** for BioLM's own reference deployments, and confirmation of the single-bucket R2 layout.

**Repo & planning layout:** the working repo dir is `/Users/qamar/dev/biolm-models/` (its own git
repo). Planning docs live in **`.planning/`** — a *temporary internal dotfile dir* that may be
checked into the private git during development, but **must be deleted (and git history nuked)
before the repo goes public.**

---

## 4. The OSS-excellence bar (north star)

Inspiration: Erik Bernhardsson's repos (`modal`, `annoy`) and best-in-class infra OSS. Guiding
principles this project commits to:

1. **Ergonomics first / "five-minute success."** `git clone` → `bm setup` → `bm deploy esm2` →
   first inference, in three commands. The README's first screen gets a user to a running model.
2. **Simplicity & the right abstractions.** Minimal surface area; one obvious way to do a thing;
   small, composable modules. The bare `gateway.py` (~20 lines) is a litmus test of this. (This is
   why we simplify `EnhancedEnum`, kill the gateway's AST-parsing discovery, and cut ~600 LOC of
   dead acquisition code before we fan out.)
3. **Consistency & uniformity.** Identical model layout, uniform schemas, uniform action verbs,
   uniform error taxonomy, uniform logging. An agent that learns one model knows them all.
4. **Modern, idiomatic Python.** Structured **logging (no `print`)**, full **type hints**, Pydantic
   v2, pinned deps, `ruff`/`black`, `uv`, **mypy enforced repo-wide** (plus `make style`). Internal
   repo has pre-existing mypy errors we won't inherit — OSS starts clean.
5. **Testing as the coherence mechanism.** Every model has integration + deployment tests with
   golden fixtures; a shared test-asset library; coverage ≥85% (denominator excludes GPU-only
   inference paths that can't run in CI). Tests must be **pytest-collectable** (W17 fixes today's
   non-collection).
6. **Docs as a feature.** Auto-generated mkdocs site; per-model API schema docs; the knowledge
   graph rendered; `CONTRIBUTING` + `PHILOSOPHY` that explain the agent-first method; `FUTURE_WORK`.
7. **Self-extending.** The `model-implementation` skill means a contributor's agent can add a new
   model that matches house style without human hand-holding.
8. **Trustworthy CI.** Reproducible, deterministic (seeds pinned), maintainer-gated for cost
   safety, green-by-default.

A concrete "Definition of Done for the repo" checklist lives at the end of `03_WORKSTREAMS.md`.

---

## 5. Models (summary)

Per the 2026-06-24 licensing investigation + user ratification (full table: `02_MODEL_INCLUSION_MATRIX.md`):

- **~45 shippable**: 44 clean MIT / Apache-2.0 / BSD models (incl. `pro1`, Apache-2.0), **plus esmc
  (300M-only — user-approved to ship, 2026-06-27)**; honor the Cambrian-Open "Built with
  ESM"/naming/attribution terms via a per-model LICENSE (a compliance task, not a blocker); the 600M
  NC variant is dropped. Plus `dummy` as the template.
- **14 excluded:** NIM (`af2_nim`, `msa_search_nim`); non-commercial (`nt`, `poet`, `pro4s`,
  `saprot`, `gemme`, `soluprot`); proprietary/ambiguous (`ablef`, `biolmtox2`, `camsol`);
  **`esm3`** (Cambrian Non-Commercial — the "ESM Open Model License" label was wrong); **`diamond`**
  (GPL-3.0 — legally shippable as a subprocess/mere-aggregation, but excluded to keep the repo
  cleanly permissive and avoid GPL-binary redistribution overhead); **`proteina_complexa`** (weights
  under NVIDIA Open Model License — royalty-free + commercial but **revocable**; **user-confirmed
  EXCLUDE 2026-06-27**, revisitable later).
- **1 ship-later (new):** `esmfold2` — genuinely MIT but from the **Chan Zuckerberg Biohub** ESM
  lineage (distinct from EvolutionaryScale); blocked on its incomplete upstream PR and a
  weights-license re-confirm. Add once merged.
- **0 remaining legal holds** (all resolved above).

The six Meta/FAIR ESM models (`esm2`, `esm1b`, `esm1v`, `esm_if1`, `esmfold`, `msa_transformer`) are
clean MIT and ship — decided, no legal needed.

---

## 6. Staged roadmap

Stages overlap, but the **load-bearing dependency is global-standards-before-per-model**: we set the
canonical rules once (Stage 2) so the per-model fan-out (Stage 3) just *applies* them. Each stage
lists its exit criteria.

### Stage 0 — Bootstrap & decisions *(this + next session)*
- Repo name (`biolm-models`), license posture, org placement, mypy=on, auth=none — **resolved** (§10).
- Licensing resolved (§5): esm3/diamond excluded; esmc 300M ships (user-approved; honor attribution);
  esmfold2 ship-later (gated on its upstream PR merging to `main`).
- Public R2 bucket `biolm-public` **confirmed live + empty** (verified 2026-06-24). Brainstorm the
  CLI command name + Modal environment name (§10).
- Scaffold the new repo (LICENSE, README stub, CONTRIBUTING, PHILOSOPHY, FUTURE_WORK, mkdocs
  skeleton, CI skeleton).
- **Exit:** repo skeleton exists; inclusion list approved; §10 decisions resolved or assigned.

### Stage 1 — Extraction & decoupling *(the load-bearing core — "the 99%")*
- **1a Extract** the included models + `commons` + `cli` + `gateway` into the new repo, excluding
  billing/auth/analytics/`workflows`/`finetune`.
- **1b Decouple `commons`:** remove billing/Django/analytics; make R2 optional; parameterize the
  bucket (`biolm-public` default + `BIOLM_R2_BUCKET` override); **both caching tiers off by default**.
- **1c Scrub** hardcoded secret names, domains, internal endpoints. (Fresh repo = no history to
  rewrite — start clean.)
- **1d Vertical slices (owned by W-slice):** prove the contract end-to-end on a clean Modal account
  from the new repo, weights from public R2, tests green — **(i) `esm2`** (GPU pytorch), **(ii)
  `peptides`** (pure CPU), **and (iii) a conda/micromamba model** (e.g. `immunebuilder` or `mpnn`) so
  commons decoupling meets the nasty build patterns *before* the fan-out, not during. These three are
  also the **first writes to public R2** (cache-miss → fetch from source → cache to R2).
- **Exit (gate before Stage 3):** the three slices are **ported + review-clean** (T0/T1 + Opus review,
  zero internal deps). Their **live deploy is "Modal Milestone A"** — a deliberate, bounded spend (do
  the cheapest, `peptides`, at minimum) per the cost-discipline policy; not an every-change gate.
  See `04_TESTING_STRATEGY.md` §0.

### Stage 2 — Global standardization & framework hardening *(do this BEFORE the per-model fan-out)*
A **global pass across all models per criterion** that sets the canonical rules and implements them
once in `commons`, so per-model work in Stage 3 is pure application. The rules are written into
`02_MODEL_INCLUSION_MATRIX.md` (Global Rules section) as the source of truth for per-model reviews.
- **Actions:** add `FOLD`; **rename `predict_log_prob`→`log_prob`**; **drop `extract_features`**
  (propermab→`predict`); keep `predict/encode/generate/score`. (W7)
- **Schemas:** lock the canonical field names — `heavy_chain`/`light_chain` (nanobody/VHH = lone
  `heavy_chain` + `NANOBODY` tag; the molecule distinction lives in tags, not field names), TCR
  `tcr_*`/`peptide`/`mhc`, cross-family `sequence`/`pdb`/`cif`/`smiles`, outputs
  `embeddings`/`logits`/`log_prob`/`score`/`plddt`. (W7)
- **Errors:** ship the `BioLMError → UserError/SystemError` hierarchy with a machine-readable `code`
  field. (W7)
- **Logging:** `get_logger(__name__)` + `configure_logging()` in commons; ruff `T20` bans `print`
  in runtime code. (W6)
- **Framework simplifications (commons, W3a + dedicated workstreams):** trim `EnhancedEnum` to
  `StrEnum`+casting-mixin; replace the gateway's AST class-discovery with an explicit
  `modal_class_name` on `ModelFamily`; cut ~600 LOC of dead weight-acquisition code (**W-acq**); make
  tests pytest-collectable (**W17**).
- **Exit:** canonical rules documented in the matrix + `CONTRIBUTING`; commons implements them;
  lint/CI enforce them.

### Stage 3 — Per-model hardening *(the big parallel fan-out — applies Stage-2 rules)*
For each shippable model, in worktree batches (see §7): deep code review + simplification, apply the
locked logging/schema/error/action rules, verify deploy + integration + deployment tests against
public R2, ensure a per-model `LICENSE`/attribution is present, polish the knowledge-graph docs.
Driven by the per-model checklist in the matrix. **Per-model batches never edit `commons/`** — they
**surface** any commons change request by appending a row to `.planning/COMMONS_REQUESTS.md`; the
coordinator batches them into a single reviewed commons-reconciliation pass (**W3b**) after the
fan-out. Batch agents deploy with **scoped R2 write creds** (first deploy of a model is a cache-miss
that fetches from source and writes to R2 — so population is a Stage-3 side effect; Stage 7 is the
final validation sweep).
- **Exit:** every shippable model passes the per-model checklist; all green in CI.

### Stage 4 — Platform surfaces
- **Gateway:** ship `gateway.py` (bare) + `gateway_with_cache.py` (both tiers, off by default; the
  billing-coupled `computed_count` removed and the duplicated partial-payload closure de-duped).
- **Web app:** standalone catalog + run-inference UI; deployed/undeployed state.
- **CLI:** `bm setup` (Modal-config check + guidance), `bm deploy`, `bm serve`, `bm cache` (off by
  default).
- **CI/CD:** maintainer-gated build/test/deploy (`pull_request_target` + label/comment trigger, with
  the well-known `pull_request_target` hardening — bind the approval to the exact tested commit; the
  workflow definition comes from base, never the PR); unit tests stay on every PR (safe).
- **Exit:** a fresh user can clone, set up, deploy a model, and serve the catalog locally.

### Stage 5 — Docs & DX polish
- mkdocs site; per-model FastAPI schema docs; README quickstart ("three commands"); render the
  knowledge graph; `PHILOSOPHY.md` (the agent-first method — see §4) + `CONTRIBUTING.md` (house
  engineering standards) + `FUTURE_WORK.md`; ship the skills; resolve the README-standard conflict
  between the two model skills.
- **Exit:** docs site builds in CI; quickstart verified on a clean machine.

### Stage 6 — Off-Modal Dockerfiles *(OPTIONAL, in-scope; decide go/defer here)*
- Generate `Dockerfile` + `requirements.txt` for **eligible** models only (no GPU-at-build; public
  weights; standard base image — investigation §3 / W15). This is the **final optional stage**: we
  decide at this point whether to include it in v1 or move it to `FUTURE_WORK.md`.
- **Exit (if pursued):** eligible models build + run off-Modal from a generated Dockerfile; the
  ineligible tail is documented in `FUTURE_WORK.md`.

### Stage 7 — Launch *(owned by W-launch — a single owner for the irreversible, ordered, gated steps)*
- **Populate public R2 by building each shipped model with `biolm-public` selected** — `download.py`
  fetches weights from the original source into the container and caches them to R2. This both
  populates the bucket *and* exercises/validates the download+cache logic for correctness. (Most
  weights are already cached as a Stage-3 side effect; this is the final completeness sweep.)
- Final security pass (W-sec).
- **Public-cleanup gate (strict order):** W-sec sign-off → W14 authors the clean public `CLAUDE.md`
  + deletes the bootstrap `CLAUDE.md` → delete `.planning/` (incl. any `_*_SCRATCH.md` /
  `_REVIEW_FIXES_TODO.md` / `COMMONS_REQUESTS.md`) → nuke git history up to launch. Nothing public may
  reference the internal repo, the porting process, or `.planning/`.
- Flip repo public under BioLM org; announcement (when everything is tested **and** marketing
  material is ready — §10.6).
- **Exit:** public repo live; external user reproduces the quickstart.

---

## 7. Execution topology — how parallel agents run this

The point of the doc set is that **future agents work independently in git worktrees** without
colliding. Two kinds of work:

> **Re-plan note (2026-06-27):** the global-standards-before-per-model restructure and the new
> framework-simplification workstreams change the dependency graph. The wave schedule below resolves
> the old "recompute the split" TODO; **re-validate it (and the batch grouping) once the Stage-2
> commons changes land.**

### Execution waves (topological schedule — the precondition for any autonomous/megarun)
Run wave-by-wave; everything in a wave runs in parallel **except** where the commons-serialization
rule applies (see Coordination rules). **Re-sync `oss-readonly-main` to `origin/main` at the start of
each wave** so the read-only reference doesn't drift.

- **Wave 0 — Bootstrap:** W1.
- **Wave 1 — Extract & scan:** W2, W-sec (initial secret scan).
- **Wave 2 — Commons sequence (SERIALIZED on shared files):** W3a (decouple + simplify) lands first →
  W-acq rebases on it → then W6, W7, W17 branch from post-W3a commons (W6↔W7 still coordinate on
  per-model `app.py`; the `modal_class_name` field is *defined* here).
- **Wave 3 — Slice gate:** W-slice (esm2 + peptides + one conda model) **review-clean** before Wave 4;
  its live deploy is **Modal Milestone A** (cheap contract smoke — see `04` §0).
- **Wave 4 — Per-model fan-out:** W4 (R2 population, incremental) + W5 batches A–H (each: writer →
  fresh-Opus reviewer). Depends on Waves 2–3.
- **Wave 5 — Platform surfaces:** W8, W9, W10, W11 (+ finalize W12 shared assets).
- **Wave 6 — Docs & skills:** W13, W14.
- **Wave 7 — Optional Dockerfiles:** W15 (go/defer decision).
- **Wave 8 — Reconcile & launch:** W3b (commons-reconciliation from `COMMONS_REQUESTS.md`) →
  W-launch (the gated, irreversible launch sequence).

### A. Cross-cutting workstreams (one worktree each)
Each workstream in `03_WORKSTREAMS.md` (bootstrap, extraction, commons-decouple, vertical-slice,
logging, schema/actions/errors, gateway, web app, CLI, CI/CD, test-assets, acquisition-simplify,
test-collection, skills, docs, secret-hygiene, optional-Dockerfiles, launch) is a self-contained
worktree + branch, e.g. `git worktree add ../biolm-models-wt/logging oss/logging`. **Independence is
NOT automatic** — follow the wave schedule above and the commons-serialization rule below.

### B. Per-model hardening (batched fan-out)
- Group the ~45 models into **batches of 5–8** (suggested grouping in the matrix, by
  architecture/Docker-bucket so each batch shares dependency context).
- **One worktree + one writer agent per batch**, following the per-model checklist.
- **Writer/reviewer separation:** after a batch's writer agent finishes, a **separate reviewer
  agent (Opus, fresh context)** reviews the batch diff against reference models. (Per house rule:
  same-context self-review is biased.)
- Models that touch only their own `models/<name>/` dir don't conflict; the risk is shared
  `commons/` edits — forbidden inside per-model batches (see coordination rules).

### Coordination rules
- **Never edit `models/commons/` inside a per-model batch.** Instead, **append the request to
  `.planning/COMMONS_REQUESTS.md`** (model · file:line · what · why); the coordinator addresses them
  in **one reviewed commons-reconciliation pass (W3b)** after the fan-out. Commons changes affect every model.
- **Stage-2 commons-touching workstreams are NOT free-parallel.** W3a, W-acq, W6, W7, W17, and the W8
  cache cleanup all edit overlapping files (`acquisition.py`/`download_helpers.py`/`downloads.py`;
  `decorator.py`/`caching.py`; per-model `app.py`). Serialize/coordinate them per Wave 2 (W3a first,
  W-acq rebases, W6/W7/W17 branch from post-W3a commons). Only the per-model `models/<name>/` edits in
  Wave 4 are genuinely parallel.
- **Re-sync `oss-readonly-main` to `origin/main` before each wave** (it's a detached worktree; it
  won't follow `origin/main` on its own).
- Each agent updates the checklist in the relevant planning doc as it completes items — the docs
  are the shared progress ledger.
- Per-batch reviewer agent uses `model: opus`; writers default to `sonnet` unless the model has
  tricky build logic (conda/GPU-build → `opus`).

---

## 8. Cross-cutting decisions (locked unless noted)

The **Complexity** column flags engineering cost — we only take on complexity when it clearly earns
its keep.

| Decision | Choice | Rationale | Complexity |
|---|---|---|---|
| Response caching | **Both tiers (modal.Dict + R2) off by default**, opt-in via one flag (e.g. `BIOLM_CACHE_ENABLED`) + user-supplied bucket/dir | Keep the warm in-memory tier + the durable R2 tier as features, but never surprise users | Low–Med |
| Gateway batch caching | Keep the (sound) batch partial-hit merge-by-index; **remove billing-coupled `computed_count`; de-dup the partial-payload closure** shared by `gateway/app.py` + `decorator.py` | It's not spaghetti — just clean up the billing leak + duplication | Low |
| Default R2 bucket | `biolm-public` (read-only for external), single bucket with `model-store/`/`model-cache/`/`test-data/` prefixes | Public weights/test data without credentials; preserves 1:1 mapping | Low |
| User R2 override | `BIOLM_R2_BUCKET` + standard AWS_* / `R2_ENDPOINT` env | Users cache to their own bucket | Low |
| R2 credentials | From env vars, injected via Modal secret in-container | Matches existing pattern (creds via Modal secrets, not local env) | Low |
| Actions | Add `FOLD`; **rename `predict_log_prob`→`log_prob`**; **drop `extract_features`** (propermab→`predict`); keep `predict/encode/generate/score`. Don't split `generate`/`design` | `fold` is the obvious agent verb (7 fold models overload `predict`); `log_prob` drops a misleading prefix; `extract_features` was a 1-model outlier; enum is barely load-bearing (string dispatch) so cheap | Low |
| Schema naming | `heavy_chain`/`light_chain` everywhere; **VHH/nanobody = lone `heavy_chain` + `NANOBODY` tag** (molecule type lives in tags, not field names); TCR `tcr_*`/`peptide`/`mhc`; PDB-chain selectors `*_id`; cross-family `sequence`/`pdb`/`cif`/`smiles`; outputs `embeddings`/`logits`/`log_prob`/`score`/`plddt`; pydantic aliases for back-compat | Agent-legibility; eliminates the 5-way heavy/light drift; the antibody/VHH/nanobody distinction is real but belongs to tags | Low–High (entity-collection naming for boltz/rf3 is High → optional/defer) |
| Errors | `BioLMError → UserError(+ValidationError400, UnsupportedOptionError, ResourceNotFoundError) / SystemError(+ModelExecutionError)`, plus a machine-readable string `code` on exceptions + `ErrorResponse` | Uniform, agent-legible errors; extends today's `UserError`/`ERROR_MAP` rather than rebuilding | Low–Med |
| Logging | stdlib `get_logger(__name__)` + `configure_logging()`; **no structlog**; ruff `T20` bans `print` in runtime code (allowed in scripts/CLI/tests) | Modernization + uniformity without a new dependency | Low |
| `EnhancedEnum` | Collapse to `class EnhancedStringEnum(_CastableEnumMixin, StrEnum)` on 3.12; delete the dead metaclass/`__iter__`/redundant `__str__`; keep only the pydantic-strict casting mixin | Don't ship an over-engineered enum publicly; nothing breaks (~83 subclasses keep the name) | Low |
| Gateway discovery | Replace AST-parsing of `app.py` with explicit `modal_class_name: str` on `ModelFamily` (the config the gateway already imports); add a CI guard | Kills a brittle, redundant, silent-failure source-parse | Low |
| mypy | **Enforce repo-wide** in OSS CI (+ `make style`) | Modernization bar; OSS starts clean (we don't inherit internal errors) | Med (initial cleanup) |
| Dockerfile split | **Optional final in-scope stage** (Stage 6), per-model by eligibility; not deferred from the outset, but go/defer is decided late | Real off-Modal value for the eligible majority; GPU-build/NIM tail can't be Dockerfiled | Med–High (per bucket) |
| CLI command name | Provisional **`bm`** (now reads "biolm-models"); alts `biolm`/`blm` | Zero-churn, short; revisit at §10 | Low |
| Modal environment | Dedicated env (provisional `biolm-models`) for BioLM's own reference deployments | Cloning users deploy to their own default env regardless | Low |
| Commons | Refactor freely **in the new repo** (it's the framework we ship) | The internal commons-freeze rule does not apply to the OSS fork | — |
| Modal spend during dev | **Minimize.** Validate via T0+T1+**Opus review** during the port; **batch** live deploy/integration/deployment into Modal **milestones** (A = cheap contract smoke; B = comprehensive at the end) | Keep porting costs low; live deploys cost real money (GPU/conda builds). See `04` §0 | Low |
| Git history | Start fresh in `biolm-models` (no internal history) | Cleanest secret hygiene | — |

---

## 9. Risks & mitigations

| Risk | Mitigation |
|---|---|
| Secret/credential leakage into public repo | Fresh history; automated secret scan in Stage 1c + pre-launch; strip secret-name constants |
| Untrusted PR runs expensive Modal jobs | Maintainer-gated CI (`pull_request_target` + label/comment); unit-tests-only for unapproved PRs |
| **`pull_request_target` secret-exfiltration footgun** | Bind the approval label to the exact tested commit (re-validate on push); workflow definition comes from base, never the PR head; never check out + execute untrusted code with secrets in scope |
| License contamination (NC/NIM/GPL) | `sources.yaml`-driven include filter; resolved (esm3/diamond excluded, esmc 300M ships with attribution honored); per-model LICENSE files; fix the wrong esm3/esmc `license.type` strings |
| Commons decoupling breaks many models at once | Vertical slices first (Stage 1d, incl. a hard conda model); commons changes isolated to reviewed workstreams; full test matrix |
| Per-model fan-out starts before global rules exist | **Global-standards-before-per-model** (Stage 2 → 3); per-model batches apply locked rules only |
| Public R2 weights cost / abuse | Read-only public bucket; R2 egress is free (Cloudflare) so storage/ops are the cost; users can self-host bucket |
| Scope sprawl (60 model dirs × many workstreams) | Strict staging; per-model checklist; deferred items documented in `FUTURE_WORK.md`, kept out of v1 |
| Knowledge-graph PDFs in R2 may include copyrighted papers | Ship metadata (`sources.yaml`) + generated `.md`, **not** raw third-party PDFs, in public bucket |

---

## 10. Open decisions

**Resolved (2026-06-24):**
1. **Repo name** — `biolm-models` (confirmed; revisitable before launch). *(user)*
2. **Legal/licensing** — esm3 **excluded** (Cambrian Non-Commercial); diamond **excluded** (clean-repo
   choice; GPL was legally shippable via subprocess); esmc **300M ship** (user-approved 2026-06-27;
   honor the Cambrian-Open "Built with ESM"/naming/attribution terms via a per-model LICENSE — a
   compliance task, not a blocker; drop 600M); esmfold2 **ship-later** — add **only after** its
   upstream PR merges into `biolm-modal` `main`, then re-confirm the weights license. *(user)*
3. **Public R2 bucket** — `biolm-public` confirmed (exists + empty, verified). Uploads = weights +
   test data + KB `.md`, **not** raw PDFs; populated by building with the public bucket (Stage 7). *(user/Nikhil)*
4. **Auth posture** — gateway ships with **no auth** by default (internal auth was for the Django
   frontend, out of scope here). *(user)*
5. **mypy** — **enforce repo-wide** + `make style`. *(user)*
6. **Launch timing** — when everything is done + tested **and** marketing material is ready. *(user)*

**Still open:**
- **CLI command name** — provisional `bm`; confirm or pick `biolm`/`blm`. *(user)*
- **Modal environment name** — provisional `biolm-models` for BioLM's reference deployments. *(user)*
- **esmfold2** upstream PR must merge into `biolm-modal` `main` (then re-confirm the weights license)
  before its ship-later row activates. *(user)*

---

## 11. Session / handoff protocol

- This planning home (`/Users/qamar/dev/biolm-models/.planning/`) is the durable state; it survives
  across sessions and compaction. Update the checklists here as the source of truth.
- A project memory entry points here (`project_oss_biolm_catalog.md`) so any future session resumes
  from this plan.
- The internal repo is **read-only reference**: agents extract *from* `/Users/qamar/dev/biolm-modal`
  *into* `/Users/qamar/dev/biolm-models`, never editing the former. Read `main` via the detached
  read-only worktree at `/Users/qamar/dev/biolm-modal-worktrees/oss-readonly-main` (don't switch the
  internal repo's branch — it has unrelated uncommitted work).
- Recommended session naming: `oss-stage1-extraction`, `oss-stage2-standards`, `oss-stage3-batch-<n>`.
