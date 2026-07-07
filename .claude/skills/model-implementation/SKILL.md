---
name: model-implementation
description: Complete workflow for implementing new biological models on biolm-hub. Use when adding a model from a paper, HuggingFace, or GitHub. Covers investigation, implementation, validation, and documentation.
---

# BioLM Model Implementation Workflow

## Purpose

This skill guides implementing new biological language models in the `biolm-hub` catalog.

Use for:
- New model implementation from a paper / HuggingFace / GitHub
- Review of an existing model implementation
- Verifying implementation correctness

## CRITICAL RULES

### 1. Do NOT modify `models/commons/`

`models/commons/` is READ-ONLY during model implementation. Conform to existing APIs. If commons genuinely needs a change, stop and raise it separately.

### 2. `make check` is MANDATORY

`make check` runs style + mypy + schema-doc check + CI-script tests + unit tests — the same
checks as CI's main `checks` job. Run it locally before pushing; never push with `make check`
failing.

`make check` does **not** build the docs. CI runs a **separate `docs` job** (`mkdocs build
--strict`), and each model's page is generated from its `config.py` + knowledge-graph files — so a
model can pass `make check` and still fail CI on the docs build. Run `make docs` too (see Phase 3).

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

`make check` (MANDATORY) + `make docs` (mkdocs --strict — the model's generated page must build) + fixture generation + local deploy + integration tests. Deployment tests are optional locally; they run in CI once a maintainer applies `deploy-approved`.

**Gate:** `make check` green; `make docs` green; unit tests pass; coverage ≥85%.

> **Docs build ordering:** the per-model page is generated from `config.py` **and** the
> knowledge-graph files authored in Phase 4 (`README.md`/`MODEL.md`/`BIOLOGY.md`, cross-links,
> tables). The Phase 3 `make docs` run only confirms nothing is hard-broken (config/schema); the
> *meaningful* strict build is the one you re-run at the **end of Phase 4**, once the KG content the
> page renders actually exists.

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
  → make docs (mkdocs --strict — the generated page must build)
  → python -m tooling.gen_model_catalog (regenerate models/README.md — else test_readme_catalog_is_fresh fails)
  → python models/MODEL/fixture.py (before tests; template: models/dummy/fixture.py)
  → python -m pytest models/MODEL/test.py
  → GATE: coverage ≥85%

Phase 4: Documentation
  → Read: documentation/GUIDE.md
  → Write README.md
  → make check && make docs && git add && git commit
  → Create PR
```

---

## Global Rules (from `CONTRIBUTING.md`)

### Actions — closed set
| Verb | Means |
|------|-------|
| `predict` | scalar/label property of a sequence or structure, **or** masked-token / fill-mask prediction (see note) |
| `fold` | 3D structure prediction (returns `pdb`/`cif` + confidence) |
| `encode` | learned representations / embeddings |
| `generate` | new sequences or structures (sampling, design, inverse folding) |
| `score` | model-defined scalar fitness (document what it means) |
| `log_prob` | per-sequence (pseudo) log-likelihood scalar |

Do not invent new verbs.

> **`predict` legitimately covers masked-token / fill-mask prediction — but mind the payload for
> large-vocab LMs.** The shipped `esm2` model exposes masked-LM fill-mask as `predict`:
> `ESM2PredictRequest` takes sequences containing `<mask>` tokens and `ESM2PredictResponse` returns
> per-position `logits` + `sequence_tokens` + `vocab_tokens` (`models/esm2/schema.py`, mapped to
> `ModelActions.PREDICT` in `models/esm2/config.py`) — not a scalar. That is correct house style.
> **However**, returning full per-position logits is only cheap for a **small-vocabulary** model
> (esm2's protein alphabet is ~20 tokens → an `[L, 20]` matrix). For a **large-vocabulary** LM the
> `[L, |vocab|]` payload bloats fast — e.g. a chemical/BPE LM like ChemBERTa has a 7,924-token vocab,
> so a fill-mask `predict` would ship an `[L, 7924]` matrix per sequence. For large-vocab models
> prefer `log_prob` (one pseudo-log-likelihood scalar per sequence) and/or `encode` (embeddings)
> over a logits-returning `predict`.

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

The full taxonomy lives in `models/commons/core/error.py`. Raise the **most specific** subclass:

| Class | `code` | Raise when |
|-------|--------|-----------|
| `UserError` | `user.error` | generic caller mistake (user-facing base) |
| `ValidationError400` | `user.validation` | payload passes type checks but fails a business rule |
| `UnsupportedOptionError` | `user.unsupported_option` | caller asked for an option/variant/param the model doesn't support |
| `ResourceNotFoundError` | `user.resource_not_found` | a user-referenced resource/asset doesn't exist |
| `ServerError` / `ModelExecutionError` | `system.*` | internal failure — usually just let it propagate (sanitized to 5xx) |

**"No bare `ValueError`" applies to imperative checks in `app.py`, NOT to Pydantic validators.** A
field/model validator (`BeforeValidator`, `@field_validator`, `@model_validator`) raising a plain
`ValueError` is correct house style — Pydantic turns it into a 422. In the *action code*, raise a
typed subclass instead. (See `models/igbert/schema.py` validators raising `ValueError`, while its
`app.py` raises `ValidationError400`.)

---

## Common Pitfalls (top 8)

1. **Non-permissive license** — check before coding anything (MIT/Apache-2.0/BSD only)
2. **`make check` failing on push** — run it locally first; never push with it red
3. **Running tests before generating fixtures** — always `python models/MODEL/fixture.py` first
4. **Unpinned dependencies** — every package must use `==X.Y.Z`
5. **Unpinned HuggingFace revisions** — use 40-char commit hash, never `"main"`
6. **Missing seeds** — set `torch`, `numpy`, `random`, `cuda` seeds for determinism (**stochastic/torch models only** — deterministic CPU/algorithmic tools like `dna_chisel`/`biotite` need none)
7. **Modifying `models/commons/`** — breaks all other models; raise as a separate change
8. **Wrong action verb** — use the closed set; folding = `fold`, not `predict`

See `resources/common_issues.md` for the full list.

---

## Resources

- `resources/quick_reference.md` — file creation order, essential commands, GPU tier table, import examples
- `resources/common_issues.md` — common pitfalls and fixes
- `models/dummy/` — the canonical template (copy this, don't invent from scratch)
