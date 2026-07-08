# Contributing

Thanks for helping grow the catalog. The whole point of `biolm-hub` is **uniformity** — the diff
between any two models should be the science, not the plumbing. These are the rules that keep it that
way. (The *why* behind them is in [`PHILOSOPHY.md`](PHILOSOPHY.md).)

## Getting set up

```bash
make install          # venv + all dev deps via uv, and pre-commit hooks
make style            # ruff + black + hygiene hooks
make mypy             # static type checking (enforced, --strict)
make test-unit        # fast tests — no Modal, no R2
```

`make check` runs the every-PR safe gate: **style + mypy + schema-doc check + CI-script tests + unit
tests** (no Modal, no R2). Keep it green locally before you push. The docs build (`make docs`, i.e.
`mkdocs build --strict`) is a separate check — run it after touching any schema, `Field(description=)`,
or root doc.

### Auto-activate with direnv (optional)

The repo ships a committed `.envrc` so [direnv](https://direnv.net) gives you "`cd` in and everything
just works": the uv `.venv` is on your PATH (so `bh`, `pytest`, `pre-commit` resolve directly) and a
local `.env` is loaded — no `source .venv/bin/activate` needed.

```bash
brew install direnv          # then add the shell hook: https://direnv.net/docs/hook.html
direnv allow                 # once per clone/worktree, and after editing .envrc
cp .env.example .env         # optional: your local Modal/R2 config (gitignored)
```

`.env.example` documents every environment variable the repo reads — all optional. Real secrets live
only in the gitignored `.env`; **never commit `.env`**. Without direnv, `source .venv/bin/activate` (or
`uv run …`) works exactly as before.

## Adding a model

> **Using an AI coding agent?** This guide is the **policy & house-rules reference**; the step-by-step
> build recipe lives in the Claude Code skills under `.claude/skills/`. Point the agent at
> **`model-implementation`** (implement → validate → deploy → document → review) and
> **`model-knowledge-base`** (the five knowledge-graph files) — both defer to *this* document for
> policy. Humans: read on. Either way, start from `models/dummy/`.

Start from **`models/dummy/`** (the template) and keep the standard layout:

```
models/<name>/
  app.py          # the Modal app + the action methods
  config.py       # ModelFamily: variants, action schemas, the modal_class_name
  schema.py       # request/response Pydantic models
  test.py         # the TestSuite (integration + deployment cases)
  download.py     # (if the model has weights) how to fetch them
  sources.yaml    # license, papers, source repos          ┐
  comparison.yaml # strengths/weaknesses, when-to-use, alts │ the knowledge graph —
  README.md       # API reference                           │ required, not optional
  MODEL.md        # architecture, training, benchmarks       │
  BIOLOGY.md      # the biology, applied use-cases           ┘
```

**License first — this section is canonical** (the skills defer to it). **Accepted:** MIT, Apache-2.0,
BSD-3-Clause (and compatible permissive licenses), plus **CC-BY-4.0** (common for model *weights*).
**GPL / copyleft** is accepted **only after a maintainer reviews the copyleft reach** for
redistribution and serving — flag it in the PR and ask; don't assume. **Not accepted:** CC-BY-NC and
other non-commercial or "academic only" terms, and proprietary licenses. Code and weights can carry
*different* licenses (e.g. MIT code, CC-BY-NC weights) — the more restrictive one governs. Declare the
license in `sources.yaml`, include a per-model `LICENSE`/attribution file, and never vendor weights or
code you can't redistribute.

## House rules (the "Global Rules")

These are uniform across every model. CI and review enforce them.

### Actions
The canonical action set is closed:

| Verb | Means |
|------|-------|
| `predict` | a scalar/label property of a sequence or structure — **or** masked-token / fill-mask prediction (mind the payload for large-vocab LMs; the `model-implementation` skill has the detail) |
| `fold` | 3D structure prediction (returns `pdb`/`cif` + confidence) |
| `encode` | learned representations / embeddings |
| `generate` | produce new sequences or structures (sampling, infilling, inverse folding, design) |
| `score` | a model-defined scalar fitness (document what it means) |
| `log_prob` | a per-sequence (pseudo) log-likelihood scalar |

Pick the verb that matches the *intent*. A folding model uses `fold`, not `predict`. Don't invent new
verbs.

### Schema field names
Field names are uniform across families; the *biology* lives in the model's metadata/tags, not in the
field names:

- **Inputs:** `sequence` / `sequences` / `msa`; `pdb` / `cif`; `smiles` (+ `ccd`); `name`; batch items
  under `items`, parameters under `params`.
- **Antibodies:** `heavy_chain` / `light_chain`. A nanobody/VHH is a lone `heavy_chain` on a model
  tagged as single-domain — there is no `vhh`/`nanobody` field. TCR chains are
  `tcr_alpha`/`tcr_beta`/`tcr_gamma`/`tcr_delta`, plus `peptide` and `mhc`.
- **Outputs:** `embeddings`, `logits`, `log_prob`, `score`, generated `sequence`, `pdb`/`cif`,
  `plddt`/`ptm`/`pae`; batch results under `results`.

When renaming for compatibility, keep the old name working via a Pydantic field alias.

Every field must carry `Field(..., description="...")` — that description is the *only* thing that
renders in the OpenAPI/JSON schema and on the docs site (plain `#` comments do not). For shared field
names, reuse the canonical wording in `tooling/field_glossary.yaml` so descriptions don't drift across
models; `tooling/check_schema_docs.py` (a unit test) fails CI on an undocumented field or one that
diverges from the glossary.

### Logging
Use the shared logger; never `print` in runtime code:

```python
from models.commons.core.logging import get_logger

logger = get_logger(__name__)
```

`print()` is rejected by lint everywhere except the CLI, scripts, and tests. Levels: `debug` for
internals, `info` for lifecycle, `warning` for degraded/fallback, `error` for failures (with
`exc_info=True`). Never log full sequences or secrets.

### Errors
Raise a typed user error for a caller's mistake (it's surfaced verbatim with a stable `code`); let
system errors propagate (they're sanitized). Never raise a bare `Exception`/`ValueError` for bad
input, and never catch-and-`print`.

### Code style
Modern, typed Python: full type hints (mypy is enforced), Pydantic v2, pinned exact dependency
versions, `ruff` + `black`. Run `make style && make mypy` before pushing.

## Testing

Tests are the coherence mechanism. There are four tiers:

| Tier | What | Needs |
|------|------|-------|
| Static | `make style`, `make mypy`, `make check-schema-docs`, `pytest --collect-only` | nothing |
| Unit | `make test-unit` | nothing |
| Integration | deploy to a Modal env + golden fixtures | Modal env + R2 |
| Deployment | run against a live endpoint | Modal env + R2 |

- **Generate fixtures, then run the file:** run `python models/<name>/fixture.py` to produce the golden
  fixtures, then `python -m pytest models/<name>/test.py`. Writing *public* goldens needs your own R2
  bucket + credentials; the public catalog's goldens are maintainer-populated (the `model-implementation`
  skill's `validation/GUIDE.md` has the mechanics).
- The **golden output is the oracle** — don't regenerate goldens to force a test green. Regenerate
  only when an output change is *intended*, and say so in the PR.
- **Reuse shared test assets** rather than hardcoding a standard sequence in your fixture. Standard
  cross-model inputs live in `models/commons/testing/shared_assets.py` as importable constants
  (e.g. `from models.commons.testing.shared_assets import STANDARD_PROTEIN`). Larger shared inputs
  live in public R2 under the canonical convention `test-data/shared/<category>/<name>.<ext>` — a
  fixture path beginning with `shared/` resolves there instead of your per-model directory.
- Cover the testable code paths you add. Coverage is a local diagnostic, not an enforced gate —
  `make test-unit` and CI run with `--no-cov` for speed; run `uv run pytest` (no `--no-cov`) to see a
  report with missing lines.

### Verify your model

Before opening a PR for a new or changed model, confirm it lands in house style and actually runs:

- **`make check`** must be green — this is the every-PR safe gate (style, mypy, the schema-doc check,
  CI-script tests, and unit tests). It runs Modal-free, so anyone can run it locally.
- **Added or renamed a model? Regenerate the catalog index** — `python -m tooling.gen_model_catalog`,
  then commit `models/README.md`. Skipping this leaves `make check` red on the stale index.
- **`make docs`** must build (`mkdocs build --strict`) — your model's page is generated from its
  config + knowledge graph, so schema or KB mistakes surface here.
- **Generate goldens and run the model's test file** against a Modal deployment:
  `python -m pytest models/<name>/test.py`. The golden output is the oracle — regenerate goldens only
  when an output change is *intended*, and say so in the PR. Integration and deployment tests
  (which need a Modal env + R2) run in the maintainer-gated `deploy.yml` workflow once a maintainer
  applies the `deploy-approved` label and approves the `biolm-hub-dev` deploy (see
  [Continuous integration and deploys](#continuous-integration-and-deploys)).

## Pull requests

- One coherent change per PR; keep `make check` green.
- Fill out the PR template (`.github/PULL_REQUEST_TEMPLATE.md`) — it's the house-rules checklist.
- For a new or significantly changed model, have a **fresh-context reviewer** (a different person, or a
  fresh agent session) read the full diff — same-context self-review misses things.
- Fix failures locally before pushing — don't push just to re-trigger CI.
- Be kind and assume good faith.

## Continuous integration and deploys

CI is **two-tier, split by trust** — cheap, safe checks run automatically, while anything that spends
Modal/R2 or touches secrets is maintainer-gated.

**Tier 1 — automatic, no secrets** (`.github/workflows/ci.yml`). Runs on every push and PR (forks
included), because it never needs Modal, R2, or any secret:

- **lint · types · unit** — style (ruff + black + hooks) + mypy + the schema-doc check + the CI
  change-detection script tests + unit tests. This job is exactly `make check`, so keep it green
  locally before you push.
- **docs build** — `mkdocs build --strict` (the same as `make docs`).
- **secret scan** — gitleaks.

**Tier 2 — maintainer-gated, secret-bearing** (`.github/workflows/deploy.yml`). The expensive Modal
deploy + integration/deployment tests. Opening or updating a PR does **not** trigger this — it runs
only when a maintainer clears **both** gates:

1. **adds the `deploy-approved` label** to the PR (applying a label needs repo write, so only a
   maintainer can start the pipeline), and
2. **approves the `biolm-hub-dev` GitHub Environment** — the deploy job pauses for a required reviewer,
   and the approval prompt shows the exact commit SHA before any secret is exposed.

Once both gates pass, the affected models — computed by `.github/scripts/detect_models.py`, where a
change under `models/commons/` fans out to every model that imports it — are deployed to the
`biolm-hub-dev` Modal environment and their integration + deployment tests run. A maintainer can also
run the pipeline manually from the Actions tab (**workflow_dispatch**), passing the model slugs to
deploy.

The `deploy-approved` label pins the run to the commit it was added on; a later push does **not**
deploy, so the code that runs is exactly what was reviewed. To ship a newer commit, re-review and then
remove and re-add the label.

> **Maintainers:** approving runs the PR's *code* (`config.py`/`app.py`) on Modal with credentials in
> scope, so **review the full diff before labeling** (one approval can fan out to *every* model if
> `models/commons/` changed). One-time setup: create the `deploy-approved` label and a `biolm-hub-dev`
> GitHub Environment with **required reviewers**, and store `MODAL_TOKEN_*`, `R2_*`, and the
> `BIOLM_HUB_DEV_ENVIRONMENT_SENTINEL` as **environment** secrets (never repo-wide — the workflow's
> preflight fails fast otherwise). Scope the Modal token to the `biolm-hub-dev` workspace and the R2
> creds to a read-only dev bucket. Full details are in the header of `.github/workflows/deploy.yml`.
