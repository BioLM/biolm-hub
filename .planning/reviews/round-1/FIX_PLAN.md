# Round 1 — Prioritized Fix Plan

De-duplicated, themed plan for every finding that survived verification. **Refuted findings are
dropped** (see `README.md` §1 for the list). Test-placeholder targets (`ablang2`, `dummy`,
`prostt5`, `rf3`, `gateway`, `test/test`) are excluded.

**Legend** — Effort: S (<1h) · M (a few hrs) · L (a day+). Tags:
`[agent: Modal-free]` fully fixable + verifiable without Modal · `[needs-Modal]` requires a live
deploy/inference to verify · `[needs-human]` requires a maintainer decision (licensing, copyright,
policy). "Edit Modal-free; verify needs-Modal" is called out where the code change is safe but
behavior must be confirmed on a deploy.

---

# 🔴 LAUNCH-BLOCKERS (do first)

## L1. De-internalize `biolm-modal` everywhere [needs-human decision on `qa`→env name; rest agent: Modal-free] — Effort M
**What:** Remove the internal bucket/repo name `biolm-modal` from all shipped files. One occurrence
is a *functional* bug, not just a leak.
**Where (all `real`):**
- `models/esmstabp/_train.py:72` (`R2_BUCKET = "biolm-modal"`, also `:74,:307`) — **also breaks
  self-population**: `download.py:8` reads from `biolm-public`, so weights upload to a bucket the
  model never reads. (security 🔴, esmstabp 🔴)
- `models/esmstabp/download.py:8`
- `models/deepviscosity/fixture.py:18` (🔴)
- `models/boltz/fixture.py:16`, `models/boltz/test.py:112,138` (🔴)
- `models/commons/storage/cache.py:48` (comment; also factually wrong) (commons 🔴)
- `models/dummy/sources.yaml:106` — **template; propagates to every new model** (oss-readiness 🔴)
**Note:** First-pass sweep, then `grep -rn "biolm-modal" models/ cli/ gateway/ docs/` to confirm zero.

## L2. De-internalize the Modal env name `qa` (and fix that it's now stale) [needs-human: choose canonical env name; agent: Modal-free to apply] — Effort M
**What:** `qa` leaks across commons + ~30 model `app.py` deploy comments AND is *functionally
stale*: CI was migrated to `biolm-models-dev` but the code wasn't, so `is_production()`/env checks no
longer recognize the real deploy env.
**Where (real):** `models/commons/util/config.py:82` (hardcoded `("qa","main")`),
`models/commons/util/environment.py:115,140`, `models/commons/modal/deployment.py:35,41`, and the
`# Force deploy to "qa" or "main" environment:` comment in ~30 model `app.py` (e.g.
`esm2:484`, `igbert:427`, `zymctrl:363`, `abodybuilder3:287`, `boltz:1044`, `evo:223`).
**Verify:** redeploy at least one model after the env rename. *(edit Modal-free; verify needs-Modal)*

## L3. Remove "BioLM-Modal" from the `bm` CLI front-door help [agent: Modal-free] — Effort S
**What:** Internal product name in user-facing help; contradicts the public package name `biolm-models`.
**Where (real):** `cli/main.py:16,18,47` (module docstring is also placed after imports → dead string; fix both). (cli 🔴, oss-readiness)

## L4. Licensing inclusion-gate decisions [needs-human] — Effort M (decision) + S–L (apply)
Each may **remove the model from the catalog** or require relicensing. Escalate to the model-inclusion owner.
- `models/clean` — upstream CLEAN ships a **Non-Exclusive Research Use License** (non-commercial),
  but LICENSE/sources.yaml/README assert BSD-3 and link a 404 path. (clean 🔴, `real`)
- `models/peptides` — dependency `peptides==0.3.4` is althonos/peptides.py declaring `__license__ =
  "GPLv3"` (possible copyleft); model ships Apache-2.0 attributed to the wrong author. (peptides 🔴)
- `models/tempro` — upstream repo has **no license**; model fabricates MIT and **redistributes
  unlicensed weights** (`user.zip`). (tempro 🔴)

