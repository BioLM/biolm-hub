# Review — `models/thermompnn/`

## Summary

ThermoMPNN is a structure-based ddG predictor (ProteinMPNN transfer-learning GNN) exposed via a single
`predict` action that handles both targeted single-point mutations and a full site-saturation-mutagenesis
(SSM) scan. The plumbing is largely conformant to the house pattern: standard file layout is complete
(app/config/schema/test/download + 5-file knowledge graph + LICENSE, plus `util.py`/`fixture.py` helpers),
the closed action set is respected (`predict`, consistent with the stability siblings `esmstabp`/`temberture`),
acquisition uses the canonical `r2_then_urls` and self-populates R2, structured logging is used throughout
with no `print`, and the per-model `LICENSE` is permissive MIT consistent with `sources.yaml`. Memory-snapshot
loading, deterministic seeding, eval-mode + `torch.no_grad()`, and per-request temp-dir cleanup are all done.

The notable issues are: (1) a **documentation/runtime mismatch** — mutation positions are documented as
"1-indexed PDB numbering" but the code uses contiguous chain-sequence indices, which silently mis-targets
residues for any PDB not numbered from 1; (2) **caller-mistake conditions in `util.predict` raise bare
`ValueError`** that escape the `UserError`/`ServerError` taxonomy and surface as HTTP 500; (3) knowledge-graph
hygiene — `sources.yaml` ships nine `pending` placeholders and `BIOLOGY.md` carries a `TODO` plus a stale
"no applied literature catalogued" claim that contradicts the five entries actually present in `sources.yaml`.
The rest are uniformity nits (snapshot strategy differs from the esm2/dummy GPU-snapshot pattern, dead
params/attributes, an unenforced `max_sequence_len`, a copyright-line transcription drift, and two dangling
comparison cross-refs).

**DoD audit (per-model):** layout ✓ · actions ✓ · field descriptions render ✓ · errors **partial** (validator
path fine, runtime path leaks `ValueError`→500) · logging ✓ (no `print`) · acquisition ✓ (self-populates) ·
licensing ✓ (MIT, minor transcription nit) · knowledge graph **partial** (`pending`/`TODO`/stale section) ·
tests ✓ (integration + deployment, lazy fixtures).

---

## 🔴 Must-fix

_None._ No correctness/security defect, secret, broken public contract, license problem, or unmet DoD item
rises to launch-blocking on its own. (See 🟠 #5 for the `qa` reference, which is leak-category per the rubric
but is a systemic repo-wide artifact rather than a thermompnn-specific defect.)

---

## 🟠 Should-fix

### 1. Mutation positions are documented as "PDB numbering" but the code uses contiguous chain-sequence indices
- **Category:** correctness / accuracy of field description
- **Location:** `schema.py:48-51` & `:110`, `util.py:208-214` & `:122-144`, `README.md:40` & `:150`, `MODEL.md:103`
- **Detail:** For user-supplied mutations the only transform is `position_0_indexed = position - 1`
  (`util.py:213-214`); for the SSM path positions come straight from `range(len(pdb["seq"]))`
  (`get_ssm_mutations`, `util.py:134`). There is no mapping through the PDB's own residue numbers anywhere —
  both paths index into the contiguous parsed chain sequence. Yet the schema says mutations are
  `'WT{position}MUT' (e.g. 'A100V')`, the response `position` is described as "Residue position (1-indexed)",
  and `README.md:150` states "Mutation positions are 1-indexed in API (matching PDB numbering)". For the very
  common case of a crystal structure whose first modeled residue is not numbered 1 (or has gaps), a user asking
  for `A45V` will silently get the 45th residue in the chain (not PDB residue 45), and the response will echo
  `position: 45`. This is a silently-wrong answer, not just a doc nit. (Wildtype letters in user mutations are
  also not checked against the actual residue at that position, compounding the silent-mismatch risk.)
