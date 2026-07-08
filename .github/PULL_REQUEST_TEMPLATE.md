## What & why

<!-- One coherent change per PR. Describe what changed and why — not just a diff summary. -->

## Type of change

- [ ] New model
- [ ] Fix (model, framework, CLI, gateway, or docs)
- [ ] Framework / commons change (`models/commons/`)
- [ ] CI/CD
- [ ] Docs only
- [ ] Other

## The gate (required for every PR)

- [ ] `make check` is green locally (style + mypy `--strict` + schema-doc check + CI-script tests + unit tests).
- [ ] `make docs` builds (`mkdocs build --strict`) — required if this touches any schema, `Field(description=...)`, or root doc.
- [ ] I didn't push just to re-trigger CI — failures were reproduced and fixed locally first.

## Adding or changing a model? (skip this section otherwise)

- [ ] Started from `models/dummy/` and kept the standard layout (`app.py` / `config.py` / `schema.py` / `test.py` / `download.py` if it has weights).
- [ ] Actions use only the closed verb set (`predict`, `fold`, `encode`, `generate`, `score`, `log_prob`) — the verb matches intent.
- [ ] Schema field names follow the uniform conventions in [`CONTRIBUTING.md`](../CONTRIBUTING.md) (`sequence`/`items`/`params`, `heavy_chain`/`light_chain`, `embeddings`, `pdb`/`cif`, …); renamed fields keep a back-compat alias.
- [ ] Every schema field has `Field(..., description="...")`; shared field names match the wording in `tooling/field_glossary.yaml`.
- [ ] The five knowledge-graph files are authored: `sources.yaml`, `comparison.yaml`, `README.md`, `MODEL.md`, `BIOLOGY.md` — license declared in `sources.yaml` and permitted by [`CONTRIBUTING.md`](../CONTRIBUTING.md) → "License first" (permissive + CC-BY-4.0; GPL only after maintainer review).
- [ ] Goldens generated and the model's test file passes: `python -m pytest models/<name>/test.py`. If goldens changed, it's because the output change is *intended* — say so below.
- [ ] Structured logging only (`models.commons.core.logging.get_logger`), typed errors (no bare `ValueError`/`Exception` for caller mistakes).

## Goldens / test changes (if any)

<!-- If you regenerated golden fixtures, explain what changed and why the new output is correct. -->

## Notes for reviewers

<!-- Anything a reviewer should know: follow-ups deferred, deploy/integration testing not yet run, etc. -->

---
See [`CONTRIBUTING.md`](../CONTRIBUTING.md) for the full contributor guide, including how the
maintainer-gated deploy + integration/deployment workflow works.
