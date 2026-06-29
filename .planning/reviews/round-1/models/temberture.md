# Review — `models/temberture/` (Round 1)

## Summary

TemBERTure is a two-variant (classifier, regression) adapter-tuned ProtBERT model exposing `encode` +
`predict`. The plumbing is broadly on-pattern: `ModelMixinSnap`, `@biolm_model_class`, `parse_variant`,
GPU memory snapshots, lazy fixtures, a `TestSuite` with integration + deployment cases, the full 5-file
knowledge graph, field-level `Field(description=...)` that renders in `model_json_schema()`, and reuse of
the shared `STANDARD_PROTEIN_STABILITY` asset. No internal-reference leakage (`biolm-modal`, `.planning`,
`qa`) was found in shipped files. Inference logic is correct and matches the schema descriptions.

Two launch-gating defects: (1) a **build-order bug** — the base-model HuggingFace fallback imports
`huggingface_hub` at download-layer build time, but `setup_download_layer(...)` is called without
`extra_pip_packages`, so a cold/empty-R2 build cannot self-populate (the exact A7 build-order rule, which
every sibling honors); and (2) a **licensing/attribution error** — the per-model `LICENSE` carries a
copyright holder ("ibmm-unibe-ch contributors") that does not match the upstream MIT notice ("Institute of
Biochemistry and Molecular Medicine", verified live). The rest are convention/consistency and
documentation-completeness issues: hand-rolled acquisition where canonical wrappers now exist, an
overloaded `prediction` output field that diverges from siblings `esmstabp`/`tempro`, shipped `TODO`
scaffolding, a `BIOLOGY.md`/`sources.yaml` contradiction, an undocumented base-model license, and a
wrong DOI.

---

## 🔴 Must-fix before launch

### 1. `huggingface_hub` missing from the download layer (build-order rule violated)
- **Category:** Acquisition (Rubric A7)
- **Location:** `models/temberture/app.py:52-57`
- **Detail:** The base-model fallback in `download.py:_download_shared_base_model` uses
  `AcquisitionStrategy.HUGGINGFACE_HUB`, which lazily runs `from huggingface_hub import snapshot_download`
  (`models/commons/storage/downloads.py:457`) **during the download-layer image build**
  (`run_function`). But `setup_download_layer(...)` is called with **no** `extra_pip_packages`, so that
  layer installs only `boto3/pydantic/requests` (`models/commons/modal/downloader.py:75-83`).
  `huggingface_hub==0.16.4` is installed only in a *later* runtime layer (`app.py:68`), which does not
  exist yet when the download runs. With a populated R2 the R2 primary succeeds and HF is never imported,
  so this is masked today; on a cold/empty bucket (a fresh fork or first deploy) the fallback crashes
  with `ModuleNotFoundError: No module named 'huggingface_hub'`, breaking the self-population the repo
  guarantees. Every sibling relying on the HF fallback passes it explicitly — `esm1b`, `esm1v`, `igbert`,
  `abodybuilder3`, `spurs`, `prostt5`, `igt5` all do `extra_pip_packages=["huggingface_hub==..."]`; esm2
  does the analogous thing for `fair-esm`. One-line fix, but it gates reproducible bootstrap.
- **Suggested fix:** Add `extra_pip_packages=["huggingface_hub==0.16.4"]` to the `setup_download_layer(...)`
  call (matching the pinned runtime version). Folding the acquisition into the canonical `r2_then_hf`
  wrapper (finding #4) handles this for you.

### 2. LICENSE copyright holder does not match upstream (MIT attribution violation)
- **Category:** Licensing (Rubric A8)
- **Location:** `models/temberture/LICENSE:3`
- **Detail:** The file reads `Copyright (c) 2024 ibmm-unibe-ch contributors` — a holder synthesized from
  the GitHub org slug + "contributors". The actual upstream notice (`LICENSE.md` at
  https://github.com/ibmm-unibe-ch/TemBERTure, verified) is `Copyright (c) 2024 Institute of Biochemistry
  and Molecular Medicine`. MIT's sole obligation is to reproduce the original copyright notice verbatim, so
  an altered holder is a genuine compliance defect. Every other MIT sibling copies the real holder
  verbatim (`esmstabp` → "Marcus Ramos", `tempro` → "Jerome Anthony E. Alvarez", `esm2` → "Meta Platforms,
  Inc. and affiliates."); temberture is the lone anomaly. The year (2024) is correct.
- **Suggested fix:** Replace line 3 with `Copyright (c) 2024 Institute of Biochemistry and Molecular
  Medicine`. Optionally point `sources.yaml: license.url` at the upstream `LICENSE.md`.

---

## 🟠 Should-fix

### 3. `prediction` output overloads two semantics and diverges from the Tm siblings
- **Category:** Schema field naming / cross-model consistency (Rubric A3 / C)
- **Location:** `models/temberture/schema.py:136-143` (and `app.py:402-417`)
- **Detail:** `prediction: float` means a 0–1 thermophilicity probability in classifier mode but a Celsius
  melting temperature in regression mode — two different units/ranges under one field and one description.
  The other two thermostability models name the same Tm scalar differently: `esmstabp` →
  `melting_temperature: float` (+ `is_thermophilic: bool`, `models/esmstabp/schema.py:71-78`); `tempro` →
  `tm: float` (`models/tempro/schema.py:63`). So the platform exposes the same output (predicted Tm) under
  three different names, and temberture's `classification: str` ("Thermophilic"/"Non-thermophilic")
  mirrors `esmstabp.is_thermophilic` with a different name and type. This is precisely the
  "plumbing-not-science" divergence the north star forbids.
- **Suggested fix:** Adopt a canonical Tm field for the regression variant (align with `esmstabp`'s
  `melting_temperature`) and stop overloading one field across variants; converge the thermophilic flag
  representation (label vs boolean) across the three siblings. Keep a Pydantic alias if renaming a public
  field. (Cross-model decision — flag to the global reviewer.)

### 4. Hand-rolled acquisition where canonical wrappers now exist
- **Category:** Acquisition / duplication (Rubric A7 / B)
- **Location:** `models/temberture/download.py:56-238`
- **Detail:** `download.py` reimplements two standard flows with raw `AcquisitionConfig` +
  `download_with_fallback`: an R2→HuggingFace base-model fetch (`_download_shared_base_model`) and an
  R2→GitHub-archive-subtree adapter fetch (`_download_temberture_archive` / `_extract_temberture_adapters`).
  `models/commons/storage/download_helpers.py` now provides `r2_then_hf(...)` (line 390) and
  `r2_then_archive(...)` (line 574), and the latter's docstring **explicitly names temberture** (line 596)
  as carrying the inline "download zip → unzip subtree" logic it is meant to replace. Adopting `r2_then_hf`
  also resolves finding #1. This is a catalog-wide pending migration (several models still hand-roll), so
  the orchestrator may want to dedupe across the fan-out.
- **Suggested fix:** Replace `_download_shared_base_model` with `r2_then_hf(...)` (passing the pinned
  `hf_repo_id`/`hf_revision`, `model_variant="shared"`, `sub_path="base_model"`) and
  `_download_variant_adapters` with `r2_then_archive(...)` + a variant filter, collapsing most of the file.

### 5. Shipped `TODO` scaffolding in public knowledge-graph docs
- **Category:** Knowledge graph / OSS readiness (Rubric A9 / C)
- **Location:** `models/temberture/README.md:150`, `MODEL.md:22`, `MODEL.md:39`, `BIOLOGY.md:41`
- **Detail:** Four `<!-- TODO: ... -->` comments (the dummy template's TODO format) ship in public docs —
  "Extract benchmark numbers ... requires PDF access", "Extract training dataset details", "Extract
  benchmark results", "Search for papers citing TemBERTure". As a result the "Published Results" /
  "Published Benchmarks" / "Training Data" sections carry no actual numbers.
- **Suggested fix:** Extract the benchmark/training numbers from the primary paper and fill the sections
  (this depends on #8), or remove the TODO scaffolding and state plainly what is/isn't available.

### 6. `BIOLOGY.md` contradicts `sources.yaml` on applied literature
- **Category:** Knowledge graph consistency (Rubric A9)
- **Location:** `models/temberture/BIOLOGY.md:39-41` vs `models/temberture/sources.yaml:40-95`
- **Detail:** BIOLOGY.md states "No applied literature entries have been catalogued yet" (plus a TODO),
  but `sources.yaml` lists five `applied_literature` entries (ESMStabP, the WIREs review, iCASE, the
  ChemBioChem review, TemStaPro). The two files disagree about whether applied literature exists.
- **Suggested fix:** Populate BIOLOGY.md "Applied Use Cases" from the five `sources.yaml` entries and drop
  the contradicting TODO.

### 7. Base-model (ProtBERT-BFD) license undocumented
- **Category:** Licensing (Rubric A8)
- **Location:** `models/temberture/sources.yaml:35-39`, `LICENSE`, `README.md:188-190`
- **Detail:** The container bundles ProtBERT-BFD (`Rostlab/prot_bert_bfd`) weights as the base model, but
  LICENSE and README cover only the TemBERTure code (MIT) and `sources.yaml` records the HF repo with no
  license. The HF model card states no explicit license, so the redistribution terms of the bundled
  weights are unverified.
- **Suggested fix:** Determine ProtBERT-BFD's license/attribution and document it (sources.yaml + README
  License section); if it cannot be confirmed, flag it explicitly rather than shipping silently.

### 8. Primary paper / base-model knowledge graph left unpopulated, and wrong TemStaPro DOI
- **Category:** Knowledge graph completeness/accuracy (Rubric A9)
- **Location:** `models/temberture/sources.yaml:16-39` and `sources.yaml:42`
- **Detail:** The single `primary_papers` entry has `arxiv: ''`, `pdf_r2: pending`, `md_r2: pending`, and
  the HuggingFace base-model `snapshot_r2: pending` — the primary source was never ingested, which is why
  the doc benchmark sections (#5) are empty. (`pending` is an accepted sentinel for `applied_literature`
  PDFs — esm2 uses it there too — but esm2's *primary* papers carry real `pdf_r2`/`md_r2` paths.)
  Separately, the TemStaPro `applied_literature` entry reuses TemBERTure's own DOI
  `10.1093/bioinformatics/btae157` (identical to the primary paper at line 19) — copy-paste error;
  TemStaPro has a different DOI.
- **Suggested fix:** Ingest the primary paper to R2 and fill the pointers (unblocks #5); correct the
  TemStaPro DOI.

---

## 🟡 Nits

### 9. `OutputModality.LOGITS` tag is not actually produced
- **Category:** Config / tag accuracy (Rubric A1)
- **Location:** `models/temberture/config.py:57`
- **Detail:** `output_modality` lists `LOGITS`, but no action returns a `logits` field — `encode` returns
  embeddings; `predict` returns a post-sigmoid probability (or Tm) plus a class label. The raw logit is
  consumed internally (`app.py:397`) and never surfaced. `EMBEDDING`/`SCALAR`/`CLASS_LABEL` map cleanly.
- **Suggested fix:** Drop `OutputModality.LOGITS` from the tag list.

### 10. f-string logging breaks the lazy-`%` house style; hardcoded variant literal
- **Category:** Logging / readability (Rubric A6 / B)
- **Location:** `models/temberture/app.py:413,415` (and `:404`)
- **Detail:** Lines 413/415 use `logger.info(f"Sequence {j+1}: ...")` while every other call in the file
  uses lazy `%`-args; not caught by ruff (the `G` ruleset isn't selected), so it's a style inconsistency.
  Line 404 compares `self.model_type == "classifier"` with a string literal instead of
  `TemBERTureModelTypes.CLASSIFIER` (the enum used at `app.py:126`).
- **Suggested fix:** `logger.info("Sequence %s: %s (prob: %.4f)", j + 1, classification, prob)` etc., and
  use the enum member.

### 11. Mutable-instance default instead of `default_factory`
- **Category:** Schema / convention (Rubric B)
- **Location:** `models/temberture/schema.py:62-66`
- **Detail:** `params: ... = Field(default=TemBERTureEncodeRequestParams(), ...)` uses a shared model
  instance as the default; esm2 uses `default_factory`. Pydantic v2 deep-copies model defaults so it is
  not a shared-mutable bug, but it diverges from the house pattern.
- **Suggested fix:** Use `default_factory=TemBERTureEncodeRequestParams`.

### 12. Cross-file metric inconsistency (ESMStabP R²)
- **Category:** Knowledge graph consistency (Rubric A9)
- **Location:** `models/temberture/comparison.yaml:18,32,41` vs `sources.yaml:77`
- **Detail:** `comparison.yaml` cites ESMStabP R² = 0.94 (three places); `sources.yaml:77` says
  "R2 = 0.95, PCC = 0.97".
- **Suggested fix:** Reconcile to one sourced value.

### 13. Heavy base image then torch downgrade (build bloat)
- **Category:** Image build / efficiency (Rubric B)
- **Location:** `models/temberture/app.py:48,62-69`
- **Detail:** The image starts from `pytorch/pytorch:2.6.0-cuda12.4` (torch 2.6.0) then
  `uv_pip_install("torch==2.0.1", ...)` to satisfy `adapters==0.1.1`, installing torch twice. Functionally
  fine (the 2.0.1 wheel bundles its own CUDA libs), but wasteful; low priority since the old stack is
  genuinely required by the science.
- **Suggested fix:** Optionally start from a slimmer/torch-2.0.1-matching CUDA base.

### 14. `per_residue_embeddings`/`cls_embeddings` spelling vs glossary
- **Category:** Field naming consistency (Rubric A4)
- **Location:** `models/temberture/schema.py:120-127`
- **Detail:** `tooling/field_glossary.yaml` pins `per_token_embeddings`/`residue_embeddings`; temberture
  uses `per_residue_embeddings` + `cls_embeddings`. These aren't glossary-pinned keys (no CI failure) and
  `dsm` uses the same two names, so it's a catalog-wide drift, not a temberture-specific defect. Noted for
  the global reviewer.
- **Suggested fix:** No per-model change required; consider converging the catalog on one spelling.

---

## D. Definition-of-Done audit (per-model view)

- **Standard layout (app/config/schema/test/download + 5-file KG):** Met.
- **Closed-set actions, intent-matched:** Met (`encode`, `predict`).
- **Field descriptions render in `model_json_schema()`:** Met (all `Optional` fields use field-level
  `Field`, not `Optional[Annotated[...]]`; encode `model_config` matches the esm2 house pattern).
- **Typed errors / no print / structured logging:** Mostly met (no `print`; generic `except` re-raises with
  `exc_info`; minor lazy-`%` slip #10). Exceptions propagate rather than mapping to `UserError`/
  `ServerError`, consistent with esm2.
- **Acquisition self-populates public bucket / build-order honored:** **NOT met** (#1); also hand-rolled
  rather than canonical (#4).
- **Per-model LICENSE permissive + consistent with sources.yaml + attribution honored:** **NOT met**
  (#2 holder mismatch; #7 base-model license undocumented).
- **Knowledge graph accurate/consistent/complete:** **Partially met** — shipped TODOs (#5), internal
  contradiction (#6), unpopulated primary source + wrong DOI (#8), metric drift (#12).
- **Tests: TestSuite + integration + deployment, lazy fixtures, shared assets:** Met (reuses
  `STANDARD_PROTEIN_STABILITY`; no module-scope network I/O).
- **No internal-reference leakage:** Met.
