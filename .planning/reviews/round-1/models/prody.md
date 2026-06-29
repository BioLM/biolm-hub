# Review — `models/prody/`

**Reviewer:** independent round-1 · **Rubric:** `.planning/reviews/round-1/RUBRIC.md`
**Sibling baselines:** `models/biotite/` (closest analog — structure-in, RMSD `predict`), `models/esm2/`, `models/dummy/`.

## Summary

ProDy is a well-documented, single-variant CPU-only algorithmic wrapper exposing two actions:
`encode` (InSty non-covalent interaction analysis) and `predict` (RMSD). The knowledge graph is rich
and mostly accurate, the layout is standard (no `download.py` is correct — there are no weights), the
LICENSE flags its reconstructed copyright, and there is **no internal-reference leakage** (`biolm-modal`,
`qa`, `.planning`, internal domains all clean). Schema field descriptions render correctly.

The model is, however, the least "plumbing-uniform" of the structural models. The dominant issues are
(1) an **error taxonomy that only half-conforms** — ~12 runtime sites raise bare `ValueError`/`raise`
that fall through to a generic HTTP 500 instead of the typed `UserError`/`ServerError` contract that
the sibling `biotite` follows and that the DoD requires repo-wide; (2) **dead/contradictory surface
area** — an unused `InteractionType` enum and an unused `compute_all_interactions` param, plus a
`comparison.yaml` that advertises an interaction type (disulfide bonds) the code does not compute; and
(3) **heavy double-parsing** of structures inside Pydantic validators that are then re-parsed during
processing. `utils.py` is also far more defensive/clever than the problem demands (38 KB, string-matching
ProDy internal error messages). None of these are security/secret issues; most are quality and
uniformity.

---

## 🔴 Must-fix before launch

### 1. Runtime raises bare `ValueError`/`raise` → falls through to generic 500; user errors misclassified
**Category:** Errors (A.5) / Definition-of-Done (errors enforced repo-wide, `03_WORKSTREAMS.md:330`)
**Location:** `models/prody/utils.py:84, 160, 201, 525, 535, 587, 596, 610, 703, 712, 722, 730, 740, 743, 1007, 1010` (and `app.py:104` re-raise)
**Detail:** The decorator's `ERROR_MAP` (`models/commons/core/decorator.py:417`) only routes `BioLMError`
subclasses (`ValidationError400`, `ModelExecutionError`, …) and Pydantic/Modal exceptions. A bare
`ValueError` raised from runtime code is **not** in the map, so `_handle_errors` falls through to
`"Uncaught exception: {exc}"` with `status_code=500` and `code=None` (`decorator.py:454-462`). ProDy uses
the typed taxonomy in *some* places (`ValidationError400` at `utils.py:40, 546, 560, 920, 938, 954, 959,
980`) but raises bare `ValueError` in many others. Consequences:
- Genuine **caller mistakes** — unparseable structure (`utils.py:201`), "structure too small"/validation
  after H-addition (`587`), non-protein/empty after H-add — are returned as **HTTP 500**, not 400.
- Genuine **system faults** (CIF→PDB conversion `84`, hydrogen addition `160`, RMSD compute `1007`) are
  returned as untyped 500 `"Uncaught exception: …"` rather than `ModelExecutionError` (`system.*` code).
- Raw exception text (including ProDy internals) is echoed to the client verbatim.

The sibling `biotite/app.py` does this correctly (`ValidationError400` for bad input,
`ModelExecutionError` for compute failures). The DoD requires "errors … enforced repo-wide".
**Fix:** Replace every runtime `raise ValueError(...)` / bare `raise` in `utils.py` with the right typed
error — `ValidationError400` for caller-caused conditions (bad/too-small/non-protein structure, no
matching chains), `ModelExecutionError` for ProDy/OpenMM/hydrogen-addition failures. Keep bare
`ValueError` only inside Pydantic validators in `schema.py` (where it is the correct idiom — Pydantic
converts it to a 422). Drop the redundant `app.py:99-104` catch-log-`raise` (the decorator already logs).

