# Cross-cutting review — CI/CD

**Dimension:** CI/CD (`.github/workflows/ci.yml`, `deploy.yml`, `docs.yml`, `.github/scripts/`)
**Date:** 2026-06-29
**Reviewer:** independent (round-1)

## Summary

The CI/CD layer is in good shape and, in places, unusually careful. The split is correct: `ci.yml`
runs only secret-free checks (lint/types/unit/schema-docs/script-tests/docs-build) on every PR via
`pull_request`, while all Modal/R2/secret work is isolated in `deploy.yml` behind a
`pull_request_target` + label gate. The security model is explicitly documented (base-branch workflow
definition, label-as-trust-boundary, `revoke-on-push` commit binding, environment-scoped secrets) and
the shell-injection defense is real: matrix model names flow through quoted intermediate env vars
(`MODEL: ${{ matrix.model }}` → `"$MODEL"`), which is the GitHub-recommended mitigation and holds
regardless of the (PR-controlled) `_safe_model_names` regex. All 60 script tests pass locally; ruff
covers the scripts (T20 correctly ignored under `**/scripts/**`).

The findings below are mostly hardening, consistency, and simplicity issues rather than live security
holes. The two worth real attention before launch: (1) the label gate trusts anyone with GitHub
**triage** permission, not just code-writers, and the mitigating environment required-reviewers is only
*recommended*, not enforced; (2) the entire symbol-level dependency-analysis machinery in
`analyze_commons_dependencies.py` is effectively dead weight — it always collapses to module
granularity — so ~300 lines could become ~30. Also: the CI scripts silently escape `mypy` (it skips
the dotted `.github` dir), and there's an internal `(W11)` workstream reference leaking into shipped
`ci.yml`.

No secret leaks, no broken public contract, no live remote-code-execution-with-secrets path that
isn't gated and documented.

---

## Findings

### 🟠 should-fix

#### 1. Label gate trusts the GitHub *triage* role, not just code-writers; the mitigating env required-reviewers is optional
**category:** security / trust-isolation
**location:** `.github/workflows/deploy.yml:93` (label `if:`), `:124-129` (`environment: modal-dev`), `:22-34` (maintainer setup notes)

The deploy job's trust boundary is the `deploy-approved` label. But on GitHub, **managing labels
requires only the *Triage* permission level**, which is strictly below Write and grants no
code-push/merge rights. A collaborator with triage-only access (a common grant for community
maintainers/bots) can therefore label an arbitrary fork PR and trigger the *only* secret-bearing job,
running that PR's `config.py`/`app.py` on Modal with the maintainer's token. The documented mitigation
— a `modal-dev` Environment with **required reviewers** — closes this, but the workflow comments frame
required-reviewers as protecting against the push-TOCTOU window (`:24-27`), not against the
triage-role escalation, and nothing in the repo *enforces* that the environment is configured. If a
maintainer wires up secrets but forgets required reviewers, triage users gain deploy power.

**fix:** Make environment required-reviewers a hard prerequisite, and say so explicitly: in the
setup notes (`:22-34`) state that **without required reviewers, anyone with triage permission can
deploy**, so the environment MUST have required reviewers before secrets are added. Optionally also
verify the actor: add a guard such as `github.event.pull_request.author_association` /
`OWNER|MEMBER|COLLABORATOR` check, or assert the labeler is a maintainer, as defense-in-depth.

#### 2. Symbol-level dependency analysis is redundant — it always degrades to module granularity (~300 lines of dead complexity)
**category:** software-engineering / weak abstraction (10x)
**location:** `.github/scripts/analyze_commons_dependencies.py:152-222`, `:70-150` (reverse symbol map), `:277-313`

`build_import_map()` registers a module-level wildcard `f"{module}.*"` for **every** model that
imports from a module (`:147`). And `extract_changed_symbols_from_diff()` adds `"*"` to the changed
set for **every** changed line in a commons file (`:203`). Consequently, in `_process_symbol_changes`
the `wildcard_key = f"{module}.*"` lookup (`:213,220-221`) already pulls in *all* models importing
that module, so the specific-symbol lookup (`:216-217`) can never add a model the wildcard didn't.
The net behavior is exactly "any change to commons module X → all models importing X" — i.e. pure
module granularity. The entire apparatus that exists to be finer-grained (the AST symbol extraction,
the six regex symbol patterns, the `symbol_to_models` per-symbol keys, `_get_git_diff`, threading
`diff_output` through `detect_models.py`) buys nothing over `_process_conservative_matching()` alone.

