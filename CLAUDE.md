# CLAUDE.md — TEMPORARY bootstrap (delete & replace before this repo is public)

> 🛑 **This entire file is temporary, and it knows it.**
> It exists ONLY to orient agents during the private phase of porting a curated subset of the
> internal `biolm-modal` repo into this open-source repo. It is **not** the public CLAUDE.md.
>
> **Before launch:** delete this file and replace it with a clean, permanent **public CLAUDE.md**
> that documents the project for outside contributors and references **nothing** about this porting
> process, the internal `biolm-modal` repo, or `.planning/`. Authoring that public CLAUDE.md (and
> deleting this bootstrap) is a tracked deliverable — see `.planning/03_WORKSTREAMS.md` (W14) and its
> Definition of Done.

Everything below is porting-phase scaffolding, not permanent project documentation.

## Read the plan first (and to RESUME mid-execution)
This repo is **mid-execution**. On a fresh session, orient in this order: **(1)** the project memory
`project_oss_biolm_catalog.md` (live status + all ratified decisions), **(2)** `git log --oneline`
(what's committed), **(3)** `.planning/00_MASTER_PLAN.md` + `.planning/04_TESTING_STRATEGY.md` §0
(the **Modal cost-discipline** validation model), **(4)** `.planning/03_WORKSTREAMS.md` +
`.planning/02_MODEL_INCLUSION_MATRIX.md` for the next work. (`README.md` = index; `01` = evidence base.)

**Status (2026-06-27) — EXECUTION IN PROGRESS.** The commons + global-rules phase is **done &
committed** (13 commits on `main` = the porting trunk): W1 bootstrap → W2 extraction (46 models, 14
excluded) → W3a commons decouple + 46-model API migration → W-acq → W7 (canonical actions
`predict/fold/encode/generate/log_prob/score` + `BioLMError→UserError/ServerError` taxonomy) → W6
(structured logging, `print` banned via ruff T20) → W17 (pytest collection). **NEXT = W5 per-model
hardening fan-out** (46 models, batches A–H in `02`; this is where the deferred schema-FIELD renames
apply). **Validate Modal-free** (static + Opus review); batch live deploys into Milestone A
(`peptides` smoke) / B (comprehensive) — see `04` §0. **Commit per major block.**

## Porting ground rules
- The internal repo **`/Users/qamar/dev/biolm-modal` is READ-ONLY reference** (reference branch =
  `main`). Read `main` via the detached read-only worktree
  `/Users/qamar/dev/biolm-modal-worktrees/oss-readonly-main` — do NOT switch the internal checkout (it
  has unrelated uncommitted work). Extract FROM it INTO here; never edit it. Ignore its untracked root
  `.md` files / `ref/`.
- `.planning/` is a temporary internal dotfile dir — it is deleted (and git history nuked) before
  the repo goes public. Don't reference `.planning/` from any file meant to ship publicly.
- Use isolated git worktrees for parallel work (master plan §7). **Never edit `models/commons/` inside
  a per-model batch** — surface requests to `.planning/COMMONS_REQUESTS.md` for the W3b reconciliation
  pass (commons is its own reviewed workstream).

## Conventions that carry into the public repo (tooling lands in W1)
- `make style` before every commit (once the Makefile / pre-commit hooks exist).
- Pin all ML dependencies to exact versions.
- R2 credentials come from Modal secrets, not local env vars.
- Structured logging only — no `print` (W6).
- Run a model's tests via explicit `python -m pytest models/<model>/test.py`; generate fixtures first.

## Memory
This dir's project memory is seeded; canonical entry: `project_oss_biolm_catalog.md`.