---

## 🟠 Should-fix

### 2. `comparison.yaml` advertises "disulfide bonds"; the code computes `repulsive_ionic` instead
**Category:** Knowledge graph accuracy / consistency (A.9, C)
**Location:** `models/prody/comparison.yaml:6` vs `models/prody/utils.py:285-292`
**Detail:** `comparison.yaml` claims "detects 6 interaction types: hydrogen bonds, salt bridges,
hydrophobic contacts, pi-stacking, cation-pi, and **disulfide bonds**". `extract_interactions`
(`utils.py:285-292`) actually computes: `hydrogen_bond, salt_bridge, hydrophobic, pi_stacking, cation_pi,
repulsive_ionic` — **no disulfide bonds**, and `repulsive_ionic` is missing from the claim. The
interaction set is also inconsistent across the 5 KB files: README line 3 lists 5 types (omits
repulsive ionic), README "CAN be used" (line 33) correctly lists repulsive ionic, MODEL.md table
(lines 15-22) correctly lists repulsive ionic, BIOLOGY.md (lines 89-99) lists 5 (omits both). Only
README "CAN be used" and MODEL.md match the code.
**Fix:** Make all five docs agree with the code: hydrogen bonds, salt bridges, hydrophobic, pi-stacking,
cation-pi, repulsive ionic. Remove the "disulfide bonds" claim from `comparison.yaml:6` (or implement
`getDisulfideBonds()` if that capability is actually intended).

### 3. Dead `InteractionType` enum, inconsistent with produced types
**Category:** Simplicity / dead code (B), schema accuracy (A.4)
**Location:** `models/prody/schema.py:501-512`
**Detail:** `InteractionType` is defined but **never referenced** anywhere (`grep` confirms a single
hit). `Interaction.interaction_type` is typed as plain `str` (`schema.py:518`), not this enum. Worse,
the enum's members (`disulfide_bond`, `van_der_waals`, `ionic`, `covalent`) are values the code never
produces, while the value it *does* produce (`repulsive_ionic`) is absent. It reads as an aspirational
placeholder that drifted from the implementation.
**Fix:** Either delete the enum, or wire it up as the type of `Interaction.interaction_type` and make
its members exactly the produced set (`hydrogen_bond, salt_bridge, hydrophobic, pi_stacking, cation_pi,
repulsive_ionic`). The latter would also self-document the response contract.

### 4. Dead `compute_all_interactions` request parameter
**Category:** Simplicity / misleading API (B)
**Location:** `models/prody/schema.py:53-56`, advertised in `README.md:72`
**Detail:** `compute_all_interactions` (default `True`) is declared and documented as a request param,
but is **never read** in `utils.py` or `app.py` (`grep` shows hits only in schema, README, and the
fixture inputs). `extract_interactions` always computes every type regardless. A no-op flag in the
public schema misleads callers.
**Fix:** Remove the field (and the README row), or actually honor it in `extract_interactions`.

### 5. Structures are fully ProDy-parsed twice (validator + processing)
**Category:** Efficiency / modularity (B)
**Location:** `models/prody/schema.py:152-219` (`validate_chains_are_protein`), `schema.py:362-480`
(`validate_chains_exist`) vs `models/prody/utils.py:517, 908-909`
**Detail:** Both request models run `@model_validator(mode="after")` hooks that write the structure to a
temp file and call `parsePDB`/`parseMMCIF` to verify chains are protein. The endpoint logic then writes
to a temp file and parses the *same* structure again in `process_structure_for_insty`/`compute_rmsd`.
For an 8-item batch of large structures (the model advertises `max_sequence_len=10000`, 16 GB RAM) this
doubles parse cost, and with caching enabled the validators re-run on every partial-payload
re-validation (`decorator.py:267`). It also makes the two validators large `# noqa: C901` blocks that
duplicate `_determine_molecule_type` logic.
**Fix:** Do the protein-chain check once, in the processing path (where the structure is already
parsed), and reduce the validators to cheap, parse-free checks (presence/exclusivity of `pdb`/`cif`,
chain-pair shape). This both removes the double parse and shrinks the validator complexity.

