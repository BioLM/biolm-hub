# Round-1 Review — Dependencies & Image Build (cross-cutting)

**Reviewer scope:** `pyproject.toml` (deps / pins / extras), `uv.lock`, `.python-version`, the shared
image-build helpers (`models/commons/modal/downloader.py`, `models/commons/modal/source.py`,
`models/commons/util/config.py::common_requirements`), and every `models/*/app.py` image-build block.
Graded against RUBRIC §A (esp. A.7 acquisition / build-order rule), §B (10x/dead-code/consistency),
§C (OSS-readiness / no-internal-leakage), and the CLAUDE.md ground rule "pin all ML deps to exact
versions".

## Summary

The build architecture is genuinely good: a single `setup_download_layer()` (weights, cache-busted by a
source hash) + `setup_source_layer()` (code) pair is reused by all 46 models, `common_requirements` is
centralized, container pins are mostly exact-and-commented, dev/lock/extras are coherent, and build
artifacts (`site/`, `*.egg-info`, `__pycache__`) are correctly gitignored. `.python-version` (3.12) is
consistent with `requires-python` and the black/ruff/mypy targets; per-model container Pythons
(3.10/3.11/3.12) legitimately vary by model compatibility.

The most important defect is a **build-order-rule violation (A.7)** in a subset of HuggingFace-backed
models (`esmc`, `zymctrl`, `temberture`, latently `evo2`): they run the HF acquisition strategy inside
the download layer but install `huggingface_hub` only in the *runtime* layer added *after* it, so the
documented "self-populate from HF on a cold R2 bucket" path raises `ImportError` at build. Eleven sibling
HF models do this correctly via `extra_pip_packages`, so this is both a correctness bug and a
cross-model inconsistency. Secondary issues: one dead build helper that still leaks internal
workflow concepts, a fabricated dependency-pin justification in `pyproject.toml`, and loose pins in the
download layer that contradict the exact-pin rule.

No secrets, no `biolm-modal` references, no `.planning` refs, and no raw third-party PDFs were found in
the build/dependency surface. (Note: `models/commons/util/config.py:82-84` hardcodes the internal `qa`
environment name — flagging for the internal-leakage reviewer; out of this dimension's scope.)

---

## Findings

### 🟠 1. Build-order rule violated: HF download layer is missing `huggingface_hub` (esmc, zymctrl, temberture; latent in evo2)
**Category:** Acquisition / build-order (A.7) + cross-model consistency
**Location:** `models/esmc/app.py:55-69`, `models/zymctrl/app.py:43-56`,
`models/temberture/app.py:52-68`, `models/evo2/app.py:57-83`

`setup_download_layer()` only installs `boto3`, `pydantic`, `requests` plus whatever the caller passes in
`extra_pip_packages` (`models/commons/modal/downloader.py:77-85`). Its `run_function` executes at the
*position it is chained into the image*, i.e. before the later `.uv_pip_install(...)` runtime layers. For
the four models above the download layer runs `r2_then_hf` / the `HUGGINGFACE_HUB` fallback, which calls
`download_from_hf()` → `from huggingface_hub import snapshot_download`
(`models/commons/storage/downloads.py:457`). But `huggingface_hub` is installed *only* in the runtime
layer added afterward:

- `esmc/app.py:67` — `.uv_pip_install("huggingface_hub==0.36.2")  # Required for HF fallback in download.py`
- `zymctrl/app.py:55` — `"huggingface_hub==0.26.0",  # Required for HF fallback in download.py`
- `temberture/app.py:68` — `"huggingface_hub==0.16.4",  # Compatible version with adapters==0.1.1`
- `evo2/app.py` — `huggingface_hub` is not in the download layer at all (relies on a pre-populated R2,
  per the comment in `evo2/download.py:56-58`).

The in-file comments in `esmc`/`zymctrl` literally say the package is needed for the *download* fallback,
yet place it where the download layer can't see it. On a **cold R2 bucket** (the exact self-population
scenario A.7 exists for, and what an outside contributor hits when overriding `BIOLM_R2_BUCKET`), the
build-time HF fallback fails with `ImportError`. The base `pytorch/pytorch:*` images do not ship
`huggingface_hub`, so there is no transitive rescue. Eleven other HF models do this correctly —
`esm1b/esm1v/igbert/igt5/prostt5/e1` (`huggingface_hub==0.26.0`), `dsm` (`0.36.0`), `spurs` (`0.24.6`),
`dnabert2` (`0.19.4`), `omni_dna` (`0.27.1`), `abodybuilder3` (`0.26.0`) — all via
`setup_download_layer(extra_pip_packages=[...])`.

