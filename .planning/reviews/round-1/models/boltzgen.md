# Review — `models/boltzgen/`

**Reviewer:** independent round-1 (rubric A–D)
**Verdict:** Solid, careful engineering with an unusually broad/complex design-spec schema that is well-described
and well-tested at the unit level. The plumbing is mostly house-conformant. No correctness/security bug in the
runtime hot path, but several **should-fix** documentation-vs-schema mismatches, a left-on `debug=True` info-leak,
and knowledge-graph/provenance residue (`pending`, a `<!-- TODO -->`, an unverified LICENSE note, mismatched
upstream commits) that should be cleaned before launch.

Cross-checks performed: every field description renders in `model_json_schema()` (verified by loading both
request and response models — none missing). Action verb (`generate`) matches intent. Slug/display_name are
consistent across config / sources.yaml / comparison.yaml (`boltzgen` / `BoltzGen`). Download self-populates R2
on HF fallback. No `biolm-modal` / `.planning` / `qa` / internal-domain leakage in shipped files.

---

## 🔴 must-fix
_None._ (No correctness/security/secret/license-blocking defect found in runtime code. The licensing item below
is borderline and is filed as 🟠.)

---

## 🟠 should-fix

### 1. README parameter table & examples contradict the schema (and the README itself)
- **Category:** Docs / Correctness
- **Location:** `README.md:170-171`, `README.md:288` (vs `README.md:37`, `schema.py:600-625`)
- **Detail:** The "Request Parameters" table documents `num_designs` **default 10000, range 1-100000** and
  `budget` **default 100, range 1-10000**. The schema enforces `num_designs` **default 100, ge=1, le=500** and
  `budget` **default 100, ge=1, le=500**. README §"Key Parameters" line 37 even states "both are capped at 500
  per request" — so the README contradicts itself. Worse, the worked example at `README.md:288` uses
  `num_designs=10000`, which a contributor copy-pasting will find **hard-fails Pydantic validation** (`le=500`).
- **Fix:** Update the table to `default 100 / range 1-500` for both params, and change every `num_designs=10000`
  example to a legal value (e.g. `num_designs=200`). Align MODEL.md and comparison.yaml (next item).

### 2. Docs reference a phantom `output_zip` response field
- **Category:** Docs / schema mismatch
- **Location:** `README.md:211`
- **Detail:** The documented response JSON includes `"output_zip": "base64-encoded zip of full output directory
  (optional)"`. `BoltzGenDesignResult` (`schema.py:790-814`) has only `cif`, `metrics`, `sequence`. No
  `output_zip` is ever produced. Callers will wait for a field that never arrives.
- **Fix:** Remove `output_zip` from the documented response (or implement it). Also reconcile the example metric
  keys (`iptm`, `scrmsd`) with the schema description, which advertises `plddt`/`ptm`/`affinity`.

### 3. `debug=True` left on the endpoint — leaks debug logs & stack traces to callers; deviates from house pattern
- **Category:** Security / Convention
- **Location:** `app.py:245`  (`@modal_endpoint(app_name=app_name, debug=True)`)
- **Detail:** With `debug=True`, `modal_endpoint` builds a `DebugLogger(enabled=True)`. On any error,
  `_error_response` appends the captured debug logs (including the truncated payload) and, on the uncaught
  fall-through, the full `traceback.format_exc()` into the `errors[]` returned **to the API caller**
  (`decorator.py:503-514`). Every other production model uses the default `debug=False` (esm2, dummy, …); only
  `boltz` and `boltzgen` set `debug=True`. For a public service this exposes internal file paths / stack
  structure on error paths.
- **Fix:** Drop `debug=True` (use the default). If verbose container-side logging is wanted, that already happens
  via `get_logger`; the caller-facing debug payload should stay off.

### 4. Knowledge-graph completeness: `pending` placeholders + a shipped `<!-- TODO -->`
- **Category:** Knowledge graph (rubric A9 — "no stray TODO/pending/template placeholders shipping")
- **Location:** `sources.yaml:62,69,70,77,78,93,105,106` (eight `pending` values for `pdf_r2`/`md_r2`);
  `MODEL.md:34` (`<!-- TODO: Extract exact parameter counts ... -->`)
- **Detail:** Multiple `applied_literature` entries carry `md_r2: pending` / `pdf_r2: pending`, and MODEL.md ships
  an HTML TODO comment. These are template/placeholder residue that should not ship in the public knowledge graph.
- **Fix:** Populate or remove the `pending` provenance entries; resolve or delete the MODEL.md TODO comment.

### 5. Mismatched upstream commits across app/fixture/sources, with a false "same commit" comment
- **Category:** Correctness / Provenance
- **Location:** `fixture.py:27-28` (comment + `BOLTZGEN_COMMIT = 3eddb5a…`), `helpers.py:34`
  (`BOLTZGEN_COMMIT = 617e549…`, used by `app.py` to `pip install -e`), `sources.yaml:43` (`commit: 3eddb5a`)
