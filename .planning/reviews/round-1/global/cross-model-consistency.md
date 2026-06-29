# Cross-model consistency review (Round 1)

**Dimension:** Cross-model consistency — "the diff between any two models should be the science, not the plumbing."
**Scope:** all 44 model packages under `models/` (excluding `commons`), with `models/esm2` + `models/dummy` as the canonical reference shapes.
**Method:** static introspection of every `config.py` / `schema.py` / `app.py` (actions, field names, error usage, logging, file layout, class/base-class shape) plus targeted file reads; ran `tooling/check_schema_docs.py`.

## Summary

The repo is **highly uniform on the mechanical axes** that have automated enforcement, and noticeably less uniform where uniformity depends on author discipline.

What is genuinely consistent (good):
- **File layout** — every model has `app.py`/`config.py`/`schema.py`/`test.py` and the knowledge-graph files; `download.py` is present iff the model has weights. Only `dummy` (the scaffold) deviates.
- **App shape** — all 44 use `@biolm_model_class`, inherit `ModelMixin`/`ModelMixinSnap`, decorate endpoints with `@modal_endpoint`, and use `get_logger`. No stray `print` in runtime container code (only offline `_train.py` and vendored `external/` code).
- **`modal_class_name`** — uniform `<Camel>Model` everywhere.
- **Actions** — every action drawn from the closed set `predict/fold/encode/generate/score/log_prob`; no invented verbs.
- **Batch shape** — `items` request wrapper / `results` response wrapper / `params` block used uniformly.
- **Field descriptions** — `tooling/check_schema_docs.py` passes for all 44 (every field renders a description; shared fields match `field_glossary.yaml` verbatim). This is a strong, CI-enforced consistency guarantee.
- **Antibody convention** — no `vhh` field names anywhere; nanobody = lone `heavy_chain` + VHH-in-description/tag.

Where consistency breaks down (findings below):
- A **cross-cutting internal-env leak** (`qa`) in ~40/44 `app.py` files (🔴).
- The **error taxonomy is half-adopted**: `ServerError`/`ModelExecutionError` are used by **zero** models; ~11 models raise bare builtins for system faults, yielding an inconsistent error contract (🟠).
- The **non-ML "utility/analysis" models** (`biotite`, `prody`, `dna_chisel`) stretch the closed verb set in *different* directions, including `encode` with no embeddings and an `encode` action whose classes are all named `*Predict*` (🟠).
- Field-name and sibling-naming drift: `biotite.pdb_string` vs canonical `pdb`; `boltz.molecules` vs `boltzgen.entities` (🟠).
- `ablang2` carries dead request classes and inconsistent alias/underscore naming (🟠).
- The `dummy` reference model uses a bespoke `*Svc*` shape no real model follows, and is missing 2 KG files (🟡).

The schema-docs checker and the layout/shape uniformity carry most of the load; the remaining gaps are real but bounded.

---

## Findings

### 🔴 1. Internal `qa` environment name leaks into ~40/44 shipped `app.py` files
- **Category:** OSS-readiness / internal leakage
- **Location:** `models/esm2/app.py:484` (`# Force deploy to "qa" or "main" environment:`) and the equivalent line in the `if __name__ == "__main__":` docstring of ~40 models — e.g. `models/abodybuilder3/app.py:287`, `models/ablang2/app.py:355`, `models/antifold/app.py:454`, `models/biotite/app.py:404`, `models/clean/app.py:428` (`# Force deploy to QA or main:`), `models/boltz/app.py:1044` (`# Force deploy in QA/prod:`), etc.
- **Detail:** Every model's runnable `__main__` block documents force-deploy with a reference to the internal `qa` Modal environment. The rubric explicitly lists "internal `qa` env" among the red-severity internal-reference leaks that must not ship. The referenced env isn't even used by the command shown (`MODEL_SIZE=... python models/X/app.py --force-deploy`); it's pure leftover internal phrasing. Because it's hardcoded per file, it must be scrubbed everywhere, and the model scaffold/template that produced it must be fixed so new models don't reintroduce it.
- **Fix:** Replace the comment with provider-neutral wording (e.g. `# Force a (re)deploy:`) across all model `app.py` files, and update whatever skill/scaffold generates the `__main__` block. Add a CI grep guard (`rg -i '\bqa\b.*(env|deploy)'` over `models/`) to keep it gone.

