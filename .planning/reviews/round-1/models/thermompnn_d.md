# Review — `models/thermompnn_d/` (ThermoMPNN-D)

**Reviewer:** independent round-1 launch-gating review
**Target:** `models/thermompnn_d/`
**Reference baselines:** `models/esm2/` (house pattern), `models/dummy/` (template), `models/thermompnn/` (closest sibling — single-mutation predecessor)

## Summary

ThermoMPNN-D is a structure-based GNN that predicts single- and double-mutation stability change
(ddG), with an epistatic interaction mode. The port is clean and follows the house plumbing closely —
it is essentially a two-checkpoint extension of the sibling `thermompnn` model and inherits that
model's app/config/download/schema shape almost verbatim. Actions are correct (`predict` only),
schema field descriptions all render, the acquisition path (`r2_then_urls`) self-populates the public
bucket and the upstream URLs were verified to exist, and the 5-file knowledge graph is present and
mostly internally consistent (slug/display_name match config).

The one genuine launch-blocker is a **licensing compliance bug**: the vendored `LICENSE` rewrites the
upstream MIT copyright holder ("Henry Dieckhaus" → "Kuhlman Lab"), which violates MIT's requirement to
preserve the original notice. Beyond that there are a handful of should-fix items: runtime user-input
errors that surface as HTTP 500, an expensive "compute the whole landscape then filter" path for
requested double mutations, and the usual knowledge-graph completeness residue (`pending` / `TODO`)
that is shared with the sibling model. Nothing else is structurally wrong.

Several findings are **systemic** (also present in `thermompnn` and/or the `esm2` reference). They are
reported here because the rubric asks for them, but they should be resolved repo-wide rather than only
in this model.

---

## 🔴 Must-fix

### 1. LICENSE misattributes the upstream copyright holder
- **Category:** Licensing / OSS compliance
- **Location:** `models/thermompnn_d/LICENSE:3`
- **Detail:** The vendored file reads `Copyright (c) 2024 Kuhlman Lab`. The actual upstream
  `Kuhlman-Lab/ThermoMPNN-D/main/LICENSE` (verified) reads **`Copyright (c) 2024 Henry Dieckhaus`**.
  MIT's central condition is that "the above copyright notice ... shall be included in all copies" —
  i.e. the *original* notice. Replacing the holder fails that obligation, and the rubric explicitly
  flags an inferred/changed holder as a launch blocker. (`sources.yaml` correctly says `type: MIT`, so
  only the holder line is wrong.) The sibling `models/thermompnn/LICENSE` shows the same anti-pattern
  ("2023 Kuhlman Lab"), suggesting the vendoring step rewrote holders generically — worth auditing
  repo-wide.
- **Fix:** Copy the upstream `LICENSE` verbatim: `Copyright (c) 2024 Henry Dieckhaus`.

---

## 🟠 Should-fix

### 2. Runtime user-input errors surface as HTTP 500 instead of 400
- **Category:** Errors / contract
- **Location:** `models/thermompnn_d/app.py:228-256` (the `predict()` call is wrapped only by
  `try/finally`, not `try/except`); raises originate in `models/thermompnn_d/util.py:171,239,333`
  (`raise ValueError("No chains found in PDB file")`) and `util.py:478`.
- **Detail:** Mutation *format* errors are caught at request-validation time (schema `model_validator`
  → 422), but *semantic* runtime problems caused by the caller — e.g. a PDB that parses to zero chains,
  or a `chain` that is not present — raise a bare `ValueError` from `util.py`. App-level code does not
  convert these to `UserError`, so `modal_endpoint`'s `_handle_errors` fall-through
  (`decorator.py:454-462`) returns a 500 "Uncaught exception". Per rubric A5 these are caller mistakes
  and should be 4xx. (Shared with the sibling `thermompnn`.)
- **Fix:** Wrap the `predict()` call in `try/except (ValueError, ...) as e: raise UserError(...)`, or
  raise `UserError`/`ValidationError400` directly inside the `util.py` chain-resolution helpers.

