# FABLE — take biolm-hub to a clean v1 public launch

You're Fable. You're taking over `biolm-hub` (`/Users/qamar/dev/biolm-hub`) from a previous
Claude (Opus 4.8) that did a large amount of work. **Read this whole doc, then do the audit in §1
before touching anything.** After that, you own the outcome — I'm handing you the goal, not the steps.

---

## 0. The goal (this is the whole thing)

**Ship `biolm-hub` as a genuinely public-ready v1 open-source release.** It's a standardized,
agent-first catalog of open biological ML models that deploy on Modal in a couple of commands. The
entire reason it exists is **uniformity**: the diff between any two models should be the *science*,
not the plumbing — same layout, same action verbs, same schema conventions, same errors, same logging,
same knowledge-graph, all self-populating from a credential-less clone. A stranger should be able to
`git clone`, `bh setup`, `bh deploy esm2`, and get a real inference in five minutes with nothing but a
Modal account.

I'm not going to tell you how to get there. You'll figure out the "how" better than I can. What I'm
giving you instead is: the existing work to build on, a set of house rules you can't cross, and a hard,
checkable bar for "done." Fence yourself with those and run wide open.

---

## 1. First: audit EVERYTHING with fresh eyes (do this before any change)

The previous agent's work is *fuel, not gospel*. **A builder never gets to grade its own work.** So
before you continue it, independently verify all of it, from start to finish, against the real
artifacts — not against anyone's claims (including this doc's). Spin up fresh-context sub-agents to do
the auditing so you're not anchored on the prior trajectory.

Concretely, you must explore **all** of: **every `.md` under `.planning/` (and its subfolders)** — the
lists below are the priority reading order, NOT the complete set, so don't stop at the named files; the
**full current state of the code**; the **entire git commit history** of this repo; the **original
internal repo** at `~/dev/biolm-modal`; the **live R2 bucket** structure + contents; and the **live Modal
environments** via the `modal` CLI. In roughly this order:

