# Testing Strategy — how agents change code and verify it

**Created:** 2026-06-27. The contract every workstream + subagent follows so code can be modified and
**proven** at each step of the megarun. Ties to: W17 (collection), W12 (shared assets), W4 (R2
fixtures), W11 (CI gating), W-slice (the canary). Per-model acceptance in `02` maps to the tiers here.

> **Hard prerequisite:** **W17 must land before the fan-out.** Until `generate_tests_from_suite`
> returns-and-assigns (not `inspect.currentframe()` injection), `pytest` silently collects **zero**
> tests and "green" is meaningless. Treat W17 + a `pytest --collect-only` CI smoke-test as the gate
> that makes every later tier trustworthy.

---

## 0. Modal cost discipline (READ FIRST — 2026-06-27 user directive)

**Minimize Modal spend during development.** Live Modal deploys + T2/T3 testing cost real money
(GPU/conda builds especially). So during the port we validate **cheaply** and **batch** the expensive
Modal runs:

- **Development validation (cheap, the default):** every change is validated by **T0 (static) + T1
  (unit) + a fresh-context Opus review** of the diff (correctness, contract adherence, commons-API
  breakage, schema/action/logging/error conformance). The Opus review *replaces a live deploy* during
  the port. **Do NOT deploy per-change.**
- **Modal milestones (deliberate, bounded spend — surface the intended cost to the user first):**
  - **Milestone A — contract smoke (recommended, cheap):** once the Stage-2 commons sequence + the
    three slice models are review-clean, deploy the **single cheapest model (`peptides`, pure CPU)** —
    or the full slice if budget allows — to confirm the decoupled commons actually deploys + runs.
    Catches systemic commons breakage before the fan-out piles on.
  - **Milestone B — comprehensive (required, the big spend):** once all models are ported +
    review-hardened, run the full T2+T3 matrix (deploy + integration + deployment) so CI is green for
    real. The user is fine doing this as a single pass at the end.
- **Tradeoff:** review-based validation reduces but does not eliminate the risk that only a live
  deploy would catch (a subtle Modal-build break). Keeping Milestone A early bounds that risk; the
  user has accepted the rest.

---

## 1. The test tiers (what exists, what each needs)

The internal `TestSuite`/`generate_tests_from_suite` infra emits pytest tests with markers
(`integration`, `deployment`, `slow`, `e2e`, `live_modal`). Fixtures are programmatic
(`FixtureGenerator` writes golden inputs + outputs to `test-data/models/<slug>/` in R2);
`runner.py` loads input + golden output from R2, runs `.remote()` with retry, compares with
tolerances/validators.

| Tier | What | External deps | Speed | When |
|---|---|---|---|---|
| **T0 Static** | `make style` (ruff/black), **mypy**, import check, `pytest --collect-only models/<m>/test.py`, action-name + `print`/`T20` lint, `modal_class_name` CI guard | none | seconds | every change, always first |
| **T1 Unit** | `pytest -m "not integration and not deployment and not slow and not e2e and not live_modal"` | none | seconds–min | every change |
| **T2 Integration** | deploy to a **dev Modal env**, generate fixtures, run `@pytest.mark.integration` — golden input/output from R2, tolerances/validators | Modal (dev) + R2 (read, + write on first deploy) | minutes (GPU build) | any change to a model's behavior/build, or to `commons/` |
| **T3 Deployment** | `@pytest.mark.deployment` against the live deployed endpoint | Modal (dev) + R2 | minutes | after T2, before "done" |

**Provisioning needed (user — see §5):** a **dev Modal environment** distinct from the prod
`biolm-models` env (suggest `biolm-models-dev`) + **R2 write creds** (already confirmed working on
`biolm-public`). T0/T1 need neither and run in any clone/CI.

---

## 2. The change → verify loop (every agent, every workstream)

