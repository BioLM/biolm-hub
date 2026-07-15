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

### 2b. Blind check of every fabricatable value

Benchmark numbers, author surnames, DOIs, and venues are the values most likely to drift from the
source — and the hardest to catch by re-reading your own draft, because you wrote them believing
them. Verify them without that bias, using a fresh-context reviewer when one is available:

- Spawn a fresh reviewer that does **not** see the drafted docs. Hand it only the primary paper(s)
  and the list of claims to check (each benchmark number with its cited table/figure; each "X et
  al., YEAR" attribution; each DOI/arXiv id).
- The reviewer re-derives each value straight from the source and reports what it found.
- Reconcile: any value that doesn't match the source is corrected or removed before the PR. A value
  the reviewer cannot locate in the source is treated as unsupported — cut it or document the gap.

When this skill runs as part of `model-implementation`, this blind check folds into that workflow's
Phase 5 fresh-context review of the full diff — run it there rather than twice. When this skill runs
on its own, this pass is the knowledge graph's only blind check; run it whenever a fresh-context
reviewer is available.

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

Run all four in one pass from the repo root (replace `<slug>`); a clean run is the go signal, and
any non-zero exit names the file to fix:

```bash
python -c "import yaml; yaml.safe_load(open('models/<slug>/sources.yaml'))" \
  && python -c "import yaml; yaml.safe_load(open('models/<slug>/comparison.yaml'))" \
  && make style \
  && make docs \
  && echo "KG VALIDATION PASSED — ready for PR"
```

If this prints `KG VALIDATION PASSED`, the syntax/style/docs gate is green. If it stops early, fix
the file it names and re-run the whole block — do not proceed on a partial pass.

---

## Gate Criteria

- [ ] Actions + schema fields in the docs match `schema.py`/`config.py`
- [ ] Every benchmark number is cited; no fabricated values
- [ ] Every author attribution written in prose (e.g. "Rollins et al., 2024" in `README.md`/`MODEL.md`) is backed by an `authors` list on that paper's `sources.yaml` entry, and the surname is verified against the actual paper (search the DOI/arXiv) — record authors in structured form so the prose stays auditable, never assert "et al." from memory
- [ ] Every benchmark number and author attribution has been re-derived from the primary source by a reviewer that did not see the drafts, and reconciled
- [ ] License agrees across `sources.yaml`, README, and `LICENSE`
- [ ] All referenced model slugs exist in `models/`
- [ ] `sources.yaml` and `comparison.yaml` are valid YAML
- [ ] `make style` passes
- [ ] `make docs` passes (mkdocs --strict — the generated model page builds)

When all boxes are checked, the knowledge graph is complete and ready for the PR.
