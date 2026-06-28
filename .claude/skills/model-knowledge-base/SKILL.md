---
name: model-knowledge-base
description: Author the five knowledge-graph files (sources.yaml, comparison.yaml, README.md, MODEL.md, BIOLOGY.md) for a model in biolm-models. Use when adding a new model or improving existing documentation for a model whose sources are publicly available on arXiv/bioRxiv/GitHub/HuggingFace.
---

# Model Knowledge Base

## Purpose

Author the five knowledge-graph files required for every model in `biolm-models`. These files are
not optional -- see `CONTRIBUTING.md`. The standard layout is:

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

## Critical Rules

1. **`models/commons/` is read-only.** Never edit it as part of KB work.
2. **License first.** Only permissively-licensed models (MIT / Apache-2.0 / BSD and compatible) are
   accepted. Verify the upstream license before writing any documentation.
3. **Templates from `models/dummy/`.** Not from this skill directory.
4. **Public sources only.** Read papers from arXiv/bioRxiv/DOI URLs and code from
   GitHub/HuggingFace. No internal R2 access is required to complete this skill.

## Workflow (4 Phases, in order)

| Phase | Output | Guide |
|-------|--------|-------|
| 1. Discovery | `sources.yaml` | `discovery/GUIDE.md` |
| 2. Comparison | `comparison.yaml` | `comparison/GUIDE.md` |
| 3. Documentation | `README.md`, `MODEL.md`, `BIOLOGY.md` | `documentation/GUIDE.md` |
| 4. Validation | All files cross-checked | `validation/GUIDE.md` |

Do not skip phases. Each phase has a gate that must pass before proceeding.

## Quick Start

For a model that has `config.py` and `app.py` but no knowledge-graph files:

```
1. Read discovery/GUIDE.md     ->  create sources.yaml
2. Read comparison/GUIDE.md    ->  create comparison.yaml
3. Read documentation/GUIDE.md ->  create README.md, MODEL.md, BIOLOGY.md
4. Read validation/GUIDE.md    ->  cross-check everything; run make style
```

## Common Pitfalls

- **Forgetting the license** -- check the GitHub/HuggingFace LICENSE file, not just the API
  metadata field. Code and weights often have different licenses; document both and record the more
  restrictive one in `sources.yaml`.
- **Fabricated benchmark numbers** -- only use values directly from papers with explicit citations
  (e.g., "Table 2 of Lin et al., 2023"). Never estimate.
- **Content duplication across MODEL.md and README.md** -- README.md has concise summaries;
  MODEL.md has full technical depth. Do not copy paragraphs between them.
- **Old action names** -- the canonical actions are `predict`, `fold`, `encode`, `generate`,
  `score`, `log_prob`. Do not use deprecated names (`predict_log_prob`, `extract_features`, `vhh`).
- **Missing cross-references** -- README.md, MODEL.md, and BIOLOGY.md must link to each other at
  the bottom of each file.
- **Non-permissive license** -- if you find a CC-BY-NC or custom non-commercial license, do not
  proceed. Flag it in the PR; the model may not be eligible for the catalog.
