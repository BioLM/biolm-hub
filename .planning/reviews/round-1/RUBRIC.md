# Review Round-1 — Rubric

Shared criteria for the independent review. Every reviewer grades against this. Ground yourself by also
skimming `.planning/03_WORKSTREAMS.md` (esp. the **Definition of Done** at the end), `.planning/00_MASTER_PLAN.md`,
`.planning/04_TESTING_STRATEGY.md`, and `CONTRIBUTING.md` / `PHILOSOPHY.md`. The repo's north star:
**uniformity — the diff between any two models should be the science, not the plumbing.**

## Severity
- 🔴 **must-fix before launch** — correctness/security bug, secret or internal-reference leak (`biolm-modal`,
  internal `qa` env, internal domains, `.planning` refs in shipped files), license problem, broken public
  contract, a Definition-of-Done item not met.
- 🟠 **should-fix** — convention violation, missing/ wrong field description or test, a weak abstraction or
  duplication with real impact, a documentation gap, an inconsistency across models.
- 🟡 **nit** — style, naming, minor polish, optional improvement.

For each finding give: severity, category, a one-line title, the exact `file:line` location, a concrete detail
(what's wrong and why it matters), and a specific suggested fix. Prefer few high-confidence findings over many
speculative ones; if unsure, mark it 🟡 and say so.

## A. Conformance to the ratified standards
1. **Layout** — standard files present and correct: `app.py`, `config.py`, `schema.py`, `test.py`,
   `download.py` (if weights), and the 5-file knowledge graph (`sources.yaml`, `comparison.yaml`, `README.md`,
   `MODEL.md`, `BIOLOGY.md`). `config.py` defines a `ModelFamily` with `modal_class_name`, `action_schemas`,
   variants, tags.
2. **Actions** — only the closed set `predict / fold / encode / generate / score / log_prob`; the verb matches
   intent (a folding model `fold`s, doesn't overload `predict`). No invented verbs.
3. **Schema field names** — uniform across families; biology lives in tags, not field names. Inputs
   `sequence(s)`/`msa`, `pdb`/`cif`, `smiles`, `items`, `params`; antibodies `heavy_chain`/`light_chain`
   (nanobody = lone `heavy_chain` + single-domain tag, no `vhh`); outputs `embeddings`/`logits`/`log_prob`/
   `score`/`plddt`/`ptm`/`pae`, batch under `results`. Renames keep a Pydantic alias.
4. **Field descriptions** — every request/response field has a `Field(description=...)` that RENDERS in
   `model_json_schema()` (a Field nested in `Optional[Annotated[...]]` silently drops it). Shared fields match
   `tooling/field_glossary.yaml`. Descriptions are accurate, concise, no leaked sequences/secrets.
5. **Errors** — typed `UserError`/`ServerError` (subclasses of `BioLMError`) with stable `code`s for caller
   mistakes; system faults propagate/sanitized. No bare `ValueError`/`Exception` for bad input; no catch-and-print.
6. **Logging** — `get_logger`; no `print` in runtime code; sensible levels; never logs full sequences/secrets.
7. **Acquisition** — canonical `r2_then_hf` / `r2_then_library` / `r2_then_urls` (or documented custom);
   self-populates the public bucket; build-order rule honored (lib/`huggingface_hub` listed in
   `setup_download_layer(extra_pip_packages=...)` when the fallback imports it at build time).
8. **Licensing** — per-model `LICENSE` present, permissive (MIT/Apache/BSD/CC-BY and compatible), and consistent
   with `sources.yaml`; attribution obligations honored; no inferred holder/year left unflagged.
9. **Knowledge graph** — all 5 files present, accurate, internally consistent (slug/display_name match config),
   complete (no stray `TODO`/`pending`/template placeholders shipping), no internal-only content.
10. **Tests** — `TestSuite` with integration + deployment cases; fixtures lazy-load (no module-scope R2/network);
    reuse shared assets instead of hardcoding standard sequences.

## B. Software-engineering quality
- **Modularity & abstraction** — clear separation of concerns; the abstraction earns its keep (not over- nor
  under-engineered); shared logic lives in `commons`, not copy-pasted across models.
- **Simplicity / "10x"** — is anything more clever than the problem demands? Dead code, unused params, leftover
  scaffolding, needless indirection? Could it be materially simpler?
- **Readability** — idiomatic modern typed Python (Pydantic v2, full type hints), good names, right amount of
  comments, consistent with surrounding code.
- **Correctness** — logic bugs, wrong defaults, off-by-one, mishandled edge cases, schema/runtime mismatches
  (e.g. a description that contradicts what `app.py` actually computes).

## C. Open-source readiness
- **Docs** — clear to an outside contributor; examples correct; no dead links; reflects the actual code.
- **No internal leakage** — no `biolm-modal`, internal env names (`qa`), internal domains, `.planning` refs, or
  raw third-party PDFs in anything that ships.
- **Consistency** — the same concept is done the same way everywhere; cross-model uniformity.

## D. Definition-of-Done audit
Check each DoD item from `.planning/03_WORKSTREAMS.md` and report which are met / partially met / not met, with
evidence (global reviewers especially).
