# Milestone B — deploy + test matrix (plan + status)

User authorized the full deploy/test on Modal (2026-06-30, session `oss-w3b-wsec`), with the
preconditions: finalize commons (R2 weight path, abstraction adoption) first, then deploy in
**staged waves** surfacing cost. Deploy env = `biolm-models-dev` (secrets `cloudflare-r2` +
`hf-api-token` present; workspace `biolm`). Deploy cmd:
`MODEL_SIZE=<v> MODAL_ENVIRONMENT=biolm-models-dev .venv/bin/python models/<m>/app.py --force-deploy`.

## Wave 0 — readiness (Modal-free) — ✅ DONE
- **R2 weight path finalized** → `biolm-public/biolm-hub/models/<slug>/<weights_version>/...`
  (+ `biolm-hub/test-data/`, `biolm-hub/model-cache/`). Commit `4245dc8`. Round-trip verified.
- **Commons-abstraction audit** (all 39 models): base class / modal_class_name / canonical actions /
  logging / weights_version all ✓. Fixed user-input bare-ValueError → typed `UnsupportedOptionError`
  (immunebuilder, dsm). Custom-download models (abodybuilder3/boltzgen/progen2/temberture/tempro/evo2)
  use `download_with_fallback` legitimately (flat wrappers can't express their strategies) — OK.
- **make-check GREEN**: ruff/black, schema guard ✓39, mkdocs --strict (38 pages), mypy-scripts 0,
  tests 206 pass (1 known test_cache R2-creds fail).

### Deferred (not blockers for the deploy — we deploy WITH creds):
- **R2 secret-mount activation switch** (creds-less end-user path): Modal 1.3.5 `Secret.from_name` has
  NO `required=False`, so making the `cloudflare-r2` mount optional needs a conditional mechanism — and
  the secret is mounted ONLY at build time (downloader.py:113), not runtime. Do as a focused follow-up +
  validate creds-less read AFTER weights are populated. Not needed for our deploy.
- sadie `pip_install`→`uv_pip_install` (deliberate: sadie pins pydantic v1); evo2 dead R2-only branch;
  e1 cu11.8 CUDA tag — all build/download logic in untestable models → validate at deploy.

## Wave plan (from the audit deploy-matrix; staged, cheapest-first)
**Wave 1 — representatives (validate the NEW R2 path + pipeline on one per pattern):**
esm2-150m (CPU, r2_then_library) · a r2_then_hf (zymctrl/dnabert2, T4) · mpnn (CPU, r2_then_urls) ·
a micromamba/py3.10 (thermompnn, T4) · dna_chisel (CPU, weightless). Confirm each self-populates to
`biolm-hub/models/...` + invokes correctly + golden fixture.

**Wave 2 — CPU + small-GPU fan-out:** remaining CPU (ablang2, antifold, biotite, deepviscosity, esm1v×5,
immunebuilder, prody, sadie, tempro, progen2-oas) + T4 (esm_if1, esm1b, igbert×2, igt5×2, immunefold×2,
msa_transformer, progen2 med/large/BFD90, spurs, temberture×2, thermompnn_d, zymctrl, e1-150m, esm2-35m).

**Wave 3 — L4/A10G:** evo×2, evo2×2, omni_dna×3, prostt5×2, e1-650m/3b, dsm×3, esmc, esmfold, pro1×2.

**Wave 4 — A100/L40S (largest):** boltzgen (A100_40), rf3 (A100_40), chai1 (A100_80), dsm-3B (A100_40),
abodybuilder3-language (L40S), esm2-3B (T4+L40S).

Per model: deploy → self-populate R2 → integration test (T2) → generate+review golden fixture →
deployment test (T3). Idle apps = $0; `modal app stop <name> --env biolm-models-dev` to tear down.

## Watch-items (from audit Part 4) to verify on first deploy
esmfold backbone `esm2_t36_3B_UR50D` ✓conf; immunefold Zenodo API + fair-esm CDN ✓conf; evo HF_HUB_CACHE
redirect ✓conf; progen2 GCS shared-prefix full-set download ✓conf; antifold OPIG URL (univ. server — verify
liveness on cold start); StrEnum-3.10 shim ✓conf; boltzgen test_unit pandas (pre-existing test-only).

## Cleanup
- `peptides` app still deployed on dev but DROPPED from catalog → `modal app stop peptides --env biolm-models-dev`.
</content>