### 🟠 2. Error taxonomy is only half-adopted; system faults use bare builtins inconsistently
- **Category:** Conformance (errors) / consistency / Definition-of-Done (W7)
- **Location:** `models/commons/core/error.py` (defines `ServerError`/`ModelExecutionError`, used by 0 models); bare system-fault raises in `models/clean/app.py:178,209,219`, `models/esmstabp/app.py:114,141,170,175`, `models/temberture/app.py:155,165,168`, `models/tempro/app.py:84,182,194`, `models/immunebuilder/app.py:85,172,199`, `models/dsm/app.py:234,251`, `models/deepviscosity/app.py:214`, `models/prostt5/app.py:175,218`, `models/abodybuilder3/app.py:171`, `models/dnabert2/app.py:234`, `models/boltzgen/app.py:224`. Decorator fall-through: `models/commons/core/decorator.py:455-460`.
- **Detail:** W7 ratified a two-branch taxonomy (`UserError` family + `ServerError`/`ModelExecutionError`). In practice `UserError` is used by only ~8 models (boltz, boltzgen, chai1, pro1, rf3, rfd3, thermompnn, thermompnn_d) and **`ServerError`/`ModelExecutionError` are used by none**. The ~11 models above raise bare `ValueError`/`RuntimeError` for genuine *system* faults (weights missing, adapter dir absent, upstream ESM2 endpoint unreachable, internal config invariant). These fall through `ERROR_MAP` to the generic branch: `detail="Uncaught exception: {exc}"`, `status_code=500`, **`code=None`** (and `traceback` appended when debug is enabled, `decorator.py:507-509`). So a fault that *should* be a clean `system.model_execution` 500 instead surfaces as an uncoded "Uncaught exception" with the raw internal message echoed in `detail`. The user-input side is fine (Pydantic validators raise `ValueError`→422 correctly; that's the house pattern), but the system side of the taxonomy is effectively dead and the contract differs model-to-model.
- **Fix:** Route deliberate internal faults through `ServerError`/`ModelExecutionError` so they carry the stable `system.*` code and a sanitized detail; reserve true fall-through for genuinely unexpected exceptions. At minimum, wrap the upstream-call failures (esmstabp/tempro calling ESM2) and weights-missing paths.

### 🟠 3. `dna_chisel` wires `encode` but is a property-prediction model (classes named `*Predict*`)
- **Category:** Conformance (actions — verb matches intent) / consistency
- **Location:** `models/dna_chisel/config.py:43` (`name=ModelActions.ENCODE`) with `request_schema=DnaChiselPredictRequest` / `response_schema=DnaChiselPredictResponse`; response fields at `models/dna_chisel/schema.py:130-211` (`gc_content`, `cai`, `melting_temperature`, `codon_usage_entropy`, `tata_box_count`, …).
- **Detail:** The action is `ENCODE` (which the house pattern reserves for embeddings/representations), but the response returns **scalar sequence properties**, and *every* schema class is named `DnaChisel*Predict*` (`DnaChiselPredictRequest`, `DnaChiselPredictRequestItem`, `DnaChiselPredictResponseResult`, …). This is an internally self-contradicting model: the class names and the payload say "predict," the public action says "encode." It also misleads API callers, who will reach a property calculator under `/encode`. Borderline-🔴 since it's a public action verb, but functionally it works, so 🟠.
- **Fix:** Change the action to `ModelActions.PREDICT` (matches both the class names and the property-prediction intent). No schema renames needed.

### 🟠 4. Non-ML "utility/analysis" models stretch the closed verb set inconsistently
- **Category:** Conformance (actions) / consistency
- **Location:** `models/biotite/config.py:49-56` (`GENERATE`→`ExtractChains`, `PREDICT`→`RMSD`); `models/prody/config.py:45-52` (`ENCODE`→interaction analysis, `PREDICT`→`RMSD`); `models/dna_chisel` (see #3). Prody encode result with no embeddings: `models/prody/schema.py:578-613`.
- **Detail:** The six-verb set fits ML inference but not library-style structural utilities, and the three utility models resolve the impedance mismatch differently. `biotite` uses `generate` for chain extraction (a transform, not generation). `prody` uses `encode` for inter-chain interaction analysis (hydrogen bonds / salt bridges / interaction matrices — **no embeddings at all**, breaking the meaning of `encode`). Both `biotite` and `prody` compute pairwise RMSD and at least agree on `predict` for that, but the surrounding verbs diverge. The net effect is exactly the failure the north-star warns against: for these models the plumbing (which verb) differs, not just the science.
- **Fix:** Standardize utility-op verbs: structural/sequence *analysis that returns measurements* → `predict`; reserve `encode` for embeddings and `generate` for sequence/structure generation. Re-map `prody` interaction analysis and `biotite` chain extraction to `predict`. If the closed set truly can't express these, ratify a documented convention (these models already carry a `UTILITY`-style task tag).

### 🟠 5. `biotite` uses `pdb_string` where the house field name is `pdb`
- **Category:** Conformance (schema field names) / consistency
- **Location:** `models/biotite/schema.py:34` (`pdb_string: Annotated[str, ...]`).
- **Detail:** Nine structure models take a single structure as `pdb` (`antifold`, `abodybuilder3`, `esmfold`, `esm_if1`, `mpnn`, `spurs`, `immunebuilder`, `immunefold`, `thermompnn`/`thermompnn_d`). `biotite`'s `ExtractChains` input gratuitously calls it `pdb_string`. (The two-structure `pdb_a`/`pdb_b` in `biotite` RMSD and `prody` RMSD is a legitimate, *shared* deviation for pairwise input and should stay.) The rubric mandates `pdb`/`cif` for structure inputs.
- **Fix:** Rename `pdb_string` → `pdb` (add a Pydantic `alias="pdb_string"` if any caller already depends on the old name).

### 🟠 6. `ablang2` carries dead request classes and inconsistent alias/underscore naming
- **Category:** Software quality (dead code) / consistency
- **Location:** `models/ablang2/schema.py:81` (`AbLang2SeqcodingRequest`), `:114` (`AbLang2RescodingRequest`) — both defined, never referenced anywhere in the repo. Alias block `:192,265,340,361` (`AbLang2PredictRequest = _AbLang2LikelihoodRequest`, `AbLang2GenerateRequest = _AbLang2RestoreRequest`, …). Underscored privates `:177,250,334,355`.
- **Detail:** `ablang2` is the least "diff-is-only-science" model. Its native concepts (Seqcoding / Rescoding / Likelihood / Restore) are aliased onto canonical action names, but inconsistently: `_AbLang2LikelihoodRequest`/`_AbLang2RestoreRequest` are underscore-private while the equivalent `AbLang2SeqcodingRequest`/`AbLang2RescodingRequest` are public — *and the latter two are dead code* (encode is wired to `AbLang2EncodeRequest`). The action↔intent mapping is also a stretch (`predict`=per-residue likelihood matrix, `generate`=masked-residue restoration). A reader cannot tell from the class names which action a schema serves.
- **Fix:** Delete the two unused `*coding*Request` classes; pick one naming scheme (either canonical `AbLang2<Action>Request/Response` throughout, or native names with a single consistent alias layer) so the action→schema mapping is obvious.

### 🟠 7. Boltz family: same concept named `molecules` vs `entities` with different nesting
- **Category:** Consistency (sibling models)
- **Location:** `models/boltz/schema.py:465` (`molecules: list[BoltzEntity]`, nested inside a per-item input object) vs `models/boltzgen/schema.py:743` (`entities: list[BoltzGenEntity]`, directly under `items`).
- **Detail:** Two sibling models from the same Boltz lineage model the identical concept — "the list of molecular entities to fold/design" — with different field names *and* different nesting depth. For users working across both, the diff is plumbing, not science.
- **Fix:** Align the Boltz family on one field name (`entities` is the more accurate term) and one nesting shape.

### 🟡 8. `dummy` (a canonical reference shape) uses a bespoke `*Svc*` shape no real model follows
- **Category:** Consistency / docs (reference model)
- **Location:** `models/dummy/schema.py` — `DummySvcRequest`, `DummySvcResponse`, `DummySvcResponseResult`, fields `dummy_model_input_field`, `dummy_svc_resp_field`.
- **Detail:** The rubric names `dummy` as one of the two canonical shapes, yet its naming follows none of the house conventions real models use: `*SvcRequest/Response` ("Svc" appears in no other model), and placeholder field names instead of the `<Model><Action>Request`/`sequence`/typed-`items` pattern. As the example new contributors copy, it should model the real pattern. Low stakes (it's a scaffold) → 🟡.
- **Fix:** Rename to `Dummy<Action>Request`/`Response` and use a representative input field (e.g. `sequence`/`text`) so the scaffold mirrors the house pattern, or clearly document that `dummy` is intentionally abstract and point new contributors at `esm2` instead.

### 🟡 9. `dummy` is missing 2 of the 5 knowledge-graph files (+ `LICENSE`)
- **Category:** Conformance (layout) / consistency
- **Location:** `models/dummy/` — no `comparison.yaml`, no `LICENSE` (has `sources.yaml`, `README.md`, `MODEL.md`, `BIOLOGY.md`).
- **Detail:** Every real model ships all five KG files; `dummy` ships four and omits `comparison.yaml` (and the per-model `LICENSE`). If `dummy` ships publicly as the scaffold, the "all 5 present" invariant should either hold for it too or it should be explicitly excluded from the rule so the gap reads as intentional rather than an oversight.
- **Fix:** Either add a minimal `comparison.yaml`/`LICENSE` to `dummy`, or add it to an explicit exclusion list in the layout check and note "scaffold model" in its README.

### 🟡 10. Antibody chain-selector naming drift: `antifold.nanobody_chain_id`
- **Category:** Consistency (antibody convention)
- **Location:** `models/antifold/schema.py:158-161` (`nanobody_chain_id`, mutually exclusive with `heavy_chain_id`).
- **Detail:** The house convention is nanobody = lone `heavy_chain` + single-domain tag (no nanobody-specific field). `antifold` is a structure model that points at a *PDB chain*, so a `nanobody_chain_id` selector is defensible — but it's the only place a "nanobody"-named field appears, so flagging for consistency. Borderline; defensible as a chain pointer (not a sequence field).
- **Fix:** Consider documenting the chain-selector exception in `CONTRIBUTING.md`'s schema conventions, or fold nanobody handling into `heavy_chain_id` + the single-domain tag to keep the field set uniform.

---

## Definition-of-Done notes (this dimension)
- **W7 (canonical actions + error taxonomy):** Actions DoD = **met** (closed verb set everywhere, modulo the verb-*intent* gaps in #3/#4). Error-taxonomy DoD = **partially met** — `UserError` adopted where input is rejected, but the `ServerError`/`ModelExecutionError` branch is unused by all 44 models (#2).
- **W6 (logging, no print):** **met** in runtime code (`get_logger` everywhere; `print` only in offline `_train.py` and vendored `external/`).
- **Schema-field uniformity (W3a/field glossary):** **met and CI-enforced** (`check_schema_docs.py` green for 44), aside from the field-name drifts in #5/#7.
- **Public-CLAUDE / no internal leakage (W14):** **not met** — the `qa` env reference (#1) ships in ~40 files.

---

## Verification

Adversarial re-check of every finding against current code (each cited path/line opened).

- **#1 `qa` env leak — REAL.** Confirmed in 42/44 `app.py` `__main__` docstrings; exact cited lines match (`esm2/app.py:484`, `abodybuilder3/app.py:287`, `ablang2/app.py:355`, `antifold/app.py:454`, `biotite/app.py:404`, `clean/app.py:428`, `boltz/app.py:1044`, plus the QA/prod variants in evo/evo2/esmc/dnabert2/e1/omni_dna/spurs/tempro/deepviscosity/peptides). Pure leftover internal phrasing, not used by the shown command.
- **#2 Error taxonomy half-adopted — REAL (one sub-claim overstated).** Bare-builtin system faults confirmed at all cited lines (e.g. `esmstabp/app.py:170` "ESM2 endpoint call failed", `temberture/app.py:165` "Adapter directory not found", `esmstabp/app.py:114` weights-missing), and `decorator.py:454-460` confirms fall-through → `detail="Uncaught exception: {exc}"`, `status_code=500`, `code=None`. BUT the claim "`ServerError`/`ModelExecutionError` are used by none" is false: `biotite/app.py:15,257,384` imports and raises `ModelExecutionError`. Substance (inconsistent error contract, dead system branch in ~11 models) holds; the "zero models" count is off by one (biotite).
- **#3 `dna_chisel` encode-vs-predict — REAL.** `config.py:43` wires `ModelActions.ENCODE` to `DnaChiselPredictRequest/Response`; all schema classes named `DnaChisel*Predict*` (`schema.py:112,130,213`); response returns scalar properties (`gc_content`, `cai`, `melting_temperature` at `schema.py:130+`). The config comment "action name is encode, not predict" confirms the self-contradiction.
- **#4 Utility models stretch verb set — REAL.** `biotite/config.py:49-56` (`GENERATE`→ExtractChains, `PREDICT`→RMSD); `prody/config.py:43-52` (`ENCODE`→InSty interaction analysis, `PREDICT`→RMSD); `prody/schema.py:578-613` `ProDyEncodeResponseResult` returns interaction/energy matrices and H-bond summaries — no embeddings. Verb-vs-intent divergence is demonstrable (normative severity is a judgment, factual basis solid).
- **#5 `biotite.pdb_string` — REAL.** `biotite/schema.py:34` `pdb_string: Annotated[str,...]`; canonical single-structure field is `pdb` (`abodybuilder3/schema.py:122`, `esmfold/schema.py:63`, `antifold/schema.py:221,323`).
- **#6 `ablang2` dead classes — REAL.** `schema.py:81 AbLang2SeqcodingRequest` and `:114 AbLang2RescodingRequest` are defined and referenced nowhere (repo-wide grep finds only their definitions); encode is wired to `AbLang2EncodeRequest` (`config.py:58`). Alias layer `schema.py:192,265,340,361` confirms the inconsistent public/underscore-private naming.
- **#7 boltz `molecules` vs boltzgen `entities` — REAL.** `boltz/schema.py:465` `molecules: list[BoltzEntity]` vs `boltzgen/schema.py:743` `entities: list[BoltzGenEntity]` for the molecular-entity list. Different field name + type for the sibling concept (fold-vs-design schemas differ, but the list-name divergence is real); naming severity is a consistency judgment.
- **#8 `dummy` `*Svc*` shape — REAL.** `dummy/schema.py:30,43,56` `DummySvcRequest/ResponseResult/Response`; "Svc" appears in no other model (repo-wide grep). Placeholder fields `dummy_model_input_field:25`, `dummy_svc_resp_field:48`. (🟡 — scaffold.)
- **#9 `dummy` missing KG files — REAL.** `dummy/` has no `comparison.yaml` and no `LICENSE`; it is the only real model package missing either (commons/`__pycache__` aside). (🟡.)
- **#10 `antifold.nanobody_chain_id` — REAL (borderline, as flagged).** `antifold/schema.py:158` is the only nanobody-named field in any schema (no `vhh` anywhere). Factual drift confirmed; the finding itself concedes it's defensible as a PDB-chain pointer rather than a sequence field.

**Net:** 10/10 findings hold on their factual basis. Only correction: #2's "used by none" is wrong — `biotite` uses `ModelExecutionError` — but #2's substantive inconsistency claim still stands.