### 6. OSS attribution gap for GPL OpenBabel + PDBFixer runtime dependencies
**Category:** Licensing (A.8)
**Location:** `models/prody/app.py:28-47`, `models/prody/LICENSE`, `models/prody/sources.yaml`
**Detail:** The image installs and the runtime invokes **OpenBabel** (`apt` `openbabel` +
`openbabel-wheel==3.1.1.22`, `utils.py:63-70, 119`) and **PDBFixer** (`pip install
git+https://github.com/openmm/pdbfixer.git@v1.8.1`) for hydrogen addition. OpenBabel is **GPL-2.0**;
PDBFixer is MIT. `LICENSE` and `sources.yaml` cover only ProDy (MIT). For an open-source repo, the GPL
OpenBabel dependency (even as an optional, non-default `hydrogen_method`) warrants maintainer/legal
attention, and both extra tools should be acknowledged.
**Fix:** Add OpenBabel and PDBFixer to `sources.yaml` (`source_repos`/notes) and the per-model LICENSE
"this model also uses…" note, and have a maintainer confirm the GPL OpenBabel dependency is acceptable
for distribution (or default-only PDBFixer and gate OpenBabel behind a documented opt-in).

---

## 🟡 Nits / polish

### 7. Unreachable post-calculation hydrogen-addition block
**Location:** `models/prody/utils.py:747-765`
**Detail:** `if params.add_hydrogens and not hydrogens_added:` after the interaction calc is dead when
`add_hydrogens=True` (hydrogens are already added at `563-596`, setting `hydrogens_added=True`, or that
block raises). Leftover scaffolding that recomputes `interactions_obj` for no reason.
**Fix:** Delete the block.

### 8. `PYTHONHASHSEED` set at runtime is a no-op
**Location:** `models/prody/utils.py:499`, `models/prody/app.py:81`
**Detail:** `os.environ["PYTHONHASHSEED"] = "42"` has no effect after the interpreter has started; it
only matters if set before process launch. Presented as a determinism control (MODEL.md "Determinism"
table) but does nothing. `random.seed`/`np.random.seed` are the effective ones.
**Fix:** Drop the `PYTHONHASHSEED` lines (and the MODEL.md row) or set it via the image env, not at
request time.

### 9. `traceback.print_exc()` in runtime code bypasses structured logging
**Location:** `models/prody/utils.py:524, 534`
**Detail:** House rule is "structured logging only — no print" (CLAUDE.md / W6). These write a raw
traceback to stderr from inside `except … : traceback.print_exc(); raise` blocks; they slip past ruff
`T20` (which flags only the `print` builtin) but violate the spirit, and are redundant — the decorator
already logs/handles the re-raised exception.
**Fix:** Remove both `traceback.print_exc()` calls (the surrounding `try/except/raise` adds nothing —
let the exception propagate, or `logger.error(..., exc_info=True)`).

### 10. 50-line investigation TODO shipped in `test.py`
**Location:** `models/prody/test.py:6-55`
**Detail:** A large "TODO: ProDy Encode Test Non-Determinism Investigation" block ships in the test
file. The actionable caveat (±1 H-bond non-determinism) is already documented in MODEL.md/README; the
rest is internal investigation residue. Sibling `biotite/test.py` and `esm2/test.py` are clean.
(`test*.py` is `T20`-exempt, so this is style only.)
**Fix:** Trim to a 2-3 line comment explaining the custom validator; drop the FUTURE IMPROVEMENTS log.

### 11. `enable_memory_snapshot=False` deviates from siblings on a weak rationale
**Location:** `models/prody/app.py:63`
**Detail:** Comment "Disabled: snapshots cached stale code" reads as a dev-time workaround.
biotite/esm2/dummy all use `enable_memory_snapshot=True` (+ `ModelMixinSnap`). prody correctly uses the
non-snapshot `ModelMixin` to match, so it is internally consistent — but a CPU-only deterministic
library is exactly the case that benefits from snapshot cold-start speedup. Confirm the disable is a
real production decision, not a stale-code debugging artifact.
**Fix:** Re-enable snapshots (switch to `ModelMixinSnap`, `@modal.enter(snap=True)`) unless there is a
documented reason ProDy cannot snapshot; otherwise keep a clearer rationale.

