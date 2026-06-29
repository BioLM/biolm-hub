# Review — `models/mpnn/` (Round 1)

**Reviewer:** independent launch-gating review
**Target:** `models/mpnn/` (ProteinMPNN / LigandMPNN family — inverse folding, `generate` action)
**Verdict:** Close to ready. The plumbing largely matches the house pattern (commons decorators,
`ModelFamily`, `r2_then_urls` acquisition, structured logging, no `print`, glossary-pinned `seed`/
`temperature` descriptions match verbatim). One launch-gating licensing-accuracy defect (verified
against upstream), plus a cluster of should-fix items: a docs/code resource contradiction, response
DTOs built on the wrong base class, dead variant-request scaffolding, internal plumbing params leaking
into the public schema, and a residue-position validation bug that rejects legitimate non-1-indexed PDBs.

---

## Summary

`app.py`, `config.py`, `download.py`, and the knowledge-graph files are solid and conventional.
Findings concentrate in `schema.py` (dead code, internal-param leakage, a validation bug, wrong response
base class), the `LICENSE` (wrong copyright year + an unresolved "confirm before release" note), and the
docs (a 128 MB / 0.125-core claim that contradicts the 3 GB / 1 CPU spec in `config.py`). The `pending`
R2-asset placeholders in `sources.yaml` are house-wide (esm2 has the same count) and are **not** flagged.

---

## 🔴 Must-fix before launch

### 1. `LICENSE` ships an inaccurate copyright year and an unresolved pre-release note
- **Category:** Licensing
- **Location:** `models/mpnn/LICENSE:3`, `models/mpnn/LICENSE:29-30`
- **Detail:** The file states `Copyright (c) 2023 Justas Dauparas` and ends with a parenthetical
  "(The copyright holder/year above are inferred from the upstream repository; confirm the exact line
  against the LigandMPNN LICENSE before public release.)". I verified the upstream file
  (`raw.githubusercontent.com/dauparas/LigandMPNN/main/LICENSE`): it reads
  **`Copyright (c) 2024 Justas Dauparas`**. So (a) the year is wrong (2023 vs 2024), meaning we are not
  reproducing the actual MIT copyright notice we are obligated to preserve, and (b) the file carries an
  explicit launch-gate TODO in shipped legal text. The reference model `models/esm2/LICENSE` has no such
  self-note. The file itself says this must be resolved before the repo is public.
- **Fix:** Change the year to `2024`, delete the two-line parenthetical note (lines 28-30), keeping the
  clean attribution paragraph that mirrors esm2's LICENSE.

---

## 🟠 Should-fix

### 2. Docs claim 128 MB / 0.125 cores; `config.py` specs 3 GB / 1 CPU
- **Category:** Documentation / correctness (doc–code mismatch)
- **Location:** `models/mpnn/config.py:33-37` vs `models/mpnn/README.md:39,262-270`,
  `models/mpnn/MODEL.md:155-163`, `models/mpnn/comparison.yaml:13`
- **Detail:** `MPNNResourceSpec = ModalResourceSpec(cpu=1.0, memory=3072, gpu=None)` (3 GB RAM, 1 CPU).
  But README "Resource Requirements" and the "Model Variants" line both say "128 MB memory" /
  "0.125 cores"; MODEL.md "Memory & Compute Profile" repeats 128 MB / 0.125 cores; and comparison.yaml
  asserts as a *strength* "...with 128 MB memory footprint makes it the cheapest and fastest model to
  run on the platform." The 128 MB figure is ~24x off and the "cheapest" claim is materially false.
- **Fix:** Update all three docs to 1 CPU / 3 GB (or, if 3 GB is over-provisioned, reduce the spec and
  reconcile). Treat `config.py` as the source of truth.

### 3. Response DTOs inherit `RequestModel` instead of `ResponseModel`
- **Category:** Convention / robustness
- **Location:** `models/mpnn/schema.py:626` (`class MPNNGenerateResponseItem(RequestModel)`),
  `models/mpnn/schema.py:665` (`MPNNSCGenerateResponseItem` inherits the same)
- **Detail:** The house pattern bases response payloads on `ResponseModel` (`models/esm2/schema.py:143,
  191,209`; `models/dummy/schema.py:43,56`). Per `models/commons/model/pydantic.py:30-41`, `RequestModel`
  is `extra="forbid"` while `ResponseModel` is `extra="ignore"`. These items are populated from the
  `infer()` dict via `model_validate(i)` in `app.py:281,285`. It works **today** only because
  `util.infer` returns exactly the declared keys; the moment upstream `util.py` adds an output key, a
  `forbid` response item raises at serialization instead of silently dropping it. It is also an
  inconsistency a contributor will trip over.
- **Fix:** Base `MPNNGenerateResponseItem` (and thus `MPNNSCGenerateResponseItem`) on `ResponseModel`.

