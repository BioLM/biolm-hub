# Round-1 fix campaign — Phase B deferred items (CLOSED ledger)

Phase B (per-model fan-out, 2026-06-30) applied the Modal-free, model-local fixes from each
`models/<m>.md` review and deferred the items below. **As of 2026-07-05 this ledger is CLOSED**: every
item is either DONE (with the commit/mechanism) or reclassified POST-V1 (with the reason). Milestone B
(all 36 models deploy + integration green on `biolm-hub-dev`) resolved the deploy-gated items; the
schema-uniformity pass (`3024aaa`) and commons pass (`88c2474`) resolved the code items; the residual
K3 params-optionality fix (2026-07-05) closes the last schema-uniformity item.

## A. Response-output shape/rename changes — DONE (Milestone-B deploy-verified, applied with aliases)
- `ablang2` — **DONE** (`3024aaa`): encode unified — `seqcoding`→`embeddings`, `rescoding`→
  `residue_embeddings`, `likelihood`→`logits`; the `Union[Seqcoding,Rescoding]Response` collapsed to one
  type. Old names preserved via validation aliases.
- `abodybuilder3` — **DONE**: pLDDT response type corrected from `Optional[list[list[float]]]` to the
  flat `Optional[list[float]]` that the runtime `squeeze(0).tolist()` actually returns; deploy-verified
  at Milestone B (abodybuilder3-plddt integration green).
- `esm1v` — **RECLASSIFIED (not a defect; kept as-is)**: predict returns `token`/`token_str`/`score`,
  which is a fill-mask *ensemble variant-effect* output, semantically distinct from the
  `logits`/`sequence_tokens`/`vocab_tokens` shape of esm2/esm1b. Documented as intentional rather than
  forced into the LM-logits shape.
- `temberture` — **DONE** (`3024aaa`): per-position output converged to the catalog-canonical
  `residue_embeddings`; `cls_embeddings`→`bos_embeddings`. Old names preserved via aliases.
- `igbert` / `igt5` — **DONE** (`3024aaa`): embeddings sliced to true sequence length (special/pad rows
  removed; no longer batch-padding-dependent).
- `omni_dna` — **DONE**: encode now returns the standard house `results: list[OmniDNAEncodeResponseResult]`
  wrapper (`mean`/`last` fields); the length-1 list-of-objects divergence is gone.

## B. Cross-model coordinated passes — DONE / MOOT
- Confidence-field convergence — **DONE** (`3024aaa`): `mean_plddt` pinned in the glossary; esmfold/
  immunefold `plddt`→`mean_plddt`; bare `plddt` intentionally left per-model (per-residue list in folding
  models vs boolean request flag elsewhere — documented in the glossary). **Tm-field convergence is
  MOOT**: `esmstabp` and `tempro` were both dropped from the catalog, leaving `temberture` (`prediction`)
  as the sole Tm model — no cross-model convergence remains.
- `*PredictLogProb*` / `...Predict...`-for-non-predict class-name drift — **DONE**: LogProb/Score request
  classes are now named after their action verb (e.g. `ESM2LogProbRequest`, `DSMScoreRequest`,
  `AbLang2LogProbRequest`); no `*PredictLogProb*` classes remain in the catalog.
- Response DTOs inheriting `RequestModel` — **DONE** (`3024aaa`): the 4 offending DTOs re-based to
  `ResponseModel`.

## C. Commons-scope lifts — DONE / POST-V1
- `seed_everything` lift — **DONE** (`88c2474`): lifted to `commons.util.device.seed_torch`
  (abodybuilder3/immunebuilder copy-paste de-duped).
- `build_partial_payload` de-dup + sadie gateway serialization — **DONE** (`88c2474`): payload closure
  de-duped in `decorator.py`; sadie's `__reduce__` stopgap removed (gateway round-trip deploy-verified at
  Milestone B).
- `STANDARD_PROTEIN_HOMOLOGS` shared test asset (e1) — **POST-V1**: marginal with a single consumer; add
  to `commons/testing/shared_assets.py` when a second model reuses it.
- `chai1`/`omni_dna` acquisition-path refactors touching the commons caching contract — **POST-V1**: both
  models acquire weights and deploy correctly (Milestone B); the refactor is optional cleanliness, not a
  defect.

## D. R2-artifact-dependent — DONE (Milestone B) / accepted convention
- Numerical-verification rows (boltzgen, immunebuilder, esm2, …) — **DONE**: numeric golden verification
  ran and passed for all 36 models at Milestone B. Reproducible *standard benchmarks* (ProteinGym, etc.)
  are tracked separately in `FUTURE_WORK.md` (POST-V1).
- `sources.yaml` primary `md_r2`/`commit`/`snapshot_r2` "pending" placeholders — **accepted house
  convention** (not a launch blocker): the docs generator does not render internal `*_r2` paths, and the
  deploy-populated R2 artifacts landed at Milestone B.
- `chai1` pre-caching ESM-2 3B embedding weights into R2 — **POST-V1**: a cold-start optimization; chai1
  folds correctly without it (Milestone B deploy-verified).

## E. Lower-priority cleanups — POST-V1 / accepted convention
- `dna_chisel` encode 20-branch if-chain + assorted `# noqa: C901` refactors — **POST-V1** code polish
  (no API impact).
- Input `max_length` bounds (dsm, others) — **POST-V1**: needs a profiling/human decision.
- `applied_literature` `pdf_r2: pending` entries — **accepted house convention** (not a defect).

## F. Residual K3 (2026-07-05) — params-optionality — DONE
- Request schemas whose `params` field lacked a default made `params` *required*, contradicting its
  "optional / defaults used when omitted" description on the docs pages. **DONE**: added
  `default_factory` to `mpnn` (`AllMPNNGenerateParams`), `thermompnn` (`ThermoMPNNPredictParams`), and
  `thermompnn_d` (`ThermoMPNNDPredictParams`) — all three params classes instantiate cleanly with no
  args, so omitting `params` now uses defaults (no golden impact; existing fixtures send `params`
  explicitly and validate identically). **`antifold` FLAGGED, not forced**: its params carry the required
  PDB chain selectors (a `model_validator` requires at least one of `heavy_chain_id`/`light_chain_id`), so
  there is no valid empty default — `params` is genuinely required, and its description was corrected to
  say so.

> The CI-config items deferred in Phase A (mypy over `.github/scripts`; gitleaks gate; T20-ignore
> narrowing) were tracked in `REMAINING_WORK.md` and have since been closed (strict mypy over
> `.github/scripts` is now blocking in CI — commits `bbe2c64`/`6e28b42`/`bf53763`/`98e91ff`).
