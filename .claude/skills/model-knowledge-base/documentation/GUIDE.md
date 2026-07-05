# Phase 3: Documentation

## Purpose

Author the three human-readable knowledge-graph files from the primary paper and the implemented
code: `README.md` (API reference), `MODEL.md` (technical depth), and `BIOLOGY.md` (biological
context). Follow the templates in `models/dummy/` exactly — they are the authoritative format.

## Prerequisites

- Phase 1 (`sources.yaml`) and Phase 2 (`comparison.yaml`) complete.
- Primary paper(s) read; `models/<slug>/` code (`config.py`, `schema.py`, `app.py`) available to read
  for actions, variants, and resource requirements.

---

## The three files (copy the template, then fill it in)

Start each file by copying the matching `models/dummy/*` template and replacing the placeholders.
**All non-`[OPTIONAL]` sections are required**; include an `[OPTIONAL]` section only when it applies,
and delete it otherwise (do not leave it empty).

### `README.md` — API reference (`models/dummy/README.md`)
Required sections: Overview, Architecture, Model Variants, Capabilities & Limitations,
**Actions / Endpoints** (a row per action with the canonical verb + the request/response fields),
Usage Examples, Performance & Benchmarks, Implementation Verification, Resource Requirements,
Implementation Notes, License. Use the canonical action verbs (`predict`/`fold`/`encode`/`generate`/
`score`/`log_prob`) and the canonical schema field names — read them from the model's `schema.py`.

### `MODEL.md` — technical details (`models/dummy/MODEL.md`)
Required sections: Architecture, Performance & Benchmarks, Strengths & Limitations,
Implementation Details, Versions & Changelog. This is where full technical depth lives — README.md
only summarizes.

### `BIOLOGY.md` — biological context (`models/dummy/BIOLOGY.md`)
Required sections: Molecule Coverage, Biological Problems Addressed, Applied Use Cases,
Related Models, Biological Background.

---

## Steps

1. **Read the code first.** `config.py` gives variants, actions, and resource specs; `schema.py`
   gives exact input/output field names. The docs must match the code, not the paper's notation.
2. **Author `README.md`** from the template. The Actions / Endpoints table must list each real action
   and its fields verbatim from `schema.py`.
3. **Author `MODEL.md`** — architecture and training from the paper; benchmarks only with explicit
   citations (e.g. "Table 2 of Lin et al., 2023"). Never estimate a number.
4. **Author `BIOLOGY.md`** — molecule coverage, the biological problem, and concrete applied use cases.
5. **Cross-link** all three (and `sources.yaml`/`comparison.yaml`) at the bottom of each file.

---

## Quality Criteria

- Every benchmark number is traceable to a paper table/figure with a citation; no fabricated numbers.
- README.md summarizes; MODEL.md has the depth. Do not copy paragraphs between them.
- Action verbs and schema field names match `models/<slug>/schema.py` and the Global Rules.
- No internal references (no internal repo or service names, no internal R2 uploads, no billing/redis layer).

---

## Gate Criteria

- [ ] `README.md`, `MODEL.md`, `BIOLOGY.md` created in `models/<slug>/` from the `models/dummy/` templates
- [ ] All required (non-`[OPTIONAL]`) sections present; inapplicable `[OPTIONAL]` sections removed
- [ ] Actions / Endpoints table matches the model's real actions + `schema.py` fields
- [ ] Every benchmark cited to a specific paper location
- [ ] The three files cross-link each other
