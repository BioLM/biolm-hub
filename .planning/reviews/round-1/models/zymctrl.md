# Review — `models/zymctrl/`

**Reviewer:** independent round-1 (rubric A–D)
**Verdict:** Solid, well-documented single-variant generative model that closely follows the house
pattern (config/schema/download/test/knowledge-graph all present and largely consistent with `esm2`
and `progen2`). One launch-gating issue: the HuggingFace fallback dependency is installed in the
wrong image layer, so a cold-R2 deploy cannot self-populate. A handful of should-fix items:
perplexity is computed over padding/EOS tokens (contradicting the documented "amino-acids-only"
methodology), `temperature` permits a value that crashes generation, the encode response field is
named `embedding` where the rest of the repo uses `embeddings`, and the fixture hardcodes a standard
sequence that lives in the shared-asset library.

Cross-checked: actions are in the closed set (`generate`/`encode`); slug/display_name are consistent
across `config.py`/`schema.py`/`sources.yaml`/`comparison.yaml`; all `comparison.yaml` model slugs
exist in `models/`; LICENSE (Apache-2.0 + NOTICE) matches `sources.yaml`; no `biolm-modal`/`.planning`/
internal-domain leaks; nested `results: list[list[...]]` generate shape matches `progen2`.

---

## 🔴 Must-fix

### 1. HF fallback dep (`huggingface_hub`) is in the wrong image layer → cold-R2 self-populate build fails
**Category:** Acquisition / build-order (rubric A7, DoD self-population)
**Location:** `models/zymctrl/app.py:43-57` (and the misplaced dep at `app.py:55`)

`setup_download_layer(...)` runs `download_model_assets` → `r2_then_hf` **at image-build time** inside
its own `run_function`. That download layer only installs `boto3`/`pydantic`/`requests` plus whatever
is passed via `extra_pip_packages` (see `models/commons/modal/downloader.py:77-85`). On an R2 cache
miss the HF fallback calls `download_from_hf` → `from huggingface_hub import snapshot_download`
(`models/commons/storage/downloads.py:457`, reached via `_acquire_huggingface_hub`,
`models/commons/storage/acquisition.py:665-728`).

ZymCTRL installs `huggingface_hub==0.26.0` only in the **later** `app.py` runtime layer
(`app.py:55`) — i.e. *after* the download layer has already run. The author's own comment even says
"Required for HF fallback in download.py", but it is placed where the build-time download can't see
it. So against an empty/new bucket the image build raises `ModuleNotFoundError: huggingface_hub` and
the deploy fails; the model only works because R2 is already warm. `esm2` does this correctly by
passing its fallback lib to `setup_download_layer(extra_pip_packages=[...])` (`models/esm2/app.py:47-56`).

**Fix:** pass `huggingface_hub` to the download layer:
```python
image = setup_download_layer(
    image,
    base_model_slug=ZymCTRLParams.base_model_slug,
    params_version=ZymCTRLParams.params_version,
    extra_pip_packages=["huggingface_hub==0.26.0"],
)
```
(Keep it in the runtime install too, or rely on `transformers` pulling it in.)

---

## 🟠 Should-fix

### 2. Perplexity is computed over `<end>`/EOS/padding tokens, contradicting the documented methodology
**Category:** Correctness / schema-vs-runtime claim mismatch (rubric B, A4)
**Location:** `models/zymctrl/app.py:104-130` (loss over `shift_labels`) + caller `app.py:249-258`

`generate()` calls `self.model.generate(..., num_return_sequences=num_samples)` (default 5). HF pads
all returned rows to the longest sequence with `pad_token_id` (0). `calculate_sequence_perplexity`
then takes `shift_labels = input_ids[:, sequence_start_idx:]` and runs `CrossEntropyLoss(reduction=
"mean")` with no `ignore_index`/mask — so the mean loss includes the `<end>` token, `<|endoftext|>`,
and (for every sequence that finished before the longest) a run of `<pad>` tokens. This contradicts
the docstring "perplexity is computed on the amino acid tokens, excluding the EC number and control
tokens" (`app.py:89-94`) and the same claim repeated in `MODEL.md`/`README.md`/`BIOLOGY.md`. Because
padding length varies per sample, it distorts the ascending perplexity sort that is the model's
headline quality signal. (No contamination when `num_samples=1`, but the default is 5.)

**Fix:** mask out everything from the first `<end>`/EOS onward before computing loss (e.g. truncate
each row at its EOS, or pass `ignore_index=pad_token_id` and zero out post-EOS positions), so loss
covers only amino-acid token positions as documented.

