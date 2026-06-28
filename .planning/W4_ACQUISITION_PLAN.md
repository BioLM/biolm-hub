# W4 — Acquisition / R2 self-population plan (audited 2026-06-28)

> **Goal (user-ratified):** EVERY weight model uses ONE canonical pattern — **R2 cache first → on miss
> fetch from the original source (HF / direct URL / GitHub / library loader) → cache back to R2 in the
> SAME container path** — so `git clone → deploy` self-populates `biolm-public`. Use the shared commons
> wrappers; do NOT reinvent per-model. Surfaced by Milestone A (esm2 couldn't deploy: empty R2 +
> R2_ONLY). Internal repo was R2_ONLY too (its bucket was pre-populated separately). Based on two Opus
> audits (per-model download.py + commons acquisition subsystem). Internal file — deleted at launch.

## Canonical public API (standardize on these; demote `standard_r2_download`)
`r2_then_hf` · `r2_then_urls` · `r2_then_library` · **`r2_then_archive` (NEW)** · `download_with_fallback`
+ `CustomSourceConfig` (escape hatch only). Templates: `esm1b` (hf), `msa_transformer` (fair-esm library),
`tempro` (github-zip custom), `immunebuilder`/`rf3` (urls). `standard_r2_download` is the ONLY wrapper that
can't self-populate → demote (keep only for the `esmstabp` self-trained exception, with a clear error).

## Cache-to-R2 path = CONFIRMED correct (write prefix == read prefix == `model-store/<slug>/v1/...`).
Every model is `params_version="v1"`. HF models nest at `…/models--<repo>/snapshots/<rev>/`.

---

## PHASE 1 — Commons acquisition cleanup (do FIRST; Opus implementer + fresh Opus reviewer; commons changes authorized)
Order: B3 → B4 → **B1/B2 (the correctness fix)** → add `r2_then_archive` → public API/dead-code.

- **B1/B2 — marker-gated, unified R2 read (🔴 CORRECTNESS, the most important).** The R2-primary read
  (`_build_r2_primary`→`_acquire_r2_only`→`download_model_from_r2`, `downloads.py:287`) lists+pulls every
  object under the prefix with NO `.r2_cache_complete` marker gate, while the WRITE path always writes the
  marker and `restore_from_r2_atomic` (`r2_utils.py:567`) requires it. ⇒ an interrupted self-populate is
  silently restored as "success" and loads PARTIAL/broken weights instead of falling back to source (made
  worse because `r2_then_hf`/`library` skip `required_files` on the primary). **Fix:** route the R2-primary
  through the marker-gated `restore_from_r2_atomic` (or add a completion-marker precondition to
  `_acquire_r2_only`); treat missing/partial marker as a cache miss → source fallback. Folds the two
  divergent R2 read impls into one (also fixes `download_model_from_r2` pulling the marker/manifest dotfiles
  into the model dir).
