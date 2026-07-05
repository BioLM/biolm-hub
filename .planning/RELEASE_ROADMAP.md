# ▶▶ READ FIRST — Release Roadmap & Your Decisions (resume anchor)

> ## 🔄 STATUS RECONCILIATION — 2026-07-05 (added post-overnight; trust THIS for "what's done")
> Everything below is a **2026-07-01 mid-project snapshot** — read it for rationale and the ⭐ decision
> framing, but for *current status* trust this banner + `.planning/FABLE_HANDOFF.md`.
>
> **DONE since 2026-07-01:** catalog trimmed to **36 SHIP + dummy** (dropped `tempro` + `pro1`;
> peptides/clean/boltz/rfd3/esmstabp already out) · full **`biolm-models`→`biolm-hub` + `bm`→`bh`
> rebrand** · **R2 uniform re-layout** to `biolm-hub/{model-weights,test-data,model-cache}/models/<slug>`
> (validated live on esm2) · **schema standardization (#5)** · **licenses** esmc/igbert/igt5→MIT +
> **contacts** `support+security@` / `support+conduct@` · **golden fixtures generated for 35/36 models**
> (only `chai1` missing — a Modal image-build bug) · **`mypy --strict` = 0 across 343 files and now a
> BLOCKING CI gate** (the ~1236-error debt is paid down). CI is green.
>
> **⚠️ The TL;DR below that says "Milestone B is DONE / 38 models" is STALE** — that was a sample/first
> pass. A **full 36-model deploy + integration/deployment matrix at the final state is still OWED.**
>
> **⭐ Decision status:** D1 tempro = DROPPED ✓ · D3 pro1 = DROPPED ✓, esmc/igbert/igt5 = MIT ✓ (**still
> need you:** prody's transitive OpenBabel GPL-2.0 + the inferred per-model copyright holders) · D4
> contacts set ✓ (**confirm** the inboxes route to a human) · D5 rebrand DONE, goldens 35/36, prod-deploy
> still optional · D6 peptides = stay dropped ✓ · **still need you: D2** (Modal CI token + `deploy-approved`
> gate on a `modal-dev` GitHub Environment) and **D8** (verify no raw PDFs in the now-public bucket +
> delete the stale `protocols-r2-bkt`/`ngc-cli-api-key` secrets + green-light the big legacy-R2 cleanup).
>
> **Still-open engineering:** `chai1` build fix · `#6` commons (sadie serialize, decorator de-dup,
> seed_everything lift) · the **full deploy/test matrix** · **R2 public-ready cleanup** (legacy
> `biolm-hub/models/` ~255 GB + `model-store/` ~34 GB + partial caches) · **W-launch** minus the two
> irreversibles (nuke history, flip public).

**Authoritative as of 2026-07-01 (session `oss-w3b-wsec`).** Supersedes stale items in the older `.planning`
docs. Read THIS first, make the decisions in the ⭐ section, then tell me "go" on the code work.

## TL;DR — where we are
**Milestone B is DONE.** All **38 SHIP models + `dummy`** deploy AND cold-start-runtime-validated on Modal
**dev** (`biolm-models-dev`), on the new **`biolm-public/biolm-hub/models/...`** R2 path. 9 real port-drift bugs
found + fixed. Codebase green (ruff/black/schema✓/tests). The catalog actually runs end-to-end now — which was
never true before. What's left to a public flip = **your decisions + a bounded, well-understood set of tasks.**
Nothing is a framework flaw. Detail lives in `.planning/MILESTONE_B_PROGRESS.md` (validation log) and the
per-topic docs (`RENAME_TO_BIOLM_HUB.md`, `MAINTAINER_LAUNCH_CHECKLIST.md`, `reviews/round-1/PHASE_B_DEFERRED.md`).

---

## ⭐ DECISIONS FOR YOU — ordered by importance
For each: **the decision · YOUR ACTION · MY RECOMMENDATION.**

### D1 · 🔴 tempro license — the one real legal risk (highest)
- **Decision:** tempro's upstream ships **no license** (`license: null` → all-rights-reserved). It self-populates
  its weights into the public `biolm-public` bucket = **redistributing all-rights-reserved weights.**
- **YOUR ACTION:** pick one — (a) accept the risk, (b) email the author (github.com/Jerome-Alvarez/TEMPRO) for
  permission/relicense, or (c) **drop it from v1** like peptides.
- **MY REC:** **(c) drop for v1** (clean `git rm` + revert; re-include when resolved) — or (b) if a quick yes is
  likely. This is the single clearest legal exposure in the catalog and mirrors the peptides call. If you drop
  it, I also remove the tempro→esm2 cross-app dependency note. ~30 min of work.

### D2 · 🟠 Infra: Modal CI token + deploy-gate (unblocks CI-driven + prod deploys)
- **Decision:** provision the GitHub-side secrets + the maintainer deploy gate.
- **YOUR ACTION:** in the repo's GitHub settings, create a **`modal-dev` Environment** and add **Environment
  secrets**: `MODAL_TOKEN_ID` + `MODAL_TOKEN_SECRET` (same values as the internal `biolm-modal` repo) +
  `R2_ACCESS_KEY_ID` / `R2_SECRET_ACCESS_KEY` / `R2_REGION` / `R2_ENDPOINT`. Add the **`deploy-approved`** label
  + required reviewers on that Environment.
- **MY REC:** do this when you want CI-/gated-PR-driven deploys. **Not urgent** — we deploy manually to dev fine.
  Required before `deploy.yml`'s first live run + any prod deploy. ~15 min.

### D3 · 🟠 License confirmations (attribution obligations)
- **Decision:** confirm each model's license terms are correct + acceptable for a permissive catalog.
- **YOUR ACTION:** confirm — **pro1** (READ Meta's Llama-3.1 Community License — it has use-based restrictions;
  pro1 re-fetches Llama from HF per deploy, so a deployer needs an HF token with Meta terms accepted), **esmc**
  (Cambrian "Built with ESM" wording), **igbert/igt5** (CC-BY-4.0 attribution), **prody** (transitive OpenBabel
  GPL-2.0, apt-installed), + spot-check inferred copyright holders across per-model LICENSEs.
- **MY REC:** most are fine (permissive/attribution). **pro1's Llama license is the one to actually read** — if
  its restrictions are unacceptable, drop pro1 (it's the only Meta-Llama model). prody's OpenBabel is an
  apt-installed tool (mere aggregation, not vendored) → I'd **accept** it. No copyleft *model* remains
  (peptides was the only one, already dropped).

### D4 · 🟠 Public contacts (trivial but ships publicly)
- **Decision:** are `security@biolm.ai` + `conduct@biolm.ai` real, monitored inboxes?
- **YOUR ACTION:** confirm or replace `SECURITY.md:8` + `CODE_OF_CONDUCT.md:32`.
- **MY REC:** confirm they route to a human. 2 min.

### D5 · 🟡 Rebrand + prod + golden-fixture timing (sequencing)
- **Decision:** when to do the `biolm-hub` rebrand, the prod deploy, and the golden fixtures.
- **YOUR ACTION:** greenlight the sequence.
- **MY REC:** bundle **rebrand + golden fixtures** as the final pre-launch step (you already decided goldens go
  in the final-named env once bucket/env names are frozen). **Prod deploy is OPTIONAL for the repo release** —
  only needed if BioLM hosts a public inference instance; the OSS value is that users deploy to THEIR Modal.

### D6 · 🟡 peptides re-inclusion
- **Decision:** chase the peptides MIT-vs-GPL-3.0 resolution with althonos now?
- **MY REC:** leave dropped for v1; revisit post-launch (a clean revert once upstream confirms MIT).

### D7 · 🟡 Optional scope (defer)
- Round-2 verification review · W15 off-Modal Dockerfiles · esmfold2 activation (after its upstream PR merges).
- **MY REC:** defer all to post-v1 / FUTURE_WORK. The parallel-Opus Milestone-B validation already gives strong
  confidence; a Round-2 is optional insurance, not a blocker.

### D8 · 🟢 PDF-in-R2 check + secret cleanup (low urgency)
- **YOUR ACTION:** verify no raw third-party paper PDFs landed in the now-anonymously-readable `biolm-public`;
  optionally delete the unused `protocols-r2-bkt` + `ngc-cli-api-key` Modal secrets.
- **MY REC:** check when you next have R2 access.

---

## ✅ What I can start immediately (no decision needed — just say "go on Phase A")
All Modal-free or dev-deploy-verifiable:
1. **Fix abodybuilder3 `plddt=True` (a real latent 500)** + apply the **response-shape renames** (ablang2, esm1v,
   temberture, igbert/igt5, omni_dna) with Pydantic aliases, re-deploy the affected models on dev, log-verify.
2. **Small build/watch-item fixes:** rf3 `n_recycles ge=2`, evo2 dead R2-only branch, e1 `cu11.8`→`cu12.4`,
   sadie `pip`→`uv`.
3. **Cross-model polish:** Tm/pLDDT field convergence (0–100), `*PredictLogProb*` class-name drift, response
   DTOs inheriting the wrong base.
4. **Commons follow-ups (with a representative dev deploy):** sadie gateway-serialize; `decorator.py`
   partial-payload de-dup.
5. **Reconcile the stale `.planning` docs** to reality (see below).

---

## Full ordered release path (recap)
- **Phase A — Finish the code** (me; Modal-free/dev-verifiable) — the list above.
- **Phase B — Infra + activate creds-less path** (D2 you → then me: R2 secret-mount switch, live-validate the
  r2.dev anonymous read, deploy.yml first gated-PR run, gitleaks first CI run).
- **Phase C — Legal/contacts sign-off** (D1, D3, D4, D8).
- **Phase D — Final `biolm-hub` env** (D5): rebrand bundle (repo create, CLI `bm`→`bh`, Modal envs; R2 prefix
  already done) + golden fixtures + optional prod deploy + cached-gateway/deployed-catalog deploy-tests.
- **Phase E — W-launch (irreversible, ordered):** final R2 completeness sweep + security sign-off → confirm the
  permanent public `CLAUDE.md` → **delete `.planning/`** → **nuke git history** → **flip public** (gated on
  marketing being ready).
- **Deferred by design (FUTURE_WORK.md):** off-Modal Dockerfiles, ProteinGym benchmarks, self-improving skill,
  BuildKit fast builds, esmfold2.

---

## Doc-hygiene note (the older docs are partly stale)
`00_MASTER_PLAN`, `03_WORKSTREAMS`, `REMAINING_WORK §1–§4`, and `reviews/round-1/FIX_PLAN.md` mostly describe
**already-completed** work, and carry ~6 contradictions vs reality: R2 anonymous-read is DONE (some docs still
call it open), the R2 `biolm-hub/` prefix re-path is DONE (RENAME §4 + CHECKLIST §E still list it deferred),
peptides is DROPPED (a couple of Open-Questions still assume it ships). **THIS doc + `MILESTONE_B_PROGRESS.md` +
`MAINTAINER_LAUNCH_CHECKLIST.md` are authoritative.** I can reconcile the stale ones in one pass (part of Phase A).
</content>
