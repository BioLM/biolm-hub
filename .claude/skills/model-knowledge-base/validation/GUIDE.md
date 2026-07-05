# Phase 4: Validation

## Purpose

Cross-check the five knowledge-graph files against each other, the model's code, and the primary
paper before opening the PR. Catch drift, fabricated numbers, and broken references.

## Prerequisites

- Phases 1–3 complete: `sources.yaml`, `comparison.yaml`, `README.md`, `MODEL.md`, `BIOLOGY.md` all
  exist in `models/<slug>/`.

---

## Checks

### 1. Consistency against the code
- Action verbs in `README.md` match `models/<slug>/config.py` / `schema.py` exactly (canonical set:
  `predict`/`fold`/`encode`/`generate`/`score`/`log_prob`).
- Schema field names in the README's Actions table match `schema.py` verbatim.
- Variants listed in `README.md`/`MODEL.md` match `config.py`.
- Resource requirements match the model's Modal resource spec.

### 2. Consistency against the paper
- Every benchmark number cites a specific paper location; no estimated or rounded-without-source values.
- Architecture and training claims trace to the paper.

### 3. Consistency across the docs
- The license in `sources.yaml`, the README License section, and any per-model `LICENSE` agree.
- All model slugs referenced in `comparison.yaml` (`alternatives`, `complements`) exist under `models/`.
- `README.md`, `MODEL.md`, `BIOLOGY.md` cross-link each other.
- No paragraph duplicated between README.md and MODEL.md.

### 4. Syntax + style + docs build
- `python -c "import yaml; yaml.safe_load(open('models/<slug>/sources.yaml'))"` — valid.
- `python -c "import yaml; yaml.safe_load(open('models/<slug>/comparison.yaml'))"` — valid.
- `make style` passes (it lints docs/YAML hygiene too).
- `make docs` passes (`mkdocs build --strict`). The model's doc page is **generated** from these
  knowledge-graph files + `config.py`, and CI runs the docs build as a **separate job** — a broken
  cross-link, malformed markdown table, or bad YAML here fails CI even when `make style`/`make check`
  are green.

---

## Gate Criteria

- [ ] Actions + schema fields in the docs match `schema.py`/`config.py`
- [ ] Every benchmark number is cited; no fabricated values
- [ ] License agrees across `sources.yaml`, README, and `LICENSE`
- [ ] All referenced model slugs exist in `models/`
- [ ] `sources.yaml` and `comparison.yaml` are valid YAML
- [ ] `make style` passes
- [ ] `make docs` passes (mkdocs --strict — the generated model page builds)

When all boxes are checked, the knowledge graph is complete and ready for the PR.
