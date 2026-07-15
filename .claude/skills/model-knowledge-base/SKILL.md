---
name: model-knowledge-base
description: Author a model's knowledge graph in biolm-hub — the five files sources.yaml, comparison.yaml, README.md, MODEL.md, and BIOLOGY.md for one model. Use when adding a new model, when improving an existing model's knowledge graph, and when the model-implementation flow reaches its documentation phase; also runs standalone. Applies to any model whose sources are public on arXiv/bioRxiv/GitHub/HuggingFace.
---

# Model Knowledge Base

## Purpose

Author the five knowledge-graph files required for every model in `biolm-hub`. These files are
not optional -- see `CONTRIBUTING.md`, which is also the canonical source for house rules and the
accepted-license policy (this skill authors the knowledge graph; it doesn't restate policy). The
standard layout is:

```
models/<slug>/
  sources.yaml    # license, papers, source repos
  comparison.yaml # strengths/weaknesses, when-to-use, alts
  README.md       # API reference
  MODEL.md        # architecture, training, benchmarks
  BIOLOGY.md      # the biology, applied use-cases
```

All templates live in `models/dummy/`. Point at those -- do not duplicate them here.

> **R2 population note**: Uploading PDFs, markdown conversions, and repo snapshots to R2 is a
> maintainer operation and is out of scope for external contributors. Leave `pdf_r2`, `md_r2`,
> `snapshot_r2`, and `page_md_r2` fields in `sources.yaml` as `""` and move on.

> **Invoked from `model-implementation`.** This skill is called from the documentation phase (Phase 4)
> of the `model-implementation` workflow — and its output is checked in that workflow's Phase 5 review.
> It **owns all five** KG files, including `README.md`. It can also run standalone. Either way, the
> model's `config.py`, `schema.py`, and `app.py` must already exist (Phase 2 of `model-implementation`):
> author the code first, then the knowledge graph.

## Critical Rules

1. **Never fabricate — this rule outranks every count and every template field.** Every benchmark
   number, DOI, author name, venue, and citation must come from a source you have actually read: a
   paper table or figure, a LICENSE file, a model card. When an honest, exhaustive search comes up
   short — fewer than three applied papers, an unresolved license, a benchmark the paper doesn't
   report — write one line documenting the gap and move on. A target count or an empty template
   field is never a reason to invent a value. A documented gap passes every gate in this skill; an
   invented value fails review even when every box is checked.
2. **`models/commons/` is read-only.** Never edit it as part of KB work.
3. **License first.** Only permissively-licensed models (MIT / Apache-2.0 / BSD and compatible) are
   accepted. Verify the upstream license before writing any documentation.
4. **Templates from `models/dummy/`.** Not from this skill directory.
5. **Public sources only.** Read papers from arXiv/bioRxiv/DOI URLs and code from
   GitHub/HuggingFace. No internal R2 access is required to complete this skill.

## Workflow (4 Phases, in order)

| Phase | Output | Guide |
|-------|--------|-------|
| 1. Discovery | `sources.yaml` | `discovery/GUIDE.md` |
| 2. Comparison | `comparison.yaml` | `comparison/GUIDE.md` |
| 3. Documentation | `README.md`, `MODEL.md`, `BIOLOGY.md` | `documentation/GUIDE.md` |
| 4. Validation | All files cross-checked | `validation/GUIDE.md` |

Do not skip phases. Each phase gate must pass before the next begins. After Phase 4, the knowledge
graph is PR-ready only once `make style` and `make docs` both pass (`validation/GUIDE.md` runs these).

## Common Pitfalls

- **Forgetting the license** -- check the GitHub/HuggingFace LICENSE file, not just the API
  metadata field. Code and weights often have different licenses; document both and record the more
  restrictive one in `sources.yaml`. **If upstream ships no LICENSE file** (license declared only as a
  HuggingFace card metadata tag — common), record the SPDX id + a link to the card/canonical license
  text in `sources.yaml`/`LICENSE` and note it; don't get blocked on the missing file.
- **Fabricated benchmark numbers** -- only use values directly from papers with explicit citations
  (e.g., "Table 2 of Lin et al., 2023"). Never estimate.
- **Fabricated citations to hit the ≥3 applied-papers target** -- when an honest search finds fewer
  than three, document the gap; never invent one. Procedure: `discovery/GUIDE.md` Step 4.
- **Content duplication across MODEL.md and README.md** -- README.md has concise summaries;
  MODEL.md has full technical depth. Do not copy paragraphs between them.
- **Old action names** -- the canonical actions are `predict`, `fold`, `encode`, `generate`,
  `score`, `log_prob`. Do not use deprecated names (`predict_log_prob`, `extract_features`, `vhh`).
- **Missing cross-references** -- README.md, MODEL.md, and BIOLOGY.md must link to each other at
  the bottom of each file.
- **Cross-model or YAML links in prose** — never link another model or a `.yaml` file by relative
  path in body prose; name other models in **bold + backtick slug** (e.g. **DNABERT-2** `dnabert2`).
  The docs generator rewrites cross-file links by filename alone, so a relative link silently
  misfires. Mechanics and the one allowed exception: `documentation/GUIDE.md` Step 5.
- **Non-permissive license** -- if you find a CC-BY-NC or custom non-commercial license, do not
  proceed. Flag it in the PR; the model may not be eligible for the catalog.
