# Round-1 Review — OSS Readiness & Top-Level Docs

**Dimension:** OSS readiness & top-level docs
**Scope:** `README.md`, `CONTRIBUTING.md`, `PHILOSOPHY.md`, `SECURITY.md`, `CODE_OF_CONDUCT.md`,
`FUTURE_WORK.md`, `LICENSE`, `CLAUDE.md`, `.gitignore` — plus the docs-site source pages
(`docs/index.md`, `docs/quickstart.md`, `mkdocs.yml`) and cross-cutting OSS concerns (internal
leakage, quickstart reproducibility).
**Reviewer model:** Opus 4.8

## Summary

The top-level docs are in good shape and, importantly, the W14 deliverable landed: the **temporary
bootstrap `CLAUDE.md` has been replaced by a clean public one** (no `biolm-modal` / `.planning` / `qa`
references) — that DoD item is met. `CONTRIBUTING.md` is notably accurate: its claims about the
Makefile targets, the two-workflow CI split, the `deploy-approved` label, the `modal-dev` environment,
and `detect_models.py` all match the actual `.github/` files. `LICENSE` is real Apache-2.0, consistent
with `pyproject.toml`, and 43/44 model dirs carry a per-model `LICENSE` (only the `dummy` template
lacks one, which is correct). The docs site builds green under `mkdocs build --strict` (43 model pages
generated), and every doc-referenced code path I spot-checked (`get_logger`, `STANDARD_PROTEIN`,
`field_glossary.yaml`, `detect_models.py`) exists.

The launch-gating problems are: (1) an **internal-name leak (`biolm-modal`) still present in shipped
files**, most damagingly in the `models/dummy/` *template* every new model is copied from — the
de-internalization sweep (`biolm-modal`→`biolm-public`) is not complete; (2) the **headline quickstart
is not literally reproducible** — `bm` is a venv console-script and no doc tells the user to activate
the venv (or use `uv run`), so `make install && bm setup` fails with `command not found` for a fresh
user, and `docs/index.md`'s "Five-minute success" block omits `make install` entirely; (3) the
**front-door CLI command list is wrong** in both `README.md` and `docs/index.md` (omits `cache` and
`kb`); and (4) `SECURITY.md` / `CODE_OF_CONDUCT.md` ship unresolved "confirm/replace this contact
before launch" placeholder comments on the official reporting addresses.

DoD audit (docs/OSS items):
- ✅ Public `CLAUDE.md` authored, bootstrap deleted (clean of internal refs).
- ✅ Docs site builds (`--strict`); every shipped model has a page; PHILOSOPHY/CONTRIBUTING/SECURITY/
  LICENSE/FUTURE_WORK present.
- ✅ Deploy env de-internalized (`qa` → `biolm-models-dev`); no `.planning` refs in shipped files.
- ⚠️ "git clone → bm setup → bm deploy esm2 → inference in three commands … verified on a clean
  machine" — **not met as written**: requires `make install` (so not 3 commands) and the documented
  copy-paste path fails because `bm` isn't on PATH (see finding #2). Casts doubt on the W14
  "verify the quickstart on a clean machine" acceptance step.
- ⚠️ "nothing references the internal repo" — **not met**: `biolm-modal` still in shipped files
  (finding #1).

---

## Findings

### 🔴 must-fix before launch

#### 1. Internal-name leak `biolm-modal` in shipped files — including the `dummy` template
- **Category:** No internal leakage / OSS readiness (DoD)
- **Location:** `models/dummy/sources.yaml:106` (template); also `models/commons/storage/cache.py:48`,
  `cli/main.py:16,18,47`, and per-model files `models/deepviscosity/fixture.py:18`,
  `models/esmstabp/download.py:8`, `models/esmstabp/_train.py:72`, `models/boltz/fixture.py:16`,
  `models/boltz/test.py:112,138`.
- **Detail:** The ratified de-internalization sweep (`biolm-modal` → `biolm-public`, recorded in
  `.planning/REMAINING_WORK.md`) is incomplete. The rubric classes any `biolm-modal` reference in a
  shipped file as a 🔴 internal-reference leak. The most damaging instance is
  `models/dummy/sources.yaml:106` — `# R2 path (without r2://biolm-modal/ prefix) to the PDF.` —
  because `models/dummy/` is the template `README.md:61` and `CONTRIBUTING.md:21` explicitly tell every
  contributor to copy, so the leak propagates into every future model's `sources.yaml`. (Per-model
  occurrences are also each in the relevant per-model reviewer's scope; listed here as evidence the
  sweep is not done.)
- **Fix:** Run the `biolm-modal`→`biolm-public` sweep to completion across all shipped files (grep
  `biolm[-_]modal` excluding `.planning/`). At minimum fix the template `models/dummy/sources.yaml` and
  `models/commons/storage/cache.py` now, since those are framework/template files in this dimension's
  blast radius.

### 🟠 should-fix

