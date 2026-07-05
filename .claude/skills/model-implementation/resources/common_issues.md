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

3. **Missing seeds.** Set `torch`, `numpy`, `random`, and CUDA seeds so fixtures and tests are
   reproducible. Non-deterministic models: use the test suite's tolerances/validators, not exact match.
4. **Unpinned dependencies.** Every package pins an exact version (`==X.Y.Z`). No ranges, no unpinned.
5. **Build-time imports of a fallback library.** If `download.py` imports a library at build time
   (e.g. a `r2_then_library` fallback), list it in `setup_download_layer(extra_pip_packages=[...])`
   or the image build fails with `ModuleNotFound`.

## Implementation correctness

6. **Wrong action verb.** Use the closed set — folding is `fold` (not `predict`), a (pseudo)
   log-likelihood is `log_prob`, embeddings are `encode`. Don't invent verbs.
7. **Non-canonical schema fields.** Reuse the standard names (`sequence`, `heavy_chain`/`light_chain`,
   `pdb`/`cif`, batch `items`/`results`). When renaming for compatibility, keep the old name working
   via a Pydantic field alias.
8. **`print()` in runtime code.** Banned by lint. Use `logger = get_logger(__name__)` and
   `logger.info/debug/warning/error`. Never log full sequences or secrets.
9. **Bare `Exception`/`ValueError` for bad input.** Raise a typed `UserError` (with a stable `code`)
   for caller mistakes; let system errors propagate. Never catch-and-`print`.
10. **Module-scope R2 reads / heavy imports in `fixture.py`.** Keep them lazy (inside functions) so
    `pytest models/<model>/test.py --collect-only` works with no Modal/R2.

## Testing & validation

11. **Running tests before generating fixtures.** Always `python models/<model>/fixture.py` first;
    the integration tests load the goldens it writes.
12. **Regenerating goldens to force a green test.** The golden output is the oracle. Only regenerate
    when an output change is *intended*, and say so in the PR.
13. **Pushing with `make check` red.** `make check` (style + mypy + schema-doc check + CI-script
    tests + unit tests) is CI's main `checks` job. Fix failures locally first; never push just to
    re-trigger CI. Note `make check` does **not** build docs — CI runs a separate `mkdocs build
    --strict` job, so also run `make docs` (a broken schema description or generated page fails it).

## Modal / deployment

14. **Wrong resource tier.** Start with the smallest GPU tier that fits; bump only on OOM.
15. **Editing `models/commons/`.** It is read-only during model work — a change there affects every
    model. If commons genuinely needs something, raise it as a separate change.
16. **Hand-uploading test data.** `bh r2` is read-only; fixture upload is handled by
    `FixtureGenerator`. Never try to upload fixtures manually.
