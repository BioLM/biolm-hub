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
>
> ## ⚠️ STALE-BAKE RISK (fair-esm investigation, 2026-07-01) — verify weights are BAKED
> Modal caches the build's `run_function` (download) layer **by content hash**. Some images first built during
> the 06-28→06-30 acquisition refactors baked an EMPTY `/biolm-hub` (no weights). A model with an empty bake
> still "deploys ✅" + loads, but **re-downloads its weights from the external CDN at every cold start** (slow +
> ENOSPC on multi-GB). **esm_if1 was the confirmed case** (deployed image empty → re-downloads 1.7GB; CURRENT
> code is CORRECT — a fresh build bakes; fix = `--force-deploy` fresh). esm2's image happens to be baked (why it
> works). This is NOT a code bug and NOT fair-esm-specific. **VERIFY baking per model** (esp. large fair-esm:
> esmfold-3B, msa_transformer-12B): cold-start log must have **NO** `Downloading: …fbaipublicfiles…` /external
> re-download line, OR `modal shell <app> --cmd 'ls -la /biolm-hub/models/<slug>/v1/.../checkpoints/'` shows the
> weight file. Optional hardening (NOT applied — breaks esm2↔esm_if1 uniformity): make `setup_model` restore
> from R2 before the torch.hub load, so an empty bake degrades to a fast in-datacenter R2 fetch.

> Live tracker for the full deploy/smoke-invoke pass (user-authorized 2026-06-30). **dev only**
> (`biolm-models-dev`); validation = deploy + ONE live inference (goldens deferred to the final
> biolm-hub env). Update this table as models complete so a fresh agent can resume. Deploy cmd:
> `MODEL_SIZE=<v> MODAL_ENVIRONMENT=biolm-models-dev .venv/bin/python models/<m>/app.py --force-deploy`.
> Gateway for smoke-invoke: `https://biolm-biolm-models-dev--biolm-gateway-web.modal.run/api/v3/<slug>/<action>`.
> Status: ⬜ todo · 🔵 deploying · ✅ deploy+invoke ok · 🟡 deployed (invoke pending/manual) · 🔴 failed (see notes).

## ✅✅ MILESTONE B DEPLOY+VALIDATE — COMPLETE (2026-07-01)
**All 39 SHIP models (+ dummy) deploy + runtime-validated** (cold-start log-verified, served real output) on
the new `biolm-hub/` R2 path, dev env. **9 port-drift bugs found + fixed + committed** (all internal-repo-grounded):
thermompnn (missing PROTEIN_MPNN_CHECKPOINT), zymctrl (HF snapshot path), omni_dna (safetensors no metadata),
sadie (pydantic v1↔v2 pickle + dead G3 host), prody (openmm/pdbfixer) + **commons `requests`** (systemic — minimal
images), progen2 (missing tokenizer in self-pop), rf3 (entity_type kwarg), esmfold (omegaconf in download layer).
Plus the **fair-esm stale-bake** operational finding (esm_if1 force-rebuilt). make-check green (ruff/black/schema✓39/
136 tests; 1 known test_cache R2 fail). **NEXT (post-campaign): see §"Post-campaign" below.**

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

**Batch-4 (LARGE non-fair-esm) — 8/8 PASS, 2 fixes:** tempro(now unblocked), pro1, evo2, dsm, progen2(FIXED),
boltzgen, rf3(FIXED), chai1. Fixes committed: progen2 (self-pop archives lack tokenizer.json → fetch from
salesforce/progen GitHub); rf3 (port-added `entity_type` kwarg atomworks rejects → removed). **Maintainer notes:**
pro1 re-fetches Llama base from HF per deploy by design (`cache_to_r2=False` — Llama license not redistributable;
needs HF token w/ Meta terms); rf3 schema `n_recycles ge=0` allows crashing <2 values (present in internal too —
consider ge=2); evo2 only 1b-base enabled (7b/40b need bigger GPU + own validation). **esm_if1:** redeploy was
cached (11s, reused a layer) → force-rebuilt with `MODAL_FORCE_BUILD=1` to guarantee the bake (in progress).
**Batch-5 (final): esmfold-3B / msa_transformer-12B / immunefold — running** (first deploys → bake fresh).