- **B3 — delete dead bypass-detector surface:** `LibrarySourceConfig.{setup_function,import_modules,
  monitor_directories,enable_diagnostics}`, `AcquisitionResult.{bypass_detected,bypass_locations}`,
  `HfSourceConfig.use_auth_token` (never read), and the pass-through kwargs in `acquire_library_managed_model`
  + `r2_then_library`. (Earlier W-acq kept `bypass_*` as stubs — audit confirms they're now unused; safe to drop.)
- **B4 — add `cache_to_r2: bool = True` to `r2_then_library`** (it hardcodes `enable_r2_cache=True`), then
  migrate `evo`/`pro1` off the legacy `acquire_library_managed_model` and DELETE that legacy wrapper.
- **NEW `r2_then_archive(*, base_model_slug, params_version, model_variant=None, sub_path=None, archive_url,
  extract_subtrees: dict[str,str], strip_repo_root=True, required_files=None, headers=None, verify_ssl=True,
  timeout=1800) -> AcquisitionResult`** — R2 primary (marker-gated) → on miss `download_archive` + for each
  `(src_prefix→dest)` `extract_archive_subtree` (auto-strip the `<Repo>-<ref>/` root) → cache to R2. Build on
  the existing `download_archive`/`extract_archive_subtree`. Replaces ~150 lines of hand-rolled zip logic in
  tempro/deepviscosity/temberture/clean. (Also gives `add use_auth_token+allow_patterns to r2_then_hf` so
  evo2 can drop its raw `acquire_model_weights` — optional.)
- **Public API:** re-export the blessed wrappers + `download_with_fallback`/`CustomSourceConfig`/filter+variant
  helpers/`get_model_dir_util` from `models/commons/storage/__init__.py` (currently empty). Remove dead
  `acquire_custom_weights`, `quick_r2_check`; simplify `get_r2_prefix_from_target_dir`; resolve the
  `custom_function` "deprecated but required" contradiction; reconcile/remove the stray packaged
  `DOWNLOAD_MODEL_WEIGHTS_README.md`.

## PHASE 2 — Per-model migration onto the canonical wrappers (fan-out; reviewed). esm2 FIRST + deploy-validate.
**⚠️ HF flat→snapshot footgun:** esm1v/igbert/igt5/prostt5/progen2 load weights FLAT via
`from_pretrained(model_dir)`; moving to `r2_then_hf` nests them in a snapshot dir → must update BOTH
`download.py` AND the app's `get_model_dir` to return `build_hf_snapshot_path(...)`. Never migrate download.py alone.

| Model | → wrapper | source (confidence) |
|---|---|---|
| **esm2** | r2_then_library (fair-esm) | per-size init_fn `set_dir(t)+load_model_and_alphabet_hub(model_id_mapping[size])` (HIGH) — **proof model** |
| esm_if1 | r2_then_library (fair-esm) | `esm_if1_gvp4_t16_142M_UR50()` (HIGH) — note dbl-`checkpoints` sub_path |
| esmfold | r2_then_library (fair-esm) | `esmfold_v1()` (pulls esm2_3B backbone) (HIGH) |
| esm1v | r2_then_hf | `facebook/esm1v_t33_650M_UR90S_{1..5}` (HIGH); `"all"`=5-repo loop; flat→snapshot |
| igbert | r2_then_hf | `Exscientia/{IgBert,IgBert_unpaired}` (HIGH); flat→snapshot |
| igt5 | r2_then_hf | `Exscientia/{IgT5,IgT5_unpaired}` (HIGH); drop redundant filter; flat→snapshot |
| prostt5 | r2_then_hf | `Rostlab/ProstT5` (+pin revision) (HIGH); flat→snapshot |
| progen2 | r2_then_hf | per-variant HF mirror — **CONFIRM repo online** (likely `hugohrban/progen2-*`) (LOW) |
| antifold | r2_then_urls | `{"model.pt":"https://opig.stats.ox.ac.uk/data/downloads/AntiFold/models/model.pt"}` (HIGH) |
| mpnn | r2_then_urls | 6× `files.ipd.uw.edu/pub/ligandmpnn/<f>.pt` + HyperMPNN GitHub raw (HIGH) — removes bespoke branch |
| immunefold | r2_then_urls/custom | CarbonMatrixLab ckpts + esm2_3B — **CONFIRM ckpt host online** (MED/LOW) |
| boltz | r2_then_library or r2_then_hf | boltz lib auto-dl / `boltz-community/boltz-{1,2}`, `BOLTZ_CACHE`→target (MED) |
| abodybuilder3 | custom | Zenodo ckpts + r2_then_hf ProtT5 `Rostlab/prot_t5_xl_uniref50` — **CONFIRM Zenodo URL** (LOW) |
| **esmstabp** | **EXCEPTION — no migration** | self-trained RandomForest `{1..4}.joblib` (no public upstream); keep R2-authoritative, raise a clear "regenerate via `_train.py`" error on R2 miss (HIGH) |
| evo | r2_then_library (+B4 cache flag) | evo PyPI → HF `togethercomputer/evo-1-*`; **stop `cache_to_r2=False`** (redirect HF cache→target) |
| pro1 | r2_then_library or document | base + LoRA `mhla/pro-1`; currently `cache_to_r2=False` ("too large for R2") — enable caching OR document as an intentional exception |

**Also (consistency, lower priority):** migrate deepviscosity/temberture → `r2_then_archive`; extract the
thermompnn/thermompnn_d shared ckpt-move helper; fold evo2 into `r2_then_hf`(+auth); rfd3 stays foundry-CLI
custom but use `R2Utils.get_r2_prefix_from_target_dir` (not a hardcoded prefix); standardize `get_model_dir`
signatures; add `get_logger` to antifold/download.py; consolidate hand-rolled variant-filter closures onto
`build_variant_filter`/`build_model_type_filter`.

## PHASE 3 — Validation
esm2 deploy to `biolm-models-dev` (set `MODAL_ENVIRONMENT`) → confirm cache-miss→fair-esm fetch→R2 write→reload
→ finishes **Milestone A**. The other models self-populate on their first deploy at **Milestone B** (batched).

## Open confirmations (network was down during audit — confirm before/at migration, via WebSearch or deploy)
progen2 HF repo · immunefold ckpt host · abodybuilder3 Zenodo URL · boltz endpoint. esmstabp + pro1 are
exceptions needing a ratified call (esmstabp self-trained; pro1 "too large for R2").