- **Fix:** Either (a) map user positions through the parsed PDB residue numbering and validate the supplied
  wildtype against the structure, or (b) if sequence-index semantics are intentional, correct every doc/field
  description to say "1-indexed position within the selected chain's modeled sequence (not PDB residue
  numbers)" and add a note that the WT letter must match the structure.

### 2. Caller-mistake conditions in `util.predict` raise bare `ValueError` → surface as HTTP 500
- **Category:** errors (typed taxonomy)
- **Location:** `util.py:171` (`raise ValueError("No chains found in PDB file")`), `:199-206`; `app.py:214-221`
- **Detail:** `app.py` only wraps *params* validation in `try/except ValidationError → UserError`
  (`app.py:191-197`). The actual inference call `predict(...)` (`app.py:216`) is not guarded, so a bad
  user-controlled chain (e.g. `chain="Z"` not in the structure → empty parse downstream), a structure that
  yields no chains, or an out-of-range position raises a plain `ValueError`/`IndexError`. The `modal_endpoint`
  `ERROR_MAP` (`commons/core/decorator.py:417-430`) has no entry for `ValueError`, so these fall through to the
  generic "Uncaught exception" 500 handler rather than a 400 `UserError`. Caller mistakes should be 4xx.
  (Note: the bare `ValueError`s inside the Pydantic `@model_validator` at `schema.py:53-85` are fine — Pydantic
  converts them to `ValidationError` → 422 — so those are *not* part of this finding.)
- **Fix:** Validate the chain exists and positions are in range up front and raise `UserError` (with a stable
  `code`); or wrap the `predict(...)` call to translate caller-facing `ValueError`s into `UserError`. Leave
  genuine system faults to propagate.

### 3. `sources.yaml` ships nine `pending` placeholder values
- **Category:** knowledge graph completeness
- **Location:** `sources.yaml:42-43, 58, 70-71, 83-84, 95-96`
- **Detail:** Five of the six `applied_literature` entries have `pdf_r2: pending` / `md_r2: pending`. The rubric
  (A9) calls out shipping `pending` placeholders; the reference `esm2`/`dummy` `sources.yaml` have none. Either
  the archival is incomplete or `pending` is being used as a sentinel that should not ship publicly.
- **Fix:** Populate the real R2 paths, or drop the `pdf_r2`/`md_r2` keys for not-yet-archived references (use
  `null`/omit rather than the literal string `pending`), consistent with the other models.

### 4. `BIOLOGY.md` contradicts `sources.yaml` and carries a `TODO`
- **Category:** knowledge graph consistency / TODO residue
- **Location:** `BIOLOGY.md:43-45`
- **Detail:** BIOLOGY.md states "No applied literature entries have been catalogued yet." and embeds
  `<!-- TODO: Search for papers citing ThermoMPNN ... -->`, but `sources.yaml:34-99` already lists five
  `applied_literature` entries and `comparison.yaml` is fully populated. A shipped `TODO` and a stale,
  self-contradicting "Applied Use Cases" section is exactly the template residue the rubric flags.
- **Fix:** Remove the `TODO` comment and replace the "Applied Use Cases" placeholder with a short summary drawn
  from the `applied_literature` already captured in `sources.yaml` (HyperMPNN design work, Human Domainome
  benchmarking, SPURS comparison, etc.).

### 5. Internal `qa` environment referenced in the deploy docstring (systemic)
- **Category:** internal-reference leak
- **Location:** `app.py:241` (`# Force deploy to "qa" or "main" environment:`)
- **Detail:** Per rubric §C/severity, an internal `qa` env name in shipped files is a leak. This exact comment
  is also present in the reference `esm2/app.py:484`, so it is a templated artifact, not a thermompnn-specific
  defect — hence 🟠 here with the recommendation that a global reviewer sweep it repo-wide rather than patching
  one model. It is a non-functional comment.