### 3. Requested-mutation paths compute the full double-mutation landscape, then filter
- **Category:** Efficiency / simplicity (rubric B "10x")
- **Location:** `models/thermompnn_d/util.py:283-285` (additive) and `util.py:396-407` (epistatic).
- **Detail:** When the caller supplies a small list of specific double mutations, the additive path
  calls `format_output_double(..., threshold=1000.0, distance=1000.0)` and the epistatic path forces
  `effective_distance = max(max_distance_needed + 1.0, 100.0)` with `threshold=1000.0`, i.e. it
  evaluates essentially *every* residue pair (O(N²·400)) only to keep the handful the user asked for.
  For the epistatic model this runs the full pairwise GNN over ~all pairs within ≥100 Å — easily a
  timeout/OOM risk on moderate proteins when the user requested two mutations. The SSM-scan paths
  (mutations=None) are fine; only the targeted path is wasteful.
- **Fix:** For an explicit mutation list, evaluate only the requested pairs (build the pair set
  directly and score those), rather than scanning the whole landscape and filtering.

### 4. Knowledge-graph completeness: `pending` artifacts and `TODO` placeholders ship
- **Category:** Knowledge graph / docs (rubric A9)
- **Location:** `sources.yaml:40-41,49-50,58-59,72-73,88-89` (`pdf_r2: pending` / `md_r2: pending`
  on all five `applied_literature` entries); `README.md:162`, `MODEL.md:26`, `MODEL.md:47`,
  `BIOLOGY.md:48` (`<!-- TODO: ... requires PDF access -->`).
- **Detail:** The rubric explicitly names stray `pending`/`TODO` as residue that must not ship. The
  primary paper has real R2 paths, but every applied-literature entry is `pending`, and three doc
  files carry "extract benchmarks / training data — requires PDF access" TODOs (so README/MODEL ship
  empty "Published Results"/"Training Data" sections). Systemic — the sibling `thermompnn` has the
  identical residue.
- **Fix:** Populate the `pending` R2 fields (or drop the keys if those artifacts aren't being
  catalogued) and either fill or remove the benchmark/training TODO blocks before public launch.

### 5. `comparison.yaml` lists a model alternative that has no model in the repo
- **Category:** Knowledge graph consistency / dead link
- **Location:** `models/thermompnn_d/comparison.yaml:48-50` (`alternatives: - model: gemme`); also
  referenced in `dont_use_when:36`.
- **Detail:** There is no `models/gemme/` directory in the repo, so the structured `model: gemme`
  cross-reference is dangling. The catalog/`bm serve` linker and any cross-model consistency check will
  not resolve it. All other referenced slugs (`thermompnn`, `spurs`, `temberture`, `boltz`, `esm2`)
  do exist.
- **Fix:** Remove the `gemme` alternative (and the free-text mention), or gate such references to
  slugs that exist in the repo.

---

## 🟡 Nits

### 6. `util.py` bypasses the commons structured logger
- **Category:** Logging convention (W6)
- **Location:** `models/thermompnn_d/util.py:9,19,393`
- **Detail:** Uses stdlib `logging.getLogger(__name__)` and an f-string log
  (`logger.warning(f"Skipping invalid mutation '{mut_str}': {e}")`) instead of
  `models.commons.core.logging.get_logger` + lazy `%`-args used everywhere else (`app.py`,
  `download.py`, `fixture.py`). Minor, but it is the one file in the model that diverges from the
  structured-logging convention.
- **Fix:** `from models.commons.core.logging import get_logger; logger = get_logger(__name__)` and use
  `logger.warning("Skipping invalid mutation '%s': %s", mut_str, e)`.

### 7. Dead/redundant params re-validation in `predict()`
- **Category:** Simplicity / dead code
- **Location:** `models/thermompnn_d/app.py:205-211`
- **Detail:** `payload.params` is already a validated `ThermoMPNNDPredictParams` (the request schema
  declares it as such), so `ThermoMPNNDPredictParams.model_validate(payload.params.model_dump(...))`
  is a no-op clone and the `except ValidationError -> UserError` branch is unreachable. Copy-pasted
  from the sibling. Harmless but misleading.