- **Detail:** The boltzgen code that is actually **installed and run** is pinned to `617e549…` (helpers.py →
  app.py). The fixture generator fetches example structures from `3eddb5a…` and its comment claims it is "Pinned
  to same commit used in app.py for reproducibility" — which is false. `sources.yaml` records `3eddb5a…` as the
  provenance snapshot, i.e. not the deployed code commit. Three references, two commits, one wrong comment.
- **Fix:** Pick a single source-of-truth commit. At minimum correct the fixture.py comment, and make
  `sources.yaml.commit` reflect the commit actually deployed (`617e549…`), or document why they differ.

### 6. LICENSE ships an unresolved "reviewer should verify" note with inferred holder/year
- **Category:** Licensing
- **Location:** `LICENSE:26-29`
- **Detail:** Copyright line is `Copyright (c) 2025 BoltzGen Contributors`, and the trailer states the holder and
  year were **inferred** and that "Reviewer should verify against the upstream LICENSE file before public
  release." That verification is a launch gate (rubric A8: "no inferred holder/year left unflagged" — it's
  flagged, but unresolved), and the process-note text itself is residue that should not ship in a LICENSE file.
- **Fix:** Verify the upstream `HannesStark/boltzgen` LICENSE, set the exact holder/year, and delete the
  reviewer-note trailer.

### 7. Malformed `arxiv` field in sources.yaml
- **Category:** Knowledge graph / metadata
- **Location:** `sources.yaml:25`  (`arxiv: 2025.11.20.689494`)
- **Detail:** `2025.11.20.689494` is the **bioRxiv DOI suffix**, not an arXiv identifier (the `doi:` field below
  correctly carries `10.1101/2025.11.20.689494`). The work is a bioRxiv preprint with no arXiv ID, so the `arxiv`
  key is wrong/misleading.
- **Fix:** Remove the `arxiv` key (or leave it empty); the DOI already captures the identifier.

---

## 🟡 nit

### 8. `traceback.print_exc()` duplicates structured logging
- **Location:** `helpers.py:206-209`
- **Detail:** `extract_sequence_from_cif` already does `logger.warning("Failed to extract sequence from CIF: %s",
  e, exc_info=True)` then immediately `import traceback; traceback.print_exc()`. The second call dumps an
  unstructured traceback to stderr and is redundant with `exc_info=True`. (Not caught by ruff T20 because it is
  not the `print` builtin, but it violates the structured-logging intent.)
- **Fix:** Delete the `import traceback` + `traceback.print_exc()` lines.

### 9. Unreachable defensive guard
- **Location:** `app.py:264-267`
- **Detail:** `if len(payload.items) > 1: raise UserError(...)` can never fire — `BoltzGenDesignRequest.items`
  is `Field(max_length=BoltzGenParams.batch_size)` with `batch_size = 1`, so validation rejects >1 first.
- **Fix:** Drop the check, or add a comment that it is belt-and-suspenders.

### 10. `reset_res_index` doc says "from 0" in README but "from 1" in schema
- **Location:** `README.md:648` ("renumber specified chains **from 0**") vs `schema.py:309,762` ("Reset residue
  numbering to start **from 1**")
- **Detail:** Internal documentation contradiction on the same feature.
- **Fix:** Confirm the actual boltzgen behavior and make both descriptions agree.

### 11. `Task.STRUCTURE_PREDICTION` tag contradicts the model's own docs
- **Location:** `config.py:47` vs `comparison.yaml:19,34`
- **Detail:** config tags the family with `Task.STRUCTURE_PREDICTION`, but comparison.yaml explicitly says "Not a
  structure prediction model... use Boltz, RF3, or AF2 NIM". (There is no `structure_generation` Task enum;
  `output_modality=[STRUCTURE]` already conveys that it emits structures.)
- **Fix:** Consider dropping `STRUCTURE_PREDICTION` from `task` (keep `SEQUENCE_GENERATION`), or reconcile the
  docs to explain the internal folding stage.

### 12. test.py campaign-size comments disagree with each other and the fixtures
- **Location:** `test.py:13` (docstring: chorismite `num_designs=3, budget=2`) vs `test.py:205-207` (comment:
  `num_designs=2, budget=1`); the actual R2 fixtures are generated by `fixture.py` at `num_designs=3, budget=2`.
- **Fix:** Make the inline comments match the fixtures.

### 13. HF-hub fallback dependency is implicit, not declared
- **Location:** `app.py:119` (`setup_download_layer(...)` with no `extra_pip_packages`)
- **Detail:** `download.py`'s fallback uses `AcquisitionStrategy.HUGGINGFACE_HUB`, which imports
  `huggingface_hub` (`downloads.py:457`). The download layer's base packages are only `boto3/pydantic/requests`,
  so this works **only** because boltzgen is `pip install`-ed earlier in the image and transitively provides
  `huggingface_hub`. The house rule (rubric A7) is to list build-time fallback deps explicitly.
- **Fix:** Pass `extra_pip_packages=["huggingface_hub"]` (pinned) to `setup_download_layer`, or document the
  transitive reliance.

