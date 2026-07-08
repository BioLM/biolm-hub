# Phase 4: Documentation

## Purpose
Document the model for users and the public catalog.

All five knowledge-graph files — `README.md`, `MODEL.md`, `BIOLOGY.md`, `sources.yaml`,
`comparison.yaml` — are **owned by the `model-knowledge-base` skill**. This phase does **not**
hand-author them; it **invokes** that skill (`config.py`/`schema.py`/`app.py` from Phase 2 must
already exist, since the KG skill reads them), verifies its output, and then opens the PR.

---

## 4.1 The `README.md` the KG skill produces

`README.md` is one of the five files **owned by `model-knowledge-base`** — you invoke that skill
(§4.2) rather than hand-authoring it here. The reference below is what the skill's README must
contain, so you can verify its output: follow `models/dummy/README.md` as the template — all its
sections are required; include `[OPTIONAL]` sections only when applicable.

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

> **Ship a `LICENSE` file.** Every model dir includes `models/<name>/LICENSE` containing the upstream
> license text copied **verbatim** from the source repo. Its license must agree with `sources.yaml`
> and the README's License section — the `model-knowledge-base` validation cross-checks all three.

---

## 4.2 Knowledge Graph — Invoke `model-knowledge-base` (owns all five files)

`model-knowledge-base` authors **all five** knowledge-graph files — not just these four — to its own
standard; this phase only invokes it:

- `README.md` — public-facing API reference (see §4.1 for the sections it must contain)
- `sources.yaml` — complete source manifest (you created a skeleton in Phase 1; the skill fills it out)
- `comparison.yaml` — strengths/weaknesses, when-to-use, alternatives
- `MODEL.md` — architecture deep-dive, training details, benchmarks
- `BIOLOGY.md` — the biology, applied use cases, biological context

Invoke `model-knowledge-base` **now, before the PR** — all five KG files must be authored to the KG
skill's standard as part of this phase. It needs `config.py`/`schema.py`/`app.py` (Phase 2) to exist
first.

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
- Deploy status: a `biolm-hub-dev` deploy + live inference call succeeded, **or** (credential-less) an explicit note that deploy is unverified for a maintainer to complete (see `validation/GUIDE.md §3.5`)
- Any notes on resource allocation choices

---

## Documentation Checklist

- [ ] All five knowledge-graph files authored via `model-knowledge-base` and passing its validation
- [ ] `README.md` follows `models/dummy/README.md` structure
- [ ] All required sections present
- [ ] BibTeX citation valid and links working
- [ ] Limitations are clear and honest
- [ ] Performance metrics verified against the paper
- [ ] `sources.yaml` has license and primary papers filled in
- [ ] `models/<name>/LICENSE` present with the upstream license text; agrees with `sources.yaml`/README
- [ ] `make check` passes
- [ ] PR description explains what was added, what was tested, and deploy status (§3.5 carve-out)

## Gate

All five knowledge-graph files present and passing the `model-knowledge-base` validation;
`make check` green; PR created. (The mandatory Phase 5 review — a fresh-context reviewer sign-off on
all four dimensions — follows; see `SKILL.md`.)
