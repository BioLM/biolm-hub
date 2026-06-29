# Review — `models/dummy/` (round 1)

## Summary

`dummy` is the repo's ratified **TEMPLATE** model (`.planning/02_MODEL_INCLUSION_MATRIX.md:33` —
"keep as the new-model template"; CONTRIBUTING + the skills point new contributors at
`models/dummy/README.md` as the README standard). It is therefore reviewed on two axes: (1) as a real,
deployable smoke-test model and (2) as the canonical scaffold every new model is copied from. The
*plumbing* is clean and idiomatic — `config.py` builds a correct single-variant `ModelFamily` with the
right `modal_class_name`, `action_schemas`, tags (`PLACEHOLDER`/`UTILITY`/`TEXT` are all legitimate
enum members intended for utility models), and naming function; `schema.py` matches the house pattern
(`ModelParams` subclass mirrors `ESM2Params`; batch under `results`, input under `items`; every field
has a rendering `Field(description=...)`); `app.py` uses `get_logger` (no `print`), the snapshot
mixin, and the canonical decorator/deploy helpers; `test.py` has both integration + deployment cases
with lazy, programmatic input. The schema descriptions accurately match what `app.py` computes
(suffix append + `data_file_content` from the build-time JSON), and `test.py`'s expected output is
consistent with `initialize_data` (`{"hello": "world"}`). No weights, so the `r2_then_*` acquisition
wrappers correctly do not apply (`setup_source_layer` only).

The findings below are concentrated in the **knowledge-graph / packaging** layer, where `dummy`
diverges from the other 43 models — and because this is the template, each divergence propagates into
every model copied from it. One internal-reference leak is launch-gating.

Because `dummy` IS the template, its `README.md`/`MODEL.md`/`BIOLOGY.md`/`sources.yaml` being
unpopulated scaffolds (`{Model Display Name}`, `Author A`, TODO blocks) is **by design** and is NOT
flagged as "template residue shipping" — that is the intended content of these files.

---

## 🔴 Must-fix

### 1. Internal-reference leak: `r2://biolm-modal/` in a shipped (and template-propagated) file
- **Category:** No internal leakage / open-source readiness (rubric C, A.9)
- **Location:** `models/dummy/sources.yaml:106`
- **Detail:** The comment reads `# R2 path (without r2://biolm-modal/ prefix) to the PDF.`
  `biolm-modal` is the internal repo/bucket name and is explicitly enumerated by the rubric as a
  launch-gating internal-reference leak. It also contradicts this same file's own header convention,
  which documents the public bucket `r2://biolm-public/knowledge-base/...` (lines 10, 13–15). Worst of
  all, this is the **template**: every new model authored by copying `dummy/sources.yaml` will carry
  the leaked name forward. (Already tracked in `.planning/REMAINING_WORK.md` de-internalization sweep
  as "still open" — listed as `models/dummy/sources.yaml (comment)` — but not yet fixed.)
- **Fix:** Change the comment to `# R2 path (without r2://biolm-public/ prefix) to the PDF.` and grep
  the file once more for any other `biolm-modal` occurrence.

---

## 🟠 Should-fix

### 2. Missing `comparison.yaml` — incomplete 5-file knowledge graph (template gap)
- **Category:** Knowledge graph completeness / cross-model uniformity (rubric A.1, A.9)
- **Location:** `models/dummy/` (directory — file absent)
- **Detail:** The ratified knowledge graph is five files: `sources.yaml`, `comparison.yaml`,
  `README.md`, `MODEL.md`, `BIOLOGY.md`. `dummy` ships only four — it is the **only model of 44 with a
  `config.py` that lacks a `comparison.yaml`** (verified by directory scan; `esm2` has one). Since
  contributors copy `dummy` as the scaffold, the missing file means they get no template for
  `comparison.yaml` and are likely to omit it too.
- **Fix:** Add a `models/dummy/comparison.yaml` template scaffold (mirroring the structure of
  `models/esm2/comparison.yaml`, with placeholder/illustrative content consistent with the other
  template docs).

