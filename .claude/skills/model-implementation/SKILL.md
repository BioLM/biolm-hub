---
name: model-implementation
description: Complete workflow for implementing, porting, reviewing, and validating biological models on biolm-hub. Use when adding a model from a paper, HuggingFace, or GitHub, when porting or adapting a reference model, or when reviewing, verifying, or validating a model implementation for correctness and house style. Covers investigation, implementation, validation, documentation, and review.
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

## Workflow Overview (5 Phases)

### Phase 1: Investigation
Read: `investigation/GUIDE.md`

Gather information, check the license, find reference models, draft `sources.yaml`, determine variants/actions/resources.

**Gate:** License confirmed permissive; **scope in-bounds** (no Modal Volume / server-side reference DB / server-side MSA search); reference model(s) identified; actions/schemas approved.

---

### Phase 2: Implementation
Read: `implementation/GUIDE.md`

Write files in dependency order: `schema.py` → `config.py` → `download.py` (if needed) → `app.py` → `test.py` → `__init__.py`.

**Gate:** All files written; `make check` passes.

---

### Phase 3: Validation
Read: `validation/GUIDE.md`

`make check` (MANDATORY) + `make docs` (mkdocs --strict — the model's generated page must build) + golden fixture generation (input + output) + a `biolm-hub-dev` deploy with at least one live inference smoke call (REQUIRED if you have Modal credentials; credential-less contributors flag it unverified in the PR — see `validation/GUIDE.md §3.5`) + integration tests. The full integration/deployment matrix also re-runs in CI once a maintainer applies `deploy-approved`.

**Gate:** `make check` green; `make docs` green; unit tests pass; coverage ≥85%; golden input + golden output recorded in R2 and loaded by an integration test, compared with the tolerance mode that matches the output type (goldens are the default even for stochastic models — see `implementation/GUIDE.md §2.5`; a custom `validator=` only where the contract can't be expressed as a tolerance, justified in the PR); with Modal credentials, a `biolm-hub-dev` deploy + one live inference call succeeded (credential-less: stated unverified in the PR — see `validation/GUIDE.md §3.5`).

> **Docs build ordering:** the per-model page is generated from `config.py` **and** the
> knowledge-graph files authored in Phase 4 (`README.md`/`MODEL.md`/`BIOLOGY.md`, cross-links,
> tables). The Phase 3 `make docs` run only confirms nothing is hard-broken (config/schema); the
> *meaningful* strict build is the one you re-run at the **end of Phase 4**, once the KG content the
> page renders actually exists.

---

### Phase 4: Documentation
Read: `documentation/GUIDE.md`

Invoke the `model-knowledge-base` skill **before the PR** to author all five knowledge-graph files (`README.md`, `MODEL.md`, `BIOLOGY.md`, `sources.yaml`, `comparison.yaml`). That skill **owns** all five — this phase only invokes it (`config.py`/`schema.py`/`app.py` from Phase 2 must already exist).

**Gate:** all five knowledge-graph files present and passing the `model-knowledge-base` validation.

---

### Phase 5: Review

A **separate reviewer with fresh context** — spawn a subagent; same-context self-review is biased
(`CLAUDE.md`) — reviews the full diff against the four dimensions below. The Phase 2 self-review
checklist (`implementation/GUIDE.md`) and the Phase 3/4 gates *feed* this review; they do not replace it.

When `model-knowledge-base` was invoked in Phase 4, its blind re-derivation of every fabricatable value
— benchmark numbers, author surnames, DOIs, from the primary source — folds into this single Phase 5
review rather than running as a separate pass.

1. **Schema uniformity** — field names match the uniform house rules (`sequence`/`sequences`/`msa`,
   `smiles`, batch `items`, `params`, `heavy_chain`/`light_chain`,
   `embeddings`/`logits`/`log_prob`/`score`/`plddt`/`ptm`/`pae`, batch `results`) and are **not**
   copied from the reference model; any rename preserves the old name via `AliasChoices` (input only).
2. **Action verbs** — every action is in the closed set (`predict`/`fold`/`encode`/`generate`/`score`/`log_prob`)
   and matches intent (a folding model `fold`s; it does not overload `predict`).
3. **Typed errors + logging** — caller mistakes raise the most specific `UserError` subclass (no bare
   `ValueError` in `app.py` action code); `get_logger` only, never `print`; no full sequences or
   secrets logged.
4. **Field descriptions + docs** — every schema field has a *rendered* `Field(description=...)`
   consistent with `tooling/field_glossary.yaml`; `make check` and `make docs` are green.

**Gate:** Phase 5 complete when a fresh-context reviewer signs off on all four dimensions.

---

## Command Runbook

The phase map and its gates live in the Workflow Overview above; this is only the command sequence.
Read each phase's `GUIDE.md` for the detail.

```bash
# Phase 1 is investigation — no commands. Phases 2 → 4:
make check                                # style + mypy + schema-doc + CI-script + unit (CI's `checks` job)
make docs                                 # mkdocs --strict (separate CI job — the generated page must build)
python -m tooling.gen_model_catalog       # refresh models/README.md (else test_readme_catalog_is_fresh fails)
python models/<name>/fixture.py           # record golden input + output BEFORE tests (template: models/dummy/fixture.py)
python -m pytest models/<name>/test.py
MODAL_ENVIRONMENT=biolm-hub-dev bh deploy <name> --force   # + one live call (REQUIRED with Modal creds; else flag unverified in PR)
```

Then invoke `model-knowledge-base` for all five knowledge-graph files (before the PR), and spawn a
fresh-context reviewer (Phase 5) over the full diff.

---

## Global Rules — canonical in `CONTRIBUTING.md`

**`CONTRIBUTING.md` → "House rules" is the source of truth** for the closed verb set, schema field
names, licensing, logging, and errors — read it, don't restate it. This recap is only what bites
during implementation.

### Actions — closed set
`predict` · `fold` · `encode` · `generate` · `score` · `log_prob`. Pick the verb that matches intent —
a folding model `fold`s, it doesn't overload `predict`. Don't invent verbs.

> `predict` covers masked-token / fill-mask prediction as well as scalar/label prediction. For a
> **large-vocabulary** LM, returning full per-position logits bloats the payload — prefer `log_prob`
> and/or `encode`. Payload sizing and the `esm2` fill-mask example: `implementation/GUIDE.md §2.2`.

### Schema field names
Uniform across families; the biology lives in metadata/tags, not field names (canonical list in
`CONTRIBUTING.md`). Inputs: `sequence` / `sequences` / `msa`; `pdb` / `cif`; `smiles` (+ `ccd`);
`name`; batch items under `items`, parameters under `params`. Antibodies: `heavy_chain` /
`light_chain` (nanobody/VHH = lone `heavy_chain`); TCR = `tcr_alpha`/`tcr_beta`/`tcr_gamma`/`tcr_delta`
+ `peptide` + `mhc`. Outputs: `embeddings`, `logits`, `log_prob`, `score`, `sequence`, `pdb`/`cif`,
`plddt`/`ptm`/`pae`; batch results under `results`.

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
Raise the **most specific** `UserError` subclass for a caller mistake in `app.py` action code; let
system errors propagate (they're sanitized to 5xx). A Pydantic validator raising a plain `ValueError`
is correct — that rule is about imperative checks in `app.py`, not validators. Full taxonomy table and
worked cases: `implementation/GUIDE.md §2.4`.

---

## Common Pitfalls (the five that bite first)

1. **Non-permissive license** — check before writing any code (permissive + CC-BY-4.0; GPL needs maintainer review — see `investigation/GUIDE.md §1.1`).
2. **Out-of-scope infrastructure** — needs a Modal Volume, a server-side reference DB (UniRef/BFD/MGnify/PDB70), or server-side MSA/template search → **STOP before coding or deploying** (`investigation/GUIDE.md §1.2`). The catalog takes MSAs as an `msa`/`alignment` request input; it does not host databases or run alignment on the endpoint.
3. **`make check` red on push** — run it locally first; never push to re-trigger CI.
4. **Tests before fixtures** — always `python models/<name>/fixture.py` first.
5. **Editing `models/commons/`** — read-only during model work; raise commons changes separately.

Full list (dependencies, HF revisions, seeds, tokenizers, mypy, action verbs, resource tiers, …):
`resources/common_issues.md`.

---

## Resources

- `resources/quick_reference.md` — file creation order, essential commands, GPU tier table, import examples
- `resources/common_issues.md` — common pitfalls and fixes
- `resources/model_upgrade_tiers.md` — dependency/upgrade risk tiers (GREEN/YELLOW/RED) for choosing or bumping a model's Python + package pins
- `investigation/GUIDE.md §1.4` — the reference-model selection table (which shipped model to copy for protein / DNA / structure / folding / HF-weights / no-weights inputs)
- `models/dummy/` — the canonical template (copy this, don't invent from scratch)
