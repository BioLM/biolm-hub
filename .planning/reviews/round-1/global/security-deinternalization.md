# Global Review — Security & De-internalization

**Dimension:** Security & de-internalization (whole repo)
**Reviewer:** independent round-1 · **Rubric:** `.planning/reviews/round-1/RUBRIC.md` (§A.4/6, §C "No internal
leakage", §D Definition-of-Done)
**Repo state:** HEAD `263bc7c` (W14 done). `.planning/` still tracked (expected; deleted + history nuked at
W-launch).

## Summary

The hard-secret posture is clean: no hardcoded credentials, AWS keys, PEM/SSH keys, bearer/GitHub/OpenAI
tokens, `.env`/`.pem`/`modal.toml` files, local `/Users/...` paths, usernames (`aqamar`), or raw third-party
PDFs are tracked. `.gitignore` correctly excludes `.env*`. CI (`deploy.yml`) sources all credentials from GitHub
secrets and already uses the de-internalized Modal environment name `biolm-models-dev`. Root docs
(`README.md`, `CONTRIBUTING.md`, `PHILOSOPHY.md`), `mkdocs.yml`, `Makefile`, and the gateway are free of
internal identifiers. The on-disk `CLAUDE.md` is the clean **public** version (the temp bootstrap was already
replaced in W14) — no `.planning`/`biolm-modal`/porting refs in any shipped doc. No shipped file references
`.planning/`.

**But the de-internalization sweep is materially incomplete in the *model and commons code/docs*** — exactly
the two identifiers the rubric flags as launch-gating:

1. **`biolm-modal`** (internal bucket/repo name) still appears in 7+ shipped files, including one as
   **load-bearing code that also breaks self-population** (`esmstabp/_train.py`).
2. **`qa`** (internal Modal environment name) is wired into commons config + 45 shipped files. CI was migrated
   to `biolm-models-dev` but the code was **not**, so `qa` is now both an internal leak *and* functionally stale
   (`is_production()` no longer recognizes the real deploy environment).

Plus a large-surface internal-architecture leak: 63 model `MODEL.md`/`README.md` files describe an internal
"BioLM platform layer / Redis two-tier caching" that does not exist in the OSS deployment and renders into the
public docs site. REMAINING_WORK §3 already tracks the `biolm-modal`/`qa` sweep as a W-sec/W-launch item, but it
has not been executed and these are launch blockers per the rubric. W-sec's planned secret-scanning gate
(gitleaks/trufflehog) is also not yet wired into CI.

---

## 🔴 Must-fix before launch

### 1. `R2_BUCKET = "biolm-modal"` hardcoded in shipped training code — internal-name leak **and** broken self-population
- **Category:** internal leakage / correctness
- **Location:** `models/esmstabp/_train.py:72`
- **Detail:** `R2_BUCKET = "biolm-modal"` is live code (used by the upload step in
  `train_esmstabp_models`), not a comment. Two problems: (a) `biolm-modal` is the internal repo/bucket name the
  rubric lists as a 🔴 leak; (b) the deployed model reads weights from `r2_bucket_name`
  (`commons/util/config.py:9`, default **`biolm-public`**, overridable via `BIOLM_R2_BUCKET`), so the trainer
  writes to one bucket while `download.py` reads from another — self-population silently fails unless a
  contributor happens to set `BIOLM_R2_BUCKET=biolm-modal`. The model-level esmstabp review flagged the same.
- **Fix:** Import and use the canonical `r2_bucket_name` from `models.commons.util.config` instead of a local
  literal, so the trainer and downloader agree and honor `BIOLM_R2_BUCKET`. Also reconsider whether the
  `_train.py` script needs to ship at all; if it does, it must use the public bucket.

### 2. Residual `biolm-modal` references in shipped files (comments / docstrings / template)
- **Category:** internal leakage
- **Location:** `models/dummy/sources.yaml:106`; `models/commons/storage/cache.py:48`;
  `models/deepviscosity/fixture.py:18`; `models/esmstabp/download.py:8`; `models/boltz/fixture.py:16`;
  `models/boltz/test.py:112` and `:138`
- **Detail:** The rubric explicitly enumerates `biolm-modal` as a launch-gating internal-reference leak in any
  shipped file. These are R2-path comments/docstrings (`r2://biolm-modal/...`). The most dangerous is
  `models/dummy/sources.yaml:106` — **dummy is the ratified template**, so every new model copies the leaked
  name forward. `commons/storage/cache.py:48` is in central shared code. The `biolm-modal`→`biolm-public` sweep
  is tracked in `.planning/REMAINING_WORK.md` §3 but not yet executed.
- **Fix:** Replace every `r2://biolm-modal/...` with the de-internalized `r2://biolm-public/...` (or, better,
  describe the location abstractly, e.g. "the public test-data bucket under `test-data/...`"), and fix the
  template first so it stops propagating.

### 3. Internal Modal environment name `qa` leaks across commons + ~45 shipped files (and is now functionally stale)
- **Category:** internal leakage / consistency / correctness
- **Location:** canonical: `models/commons/util/config.py:82` (`qa_environment_name = "qa"`,
  `deployed_environment_names = ["qa", "main"]`); `models/commons/util/environment.py:115` and `:140`
  (docstrings); `models/commons/modal/deployment.py:35` (help text) and `:41`
  (`if current_env in ("qa", "main")`); plus the `# Force deploy to "qa" or "main" environment:` /
  `# Force deploy in QA/prod:` comment in ~30 model `app.py` files (e.g. `models/esm2/app.py:484`,
  `models/boltz/app.py:1044`, `models/evo/app.py:223`, `models/peptides/app.py:139`, ...).
- **Detail:** The rubric explicitly lists "internal `qa` env" as a 🔴 leak, and the ratified plan
  (`.planning/REMAINING_WORK.md:198`) calls for `qa→biolm-models-dev`. CI was already migrated
  (`.github/workflows/deploy.yml:60` sets `MODAL_ENVIRONMENT: biolm-models-dev`), but the code/config/docs were
  not — so this is both an internal-name leak **and** a live inconsistency: `is_production()`
  (`environment.py:136`) compares the current env to `deployed_environment_names = ["qa", "main"]`, which no
  longer contains the actual CI deploy environment `biolm-models-dev`. The production-confirmation guard in
  `run_or_deploy_modal_app` therefore won't recognize `biolm-models-dev` as a deployed environment.
  Additionally, `deployment.py:41` **hardcodes** the tuple `("qa", "main")` instead of importing
  `deployed_environment_names` from config — duplication that will drift from the canonical list.
- **Fix:** Rename `qa_environment_name = "qa"` → the de-internalized value (e.g. `"biolm-models-dev"`) in
  `config.py`; make `deployment.py` import and use `deployed_environment_names` instead of the literal
  `("qa", "main")`; update the `environment.py` docstrings; and replace the per-model deploy comments (regenerate
  from the template so all 30 are consistent). Verify `is_production()` then recognizes the real CI environment.

---

## 🟠 Should-fix

### 4. Internal "BioLM platform layer / Redis two-tier caching" architecture described in 63 docs — renders into the public site and is wrong for OSS
- **Category:** internal leakage / docs accuracy / cross-model consistency
- **Location:** 63 files (`MODEL.md`/`README.md`) across ~44 models, originating from the template
  `models/dummy/MODEL.md:252` and `models/dummy/README.md:234`; e.g. `models/evo/MODEL.md:197`,
  `models/igbert/MODEL.md:163`, `models/boltz/MODEL.md:178`, `models/abodybuilder3/MODEL.md:138`.
- **Detail:** These sections say response caching "(Redis/R2 two-tier) is handled by **the BioLM platform
  layer, not by the model container**" with "Redis (Modal Dict) caching." This describes BioLM's internal
  *hosted* production infrastructure. In this OSS repo the only caching that exists is the commons two-tier
  cache (`modal.Dict` + R2 gzip), which lives **in** the container/commons, is **off by default**, and is
  toggled by `BIOLM_CACHE_ENABLED` (`commons/util/config.py:58`) — there is no external "BioLM platform layer"
  and no Redis. So the text both leaks internal architecture and is factually false for a contributor who
  self-deploys. Worse, `MODEL.md`/`README.md` are embedded into the generated docs site
  (`docs/gen_pages.py:40` maps `README.md`→`index.md`; MODEL/BIOLOGY are embedded), so this renders publicly
  for the whole catalog. Borderline 🔴 given the public-render surface; kept 🟠 because it uses the public org
  name rather than `biolm-modal`/`qa` literally.
- **Fix:** Rewrite the template caching section to describe the actual OSS mechanism (commons `modal.Dict` +
  R2, opt-in via `BIOLM_CACHE_ENABLED`, default off) and drop "BioLM platform layer"/"Redis"; regenerate the
  per-model docs from the corrected template so all ~44 stay uniform.

### 5. Stale internal decorator names `biolm_modal_function` / `biolm_modal_endpoint`
- **Category:** internal leakage / dead reference
- **Location:** `models/commons/core/decorator.py:435` (docstring: "the biolm_modal_function decorator");
  `.github/scripts/analyze_commons_dependencies.py:94` (comment: `from models.commons.core.decorator import
  biolm_modal_endpoint`)
- **Detail:** The actual decorator is `modal_endpoint` (`decorator.py:29`). Both references name the old
  internal `biolm_modal_*` decorator, which no longer exists — so they leak the internal naming **and** are
  factually wrong (a contributor following the comment would import a non-existent symbol).
- **Fix:** Replace `biolm_modal_function`/`biolm_modal_endpoint` with `modal_endpoint` in both locations.

### 6. Internal "Django host" / `training.*` architecture leaked in a central commons docstring
- **Category:** internal leakage
- **Location:** `models/commons/data/serializer.py:169`
- **Detail:** The `serialize_model` docstring says "Any object whose class lives in a module not available on
  the caller side (e.g. ``training.*`` on the Django host)…". The OSS repo has no Django host and no
  `training.*` module — this exposes BioLM's internal production topology and is confusing to outside
  contributors, in a heavily-shared commons file.
- **Fix:** Replace the example with a generic one, e.g. "(e.g. a class defined only in the calling
  application's modules)".

### 7. Dead, internal-named Modal secrets defined in commons config
- **Category:** dead code / internal leakage
- **Location:** `models/commons/util/config.py:71-72` (`protocols_r2_bucket_secret_name = "protocols-r2-bkt"`,
  `protocols_r2_bucket_secret`) and `:77-78` (`nvidia_ngc_secret_name = "ngc-cli-api-key"`, `nvidia_ngc_secret`)
- **Detail:** Neither symbol is imported or used anywhere in the repo (verified by grep across
  `models/`, `cli/`, `gateway/`). `protocols-r2-bkt` references the internal "Protocols" product/bucket; both are
  dead `modal.Secret.from_name(...)` calls that point at internal secret names with no consumer. Dead code that
  also leaks internal secret names.
- **Fix:** Delete both unused secret definitions. (If a future model needs the NGC key, re-add it at that point.)

### 8. No secret-scanning gate in CI/pre-commit (W-sec DoD)
- **Category:** Definition-of-Done / security process
- **Location:** `.github/workflows/ci.yml`, `.pre-commit-config.yaml` (absent)
- **Detail:** `.planning/REMAINING_WORK.md` §3 lists a `gitleaks`/`trufflehog` scan (CI + pre-launch) as a
  W-sec gate. No such scan exists in CI or pre-commit today. Given this repo flips from private to public, an
  automated secret scan over the full history before launch is the safety net for exactly the kind of residual
  leakage found above.
- **Fix:** Add a gitleaks (or trufflehog) job to `ci.yml` and/or a pre-commit hook, and run a full-history scan
  as part of the W-launch checklist before flipping public.

---

## 🟡 Nits

### 9. Public contact addresses still carry "confirm before launch" placeholders
- **Category:** OSS readiness
- **Location:** `CODE_OF_CONDUCT.md:32` (`conduct@biolm.ai`), `SECURITY.md:8` (`security@biolm.ai`)
- **Detail:** Both carry `<!-- maintainers: confirm/replace this contact before launch -->`. Not a leak
  (`biolm.ai` is the org's public domain), but a public security-disclosure address must be a real, monitored
  inbox before the repo goes public.
- **Fix:** Confirm the inboxes exist/are monitored and remove the placeholder comments.

### 10. `.planning/` is tracked in git (expected, but launch-sequence dependent)
- **Category:** Definition-of-Done reminder
- **Location:** `.gitignore:38` intentionally keeps `.planning/` tracked; whole `.planning/` tree.
- **Detail:** `.planning/` (and these review files) contain the internal porting record and internal-repo paths.
  This is by design during the private phase, but the entire dir plus git-history nuke is the final
  irreversible W-launch step. No shipped file references it (verified), so the only risk is forgetting the
  deletion/history-nuke. Flagging for the launch checklist only.
- **Fix:** Ensure the W-launch sequence (`.planning/REMAINING_WORK.md:228`) deletes `.planning/` and nukes git
  history before the repo is made public.

---

## Definition-of-Done audit (security & de-internalization slice)

| Item | Status | Evidence |
|------|--------|----------|
| No hardcoded secrets / keys / tokens; no tracked `.env`/`.pem`/cred files | **MET** | grep sweeps clean; `.gitignore` excludes `.env*`; CI uses GitHub secrets |
| No raw third-party PDFs tracked | **MET** | `git ls-files` finds no `.pdf/.docx/.pptx` |
| No `.planning/` refs in shipped files | **MET** | grep clean outside `.planning/` |
| Temp bootstrap `CLAUDE.md` replaced by clean public one | **MET** | on-disk `CLAUDE.md` is public; replaced in W14 (`263bc7c`) |
| Root docs / CI / gateway free of internal identifiers | **MET** | grep clean; CI uses `biolm-models-dev` |
| `biolm-modal` removed from all shipped files | **NOT MET** | findings #1, #2 (incl. live code in `_train.py`) |
| `qa` internal env name de-internalized in code/docs | **NOT MET** | finding #3 (~45 files; CI migrated, code not) |
| No internal-architecture leakage in shipped docs | **NOT MET** | finding #4 (BioLM platform layer/Redis ×63), #6 (Django host) |
| Secret-scanning gate (gitleaks/trufflehog) in CI + pre-launch | **NOT MET** | finding #8 |
| `.planning/` deleted + history nuked | **DEFERRED** | W-launch; tracked, reminder #10 |

## Verification

Adversarial re-check of each flagged finding against the live tree (attempted to refute; cited evidence below).

| # | Finding | Verdict | Reasoning (file:line) |
|---|---------|---------|-----------------------|
| 1 | `R2_BUCKET="biolm-modal"` in `_train.py` | **real** | `models/esmstabp/_train.py:72` sets it as live code; `:307` `s3.put_object(Bucket=R2_BUCKET,...)` uploads there, while the download chain reads `config.r2_bucket_name` (default `biolm-public`, `commons/util/config.py:9`; used in `storage/downloads.py:42`, `acquisition.py:17,252`) — write/read bucket mismatch confirms broken self-population. |
| 2 | Residual `biolm-modal` in shipped files | **real** | Confirmed at every cited loc: `dummy/sources.yaml:106`, `commons/storage/cache.py:48`, `deepviscosity/fixture.py:18`, `esmstabp/download.py:8`, `boltz/fixture.py:16`, `boltz/test.py:112,138` (+ extra hit `.claude/skills/model-knowledge-base/documentation/GUIDE.md`). dummy is the ratified template so it propagates. |
| 3 | `qa` env leak + functional staleness | **real** | `commons/util/config.py:82,84` `deployed_environment_names=["qa","main"]`; `environment.py:140` docstring + `is_production()` (`:148`) compare to that list; `deployment.py:41` hardcodes `("qa","main")`. CI deploys to `biolm-models-dev` (`deploy.yml:60`), absent from the list → `is_production()` returns False for the real deploy env. 30 model `app.py` files still carry `qa` deploy comments. Leak AND live inconsistency. |
| 4 | "BioLM platform layer / Redis two-tier" in public-rendered docs | **real** | Confirmed at `evo/MODEL.md:197`, `igbert/MODEL.md:163-164`, `boltz/MODEL.md:178`; 61 MODEL.md/README.md files carry the "BioLM platform layer" phrase (finding said ~63 — count slightly high, substance holds). `docs/gen_pages.py:258` embeds `MODEL.md` and `:245/:306` embed `README.md` into the generated site → renders publicly. Describes internal hosted infra (no Redis/platform layer exists in OSS; commons cache is in-container, off by default `config.py:58-64`). |
| 5 | Stale `biolm_modal_function`/`biolm_modal_endpoint` names | **real** | Actual decorator is `modal_endpoint` (`commons/core/decorator.py:29`); docstring `:435` says "the biolm_modal_function decorator"; `.github/scripts/analyze_commons_dependencies.py:94` comment imports `biolm_modal_endpoint`. Both names are non-existent symbols → leak + factually wrong. |
| 6 | `training.*` on Django host in commons docstring | **real** | `commons/data/serializer.py:169` docstring example "(e.g. ``training.*`` on the Django host)" — no Django host / training.* module in OSS; leaks internal topology in a heavily-shared file. |
| 7 | Dead internal-named Modal secrets | **real** | `commons/util/config.py:71-72` (`protocols-r2-bkt`) and `:77-78` (`ngc-cli-api-key`) defined; grep across `models/` shows `protocols_r2_bucket_secret` / `nvidia_ngc_secret` are never imported/used outside config.py. Dead `Secret.from_name(...)` leaking internal secret names. |
| 8 | No secret-scanning gate in CI/pre-commit | **real** | `.github/workflows/ci.yml` has no gitleaks/trufflehog; `.pre-commit-config.yaml` exists but contains only pre-commit-hooks + ruff + black (no secret scan); no gitleaks/trufflehog anywhere under `.github/`. Gate absent before private→public flip. |

**Summary:** all 8 findings stand as **real**. Only nuance: finding #4's file count is ~61 (not 63) and #3's "~45 files" is ~33 py files / 30 app.py comments — magnitudes are approximate but every cited file:line is accurate and the substantive leaks/inconsistencies are demonstrable in the live tree.