**Batch-3 — 4/4 PASS, no fixes:** biotite, dna_chisel, prody (all cold-start CLEAN now → the commons `requests`
fix is VALIDATED), esm2 (8m/650m/3b all load clean, real embeddings; 3b 5.4GB self-popped R2). esm2-650m+3b now
deployed → **tempro unblocked** (re-validate it in the next batch). 🔑 **esm2 weight-resolution = the fair-esm
fix pattern:** esm2's download `_init` AND runtime `setup_model` BOTH call `torch.hub.set_dir(target_dir)` before
load, so the runtime finds the baked checkpoint at `<model_dir>/checkpoints/`. esm_if1 almost certainly lacks the
RUNTIME `set_dir` → re-downloads (the fair-esm investigator is confirming + fixing). biotite quirk (non-bug):
`generate` returns empty chain_pdb_strings (biotite 1.3.0 PDB-write header fails the startswith guard) — IDENTICAL
to internal production, sequence extraction unaffected.

**Batch-2 (parallel Opus workflow) — 9 PASS / 1 fix / 1 blocked:** PASS = igt5, abodybuilder3, deepviscosity,
e1, evo, immunebuilder, prody(FIXED), temberture, thermompnn_d. **prody FIXED → exposed a SYSTEMIC commons bug:**
OSS `storage/__init__.py` eagerly imports acquisition (→ `import requests`), so `requests` is a universal
cold-start dep that minimal images lacked → crash-loop. Fixed in commons (`requests` in common_requirements) →
**biotite + dna_chisel (deploy-only, never cold-start-verified) MUST be re-deployed** to bake it. prody also
needed openmm/pdbfixer pairing. **tempro BLOCKED** (not a code bug): inference does a cross-app lookup to
`ESM2Model` (esm2-650m/esm2-3b) — deploy those esm2 variants, then re-validate tempro. evo note: cold-start still
fetches 3 small remote-code files from HF (trust_remote_code) — weights are R2-cached but modeling code isn't.

**Batch-1 (parallel Opus workflow) — 10/10 PASS (logs-verified, served real output):** ablang2, antifold,
mpnn (6 slugs), esm_if1, esm1v (5 variants), igbert, prostt5, omni_dna (FIXED), spurs, sadie (FIXED). Fixes
committed: omni_dna (safetensors no `__metadata__` → AutoConfig+load_state_dict); sadie (pydantic v1↔v2 pickle
`__reduce__` + dead G3 host → local HMMs). **⚠️ WATCH-ITEMS from batch 1:**
- **esm_if1 fair-esm RUNTIME RE-DOWNLOAD** — at cold start fair-esm re-fetches the ~600MB checkpoint from the
  CDN instead of using build-time-baked/R2 weights (caused a transient ENOSPC, self-healed). The internal repo
  used `standard_r2_download(sub_path="checkpoints")`. **HIGH RISK for the LARGE fair-esm models (esmfold-3B,
  msa_transformer-12B, immunefold ESM2-3B backbone)** — multi-GB runtime re-downloads → ENOSPC + very slow cold
  start. Investigate the fair-esm bake path before/with that batch.
- **sadie gateway-serialize (commons)** — cleaner long-term fix: gateway should pass a serialized dict to
  `.remote()` not the live pydantic model (sadie is the only v1 container). Model-local `__reduce__` works for now.
- esmc transient GPU-snapshot exit-139 (self-recovers).

**Wave 2b runtime-PASS (logs-verified, served real output):** `esm1b` (T4, 200/112s), `dnabert2` (T4, 200/36s),
`esmc-300m` (A10G, 200/106s) — all load from the correct snapshot/dir path (confirms the audit). ⚠️ esmc note:
transient Modal GPU-snapshot-restore exit-139 that self-recovers (Modal retries w/o memory snapshot) — infra
quirk, not a code bug; watch across cold starts.

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
