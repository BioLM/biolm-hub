# Phase 4: Documentation

## Purpose
Document the model for users and the public catalog.

There are two documentation artifacts:
1. **`README.md`** — API reference and scientific context (authored here)
2. **Knowledge graph** (`sources.yaml`, `comparison.yaml`, `MODEL.md`, `BIOLOGY.md`) — delegate to the `model-knowledge-base` skill

---

## 4.1 `README.md`

Follow `models/dummy/README.md` as the template — all its sections are required. Include `[OPTIONAL]` sections only when applicable.

The README is the public-facing API reference. It must be:
- **Specific** — use numbers, not vague descriptions
- **Honest** — document limitations clearly
- **Scientifically accurate** — verify all metrics against the paper

**Required sections** (follow dummy's structure):

1. **Model overview** — what the model does, primary use case, key differentiator (2-3 sentences)

2. **Architecture** — model type (Transformer, GNN, etc.), parameters, layers, training data and size

3. **Capabilities & Limitations** — what the model CAN and CANNOT do; include length limits, unsupported types, known failure modes

4. **Performance & Benchmarks** — key metrics from the paper, benchmark datasets, comparison to baselines; cite the paper

5. **Implementation Notes** (if notable) — deviations from the original implementation, platform-specific notes; include a one-line sanity check against published values (e.g., "Spearman r = 0.95 on ProTherm, matching Table 2 of the paper")

6. **References** — BibTeX citation + links (GitHub, HuggingFace, project site)

**What NOT to include:**
- Installation instructions (handled by the platform)
- Step-by-step usage tutorials (the API is self-documenting via schemas)
- Information duplicated from `config.py` or `schema.py`

---

## 4.2 Knowledge Graph — Delegate to `model-knowledge-base`

The following files are authored by the `model-knowledge-base` skill, not here:

- `sources.yaml` — complete source manifest (you created a skeleton in Phase 1; the skill fills it out)
- `comparison.yaml` — strengths/weaknesses, when-to-use, alternatives
- `MODEL.md` — architecture deep-dive, training details, benchmarks
- `BIOLOGY.md` — the biology, applied use cases, biological context

Invoke the skill after your PR is merged, or coordinate with a maintainer.

---

## 4.3 Finishing Up

```bash
# Final style + type check
make check
# Build the docs site — your generated per-model page must pass mkdocs --strict.
# This is a SEPARATE CI job that `make check` does NOT run; the knowledge-graph
# files you just authored (README/MODEL/BIOLOGY, cross-links, tables) are the
# most common cause of a strict-mode docs failure.
make docs

# Stage and commit
git add models/<name>/
git commit -m "feat(<name>): add <Model Name> — <one-line summary>"

# Create PR
gh pr create --title "feat(<name>): add <Model Name>" --body "..."
```

PR body should include:
- What the model does and why it was added
- License confirmation (SPDX identifier from `sources.yaml`)
- What was tested locally (at minimum: `make check` + `make docs` + unit tests)
- Any notes on resource allocation choices

---

## Documentation Checklist

- [ ] `README.md` follows `models/dummy/README.md` structure
- [ ] All required sections present
- [ ] BibTeX citation valid and links working
- [ ] Limitations are clear and honest
- [ ] Performance metrics verified against the paper
- [ ] `sources.yaml` has license and primary papers filled in
- [ ] `make check` passes
- [ ] PR description explains what was added and what was tested

## Gate

PR created; `make check` green; all required files present.
