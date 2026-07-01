# CLAUDE.md

Guidance for AI coding agents (and humans) working in **biolm-hub** — a standardized,
agent-first catalog of open biological ML models that deploy on [Modal](https://modal.com).

The whole point of this repo is **uniformity**: the diff between any two models should be the
science, not the plumbing. Hold that line.

## What this repo is

Every model lives under `models/<name>/` with an identical layout, the same action verbs, the same
request/response schema conventions, structured logging, a shared error taxonomy, and a
machine-readable knowledge graph. An agent that learns one model can use them all, and can add a new
one that lands in house style.

## Repo map

| Path | What |
|------|------|
| `models/<name>/` | One model: `app.py` (Modal app + action methods), `config.py` (`ModelFamily`: variants, action→schema map, `modal_class_name`), `schema.py` (request/response Pydantic models), `test.py` (`TestSuite`), `download.py` (weights, if any), and the knowledge graph (`sources.yaml`, `comparison.yaml`, `README.md`, `MODEL.md`, `BIOLOGY.md`). |
| `models/commons/` | The shared framework: config, decorators, Modal image helpers, R2 storage/download, the base Pydantic models, logging, the error taxonomy, and the testing harness. Changes here ripple to every model — change with care. |
| `models/dummy/` | The template. Start a new model by copying it. |
| `cli/` | The `bh` CLI (`setup`, `deploy`, `serve`, `cache`, `r2`, `kb`). |
| `gateway/` | A unified inference endpoint + the catalog web app (`bh serve`). |
| `docs/` | The mkdocs site. Per-model pages are **generated** from each model's config + knowledge graph by `docs/gen_pages.py` — don't hand-write per-model doc pages. |
| `tooling/` | Repo-quality tooling (e.g. the schema-description consistency checker). |

## House rules (CI and review enforce these)

- **Actions are a closed set:** `predict`, `fold`, `encode`, `generate`, `score`, `log_prob`. Pick
  the verb that matches intent (a folding model `fold`s, it doesn't overload `predict`). Don't invent
  verbs.
- **Schema field names are uniform across families;** the biology lives in metadata/tags, not field
  names. Inputs: `sequence`/`sequences`/`msa`, `pdb`/`cif`, `smiles`, batch items under `items`,
  parameters under `params`. Antibodies: `heavy_chain`/`light_chain` (a nanobody/VHH is a lone
  `heavy_chain` on a single-domain-tagged model — there is no `vhh` field). Outputs: `embeddings`,
  `logits`, `log_prob`, `score`, `pdb`/`cif`, `plddt`/`ptm`/`pae`; batch results under `results`.
  Preserve old names with a Pydantic alias when renaming.
- **Every schema field carries a `Field(..., description="...")`.** This is the *only* mechanism that
  renders in the OpenAPI/JSON schema and the docs site — plain `#` comments do not. Reuse the
  canonical wording in `tooling/field_glossary.yaml` for shared field names so descriptions stay
  consistent across models. `tooling/check_schema_docs.py` (a unit test) fails CI on an undocumented
  field or a shared field that drifts from the glossary.
- **Structured logging only.** `from models.commons.core.logging import get_logger`. `print()` is
  rejected by lint outside the CLI, scripts, and tests. Never log full sequences or secrets.
- **Typed errors.** Raise a typed user error for a caller's mistake (surfaced verbatim with a stable
  `code`); let system errors propagate (they're sanitized). Never raise a bare `ValueError` for bad
  input.
- **Modern, typed Python.** Full type hints (mypy is enforced), Pydantic v2, pinned **exact** ML
  dependency versions, `ruff` + `black`.

## Working in the repo

```bash
make install      # venv + all deps via uv, plus pre-commit hooks
make style        # ruff + black + hygiene hooks
make mypy         # static type checking (enforced)
make check        # everything CI runs on every PR: style + mypy + schema-doc check + CI-script tests + unit tests
make docs         # build the docs site (mkdocs --strict) — run after touching schemas or docs
```

- **Run a model's tests explicitly:** `python -m pytest models/<name>/test.py` (generate fixtures
  first). Don't rely on full-directory collection for a single model.
- Keep `make check` green locally **before** pushing — don't push just to re-trigger CI.
- For a significant change, have a separate reviewer pass over the diff with fresh context.

## Adding a model

1. Copy `models/dummy/` to `models/<name>/` and follow [`CONTRIBUTING.md`](CONTRIBUTING.md).
2. Implement `config.py` / `schema.py` / `app.py`; add `download.py` if it has weights (use the
   canonical `r2_then_hf` / `r2_then_library` / `r2_then_urls` wrappers so weights self-populate the
   public bucket — see `models/commons/storage`).
3. Document every schema field with `Field(description=...)`; author the five knowledge-graph files.
4. `make check` and `make docs` must be green; the model's page is generated automatically.

The `model-implementation` and `model-knowledge-base` skills under `.claude/skills/` walk through the
full flow.

## Deploying

```bash
bh setup                 # checks Modal (required) + R2 (optional) config
bh deploy <model>        # deploys to your Modal workspace
```

Deployed endpoints — and `bh serve --host 0.0.0.0` — are **unauthenticated** and bill your Modal
account. Don't expose them publicly without your own access control.

## More

- [`CONTRIBUTING.md`](CONTRIBUTING.md) — the full contributor guide, testing tiers, and how CI works.
- [`PHILOSOPHY.md`](PHILOSOPHY.md) — why the catalog is built the way it is.
- The docs site (`make docs`) renders every model's API schema and knowledge graph.