### 12. Verb choice for both actions is a stretch of the closed set
**Location:** `models/prody/config.py:43-54`
**Detail:** RMSD is exposed as `predict` and InSty interaction analysis as `encode`. RMSD is a scalar
comparison metric (`score` arguably fits better); InSty returns a dictionary of interactions, not an
embedding/representation (`encode` implies the latter). This is *consistent with* `biotite` (which also
maps RMSD→`predict`), so it is a defensible house choice — flagging for the uniformity discussion, not
as a unilateral prody bug.
**Fix:** None required if the repo standard is "RMSD = predict"; otherwise consider `score` for RMSD.

### 13. `comparison.yaml` over-states per-interaction energy
**Location:** `models/prody/comparison.yaml:8, 29` vs `models/prody/utils.py:240-249`, `schema.py:528`
**Detail:** Strengths/use_when tout "Energy estimation for each interaction … identifying which contacts
contribute most." But the per-`Interaction.energy` field is only populated when ProDy's interaction
lists have >7 elements (`utils.py:245`); the standard InSty getters (`getHydrogenBonds`, etc.) return
7-tuples without energy, so `energy` is in practice `None`. Energy is only available via the optional
`energy_matrix` (`buildInteractionMatrixEnergy`). (Low confidence — could not run ProDy here to confirm
tuple length; please verify.)
**Fix:** Verify against a real run; if confirmed, soften the claim to "interaction energy *matrix*
available on request" rather than "energy estimation for each interaction."

### 14. Same task, two request shapes vs `biotite` (cross-model inconsistency)
**Location:** `models/prody/schema.py:324, 338` vs `models/biotite/schema.py:79-85`
**Detail:** For pairwise RMSD, prody uses separate `chain_a`/`chain_b` (`str | list[str]`) fields while
biotite uses one `chain_ids: {'a': [...], 'b': [...]}` dict. Two shapes for the same "which chains in
each structure" concept across the two structural models. prody's is arguably cleaner; worth aligning
during the uniformity pass.

### 15. `pending` placeholders in `sources.yaml`
**Location:** `models/prody/sources.yaml:29, 36, 47, 54, 57, 64, 66, 73, 75, 83-93`
**Detail:** Several `md_r2: pending` / `snapshot_r2: pending` / `pdf_r2: pending` values. Rubric A.9
flags `pending` as residue, but this is a **repo-wide** convention (biotite's `sources.yaml` uses the
same `pending`), so it is not prody-specific. Noting for the global reviewer to decide whether the
internal `*_r2` ingestion-status fields should ship publicly at all.

---

## D. Definition-of-Done audit (model-scoped)

- **Layout / config (A.1):** ✅ Met. All standard files + 5-file KG present; no `download.py` is correct
  (no weights). `config.py` defines a proper single-variant `ModelFamily`.