### 3. `temperature` allows `0.0`, which raises an uncaught error under `do_sample=True`
**Category:** Schema/validation edge case (rubric A5, B)
**Location:** `models/zymctrl/schema.py:62-67` (`ge=0.0`), used at `app.py:216,236-247`

`generate()` always passes `do_sample=True`. With `temperature=0.0`, transformers'
`TemperatureLogitsWarper` raises `ValueError` (temperature must be > 0), which surfaces as an
unhandled server error rather than a clean 422. The schema advertises `0.0` as valid (and `README.md:64`
mirrors `0.0-2.0`).

**Fix:** change the bound to `gt=0.0` (and update `README.md` to `>0.0–2.0`).

### 4. Encode response field `embedding` (singular) deviates from the repo-wide `embeddings`
**Category:** Schema field-name uniformity (rubric A3, C)
**Location:** `models/zymctrl/schema.py:205-208`

Every other embedding model uses the plural `embeddings` for the pooled-vector field:
`dsm` (the closest analog — a single flat `embeddings: Optional[list[float]]`,
`models/dsm/schema.py:255`), `esm2`/`esmc`/`esm1b` (`embeddings: Optional[list[LayerEmbedding]]`).
ZymCTRL is the only model naming it `embedding`. The companion `per_token_embeddings` *does* match the
house name, which makes the singular `embedding` stand out further. The rubric's north star is that
the diff between models is the science, not the plumbing.

**Fix:** rename to `embeddings` (keep `embedding` as a Pydantic `alias` if back-compat is desired).
Update `app.py:341,345` and `README.md:110-114` accordingly.

### 5. Fixture hardcodes a standard sequence that lives in the shared-asset library
**Category:** Tests / shared assets (rubric A10, W12 DoD)
**Location:** `models/zymctrl/fixture.py:73`

The encode fixture hardcodes `"MKTVRQERLKSIVRILERSKEPVSGAQLAEELSVSRQVIVQDI"`, which is a truncated
prefix of `STANDARD_PROTEIN_STABILITY` in `models/commons/testing/shared_assets.py:29-30`. W12 added
the shared-asset library precisely to dedupe these; peers (`esmstabp`, `temberture`, `esm1b`, `esmc`,
`e1`, `dsm`) import their fixture sequences from `shared_assets`. ZymCTRL does not.

**Fix:** import and reuse `STANDARD_PROTEIN_STABILITY` (slice if a shorter input is intentionally
wanted, with a comment) instead of an inline literal.

### 6. Internal `qa` environment name in the shipped `__main__` docstring
**Category:** Open-source readiness / internal leakage (rubric C)
**Location:** `models/zymctrl/app.py:363` (`# Force deploy to "qa" or "main" environment:`)

The rubric lists the internal `qa` env among internal-reference leaks. **Systemic note:** this exact
comment is copy-pasted in `esm2` (`models/esm2/app.py:484`) and almost certainly every model's
`__main__` block, so it should be fixed as a repo-wide sweep (or in the shared template), not just
here. Flagging for dedupe by the orchestrator.

**Fix:** drop the internal env names from the usage docstring (e.g. "optionally deploy" without naming
`qa`).

---

## 🟡 Nits

### 7. `layer` request-param description is phrased as a response field
**Category:** Field description accuracy (rubric A4)
**Location:** `models/zymctrl/schema.py:146-151`

`description="Model layer this representation was taken from."` is past-tense response phrasing
(it's copied from `esm2`'s response-side `LayerEmbedding.layer`). Here `layer` is an input the caller
*chooses*. Suggest: "Hidden layer to extract the representation from (negative indexes count from the
last layer)."

### 8. `sources.yaml` applied-literature entries carry `unknown2024*.pdf` placeholder filenames
**Category:** Knowledge-graph polish (rubric A9)
**Location:** `models/zymctrl/sources.yaml:65,81,89` (`unknown2024.pdf`, `unknown2024b.pdf`,
`unknown2024c.pdf`)

These look like unresolved-author residue — the convention elsewhere is `<firstauthor><year>.pdf`
(e.g. the primary paper's `munsamy2024.pdf`, esm2's `lin2023.pdf`). Several of these entries also omit
`authors`. (The `pdf_r2: pending`/`md_r2: pending` values themselves match the house pattern — `esm2`
uses `pending` for applied lit too — so those are fine.) Suggest renaming to real author/year stems
and filling `authors`.

### 9. Perplexity does a second full forward pass per sample
**Category:** Simplicity / efficiency (rubric B)
**Location:** `models/zymctrl/app.py:251-258` → `app.py:104-130`