1. **The original task definition** (READ THESE FIRST — they're what defined the whole project; review
   every commit and decision against them):
   - `.planning/00_MASTER_PLAN.md` — the master plan (start here).
   - `.planning/03_WORKSTREAMS.md` — the W1–W17 workstream breakdown (the original scope).
   - `.planning/02_MODEL_INCLUSION_MATRIX.md` — which models ship vs are excluded, and *why*.
   - `.planning/04_TESTING_STRATEGY.md` — the T0–T3 testing tiers + golden-fixture strategy.
   - `.planning/01_INVESTIGATION_FINDINGS.md`, `.planning/W4_ACQUISITION_PLAN.md`,
     `.planning/W5_HARDENING_GUIDE.md`, `.planning/COMMONS_REQUESTS.md` — the deeper design docs.
   - `.planning/reviews/round-1/` — the independent multi-agent review that shaped the work.
     **⚠️ STATUS: this is largely HANDLED, not open. The review itself and its Phase-A + Phase-B fix
     campaigns were completed stages ago (~529 findings triaged + fixed). Read this tree for
     provenance/context — do NOT treat it as an open TODO list, and do NOT re-do fixes that already
     landed.** The only still-live remnant is `PHASE_B_DEFERRED.md`, and even most of *that* was closed
     last night by the schema-standardization pass (`#5`) and the strict-mypy pass. Cross-referencing
     `PHASE_B_DEFERRED.md` against current reality:
       - **§A response-shape renames** — mostly DONE via `#5`, but under `field_glossary.yaml` names that
         *diverge* from what the doc proposed (e.g. it suggested `rescoding→per_token_embeddings`; `#5`
         landed `→residue_embeddings`; `temberture prediction→score` not the doc's wording). Genuinely
         still open: `esm1v` predict shape (a prior pass judged `score` already canonical — reconcile
         which is right), the `igbert`/`igt5` pad-row length question, and confirming `#5`'s chosen
         canonical names are the ones you want.
       - **§B cross-model** — `*PredictLogProb*` class-name drift DONE; Tm/pLDDT convergence DONE/moot
         (all pLDDT already 0–100); **still open:** the response DTOs that inherit `RequestModel` instead
         of `ResponseModel` (deliberately deferred to deploy-verify).
       - **§C commons-scope lifts** = folded into **`#6`** (still open).
       - **§D R2-artifact / deploy-dependent rows** (sources.yaml `*_r2` placeholders, numerical
         benchmark rows, chai1 ESM-2 pre-caching) = the **Milestone-B deploy/test matrix + R2
         population** (still open).
       - **§E** = post-v1 polish (mostly deferrable).
     So the round-1 residual maps onto the SAME remaining-work buckets in §2 — treat it as *verify and
     close the small tail*, not *re-review from scratch*. Do read `README.md`, `RUBRIC.md`, `FIX_PLAN.md`,
     `DROPPED_MODELS.md`, `PHASE_B_DEFERRED.md`, and skim the per-model (`models/*.md`) + cross-cutting
     (`global/*.md`) findings so you know *why* things are the way they are.

2. **The current decision + state docs** (these supersede stale bits of the originals — trust these
   for "where we are," but *verify* them):
   - `.planning/RELEASE_ROADMAP.md` — the decision-forward resume anchor + the ⭐ open decisions.
   - `.planning/REMAINING_WORK.md` — the master open-items ledger.
   - `.planning/MILESTONE_B_PLAN.md` + `MILESTONE_B_PROGRESS.md` — the full deploy/test matrix.
   - `.planning/MAINTAINER_LAUNCH_CHECKLIST.md` — the human/legal/infra sign-offs.
   - `.planning/RENAME_TO_BIOLM_HUB.md` — the rebrand bundle (mostly executed; verify).
   - The auto-memory at
     `/Users/qamar/.claude/projects/-Users-qamar-dev-biolm-hub/memory/release-decisions-2026-07-01.md`
     and `.../project_oss_biolm_catalog.md` — the previous agent's live state + hard-won gotchas.
     Also read the Claude Code **session traces** for this project if you can — they show what the
     prior agent actually tried, what worked, and what broke (golden-io, the zsh word-split trap, the
     Modal mount-race, the mpnn/spurs fixture pattern). Learn from them instead of rediscovering.

3. **The repo itself** — `CLAUDE.md`, `PHILOSOPHY.md`, `CONTRIBUTING.md`, `README.md`,
   `FUTURE_WORK.md`, the `.claude/skills/` (`model-implementation`, `model-knowledge-base`,
   `pr-management`), the `models/`, `gateway/`, `cli/`, `tooling/`, `docs/` trees, and the **full git
   commit history** (the recent `fix(mypy)`, `test(fixtures)`, `chore(rebrand)`, `fix(release)` commits
   are last night's work — review them critically).

4. **The original internal source repo** at `~/dev/biolm-modal` — read its **`main`** branch (the
   canonical reference; the working branch `aqamar/auto-model-phase-1` is also present if you need the
   latest internal state). biolm-hub was **extracted and de-internalized** from this repo — it is the
   ground truth for the *science* of every model. Diff against it to (a) confirm fidelity — no model
   logic, weights source, or biology was dropped or corrupted in the extraction — and (b) confirm the
   de-internalization is *total*: no `biolm-modal`/`qa`/internal-host/billing/internal-URL identifiers,
   no leaked secrets, nothing internal survived into the public repo.

5. **The live Modal environments** — use the `modal` CLI (deploys target `MODAL_ENVIRONMENT=
   biolm-hub-dev`; prod is `biolm-hub`). List apps, secrets, and images. Confirm they're clean:
   the only secrets that should matter are `cloudflare-r2` + `hf-api-token`; stale ones
   (`protocols-r2-bkt`, `ngc-cli-api-key`) should be gone; idle helper/sample apps (`golden-io`,
   `esm2-8m`) can be stopped.
   **The `modal` CLI is not a one-time audit tool — lean on it throughout development and testing.**
   Modal containers can **crash-loop or fail to start SILENTLY**: a deploy can report success, and a
   call can error/hang/return nothing, with no obvious cause — the ONLY reliable signal is the container
   logs. After every deploy, and any time a model behaves oddly, run `modal app logs <app> --env
   biolm-hub-dev` (and `modal app list --env …`) to check container health. Never infer a model is
   healthy from a successful deploy, an HTTP status, or a `curl`. **Concrete lead to chase now:** `esm1v`
   appears to be crash-looping — *"Containers in app.ESM1vModel.* are repeatedly failing to start. As a
   result, function calls are currently unable to run."* — start by reading its container logs.

6. **The live R2 bucket** (`biolm-public`, credentials in the `cloudflare-r2` Modal secret; there's a
   deployed `golden-io`/`r2_fixtures`/`r2_delete` helper pattern under `scratchpad/` you can reuse, or
   write your own Modal function). **It must become public-ready**: audit the entire `biolm-hub/`
   prefix and the bucket root. Today there is known cruft to remove — legacy `biolm-hub/models/`
   (~255 GB, pre-relayout), `model-store/` (~34 GB), possibly a `tempro/` leftover, and partial/corrupt
   weight caches (the prior agent hit one on `mpnn`). Public-ready means: **clean, organized, zero
   stale/intermediate/partial files, zero dropped-model or non-redistributable weights, zero raw
   third-party PDFs.**

Only after you've built your own accurate picture should you continue the work.

---

## 2. Where things actually stand (verify all of this — don't take it on faith)

**Done + committed + pushed (CI green):**
- 36 SHIP models + `dummy` (dropped `tempro` all-rights-reserved, `pro1` Meta-Llama, `peptides`,
  `clean`, `boltz`, `rfd3`, `esmstabp` — do NOT re-add without resolving their license).
- Full rebrand: repo `biolm-models`→`biolm-hub`, CLI `bm`→`bh`, Modal envs `biolm-hub{,-dev}`.
- R2 uniform layout constants → `biolm-hub/{model-weights,test-data,model-cache}/models/<slug>` (the
  `#9` change; **validated live** — esm2 self-populated weights at the new path).
- Schema standardization (`#5`): response-field/class renames converged to the glossary.
- Licenses (esmc/igbert/igt5 → MIT) + contacts (`support+security@` / `support+conduct@`).
- **Golden fixtures: 36 of 36 models generated** into `biolm-hub/test-data/models/<slug>/` (every
  model's `fixture.py` now produces self-contained inputs; structure models fetch a canonical PDB).
  The 11 heavy models that a process-restart had interrupted (esm2, rf3, boltzgen, evo, evo2, esmfold,
  chai1, immunebuilder, immunefold, antifold, esm_if1) were **re-generated and confirmed present** — a
  full R2 enumeration shows all 36 model dirs with plausible-complete counts (2–28 files each).
  ⚠️ **These goldens are UNREVIEWED and unvalidated**: no `pytest models/<m>/test.py -m integration`
  round-trip has been run against them yet (that's Milestone-B / bar #2). Generated via the deployed
  `golden-io` writer + `scratchpad/gen_goldens.py <slug>` (routes R2 writes through Modal so no local
  creds are needed). **mpnn** (28 files) and **spurs** (8) are present but their `fixture.py` still
  reach out (mpnn fetches a PDB from RCSB; spurs reads a TSHR260 CIF that must exist in R2) — verify
  those two regenerate cleanly from a truly empty R2 before trusting them.
- **mypy `--strict` = 0 across the whole tree (343 files) and is now a BLOCKING CI gate.** ~1,236
  errors were paid down; strict mode surfaced and fixed several real latent bugs.

**NOT done (this is your work — but re-scope it yourself against §1, don't just trust this list):**
- **chai1** build reliability — it *previously* failed to build ("dockerfile has no stages and cannot
  be built"), but on the re-run it **did build and generated 4 fixtures**. So the bug is **intermittent**
  (smells like a build-cache / layer-ordering race), not a hard block. Reproduce it, find the root cause,
  and make chai1's build deterministic before you trust its goldens.
- **The full deploy + integration/deployment test matrix** (`Milestone B`, at the *final* state) — the
  prior agent only proved self-population on a sample. Deploy ALL 36 to `biolm-hub-dev`, cold-start
  invoke every action, and make `pytest models/<m>/test.py -m integration` pass against the goldens
  for every model. Goldens must be *reviewed*, not blindly trusted.
- **`#6` commons follow-ups** (COMMONS_REQUESTS): sadie gateway-serialization; `decorator.py`
  partial-payload de-dup — runtime-path changes that need a representative deploy-verify.
- **R2 public-ready cleanup** (see §1.6) + the credential-less read path live-validated on a real
  deploy (the r2.dev anonymous read).
- **A dedicated `.claude/skills/` sprint.** Do a thorough, standalone assessment of the checked-in agent
  skills (`model-implementation`, `model-knowledge-base`, `pr-management`). They are the *agent-first
  onboarding* — the entire "an agent that learns one model can add the next one in house style" promise
  rides on them — so they must be **up-to-date, clean, neat, and actually WORK.** That means: current
  with post-rebrand reality (`biolm-hub`/`bh`, the standardized schema + action-verb conventions +
  `tooling/field_glossary.yaml`, the golden-fixture generation flow, the R2 layout, the now-blocking
  strict-mypy gate); zero stale or internal references; internally consistent with `CONTRIBUTING.md` +
  `CLAUDE.md` + the `dummy` template; and **executable end-to-end**. Prove it, don't eyeball it: have a
  **fresh-context agent actually FOLLOW `model-implementation`** to add a new small model from `dummy`
  all the way through `make check` + a dev deploy + golden generation, and **follow `model-knowledge-base`**
  to author the five knowledge-graph files — if a skill can't be followed to a passing, house-style
  result, it isn't done.
- Everything still open in `RELEASE_ROADMAP.md` (⭐ decisions), `REMAINING_WORK.md`,
  `MAINTAINER_LAUNCH_CHECKLIST.md`, and `reviews/round-1/PHASE_B_DEFERRED.md`.
- **W-launch**, all of it *except* the two irreversible steps (see house rules).

---

## 3. House rules (never cross these — no matter how you reach the goal)

- **Uniformity is the product.** Closed action-verb set (`predict`/`fold`/`encode`/`generate`/`score`/
  `log_prob`). Uniform schema field names across families — the biology lives in metadata/tags, never
  in field names. Every schema field carries a `Field(..., description=...)` matching
  `tooling/field_glossary.yaml`. When you rename a field, preserve the old name via a Pydantic alias.
- **`make check` and `make docs` (mkdocs `--strict`) are green before any push**, and **mypy `--strict`
  stays at 0** (it's blocking now — do not regress it, do not silence it with blanket ignores; every
  `# type: ignore` is error-code-specific with a reason). ruff + black clean.
- **Structured logging only; typed errors only** (raise a typed user error for caller mistakes; never a
  bare `ValueError`). Never log secrets or full sequences.
- **Credentials live only in Modal secrets** (`cloudflare-r2`, `hf-api-token`). Never commit creds. The
  public bucket is anonymously readable → **no raw third-party PDFs, no non-redistributable weights**
  (the dropped models exist for legal reasons — respect that).
- **Don't hard-code special cases.** Describe the behavior and let the model/config handle it. Don't
  over-engineer.
- **The builder never grades itself.** Every substantive change is verified by a *separate,
  fresh-context* Fable sub-agent pointed at the **real artifact** — the actual endpoint response, the
  actual R2 listing, the actual `mkdocs` output, the actual mypy/test run — and told to *prove it's not
  done*. Only merge on that evidence.
- **These require me (the human) — do not do them autonomously:** rewriting/nuking git history;
  flipping the repo public; deleting the large R2 legacy trees without my explicit go; deleting
  workspace-shared Modal secrets; any *production* (`biolm-hub`) deploy. Everything else — dev deploys,
  golden regen, R2 cache cleanup of clearly-partial/corrupt entries, code, docs — **make the call
  yourself.**

---

## 4. The bar for "done" (concrete — check yourself against this, not against "looks good")

Don't stop at your own idea of good enough. You're done only when a fresh-context auditor can verify
**all** of these against reality:

1. **All 36 SHIP models + dummy deploy to `biolm-hub-dev` and cold-start-invoke correctly for every
   action**, from a **credential-less checkout** (only Modal auth) — weights self-populate R2 at
   `biolm-hub/model-weights/models/<slug>`. Proven by an agent that *actually deploys, reads
   `modal app logs` to confirm containers are healthy (not crash-looping), and hits every endpoint* —
   not by reading code and not by trusting a green deploy or a 200. (chai1's build bug fixed; `esm1v`'s
   crash-loop resolved.)
2. **Every model has reviewed golden fixtures in R2, and `pytest models/<m>/test.py -m integration`
   passes for all 36** against them.
3. **`make check` (style + blocking mypy=0 + schema-docs + scripts + unit) and `make docs` are green;
   CI is green;** gitleaks finds nothing.
4. **R2 `biolm-public` is public-ready**: under `biolm-hub/` there is only `model-weights/models`,
   `test-data/models` (+ `shared`), and `model-cache/models`; **no** `model-store/`, **no** old
   `biolm-hub/models/`, **no** partial/corrupt caches, **no** dropped-model or non-redistributable
   weights, **no** raw PDFs. A fresh-context auditor enumerates the whole bucket and finds zero cruft.
5. **De-internalization is total**: a fresh agent greps the tree and diffs against `~/dev/biolm-modal`
   and finds zero internal identifiers and zero leaked secrets.
6. **The `MAINTAINER_LAUNCH_CHECKLIST` is fully satisfied**, the docs site renders every model
   correctly, the **five-minute quickstart actually works** end-to-end from a clean checkout with only a
   Modal account, and **the `.claude/skills/` are current, clean, and verified-working** — a
   fresh-context agent can follow `model-implementation` (add a model from `dummy` → `make check` +
   deploy + goldens) and `model-knowledge-base` (author the 5 KG files) to a passing, house-style result.
7. **Everything in `REMAINING_WORK.md` / `PHASE_B_DEFERRED.md` is either done or explicitly, defensibly
   reclassified as post-v1** (with the reason written down).
8. **W-launch is staged and one step from go** — every prerequisite done, the two irreversible steps
   (nuke history, flip public) documented and ready for me to trigger.

For anything without an obvious test ("is the bucket public-ready?", "does a new user succeed in 5
minutes?"), **invent the measuring stick and hand it to a fresh sub-agent** — e.g. have it run the
quickstart from a clean clone, or enumerate the bucket and judge it against rule #4. Whatever *builds*
a thing never *grades* it.

---

## 5. How to run it

This is a big, months-defining foundation, so treat it like the engineering-team pattern:

- **Plan first, and ask me EVERYTHING that's ambiguous or undecided — up front, in one batch (the one
  time you pause).** Before writing code, read §1 fully, then produce a plan and surface **every** open
  question, ambiguity, or unmade decision you hit while auditing — not just the ones I've pre-listed.
  The pre-listed ones are *examples*, not the full set: the ⭐ open decisions in `RELEASE_ROADMAP.md`
  (incl. its reconciliation banner), the `MAINTAINER_LAUNCH_CHECKLIST` sign-offs (license confirmations,
  real contact inboxes, prod-deploy yes/no, R2-cleanup scope + go-ahead on the big deletes, the chai1
  approach, final env/prod-rename timing). Beyond those, if anything is genuinely undecided or you could
  reasonably go two ways on something **consequential or hard to reverse** (a schema/naming call, what
  counts as public-ready, scope/priority, a cost/risk tradeoff, a model's inclusion or licensing) —
  **put it in the up-front batch and ask; do not silently guess.** Ask everything at once so I can answer
  in one pass. (Trivial, reversible choices you should just make — see §6; don't pester me on those.)
  Once the plan and answers are settled, **run without stopping** except for the §3 human-only items.
  If a *new* genuinely-blocking ambiguity surfaces mid-run, batch it and ask rather than guess on
  something consequential.
- **Then fan out.** Run several Fable sessions in parallel pulling from a task list (deploy-and-verify
  each model is naturally per-model; so is auditing each review finding). Each session triple-checks
  its own work with fresh-context sub-agents and produces evidence (the real endpoint output, the real
  R2 listing). One integrator Fable keeps everything green — merges, runs `make check` + `make docs`,
  tests like a real user, and never lets mypy/tests/docs go red.
- **Loop against the bar.** Build → have a fresh agent try to prove it's *not* done → close the biggest
  gap → repeat. You don't get to declare victory; §4 does. Keep going until a fresh auditor can't find
  a gap.
- **Post progress somewhere I can watch** (keep `REMAINING_WORK.md` or a running status doc updated
  with what's green, what's left, and the evidence) so I can glance and redirect.

## 6. Get out of your own way

- Modal auth is configured; deploy with `MODAL_ENVIRONMENT=biolm-hub-dev`. R2/HF creds are in the
  Modal secrets — for **local** golden writes use the deployed-Modal-function pattern
  (`scratchpad/golden_io.py`) so no creds ever touch the shell. `scratchpad/` is gitignored session
  tooling (helpers for R2 list/cat/delete + golden gen are already there — reuse or replace them).
- **Real Modal spend is authorized** for dev deploys, golden generation, and validation. Be
  cost-aware (idle apps scale to $0; run ~6–8 concurrent, not 40), but **don't ask permission per
  deploy** — you have the budget, just spend it sensibly.
- Known traps the prior agent already paid for (don't repeat them): the shell is **zsh** — `for x in
  $VAR` doesn't word-split (use literal lists); **never edit anything under `models/` while a Modal
  build is running** (it aborts the build); write logs to a stable path, not the session tmp dir.
- **Modal fails SILENTLY.** Containers crash-loop / fail to start with no signal in the deploy output or
  the HTTP layer — a "successful" deploy and a 200 (or a hang, or a 303/000) tell you nothing about
  container health. The truth is only in `modal app logs <app> --env biolm-hub-dev`. Check logs after
  every deploy and whenever a call misbehaves; treat "green deploy" as unverified until the logs and a
  real invocation confirm it. (`esm1v` looks like it's crash-looping right now — chase it via its logs.)
- Only come back to me when you're **truly blocked**, or for a §3 human-only decision. Otherwise, make
  the call — your judgment on the "how" is the whole point.

Start with §1. Verify everything. Then take it home.