- **Fix:** Repo-wide: reword the deploy-usage comment to drop the internal environment name (e.g. "Force deploy
  to the target Modal environment").

---

## 🟡 Nits

### 6. Snapshot strategy diverges from the esm2/dummy GPU-snapshot house pattern
- **Category:** uniformity
- **Location:** `app.py:116-174`
- **Detail:** esm2/dummy use a single `@modal.enter(snap=True)` that loads directly on GPU together with
  `experimental_options={"enable_gpu_snapshot": True}` on `@app.cls`. ThermoMPNN instead uses two enter methods
  — `load_model(snap=True)` on CPU then `setup_model(snap=False)` to transfer to GPU — and omits
  `enable_gpu_snapshot`. Both are valid Modal patterns (the CPU-snap/GPU-restore approach is arguably more
  conservative), but it is a plumbing difference from the two reference models.
- **Fix:** Either align with the esm2 GPU-snapshot pattern, or add a one-line comment explaining the deliberate
  CPU-snapshot choice so the divergence reads as intentional.

### 7. Dead parameter and unused attribute
- **Category:** simplicity / dead code
- **Location:** `util.py:24` & `:33` (`protein_mpnn_checkpoint` param is documented "unused, kept for
  compatibility" and never referenced), `app.py:149` & `:152` (`self.config` is stored but never read;
  `PROTEIN_MPNN_CHECKPOINT` is passed only to the dead param)
- **Detail:** The ProteinMPNN backbone is located via `cfg.platform.thermompnn_dir` + the
  `vanilla_model_weights/` layout enforced in `download.py`, so the checkpoint name argument does nothing.
- **Fix:** Drop the `protein_mpnn_checkpoint` parameter and the `PROTEIN_MPNN_CHECKPOINT` import/pass-through in
  `app.py`; assign `self.model, _ = load_thermompnn(...)` (or drop the returned config entirely).

### 8. `max_sequence_len`/`batch_size` declared but not wired into the schema; 1024-residue limit unenforced
- **Category:** correctness / consistency
- **Location:** `schema.py:21-22`, `schema.py:97-98`
- **Detail:** `ThermoMPNNParams.max_sequence_len = 1024` and `batch_size = 1` are set but unused — the item cap
  is hardcoded `max_length=1` (esm2 references `ESM2Params.batch_size`), and the PDB Field bounds only by
  `max_pdb_str_len` (~2.5 MB), not residue count. README/MODEL/comparison all advertise a hard "up to 1024
  residues" limit, but a 1500-residue structure under 2.5 MB is accepted and will OOM on the T4 (→ 500) rather
  than getting a clean 400.
- **Fix:** Reference `ThermoMPNNParams.batch_size` for the items `max_length`, and either enforce the residue
  cap (count residues post-parse and raise `UserError` over 1024) or soften the docs to "guideline, not
  enforced".

### 9. LICENSE copyright line drifts from upstream
- **Category:** licensing / attribution
- **Location:** `LICENSE:3`
- **Detail:** Local file says `Copyright (c) 2023 Kuhlman Lab`; the upstream ThermoMPNN LICENSE reads
  `Copyright (c) 2023 Kuhlman-Lab` (verified). MIT requires the notice be reproduced verbatim. Also, the bundled
  ProteinMPNN backbone weights carry their own MIT license (Dauparas et al. / University of Washington) that is
  not separately captured in `LICENSE`/`sources.yaml`.
- **Fix:** Match the upstream holder string exactly (`Kuhlman-Lab`), and add a short ProteinMPNN attribution
  note (license + source) to `sources.yaml`/`LICENSE` since its weights are an inference dependency.

### 10. `comparison.yaml` references models absent from this repo
- **Category:** cross-model consistency
- **Location:** `comparison.yaml:52` (`gemme`) and `:66` (`camsol`); also referenced in `dont_use_when`
- **Detail:** Of the slugs referenced, `gemme` and `camsol` have no `models/<slug>/` directory in this repo
  (the others — `thermompnn_d`, `spurs`, `esmstabp`, `temberture`, `boltz`, `esm2` — all resolve). Dangling
  cross-references will break any tooling that links comparison entries to catalog models.
- **Fix:** Confirm these two are in-scope for the OSS catalog; if not, remove the `gemme`/`camsol` entries (or
  gate them until those models land).

### 11. `from datasets import Mutation` shadows the HuggingFace `datasets` package name
- **Category:** robustness
- **Location:** `util.py:13`
- **Detail:** `datasets` here is ThermoMPNN's local module (resolved via the `sys.path.insert(0, "/root/ThermoMPNN")`
  at `util.py:11`). It works only because HF `datasets` is not installed in the image and the insert is at
  index 0; it is a fragile name collision that a future dependency could break silently.