## L5. License correctness (copyright holder/year + reviewer notes) [needs-human verify; agent: Modal-free to apply] — Effort M
**What:** Fix wrong/placeholder copyright and strip "confirm before release" notes that must not ship.
**Where (real):**
- `models/mpnn/LICENSE:3,29-30` — wrong year (2023 vs upstream 2024) + pre-release note (🔴)
- `models/thermompnn_d/LICENSE:3` — misattributes upstream MIT holder ("Henry Dieckhaus"→"Kuhlman Lab"), an MIT-compliance violation (🔴)
- `models/biotite/LICENSE:3,38-39` — unverified copyright + confirm note (🔴)
- 🟠 reviewer-note / inferred-copyright cleanup (same fix class): `boltz`, `boltzgen`, `chai1`,
  `evo`, `immunefold`, `omni_dna`, `pro1`, `rfd3`, `dnabert2` LICENSE/NOTICE files.

## L6. Acquisition build-order: move `huggingface_hub` into the download layer (A.7) [agent: Modal-free edit; verify needs-Modal] — Effort S each
**What:** HF fallback runs at build time in the download layer, but the dep is installed only in the
later runtime layer → cold/empty-R2 self-population build fails with `ImportError`. Pass it via
`setup_download_layer(extra_pip_packages=[...])` like the 11 sibling HF models do.
**Where (real):** `models/esmc/app.py:55-69` (🔴), `models/zymctrl/app.py:43-56` (🔴),
`models/evo2/app.py:57-83` (🔴), `models/temberture/app.py:52-68` (deps-build), and the related
`models/spurs/app.py:47-59` (ESM2 download layer omits `fair-esm`).

## L7. Broken public contracts — documented inputs/outputs that crash or lie [mostly agent: Modal-free; some verify needs-Modal] — Effort S–M each
- `models/dna_chisel` — `restriction_enzymes=None` (the documented disable path) → unhandled
  `TypeError`/HTTP 500. `app.py:154-169,407-410`. **S** `[agent: Modal-free]`
- `models/dsm` — `generate` silently ignores `max_length`/`top_k`/`top_p` (never forwarded to
  `mask_diffusion_generate`); empty-string "unconditional" yields empty output. `app.py:557-662`.
  **M** *(edit Modal-free; verify needs-Modal)*
- `models/esmfold` — pLDDT returned 0–100 but schema/docs declare 0–1; "filter >0.7" guidance is
  meaningless. Fix scale or docs across `schema.py:64-65` + 5 KG files. **M** `[needs-human: choose 0–1 vs 0–100]`
- `models/rfd3` — `symmetry`, `cyclic_chains`, `conditioning_mode`, `output_format`,
  `smiles`/`ccd_code`, `bonds` accepted by schema but never reach the engine
  (`_create_design_specification`). Either wire them or remove from schema/docs/tests. `app.py:494-633`. **L** `[needs-human: wire vs remove scope]`
- `models/boltz` — `msa_search` depends on the EXCLUDED `msa_search_nim` (absent; leaks closed-NIM
  ref). Remove the feature/field or document+gate it off. `schema.py:37-49,123-130`,
  `app.py:130-140,262,307`. **M** `[needs-human: drop feature?]`

## L8. CI / tooling red on a clean tree [agent: Modal-free] — Effort S–M
- `cli/test_kb.py` — 14 unit tests fail (`typer.Exit` vs `click.exceptions.Exit`); collected by the
  safe CI tier, so DoD #1 "green from clean clone" is false. **S** (dod-audit 🔴)
- `cli/kb.py:360` — `bm kb matrix` imports `models.scripts.generate_comparison_matrix`, which never
  existed → `ModuleNotFoundError` on first use. Implement or remove the command. **S** (cli 🔴)
- `models/commons/testing/comparator.py:177-186` — `cosine_distance_threshold` is silently
  overridden by the final `rel_tol` gate, so the ~2% tolerance ~15 models rely on is inert. **M**
  (testing 🔴) *(edit Modal-free; re-run golden comparisons to confirm)*