### 4. Dead variant-request scaffolding in `schema.py`
- **Category:** Simplicity / dead code
- **Location:** `models/mpnn/schema.py:553-618`
- **Detail:** `LigandMPNNGenerateRequest`, `GlobalMembraneMPNNGenerateRequest`, and
  `ResidueMembraneMPNNGenerateRequest` (including the latter's `validate_membrane_params` model-validator)
  are defined but never imported or referenced anywhere — `config.py` and `app.py` use only
  `MPNNGenerateRequest`/`MPNNGenerateResponse` (grep across the repo finds no other usage). The
  per-variant strictness is instead implemented at runtime in `app.py:218-237` via `mpnn_schema_map`.
  ~65 lines of unreachable code that will confuse readers about which request type is live.
- **Fix:** Delete the three unused `*GenerateRequest` classes.

### 5. Internal/plumbing params leak into the public request schema
- **Category:** Schema cleanliness / public contract
- **Location:** `models/mpnn/schema.py:209-255` (within `MPNNGenerateParams`, inherited by the request
  schema `AllMPNNGenerateParams`)
- **Detail:** Fields documented as "Internal use only; always null in API requests"
  (`pdb_path`, `redesigned_residues_multi`, `fixed_residues_multi`, `bias_AA_per_residue_multi`,
  `omit_AA_per_residue_multi`, `save_stats`, `ligand_mpnn_use_side_chain_context`) plus argparser-default
  plumbing (`fasta_seq_separation`, `file_ending`, `zero_indexed`, `verbose`) all render in the public
  `model_json_schema()` because `MPNNGenerateParams` is the base of the request `AllMPNNGenerateParams`.
  Several are actually user-settable (`verbose: bool=True`, `zero_indexed: int=0`,
  `fasta_seq_separation: str=":"`, `file_ending: str=""`) and flow straight into `SimpleNamespace` → `infer`
  (`app.py:240-270`), so a caller can toggle internal behavior. esm2/dummy keep request schemas minimal.
  The only reason these exist on the model is that `app.py:240` builds the full arg namespace from
  `AllMPNNGenerateParams().model_dump()` — but those defaults can be injected server-side instead of
  being public fields.
- **Fix:** Remove the internal/plumbing fields from the user-facing params model and set them server-side
  in `app.py` when assembling the `SimpleNamespace` (e.g. `params.setdefault(...)`), so the public schema
  only advertises real user controls.

### 6. Residue-position validation rejects valid non-1-indexed PDBs (and accepts invalid ones)
- **Category:** Correctness
- **Location:** `models/mpnn/schema.py:347-373` (`parse_pdb_string`), `schema.py:412-416`
  (`validate_residue_lists`), and the inline checks at `schema.py:499,516,534`
- **Detail:** `parse_pdb_string` returns *counts* of unique residues per chain, and validation then checks
  `1 <= residue_number <= chain_counts[chain_id]`. PDB author residue numbering is not guaranteed to start
  at 1 or be contiguous. For a chain numbered 100-150 (51 residues), a legitimate spec like `A120` is
  rejected (`120 > 51`), while a non-existent `A30` is accepted (`30 <= 51`). LigandMPNN residue specs use
  author numbering, so this is wrong for real RCSB structures. (The common MPNN-on-RFdiffusion-output case
  is 1-indexed, which is why it has not surfaced.)
- **Fix:** Have `parse_pdb_string` return the actual *set* of `(res_num, insertion_code)` per chain, and
  validate membership against that set instead of a `1..count` range.

---

## 🟡 Nits / minor

### 7. Deployment/integration tests cover only 2 of 6 deployed variants, with a presence-only validator
- **Category:** Tests
- **Location:** `models/mpnn/test.py:18-43,9-12`
- **Detail:** Only `protein` and `ligand` are exercised (the timeout rationale at `test.py:15-17` is
  reasonable), leaving `soluble`, `global_label_membrane`, `per_residue_label_membrane`, and `hyper`
  with no integration/deployment coverage. The validator `_validate_mpnn_generate` only asserts that
  `results` exists and is non-empty — no field-presence, type, or value-range checks (contrast esm2's
  tolerance-based output comparison). The membrane/hyper code paths are the ones most likely to regress.
- **Fix:** Add a lightweight structural validator (assert each result has `sequence`/`pdb`/
  `overall_confidence` and that confidences are in [0,1]) and include at least one membrane variant in
  the suite.

### 8. Foundational ProteinMPNN paper has no R2 assets in `sources.yaml`
- **Category:** Knowledge graph completeness
- **Location:** `models/mpnn/sources.yaml:30-31`
- **Detail:** The primary ProteinMPNN (Science 2022) entry has `pdf_r2: pending` / `md_r2: pending`,
  while the secondary LigandMPNN 2024 primary is fully populated (lines 41-42), and esm2's primary papers
  are both populated. (`pending` on *applied_literature* is house-wide and not flagged.) The most-cited
  paper for this model lacking its primary R2 assets is a small completeness gap.
- **Fix:** Populate the ProteinMPNN paper's `pdf_r2`/`md_r2` (or confirm it is intentionally deferred).

---

## Cross-checks that passed (no action needed)
- Glossary verbatim fields match: `seed` ("Random seed for reproducible sampling.") and `temperature`
  ("Sampling temperature; higher values increase diversity.") exactly match
  `tooling/field_glossary.yaml`.
- `overall_confidence`/`ligand_confidence` descriptions ("exp of negative cross-entropy loss") match
  `util.py:589-593` (`np.exp(-loss)`); `FloatLike` correctly coerces the formatted-string outputs that
  `util.py` returns into floats under the strict models.
- Acquisition is canonical (`r2_then_urls` in `download.py`), self-populates one shared R2 prefix for all
  variants, and `verify_ssl=False` is documented (IPD TLS chain); no `huggingface_hub` build-time import,
  so no `extra_pip_packages` needed in `setup_download_layer`.
- Action verb is correct (`generate` for inverse folding; `task=[INVERSE_FOLDING]`), `modal_class_name`
  matches the class, slug/`display_name` are consistent across `config.py`/`sources.yaml`/
  `comparison.yaml` ("mpnn"/"MPNN").
- No `print` in runtime code; structured `get_logger` used throughout; no `biolm-modal`/`qa`/`.planning`
  leakage in any shipped file.
- `comparison.yaml`'s `biolmtox2` reference points to a model not in `models/`, but esm2 and 3 other
  models reference the same slug — this is a catalog-wide convention question, not an mpnn defect.

## Verification

Adversarial re-check of 6 high-severity findings (verifier could not refute any; all confirmed against code/upstream):

1. **LICENSE wrong year + unresolved pre-release note** — **real**. `models/mpnn/LICENSE:3` reads "Copyright (c) 2023 Justas Dauparas"; upstream `raw.githubusercontent.com/dauparas/LigandMPNN/main/LICENSE` reads "Copyright (c) 2024 Justas Dauparas" (fetched). The launch-gate note ships in shipped legal text at `LICENSE:29-30`.
2. **Docs 128 MB / 0.125 cores vs config 3 GB / 1 CPU** — **real**. `config.py:33-37` is the only resource spec: `cpu=1.0, memory=3072`. `README.md:39,266`, `MODEL.md:159`, `comparison.yaml:13` all assert 128 MB / 0.125 cores; the 128 MB figure is ~24x below the deployed 3072 MB.
3. **Response DTOs inherit RequestModel not ResponseModel** — **real**. `schema.py:626` `MPNNGenerateResponseItem(RequestModel)` and `:665` `MPNNSCGenerateResponseItem(MPNNGenerateResponseItem)`; `commons/model/pydantic.py:30,33` RequestModel is `extra="forbid"`. esm2 (`schema.py:143,191,209`) and dummy (`schema.py:43,56`) responses use ResponseModel (`extra="ignore"`). Items built via `model_validate(i)` at `app.py:281,285` — a future extra infer() key would raise.
4. **Dead variant-request classes** — **real**. Repo-wide grep: `LigandMPNNGenerateRequest`/`GlobalMembraneMPNNGenerateRequest`/`ResidueMembraneMPNNGenerateRequest` (`schema.py:553,567,581`) and `validate_membrane_params` (`:595`) appear only at their definitions; never imported/used. config/app wire `MPNNGenerateRequest` + runtime `mpnn_schema_map` (the *Params* classes, which ARE used). ~66 dead lines (553-618).
5. **Internal/plumbing params leak into public schema** — **real**. `schema.py:209-255` fields live on `MPNNGenerateParams`, base of request type `AllMPNNGenerateParams` (`:299,420`); none use `exclude=`, so all render in `model_json_schema()`. `verbose`(bool,True), `zero_indexed`(int,0), `fasta_seq_separation`(str,':'), `file_ending`(str,'') are user-settable and flow `model_dump(exclude_unset/none)` -> filter -> `AllMPNNGenerateParams().model_dump()` -> `SimpleNamespace` -> `infer` (`app.py:225-270`).
6. **Residue-position validation off by author-numbering** — **real**. `parse_pdb_string` (`schema.py:347-373`) returns only per-chain unique-residue *counts*, never actual author numbers. Validation compares `1 <= residue_number <= chain_counts[...]` (`:412,499,516,534`). For a chain numbered 100-150 (count 51), "A120" is wrongly rejected and "A30" wrongly accepted; LigandMPNN residue specs use PDB author numbering, so this misvalidates real RCSB structures (1-indexed RFdiffusion outputs hide it).
