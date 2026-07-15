# CI impact and the deploy-approved decision

Predict what a change will deploy before you push or request the label. The full CI/deploy policy is
canonical in `CONTRIBUTING.md` → "Continuous integration and deploys"; this reference owns the
operational blast-radius technique and the label-request decision.

## Two workflows, one gate

`main` is protected — no direct pushes; every change lands via PR. In the PR's checks UI you see
three required checks from `ci.yml`: **`lint · types · unit`** (job id `checks` — this is `make
check`), **`docs build`** (job `docs` — `mkdocs build --strict`), and **`secret scan`** (job
`secrets` — gitleaks, tuned by `.gitleaks.toml`). None of them carry secrets, so they run on fork
PRs too.

The expensive Modal deploy + integration/deployment matrix lives in `deploy.yml` ("Gated Deploy &
Test") and runs only after a maintainer applies the `deploy-approved` label (or dispatches it
manually via `workflow_dispatch`, passing the model slugs to deploy). The facts that drive a
blast-radius or label decision:

- **Opening or pushing to a PR never deploys.** The matrix is maintainer-gated behind
  `deploy-approved` **and** the `biolm-hub-dev` GitHub Environment approval (a required reviewer sees
  the exact commit SHA before any secret is exposed).
- **The label pins to the commit it was added on.** A later push does not re-deploy and does not
  remove the label; to ship a newer commit a maintainer re-reviews, then removes and re-adds it.
- **Secrets never reach a fork.** Modal/R2 creds live only on the `biolm-hub-dev` GitHub Environment
  (required reviewers), never repo-wide — so untrusted PRs can run CI but can't deploy, and `ci.yml`
  carries no secrets at all.

## Predicting CI Impact Before Pushing / Requesting the Label

The "Gated Deploy & Test" pipeline is SELECTIVE — it uses smart detection scripts to determine which models to deploy+test based on the git diff. **Before requesting `deploy-approved`, predict the blast radius:**

```bash
# Predict which models would be deployed+tested when the label is applied.
# Run from the REPO ROOT — the script lists `models/` relative to the cwd, so a
# `cd .github/scripts` first finds zero models. (CI runs it from the root too.)
python .github/scripts/detect_models.py origin/main --smart 2>&1

# Check if "CI" is already running (pushing cancels it)
gh run list --branch $(git branch --show-current) --status in_progress --json databaseId --jq length
```

Note: the "CI" workflow always runs all unit tests regardless of what changed.

### What the Deploy Matrix Triggers

| Change | Models Deployed | Unit Tests (CI) |
|--------|----------------|-----------------|
| Single model file (`models/esm2/app.py`) | Only that model | All |
| Any commons **code** change (non-docs) | Depends on the mode (see below). **Smart** (`--smart`, what `deploy.yml` runs): only the models whose imports reach the changed commons module, via the dependency import-map — but it **falls back to all models** if the analysis errors. **Default** (no `--smart`): **all models**, unconditionally. | All |
| Commons **docs-only** change (`README.md`, `*.yaml`, ...) | 0 models (skipped by both modes) | All |
| `pyproject.toml`, `uv.lock`, `Makefile` | 0 models | All |
| `.github/workflows/*.yml` | 0 models | All |
| Only docs (`.md`, `.txt`) | 0 models | 0 |

There is **no hardcoded list of "critical" commons files.** The blast radius of a commons change is
decided entirely by `detect_models.py`'s two modes (`.github/scripts/detect_models.py`):
- **Default mode** — any non-docs change under `models/commons/` triggers **all** valid models. Simple
  and battle-tested.
- **Smart mode** (`--smart`, used by `deploy.yml`) — builds an import map
  (`analyze_commons_dependencies.py`'s `DependencyAnalyzer`) and triggers only the models that import
  the changed commons module; on any error it **falls back to default (all models)**. A
  widely-imported module (e.g. the base pydantic models) still fans out to nearly everything.

In both modes a docs/data-only commons change (`*.md`, `*.yaml`) triggers **zero** models.

### Decide before requesting `deploy-approved`

Predict the fan-out from the repo root, then read the row you land on:

```bash
python .github/scripts/detect_models.py origin/main --smart
```

| Predicted deploy | Commons code changed? | Do this |
|------------------|-----------------------|---------|
| 0 models | — | Label is free — request it. |
| 1–5 models | No | Deploy those models locally first, then request the label. |
| 6–15 models | Either | Batch: accumulate fixes, test code-changed models locally, then label. |
| >15 models | — | Batch everything. Test every `models_with_code_changes` model locally. Never label with a known failure. |
| any | Yes | Treat as the >15 row — a commons change can fan out to all models (all in default mode; the smart-mode import subset, or all on fallback, in `deploy.yml`). |

Before pushing, if CI (style/mypy/unit) is currently running, note that **pushing now CANCELS the
in-progress run** — wait, or use `gh run rerun <id> --failed` to retrigger only the failed jobs.

### Which Models to Test Locally

Test the models in `models_with_code_changes` (those with direct file changes). These are most likely to fail. Models triggered only by commons inheritance are lower risk.