- **Fix:** Use `params = payload.params` directly and delete the dead try/except.

### 8. Internal env name `qa` in shipped docstring
- **Category:** Internal leakage (systemic)
- **Location:** `models/thermompnn_d/app.py:268` (`# Force deploy to "qa" or "main" environment:`)
- **Detail:** The rubric lists the internal `qa` env as leakage. This exact line is present in the
  `esm2` reference (`app.py:484`) and the sibling — it is a repo-wide template line, not unique to this
  model, so fix it globally rather than only here.
- **Fix:** Generalize the docstring (drop the named environments) as part of a repo-wide sweep.

### 9. Weights self-populate from mutable `main`, not the pinned commit
- **Category:** Reproducibility
- **Location:** `models/thermompnn_d/download.py:17,39-41`
- **Detail:** Code clones the repo at a pinned commit (`config.py:22`), but the checkpoint URLs use
  `.../raw/main/...`. If upstream re-publishes the weights on `main`, the cached-to-R2 checkpoints
  could drift out of sync with the pinned code (until R2 is populated, after which R2 is
  authoritative). Shared with the sibling.
- **Fix:** Pin the weight URLs to the same commit:
  `.../raw/{thermompnn_d_commit_hash}/model_weights/...`.

### 10. `BIOLOGY.md` contradicts `sources.yaml` on applied literature
- **Category:** Knowledge graph consistency (systemic)
- **Location:** `models/thermompnn_d/BIOLOGY.md:46` ("No applied literature entries have been
  catalogued yet.") vs `sources.yaml:32-89` (five `applied_literature` entries).
- **Detail:** The two files disagree on whether applied literature exists. Defensible if "applied use
  cases" (papers *using* the model) is meant to differ from `applied_literature` (benchmark/method
  comparisons), but as written it reads as a contradiction. Same pattern in the sibling.
- **Fix:** Reword the BIOLOGY.md section to reflect the catalogued comparison/benchmark literature, or
  clarify the distinction.

### 11. Checkpoint-constant naming inconsistency
- **Category:** Naming
- **Location:** `models/thermompnn_d/config.py:34-35`
- **Detail:** `THERMOMPNN_D_EPISTATIC_CHECKPOINT` and `PROTEIN_MPNN_CHECKPOINT` carry the family
  prefix, but the single checkpoint is `THERMOMPNN_SINGLE_CHECKPOINT` (no `_D_`). Minor readability.
- **Fix:** Rename to `THERMOMPNN_D_SINGLE_CHECKPOINT` for consistency.

### 12. Duplicated synthetic PDB fixture
- **Category:** Test asset reuse (W12)
- **Location:** `models/thermompnn_d/fixture.py:28-100` (identical `_SAMPLE_PDB` to
  `models/thermompnn/fixture.py`).
- **Detail:** The same hand-built 10-residue PDB is hardcoded in both MPNN-family models. The shared
  asset library currently holds only sequences (`shared_assets.py`) but documents a `shared/pdb/`
  convention. This is a candidate for promotion so the two models don't drift independently. Low
  priority (no shared PDB asset exists yet).
- **Fix:** When a `shared/pdb/` asset is introduced, reference it from both fixtures.

### 13. Low-confidence: in-repo code does not enforce `no_grad` / position indexing claimed in docs
- **Category:** Doc-vs-code (low confidence — depends on upstream `v2_ssm`)
- **Location:** `models/thermompnn_d/util.py` (no explicit `with torch.no_grad()`, unlike sibling
  `thermompnn/util.py:226`); `MODEL.md:116`; `schema.py:169-177` ("1-indexed").
- **Detail:** All inference is delegated to upstream `v2_ssm` (`run_single_ssm`, `run_epistatic_ssm`,
  `format_output_*`), so the "Inference under torch.no_grad(): Yes" claim and the 1-indexed positions
  for SSM-scan results rely on `v2_ssm`'s behavior rather than being enforced/normalized in this repo.
  This is flagged only as something to confirm during live validation; the model is marked VERIFIED so
  the format very likely holds.
