# Phase 1: Investigation

## Purpose
Gather information about the model, confirm the license is permissive, find analogous reference models, and produce a skeleton `sources.yaml`. This prevents costly rework: wrong action verbs, incompatible weights, or a license that blocks acceptance are all cheaper to catch here.

---

## 1.1 License Check — Do This First

**Only permissively-licensed models are accepted:** MIT, Apache-2.0, BSD-3-Clause, and compatible permissive licenses. CC-BY-NC, GPL, proprietary, and "academic only" licenses are **not accepted**.

1. Find the LICENSE file in the source repo or the model card.
2. Record the SPDX identifier (e.g., `Apache-2.0`).
3. If unclear or non-permissive, **stop and ask the user** before proceeding.

---

## 1.2 Gather Model Information

Review the available sources — paper, GitHub repo, HuggingFace model card, project website. For each:

**GitHub / source repo:**
- Architecture and inference code
- All dependencies with exact versions
- Weight-loading / download mechanism

**HuggingFace (if available):**
- Model card usage examples
- Exact commit hash for reproducibility
- Model variants and sizes
- Authentication requirements

**Research paper:**
- Input/output specifications
- Preprocessing requirements
- Batch size and sequence length limits
- Performance benchmarks (useful for validation sanity checks)

---

## 1.3 Find a Reference Model

Browse `models/` to find the closest analogous implementation. Read its `app.py`, `config.py`, `schema.py`, `test.py`, and `download.py` (if present). Copy patterns; adapt only what is specific to the new model.

**Selection criteria:**

| Dimension | Look at |
|-----------|---------|
| Protein sequence input | `esm2/`, `esmc/`, `peptides/` |
| DNA/RNA input | `nt/`, `evo/`, `dnabert2/` |
| Structure (PDB) input | `mpnn/`, `esmfold/`, `chai1/` |
| HuggingFace weights | `esmc/`, `nt/`, `esm3/` |
| Custom URL weights | `mpnn/`, `antifold/` |
| No external weights | `peptides/`, `biotite/` |
| Single variant, one action | `peptides/` |
| Multi-variant, one action | `nt/` |
| Multi-variant, multi-action | `esm2/` |

> **Rule:** Never invent import organization, decorator usage, or class structure. Copy from the reference model.

---

## 1.4 Determine Specifications

Work through these before writing a line of code:

**Variants:** Are there size variants (`8m`, `35m`, `650m`)? Type variants (`protein`, `ligand`)? Single variant?

**Actions:** Which of the six canonical verbs applies?
- `predict` — scalar/label property
- `fold` — 3D structure (returns `pdb`/`cif`)
- `encode` — embeddings / representations
- `generate` — new sequences or structures
- `score` — model-defined fitness scalar
- `log_prob` — per-sequence log-likelihood

Map each action to its input/output schema fields (using the standard field names from `CONTRIBUTING.md`).

> **Get user approval on actions and schemas before proceeding.**

**Resources:** For each variant, estimate GPU, memory, CPU, and timeout. See `resources/quick_reference.md` for the GPU tier table.

**Dependencies:** List all pip packages with exact versions. Note any system packages or conda requirements.

**Weight acquisition:** Where do weights come from (HuggingFace, URL, GitHub, none)? Authentication required? Total size per variant?

---

## 1.5 Create a Skeleton `sources.yaml`

Create `models/<name>/sources.yaml` now — a skeleton is better than none, and the license field is required before any code is merged.

Minimum required fields:

```yaml
model_slug: "your-model-slug"    # must match directory name and config.py base_model_slug
display_name: "Your Model Name"

license:
  type: "Apache-2.0"             # SPDX identifier
  url: "https://github.com/org/repo/blob/main/LICENSE"
  notes: ""                      # add context if needed, e.g. "weights are CC-BY-4.0"

molecule_types:
  - "protein"                    # from InputMolecule enum

tasks:
  - "embedding"                  # from Task enum

primary_papers:
  - title: "Full paper title"
    arxiv: ""                    # arXiv ID or bioRxiv DOI suffix
    doi: ""
    venue: ""
    year: 2024
    authors:
      - "Author A et al."

source_repos:
  - type: "github"               # github / huggingface / other
    url: "https://github.com/org/repo"
    commit: ""                   # pin this during implementation
```

See `models/dummy/sources.yaml` for the complete schema including `applied_literature`, `comparison`, and R2 knowledge-base paths. The full knowledge graph is authored by the `model-knowledge-base` skill — fill in what you know now and leave the rest for that phase.

---

## 1.6 Evaluate Endpoint Reuse

If the new model calls an existing hosted model (e.g., ESM-2 for embeddings), verify compatibility before assuming you can reuse the endpoint:

- Read the candidate's `schema.py` — exact field names and types
- Read the candidate's `app.py` — layer index, dimensions, pooling
- Confirm the extraction logic matches the paper

If compatible, use `modal.Cls.lookup()`. Document the decision (which endpoint, which params, and why).

---

## Gate

Before moving to Phase 2, confirm:

- [ ] License confirmed permissive and recorded in `sources.yaml`
- [ ] Reference model(s) identified; key files read
- [ ] Variants, actions, and schemas approved by user
- [ ] Resource requirements estimated
- [ ] `sources.yaml` skeleton committed (or ready to commit with Phase 2)
