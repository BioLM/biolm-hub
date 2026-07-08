# Philosophy

`biolm-hub` exists so nobody has to keep reinventing the same plumbing. Open biological ML models
usually arrive as fragile research code — undocumented dependencies, a one-off serving story — so
every person (and every agent acting for them) re-solves the same problems before getting a single
prediction. The durable value is **not making everyone reinvent the wheel**: a clean, standardized,
deploy-anywhere catalog that any human or agent can pull from and run, and that the community can
extend.

So the design center is **agent-first**. Every choice optimizes for an LLM/agent consumer, because an
interface that an agent can use reliably is also one a human can use reliably.

## Principles

1. **Ergonomics first — "five-minute success."** `git clone` → `bh setup` → `bh deploy esm2` → first
   inference, in three commands. If the first screen of the README doesn't get someone to a running
   model, that's a bug.

2. **Simplicity and the right abstractions.** Minimal surface area; one obvious way to do a thing;
   small, composable modules. When a piece of machinery is more clever than the problem demands, we
   cut it.

3. **Consistency and uniformity.** Identical model layout, uniform schemas, uniform action verbs, a
   uniform error taxonomy, uniform logging. An agent that learns one model knows them all — and the
   diff between any two models is *only* the science, never the plumbing.

4. **Modern, idiomatic Python.** Type hints throughout, Pydantic v2, structured logging (no stray
   `print`s), pinned dependencies, `ruff`/`black`, `mypy`, `uv`.

5. **Testing as the coherence mechanism.** Every model ships integration + deployment tests with
   golden fixtures and a shared test-asset library. Tests are how we keep dozens of independently
   contributed models honest.

6. **Docs as a feature.** A per-model knowledge graph (`sources.yaml`, `comparison.yaml`, `MODEL.md`,
   `BIOLOGY.md`) tells an agent *which* model to use — training data, benchmarks, when-to-use,
   alternatives, license — not just how to call it.

7. **Self-extending.** Adding a model should be something a contributor's agent can do end-to-end and
   still land in house style. The model template and `CONTRIBUTING.md` encode the rules so the
   catalog grows without losing its shape.

8. **Trustworthy by default.** Reproducible builds, pinned seeds, permissive licensing checked at the
   source (`sources.yaml`), and CI that's safe for untrusted contributions.

## The agent-first API, concretely

- **Action verbs are a closed, legible set:** `predict`, `fold`, `encode`, `generate`, `score`,
  `log_prob`. A folding model *folds*; it doesn't overload `predict`.
- **Field names are uniform across families.** A protein sequence is a `sequence`; an antibody is a
  `heavy_chain` + `light_chain`; a structure is a `pdb` or `cif`. The *biology* (is this a nanobody?
  a TCR?) lives in the model's metadata, not in ad-hoc field names.
- **Errors are machine-readable.** A caller's mistake comes back as a clear, typed user error with a
  stable `code`; our faults are sanitized system errors. An agent can branch on the `code` instead of
  parsing prose.

If you're contributing, [`CONTRIBUTING.md`](CONTRIBUTING.md) turns these principles into concrete
rules.
