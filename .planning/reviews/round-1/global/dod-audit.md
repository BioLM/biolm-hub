# Round-1 Review — Definition-of-Done Audit

**Dimension:** Cross-cutting Definition-of-Done audit (rubric §D + §A/§B/§C where a DoD item touches them).
**Method:** Each DoD item from `.planning/03_WORKSTREAMS.md` (the 12-item launch checklist, lines 323–335,
plus the per-workstream *Acceptance* criteria) verified against the actual repo state on `main` @ `263bc7c`
(`feat(W14): docs site + per-field OpenAPI schema descriptions`).

> Note: the work is paused after W14. By the **ratified sequencing** (`REMAINING_WORK.md` §SEQUENCING:
> "build ALL features first, deploy/test the full matrix LAST"), several DoD items are *deliberately* deferred
> to **Milestone B** (full deploy + golden fixtures), **W-sec** (license/secret hygiene), and **W-launch**
> (destructive launch steps). Those are reported as **not-met / partial with the deferral noted** — they are
> still genuine launch blockers, just on the planned-last path. The findings worth acting on *now* are the
> ones where a workstream is **claimed DONE but the repo contradicts the claim** (esp. F1, F2).

## Summary

Of the 12 launch-checklist DoD items: **5 fully met**, **4 partial**, **3 not-met** (two of those three are the
explicitly-deferred Milestone-B / W-launch chunks).

The repo's structural conformance is strong: **all 43 SHIP models** carry the full file set
(`config/schema/app/test` + 5-file knowledge graph + `LICENSE`) and a `modal_class_name`; `esm3`/`diamond`
excluded; `esmc-300M` ships with correct Cambrian-Open attribution; actions are the closed set; `EnhancedStringEnum`
trimmed; `TargetedBypassDetector` deleted; tests are pytest-collectable; the schema-doc checker passes for 44 models;
the bare/cached gateways and config-driven (no-AST) discovery are in place; CI is maintainer-gated; the docs site
builds 43 model pages; the bootstrap `CLAUDE.md` has been replaced by a clean public one.

Two findings contradict "done" claims and should be fixed regardless of Milestone B:
- **F1 (🔴):** `gateway/schemas/introspection.py` is a full **billing/auth/usage** schema (`BillingState`,
  `monthly_charges`, `bypass_billing`, `institute_id`, `can_access_api`, …) that is **imported nowhere** — dead
  internal code that directly violates DoD #11 ("no billing/auth/analytics references anywhere"), despite W8 claiming
  "stripped auth/billing/analytics".
- **F2 (🔴):** **14 `cli/test_kb.py` unit tests fail on a clean tree** (`typer.Exit` vs `click.exceptions.Exit`).
  These are plain unit tests with no integration marker, so the safe CI tier (`pytest -m "not integration …"`) runs
  and **fails** them — meaning DoD #1's "green in CI from a clean clone" and W11's "unapproved PR runs lint+mypy+unit
  (green)" are **false right now**.

Remaining issues are internal-reference leakage that W-sec hasn't swept yet (F3–F5), an unrecorded `esmfold2`
(F6), and a README that overclaims the credential-less quickstart (F7).

---

## DoD checklist — item-by-item