This is a ratified-standard (A.7 / DoD) conformance miss that breaks cold-cache self-population; treat as
🔴 if first-deploy self-population to a cold public bucket is a launch gate.

**Fix:** Add `huggingface_hub` to `extra_pip_packages` of each affected `setup_download_layer(...)` call
(pin to the same version already used in the runtime layer), e.g. `esmc`:
`setup_download_layer(..., extra_pip_packages=["huggingface_hub==0.36.2"])`. Keep the runtime install too
(the model loader also needs it). Do the same for `zymctrl`, `temberture`, and `evo2`.

---

### 🟠 2. Dead build helper leaks internal "workflows" concepts (`setup_workflow_source_layer`)
**Category:** Dead code / 10x / OSS-readiness (C: no internal leakage)
**Location:** `models/commons/modal/source.py:76-141`

`setup_workflow_source_layer()` is never called anywhere in `models/`, `cli/`, or `gateway/` (its only
occurrences are inside its own docstring example, lines 93/96). It targets a `workflows/` directory that
does not exist in this repo, and its docstring example names internal workflow slugs (`"xgboost"`,
`"abworkflow"`) carried over from the internal `biolm-modal` repo. This is leftover scaffolding that adds
surface area and leaks an internal concept into a file that ships publicly.

**Fix:** Delete `setup_workflow_source_layer` (and the `include_models`/`workflows` machinery) until a
real workflow ships. If retained, drop the internal slug names from the example.

---

### 🟠 3. Fabricated dependency-pin justification in `pyproject.toml` (`docs` extra)
**Category:** OSS-readiness / docs accuracy (C)
**Location:** `pyproject.toml:38-41`

The comment justifies pinning `mkdocs-gen-files==0.5.0` / `mkdocs-literate-nav==0.6.1` as: *"Pinned to the
last releases before these plugins took a hard dependency on `properdocs`, which injects a promotional
banner into every build."* No package named `properdocs` exists, and neither `mkdocs-gen-files` nor
`mkdocs-literate-nav` (both by `oprypin`) has ever depended on such a thing; `mkdocs-gen-files==0.5.0` is
already the latest release, so "last release before X" is moot. This reads as a hallucinated rationale
that will ship in the public `pyproject.toml`.

**Fix:** Replace with the real reason for the pin (or drop the pin to a range like the other docs deps).
If the intent was simply reproducibility, say so plainly.

---

### 🟠 4. Loose, inconsistent pins in the download layer contradict the exact-pin rule
**Category:** Pinning discipline / reproducibility (CLAUDE.md ground rule; A consistency)
**Location:** `models/commons/modal/downloader.py:77-81`

The download layer's `base_packages` pins `pydantic>=2.0,<3.0` and `requests>=2.28.0,<3.0` (only
`boto3==1.35.78` is exact). The rest of the codebase pins `pydantic==2.11.7` exactly
(`pyproject.toml`, `common_requirements`). Because `_add_minimal_commons` mounts each model's `schema.py`
and `config.py` (Pydantic v2 models) into the download container and they are imported during the
download run, a drifting `pydantic` 2.x at build time can diverge from the `2.11.7` used at runtime —
unreproducible builds and a possible build/runtime behavior mismatch.