This is real cost: ~300 lines of security-adjacent, fragile diff/regex code (false-positive matches
on `==` comparisons, `+++`/`---` header edge cases, space/rename-in-path breakage) that a maintainer
must trust and keep working, for zero behavioral benefit.

**fix:** Collapse to the module-granular core: build `{model -> set(imported commons modules)}`, and
for each changed commons file return all models importing that module (plus `CRITICAL_COMMONS_FILES`
→ all). Delete `extract_changed_symbols_from_diff`, `_process_symbol_changes`, the `symbol_to_models`
machinery, `_get_git_diff`, and the `diff_output` plumbing. Keep the tests that assert the
module-level behavior.

#### 3. CI scripts silently escape strict `mypy` — 20 type violations go unenforced
**category:** consistency / OSS quality
**location:** `.github/workflows/ci.yml:38` (`uv run mypy .`); `pyproject.toml [tool.mypy] exclude`; `.github/scripts/detect_models.py:138,203,232`, `analyze_commons_dependencies.py:238`

The repo enforces `strict = true` mypy, but `mypy .` does **not** descend into `.github` (mypy skips
dotted directories during recursive discovery), and the mypy `exclude` only lists
`external|.venv|build|dist|docs|tooling`. Running mypy directly on the scripts surfaces 20 strict
errors across the three modules — e.g. bare `dict` return types (`detect_models.py:138,203`), untyped
`def main()` (`:232`), and an implicit-Optional `diff_output: str = None`
(`analyze_commons_dependencies.py:238`). So the security-sensitive change-detection code is held to a
*lower* bar than every model. Not currently red (CI stays green precisely because these files are
invisible to mypy), but it's an enforcement gap in exactly the code where correctness matters.

**fix:** Add the scripts to the type-check step (`uv run mypy . .github/scripts` or a dedicated mypy
invocation) and fix the resulting errors (`dict[str, str]`, `-> None`, `str | None = None`, etc.).

#### 4. Internal workstream reference `(W11)` leaks into shipped `ci.yml`
**category:** internal leakage (OSS-readiness)
**location:** `.github/workflows/ci.yml:5`

> `# workflow (W11) so untrusted PRs never trigger expensive Modal jobs.`

`(W11)` is an internal `.planning/03_WORKSTREAMS.md` workstream ID, meaningless to outside
contributors and a tell of the private porting process. The rubric lists internal-process references
in shipped files as launch-gating. (`deploy.yml` is clean of W-refs; this is the only one in the
CI/CD surface.)

**fix:** Drop the `(W11)` parenthetical: "...are maintainer-gated in a separate workflow
(`deploy.yml`) so untrusted PRs never trigger expensive Modal jobs."

#### 5. Default-mode treats a commons *docs-only* change as triggering ALL models (inconsistent with smart mode)
**category:** correctness / cross-mode inconsistency (cost)
**location:** `.github/scripts/detect_models.py:61-66` vs `:92-94`

In `detect_affected_models_default`, the `models/commons/` check (`:61`) short-circuits and returns
`get_all_valid_models()` **before** the `is_docs_only` check at `:71`. So a change to
`models/commons/README.md` (or any commons `.md/.yaml/.json`) deploys all 44 models. Smart mode's
`_categorize_changed_files` correctly applies `is_docs_only` to commons (`:92-94`) and does not
trigger. This violates the Modal cost-discipline north star and is an inconsistency the tests don't
catch. **Impact is currently latent**: the only workflow caller passes `--smart`, and smart's own
failure-fallback sets all-models without reaching this code, so pure default mode is never exercised
in CI today. Still worth fixing so the two paths agree.

**fix:** In default mode, apply `is_docs_only(file_path)` to commons files before setting
`commons_changed`/returning all models, mirroring `_categorize_changed_files`.

### 🟡 nits

#### 6. Seven detect outputs are emitted but never consumed
**category:** dead code
**location:** `.github/scripts/detect_models.py:210-228`