1. Work in an isolated git worktree (or in-tree for serialized solo work like W3a).
2. **T0 static** — must pass before anything else. (Cheap; catches most mistakes.)
3. **T1 unit** — must pass.
4. A **fresh-context Opus reviewer** checks the diff (correctness, contract/commons-API breakage,
   schema/action/logging/error conformance). **During the port this is the primary validation**, in
   place of a live deploy (cost discipline, §0). Required for W3a/W3b and every W5 batch.
5. **T2/T3 (Modal) are deferred to milestones (§0)** — not run per-change. When a milestone runs, use
   the canonical command `python -m pytest models/<m>/test.py -m integration` (then `-m deployment`).
6. Mark a checklist item done when T0 + T1 + review pass; mark **deploy-dependent** acceptance done
   only after the relevant Modal milestone confirms it.

**Golden-fixture discipline (critical):** the golden output in R2 is the **oracle**. Do **not**
blindly regenerate goldens to make a test pass — that masks regressions. Regenerate a golden only when
the output change is **intended and reviewed**; record why in the diff. For non-deterministic models,
rely on the suite's **tolerances/validators** (and pinned seeds), not on exact-match.

---

## 3. Scope of testing per change type (cost control)

T2/T3 cost Modal compute (some builds are GPU/conda-heavy), so **don't run the full ~45-model matrix
on every change.** Scope by blast radius:

- **Single-model change (a W5 batch model):** T0+T1 on the repo; T2+T3 on **that model** (+ its variants).
- **`commons/` change (W3a, W-acq, W8-cache, W6/W7 commons bits):** commons affects *every* model →
  run T2 on a **representative canary set** that spans the build buckets — the **W-slice trio (esm2
  GPU, peptides CPU, one conda model)** plus one micromamba (`mpnn`) and one GPU-build (`evo2` or
  `chai1`). Full matrix only at the integration point (pre-merge of the commons sequence), via the
  smart change detector (`detect_models.py` — commons change ⇒ all, `--smart` narrows).
- **Schema/action rename (W7):** T0 catches signature breaks repo-wide; T2 on one model per affected
  family (antibody, fold, log_prob) confirms the rename + alias back-compat.
- **Cross-cutting lint (W6 logging / T20):** T0 only (no deploy).

---

## 4. CI mapping (W11) + guardrails

- **Every PR (safe, no external resources):** T0 + T1 only — runs for untrusted external PRs too.
- **Maintainer-gated (label/`/deploy`, `pull_request_target` hardened):** T2 + T3 matrix over changed
  models. Never expose secrets to untrusted code.
- **Guardrails (house rules — non-negotiable in the megarun):**
  - **Fix failing models locally first; never push just to re-trigger CI.**
  - **Never push unless ALL currently-failing models are verified green locally.**
  - A "done" claim requires the actual command + pass/fail output, not an assumption.

---

## 5. What must be true before the megarun can self-verify

- [ ] **W17 merged** — `pytest --collect-only models/<m>/test.py` returns ≥1 item (else green is fake).
- [ ] **Dev Modal env created** (e.g. `biolm-models-dev`) + **R2 write creds wired** (so T2/T3 can deploy
      + populate). *(user provisions — see master plan §10.)*
- [ ] **W3a commons-decouple merged** so a model deploys from the new repo with zero internal deps.
- [ ] **W-slice review-clean** (esm2 + peptides + one conda model: code ported + T0/T1 + Opus review)
      before fan-out. Its **live T2/T3 deploy is Milestone A** (§0) — a deliberate, bounded Modal
      spend, not an every-change gate.
- [ ] **W12 shared-asset convention locked** (so fixtures are written right the first time).
- [ ] **W11 CI** runs T0+T1 on every PR and gates T2+T3.

During the port, agents validate via T0 + T1 + Opus review (§0); **deploy-dependent acceptance is
confirmed only at the Modal milestones (A/B)**, not continuously. The orchestrator must not claim a
model "deploys + tests green" until the relevant milestone has actually run it.
