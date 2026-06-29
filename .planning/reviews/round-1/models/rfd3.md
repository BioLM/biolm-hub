# Review — `models/rfd3/` (RFdiffusion3)

**Reviewer:** independent round-1 (rubric A–D)
**Verdict:** Not launch-ready. The plumbing is mostly conventional and the knowledge-graph is rich, but
the **request schema advertises and tests several conditioning features (`symmetry`, `conditioning_mode`,
`output_format`, …) that `app.py` silently drops** — a documented, tested public-contract that produces
wrong scientific output without error. Secondary issues: error-taxonomy misuse (server faults raised as
`UserError`, raw exception strings leaked), a server-side file-path field exposed to remote callers, a
non-standard nested `results` shape, duplicated R2-caching code, and an internal "verify before public
release" note shipped inside `LICENSE`.

Layout is complete: `app.py`, `config.py`, `schema.py`, `download.py`, `test.py` (+ `test_errors.py`,
`test_motif_scaffolding.py`, `fixture.py`) and all 5 knowledge-graph files are present. `config.py` defines
a proper `ModelFamily` (`modal_class_name="RFD3Model"`, action `generate`, single variant). Shared
sampling fields (`seed`, `temperature`, `diffusion_batch_size`) match `tooling/field_glossary.yaml`
verbatim. No `print()` in runtime code; no `biolm-modal`/`.planning` leakage.

---

## 🔴 Must-fix

### 1. Multiple documented/tested request parameters are silently ignored
**Category:** correctness / broken public contract
**Location:** `models/rfd3/app.py:494-633` (`_create_design_specification`), `models/rfd3/app.py:344-368`
(engine config); `models/rfd3/schema.py:97-134`, `47-69`, `144`

`_create_design_specification` only ever writes these spec keys: `input, length, contig, unindex, ligand,
select_fixed_atoms, partial_t, motif_selection, target_chain`. The following request fields are accepted
by the schema but **never reach the engine** (confirmed by grep — zero references in `app.py`):

- `params.symmetry` and `params.cyclic_chains` — the `symmetric_design` mode is documented in
  `README.md:62/213-246` and `BIOLOGY.md`, and has a dedicated test (`test.py` `INPUT3`, `symmetry="C3"`;
  `fixture.py` `INPUT3`). The value is dropped, so the model returns a **non-symmetric** structure. The
  test still "passes" because `_validate_rfd3_generate` only checks that *a* CIF parses — it never asserts
  C3 symmetry. This is silently-wrong output for an advertised, tested feature.
- `params.conditioning_mode` (5-value enum) — drives nothing; behavior is inferred purely from which input
  fields are present, so the enum can contradict the actual inputs with no effect or warning.
- `params.output_format` (`schema.py:129`, "cif or pdb") — output is always CIF; `pdb` is a no-op.
- `RFD3Component.smiles` and `RFD3Component.ccd_code` (`schema.py:55-58`) — ligands can only be introduced
  via the `ligands` residue-name list; a SMILES/CCD-specified small molecule is dropped.
- `RFD3DesignRequestInput.bonds` (`schema.py:144`) — custom bonds are never emitted.

**Fix:** Either (a) wire each field into the foundry spec (`symmetry`/`cyclic_chains` → the foundry
symmetry keys; `smiles`/`ccd_code` → ligand components; `bonds` → covalent-bond spec; honor
`output_format`), or (b) remove the fields that the implementation does not support and delete/repair the
tests/docs that imply they work. At minimum, `symmetry` must not be silently dropped while a
`symmetric_design` mode + test advertise it. If a mode is unsupported, raise a typed `UserError` rather
than returning a wrong structure.

---

## 🟠 Should-fix

### 2. `input_structure_path` exposes server-side file reads to remote callers
**Category:** security / API contract
**Location:** `models/rfd3/schema.py:154-157`; `models/rfd3/app.py:287-316`

