# Phase 2: Comparison

## Purpose

Author `comparison.yaml` -- machine-readable guidance on when to use this model, when not to, and
how it relates to other models in the catalog. This file helps agents and users pick the right
model for their task.

## Prerequisites

- Phase 1 complete (`sources.yaml` gate criteria met).
- Have read the primary paper's benchmark results.
- Familiarity with the existing catalog (`models/` directory).

---

## comparison.yaml Structure

Copy the template at `models/dummy/comparison.yaml` and fill it in — it is the authoritative format,
carrying inline field-by-field guidance and all required keys (`model_slug`, `display_name`,
`last_updated`, `strengths`, `weaknesses`, `use_when`, `dont_use_when`, `alternatives`,
`complements`). Do not re-invent the structure here; the Steps below explain how to populate each
section, and the Gate Criteria list the minimum entry counts.

---

## Steps

### Step 1: Identify the model's competitive group

Group the model with the catalog models that share its task. These clusters (by directory slug) are
**illustrative, not exhaustive** — the catalog changes, so always confirm a slug with `ls models/`
before you reference it in `comparison.yaml`. The Gate below rejects any slug that has no
`models/<slug>/`.

- **Protein embeddings / PLMs**: `esm2`, `esmc`, `esm1b`, `esm1v`, `msa_transformer`, `prostt5`, `e1`, `dsm`
- **Protein generation / design**: `progen2`, `zymctrl`, `mpnn`, `esm_if1`
- **Structure prediction**: `esmfold`, `chai1`, `rf3`
- **Complex / binder design**: `boltzgen`
- **Antibody sequence**: `ablang2`, `igbert`, `igt5`
- **Antibody structure**: `antifold`, `abodybuilder3`, `immunefold`, `immunebuilder`
- **Stability / property prediction**: `thermompnn`, `thermompnn_d`, `temberture`, `spurs`
- **Developability**: `deepviscosity`
- **DNA / genomics**: `dnabert2`, `omni_dna`, `evo`, `evo2`
- **Utility**: `biotite`, `prody`, `sadie`, `dna_chisel`

### Step 2: Write strengths and weaknesses

Draw from: primary paper benchmarks, BIOLOGY.md "Alternative Models" section, `config.py`
resource requirements and variant options, and practical deployment characteristics.

- BAD: "Good performance"
- GOOD: "Top-5 on ProteinGym variant effect prediction across 87 DMS datasets (650M variant)"

Write at least 5 strengths and 5 weaknesses.

### Step 3: Define use / don't-use cases

For `use_when`, describe concrete scenarios. For `dont_use_when`, always name the better
alternative.

- BAD: "When you need structure"
- GOOD: "When you need structure-conditioned sequence design (use ProteinMPNN instead -- it accepts backbone coordinates)"

### Step 4: Map alternatives and complements

**Alternatives** -- models that overlap in capability. Explain when each is better AND when it is
worse. Only include models that genuinely overlap.

**Complements** -- models commonly used together in pipelines. Describe the typical workflow and
reference a protocol YAML if one exists.

Verify all referenced model slugs exist under `models/`.

---

## Quality Criteria

- Every claim traceable to a paper, benchmark, or empirical observation.
- No bare superlatives ("best", "superior") without qualification.
- Include variant specifics when relevant ("ESM2-650M outperforms, but ESM2-8M does not").
- Entries concise and actionable (1-2 sentences each).
- All referenced model slugs verified to exist in `models/`.

---

## Gate Criteria

- [ ] `comparison.yaml` created in `models/{slug}/`
- [ ] At least 5 entries in `strengths` (hard floor: 3)
- [ ] At least 5 entries in `weaknesses` (hard floor: 3)
- [ ] At least 5 entries in `use_when` (hard floor: 3)
- [ ] At least 5 entries in `dont_use_when` (hard floor: 3)
- [ ] At least 1 entry in `alternatives` (unless the model is uniquely niche with no overlap)
- [ ] At least 1 entry in `complements` (unless the model is truly standalone)
- [ ] All referenced model slugs exist in `models/`
- [ ] No unqualified subjective claims
- [ ] Valid YAML syntax (`python -c "import yaml; yaml.safe_load(open('models/{slug}/comparison.yaml'))"`)