| # | DoD item (line) | Status | Evidence |
|---|---|---|---|
| 1 | W-slice gate; all SHIP models pass checklist + **green in CI from a clean clone** | **Partial** | Structural checklist ✓ (43/43 complete, `modal_class_name` set). **But** 14 `cli/test_kb.py` unit tests fail on clean tree → safe CI tier is RED (F2). Milestone-B integration/deployment + golden fixtures not run; `esmstabp` can't deploy without a manual train+upload. |
| 2 | `clone → bm setup → bm deploy esm2 → inference` in 3 commands | **Partial** | `bm setup/deploy/serve/cache/r2` all exist (`cli/`). **But** R2 anonymous public-read is **not implemented** (no `signature_version=UNSIGNED` in `models/commons/`), so a credential-less clone can't pull public weights; `README.md:32` overclaims "no credentials beyond Modal" (F7). |
| 3 | Bare + cached gateways; **both tiers off by default**; discovery config-driven (**no AST**) | **Met** | `gateway/server.py` + `gateway/server_with_cache.py`; both cache tiers gated by `BIOLM_CACHE_ENABLED` (`routing.py:132,311`); `model_discovery.py` reads `ModelFamily.modal_class_name` (no source scanning); CI guard `gateway/test_discovery.py`. (Cached gateway not yet deploy-tested → Milestone B.) |
| 4 | Web app serves catalog w/ deployed/undeployed state | **Met** | `cli/serve.py` + `gateway/catalog/`; deploy-proven on dev per ledger §4. |
| 5 | CI maintainer-gated; unapproved PRs run only lint+mypy+unit | **Met (structure)** | `ci.yml` safe tier (`permissions: contents: read`, no secrets, lint+mypy+schema-docs+ci-script-tests+unit+docs); `deploy.yml` = `pull_request_target` + `deploy-approved` label + `revoke-on-push` + `modal-dev` Environment, secrets only in `deploy-and-test`. (The "unit" leg currently fails — see F2.) |
| 6 | Public R2 serves weights + test data for **all** shipped models; no raw PDFs | **Not met (deferred → Milestone B)** | Self-population code complete; only `esm2` + 4 sample patterns deploy-proven; **golden fixtures don't exist in R2 yet**; `esmstabp` needs manual upload; anon-read not implemented. No raw PDFs in the repo ✓ (`find -name '*.pdf'` empty). |
| 7 | Canonical actions/schema/errors/logging enforced; `EnhancedEnum` trimmed; `acquisition.py` simplified; tests pytest-collectable | **Met** | Actions = closed set (no `EXTRACT_FEATURES`/`PREDICT_LOG_PROB`); error taxonomy in `commons/core/error.py`; ruff `T20` passes on `models/`; `EnhancedStringEnum(_CastableEnumMixin, StrEnum)`; `TargetedBypassDetector` deleted; `pytest --collect-only models/esm2/test.py` → 40 items; `check_schema_docs.py` → ✓ 44 models. |
| 8 | Skills ship; README-standard conflict resolved; contributor agent can add a model | **Met** | `.claude/skills/{model-implementation,model-knowledge-base,pr-management}`; README conflict resolved (template points to `models/dummy/README.md`). |
| 9 | Docs site builds; every model has a page; PHILOSOPHY/CONTRIBUTING/SECURITY/LICENSE/FUTURE_WORK present; mypy enforced | **Met** | `site/models/` has 43 model pages + index (`dummy` correctly excluded); all top-level docs present; `mypy` in `Makefile` (`make mypy`/`check`) + `ci.yml`. |
| 10 | esm3/diamond excluded; esmc-300M Cambrian-Open; esmfold2 merged-or-recorded | **Partial** | esm3/diamond absent ✓; `esmc/LICENSE` + `sources.yaml` carry Cambrian-Open "Built with ESM" attribution, 600M excluded ✓. **esmfold2 is neither shipped nor recorded in `FUTURE_WORK.md`** (only in internal `REMAINING_WORK.md`, which is deleted at launch) — F6. Many per-model LICENSEs carry inferred holders/years (W-sec open). |
| 11 | **No billing/auth/analytics/internal-domain references anywhere** | **Not met** | `gateway/schemas/introspection.py` = dead billing/auth schema (F1); `biolm-modal` in 12 shipped locations incl. CLI help branding + a functional bucket constant (F3); `# Force deploy to "qa"` in 30 model `app.py` (F4); "Django host" in commons (F5). |
| 12 | Bootstrap `CLAUDE.md` deleted+replaced; `.planning/` removed; git history nuked (W-launch) | **Partial** | Public `CLAUDE.md` authored & clean (no `biolm-modal`/`.planning`/porting refs) ✓ (W14). `.planning/` still present + git history not nuked — owned by **W-launch** (not yet run; expected). |

---

## Findings by severity