`_build_model_outputs` emits `has_models_with_code_changes`, `count`, `commons_changed`,
`has_unit_test_changes`, `detection_method`, `models_saved`, `time_saved_minutes`. Only
`models_changed`, `has_models`, and `models_with_code_changes` are referenced by any workflow
(confirmed across `.github/workflows/`). The rest (and the `has_unit_test_changes` computation, which
uses a loose `"test" in f` substring match) are dead.

**fix:** Drop the unconsumed outputs (and the `has_unit_test_changes` substring heuristic), or, if
kept for human-readable step logs, move them to log lines rather than `$GITHUB_OUTPUT`.

#### 7. `is_non_code` classifies *all* `.yaml/.yml/.json` as non-code → risk of skipping a functional-config redeploy
**category:** correctness (heuristic)
**location:** `.github/scripts/ci_utils.py:17,20-30`

Treating every `.yaml/.yml/.json` as docs/metadata is right for the knowledge-graph files
(`sources.yaml`, `comparison.yaml`) but means a model whose runtime depends on a checked-in
`*.json`/`*.yaml` (e.g. a weights manifest or label map consumed at inference time) would **not**
trigger a redeploy when that file changes — a silent stale-deploy. Safe for today's models (all
config lives in `config.py`), but it's an under-detection trap for future contributors.

**fix:** Either narrow the data-file skip to the known knowledge-graph filenames, or document the
assumption ("functional config must live in `*.py`") prominently so contributors don't put
load-bearing config in YAML/JSON.

#### 8. `_SAFE_MODEL_NAME` permits a leading hyphen → CLI option-injection vector
**category:** security (minor)
**location:** `.github/scripts/detect_models.py:28`

`^[A-Za-z0-9_-]+$` accepts names like `-rf` or `--force`. Such a name passes validation and becomes
`bm deploy "-rf" --force` / `pytest "models/-rf/test.py"`, where the CLI may interpret it as an
option rather than a positional (option injection, distinct from shell injection which the quoting
already blocks). Requires a maintainer-reviewed malicious directory name, so low likelihood.

**fix:** Disallow a leading hyphen, e.g. `^[A-Za-z0-9_][A-Za-z0-9_-]*$`.

#### 9. Misplaced module docstring in the analyzer (dead string expression)
**category:** readability
**location:** `.github/scripts/analyze_commons_dependencies.py:1-16`

The triple-quoted description (`:8-16`) sits **after** the imports (`:1-6`), so it is not the module
docstring — it's a no-op expression statement and won't appear in `help()`/`__doc__`.

**fix:** Move the docstring to the top of the file (before imports).

#### 10. Doc comment overstates the (PR-controlled) regex as the injection guarantee
**category:** documentation accuracy
**location:** `.github/workflows/deploy.yml:150-158`; `.github/scripts/detect_models.py:24-28`

The comment says matrix values are safe because they are "validated to `^[A-Za-z0-9_-]+$` by
detect_models.py." In the fork-PR threat model that file is checked out from the PR and runs in
`detect`, so its validation can be removed by the attacker. The *actual* guarantees are (a) the
quoted intermediate env var (which holds regardless) and (b) the maintainer's full-diff review. Worth
stating accurately so a future maintainer doesn't lean on the regex as the boundary.

**fix:** Reword to credit the env-var quoting + human review as the real defenses, with the regex as
best-effort defense-in-depth for the trusted (`push`) path only.

#### 11. `detect` checkout runs untrusted PR code without `persist-credentials: false`
**category:** hardening (minor)
**location:** `.github/workflows/deploy.yml:100-104` (vs `:135-139` on `deploy-and-test`)

`deploy-and-test` correctly sets `persist-credentials: false`, but the `detect` checkout — which also
runs PR-controlled code (`detect_models.py`) — leaves the (read-only `contents: read`) `GITHUB_TOKEN`
persisted in `.git/config`. The token can't write, so impact is low, but there's no reason to expose
it to untrusted code.

**fix:** Add `persist-credentials: false` to the `detect` checkout.

---

## Definition-of-Done notes (CI/CD scope)