## L9. Remove the dead billing/auth/analytics schema from the gateway [agent: Modal-free] — Effort S
**What:** `gateway/schemas/introspection.py` still defines `BillingState`, `monthly_charges`,
`bypass_billing`, `institute_id`, `can_access_api` — contradicts the W8 "auth/billing stripped"
claim and DoD #11. The file is unimported (dead). Delete it (and confirm no importers). (dod-audit 🔴, `real`)

---

# 🟠 SHOULD-FIX (grouped by theme)

## S1. Remaining internal-reference leaks [agent: Modal-free] — Effort M (batch)
- "BioLM platform layer / Redis two-tier caching" described in **63 MODEL.md/README.md** files,
  originating from `models/dummy/MODEL.md:252` + `models/dummy/README.md:234`; renders into public
  docs. Fix the template, then regenerate/sweep. (security, dod-audit)
- `models/commons/data/serializer.py:126,169` — "Django host" / `training.*` internal-stack refs.
- `models/commons/core/decorator.py:435` + `.github/scripts/analyze_commons_dependencies.py:94` —
  stale `biolm_modal_function`/`biolm_modal_endpoint` names.
- `models/commons/util/config.py:71-72,77-78` — dead internal-named Modal secrets
  (`protocols-r2-bkt`, `ngc-cli-api-key`).
- `models/commons/modal/source.py:76-141` — dead `setup_workflow_source_layer` leaks workflow slugs.
- `.github/workflows/ci.yml:5` — internal `W11` workstream reference.
- `models/pro1/config.py:78` (`W8` comment), `models/pro1/sources.yaml:84-85` (internal authoring skill).

## S2. Apply the error taxonomy uniformly (W7) [agent: Modal-free] — Effort L (systemic)
- **System-error branch is dead.** ~21 inference paths use bare `raise e` → generic
  "Uncaught exception" 500 with `code=null` and raw exception text in the body. Replace with typed
  `ServerError`/`ModelExecutionError` (and use idiomatic bare `raise`). Sites:
  `esm2:167,191`, `esm1v:136,175`, `esm1b:146,168`, `igbert:189`, `igt5:165`,
  `msa_transformer:201`, `progen2:188,202`, `sadie:102`, `temberture:222,251`, `tempro:243`,
  `prostt5:380`, `immunebuilder:265,352`, `abodybuilder3:242`, `antifold:209`. (errors-logging)
- **`ServerError` base missing from `ERROR_MAP`** → a raised `ServerError` is reported as a bug.
  `models/commons/core/decorator.py:417-430`. **S**
- **`UnsupportedOptionError`/`ResourceNotFoundError` wired but never raised**; their natural sites
  use bare exceptions: `boltz:453`, `abodybuilder3:171`, `immunebuilder:85,199`, `dsm:234`,
  `prostt5:175,218`. (errors-logging) **M**
- **Caller mistakes → 500 instead of 400** (raise `ValidationError400`): `esm_if1`
  (`app.py:162`, `_sample_sequences.py:133,138,147`), `prody` (~12 sites in `utils.py`),
  `thermompnn` (`util.py:171,199-206`), `thermompnn_d` (`util.py:171,239,333,478`), `sadie`
  (`app.py:122-128` blanket except), `immunebuilder` (`app.py:350-352`), `deepviscosity`
  (`util.py:261-310`). **M**
- **CUDA-OOM swallowed → fake 200 success**: `esm_if1:187-198`, `esmfold:174-186`. **S**
- **`boltz` misclassifies internal weights-dir fault as 400 and leaks container path**:
  `models/boltz/app.py:571`. **S**
- **Core modules bypass `get_logger`** (W6 "one logger"): `commons/core/caching.py:19`,
  `commons/data/serializer.py:13`, `thermompnn_d/util.py:19`. **S**

## S3. Knowledge-graph hygiene — dangling comparison.yaml slugs [agent: Modal-free] — Effort M (batch)
**What:** `comparison.yaml` references models not in the catalog; `evo` actually fails
`bm kb validate evo` (exit 1). Remove/redirect each dangling ref and add a `bm kb validate --all`
gate.
**Where (real):** `nt` → dna_chisel, dnabert2, **evo (🔴)**, evo2, omni_dna; `af2_nim` → boltz,
chai1; `propermab`/`ablef` → abodybuilder3, immunefold (also propermab is EXCLUDED), immunebuilder;
`gemme`/`camsol`/`diamond` → clean, thermompnn, thermompnn_d, spurs; `poet`/`saprot` → msa_transformer;
`pro4s` → spurs; `nanobert`/`biolmtox2` → immunebuilder.