#### 2. Documented quickstart is not reproducible — `bm` is not on PATH after `make install`
- **Category:** Docs accuracy / DX (DoD: "five-minute success", clean-machine quickstart)
- **Location:** `README.md:24-27`, `docs/quickstart.md:19`, `Makefile:17`
- **Detail:** `bm` is a console-script entry point (`pyproject.toml:65` → `cli.main:app`) installed
  into `.venv/bin/bm`. `make install` runs `uv venv` + `uv sync` but never activates the venv, and **no
  doc anywhere mentions activating it or prefixing `uv run`** (verified: zero `activate` / `uv run bm`
  guidance in README, quickstart, index, Makefile, CONTRIBUTING). So a fresh user copy-pasting
  `make install` then `bm setup` gets `command not found: bm`. The Makefile even ends with
  `✅ Installed. Run 'bm setup' …`, reinforcing the broken invocation. This directly breaks Principle #1
  ("If the first screen of the README doesn't get someone to a running model, that's a bug" —
  `PHILOSOPHY.md`) and the DoD's clean-machine quickstart.
- **Fix:** Add an explicit activation step to the quickstart (`source .venv/bin/activate`) — or change
  the install flow to `uv tool install .` so `bm` is globally available — or document `uv run bm setup`.
  Update the Makefile install echo to match whatever is chosen. Then actually run the quickstart on a
  clean checkout to confirm.

