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

Group the model with the catalog models that share **both its task and its input modality** — the
kind of data it consumes (protein sequence, DNA, RNA, SMILES, 3D structure, antibody chains, MSA).
A model can be the **sole member** of its group (e.g. the only SMILES model); if so it has no
in-catalog alternatives, and that is correct — see Step 4, and leave `alternatives` empty rather
than reaching into another modality. These clusters (by directory slug) are **illustrative, not
exhaustive** — the catalog changes, so always confirm a slug with `ls models/` before you reference
it in `comparison.yaml`. The Gate below rejects any slug that has no `models/<slug>/`.

- **Protein embeddings / PLMs**: `esm2`, `esmc`, `esm1b`, `esm1v`, `msa_transformer`, `prostt5`, `e1`, `dsm`
- **Protein generation / design**: `progen2`, `zymctrl`, `mpnn`, `esm_if1`
- **Structure prediction**: `esmfold`, `chai1`, `rf3`
- **Complex / binder design**: `boltzgen`
- **Antibody sequence**: `ablang2`, `igbert`, `igt5`
- **Antibody structure**: `antifold`, `abodybuilder3`, `immunefold`, `immunebuilder`
- **Stability / property prediction**: `thermompnn`, `thermompnn_d`, `temberture`, `spurs`
- **Developability**: `deepviscosity`
- **DNA / genomics**: `dnabert2`, `omni_dna`, `evo`, `evo2`
- **Small molecules / cheminformatics (SMILES)**: `chemberta`
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

**Alternatives** -- genuine **substitutes**: a model a user could swap in **on the same input**. An
alternative MUST accept this model's primary input modality (protein sequence / DNA / RNA / SMILES /
3D structure / antibody chains / MSA) AND perform an overlapping task. Explain when each is better
AND when it is worse.

- **Never list a model that cannot accept this model's inputs.** A protein language model is not an
  alternative to a SMILES model; a DNA model is not an alternative to a protein model. If an entry's
  `when_worse` reduces to "operates on a different data type" / "is not a substitute", it is a
  **cross-modality analogue**, not an alternative — mention it in prose (`dont_use_when`, README)
  or, if genuinely used together, under `complements`; never under `alternatives`.
- If this model is the **only one of its modality/task** in the catalog, leave `alternatives` empty
  (the Gate permits this) rather than padding it with analogues.
- BAD (for a SMILES model): listing `esm2` (protein) or `dnabert2` (DNA) as alternatives.
- GOOD (for a protein-embedding model): listing `esmc` / `esm1b` — other protein LMs that embed the
  same amino-acid input.

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