- **Canonical actions (A.2):** ⚠️ Partially. Uses only `encode`/`predict` (in-set), but both are loose
  fits (see #12); consistent with biotite.
- **Schema fields / descriptions (A.3, A.4):** ✅ Largely met. `items`/`results`/`params`/`pdb`/`cif`
  used; descriptions render in `model_json_schema()` (verified). Dead enum (#3) is the exception.
- **Errors (A.5):** ❌ **Not met** — see 🔴 #1; this is the DoD "errors enforced repo-wide" gap.
- **Logging (A.6):** ⚠️ Mostly `get_logger`; two `traceback.print_exc()` (#9).
- **Acquisition (A.7):** ✅ N/A (no weights; nothing to self-populate). Test fixtures download from RCSB
  lazily inside `generate()` (not module scope) — correct.
- **Licensing (A.8):** ⚠️ ProDy MIT consistent and copyright reconstruction is flagged in LICENSE, but
  GPL OpenBabel / PDBFixer deps unattributed (#6).
- **Knowledge graph (A.9):** ⚠️ Present and rich, but interaction-type claims contradict the code (#2).
- **Tests (A.10):** ✅ `TestSuite` with integration + deployment cases, lazy fixtures, custom
  tolerance validator for the documented non-determinism. (TODO bloat #10 is cosmetic.)

---

## Verification

Adversarial re-check of the six HIGH-severity findings against the actual code.

- **#1 Bare ValueError → generic HTTP 500 / untyped faults — REAL.** `ERROR_MAP`
  (decorator.py:417-430) contains no `ValueError`; plain `ValueError` is not an
  `isinstance` of any mapped type, so `_handle_errors` falls through to
  `"Uncaught exception: {exc}"`, status 500, `code=None`, echoing raw text
  (decorator.py:454-462). prody/utils.py raises bare `ValueError` at 16 sites
  (84,160,201,535,587,596,610,650,665,703,712,722,730,743,1007,1010) while using
  `ValidationError400` only at 40,546,560,920,938,954,959,980; sibling
  biotite/app.py correctly imports+uses `ValidationError400`/`ModelExecutionError`
  (biotite/app.py:15,257,384). User-mistake cases (parse fail 201, post-H-add
  validation 587) return 500 not 400; system faults (84,160,1007) are untyped 500.
- **#2 comparison.yaml advertises disulfide bonds; code computes repulsive_ionic — REAL.**
  comparison.yaml:6 claims "...cation-pi, and disulfide bonds"; `extract_interactions`
  (utils.py:285-292) computes hydrogen_bond, salt_bridge, hydrophobic, pi_stacking,
  cation_pi, repulsive_ionic — disulfide absent, repulsive_ionic omitted from the claim.
  Cross-file: README:3 + BIOLOGY.md:89-99 list only 5 (omit repulsive ionic); only
  README:33 ("CAN be used") + MODEL.md:15-22 match the code.
- **#3 Dead InteractionType enum — REAL.** Defined schema.py:501-512; `grep` shows the
  sole hit is the definition itself. `Interaction.interaction_type` is `str` (schema.py:518),
  not the enum. Members disulfide_bond/van_der_waals/ionic/covalent are never produced;
  produced value repulsive_ionic is absent from the enum.
- **#4 Dead compute_all_interactions param — REAL.** Declared schema.py:53-56 (default True),
  documented README.md:72; `grep` finds it only in schema, README, and fixture.py inputs —
  never read in utils.py/app.py. `extract_interactions` always computes all 6 types
  unconditionally (utils.py:285-292), so the flag is a no-op.
- **#5 Structure parsed twice via ProDy — REAL.** `@model_validator(mode="after")`
  (schema.py:152-219 encode; 362-480 predict) writes a temp file and calls
  parsePDB/parseMMCIF to check protein chains; processing re-writes + re-parses in
  process_structure_for_insty (utils.py:504-517) and compute_rmsd (utils.py:898-909).
  Partial re-validation re-runs validators via `_validate_payload` (decorator.py:267).
  (The `validate_pdb`/`validate_cif` BeforeValidators are a separate text-level check,
  not ProDy parses — so "twice via ProDy" is accurate, not overstated.)
- **#6 GPL OpenBabel + MIT PDBFixer attribution gap — REAL.** Image installs apt `openbabel`
  + `openbabel-wheel==3.1.1.22` and pip `pdbfixer@v1.8.1` (app.py:28-47); runtime invokes
  OpenMM (utils.py:63-70) and addMissingAtoms with openbabel/pdbfixer (utils.py:119).
  OpenBabel is GPL-2.0, PDBFixer/OpenMM MIT/permissive. LICENSE and sources.yaml cover
  only ProDy (MIT) — no OpenBabel/PDBFixer/OpenMM acknowledgment (README links them but
  the license-tracking files do not). GPL runtime dep in an OSS repo warrants review.

**Summary: 6/6 REAL.** All findings are concretely demonstrable in the cited code.