### 🔴 F1 — Dead billing/auth/analytics schema still in the shipped gateway (DoD #11)
- **Category:** internal leakage / dead code
- **Location:** `gateway/schemas/introspection.py` (whole file; e.g. `:21` `BillingState`, `:31` `IntrospectionBillingState`, `:38` `bypass_billing`, `:4-7` `IntrospectionUser{username,company_id,environment_id}`, `:11-13` `IntrospectionAuthorization{can_access_api}`)
- **Detail:** The file defines a complete user/auth/usage/**billing** introspection model — `monthly_charges`, `lifetime_charges`, `bypass_billing`, `payment_past_due_or_canceled`, `rate_limit_per_minute`, `institute_id`, `allowed_models`. It is **imported nowhere** (`grep -rn "gateway.schemas\|Introspection\|BillingState" gateway/ cli/` returns only the file itself). W8's ledger entry claims "Stripped auth/billing/analytics/state (−1.8k LOC)", and `gateway/{server,config,routing}.py` advertise "no auth, no billing, no analytics" in prose — but this schema directly contradicts DoD #11's "No billing/auth/analytics references anywhere." It would ship as-is.
- **Fix:** Delete `gateway/schemas/introspection.py` (and the now-empty `gateway/schemas/` package if nothing else lands there). If any field is genuinely needed later, re-add it without the billing/auth concepts.

### 🔴 F2 — Safe CI tier is red: 14 `cli/test_kb.py` unit tests fail on a clean tree (DoD #1, W11)
- **Category:** correctness / CI green
- **Location:** `cli/test_kb.py` (`TestLoadSources`, `TestValidateCmd`); source under test `cli/kb.py`
- **Detail:** `pytest cli/test_kb.py` → **14 failed, 47 passed** on a clean checkout (`typer.Exit` raised vs `click.exceptions.Exit` expected — a typer/click version mismatch). These tests carry no integration/deployment marker, so the safe-tier selector in `ci.yml` (`pytest -m "not integration and not deployment and not slow and not e2e and not live_modal"`) collects and **fails** them. That makes DoD #1's "**green in CI from a clean clone**" and W11's acceptance ("unapproved external PR runs only lint+mypy+unit" — implicitly green) **false today**. The ledger acknowledges it as "pre-existing, fix in W17", but W17 is marked done and the failure persists.
- **Fix:** Reconcile the typer/click handling in `cli/kb.py`/tests (catch `click.exceptions.Exit` or pin compatible `typer`/`click`), then confirm `make check` is green end-to-end. This is mechanical but it gates "CI green."

### 🟠 F3 — `biolm-modal` internal identifier leaks in shipped code, incl. CLI help branding + a functional bucket constant (DoD #11, rubric §C)
- **Category:** internal leakage
- **Location:** `cli/main.py:16,18,47` ("BioLM-Modal Command Line Interface" / "BioLM-Modal is a platform…" — renders in `bm --help`); `models/esmstabp/_train.py:72` (`R2_BUCKET = "biolm-modal"` — a *functional* hardcoded internal bucket); `models/esmstabp/download.py:8`; `models/dummy/sources.yaml:106`; `models/commons/storage/cache.py:48`; `models/deepviscosity/fixture.py:18`; `models/boltz/fixture.py:16`, `models/boltz/test.py:112,138`
- **Detail:** 12 references to the internal repo/bucket name `biolm-modal` survive in shipped files. Most are comments/path examples, but two matter more: `cli/main.py` puts "BioLM-Modal" in the **user-facing CLI help text**, and `esmstabp/_train.py` hardcodes the internal bucket as a live constant. The ledger §3 lists most of these as "still open (functional path-strings)" for W-sec — but **`cli/main.py` is not on that list** (newly surfaced here) and is the most visible one.
- **Fix:** W-sec sweep `biolm-modal` → `biolm-public` across shipped files; re-brand the CLI help to the public name; replace the `_train.py` constant with the parameterized bucket (`BIOLM_R2_BUCKET`, default `biolm-public`).

### 🟠 F4 — Internal `qa` environment name in 30 model `app.py` files (DoD #11)
- **Category:** internal leakage
- **Location:** 30 files, e.g. `models/esm2/app.py:484`, `models/igbert/app.py:427`, `models/zymctrl/app.py:363`, `models/abodybuilder3/app.py:287` — the comment `# Force deploy to "qa" or "main" environment:` in each `__main__` usage block
- **Detail:** The rubric explicitly enumerates the internal `qa` env as a leak. It appears verbatim in 30 shipped model files as boilerplate copied from the internal repo's deploy snippet. The public environments are `biolm-models` / `biolm-models-dev`, not `qa`/`main`.
- **Fix:** Replace the boilerplate comment with the public env names (or drop the env-specific comment) across all model `app.py` files — best done as one mechanical W-sec/de-internalization pass.

### 🟠 F5 — Internal "Django host" architecture reference in commons (DoD #11)
- **Category:** internal leakage
- **Location:** `models/commons/data/serializer.py:169`
- **Detail:** Comment reads "…available on the caller side (e.g. ``training.*`` on the Django host)…" — leaks the internal platform architecture (a Django host + `training.*` modules) into shipped commons code.
- **Fix:** Reword the comment to describe the behavior generically without naming the internal host/modules.

### 🟠 F6 — `esmfold2` is neither shipped nor recorded in `FUTURE_WORK.md` (DoD #10)
- **Category:** documentation gap / plan conformance
- **Location:** `FUTURE_WORK.md` (no mention); `models/` (no `esmfold2/`)
- **Detail:** DoD #10 requires esmfold2 to be "either merged-upstream-and-shipped **or recorded in `FUTURE_WORK.md`**." It is unshipped and only tracked in the internal `REMAINING_WORK.md`, which is deleted at launch — so post-launch there will be **no public record** of the deferral. (W-launch step 5 is supposed to record it, but FUTURE_WORK is the public artifact and is empty of it now.)
- **Fix:** Add an esmfold2 entry to `FUTURE_WORK.md` (ship-after-upstream-PR, re-confirm weights/ESMC-6B-backbone license), or ship it once the upstream PR merges.

### 🟠 F7 — README overclaims credential-less quickstart; R2 anonymous read not implemented (DoD #2, rubric §C docs)
- **Category:** documentation accuracy / public contract
- **Location:** `README.md:31-32` ("Public model weights are pulled from a read-only bucket by default, so the happy path needs no credentials beyond [Modal]"); gap in `models/commons/` (no `signature_version=UNSIGNED` path)
- **Detail:** There is no unsigned/anonymous R2 read path in commons, so a credential-less clone deploying `esm2` still needs the `cloudflare-r2` secret to read public weights (the ledger §4 purple item confirms this blocked Milestone-A esm2). The README states the opposite as the happy path. This breaks DoD #2's "fresh machine, three commands" promise and is a doc-accuracy bug an external user will hit immediately.
- **Fix:** Implement the unsigned-read path in the commons R2 client (and enable anonymous reads on the bucket) — then the README is true; **or** soften the README to state Modal *and* read creds are needed until the public-read bucket lands. Track the chosen path in W4/W3b.

### 🟡 F8 — Milestone-B / W-launch deferrals (DoD #1, #6, #12) — informational
- **Category:** plan conformance (deferred by ratified sequencing)
- **Location:** `.planning/` (still present), git history (not nuked), R2 golden fixtures (don't exist), `models/esmstabp/_train.py` (manual one-time train+upload required)
- **Detail:** These are genuine launch blockers but are on the **planned-last** path (Milestone B for full deploy + golden fixtures + R2 population; W-launch for `.planning/` deletion + history nuke). Flagged so the audit is complete, not because they're off-track. Note the `esmstabp` hard dependency on a manual maintainer step before it can ever deploy — make sure that's tracked into Milestone B and called out in its docs.
- **Fix:** Execute Milestone B then W-launch per `REMAINING_WORK.md` §1/§4; ensure the esmstabp manual step is in the Milestone-B runbook.

### 🟡 F9 — `dummy` template missing `comparison.yaml` (and `LICENSE`) (rubric §A, minor)
- **Category:** template completeness
- **Location:** `models/dummy/` (no `comparison.yaml`, no `LICENSE`)
- **Detail:** The template is the canonical "copy this to start a model," and the 5-file knowledge graph includes `comparison.yaml`; its absence means a contributor copying `dummy/` won't get a `comparison.yaml` stub to fill in. (LICENSE absence is fine — the template shouldn't dictate a license.) Not a shipped model, so excluded from the docs site correctly.
- **Fix:** Add a minimal annotated `comparison.yaml` stub to `models/dummy/` so the template mirrors the required KG file set.

## Verification

Adversarial re-check of the seven HIGH-severity findings against the actual code (attempted to refute each):

1. **Dead billing/auth/analytics schema in gateway** — **REAL.** `gateway/schemas/introspection.py` is git-tracked and is a full billing/auth/usage model (`BillingState`/`IntrospectionBillingState`/`bypass_billing`/`monthly_charges`/`allowed_models`); grep across `gateway/ cli/` finds zero importers (only the file itself). Gateway prose at `config.py:3`, `server.py:6`, `routing.py:12` advertises "no auth/billing/analytics" — the dead schema directly contradicts it and DoD `03_WORKSTREAMS.md:334` ("No billing/auth/analytics... references anywhere").

2. **Safe CI tier red — 14 cli/test_kb.py failures** — **REAL.** Reproduced on clean tree: `uv run pytest cli/test_kb.py` → 14 failed, 47 passed (typer.Exit vs click.exceptions.Exit). The safe-tier selector (`ci.yml:47`, `-m "not integration and not deployment and not slow and not e2e and not live_modal"`) collects all 61 tests (no markers on these tests), so CI goes red. The authors' own ledger (`REMAINING_WORK.md:148-150`) confirms the 12+ failures and defers to W11/W17, but W17 is marked done; breaks DoD `03_WORKSTREAMS.md:323` "green in CI from a clean clone".

3. **biolm-modal leaks incl. functional bucket constant** — **REAL (one sub-claim inaccurate).** `cli/main.py:16,18,47` and `models/esmstabp/_train.py:72` (`R2_BUCKET = "biolm-modal"`, a live functional constant) plus the other 6 cited files all exist and are git-tracked; ledger §3 (`REMAINING_WORK.md:101-103`) lists the others but NOT `cli/main.py`. RUBRIC:9,59 enumerates `biolm-modal` as a must-fix leak. CAVEAT: the "renders in `bm --help` branding" sub-claim is FALSE — `bm --help` shows the `typer.Typer(help=...)` string ("BioLM command-line tools..."), the callback docstring at `:47` does not render top-level. Core DoD #11 leak (incl. the functional constant) stands regardless.

4. **Internal 'qa' env in 30 model app.py files** — **REAL.** Exactly 30 `app.py` files contain `# Force deploy to "qa" or "main" environment:` (e.g. `esm2/app.py:484`, `igbert/app.py:427`, `zymctrl/app.py:363`, `abodybuilder3/app.py:287`). RUBRIC:9,59 explicitly enumerates `qa` as an internal-reference leak; DoD `:334` "internal-domain references anywhere".

5. **'Django host' architecture leak in commons** — **REAL.** `models/commons/data/serializer.py:169` reads "...not available on the caller side (e.g. ``training.*`` on the Django host)..." — leaks internal platform architecture into shipped, git-tracked commons code.

6. **esmfold2 unshipped and absent from public FUTURE_WORK.md** — **REAL.** No `models/esmfold2/` (only `esmfold` v1); `FUTURE_WORK.md` lists 4 items, none esmfold2; the only record is internal `REMAINING_WORK.md:229` (deleted at launch). Violates DoD `03_WORKSTREAMS.md:333` ("esmfold2 either merged-upstream-and-shipped or recorded in `FUTURE_WORK.md`").

7. **README overclaims credential-less quickstart; R2 anon read unimplemented** — **REAL.** `models/commons/storage/r2.py:86-93` always builds the client from `AWS_ACCESS_KEY_ID`/`AWS_SECRET_ACCESS_KEY` env vars; grep for `UNSIGNED`/`signature_version`/`anonymous` in commons → no match (exit 1). README.md:32 claims "the happy path needs no credentials beyond Modal." The authors' own ledger (`REMAINING_WORK.md:151-160`) states this is "**not yet true**" and that the missing secret "blocked Milestone A's esm2 deploy." HF/CDN fallback does not refute it — the download layer requires the R2 secret to even attempt the read. Breaks DoD `:325` three-command fresh-machine promise.

**Net:** 7/7 real. Only inaccuracy found in adversarial review is finding 3's "renders in `bm --help`" embellishment (the callback docstring does not surface in top-level help); the underlying internal-identifier leak and functional bucket constant it cites are demonstrable, so the DoD #11 verdict is unaffected.