`input_structure_path` is a free-form filesystem path supplied by the API caller; `app.py` then `open()`s
whatever path is given (gated only to `.pdb/.cif/.mmcif` extensions). A remote client has no access to the
container filesystem, so the field is unusable for its stated purpose, and it doubles as a local-file-read
vector (any readable `*.cif`/`*.pdb` on the container, or via symlink). `structure_cif` (CIF passed as a
string) already covers the legitimate use case. (Note: sibling `models/rf3/schema.py:75-84` has the same
`structure_path`/`msa_path` smell — worth a coordinated fix.)
**Fix:** Remove `input_structure_path` from the public schema; accept structures only as `structure_cif`
content. If a path input is genuinely needed internally, keep it off the request model.

### 3. Error taxonomy: server faults raised as `UserError`; raw exception text leaked; setup failure swallowed
**Category:** errors (A5)
**Location:** `models/rfd3/app.py:385-387`, `337-342`, `183-186`

- `app.py:385-387` wraps **any** inference exception (OOM, CUDA, internal bug) in
  `UserError(f"RFdiffusion3 inference failed: {str(e)}")`. System faults must surface as `ServerError`
  (5xx), not a caller-mistake 4xx, and the raw `str(e)` (may contain internal paths/stack detail) should
  not be returned to the caller.
- `app.py:337-342` raises `UserError("...expected during initial setup before foundry integration is
  complete.")` — this is leftover scaffolding language and is a *server* configuration problem, not a user
  error.
- `app.py:183-186` swallows the foundry `ImportError` during `setup_model` ("Don't raise here") so the
  container snapshots/deploys as healthy and then 4xx's on every request. A missing engine should fail
  fast at startup (or be a clear `ServerError` at request time).
**Fix:** Use `ServerError` for engine-unavailable and inference-runtime faults; sanitize messages; let the
foundry import failure fail the container or raise a `ServerError` rather than a `UserError`.

### 4. Non-standard nested `results: list[list[...]]`
**Category:** consistency / schema field names (A3)
**Location:** `models/rfd3/schema.py:213-218`; `models/rfd3/app.py:492`

The house convention is a flat `results: list[...]` keyed per input item (`dummy`, `esm2`, `mpnn`, and —
critically — the closest analog `boltzgen`, which also emits multiple designs per input, all use a flat
list). RFD3 nests `list[list[RFD3DesignResponseResult]]`, and since `batch_size` is fixed to 1 the outer
list is **always** length 1 — pure structural noise. (Sibling `rf3` shares the nesting, so align the
foundry family together.)
**Fix:** Flatten to `results: list[RFD3DesignResponseResult]` (designs returned in order); update
`app.py:492` (`return RFD3DesignResponse(results=results)`) and the test validators.

### 5. Duplicated / partly-dead R2-caching logic
**Category:** modularity / duplication (B)
**Location:** `models/rfd3/download.py:170-217` and `models/rfd3/app.py:194-243`

Both `download_model_assets` (runtime branch) and `_cache_to_r2_if_needed` implement the same
"check `.r2_manifest.json` → `R2Utils.upload_to_r2_atomic`" caching. In practice the download layer runs at
**build** time (`MODAL_IMAGE_BUILD=1`, upload skipped) and `setup_model` only calls `get_model_dir()`
(never `download_model_assets`), so `download.py`'s runtime-upload branch is effectively dead while
`app.py` does the real upload. This is confusing and drift-prone. The canonical `r2_then_*` wrappers don't
cover a CLI fallback, so a documented custom strategy is acceptable (A7), but the caching should live in
one place.
**Fix:** Consolidate R2 caching into a single helper; remove the dead build-vs-runtime branch in
`download.py`.

### 6. `LICENSE` ships an internal reviewer note + unverified copyright
**Category:** licensing (A8) / open-source readiness
**Location:** `models/rfd3/LICENSE:30-37`

The shipped `LICENSE` appends: *"Copyright holder (RosettaCommons Foundation) and year (2025) inferred …
Reviewer should verify the exact copyright line against the upstream LICENSE file before public release."*
Flagging an inferred holder is correct per A8, but a public `LICENSE` should not contain a "before public
release" review instruction, and the verification is an unmet DoD item. `sources.yaml:6` `license.notes`
is empty, so the caveat isn't tracked in the KG either.
**Fix:** Verify the real foundry copyright line, set it exactly, and remove the reviewer note (move any
caveat to `sources.yaml` notes if needed).