### 14. `download.py` hand-rolls per-artifact AcquisitionConfig instead of reusing `r2_then_hf`
- **Location:** `download.py:80-135`
- **Detail:** `_download_artifact` rebuilds primary/fallback `AcquisitionConfig` objects manually for each of the
  6 artifacts. The canonical `r2_then_hf` helper (`download_helpers.py:390`) already does exactly this and is what
  other models use. A per-artifact loop calling `r2_then_hf(...)` would remove ~40 lines of duplication.
  (Multi-repo/multi-file means a fully-shared helper isn't a drop-in, hence 🟡 not 🟠.)
- **Fix:** Refactor `_download_artifact` to call `r2_then_hf` per artifact.

---

## D. Definition-of-Done audit (per-model slice)
- **Standard layout / config ModelFamily** — MET. All standard files present (plus `helpers.py`/`pipeline.py`
  decomposition, which is reasonable). `config.py` defines `ModelFamily` with `modal_class_name`, `action_schemas`,
  tags, naming/resource functions.
- **Canonical actions** — MET. Single `generate` action; correct verb for a design/generation model.
- **Schema field names / descriptions render** — MET. Verified no field is missing a rendered description in
  either request or response `model_json_schema()`; uses `RequestModel`/`ResponseModel`, batch under `results`.
- **Errors / logging** — MOSTLY MET. Uses `UserError` and `get_logger`. Detractors: `debug=True` info-leak (🟠 #3),
  redundant `traceback.print_exc()` (🟡 #8).
- **Acquisition self-populates R2** — MET (HF fallback caches back with `enable_r2_cache=True`); declared-dependency
  nit (🟡 #13) and reuse nit (🟡 #14).
- **Licensing** — PARTIAL. MIT and permissive, but holder/year inferred and an unresolved reviewer-note ships (🟠 #6).
- **Knowledge graph complete/consistent** — PARTIAL. Slug/display_name consistent; but `pending` placeholders +
  MODEL.md TODO (🟠 #4), wrong `arxiv` (🟠 #7), and doc/schema mismatches (🟠 #1, #2; 🟡 #10) remain.
- **Tests** — MET. Strong unit suite (`test_unit.py`, no Modal/GPU/R2), programmatic fast integration input,
  slow full-pipeline suite using R2 fixtures; fixtures lazy-loaded by the runner; no module-scope network.

## Verification

Adversarial re-check of the 7 HIGH-severity findings against the actual source. Verdicts:

1. **README param table vs schema/self — REAL.** `README.md:170` lists `num_designs` default 10000 / range 1-100000 and `:171` `budget` range 1-10000, but `schema.py:600-603` enforces `num_designs` default 100/ge=1/le=500 and `:614-617` `budget` default 100/le=500; `README.md:37` says "both are capped at 500"; the `README.md:288` example `num_designs=10000` hard-fails Pydantic `le=500`. Self-contradictory + would raise ValidationError.
2. **Phantom `output_zip` response field — REAL.** `README.md:211` documents `output_zip`, but `BoltzGenDesignResult` (`schema.py:790-814`) only defines `cif`/`metrics`/`sequence`; `grep -rn output_zip models/boltzgen/` matches README only — never produced anywhere in app/pipeline/helpers.
3. **`debug=True` leaks logs & traceback to callers — REAL.** `app.py:245` sets `debug=True` (vs decorator default `debug=False` at `decorator.py:31`; only boltz `app.py:443` also opts in). `_error_response` appends `debug_logger.get_logs()` (incl. truncated payload logged at `decorator.py:176`) when enabled (`:503-505`), and the fall-through handler passes `traceback_info=True` (`:454-461`) → `traceback.format_exc()` appended to `ErrorResponse.errors` (`:508-510`), which is serialized and returned to the caller.
4. **`pending` placeholders + shipped TODO — REAL.** `sources.yaml` lines 62,69,70,77,78,93,105,106 carry `md_r2: pending`/`pdf_r2: pending` (8 total, confirmed); `MODEL.md:34` ships `<!-- TODO: Extract exact parameter counts ... -->`.
5. **Mismatched upstream commits + false comment — REAL.** Deployed code is `617e549...` (`helpers.py:34` `BOLTZGEN_COMMIT`, imported and `git checkout`-ed in `app.py:10,79`). `fixture.py:28` pins `3eddb5a...` while `fixture.py:26` claims "Pinned to same commit used in app.py for reproducibility" — false; `sources.yaml:43` records `3eddb5a`. Three references, two commits, one wrong comment.
6. **LICENSE ships unresolved reviewer note — REAL.** `LICENSE:3` holder "BoltzGen Contributors" 2025; `LICENSE:26-29` states holder/year were inferred and "Reviewer should verify against the upstream LICENSE file before public release" — process residue inside a LICENSE file, and an unresolved launch gate.
7. **Malformed `arxiv` field — REAL.** `sources.yaml:25` `arxiv: 2025.11.20.689494` is the bioRxiv DOI suffix (date-based), not a valid arXiv ID (`YYMM.NNNNN`); `sources.yaml:26` `doi: 10.1101/2025.11.20.689494` correctly carries the same value, and `venue` (`:27`) is "bioRxiv preprint" — no arXiv ID exists for this work.

**Summary:** 7/7 REAL. Each is directly demonstrable at the cited lines; no refutation found.
