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

## Read the plan first
This repo is mid-port. Before doing anything, read **`.planning/00_MASTER_PLAN.md`**, then
`.planning/01_INVESTIGATION_FINDINGS.md`, `.planning/02_MODEL_INCLUSION_MATRIX.md`,
`.planning/03_WORKSTREAMS.md` (`.planning/README.md` is the index).

**Status (2026-06-22):** Stage 0 — planning complete, awaiting user review/feedback. No code
extracted yet.

## Porting ground rules
- The internal repo **`/Users/qamar/dev/biolm-modal` is READ-ONLY reference.** Extract FROM it INTO
  here; never edit it. It's the source of truth — re-investigate it for any detail the plan omits.
  Ignore its untracked root `.md` files / `ref/` (unrelated side-projects).
- `.planning/` is a temporary internal dotfile dir — it is deleted (and git history nuked) before
  the repo goes public. Don't reference `.planning/` from any file meant to ship publicly.
- Use isolated git worktrees for parallel work (master plan §7). Never fold `models/commons/` edits
  into per-model work (commons is its own reviewed workstream, W3).

## Conventions that carry into the public repo (tooling lands in W1)
- `make style` before every commit (once the Makefile / pre-commit hooks exist).
- Pin all ML dependencies to exact versions.
- R2 credentials come from Modal secrets, not local env vars.
- Structured logging only — no `print` (W6).
- Run a model's tests via explicit `python -m pytest models/<model>/test.py`; generate fixtures first.

## Memory
This dir's project memory is seeded; canonical entry: `project_oss_biolm_catalog.md`.