- **Maintainer-gated CI/CD (W11 DoD):** met. Safe checks on every PR (`ci.yml`); secrets isolated to a
  single label-gated, environment-scoped, commit-bound job (`deploy.yml`). Caveats: triage-role
  escalation (#1) and the optional-vs-enforced env reviewers.
- **Shell-injection defense:** met (env-var quoting; regex as defense-in-depth). Doc wording (#10) and
  leading-hyphen gap (#8) are minor.
- **Change-detection correctness:** met for the production (`--smart`) path. Latent default-mode
  inconsistency (#5) and YAML/JSON under-detection (#7).
- **Tests for CI scripts:** present and passing (60 tests); but the scripts escape `mypy` strict
  typing (#3).
- **No internal leakage:** one `(W11)` reference remains (#4). `biolm-models-dev` (Modal env) is this
  repo's own dev environment, not internal-repo leakage — fine.

## Verification

Adversarial re-check of the 5 HIGH-severity findings against the actual code (round-1 verifier).

1. **Label gate trusts triage role; env required-reviewers optional/under-framed — REAL.**
   `deploy.yml:93` gates `detect` solely on `github.event.label.name == 'deploy-approved'`, and
   `deploy-and-test` (`:124-133`) gates only on `needs.detect`. Applying an existing label needs only
   GitHub *Triage* (below Write/no code-push). The real defense is the `modal-dev` Environment's
   required reviewers, but that is a manual, repo-unenforceable setting and the setup comments
   (`:24-30`) frame required reviewers around "shows the exact commit SHA" / closing the pre-label
   window — not as the guard against triage-only labelers. Gap is demonstrable in code + docs.

2. **Symbol-level analysis redundant, degrades to module granularity — REAL.**
   `analyze_commons_dependencies.py:147` registers `f"{module}.*"` for every importing model, so the
   wildcard key is a superset of every specific-symbol key; `:201-203` co-add `"*"` in the same
   `if match:` block, so whenever a file appears in `changed_symbols` it always contains `"*"`. Thus
   `_process_symbol_changes` (`:207-222`) always hits the wildcard branch → returns the same set as
   `_process_conservative_matching`, never narrower. The AST/regex/symbol apparatus yields zero extra
   savings and zero extra models. (Minor imprecisions in the finding's asides: `+++`/`---` headers do
   not actually match the 6 patterns; `"*"` is added per matched line, not per changed line — but the
   central redundancy claim holds.)

3. **CI scripts escape strict mypy — 20 violations — REAL.**
   `pyproject.toml` `[tool.mypy] strict=true`, `exclude` = `(external|.venv|build|dist|docs|tooling)`
   (no `.github`). Reproduced that `mypy .` skips dot-directories: a `.dotdir/bad.py` was NOT checked
   while `normaldir/bad.py` was. Running `uv run mypy .github/scripts/*.py` directly → exactly
   `Found 20 errors`, including the cited `detect_models.py:138,203` (bare `dict` type-arg), `:232`
   (untyped `def main()`), and `analyze_commons_dependencies.py:238` (implicit-Optional
   `diff_output: str = None`). CI's `uv run mypy .` (ci.yml:38) never sees these files.

4. **Internal workstream ref (W11) leaks into ci.yml — REAL.**
   `ci.yml:5` literally reads "...maintainer-gated in a separate workflow (W11)...". Grep over
   `.github/` finds this is the *only* `W<n>` reference; `deploy.yml` is clean. W11 is an internal
   `.planning/03_WORKSTREAMS.md` id (matches git log `feat(W11)`), meaningless to public contributors.

5. **Default-mode treats commons docs-only as triggering ALL models — REAL (latent).**
   `detect_models.py:61-65` returns `get_all_valid_models()` for any `models/commons/` file when
   `not for_deployment_tests`, BEFORE the `is_docs_only` check at `:71`; smart mode's
   `_categorize_changed_files:92-94` correctly excludes commons docs-only (`is_docs_only` treats
   `.md/.yaml/.json/...` as non-code, per `ci_utils.py:17,30`). Confirmed latent: the sole CI caller
   uses `--smart` (`deploy.yml:121`); the only `detect_affected_models_default` invocation in that
   path passes `for_deployment_tests=True` (`:310-312`, skips the return-all), and the smart fallback
   sets all-models directly (`:183,188`). The path inconsistency is real but unreached in CI today.

**Summary:** 1 REAL, 2 REAL, 3 REAL, 4 REAL, 5 REAL (latent). None refuted.
