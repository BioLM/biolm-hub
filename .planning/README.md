# BioLM Open-Source — Planning Control Center

This directory is the **planning home** for open-sourcing a curated subset of the internal
`biolm-modal` repository as a flagship public project under the BioLM org.

It lives in `/Users/qamar/dev/biolm-models/` (the working repo dir) under **`.planning/`** — a
**temporary internal dotfile dir**. Keep open-sourcing work out of the internal repo
(`/Users/qamar/dev/biolm-modal`), which must stay undisturbed. `.planning/` may be checked into the
private git during development, but **before the repo goes public, delete `.planning/` and nuke git
history.**

## Start here (read in order)

| Doc | What it is |
|-----|-----------|
| [`00_MASTER_PLAN.md`](00_MASTER_PLAN.md) | The north star: vision, scope, naming, OSS-quality bar, the staged roadmap (Stage 0→7, incl. global-standards-before-per-model), execution topology for parallel worktree agents, cross-cutting decisions (with a complexity column), risks, and open decisions. **Read this first.** |
| [`01_INVESTIGATION_FINDINGS.md`](01_INVESTIGATION_FINDINGS.md) | The evidence base — consolidated technical findings about the internal repo (models, knowledge graph, Modal image pattern, CLI, gateway, R2/caching, CI/CD, testing, web app). Future agents read this **instead of re-investigating**. Every claim has a file path. |
| [`02_MODEL_INCLUSION_MATRIX.md`](02_MODEL_INCLUSION_MATRIX.md) | Per-model ship/later/exclude decision table (driven by `sources.yaml` license), each model's actions and Docker-split difficulty bucket, the **Global Rules** (locked Stage-2 standards), the per-model hardening checklist, and suggested batch grouping for the Stage-3 fan-out. |
| [`03_WORKSTREAMS.md`](03_WORKSTREAMS.md) | The detailed task breakdown — every workstream with goal, tasks, acceptance criteria, dependencies, owning stage, and files touched. This is what worktree agents pick up. |
| [`04_TESTING_STRATEGY.md`](04_TESTING_STRATEGY.md) | The testing contract — the T0→T3 tiers (static → unit → integration-on-Modal → deployment), the change→verify loop, golden-fixture discipline, CI gating, and the prerequisites that must hold before the megarun can self-verify. |

## Status

- **Phase: Planning (Stage 0).** No code extracted yet. Planning docs refined **2026-06-24** with a
  10-agent investigation fan-out (licensing, actions, schemas, caching, gateway discovery,
  acquisition, testing, logging/errors, `EnhancedEnum`, Dockerfile feasibility) + user-ratified
  decisions.
- **Reference source (read-only):** `/Users/qamar/dev/biolm-modal` @ `main` — read via the detached
  worktree `/Users/qamar/dev/biolm-modal-worktrees/oss-readonly-main` (don't switch the internal
  checkout; it has unrelated uncommitted work).
- **Decisions resolved:** repo name `biolm-models`; esm3 + diamond excluded; **esmc 300M ships**
  (honor Cambrian-Open attribution); esmfold2 ship-later (gated on upstream PR → `main`); auth = none;
  mypy enforced; both caching tiers off by default; `predict_log_prob`→`log_prob`; `biolm-public`
  confirmed (exists + empty). **Still open:** CLI command name, Modal env name, esmfold2 upstream PR.
  See `00_MASTER_PLAN.md` §10.

## How future agents use this

1. Read `00_MASTER_PLAN.md` to understand the stage you're in and the quality bar.
2. Find your assignment in `03_WORKSTREAMS.md` (cross-cutting) or `02_MODEL_INCLUSION_MATRIX.md`
   (a model batch).
3. Work in an **isolated git worktree** per the execution topology (§7 of the master plan).
4. Update the relevant doc's checklist as you complete items; leave the docs as the durable
   record of progress.
