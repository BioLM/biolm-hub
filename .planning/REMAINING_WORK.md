# REMAINING WORK — master open-items ledger

> **Read this FIRST on resume.** Single source of truth for EVERYTHING not yet done. Nothing here is
> forgotten — only deferred. Cross-references the detailed docs (`00_MASTER_PLAN`, `02_MODEL_INCLUSION_MATRIX`,
> `03_WORKSTREAMS`, `04_TESTING_STRATEGY`, `W4_ACQUISITION_PLAN`, `W5_HARDENING_GUIDE`, `COMMONS_REQUESTS`).
> Snapshot at the **2026-06-28 pause** (session `oss-stage3-w5-fanout`). Internal file — deleted at launch.

## STATUS SNAPSHOT — what's DONE (committed on `main`)
- **Commons + global rules** (W1/W2/W3a/W-acq/W6/W7/W17) — earlier commits.
- **W5 per-model hardening** — 43 SHIP models hardened; **nanobert + propermab EXCLUDED** (confirmed
  NonCommercial); matrix/licenses corrected (igbert/igt5→CC-BY-4.0, esmc Cambrian-Open). 43 SHIP / 16 EXCLUDE.
- **Milestone A** — peptides + esm2-150m deploy + invoke on `biolm-models-dev`; esm2 self-populated `biolm-public`.
- **W4 self-populating acquisition — 100% code-complete** — commons cleanup (marker-gate correctness fix +
  `r2_then_archive` + curated API + dead-code) + EVERY weight model migrated to the canonical wrappers +
  4 wrapper patterns deploy-proven (sample-validate) + 2 build fixes (StrEnum-3.10 shim; hf_hub in download
  layer). evo + progen2 resolved; pro1/esmstabp = documented exceptions.
- **boltzgen** internal protocols/output-delivery removed.
- **W8 Gateway — ✅ DONE (`97a513f`)** — bare + cached gateways, config-driven discovery (AST deleted),
  status_code→HTTP promotion, CI guard. Bare gateway deploy-proven on dev (see §4).
- **W9 Web app — ✅ DONE** — `bm serve` local catalog web app (browse + run individual models, no gateway
  deploy needed); deployed/undeployed greying; `[serve]` extra. bm-serve deploy-proven; T0+T1+Opus. See §4.

---

## SEQUENCING (ratified by user 2026-06-28) — build ALL features first, deploy/test the full matrix LAST
**Do NOT run the full Milestone-B deploy matrix mid-build.** Order of remaining work:
**(1)** finish ALL platform features across the board — W8 gateway → W9 web app → W10 CLI → W11 CI →
W12 shared test assets → W13 skills → W14 docs (incl. public CLAUDE.md) → W3b commons reconciliation →
W-sec — then **(2)** run **Milestone B** (deploy + golden fixtures + integration/deployment matrix for
ALL models) ONCE at the end, then **(3)** W-launch.
**INTERIM VALIDATION = the proven cheap pattern:** for any NEW commons/architecture change, deploy +
invoke ONE representative model **per variant group the change spans** (as done for esm2 / peptides /
the 4 wrapper samples) to confirm the approach is sound before fanning out — cheap, catches systemic
issues early (it already caught the StrEnum-3.10 + hf_hub build bugs), and avoids premature full-matrix
Modal spend. **Scaling rule (user-clarified 2026-06-28):** the count scales with the number of distinct
variant groups the change touches — if commons logic has, say, 2 variants (e.g. two download-wrapper
patterns, or CPU vs GPU build paths), pick TWO representatives (one from each group), not one overall.

## 1. MILESTONE B — full deploy + integration/deployment test matrix  ⟵ runs LAST (after all features)
**Needs user go-ahead (real Modal spend).** Deploy ALL models to `biolm-models-dev` (then prod
`biolm-models`) and run T2 (integration) + T3 (deployment) per `04_TESTING_STRATEGY`. It accomplishes:
- **(a) Self-population for every model** — so far only esm2 + the 4 sample patterns (mpnn/igt5/esm_if1/
  abodybuilder3) are deploy-proven. All others are Modal-free-validated only.