#### 3. `docs/index.md` "Five-minute success" omits `make install`; duplicated home pages drift
- **Category:** Docs accuracy / duplication
- **Location:** `docs/index.md:13-19` (and the README↔index duplication generally)
- **Detail:** The site home page's headline code block is `git clone` → `cd` → `bm setup` →
  `bm deploy esm2` — it omits `make install` entirely, so `bm` doesn't even exist (strictly worse than
  the README, which at least includes `make install`). Root cause: `gen_pages.py` mirrors
  `PHILOSOPHY/CONTRIBUTING/FUTURE_WORK` from the repo root (single source of truth) but **does not**
  mirror `README.md` — `docs/index.md` and `docs/quickstart.md` are hand-maintained separately, so they
  drift from `README.md`. They have already diverged (this missing step; the CLI list in #4).
- **Fix:** Add `make install` (and the venv-activation step from #2) to `docs/index.md`'s block. Long
  term, reduce duplication: either generate `index.md` from `README.md` too, or have `index.md` be a
  thin pointer to `quickstart.md` so there's one canonical quickstart.

#### 4. Front-door CLI command list is wrong — omits `cache` and `kb`
- **Category:** Docs accuracy / consistency
- **Location:** `README.md:41`, `docs/index.md:26`
- **Detail:** Both say the `bm` tool is `setup`, `deploy`, `serve`, `r2`. The actual top-level commands
  (`cli/main.py:52-63`, and the help table at `cli/main.py:84-89`) are `setup`, `deploy`, `serve`,
  `cache`, `r2`, `kb` — six. `CLAUDE.md:23` lists all six correctly, so the two most-read public docs
  contradict the canonical one.
- **Fix:** Update the README and `docs/index.md` CLI lists to include `cache` and `kb` (match
  `CLAUDE.md:23`).

#### 5. Unresolved "confirm before launch" placeholders on official reporting contacts
- **Category:** OSS readiness / launch hygiene
- **Location:** `SECURITY.md:8`, `CODE_OF_CONDUCT.md:32`
- **Detail:** Both ship `<!-- maintainers: confirm/replace this contact before launch -->` on the
  security (`security@biolm.ai`) and conduct (`conduct@biolm.ai`) addresses. These are the official
  vulnerability- and conduct-reporting channels; if the address is a guess, reports silently go
  nowhere. Shipping an explicit "confirm before launch" note in a public security policy is also a poor
  look. (`biolm.ai` is the org's public domain, so it is not itself a leak — the issue is the
  unverified-placeholder status.)
- **Fix:** Confirm the two addresses route to a monitored inbox, then delete both HTML comments before
  flipping the repo public.

#### 6. Internal product name "BioLM-Modal" in shipped CLI docstrings
- **Category:** No internal leakage
- **Location:** `cli/main.py:16`, `cli/main.py:18`, `cli/main.py:47`
- **Detail:** The CLI module docstring ("BioLM-Modal Command Line Interface", "working with BioLM-Modal
  models and infrastructure") and the Typer callback docstring ("BioLM-Modal is a platform for serving
  BioLM models on Modal") use the internal project name. The public project is `biolm-models`; the
  Typer callback docstring can surface in `--help`. Part of the same de-internalization gap as #1.
- **Fix:** Reword to `biolm-models` (e.g. "biolm-models command-line tools").

### 🟡 nit

#### 7. "Three commands" claim undercounts the real flow
- **Category:** Docs consistency
- **Location:** `PHILOSOPHY.md:13` (and the framing in `README.md:18` / `docs/index.md:11`)
- **Detail:** PHILOSOPHY states "`git clone` → `bm setup` → `bm deploy esm2` → first inference, in
  three commands," but the actual flow needs `make install` (and venv activation, #2) before `bm` works
  — four-plus steps. The DoD repeats the "three commands" wording. Minor, but it sets an expectation the
  README's own quickstart contradicts.
- **Fix:** Either say "a few commands" (as `docs/quickstart.md:3` already does) or include `make
  install` in the count.

#### 8. `pip install '.[serve]'` mixes toolchains and is redundant after `make install`
- **Category:** Docs consistency
- **Location:** `docs/quickstart.md:51`
- **Detail:** The rest of the docs use `uv` / `make install`, and `make install` runs
  `uv sync --all-extras` (`Makefile:15`) which already installs the `serve` extra. The bare
  `pip install '.[serve]'` step is therefore redundant and, without an activated venv, would install
  into the wrong environment.
- **Fix:** Drop the step (serve is already installed) or write it as `uv sync --extra serve` for
  consistency.

#### 9. `Documentation` URL points to the repo, not the published docs site
- **Category:** Docs polish
- **Location:** `pyproject.toml:69`
- **Detail:** `docs.yml` publishes the mkdocs site to GitHub Pages, but `[project.urls] Documentation`
  points back to the GitHub repo. Once Pages is live there's a real docs URL to use.
- **Fix:** Point `Documentation` at the GitHub Pages URL after the first publish.

---

## Notes / positives (no action needed)
- `CLAUDE.md` (on-disk) is the clean public version — bootstrap successfully replaced; no
  `biolm-modal` / `.planning` / `qa` references. Its CLI list and house-rules are accurate.
- `CONTRIBUTING.md`'s CI description matches `.github/workflows/ci.yml` + `deploy.yml` exactly
  (`deploy-approved` label, `modal-dev` environment with required reviewers, `detect_models.py`
  fan-out, `MODAL_TOKEN_*`/`R2_*` secrets).
- `.gitignore` is correct and its note explains why `.planning/` is intentionally not ignored (to be
  deleted with history before launch).
- `LICENSE` = Apache-2.0, `Copyright 2026 BioLM`, consistent with `pyproject.toml:8`; README's
  "framework Apache-2.0, each model carries its own upstream license" claim holds (43/44 model dirs
  have a `LICENSE`).
- Docs build is green under `mkdocs build --strict`.

## Verification

Adversarial re-check of the six HIGH-severity findings against current `main` (commit `263bc7c`, W14). All six confirmed REAL.

1. **Internal-name leak `biolm-modal` in shipped files (incl. dummy template) — REAL.** All 8 cited occurrences exist: `models/dummy/sources.yaml:106`, `models/commons/storage/cache.py:48`, `models/esmstabp/_train.py:72` & `download.py:8`, `models/deepviscosity/fixture.py:18`, `models/boltz/fixture.py:16` & `test.py:112,138`. Files are git-tracked. `README.md:61` + `CONTRIBUTING.md:21` both tell contributors to copy `models/dummy/`, so the template comment propagates. The sweep is a ratified, still-open must-fix: `.planning/REMAINING_WORK.md:97-98` ("De-internalization sweep — biolm-modal→biolm-public").
2. **`bm` not on PATH after `make install` — REAL.** `bm` is a console-script (`pyproject.toml:64-65` `bm = "cli.main:app"`) installed into `.venv/bin/bm`. `Makefile:12-17` runs `uv venv` + `uv sync` but never activates the venv; the only `.venv/bin` reference (Makefile:16) is the internal pre-commit install, not user guidance. Grep finds zero `activate` / `uv run bm` / `source .venv` guidance in README/quickstart/index/Makefile/CONTRIBUTING. Docs run `bm setup` immediately after `make install` (README.md:23-27, quickstart.md:10-19) → `command not found: bm`.
3. **docs/index.md 'Five-minute success' omits `make install` — REAL.** `docs/index.md:13-19` block is clone→cd→`bm setup`→`bm deploy` with no install step (strictly worse than README:20-28, which has `make install`). Root cause confirmed: `gen_pages.py:335-337` calls `_mirror_root` only for PHILOSOPHY/CONTRIBUTING/FUTURE_WORK — NOT README.md (line 40's `README.md`→`index.md` is link-rewrite map only, not a mirror copy). So index.md/quickstart.md are hand-maintained and have drifted.
4. **Front-door CLI command list omits `cache` and `kb` — REAL.** `README.md:41` and `docs/index.md:26` both list `setup, deploy, serve, r2` (4). Actual top-level commands are six: `cli/main.py:52-63` mounts r2, kb, cache, setup, deploy, serve, and the help table `cli/main.py:84-89` lists setup/deploy/serve/cache/r2/kb.
5. **Unresolved 'confirm before launch' placeholders on reporting contacts — REAL.** `SECURITY.md:8` (`security@biolm.ai`) and `CODE_OF_CONDUCT.md:32` (`conduct@biolm.ai`) both ship the literal `<!-- maintainers: confirm/replace this contact before launch -->` HTML comment in public-facing policy files.
6. **Internal product name 'BioLM-Modal' in CLI docstrings — REAL.** `cli/main.py:16,18` (module docstring "BioLM-Modal Command Line Interface" / "working with BioLM-Modal models and infrastructure") and `cli/main.py:47` (callback docstring "BioLM-Modal is a platform..."). Minor caveat: line 47 may not surface in `--help` because `Typer(help=...)` is set explicitly at line 25, but the strings are unquestionably shipped in source; the finding hedges with "can surface".