- **Fix:** Confirm during deployment validation; optionally normalize positions in `util.py` so the
  "1-indexed" guarantee is owned by this repo rather than upstream.

---

## Definition-of-Done notes
- **Layout / actions / schema / descriptions:** met — standard files present, single `predict` action,
  all fields carry rendering descriptions; no glossary `verbatim` fields apply (ddg/pdb/mutations are
  not pinned).
- **Acquisition:** met — `r2_then_urls` self-populates; upstream `model_weights/*.ckpt` and
  `vanilla_model_weights/` paths were verified to exist.
- **Licensing:** **not met** — wrong copyright holder (Finding 1).
- **Errors/logging:** partially met — `UserError` used at app level, but runtime user errors leak as
  500 (Finding 2) and `util.py` skips the structured logger (Finding 6).
- **Knowledge graph:** partially met — present and mostly consistent, but `pending`/`TODO` residue
  (Finding 4), a dangling `gemme` reference (Finding 5), and a BIOLOGY/sources inconsistency
  (Finding 10).

---

## Verification

Adversarial re-review of the five HIGH-severity findings (attempt to refute each against the actual code).

- **Finding 1 — LICENSE misattributes copyright holder: REAL.** `models/thermompnn_d/LICENSE:3` reads `Copyright (c) 2024 Kuhlman Lab`; upstream `Kuhlman-Lab/ThermoMPNN-D/main/LICENSE` reads `Copyright (c) 2024 Henry Dieckhaus` (confirmed via fetch). License TYPE (MIT) and `sources.yaml:3-5` URL are correct — only the holder line is wrong. Sibling `models/thermompnn/LICENSE:3` shows the same generic rewrite (`2023 Kuhlman Lab`), confirming the systemic anti-pattern.
- **Finding 2 — caller mistakes surface as HTTP 500: REAL.** `app.py:228-260` wraps the `predict()` util call (line 238) in `try/finally` only (no `except`/`UserError`); bare `ValueError`s from `util.py:171,239,333` ("No chains found in PDB file") are not in `ERROR_MAP` (`decorator.py:420-430`), so they hit the fall-through "Uncaught exception" 500 (`decorator.py:454-462`). `validate_pdb` (structure_validator.py:163-181) never checks chains, so a `chain` not present / parse-to-zero-chains is a caller mistake that 500s. Caveat: cited `util.py:478` (invalid mode) is NOT user-reachable because `mode` is enum-validated (`schema.py:26-29,38-41`); the finding's thesis holds via the chain paths regardless.
- **Finding 3 — targeted double-mutations compute full landscape then filter: REAL.** Additive targeted path `util.py:283-285` calls `format_output_double(..., threshold=1000.0, distance=1000.0)` (all pairs, no distance filter); epistatic targeted path `util.py:397-407` forces `effective_distance = max(max_distance_needed+1.0, 100.0)` with threshold `1000.0` then calls `run_epistatic_ssm`, which evaluates the GNN on essentially all pairs within >=100A — genuine O(N^2) model-eval timeout/OOM risk when the caller asked for a handful. SSM-scan (mutations=None) paths are unaffected. Lines match exactly.
- **Finding 4 — `pending` R2 + `TODO` placeholders ship: REAL.** All five `applied_literature` entries carry `pdf_r2: pending` / `md_r2: pending` (`sources.yaml:40-41,49-50,58-59,72-73,88-89`); TODO comments confirmed at `README.md:162`, `MODEL.md:26`, `MODEL.md:47`, `BIOLOGY.md:48` (grep), leaving Published-Results/Training-Data sections empty. Systemic with sibling `thermompnn`.
- **Finding 5 — `gemme` cross-reference is dangling: REAL.** `comparison.yaml:48-50` declares `- model: gemme` (and prose ref at line 36); `ls models/` shows no `models/gemme/` directory. All other referenced slugs exist (`thermompnn`, `spurs`, `temberture`, `boltz`, `esm2`), so the structured `model: gemme` link cannot be resolved by the catalog/`bm serve` linker.