After `model.generate()`, each output is re-run through the model (`model(input_ids)`) to score
perplexity — up to `num_samples` (≤20) extra full forward passes per request. The generation step can
already return per-step scores (`output_scores=True`/`return_dict_in_generate=True`); reusing them
(or batching the scoring pass) would avoid the recompute. Acceptable as-is, but noted.

---

## Definition-of-Done audit (zymctrl-scoped)
- **Layout / 5-file KG / config ModelFamily:** met — all files present; `modal_class_name`,
  `action_schemas`, tags, single-variant naming all correct.
- **Closed-set actions / verbs:** met (`generate`, `encode`).
- **Field descriptions render:** met (no `Field` buried in `Optional[Annotated[...]]`); accuracy nit
  #7.
- **Schema field-name uniformity:** partial — `embedding` should be `embeddings` (#4).
- **Errors/logging:** met — `get_logger`, no `print`, no full-sequence/secret logging; EC/AA
  validation via Pydantic field validators (idiomatic). Edge case #3.
- **Acquisition self-populates:** **not met** — build-order bug (#1).
- **Licensing:** met — Apache-2.0 + NOTICE attribution to AI4PD/Ferruz, consistent with `sources.yaml`.
- **Tests:** mostly met — integration + deployment cases, lazy fixtures, no module-scope R2/network;
  shared-asset reuse gap (#5).

---

## Verification

Adversarial re-check of the six HIGH-severity findings against the actual code.

1. **HF fallback dep in wrong image layer (cold-R2 build fails) — REAL.** `app.py:43-47` calls `setup_download_layer` with NO `extra_pip_packages`; the download `run_function` installs only boto3/pydantic/requests (`downloader.py:77-85`). `download.py:30` uses `r2_then_hf`, whose HF fallback (`acquisition.py:665` → `downloads.py:457`) does `from huggingface_hub import snapshot_download` at build time. `huggingface_hub==0.26.0` is installed only later at `app.py:55`. esm2 does it correctly via `extra_pip_packages` (`esm2/app.py:47-56`). Cold/empty bucket ⇒ ModuleNotFoundError at build.

2. **Perplexity over `<end>`/EOS/pad tokens — REAL.** `app.py:124-128` runs `CrossEntropyLoss(reduction="mean")` over `shift_labels = input_ids[:, sequence_start_idx:]` (`app.py:118`) with no `ignore_index`/mask, so trailing `<end>`, `<|endoftext|>`, and (default `num_samples=5`, `app.py:246`; pad_token_id=0, `app.py:244`) `<pad>` tokens are scored. Contradicts docstring `app.py:89-94` and README.md:209,242 / MODEL.md:48 ("amino acid tokens only").

3. **`temperature=0.0` → uncaught 500 — REAL.** `schema.py:62-67` `ge=0.0` admits 0.0; `generate()` always sets `do_sample=True` (`app.py:245`) and passes `temperature` (`app.py:240`). transformers `TemperatureLogitsWarper` raises `ValueError` for temperature≤0; raw `ValueError` is absent from `ERROR_MAP` (`decorator.py:417-430`) so it falls through to the 500 "Uncaught exception" branch (`decorator.py:454-462`), not a clean 422. README.md:64 advertises "0.0-2.0".

4. **`embedding` (singular) deviates from repo-wide `embeddings` — REFUTED.** The "only model" / "repo-wide plural" claim is false: `clean/schema.py:144` (`CLEANEncodeResult.embedding`) and `dnabert2/schema.py:79` (`DNABERT2EncodeResponseResult.embedding`) both use a flat top-level singular `embedding: list[float]` for the pooled vector, identical to `zymctrl/schema.py:205`. dsm uses plural, but the convention is genuinely mixed — there is no uniform repo-wide `embeddings`.

5. **Fixture hardcodes a shared-asset sequence — REAL (nuance).** `fixture.py:73` hardcodes a string that is exactly the first 43 chars of `STANDARD_PROTEIN_STABILITY` (`shared_assets.py:29-30`; remainder `AYLRSLGYNIVATPRGYVLAGG`), and zymctrl/fixture.py does not import `shared_assets` while peers (dsm, esmc, e1, esm1b, temberture, esmstabp) do. Nuance: it's a truncated *prefix*, not the literal full asset, so not a byte-for-byte duplicate — but it is exactly the W12 drift the shared library exists to prevent.

6. **Internal `qa` env name in shipped docstring — REAL (systemic, minor).** `app.py:363` comment names "qa"; identical comment at `esm2/app.py:484`. Note "qa" is also functional shipped code in `deployment.py:41` (`if current_env in ("qa", "main")`) and the `--force-deploy` help text (`deployment.py:35`), so it's a systemic repo-wide reference, not zymctrl-specific, and the "leak" framing is debatable since removing the comment leaves qa in the deploy logic.