## S4. Knowledge-graph hygiene — TODO/pending residue + applied-lit contradictions [agent: Modal-free] — Effort M (batch)
- Shipped `<!-- TODO -->`/placeholder text in docs: abodybuilder3, antifold, boltz, boltzgen, chai1,
  deepviscosity, dnabert2, esm1v, esm2, evo, evo2, igbert, immunebuilder, immunefold, omni_dna,
  **progen2 (🔴 — two leak the `qa` env)**, rfd3, spurs, tempro, thermompnn, thermompnn_d, pro1.
- `BIOLOGY.md` "applied literature pending/none" contradicting populated `sources.yaml`: dnabert2,
  esm1v, tempro, thermompnn, thermompnn_d, antifold, e1.
- `boltzgen` — verify the `pending` placeholders + `<!-- TODO -->` (`sources.yaml`, `MODEL.md:34`);
  malformed `arxiv` (bioRxiv DOI). *(verdicts `unverified` — confirm then fix.)*

## S5. Cross-model schema-field uniformity (A.3) [agent: Modal-free; verify needs-Modal for response shapes] — Effort M
- **Confidence field naming:** `esmfold` `mean_plddt`, `immunefold` `full_plddt` vs the house
  `plddt`. Pick one. (esmfold, immunefold)
- **Melting-temperature field:** `esmstabp` `melting_temperature`, `tempro` `tm`, `temberture`
  `prediction` — same quantity, three names. (esmstabp, tempro)
- **Response DTOs inherit `RequestModel` (extra=forbid)** instead of `ResponseModel`: `esm_if1:82`,
  `mpnn:626,665`, `progen2:96`, `esm2` (yellow), `igt5`/`igbert` nested. Fragile if upstream adds keys.
- **Divergent response shapes:** `esm1v` predict (raw HF fill-mask vs house logits shape),
  `omni_dna` encode (length-1 list-of-objects wrapper). *(verify needs-Modal)*
- **Embeddings include special/pad rows, batch-padding-dependent length:** `igbert:220-246`,
  `igt5:187-207` (diverges from esm2). *(verify needs-Modal)*
- **`antifold` `nanobody_chain_id`** violates the ratified "nanobody = lone heavy_chain + tag"
  standard and is redundant with `heavy_chain_id`. Remove. `schema.py:158-162`, `app.py:182-206`.

## S6. Per-model correctness (schema/runtime) [mixed] — Effort S–M each
- `models/abodybuilder3` — pLDDT response type `list[list[float]]` vs `squeeze(0).tolist()`;
  required chains typed `str` but `Field(None)` (silently optional → 500 on omission instead of 422).
  `schema.py:69-126`, `app.py:236`. **M** *(verify needs-Modal for plddt=True path)*
- `models/progen2` & `models/zymctrl` — `temperature` lower bound `ge=0.0` crashes under
  `do_sample=True`. Raise bound to `gt=0`. `progen2/schema.py:36-41`, `zymctrl/schema.py:62-67`. **S**
- `models/zymctrl` — perplexity computed over `<end>`/EOS/padding for `num_samples>1`, contradicting
  amino-acids-only docs and distorting the sort. `app.py:104-130`. **M**
- `models/progen2` — vocab size doc wrong (50,400 vs real 32; contradicts its own download.py).
  README/MODEL. **S**
- `models/evo` — `generated` field desc wrongly claims output includes the prompt (Evo returns
  continuation-only). `schema.py:137-139`, README. **S**
- `models/mpnn` — docs claim 128 MB/0.125 cores; config specs 3 GB/1 CPU. Residue-position
  validation `1<=n<=residue_count` mis-handles non-1-indexed PDBs. Internal plumbing params leak
  into the public request schema; dead variant-request classes. `config.py:33-37`, `schema.py`. **M**