### 3. Missing per-model `LICENSE` file (declared MIT in sources.yaml, no file present)
- **Category:** Licensing / cross-model uniformity (rubric A.8)
- **Location:** `models/dummy/` (directory — file absent); declared at `models/dummy/sources.yaml:38`
  (`type: "MIT"`)
- **Detail:** Rubric A.8 requires a per-model `LICENSE` consistent with `sources.yaml`. `dummy`
  declares `MIT` in `sources.yaml` but ships no `LICENSE` file — again the **only model of 44 without
  one** (`esm2/LICENSE` exists). As the template, this teaches contributors that a per-model `LICENSE`
  is optional, propagating the gap.
- **Fix:** Add `models/dummy/LICENSE` (an MIT license text, with a clearly placeholder copyright
  holder/year suitable for a template) so the requirement is visible in the scaffold.

### 4. `display_name` mismatch between `sources.yaml` and `config.py`/`schema.py`
- **Category:** Knowledge-graph internal consistency (rubric A.9)
- **Location:** `models/dummy/sources.yaml:30` vs `models/dummy/schema.py:11`
- **Detail:** `sources.yaml` declares `display_name: "Dummy Model"` with the explicit comment "The
  display_name from config.py / ModelFamily … Must match …", but the actual config/schema value is
  `display_name = "Dummy"` (used in `app.py` logs and the deploy description). A.9 requires
  slug/display_name to match config; here they don't, in the very file whose comment says they must.
- **Fix:** Set `sources.yaml` `display_name: "Dummy"` (or, if "Dummy Model" is preferred, change
  `schema.py`/`config.py` to match — but config is the source of truth, so align sources.yaml to it).

---

## 🟡 Nits

### 5. Template-placeholder docs surface under a browsable/deployable model directory
- **Category:** Open-source readiness / UX (rubric C)
- **Location:** `models/dummy/README.md:1` (`# {Model Display Name}`) and peers
- **Detail:** Intentional (dummy is the template), so not a residue violation — but `dummy` is also a
  live smoke-test model with deployment tests, and the local catalog app (`bm serve`) browses deployed
  models. A public visitor landing on `models/dummy` will see `{Model Display Name}` and TODO blocks
  with no signal that this is a scaffold. Low severity, ratified design.
- **Fix (optional):** Add a one-line banner at the top of `README.md` such as
  `> Template/example model — copy this directory as the starting point for a new model.` so the
  placeholder content reads as intentional.

### 6. Duplicated default content `{"hello": "world"}` in `app.py`
- **Category:** Simplicity / DRY (rubric B)
- **Location:** `models/dummy/app.py:29` (`initialize_data`) and `models/dummy/app.py:82`
  (`setup_model` fallback)
- **Detail:** The default payload is written in two places. Harmless and arguably useful as a
  defensive-fallback illustration, but since this is the copy-me template, hoisting it to a single
  module constant would model better practice.
- **Fix (optional):** Define `DEFAULT_DATA = {"hello": "world"}` once and reference it in both spots.

---

## Definition-of-Done notes (rubric D)
- **Layout / actions / schema names / field descriptions / errors / logging / tests:** MET. Single
  `predict` action (correct verb for a utility model), closed-set action, `items`/`results`, rendering
  field descriptions, structured logging, integration + deployment tests with lazy input.
- **Acquisition (A.7):** N/A — no weights; `setup_source_layer` only; build-time `initialize_data`
  JSON is appropriate. Correctly no `download.py`.
- **Knowledge graph (A.9):** PARTIALLY MET — 4 of 5 files present (no `comparison.yaml`, finding #2);
  template-scaffold content is intended; one internal-consistency miss (finding #4).
- **Licensing (A.8):** PARTIALLY MET — license declared in `sources.yaml`, but no `LICENSE` file
  (finding #3).
- **No internal leakage (C):** NOT MET — `biolm-modal` leak (finding #1, launch-gating).

## Verification

- **test** (`a:1`): **refuted** — placeholder finding; cited file `a` does not exist in the repo (`ls /Users/qamar/dev/biolm-models/a` → No such file) and the detail "test" describes no concrete code issue, so nothing is demonstrable.