**Fix:** Pin the download layer to the same exact versions as `common_requirements`
(`pydantic==2.11.7`, and an exact `requests==...`). Ideally derive `base_packages` from the shared
`common_requirements` source of truth rather than re-declaring them here.

---

### 🟡 5. Stale docstring import path in `setup_source_layer`
**Category:** Docs accuracy / readability (C)
**Location:** `models/commons/modal/source.py:27`

The docstring example imports `from models.commons.image_builder import setup_source_layer`, but the
function actually lives in `models.commons.modal.source`. A contributor copy-pasting the example gets an
`ImportError`.

**Fix:** Update the example to `from models.commons.modal.source import setup_source_layer`.

---

### 🟡 6. `huggingface_hub` version sprawl across models
**Category:** Consistency (A/C)
**Location:** `models/*/app.py` (9 distinct pins: 0.16.4, 0.19.4, 0.24.6, 0.26.0 ×10, 0.27.1, 0.30.2,
0.33.4, 0.36.0, 0.36.2)

Nine different `huggingface_hub` pins ship across the catalog. Some divergence is legitimate (e.g.
`temberture`'s `0.16.4` is constrained by `adapters==0.1.1`), but most models could share one modern pin.
The spread makes it hard to reason about the build surface and to do security bumps uniformly.

**Fix:** Consolidate to a small set of blessed versions (ideally one default in `common_requirements`-
style shared list, with documented exceptions where a model genuinely needs an older pin).

---

### 🟡 7. Generic top-level package names published as installable distributions
**Category:** Packaging hygiene (B/C)
**Location:** `pyproject.toml:76-78`

`[tool.setuptools.packages.find]` ships `cli*`, `models*`, `gateway*` as top-level importable packages.
`import models` / `import gateway` are very generic names that can collide with other packages in a shared
environment for anyone who runs `pip install biolm-models`. The project is primarily used from a repo
checkout (Modal `add_local_dir` uses relative paths), so impact is limited today, but the published
namespace is collision-prone.

**Fix:** Namespace under a single distribution package (e.g. `biolm_models/{cli,models,gateway}`), or
document that the package is intended for checkout/Modal use rather than `import models` consumption.

---

### 🟡 8. `spurs` chains two download layers; the first (ESM2 weights) carries no fallback deps
**Category:** Consistency / build-order (A.7) — minor
**Location:** `models/spurs/app.py:47-59`

`spurs` calls `setup_download_layer` twice — first for ESM2-650M weights (no `extra_pip_packages`), then
for SPURS checkpoints (correctly with `huggingface_hub==0.24.6`). ESM2's acquisition is library-managed
(`fair-esm`), which `spurs` installs only in the later runtime layer (line 75). On a cold ESM2 R2 prefix
the first layer would have no library to fall back to — same latent cold-cache caveat as finding #1,
though ESM2 weights are almost always already warm in R2.

**Fix:** If cold-bucket robustness matters, give the first layer the deps its fallback needs (or document
that the ESM2 prefix is expected to be pre-populated).

---

## Definition-of-Done audit (this dimension)

- **Exact pins / reproducibility:** *Partially met.* Container `common_requirements` and most per-model
  pins are exact and commented; `uv.lock` is present and resolves the core pins (modal 1.3.5, pydantic
  2.11.7, fastapi 0.112.0). Gaps: loose `pydantic`/`requests` in the download layer (#4) and `hf_hub`
  sprawl (#6).
- **Extras hygiene:** *Met.* `serve` / `docs` / `dev` / `mypy-types` are cleanly separated and opt-in,
  with rationale comments — except the `docs` rationale is fabricated (#3).
- **Build-order rule (A.7):** *Not met for esmc/zymctrl/temberture/evo2* (#1); met for the other 11 HF
  models and the URL/library/custom models.
- **No internal leakage in build surface:** *Mostly met,* except dead `setup_workflow_source_layer`
  leaks internal workflow slugs (#2). (`qa` env name in `config.py` flagged for the leakage reviewer.)
- **Build-artifact hygiene:** *Met.* `site/`, `*.egg-info`, `__pycache__`, weights dirs all gitignored;
  none tracked.

---

## Verification

Adversarial re-check of the four HIGH findings against the actual code/files and live PyPI data.

- **#1 HF download layer missing huggingface_hub (esmc, zymctrl, temberture; latent evo2) — REAL.**
  `setup_download_layer` installs only `boto3==1.35.78` + loose `pydantic`/`requests` + `extra_pip_packages`
  (`downloader.py:77-85`) and runs its `run_function` (`downloader.py:111-121`) at the chained position —
  before the runtime `.uv_pip_install` layers. esmc (`app.py:55-60` no `extra_pip_packages`; hf only at
  `app.py:67`), zymctrl (`app.py:55`), temberture (`app.py:68`) install `huggingface_hub` only in the later
  runtime layer; evo2 never installs it. All four run an HF fallback in the download layer
  (esmc `download.py:49` `r2_then_hf`; zymctrl `download.py:30` `r2_then_hf`; temberture `download.py:88-107`
  HUGGINGFACE_HUB fallback; evo2 `download.py:119-131` HUGGINGFACE_HUB fallback) -> `download_from_hf` does
  `from huggingface_hub import snapshot_download` (`downloads.py:457`). The 11 sibling HF models pass
  `extra_pip_packages=["huggingface_hub==..."]` to `setup_download_layer` (verified esm1b/esm1v/igbert/igt5/
  prostt5/e1/dsm/spurs/dnabert2/omni_dna/abodybuilder3). Cold-bucket build-time fallback raises ImportError.

- **#2 setup_workflow_source_layer is dead and leaks internal workflow slugs — REAL.**
  `grep -rn setup_workflow_source_layer` over the whole repo returns only `source.py:76` (def) and `:93/:96`
  (its own docstring example); no caller in `models/`, `cli/`, or `gateway/`. `ls workflows` -> No such file.
  Docstring names internal slugs `xgboost`/`abworkflow` (`source.py:85,96`). Dead code targeting a
  nonexistent dir in a publicly-shipping file.

- **#3 Fabricated 'properdocs' justification for docs-extra pins — REFUTED.**
  Live PyPI contradicts all three load-bearing claims: `properdocs` DOES exist (`pypi.org/pypi/properdocs`
  v1.6.7), mkdocs-gen-files `0.6.0/0.6.1` and mkdocs-literate-nav `0.6.x` DO declare `properdocs>=1.6.5`
  in `requires_dist`, and `0.5.0` is NOT the latest gen-files release (latest is `0.6.1`, released 2026-03-16,
  after the reviewer's knowledge cutoff). Independent search corroborates (properdocs.org, Repology, piwheels,
  libraries.io). The pin to `0.5.0` is genuinely "the last release before the properdocs dependency" — the
  rationale is substantively correct, not hallucinated. (Only the "promotional banner" flavor is unverified;
  the properdocs PyPI description doesn't mention a banner — but that is not the finding's basis.)

- **#4 Download layer uses loose pydantic/requests pins inconsistent with exact pins elsewhere — REAL.**
  `downloader.py:78-80` pins `boto3==1.35.78` exact but `pydantic>=2.0,<3.0` and `requests>=2.28.0,<3.0`
  loose, while `pyproject.toml:18` and `common_requirements` (`config.py:28`) pin `pydantic==2.11.7` exact.
  `_add_minimal_commons` mounts each model's `schema.py`/`config.py` (`downloader.py:200-204`) and they are
  imported during the download run (`_run_download_with_params` -> `from download import download_model_assets`
  -> imports `schema`/`config`). Loose build-time pydantic can drift from the 2.11.7 used at runtime;
  inconsistent with the project's exact-pin rule. (Severity arguably below HIGH: pydantic 2.x patch drift
  rarely changes behavior, and boto3 is already loose in `pyproject.toml` — but the inconsistency is real.)
