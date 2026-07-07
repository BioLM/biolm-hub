# Common Issues

Pitfalls seen repeatedly when implementing models, with the fix. The `SKILL.md` lists the top 8;
this is the fuller set.

## Licensing & sources

1. **Non-permissive license.** Check the upstream `LICENSE` (GitHub/HuggingFace) **before** writing
   code — not just the metadata field. Only MIT / Apache-2.0 / BSD (and compatible) are accepted.
   Code and weights can have different licenses; honor the more restrictive one. CC-BY-NC / custom
   non-commercial → stop, the model is ineligible.
2. **Unpinned HuggingFace revision.** Pin a 40-char commit hash, never `"main"` — `"main"` drifts and
   breaks reproducibility.

## Determinism & dependencies

3. **Missing seeds (stochastic/torch models only).** For a model with a stochastic or torch forward
   pass, set `torch`, `numpy`, `random`, and CUDA seeds so fixtures and tests are reproducible.
   Deterministic CPU/algorithmic tools (e.g. `dna_chisel`, `biotite`, `prody`, `sadie`) have nothing
   to seed — do **not** add torch seeding to them. Genuinely non-deterministic models: use the test
   suite's tolerances/validators, not exact match.
4. **Unpinned dependencies.** Every package pins an exact version (`==X.Y.Z`). No ranges, no unpinned.
5. **Build-time imports of a fallback library.** If `download.py` imports a library at build time
   (e.g. a `r2_then_library` fallback), list it in `setup_download_layer(extra_pip_packages=[...])`
   or the image build fails with `ModuleNotFound`.
6. **Strict mypy `[no-untyped-call]` from an installed dependency.** When your model's new dependency
   is *installed in the repo venv* (a real project dep — e.g. `biopython`), strict mypy follows it
   and flags every call into its untyped API as `[no-untyped-call]`. Fix it by routing the untyped
   object through a variable annotated `Any`, or by annotating the specific call with
   `# type: ignore[no-untyped-call]  # <lib> <thing> is untyped` (the pattern already used in
   `models/thermompnn_d/util.py` and `models/commons/testing/`). A dependency that lives **only** in
   the Modal image and is **not** installed locally (e.g. `dnachisel`/`primer3`) does *not* trip this
   — `ignore_missing_imports=true` makes it `Any`, so mypy can't follow it. Adding the dep to the
   repo's own deps is what turns on the checking.

   **Annotate less, not more.** A bare `result: dict = {}` trips strict mypy `[type-arg]` (a naked
   `dict`/`list` needs its type args). The fix is often to annotate *less*: an un-annotated
   `result = {}` lets mypy infer the type and passes (this is what `models/igbert/app.py` does).
   Either fully parametrize (`result: dict[str, Any] = {}`) or drop the annotation and rely on
   inference — don't add a bare `: dict`. Relatedly, returning an untyped attribute's output (e.g.
   `return self.tokenizer(...)`) trips `[no-any-return]` — route it through a typed local first.

## Implementation correctness

7. **Wrong action verb.** Use the closed set — folding is `fold` (not `predict`), a (pseudo)
   log-likelihood is `log_prob`, embeddings are `encode`. Don't invent verbs.
8. **Non-canonical schema fields.** Reuse the standard names (`sequence`, `heavy_chain`/`light_chain`,
   `pdb`/`cif`, batch `items`/`results`). When renaming for backward-compat, accept the old name on
   **input** with `validation_alias=AliasChoices("new_name", "old_name")` (new name first):

   ```python
   from pydantic import AliasChoices, Field
   residue_embeddings: list[list[float]] = Field(
       validation_alias=AliasChoices("residue_embeddings", "per_token_embeddings"),
       description="Per-residue embedding vectors.",
   )
   ```

   Do **not** use a plain `alias="old_name"` — that sets both the validation *and* serialization alias,
   so it renames the field in the **output** too (wrong for input back-compat). Real examples:
   `models/igbert/schema.py` (`AliasChoices("heavy_chain", "heavy")`), `models/esm2/schema.py`.
   Also mirror the reference's *plumbing* only — pick field names from the uniform rules, not from
   whatever the reference happened to call them (a nanobody is a lone `heavy_chain`, not `sequence`).
9. **`print()` in runtime code.** Banned by lint. Use `logger = get_logger(__name__)` and
   `logger.info/debug/warning/error`. Never log full sequences or secrets.
10. **Bare `Exception`/`ValueError` for bad input.** Raise a typed `UserError` (with a stable `code`)
   for caller mistakes; let system errors propagate. Never catch-and-`print`.
11. **Module-scope R2 reads / heavy imports in `fixture.py`.** Keep them lazy (inside functions) so
    `pytest models/<model>/test.py --collect-only` works with no Modal/R2.

## Testing & validation

12. **Running tests before generating fixtures.** Always `python models/<model>/fixture.py` first;
    the integration tests load the goldens it writes.
13. **Regenerating goldens to force a green test.** The golden output is the oracle. Only regenerate
    when an output change is *intended*, and say so in the PR.
14. **Pushing with `make check` red.** `make check` (style + mypy + schema-doc check + CI-script
    tests + unit tests) is CI's main `checks` job. Fix failures locally first; never push just to
    re-trigger CI. Note `make check` does **not** build docs — CI runs a separate `mkdocs build
    --strict` job, so also run `make docs` (a broken schema description or generated page fails it).

## Modal / deployment

15. **Wrong resource tier.** Start with the smallest GPU tier that fits; bump only on OOM.
16. **Editing `models/commons/`.** It is read-only during model work — a change there affects every
    model. If commons genuinely needs something, raise it as a separate change.
17. **Hand-uploading test data.** `bh r2` is read-only; fixture upload is handled by
    `FixtureGenerator`. Never try to upload fixtures manually.