- `models/omni_dna` — `from_config` + `load_state_dict(strict=False)` risks silent weight-drop
  (goldens can't catch it). Use `from_pretrained` like dnabert2. `app.py:131-141`. **M** *(verify needs-Modal)*
- `models/chai1` — pre-cache ESM embedding weights so default `use_esm_embeddings=True` doesn't
  download from HF at first inference. `download.py:85,132-137`. **M** `[needs-Modal]`
- `models/clean` — `max_predictions` range 1–20 dead above the algorithm's hard cap of 5; pin
  `split100.csv` (currently unpinned `main`). `schema.py:30-35`, `download.py:26-28`. **S**
- `models/thermompnn` / `thermompnn_d` — mutation positions documented as 1-indexed PDB numbering
  but code uses contiguous chain-sequence indices (silent mis-targeting); wildtype letters
  unchecked. `thermompnn/util.py:208-214`, `thermompnn_d/util.py`. **M** *(verify needs-Modal)*
- `models/thermompnn_d` — targeted double-mutation requests compute the full pairwise landscape then
  filter (O(N²·400), timeout/OOM risk). `util.py:283-285,396-407`. **M**
- `models/esm1b` — `vocab_tokens` includes non-canonical codes (X/B/U/Z/O → 25 cols vs esm2's 20),
  breaking uniformity + log_prob normalization + docs. `app.py:112-116`. **M**
- `models/dnabert2` — advertised 4–8 kbp context unreachable (2048-char schema cap); align docs or cap. **S**
- `models/rfd3` — `input_structure_path` exposes server-side file reads to remote callers (security
  smell). `schema.py:154-157`, `app.py:287-316`. **M** *(verify)*

## S7. Acquisition / downloader uniformity [agent: Modal-free; verify needs-Modal] — Effort M
Replace hand-rolled downloaders with the canonical commons helpers (`r2_then_archive`/`r2_then_hf`):
`deepviscosity` (243 lines), `evo2` (~140 lines, verdict `uncertain` — confirm), `rfd3` (duplicated
R2 caching), `clean` (bespoke), `boltzgen` (hand-rolled AcquisitionConfig). Also `models/pro1` —
migrate off the deprecated `acquire_library_managed_model` to `r2_then_library(cache_to_r2=False)`
(pro1 is the named removal blocker). `pro1/download.py:94-105`.

## S8. Docs accuracy — citations, versions, base images, action names [agent: Modal-free] — Effort M (batch)
- **Wrong citations / factual errors:** esm2 (RoPE not Learned; corrupted authors; two arXiv IDs),
  dsm (BibTeX), esmstabp (paper title), omni_dna (fabricated title), tempro (citation), e1
  ("Encrypted"→"Encoder"), igbert/igt5 (arXiv/year), evo (arXiv link, Durber→Durrant), esmc (blog
  title), sadie/spurs/peptides (fabricated acronyms / `557` feature count).
- **Wrong base image / dep versions:** antifold (CUDA vs CPU debian_slim), chai1 (torch 2.3.1 vs
  2.6.0), clean (base image), omni_dna (base image), esmstabp (numpy), abodybuilder3 (Python 3.9 vs 3.10).
- **Action named `predict` for non-predict actions:** esmfold/boltz/chai1 (docs say `predict`,
  action is `fold`), dsm (stale `predict`), dna_chisel (schema classes named `...Predict...` for
  `encode`).
- **Log_prob description wording:** evo2 uses masked-LM "Pseudo-log-likelihood" though it's
  autoregressive (`schema.py:211-214`); esm2/esm1b/esm1v family wording imprecise.

## S9. Dead code / simplicity [agent: Modal-free] — Effort M (batch)
- `models/commons/parquet_utils.py` — dead, un-importable (`from .utils import` broken). Delete.
- `models/commons/storage/acquisition.py:118-119,181-182` — dead/legacy surface with internal provenance.
- `models/commons/core/decorator.py:29-100` — suppressed-complexity FIXMEs + `[Temporary]` SDK hack;
  `caching.py:75` cache heuristic hardcodes pre-rename `heavy`/`light` (should be `heavy_chain`/`light_chain`).
- `antifold` (3 unused schema classes), `mpnn` (dead variant classes `schema.py:553-618`), `esm_if1`
  (dead scaffolding `_sample_sequences.py:53-106`), `abodybuilder3` (dup `VARIANT_RESOURCE_SPECS`),
  `prody` (dead `InteractionType` enum + dead `compute_all_interactions` param + double-parse),
  `dna_chisel`, `spurs` (`util.py:73-82,173`).
- `.github/scripts/analyze_commons_dependencies.py` — symbol-level analysis (~300 lines) always
  degrades to module granularity; collapse to the module-match. (cicd)

## S10. Convention deviations [agent: Modal-free] — Effort S–M
- `models/dna_chisel/app.py:56` — subclasses `ModelMixin` instead of `ModelMixinSnap` (lone outlier).
- `models/abodybuilder3` & `models/immunebuilder` — `seed_everything` copy-pasted; lift to commons.
- `models/esm2/app.py:64` — unused heavyweight `sentence-transformers` dep (unique to esm2); remove.
- `models/esm2/test_schema_strictness.py` — exists only for esm2; either generalize or remove the inconsistency.
- `models/commons/modal/downloader.py:77-81` — loose `pydantic`/`requests` pins violate exact-pin rule.

## S11. Logging consistency (W6) [agent: Modal-free] — Effort S
- `models/tempro/app.py` — 14 emoji log lines (uniformity outlier); de-emoji. Also commons
  `storage/acquisition.py` pervasive emoji.
- `models/spurs/app.py:185-194` — input sequences logged at INFO (deviates from esm2/dummy).
- `models/sadie/app.py:128` — error detail echoes full input sequence.

## S12. CI/CD hardening [agent: Modal-free; some needs-human policy] — Effort M
- Label gate trusts GitHub **triage** role; make environment required-reviewers **enforced** not
  recommended. `.github/workflows/deploy.yml:93,124-129`. `[needs-human policy]`
- CI scripts silently escape strict mypy (excluded dotted `.github` dir hides 20 violations);
  include them. `ci.yml:38`.
- `detect_models.py:61-66` — default mode treats a commons docs-only change as triggering ALL models
  (cost). Align with the conservative path.
- Add a **secret-scanning gate** (gitleaks/trufflehog) to CI/pre-commit (W-sec DoD). (security)

## S13. CLI polish [agent: Modal-free] — Effort M
- `bm kb missing` references non-existent `kb_acquire.py` and exposes an internal curation workflow
  external users can't act on (read-only bucket). `cli/kb.py:436`.
- `bm r2 cat` decodes each 1 MB chunk independently → corrupts multi-byte UTF-8 at boundaries.
  `cli/r2.py:372-373`.
- `bm help` is a hand-maintained duplicate of Typer auto-help and has drifted (kb subcommands in
  wrong panel). `cli/main.py:66-130`.
- `deploy.py` uses raw `print()` while the rest of the CLI uses Rich console. ~30 sites.

## S14. Docs-site generation [agent: Modal-free] — Effort M
- Every model page tagline drops the authored blockquote one-liner (`_first_paragraph` skips
  blockquotes). `docs/gen_pages.py:74-87`.
- "See also: MODEL.md/BIOLOGY.md" links (140) bounce off-site to GitHub instead of same-page
  anchors. `gen_pages.py:45-47,186-189`, `_docgen.py:183-213`.
- Duplicated `_discover()` with divergent SKIP sets (43 vs 44). `gen_pages.py` vs
  `tooling/check_schema_docs.py`.
- `_docgen.py` has zero unit tests despite being built for testability (would have caught the above two).

## S15. OSS top-level docs / quickstart [agent: Modal-free; one needs-human] — Effort M
- Quickstart not reproducible: `bm` is a venv console-script and no doc says to activate the venv /
  use `uv run`; `make install && bm setup` fails with command-not-found. `README.md:24-27`,
  `docs/quickstart.md:19`.
- `docs/index.md` "five-minute success" omits `make install`; front-door CLI command list omits
  `cache` and `kb` (README + docs/index). 
- `SECURITY.md:8` / `CODE_OF_CONDUCT.md:32` ship "confirm before launch" placeholders on the
  official reporting contacts. `[needs-human: real contact]`
- README overclaims a credential-less quickstart — R2 anonymous read is unimplemented. Either
  implement `signature_version=UNSIGNED` or fix the claim. `README.md:31-32`. `[needs-human: scope]`
- `esmfold2` is neither shipped nor recorded in `FUTURE_WORK.md` (DoD #10). Add it.

## S16. Testing-framework correctness [agent: Modal-free] — Effort M
- Runner never validates inputs against the `ModelFamily` schema — the default-schema branch is
  unreachable. `runner.py:139-149`.
- Default validators accept non-canonical batch keys (`sequences`/`data`) no model uses.
  `runner.py:40,258-271`.
- Runner's pure Modal-free helpers have no unit tests. `runner.py:313-364`.
- Over-broad `**/test*.py` per-file-ignore silently disables the T20 print-ban for all of
  `commons/testing/`. `pyproject.toml:156`. (also commons)

## S17. Verify-then-fix (unverified/uncertain 🟠) [agent: Modal-free] — Effort S each
Confirm before editing: `boltzgen` phantom `output_zip` response field (`README.md:211`),
`boltzgen` `debug=True` leaking stack traces (`app.py:245`), `progen2` `params` required vs
documented-optional (`schema.py:80-82`), `esm2` inert `exclude_unset/exclude_none` (`schema.py:144-150`),
`evo2` bespoke downloader necessity. `params`-required-vs-optional also affects `esm_if1:65-68`,
`pro1:156-158`, `progen2` (add `default_factory`).

---

# 🟡 NITS (276) — opportunistic, do not gate launch [agent: Modal-free]

Sweep alongside the themed 🟠 work, not as standalone tasks. Highest-value clusters:
- Systemic `qa`-env mentions reported at 🟡 by per-model reviewers (covered by **L2**).
- Misleading inline comments (wrong RAM/memory comments: dnabert2, esm1v, esmc, sadie, config files).
- Naming drift (`...Predict...` classes for non-predict actions; display_name casing).
- f-string vs lazy `%`-style logging (immunebuilder, spurs, chai1, tempro).
- `sources.yaml` `pending`/`unknown2024.pdf` placeholder filenames (house-wide; batch).
- Changelog rows out of chronological order (esmfold, spurs).
- Dead config (pytest markers applied to zero tests; duplicated marker registry).
Full per-item list lives in the per-target review files.

---

# Recommended sequence

1. **L4 + L5 licensing first** — `[needs-human]` decisions that can remove models from the catalog;
   resolving them changes the scope of everything downstream. Kick these off in parallel with #2.
2. **L1 + L3 + S1: the de-internalization sweep** (incl. fixing the `dummy` template before it
   propagates further). Highest-reported, includes the functional `esmstabp` bucket bug. Then
   **L2** (`qa`→canonical env) with a single redeploy to verify.
3. **L8 + L9: get CI green on a clean tree** and delete the dead gateway billing schema — unblocks
   "green from clean clone" so every later fix is gated by a trustworthy pipeline.
4. **L6 acquisition build-order** (S edits) + **S7 downloader uniformity** — needed for the OSS
   cold-bucket deploy path; verify on Milestone-A smoke deploys.
5. **L7 broken contracts** + **S6 per-model correctness** — batch the Modal-free ones; schedule the
   `[needs-Modal]` verifications into the Milestone-A/B deploy windows.
6. **S2 error-taxonomy sweep** (W7) — large but mechanical and Modal-free; do it as one focused pass
   across the ~21 sites + commons ERROR_MAP.
7. **S3 + S4 KG hygiene** — batch the comparison.yaml + TODO/pending cleanup, then add a
   `bm kb validate --all` CI gate so it can't regress.
8. **S5 schema-field uniformity** + **S8 docs accuracy** + **S14 docs-site** — user-facing polish;
   regenerate the docs site and re-run `mkdocs build --strict`.
9. **S9–S16** convention/dead-code/logging/CLI/CI/testing cleanup, then the **S17 verify-then-fix**
   items.
10. **🟡 nits** swept opportunistically inside the above passes; do a final repo-wide grep
    (`biolm-modal`, `qa`, `BioLM-Modal`, `TODO`, `pending`) before launch sign-off.
