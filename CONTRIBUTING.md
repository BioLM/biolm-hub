# Contributing

Thanks for helping grow the catalog. The whole point of `biolm-models` is **uniformity** — the diff
between any two models should be the science, not the plumbing. These are the rules that keep it that
way. (The *why* behind them is in [`PHILOSOPHY.md`](PHILOSOPHY.md).)

## Getting set up

```bash
make install          # venv + all dev deps via uv, and pre-commit hooks
make style            # ruff + black + hygiene hooks
make mypy             # static type checking (enforced)
make test-unit        # fast tests — no Modal, no R2
```

`make check` runs everything CI runs on every PR (style + mypy + unit). Keep it green locally before
you push.

## Adding a model

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

**License first.** Only permissively-licensed models (MIT / Apache-2.0 / BSD and compatible) are
accepted. Declare the license in `sources.yaml`, include a per-model `LICENSE`/attribution file, and
do not vendor weights or code you can't redistribute.

## House rules (the "Global Rules")

These are uniform across every model. CI and review enforce them.

### Actions
The canonical action set is closed:

| Verb | Means |
|------|-------|
| `predict` | a scalar/label property of a sequence or structure |
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

Tests are the coherence mechanism. There are four tiers (full detail in the testing strategy doc):

| Tier | What | Needs |
|------|------|-------|
| Static | `make style`, `make mypy`, `pytest --collect-only` | nothing |
| Unit | `make test-unit` | nothing |
| Integration | deploy to a Modal env + golden fixtures | Modal env + R2 |
| Deployment | run against a live endpoint | Modal env + R2 |

- **Generate fixtures, then run the file:** `python -m pytest models/<name>/test.py`.
- The **golden output is the oracle** — don't regenerate goldens to force a test green. Regenerate
  only when an output change is *intended*, and say so in the PR.
- Reuse the shared test assets (`test-data/shared/`) for standard sequences rather than duplicating.
- Target ≥85% coverage on testable code.

## Pull requests

- One coherent change per PR; keep `make check` green.
- Fix failures locally before pushing — don't push just to re-trigger CI.
- Be kind and assume good faith — see [`CODE_OF_CONDUCT.md`](CODE_OF_CONDUCT.md).

### How CI works

Two workflows, split by trust:

- **Every PR — safe checks** (`.github/workflows/ci.yml`): style + mypy + unit tests + the
  CI change-detection script tests + a docs build. No Modal, no R2, no secrets — so it runs on PRs
  from forks too. This is exactly what `make check` runs locally; keep it green before you push.
- **Maintainer-gated — deploy + integration/deployment** (`.github/workflows/deploy.yml`): the
  expensive Modal jobs. Opening or updating a PR does **not** trigger these. A maintainer reviews the
  change, then applies the **`deploy-approved`** label, which deploys the affected models to the dev
  Modal environment and runs their integration + deployment tests. The set of "affected models" is
  computed by `.github/scripts/detect_models.py` (a change under `models/commons/` fans out to every
  model that imports it).

**Pushing new commits revokes approval.** Any push to an approved PR automatically removes the
`deploy-approved` label, so the deploy always runs the exact commit a maintainer reviewed. Just ping a
maintainer to re-approve once your change is ready.

> **Maintainers:** approving runs the PR's *code* (`config.py`/`app.py`) on Modal with secrets in
> scope — **review the full diff before labeling**, and confirm the PR's HEAD is the commit you
> reviewed (the label deploys whatever HEAD is at click time). One approval can fan out to *every*
> model if `models/commons/` changed. One-time setup: create the `deploy-approved` label and configure
> a `modal-dev` GitHub Environment with **required reviewers**, holding the `MODAL_TOKEN_*` and `R2_*`
> secrets as **environment** secrets. Full details are in the header of `.github/workflows/deploy.yml`.
