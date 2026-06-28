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

Note: `models/dummy/comparison.yaml` does not exist yet -- use the structure below directly.

```yaml
model_slug: "{slug}"
display_name: "{display_name}"
last_updated: "YYYY-MM-DD"

strengths:
  # At least 5 entries. Be specific and actionable.
  - "Top-5 on ProteinGym variant effect prediction across 87 DMS datasets (650M variant)"

weaknesses:
  # At least 5 entries. Be honest about limitations.
  - "Truncates sequences >1022 residues -- use a chunking strategy or a model with longer context"

use_when:
  # At least 5 entries. Describe concrete scenarios.
  - "When you need general-purpose protein embeddings for downstream ML tasks like fitness prediction or clustering"

dont_use_when:
  # At least 5 entries. Always name the better alternative.
  - "When you need structure-conditioned sequence design (use ProteinMPNN instead -- it accepts backbone coordinates)"

alternatives:
  # Models that could replace this one for overlapping tasks.
  - model: "{slug}"
    when_better: "description of when the alternative is superior"
    when_worse: "description of when this model is superior"

complements:
  # Models commonly used together with this one in pipelines.
  - model: "{slug}"
    workflow: "description of how the two models work together"
    example_protocol: null
```

---

## Steps

### Step 1: Identify the model's competitive group

Common groups in the catalog:
- **Protein embeddings**: ESM2, ESMC, SaProt, MSA Transformer, PoET, ProstT5, TemBERTure
- **Protein generation**: ProGen2, ZymCTRL, ProteinMPNN, ESM-IF1
- **Structure prediction**: ESMFold, Chai-1, Boltz, RF3
- **Binder/complex design**: RFdiffusion3, BoltzGen
- **Antibody sequence**: AbLang2, IgBERT, NanoBERT, AbLEF
- **Antibody structure**: AntiFold, AbodyBuilder3, ImmuneFold, ImmuneBuilder
- **Developability**: ProperMAB, DeepViscosity, CamSol, SoluProt
- **DNA/genomics**: NT, DNABERT2, OmniDNA, Evo, Evo2
- **Property prediction**: ThermoMPNN, CLEAN, SPURS, Pro4S, GEMME
- **Utility**: Biotite, ProDy, SADIE, Peptides, DNA Chisel

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
