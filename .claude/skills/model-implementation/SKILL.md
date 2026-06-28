---
name: model-implementation
description: Complete workflow for implementing new biological models on biolm-models. Use when adding a model from a paper, HuggingFace, or GitHub. Covers investigation, implementation, validation, and documentation.
---

# BioLM Model Implementation Workflow

## Purpose

This skill guides implementing new biological language models in the `biolm-models` catalog.

Use for:
- New model implementation from a paper / HuggingFace / GitHub
- Review of an existing model implementation
- Verifying implementation correctness

## CRITICAL RULES

### 1. Do NOT modify `models/commons/`

`models/commons/` is READ-ONLY during model implementation. Conform to existing APIs. If commons genuinely needs a change, stop and raise it separately.

### 2. `make check` is MANDATORY

`make check` runs style + mypy + unit tests — exactly what CI runs on every PR. Run it locally before pushing. Never push with `make check` failing.

### 3. Follow phase order — no skipping

Complete phases in order. Each has a gate. Do NOT jump ahead.

---

## Workflow Overview (4 Phases)

### Phase 1: Investigation
Read: `investigation/GUIDE.md`

Gather information, check the license, find reference models, draft `sources.yaml`, determine variants/actions/resources.

**Gate:** License confirmed permissive; reference model(s) identified; actions/schemas approved.

---

### Phase 2: Implementation
Read: `implementation/GUIDE.md`

Write files in dependency order: `schema.py` → `config.py` → `download.py` (if needed) → `app.py` → `test.py` → `__init__.py`.

**Gate:** All files written; `make check` passes.

---

### Phase 3: Validation
Read: `validation/GUIDE.md`

`make check` (MANDATORY) + fixture generation + local deploy + integration tests. Deployment tests are optional locally; they run in CI once a maintainer applies `deploy-approved`.

**Gate:** `make check` green; unit tests pass; coverage ≥85%.

---

### Phase 4: Documentation
Read: `documentation/GUIDE.md`

Write `README.md` following `models/dummy/README.md`. Delegate the full knowledge graph (`sources.yaml`, `comparison.yaml`, `MODEL.md`, `BIOLOGY.md`) to the `model-knowledge-base` skill.

**Gate:** `README.md` complete; all knowledge-graph files present or delegated.

---

## Quick Start

```
Phase 1: Investigation
  → Read: investigation/GUIDE.md
  → Check LICENSE — stop if non-permissive
  → GATE: ref model identified, actions approved

Phase 2: Implementation
  → Read: implementation/GUIDE.md
  → Create files in order
  → GATE: make check passes

Phase 3: Validation
  → Read: validation/GUIDE.md
  → make check (MANDATORY)
  → python models/MODEL/fixture.py (before tests)
  → python -m pytest models/MODEL/test.py
  → GATE: coverage ≥85%

Phase 4: Documentation
  → Read: documentation/GUIDE.md
  → Write README.md
  → make check && git add && git commit
  → Create PR
```

---

## Global Rules (from `CONTRIBUTING.md`)

### Actions — closed set
| Verb | Means |
|------|-------|
| `predict` | scalar/label property of a sequence or structure |
| `fold` | 3D structure prediction (returns `pdb`/`cif` + confidence) |
| `encode` | learned representations / embeddings |
| `generate` | new sequences or structures (sampling, design, inverse folding) |
| `score` | model-defined scalar fitness (document what it means) |
| `log_prob` | per-sequence (pseudo) log-likelihood scalar |

Do not invent new verbs.

### Schema field names — uniform across families
- **Inputs:** `sequence` / `sequences` / `msa`; `pdb` / `cif`; `smiles`; batch items under `items`, parameters under `params`
- **Antibodies:** `heavy_chain` / `light_chain`; nanobody/VHH = lone `heavy_chain`; TCR = `tcr_alpha`/`tcr_beta`/`tcr_gamma`/`tcr_delta` + `peptide` + `mhc`
- **Outputs:** `embeddings`, `logits`, `log_prob`, `score`, `sequence`, `pdb`/`cif`, `plddt`/`ptm`/`pae`; batch results under `results`

### Logging — never `print` in runtime code
```python
from models.commons.core.logging import get_logger
logger = get_logger(__name__)
```

### Errors — typed, stable `code`
```python
from models.commons.core.error import UserError  # caller's mistake — surfaced verbatim
# ServerError — system failure — let it propagate; never catch-and-print
```

---

## Common Pitfalls (top 8)

1. **Non-permissive license** — check before coding anything (MIT/Apache-2.0/BSD only)
2. **`make check` failing on push** — run it locally first; never push with it red
3. **Running tests before generating fixtures** — always `python models/MODEL/fixture.py` first
4. **Unpinned dependencies** — every package must use `==X.Y.Z`
5. **Unpinned HuggingFace revisions** — use 40-char commit hash, never `"main"`
6. **Missing seeds** — set `torch`, `numpy`, `random`, `cuda` seeds for determinism
7. **Modifying `models/commons/`** — breaks all other models; raise as a separate change
8. **Wrong action verb** — use the closed set; folding = `fold`, not `predict`

See `resources/common_issues.md` for the full list.

---

## Resources

- `resources/quick_reference.md` — file creation order, essential commands, GPU tier table, import examples
- `resources/common_issues.md` — common pitfalls and fixes
- `models/dummy/` — the canonical template (copy this, don't invent from scratch)
