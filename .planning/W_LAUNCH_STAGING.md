# W-launch — staged, one step from go (DO NOT RUN without the maintainer's explicit go)

> This is the launch runbook. Every step below is **ready to run but intentionally NOT executed.**
> The two irreversible steps (nuke history, flip public) are the maintainer's alone, on explicit command.
> **Copy this file out of `.planning/` before Step C (which deletes `.planning/`).**

## 0. Where we are (all green as of this session)
- 36 SHIP models + `dummy` deploy + integration-pass on `biolm-hub-dev`; goldens reviewed. (§4 bars #1/#2)
- `make check` + `make docs` (mkdocs --strict) + blocking `mypy --strict`=0 green; CI green on `main`; gitleaks clean. (#3)
- R2 `biolm-public` public-ready: only `biolm-hub/{model-weights,test-data}/models` (+`model-cache`); 311 GB legacy cruft deleted; no dropped-model weights, no raw PDFs, all markers complete. (#4)
- De-internalization total in the working tree; **git history is still dirty** → the nuke in Step D is required. (#5)
- Docs site + skills current, clean, and proven-executable; credential-less deploy/read proven. (#6)

## A. Human-only prerequisites (maintainer must confirm/provide before launching)
- [ ] **Contacts** — confirm `support+security@biolm.ai` (SECURITY.md) and `support+conduct@biolm.ai` (CODE_OF_CONDUCT.md) route to a monitored human. (D4)
- [ ] **Licenses** — accept prody's transitive OpenBabel GPL-2.0 (apt-installed system tool, not vendored — recommended accept); spot-confirm inferred per-model LICENSE copyright holders (see the license spot-check notes appended by the launch-staging pass).
- [ ] **(Optional) D2 GitHub infra** — only if you want the gated-CI deploy path (`deploy.yml`) proven pre-launch: create the `modal-dev` GitHub Environment + `MODAL_TOKEN_ID`/`MODAL_TOKEN_SECRET` + `R2_*` environment secrets + the `deploy-approved` label + required reviewers. Not required for the repo release (users deploy to their own Modal). Verified currently ABSENT (`gh api repos/BioLM/biolm-hub/environments` → 0).
- [ ] **Marketing** — launch is gated on marketing material being ready (per the master plan).
- [ ] **(Optional) Prod deploy** — you chose OSS-repo-only; prod `biolm-hub` env stays empty. No action.

## B. Final pre-flight (re-run immediately before launch; all must pass)
```bash
# From a clean checkout of main:
make check          # style + mypy(--strict, blocking) + schema-docs + CI-scripts + unit
make docs           # mkdocs build --strict
# CI green on main (gh run list --branch main --limit 1)
# Optional: re-verify the 5-minute quickstart from a fresh clone with only a Modal account
#   git clone … && bh setup && BIOLM_SKIP_MODAL_SECRETS=1 bh deploy esm2  (creds-less path)
```
Also: a final R2 completeness sweep (re-run `scratchpad/r2_full_audit.py` — confirm zero cruft) + a final security sign-off (gitleaks over the tree; confirm no internal identifiers).

## C. Delete `.planning/` (reversible until the history nuke; do this in the launch commit)
```bash
# COPY OUT anything you still need first (this file, MAINTAINER_LAUNCH_CHECKLIST.md).
git rm -r .planning
# Also confirm scratchpad/ is gitignored (it is) and not tracked.
git commit -m "chore: remove internal planning docs ahead of public release"
```

## D. ⚠️ IRREVERSIBLE — Nuke git history (MAINTAINER ONLY, explicit go)
The whole history is internal porting work + carries internal identifiers (billing/redis/`biolm-modal`). Squash to a single clean commit so the public repo starts fresh. **Recommended (full nuke via orphan commit):**
```bash
git checkout --orphan _public
git add -A
git commit -m "biolm-hub: initial public release"
git branch -D main
git branch -m main
# Verify the new single-commit tree is clean + builds:
git log --oneline          # expect ONE commit
make check && make docs
# gitleaks over the (now single-commit) history one more time.
# Then force-update the remote:
git push -f origin main
```
(Alternative: `git filter-repo` if you want to preserve a curated subset of history — not recommended here; a clean single commit is simplest and safest for secret hygiene.)

## E. ⚠️ IRREVERSIBLE — Flip the repo public (MAINTAINER ONLY, explicit go, gated on marketing)
```bash
gh repo edit BioLM/biolm-hub --visibility public --accept-visibility-change-consequences
# (Optionally) enable the docs site: set the PAGES_ENABLED repo variable so .github/workflows/docs.yml publishes.
```

## F. Post-launch
- Announce (when marketing is ready).
- Re-populate `biolm-public` weights are already cached; contributors self-populate their own bucket.
- Post-v1 items live in the public `FUTURE_WORK.md` (self-healing weight bake, input option-value uniformity, off-Modal Dockerfiles, benchmarks, esmfold2, etc.).

---
**Reiterated:** Steps D and E are irreversible and are the maintainer's to run on explicit command. Nothing in this runbook has been executed.