---

## 🟡 Nits

### 7. Config `task` tags don't match a structure-only design model
**Location:** `models/rfd3/config.py:52-57`
`task=[SEQUENCE_GENERATION, STRUCTURE_PREDICTION, SEQUENCE_OPTIMIZATION]` but `output_modality=[STRUCTURE]`
only, and `BIOLOGY.md` stresses RFD3 is *design, not prediction* and *does not output sequences*.
`STRUCTURE_PREDICTION` is the de-facto "produces structure" tag (boltzgen uses it too, since the `Task`
enum has no `structure_generation`), but `SEQUENCE_GENERATION`/`SEQUENCE_OPTIMIZATION` are misleading for a
structure-only output. **Fix:** drop the sequence-* tasks (or add a `structure_generation` enum value).

### 8. `structure_cif` lacks the house CIF validator and canonical name
**Location:** `models/rfd3/schema.py:59-61`, `154`
Most models use `cif`/`pdb` fields with `Annotated[str, BeforeValidator(validate_cif/pdb)]`; RFD3 uses an
unvalidated `structure_cif` (and the `input_structure_path` from #2). **Fix:** rename to `cif` and add
`validate_cif` for consistency with the house structure-input pattern.

### 9. README internal inconsistencies vs. code
**Location:** `models/rfd3/README.md:25, 51, 310-313`
Architecture table says Output = "All-atom protein structures (PDB)" while everything else (and `app.py`)
returns mmCIF; `output_format`'s `pdb` option doesn't work (#1); README/MODEL claim max 2048 is "enforced
by `RFD3Params.max_sequence_len`" but `app.py` never validates length/sequence against it. **Fix:** correct
output format to mmCIF, drop the PDB claims, and either enforce or stop claiming the 2048 cap.

### 10. `test_errors.py` cases are effectively no-ops
**Location:** `models/rfd3/test_errors.py:11-158`
Every "error" test only asserts that Pydantic stored the value (e.g.
`assert request.items[0].input_structure_path == "/nonexistent/..."`); none invokes `app.py`, despite
docstrings saying "app.py should reject it". They give false coverage of the validation paths. **Fix:**
exercise the actual `UserError` paths (e.g. call the spec/validation helper) or delete the file.

### 11. Motif-scaffolding test pollutes the repo tree and hits the network
**Location:** `models/rfd3/test_motif_scaffolding.py:186-189, 249-275`
The validator writes generated CIFs into `models/rfd3/motif_scaffolding_outputs/` (committed working-tree
pollution) and downloads `6IM3.cif` from RCSB at import/runtime. (`print`/network are allowed in tests by
ruff, so not a T20 violation — but the artifact dir and live download are still undesirable.) **Fix:**
write to a tmp dir; pull the fixture structure from the shared test-asset library / R2 rather than RCSB.

### 12. Repo-wide: internal `qa` env name in shipped `__main__` docstring
**Location:** `models/rfd3/app.py:675` (`# Force deploy to "qa" or "main" environment:`)
The rubric flags internal `qa` env references, but this comment is repo-wide (esm2, boltzgen, chai1, …)
via the shared deploy entrypoint — defer to a global cleanup rather than treating it as rfd3-specific.

---

## Notes / non-findings (checked, OK)
- `pending` sentinels in `sources.yaml` (12) are the house norm (esm2 also 12, boltzgen 8) — not flagged.
- `TODO`/`TBD` in `MODEL.md`/`README.md` is near-universal (41/44 models) — not treated as rfd3-specific.
- Shared sampling field descriptions (`seed`, `temperature`, `diffusion_batch_size`) match the glossary
  verbatim; `items` uses the correct `Annotated[list, Field(...)]` (description renders).
- `comparison.yaml`/`sources.yaml` `model_slug`/`display_name` are internally consistent with `config.py`.
- No `print()` in runtime code; build-order is fine (foundry CLI installed before the download layer runs).

## D. Definition-of-Done snapshot
- Layout / 5-file KG / `ModelFamily`: **met**.
- Canonical action set (`generate`): **met**.
- Schema uniformity: **partial** — non-standard nested `results` (#4); `structure_cif`/`input_structure_path`
  deviate from `cif`/`pdb` (#8, #2).
- Field descriptions render & match glossary: **met**.
- Error taxonomy: **not met** (#3).
- Logging: **met**.
- Acquisition self-populates bucket via documented custom strategy: **met but duplicated** (#5).
- Licensing permissive & consistent: **partial** — unverified copyright + reviewer note shipped (#6).
- Knowledge graph complete/consistent: **met** (placeholders are house-standard).
- Tests (integration + deployment, lazy fixtures): **partial** — `test_errors.py` no-ops (#10), motif test
  side-effects (#11); generative validators don't assert the conditioning they exercise (#1).
- Correctness: **not met** — silently-ignored conditioning params (#1).
</content>
</invoke>

## Verification

Adversarial re-check of the six HIGH-severity findings against the actual code. All six confirmed **real**; could not refute any.

1. **Silently-ignored request params — REAL.** `grep 'spec\['` in `app.py` yields exactly the 9 keys named (input/length/contig/unindex/ligand/select_fixed_atoms/partial_t/motif_selection/target_chain), and `grep` for `symmetry|cyclic_chains|conditioning_mode|output_format|.smiles|ccd_code|.bonds` across `app.py` returns nothing — none reach the engine. `symmetry` is documented (`README.md:48,62,213-246`) and exercised (`test.py:130-131`, `fixture.py:77-78` `symmetry='C3'`) yet dropped; validator only checks a CIF parses (`test.py:12-64`), so the symmetric test passes on a non-symmetric structure.
2. **input_structure_path server-side file read — REAL (exfil severity limited).** `app.py:287-316` `Path(item.input_structure_path)` → `shutil.copy2` of any caller-supplied path gated only by `.pdb/.cif/.mmcif` (`app.py:302`); `structure_cif` (`app.py:271-282`) already covers the legit remote case. Sibling `rf3/schema.py:75,84` has the same `structure_path`/`msa_path` smell. (Note: output is a generated structure, not the file echoed back, so it is a server-side file-open / existence-probe vector rather than a clean read-and-exfiltrate — but the described behavior is demonstrable.)
3. **Server faults as UserError / leaked text / swallowed ImportError — REAL.** `app.py:385-387` broad `except Exception` → `UserError(f"...{str(e)}")` (system fault as 4xx + raw text); `app.py:337-342` `UserError` carries scaffolding text "expected during initial setup before foundry integration is complete" (a config fault); `app.py:183-186` swallows the foundry `ImportError` ("Don't raise here"), so the container snapshots healthy then 4xx's every request via the 337-342 path.
4. **Nested list[list[...]] results — REAL.** `schema.py:216` `results: list[list[...]]`, `app.py:492` `results=[results]`, `batch_size=1` (`schema.py:26,195`) ⇒ outer list always length 1. Siblings are flat: boltzgen/esm2/mpnn/dummy all `results: list[...]`; only `rf3:241` shares the nesting — confirms the convention deviation.
5. **Duplicated / partly-dead R2 caching — REAL.** Both `download.py:184-211` and `app.py:194-243` call `R2Utils.upload_to_r2_atomic` after a manifest check. `setup_download_layer` runs `download_model_assets` via `image.run_function` at BUILD (`downloader.py:111-121`, `MODAL_IMAGE_BUILD=1` ⇒ upload skipped, `download.py:182-211`); `setup_model` only calls `get_model_dir()` (`app.py:133`), never `download_model_assets` — so the download.py runtime-upload branch is dead and app.py does the real upload. (Finding itself notes A7 permits a custom strategy; this is a maintainability/drift issue, not a correctness bug.)
6. **LICENSE reviewer note + unverified copyright — REAL.** `LICENSE:33-37` contains the inferred-holder caveat and a "Reviewer should verify ... before public release" instruction; `sources.yaml:6` `license.notes: ''` is empty, so the caveat is untracked in the KG.
