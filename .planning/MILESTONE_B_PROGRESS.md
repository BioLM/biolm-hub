# Milestone B — deploy + smoke-invoke progress tracker

> ## ⚠️ VALIDATION METHOD — READ THIS (hard-won, user-confirmed 2026-06-30)
> **A successful `modal deploy` does NOT mean the model works.** Models load weights at COLD START
> (`@modal.enter`/`setup_model`), not at deploy. A container can **crash-loop on every request with NO
> external signal** — curl just returns `303` then hangs to `000`/timeout, which looks like "slow", not
> "broken". The ONLY reliable signal is the **container logs**:
> ```
> modal app logs <app> --env biolm-models-dev    # look for "Runner failed", Traceback, OSError, etc.
> ```
> So the real validation per model is: deploy → trigger a cold start (one invoke, even if curl 303s/hangs)
> → **read `modal app logs` for a clean inference vs an exception**. Do NOT trust curl HTTP status alone.
> (First casualty: zymctrl deployed "✅" but crash-looped on a tokenizer `OSError` — only logs revealed it.)
> Wave-subagents MUST use this method. (Also in memory: feedback_modal_container_health.)

> Live tracker for the full deploy/smoke-invoke pass (user-authorized 2026-06-30). **dev only**
> (`biolm-models-dev`); validation = deploy + ONE live inference (goldens deferred to the final
> biolm-hub env). Update this table as models complete so a fresh agent can resume. Deploy cmd:
> `MODEL_SIZE=<v> MODAL_ENVIRONMENT=biolm-models-dev .venv/bin/python models/<m>/app.py --force-deploy`.
> Gateway for smoke-invoke: `https://biolm-biolm-models-dev--biolm-gateway-web.modal.run/api/v3/<slug>/<action>`.
> Status: ⬜ todo · 🔵 deploying · ✅ deploy+invoke ok · 🟡 deployed (invoke pending/manual) · 🔴 failed (see notes).

## PER-MODEL VALIDATION CYCLE (use this — subagents too)
1. Deploy (bg, log to file): `MODEL_SIZE=<v> MODAL_ENVIRONMENT=biolm-models-dev .venv/bin/python models/<m>/app.py --force-deploy`. Wait for `✅ App '<name>' deployed successfully`. (Build log also shows `Caching to R2 at biolm-hub/models/<slug>/...` ✅ for the new-path self-pop.)
2. Cold-start: fire ONE invoke at the gateway (curl may 303/hang — that's fine, it just boots a container): `/api/v3/<slug>/<action>` with a minimal payload (sequence/DNA/PDB[fetch RCSB 1CRN]/EC). Wait ~60-90s.
3. **Verify via logs (the real signal):** `timeout 25 modal app logs <app> --env biolm-models-dev | grep -iE "Runner failed|Traceback|OSError|Can't load|Exception"` → **0 = PASS** (loaded clean); any hit = FAIL (capture the exception → fix → re-deploy).

## Reconciled deploy state (2026-06-30/07-01)
| Model | Variant | Deploy | Runtime-verified (logs) | Notes |
|---|---|---|---|---|
| esm2 | 150m | ✅ new path | ✅ | r2_then_library; encode → 640-dim embeddings (full invoke ok) |
| zymctrl | single | ✅ new path | ✅ | **FIXED snapshot-path bug** (get_model_dir→build_hf_snapshot_path); clean memory-snapshot restore, 0 errors |
| thermompnn | single | ✅ new path | ⬜ | **FIXED missing PROTEIN_MPNN_CHECKPOINT**; deploy ok; NOT yet log-verified at cold start (PDB-input predict) |
| biotite | single | ✅ (Wave2a) | ⬜ | weightless; not log-verified |
| dna_chisel | single | ✅ (Wave2a) | ⬜ | weightless; not log-verified |
| esm-if1, igt5-paired, abodybuilder3-plddt, protein-mpnn | — | ⚠️ OLD path (Milestone A) | — | **RE-DEPLOY for new biolm-hub/ path** |
| peptides | — | ⚠️ deployed but DROPPED | — | `modal app stop peptides --env biolm-models-dev` |

**Snapshot-bug audit (r2_then_hf):** zymctrl was the ONLY victim. dnabert2/esmc/omni_dna/spurs/dsm/e1 all
resolve the snapshot in app.py already (verified) — OK, no fix. igt5/esm1b/esm1v/igbert/prostt5 use the
canonical get_model_dir pattern — OK.

**Wave-2a lesson:** a subagent died after 2/5 deploys (deploys are slow → subagents time out/die on big
batches). Use SMALL batches (2-3 models) per subagent; report incrementally.

## Wave 2 — CPU + T4 (small) — ⬜
ablang2 (CPU) · antifold (CPU) · biotite (CPU, weightless) · dna_chisel (CPU, weightless) · dnabert2 (T4) ·
esm1b (T4) · esm_if1 (T4) · igbert ×2 (T4) · igt5 ×2 (T4) · spurs (T4) · zymctrl ✅ · thermompnn_d (T4) ·
esm2-8m/35m/650m · e1-150m (T4) · sadie (CPU) · prody (CPU) · mpnn (CPU) · esm1v ×5 (CPU)

## Wave 3 — L4 / A10G — ⬜
evo ×2 · evo2 ×2 · omni_dna ×3 · prostt5 ×2 · e1-650m/3b · dsm 150m/650m/650m-ppi · esmc · esmfold (A10G, 3B) ·
pro1 ×2 · temberture ×2 (T4) · immunefold ×2 (T4) · immunebuilder ×4 (CPU) · msa_transformer (T4) ·
progen2 oas/med/large/BFD90 · tempro ×2 (CPU) · deepviscosity (CPU)

## Wave 4 — A100 / L40S (largest, costliest) — ⬜
boltzgen (A100_40) · rf3 (A100_40) · chai1 (A100_80) · dsm-3B (A100_40) · abodybuilder3 plddt+language (L40S) ·
esm2-3B (T4+L40S)

## Failures / fixes log
- **thermompnn**: missing `PROTEIN_MPNN_CHECKPOINT` in config.py (port-drift) → fixed `8e..`, re-deployed ✅.

## Watch-items
- antifold OPIG univ-server URL liveness (first cold start). · sadie pip→uv (deferred). · evo2 dead branch.
- e1 cu11.8 CUDA tag (verify on e1 deploy). · Structure-input models (mpnn/esm_if1/antifold/thermompnn/
  immunefold/abodybuilder3/prody/rf3/chai1) need a PDB for invoke — fetch a small one (e.g. RCSB 1CRN).
- Old-path apps from Milestone A (protein-mpnn, esm-if1, igt5-paired, abodybuilder3-plddt) need RE-deploy for new path.
</content>
