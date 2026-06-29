# Round-1 fix campaign — Phase B deferred items (2026-06-30)

Phase B (per-model fan-out) applied the Modal-free, model-local fixes from each `models/<m>.md` review.
These items were intentionally NOT done in Phase B and are tracked here. The authoritative per-item
detail is in the per-model review files + `FIX_PLAN.md`; this groups them by where they belong next.

## A. Response-output shape/rename changes → MILESTONE B (deploy-verify, then apply with an alias)
Changing what a deployed endpoint returns; needs a live deploy to confirm the real runtime shape first.
- `ablang2`: `seqcoding`→`embeddings`, `rescoding`→`per_token_embeddings`; `likelihood`→`logits`; collapse
  encode's `Union[Seqcoding,Rescoding]Response` to one type. (descriptions already pre-aligned, safe)
- `abodybuilder3`: pLDDT response type is `Optional[list[list[float]]]` but runtime `squeeze(0).tolist()`
  is flat `list[float]` → `plddt=True` likely 500s; confirm tensor shape on deploy, then fix type.
- `esm1v`: predict response (`token/token_str/score`) → house `logits/sequence_tokens/vocab_tokens` shape.
- `temberture`: `per_residue_embeddings`→`per_token_embeddings`, `cls_embeddings`→`bos_embeddings`.
- `igbert`/`igt5`: embeddings include special/pad rows (batch-padding-dependent length).
- `omni_dna`: encode length-1 list-of-objects wrapper divergence.

## B. Cross-model coordinated passes (not safe per-model in isolation)
- Confidence/Tm field-name convergence: `plddt` (0-100) canonical; `mean_plddt`/`full_plddt` →; Tm field
  `melting_temperature` vs `tm` vs `prediction` (esmstabp dropped, so now tempro `tm` + temberture
  `prediction`).
- `*PredictLogProb*` / `...Predict...`-for-non-predict class-name drift (~6 models).
- Response DTOs that inherit `RequestModel` instead of `ResponseModel`.

## C. Commons-scope (out of per-model scope) → W3b / commons pass
- Lift `seed_everything` (abodybuilder3/immunebuilder copy-paste) into commons.
- Add a shared `STANDARD_PROTEIN_HOMOLOGS` test asset (e1) to `commons/testing/shared_assets.py`.
- `chai1`/`omni_dna` acquisition-path refactors that touch the commons caching contract.

## D. R2-artifact-dependent → MILESTONE B (need bucket writes / a live deploy)
- `sources.yaml` primary `md_r2`/`commit`/`snapshot_r2` "pending" placeholders (house-wide).
- Benchmark/numerical-verification rows that need a live deploy to fill (boltzgen, immunebuilder, esm2, …).
- `chai1` pre-caching ESM-2 3B embedding weights into R2.

## E. Lower-priority cleanups → Phase-C / future polish
- `dna_chisel` encode 20-branch if-chain simplification; assorted `# noqa: C901` refactors.
- Input `max_length` bounds needing a profiling/human decision (dsm, others).
- `applied_literature` `pdf_r2: pending` entries (accepted house convention).

> The CI-config items deferred in Phase A (mypy over `.github/scripts` = 67 errors; gitleaks gate at
> W-sec; T20-ignore narrowing) are tracked separately in `REMAINING_WORK.md`.