- **Fix:** Import via the package path (e.g. `from ThermoMPNN.datasets import Mutation` after adding the parent
  to `sys.path`) or alias to avoid the bare common name.

### 12. Test validator type hint uses a non-Optional default
- **Category:** readability / typing
- **Location:** `test.py:8`
- **Detail:** `def _validate_thermompnn_predict(actual_output: dict, _expected_output: dict = None)` — the
  defaulted `dict = None` should be `Optional[dict] = None` for correct typing.
- **Fix:** `_expected_output: Optional[dict] = None`.

## Verification

Adversarial re-review of the five HIGH-severity findings (re-read actual code/files, attempted to refute):

1. **Mutation positions documented as PDB numbering but code uses contiguous chain indices** — **REAL.**
   `util.py:213-214` does only `position_0_indexed = position - 1` and SSM uses `range(len(pdb["seq"]))`
   (`util.py:134`); nothing maps through PDB residue numbers, and the wildtype letter is never checked
   against the actual residue (schema validates format only, `schema.py:59-83`). Docs claim "1-indexed
   PDB numbering" (`README.md:40`, `MODEL.md:103`, util docstring `:160/:188`). Mirroring the SSM
   script's `range(len)` confirms `Mutation.position` is a contiguous 0-indexed offset, not a PDB
   number, so structures not numbered from 1 / with gaps silently mis-target and echo the wrong position.

2. **Caller-mistake ValueError/IndexError from predict() surface as HTTP 500 not 400** — **REAL.**
   `app.py:214-233` wraps `predict()` only in try/`finally` (no UserError-converting `except`); only
   params validation is guarded (`app.py:191-197`). `ERROR_MAP` (`decorator.py:417-430`) has no
   `ValueError`/`IndexError` entry, so the no-chains `ValueError` (`util.py:171`) and (clearest case)
   an out-of-range position — never range-checked anywhere, since `schema.py:69` only checks numeric —
   hit the fall-through "Uncaught exception" 500 (`decorator.py:454-459`). Note `util.py:199-206` is
   largely redundant with the schema validator, but the no-chains/out-of-range paths stand.

3. **sources.yaml ships nine `pending` placeholders, "references have none"** — **REFUTED.**
   The count is right (9 `pending` at `:42-43,58,70-71,83-84,95-96`), but the finding's load-bearing
   claim that reference `esm2`/`dummy` have none is false: `esm2/sources.yaml:62-107` ships **12**
   `pending` values and `dummy/sources.yaml:107,111,137,145` documents `pending` as the accepted
   sentinel ("Set to "" or "pending" if not yet uploaded"). So `pending` is an established codebase
   convention matching the reference model, not a thermompnn-specific defect.

4. **BIOLOGY.md contradicts sources.yaml and embeds a TODO** — **REAL.**
   `BIOLOGY.md:43` says "No applied literature entries have been catalogued yet." and `:45` ships a
   `<!-- TODO: Search for papers citing ThermoMPNN ... -->`, while `sources.yaml:34-99` lists five
   applied_literature entries and `comparison.yaml` is fully populated. Direct, verifiable contradiction
   plus shipped template residue.

5. **Internal `qa` env name in deploy docstring (systemic)** — **REAL (low severity / systemic).**
   The string exists at `app.py:241` ("Force deploy to "qa" or "main" environment:"), identical to
   `esm2/app.py:484` and ~18 other models' app.py. Non-functional comment, generic non-secret term,
   templated repo-wide; correctly self-flagged orange with a repo-wide-sweep recommendation rather than
   a thermompnn-specific or sensitive leak.