- **(b) Populates `biolm-public` weights** for all shipped models (first writes).
- **(c) GOLDEN TEST FIXTURES** — input/output JSON goldens do NOT exist in `biolm-public` yet; integration
  tests compare against them, so they must be **generated per-model (`fixture.py`) + reviewed**. **Major
  sub-task.** Fixtures must lazy-load (W17 — already enforced in code).
- **(d) Cache-HIT round-trip** — deploy twice; only esm2's R2 *write* was observed (read-back reasoned).

### Per-model deploy watch-items (flagged during W4 migration — verify on first deploy):
- **esmfold** — 3B-backbone identity inferred as `esm2_t36_3B_UR50D` (+regression); if wrong, the cached set
  won't match the runtime read.
- **immunefold** — ESM2-3B backbone load path; large Zenodo/LFS redirects.
- **boltz** — `mols.tar` (1.86 GB) LFS 302 redirect; flat `--cache` layout incl. `mols.tar`.
- **evo** — does the Evo library honor the `HF_HUB_CACHE` redirect (build + runtime)? If not it re-downloads
  each cold start (still works, just no R2 cache).
- **progen2** — GCS tarball streaming + the full 4-variant shared-prefix layout (oas/medium/large/BFD90).
- **antifold** — OPIG `model.pt` URL (mpnn confirmed IPD resolves; antifold's OPIG host untested).
- **conda/python-3.10 models** (immunefold, deepviscosity, thermompnn, thermompnn_d) — confirm the StrEnum
  3.10 shim (abodybuilder3 + esm_if1 already deploy-confirmed it; immunebuilder is 3.12).

### ⚠️ esmstabp — REQUIRES a manual one-time step before it can deploy:
esmstabp is a self-trained RandomForest with **no public source**. On an empty `biolm-public` its
`standard_r2_download` fails with the `_train.py` hint. **The maintainer must train + upload** the
`{1..4}.joblib` to `model-store/esmstabp/v1/` via the atomic upload (writes the completion marker) before
esmstabp can deploy. **Until then esmstabp cannot deploy.**

### Antibody golden-OUTPUT regen (W5-deferred):
`ablang2` generate, `igbert` paired-generate, `antifold` generate+score now serialize the canonical
`heavy_chain`/`light_chain` output keys. Their R2 golden OUTPUT fixtures (old keys) need a **reviewed**
regen (not blind). Input renames are alias-covered → no regen.

---

## 2. W3b — commons reconciliation pass (one reviewed pass; deferred commons edits)
- **`COMMONS_REQUESTS.md` (1 open row):** remove `protocols_r2_bucket_secret` + `protocols_r2_bucket_secret_name`
  from `commons/util/config.py` and delete the `protocols-r2-bkt` Modal secret (boltzgen no longer uses it).
- **Phase-1-deferred dead-code** (remove once their per-model consumers stop reading them): `AcquisitionResult.
  bypass_detected`/`bypass_locations` (still read by `chai1`/`ablang2` download.py — evo no longer does, it was
  migrated); `LibrarySourceConfig.monitor_directories` (passed by chai1/ablang2/msa_transformer, now
  accepted-unread); `HfSourceConfig.use_auth_token` (evo2 passes it, no-op). Migrate those readers, then delete.
- **`r2_then_archive` NIT-1** (Phase-1 review): cross-dest clobber edge case — if `extract_subtrees` maps one
  entry to `""` (target_dir root) plus sibling subdirs and the `""` entry isn't first, `rmtree` wipes a sibling.
  **Fix before ANY model wires `r2_then_archive`** (none does yet). Clear all dests up front, or forbid `""`+siblings.
- **Lower-priority** (Phase-1 audit §d): simplify `get_r2_prefix_from_target_dir`; reconcile/remove the packaged
  `models/commons/storage/DOWNLOAD_MODEL_WEIGHTS_README.md` (it would ship); confirm NGC secret unneeded (NIM excluded).

---

## 3. LICENSE / secret hygiene (W-sec, pre-launch)
Per-model LICENSE files frequently carry **inferred** copyright holders/years (flagged in-file). Confirm before launch:
- **esmc** — Cambrian-Open "Built with ESM" attribution + naming; confirm vs the upstream agreement.
- **esmstabp** — upstream ships no LICENSE file → MIT is inferred.
- **pro1** — Apache per HF card (GitHub no LICENSE) + the **Llama-3.1-8B base** under Meta's Community License.
- **igbert/igt5** — CC-BY-4.0 (attribution obligation).
- Inferred holders/years across Batch B/E/F + boltz/chai1/rf3/rfd3/boltzgen/abodybuilder3/immunebuilder/etc.
- W-sec: gitleaks/trufflehog scan (CI + pre-launch); confirm `biolm-public` holds **no raw third-party PDFs**;
  fix any remaining internal identifiers. **De-internalization sweep — `biolm-modal`→`biolm-public` bucket
  name still appears in ~11 non-`.planning` files** (`models/dummy/{sources.yaml,BIOLOGY.md}` doc blocks,
  `models/esmstabp/{README,MODEL}.md`+`_train.py`+`download.py`, `models/boltz/{fixture,test}.py`,
  `models/deepviscosity/fixture.py`, `models/commons/storage/cache.py`). W10 fixed only the dummy template's
  W10-broken `bm r2 cp` command + `dummy/MODEL.md`; the rest (incl. code path-strings in fixtures/tests that
  need care) is this sweep. Also de-internalize the temp bootstrap `CLAUDE.md` (deleted at launch anyway).

---

## 4. Remaining project phases (`03_WORKSTREAMS`)
- **W8 Gateway — ✅ DONE + bare-gateway DEPLOY-PROVEN (2026-06-28).** Bare `gateway/server.py`
  (`biolm-gateway`) + cached `gateway/server_with_cache.py` (`biolm-gateway-cache`; both response-cache
  tiers OFF by default behind `BIOLM_CACHE_ENABLED`); shared core `gateway/routing.py`. ASGI fn = `web`
  (qualified `gateway.server.web` — renamed from the funky `gateway.gateway.gateway`). AST class-discovery
  deleted → config-driven `modal_class_name` (set on dummy too); routes via `modal_app_name`.
  status_code→HTTP promotion = **YES** (proven live: esm2 out-of-bounds layers → HTTP 400 `user.validation`).
  CI guard `gateway/test_discovery.py` (88 checks). Stripped auth/billing/analytics/state (−1.8k LOC).
  **Bare gateway deployed to `biolm-models-dev` + smoke-tested:** health (130 routes), peptides encode
  (200, real features), status_code promotion (400). The **cached** gateway is NOT deploy-tested yet (its
  `_run_cached` + lazy cache-stack import + `requests==2.32.3` dep are analysis-validated only) → Milestone B.
  **Deferred to W3b** (COMMONS_REQUESTS): de-dup the partial-payload closure (`decorator.py`); fix/remove the
  `local_models_path` misnomer.
  Deploy gotchas found+fixed: file `gateway/gateway.py` shadowed the `gateway` package on `modal deploy`
  (→ renamed `server.py`); `local_models_path`=`models/commons` not `models/` (→ gateway computes the real
  dir); the cache stack imports `requests` (→ lazy-imported so the bare gateway stays minimal).
- **W9 Web app — ✅ DONE + bm-serve DEPLOY-PROVEN (2026-06-28).** Local catalog web app: `bm serve` runs
  the gateway routing **in-process** (no gateway deployment needed) + mounts the catalog UI; forms POST
  same-origin to `/api/v3/...` which calls your **individual** deployed Modal models. Deployed=active /
  undeployed=greyed (deployment status from `modal app list --json`, best-effort tri-state True/False/None,
  TTL-cached, off-loop). `gateway/catalog/{deployment_status,mount}.py` + `cli/serve.py` (`bm serve`
  `--host/--port/--env/--gateway-url`). Deployed gateway can opt into the catalog via `BIOLM_GATEWAY_CATALOG=1`
  (isolated in try/except; status query skipped in-container). Web deps = **`[serve]` extra** (`pip install
  '.[serve]'`; fastapi pinned ==0.112.0 to match the image's FastAPI internals). Validated: live `bm serve`
  against dev (6 deployed/73 undeployed correct) + 5 unit/route tests (TestClient, Modal-free) + fresh Opus
  review (all 🟠/🟡 addressed). The **deployed-catalog path** (`BIOLM_GATEWAY_CATALOG=1`) is NOT deploy-tested
  (Milestone B). NOTE for W14 docs: warn that a deployed catalog / `bm serve --host 0.0.0.0` is unauthenticated
  and bills the operator's Modal account.
- **W10 CLI — ✅ DONE (Modal-free; T0 + CLI smoke + fresh-Opus review).** New `bm setup`
  (`cli/setup.py`): network-free Modal-auth check (REQUIRED → non-zero exit + `modal token new`
  guidance if missing) + OPTIONAL local R2 creds (AWS_*); rich summary. New `bm cache`
  (`cli/cache.py`): `status` reports whether response caching (`BIOLM_CACHE_ENABLED`, off by default)
  would bake into a deploy; it's a deploy-time setting. `bm deploy --cache/--no-cache` flag bakes the
  env var in (default None = leave env untouched). **`bm r2` is now STRICTLY READ-ONLY** (user
  directive: OSS repo, no writes): removed `cp`/`rm` + all write helpers (`upload_to_r2`/`_upload_one`/
  `should_ignore_path`/`delete_r2_objects`) + a dead vestigial `@click.group() def r2()`; `cp`→read-only
  `download` (R2→local); kept `ls`/`download`/`cat`/`du`/`download-outputs`; de-internalized
  `biolm-modal`→`biolm-public` in docstrings (incl. `models/dummy/MODEL.md`). Quickstart verified
  Modal-free (esm2 already deploy-proven; no re-deploy). **Pre-existing (NOT W10):** `cli/test_kb.py
  TestValidateCmd` 12 failures = `typer.Exit` vs `click.exceptions.Exit` mismatch in `kb.py` tests
  (confirmed on a clean tree) → fix in W11/W17 test-collection pass.
- **🟣 R2 PUBLIC-READ MODEL (user-surfaced 2026-06-28, during W10; NOT yet implemented — decision +
  infra + commons change).** Intended end-state: the BioLM-owned **`biolm-public` bucket should be
  anonymously public-READABLE but not writable**. Today the Modal download layer mounts
  `cloudflare_r2_secret` even to READ public weights (this is why Milestone A's esm2 deploy blocked on a
  missing secret), so the README's "happy path needs no credentials beyond Modal" is **not yet true**.
  To make it true: **(infra, user)** enable anonymous/unsigned reads on `biolm-public` (R2 public bucket
  / r2.dev / bucket policy); **(code, commons)** give the R2 read client an unsigned-access path
  (`botocore Config(signature_version=UNSIGNED)`) when no creds are present, and stop REQUIRING the
  `cloudflare-r2` secret for read-only public-bucket access (writes/self-population to your own bucket
  still need creds). This is a W4/W3b-adjacent commons change + a representative deploy to validate —
  **Modal-spend-gated → fold into the interim-validation pattern or Milestone B.** `bm setup` already
  frames R2 as optional in anticipation of this.
- **W11 CI/CD — ✅ DONE (Modal-free; T0 + 60 script-tests + fresh-Opus SECURITY review → "core isolation
  holds, no 🔴").** Safe tier (`ci.yml`, already on every PR: style+mypy+unit+docs, `contents: read`, no
  secrets, fork-safe) + new CI-script test step. **New `.github/workflows/deploy.yml`** — maintainer-gated
  `pull_request_target`: `revoke-on-push` (removes the `deploy-approved` label on every push → binds approval
  to the reviewed SHA) + secret-free `detect` (label-gated) + `deploy-and-test` matrix (ONLY job with secrets,
  scoped to a `modal-dev` GitHub Environment; `bm deploy`→`-m integration`→`-m deployment`, env
  `biolm-models-dev`, R2_* secrets→AWS_* env). **Ported `.github/scripts/`** detect_models.py + ci_utils.py +
  analyze_commons_dependencies.py (`--smart` dependency-narrowing) + tests, de-internalized (billing paths
  dropped). Review hardening applied: model-name validator `^[A-Za-z0-9_-]+$` + quoted env vars (shell-injection
  defense-in-depth), `persist-credentials: false` on the untrusted-code checkout, `actions/setup-python` in
  detect. `make test-github-scripts` wired into `check`+CI. CONTRIBUTING documents the gate. **FOLLOW-UPS
  (not blockers):** (a) `deploy.yml` is authored + statically validated only — **first LIVE run = a real gated
  PR / Milestone B**; (b) **user must configure** the `deploy-approved` label, the `modal-dev` Environment +
  required reviewers, and `MODAL_TOKEN_*`/`R2_*` as **environment** secrets (see the deploy.yml header);
  (c) `--smart` uses a two-dot diff (`git fetch --depth=1`) → may over-detect if base advanced (cost only);
  (d) the `cli/test_kb.py TestValidateCmd` 12 fails (typer.Exit vs click.exceptions.Exit) still open (W17).
- **W12 Shared test-asset library — ✅ DONE (Modal-free; T0 + 12 commons/testing tests + fresh-Opus review,
  no 🔴).** New `models/commons/testing/shared_assets.py` (importable canonical constants: `STANDARD_PROTEIN`
  61aa + `STANDARD_PROTEIN_STABILITY` 65aa, each with its `test-data/shared/<cat>/<name>` canonical R2 name).
  Runner+generator gained a shared-aware resolver `_fixture_r2_path` — a fixture path starting with `shared/`
  resolves to `test-data/shared/...` (else per-model, byte-identical to before); read (runner) + input-read
  (generator) symmetric, outputs stay per-model. **2 assets wired across 7 models** (esm2/esm1b/esmc/e1/dsm +
  esmstabp/temberture) — de-duped the standard protein that was hardcoded 15×; substring-safe (longer composite
  sequences left intact). `test_shared_assets.py` (6 Modal-free tests). Convention propagated to CONTRIBUTING +
  the dummy template; `02` reconciled. **FOLLOW-UP (Milestone B):** populate `test-data/shared/` in `biolm-public`
  + live-test the `shared/`-path read; only asset population is incremental (no model references a `shared/` path
  yet — current reuse is via the importable constants).
- **W13 Skills** — port `.claude/skills/`; resolve the README-standard conflict; teach the final Global Rules.
- **W14 Docs site + DX** — mkdocs in CI; per-model FastAPI schema docs; render the knowledge graph; **author the
  permanent public `CLAUDE.md` and DELETE the temporary bootstrap `CLAUDE.md`** (tracked deliverable).
- **W15 Off-Modal Dockerfile** — OPTIONAL (go/defer decided late); eligible models only (no GPU-at-build, public source).
- **W-sec** — secret + license hygiene (see §3); gates Stage 7.
- **W-launch** — irreversible ordered sequence: R2 completeness sweep + sec sign-off → public CLAUDE.md → delete
  `.planning/` → nuke git history → flip repo public (gated on marketing material).
- **esmfold2** — SHIP-LATER: add only after its upstream PR (`aqamar/add-esmfold2`) merges into `biolm-modal`
  `main`, then re-confirm weights license (incl. the ESMC-6B backbone).
- **FUTURE_WORK.md** (public, deferred-on-purpose): benchmarks (ProteinGym), self-improving skills, BuildKit fast
  builds, the off-Modal Dockerfile tail.

---

## 5. Environment / process notes (for whoever resumes)
- **Deploys MUST set `MODAL_ENVIRONMENT=biolm-models-dev`** — the local active Modal profile is the internal
  `qa` env. Run modal via `.venv/bin/modal` (modal 1.3.5). Both `biolm-models` (prod) + `biolm-models-dev` exist.
- **Currently deployed on `biolm-models-dev`** (idle = $0; `modal app stop <name> --env biolm-models-dev` to remove):
  `peptides`, `esm2-150m`, `protein-mpnn`, `igt5-paired`, `esm-if1`, `abodybuilder3-plddt`, **`biolm-gateway`**
  (bare gateway, W8 smoke-test; URL `https://biolm-biolm-models-dev--biolm-gateway-web.modal.run`).
- **Secrets in `biolm-models-dev`:** `cloudflare-r2` + `hf-api-token` (user-added). `protocols-r2-bkt` NOT needed
  (boltzgen fixed). `ngc-cli-api-key` NOT needed (NIM excluded).
- **T0 gate** = `uvx ruff@0.6.9 check --no-fix <paths>` + `uvx black@24.10.0 --check` (a bare newer ruff gives
  ~hundreds of false positives — UP045 etc.). mypy is CI-gated (1.5.1 crashes on numpy stubs locally).
- **Build-order rule:** any model whose download fallback imports a library/`huggingface_hub` at build time must
  list it in `setup_download_layer(..., extra_pip_packages=[...])` (else `ModuleNotFound` mid-build).
- **`biolm-public` is not listable from the local shell** (R2 creds live only in the Modal secret).
</content>
