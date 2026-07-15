---
name: pr-management
description: Diagnose CI failures, predict deploy blast radius, and clear the pre-push/PR gate for biolm-hub. Use when a CI check is red (`lint · types · unit`, `docs build`, `secret scan`), a model fails to deploy or test on Modal, before pushing a branch or requesting the `deploy-approved` label, or when deciding whether a failure is worth retriggering.
---

# PR management for biolm-hub

Predict CI impact, debug failures at the source, and clear the gate before you push or request a
deploy. Read the reference for the task in front of you — the Core Rules below always apply.

## Core Rules (always apply)

These take precedence over everything in the references. Follow them before retriggering CI.

**Rule 1: NEVER assume transient — investigate first.** Do NOT retrigger CI until you have identified the root cause from Modal container logs. "It might be transient" is not a root cause.

**Rule 2: Container logs are the PRIMARY diagnostic.** GitHub Actions logs show symptoms. Modal container logs show causes. If you haven't checked container logs, you haven't investigated.

**Rule 3: Local debugging is the DEFAULT first action** (`references/debugging.md`). When a model fails in CI, deploy it locally + monitor container logs. This is step 1, not a fallback.

**Rule 4: 2+ failures = confirmed bug.** If a model fails twice with similar errors, stop retriggering. Fix the code.

**Rule 5: Opaque errors are NOT infrastructure errors.** "Empty error," "500," or truncated messages usually mean the real error is in container logs. Investigate, don't retrigger.

**Anti-pattern to avoid:** See failure → assume transient → `gh run rerun --failed` → wait → fails again → THEN investigate. One local deploy + container log check finds the root cause in 5 min. Retriggering without investigating first wastes that time for every model in the matrix.

## Which reference to read

| You are… | Read |
|----------|------|
| Debugging a red CI check or a model that crashed on Modal | `references/debugging.md` |
| Deciding what a change will deploy, or whether to request `deploy-approved` | `references/ci-impact.md` |
| About to push a branch or open/finish a PR | `references/pre-push.md` |
