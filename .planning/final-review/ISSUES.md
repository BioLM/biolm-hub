# biolm-hub — Final Pre-Launch Issues Ledger

Single deduplicated, prioritized worklist synthesized from all 46 review reports. Grouped:
**Launch prerequisites (human)** first, then **HIGH -> MEDIUM -> LOW** engineering fixes.
Each item: title · location(s) · source dimension/model · proposed fix. See [`SUMMARY.md`](SUMMARY.md).

> **Two former "criticals" are NOT open engineering blockers** (verified this session):
> - **esmc MIT license** — VERIFIED against live upstream `evolutionaryscale/esm/LICENSE.md`; holder
>   matches. Not a legal blocker. Only a LOW stale-doc cleanup remains (see LOW-E1).
> - **Internal code in git history** — the planned, human-only launch-time history nuke (see LP-1).

---

## Launch prerequisites (human — maintainer only; mostly outside the code tree)

- [ ] **LP-1 — Nuke git history (IRREVERSIBLE).** Whole tree only; internal
  billing/redis/pubsub/analytics code survives in prior commits. · `.planning/W_LAUNCH_STAGING.md`
  Step D · security-deinternalization F1 · Fix: squash-to-root / orphan commit, verify single-commit
  `git log`, empty `git log --all --diff-filter=D`, re-run gitleaks, then force-push.
- [ ] **LP-2 — License sign-offs.** · prody, esmc, all models · prody + esmc reports, launch checklist ·
  Fix: (a) accept prody's transitive **OpenBabel GPL-2.0** (apt system tool, not vendored) or make
  PDBFixer/MIT the documented default; (b) esmc MIT already verified — no legal action, only stale-doc
  cleanup (LOW-E1); (c) spot-confirm inferred per-model LICENSE copyright holders.
- [ ] **LP-3 — Confirm contact channels route to a monitored human** (`support+security@biolm.ai`,
  `support+conduct@biolm.ai`). · SECURITY.md, CODE_OF_CONDUCT.md · oss-readiness, launch checklist.
- [ ] **LP-4 — Delete `.planning/` in the launch commit** (copy out W_LAUNCH_STAGING.md +
  MAINTAINER_LAUNCH_CHECKLIST.md first). · security-deinternalization F3.
- [ ] **LP-5 — Marketing gate** — launch is gated on marketing material being ready. · launch checklist.
- [ ] **LP-6 — (Optional) GitHub deploy infra** if you want the gated CI deploy path proven pre-launch:
  create `modal-dev` Environment + required reviewers + `MODAL_TOKEN_*`/`R2_*` *environment* secrets +
  `deploy-approved` label. Not required for OSS release (users deploy to their own Modal). ·
  cicd-repo-architecture F1, launch checklist. (Pairs with MED-8.)

---

## HIGH (engineering — fix before flipping public)

- [ ] **HIGH-1 — omni_dna license mismatch: declares Apache-2.0, upstream weights are MIT.** ·
  `models/omni_dna/sources.yaml:4`, `README.md:22,208-209`, `comparison.yaml:18,37,41`, `LICENSE` ·
  omni_dna (F1) · Fix: set `license.type: MIT`, replace `LICENSE` with MIT text, fix README license
  table + weights lines and comparison.yaml wording.
- [ ] **HIGH-2 — evo2 README advertises an unshipped variant (`evo2-7b-base` marked "Enabled").** Only
  `evo2-1b-base` resolves in config; an agent trusting the README POSTs to a 404. Contradicts README
  line 37. · `models/evo2/README.md:32,228` (+`:37`) vs `models/evo2/config.py` · documentation (F1),
  evo2 · Fix: change 7b-base to "Planned" + drop from Resource Requirements table and reconcile line
  37 — or add it to `variant_axes` in config if it is meant to ship.
- [ ] **HIGH-3 — prody golden tolerance masks near-zero-RMSD regressions.** `rel_tol=2.0` on the two
  "RMSD of a structure against itself" cases collapses the pass condition to `actual <= 2.0A`. ·
  `models/prody/test.py:131,138` · testing-goldens (F1), prody · Fix: replace with `abs_tol=1e-6` (+ a
  small `rel_tol` like `1e-4`); leaves the real-nonzero case (`:145-147`) untouched.

---

## MEDIUM (engineering — worth doing pre-launch; some are one mechanical sweep)

### Uniformity / dead plumbing
- [ ] **MED-1 — Delete vestigial `app_username` Modal param (never read) from all 37 models.** ·
  `models/*/app.py`, `models/commons/model/base.py:14-23` docstring, `gateway/routing.py:85-87`
  comment · code-cleanliness (#1) + per-model · Fix: delete the `app_username = modal.parameter(...)`
  line everywhere + the docstring/comment refs; no-arg instantiation is unaffected. `make check`
  confirms.
- [ ] **MED-2 — Strip internal workstream codenames (`W2`/`W3a`/`W5`/`W7`/`W8`/`W9`/`W12`) from 19
  shipped files.** · `pyproject.toml:10-11`, 17x model `config.py` (same boilerplate comment),
  `models/commons/model/config.py:59-60`, `gateway/config.py:31`, `gateway/routing.py:20`,
  `gateway/test_catalog.py:1`, `models/zymctrl/fixture.py:74` · oss-readiness (#1,#5) · Fix: rewrite the
  17x boilerplate once to describe behavior; drop the pyproject provisional-deps note.
- [ ] **MED-3 — Encode `include`/pooling option VALUE diverges across models** (`per_token` x6 /
  `per_residue` x2 / `residue` x3 / `rescoding` x1) — same output field, different magic input string. ·
  `models/{esm2,esm1b,esmc,e1,msa_transformer,zymctrl,dsm,temberture,antifold,igbert,igt5,ablang2}/schema.py`
  · cross-model-consistency (#1) · Fix: pick one canonical value, accept legacy literals via
  `AliasChoices`/validator, add a `tooling/` check; keep ablang2 `rescoding` as a documented exception.
- [ ] **MED-4 — prostt5 encode output field `mean_representation` diverges from canonical
  `embeddings`.** · `models/prostt5/schema.py` (ProstT5EncodeResponseResult) · prostt5, cross-model ·
  Fix: rename to `embeddings` with a Pydantic alias, add to glossary if shared, regenerate goldens.
- [ ] **MED-5 — antifold output field `vocab` diverges from catalog-standard `vocab_tokens`.** ·
  `models/antifold/schema.py` · antifold (#1) · Fix: rename to `vocab_tokens` with a back-compat alias.

### Documentation
- [ ] **MED-6 — README section duplication + internal QA leaking onto the public docs site.** The
  generator embeds the whole README under "Usage", re-printing generated tables (Variants/Actions/
  License/References) and contributor-only sections (Implementation Verification with golden
  tolerances + stale `python models/.../app.py`/`make test` shell commands, Implementation Notes,
  Resource Requirements). · `docs/gen_pages.py:340`, `models/*/README.md`, `models/dummy/README.md` ·
  documentation (#2) + readme-section-curation (P0) [**dedup: 2 reviewers**] · Fix: add a
  section allowlist/denylist to `dg.embed()` (deny Actions/Endpoints, Model Variants, Resource
  Requirements, License, References, Implementation Verification, Implementation Notes, Performance);
  delete `## Implementation Verification` from the dummy template + skills; rename the surviving H2.
- [ ] **MED-7 — igt5 README doc drift on residue embeddings.** · `models/igt5/README.md` · igt5 (#1) ·
  Fix: reconcile the README's residue-embedding description with the actual schema/output.
- [ ] **MED-8 — biotite KB prose has dangling references to the dropped model `boltz`.** ·
  `models/biotite/*` (comparison.yaml / MODEL.md / BIOLOGY.md prose) · biotite (#1) · Fix: remove or
  repoint the `boltz` references to a shipped model.
- [ ] **MED-9 — e1 license metadata imprecise for a public launch.** · `models/e1/sources.yaml`
  (license) · e1 (M1) · Fix: tighten the license type/notes to precise, verifiable wording.

### Correctness / model logic
- [ ] **MED-10 — dna_chisel `kozak_sequence_strength` can never return 1.0 (dead feature).** Inherited
  faithfully from internal. · `models/dna_chisel` (kozak_sequence_strength) · dna_chisel (#1) · Fix:
  correct the normalization so a perfect Kozak context scores 1.0 (or document the ceiling).

### Testing / goldens
- [ ] **MED-11 — Embedding goldens are magnitude-blind and globally averaged.** Cosine-pass sets
  `diff=0` and bypasses `rel_tol`, so a uniform-scale regression passes; one flattened cosine per item
  masks localized token regressions (~11 encode models). · `models/commons/testing/comparator.py`
  (150-197, 184-189, 339-382) · testing-goldens (#2) · Fix: add a per-vector L2-norm magnitude gate
  alongside cosine, or run element-wise numeric compare in addition; at minimum document the blind spot.
- [ ] **MED-12 — Golden regeneration not self-contained for 7 models (external fetch at gen-time).** ·
  `fixture.py` of `esm_if1`,`immunefold`,`mpnn`,`prody`,`spurs` (RCSB, unpinned) + `antifold`,`boltzgen`
  (GitHub, commit-pinned) · testing-goldens (#3) · Fix: commit the small structures as in-repo fixtures
  or promote to the `test-data/shared/` R2 library; pin RCSB fetches to a fixed assembly/format.
- [ ] **MED-13 — Loose numeric tolerances mask confidence-score regressions on stochastic models.**
  `rel_tol=0.5` gates plddt/ptm/pae at +/-50%. · `models/chai1/test.py:40,49`, `models/esm_if1/test.py:29`
  · testing-goldens (#4) · Fix: keep the loose structural RMSD threshold but bound confidence scores
  separately (validator band or `abs_tol` on [0,1] scores).

### Commons architecture
- [ ] **MED-14 — Delete dead public storage helpers (some in `__all__`, 0 callers).**
  `standard_r2_download`, `acquire_library_managed_model` (deprecated), `R2Utils.create_manifest`,
  `R2Utils.check_r2_cache_exists`, `get_items_added_by_day`; drop `build_variant_filter`/
  `build_model_type_filter` from `__all__`. · `models/commons/storage/download_helpers.py:47,138,258,697`,
  `r2_utils.py:276,699`, `cache.py:189` · commons-architecture (F1) + code-cleanliness (#2)
  [**dedup: 2 reviewers**] · Fix: delete the functions + `__all__` entries; either wire `clear_r2_cache`
  into a `bh cache clear` subcommand or delete it and its test.
- [ ] **MED-15 — Collapse two parallel "restore a dir from R2" implementations.** · `downloads.py:297,223`
  (`download_model_from_r2`/`_filter_r2_objects`, R2_ONLY path) vs `r2_utils.py:86,574`
  (`download_from_r2_prefix`/`restore_from_r2_atomic`, all other strategies) · commons-architecture (F2)
  · Fix: have `_acquire_r2_only` derive the prefix and call the shared restore path; retire the second copy.
- [ ] **MED-16 — Unify the dual hand-maintained commons file lists in the download image layer.**
  `essential_files` (14 mounted) vs `commons_files` (8 hashed) must both track the import closure; drift
  yields a silent deploy crash or a stale weights layer. · `models/commons/modal/downloader.py:218-244,184-194`
  · commons-architecture (F3) · Fix: derive one list for both mount+hash (hash the mounted dir), or add
  a covering import test in CI.

### CI/CD
- [ ] **MED-17 — Coverage gate configured but never enforced (`--no-cov` everywhere).** `fail_under=85`
  + CONTRIBUTING "target >=85%" are dead letters. · `pyproject.toml:124-131`, `Makefile:47,52,56,60,64`,
  `.github/workflows/ci.yml:46,49` · cicd-repo-architecture (#2) · Fix: either run the unit-marker suite
  once with `--cov ... --cov-fail-under=85`, or delete `fail_under` and soften the CONTRIBUTING claim.
- [ ] **MED-18 — Deploy security hinges on comment-only, unenforceable repo config.** Secrets stored as
  repo-wide (vs environment) secrets silently lose the SHA-confirming approval gate. · `.github/workflows/
  deploy.yml:22-40,124-184`, `SECURITY.md` · cicd-repo-architecture (#1) · Fix: promote the maintainer
  runbook into SECURITY.md as *required*; scope the Modal token to `biolm-hub-dev` + R2 creds read-only
  dev bucket; optionally fail-fast on a missing environment-only sentinel secret. (See LP-6.)
- [ ] **MED-19 — Supply-chain hardening on the secrets-bearing workflow.** Third-party actions pinned to
  mutable major tags (not SHAs); no dependabot; gitleaks binary fetched without checksum. · `deploy.yml`
  all `uses:`, `ci.yml:70-77`, missing `.github/dependabot.yml` · cicd-repo-architecture (#3) · Fix:
  SHA-pin every `uses:` in deploy.yml, add `dependabot.yml` (github-actions + pip), add `sha256sum -c`.

### OSS ergonomics
- [ ] **MED-20 — Quickstart never shows a concrete inference call.** README runnable block ends at
  `bh deploy`; the actual prediction is prose-only (no copy-pasteable curl). · `README.md:33-41,57` ·
  oss-readiness (#3) · Fix: add a short curl example using esm2 `encode` + the printed endpoint URL.
- [ ] **MED-21 — No GitHub community-health files.** Absent: ISSUE_TEMPLATE, PULL_REQUEST_TEMPLATE,
  CODEOWNERS, FUNDING.yml — yet CONTRIBUTING tells contributors to "open an issue". · `.github/` ·
  oss-readiness (#2) · Fix: add bug-report + feature-request issue templates, a PR template restating the
  `make check`/`make docs` gate, and a CODEOWNERS mapping `models/commons/` + `.github/`.
- [ ] **MED-22 — No browseable model catalog in README; Documentation URL points at the repo not docs.**
  · `README.md:66-73`, `pyproject.toml [project.urls]` · oss-readiness (#4) · Fix: publish the mkdocs
  site (GitHub Pages via existing `docs.yml`) and point Documentation at it, or add a generated
  model-catalog table to the README.

---

## LOW (engineering — polish / follow-ups; group into a post-launch or trailing PR)

### esmc stale-doc cleanup (residual of the retired "critical")
- [ ] **LOW-E1 — Reconcile esmc docs to the verified-MIT reality.** · `models/esmc/config.py:48,84`
  ("600m excluded — non-commercial license"), `comparison.yaml` (`dont_use_when` / esm2 "use ESM2 for
  MIT"), `MODEL.md` (MIT listed as a "Con"; retired `predict_log_prob` verb) · esmc (#2,#3,#4,#5) ·
  Fix: rewrite all three config comments to agree; drop MIT-based reasons to prefer ESM2; remove MIT
  from Cons; rename `predict_log_prob` -> `log_prob` in MODEL.md.

### Typed errors / verbs
- [ ] **LOW-1 — Make the closed action set structural, not cultural.** · `models/commons/model/config.py:27`
  (`ActionSchemaMap.name: str`) · cross-model (#2) · Fix: type it `name: ModelActions` or add a
  membership validator so CI rejects an invented verb.
- [ ] **LOW-2 — A few app.py raises bypass the typed taxonomy.** boltzgen zip-traversal is a user error
  raised as a bare `ValueError` (-> sanitized 500). · `boltzgen/app.py:235`, `dsm/app.py:209,224,268`,
  `temberture/app.py:154,164,167`, `immunebuilder/app.py:180` · cross-model (#3) · Fix: `UserError` for
  boltzgen's caller-input case; `ServerError`/`ModelExecutionError` (stable code) for the system ones.
- [ ] **LOW-3 — mpnn `log_probs` (plural, per-residue matrix) not pinned in the glossary.** ·
  `models/mpnn/schema.py:554,557` · cross-model (#4) · Fix: add `log_probs`/`sampling_probs` to
  `tooling/field_glossary.yaml` with canonical wording (docs-only).

### Code cleanliness
- [ ] **LOW-4 — Remove 11 stale `# noqa: C901` + false "FIXME: refactor" comments** (functions already
  below threshold). · `commons/core/decorator.py:34,70,93`, `antifold/schema.py:233,320`,
  `esmc/app.py:167`, `dsm/app.py:186`, `prostt5/app.py:224,284`, `esm1b/app.py:214`,
  `thermompnn/download.py` · code-cleanliness (#3) · Fix: delete; verify with `ruff --select C901`.
- [ ] **LOW-5 — Standardize the ~24 genuine C901 annotations** (15 stale FIXMEs / 1 justified / rest bare)
  and remove commented-out code (85 ERA001; incl. mpnn/util.py dead `f.write` block + bare `except`).
  Standardize "unshipped variant" documentation for evo/evo2/omni_dna. · many · code-cleanliness (#3b,#4).
- [ ] **LOW-6 — Drop misleading markers.** "[Temporary]" on the live `_return_payload_schema` path
  (`decorator.py:95`); resolve mpnn `SIDE_CHAIN` "disabling for now" (`mpnn/config.py:92`); typo
  "withing"->"within" (`abodybuilder3/app.py:82`). · code-cleanliness (#5).

### Docs (cosmetic)
- [ ] **LOW-7 — ASCII `--`/`---` render as literal hyphens on many pages.** · knowledge-graph prose;
  `mkdocs.yml` · documentation (#3) · Fix: normalize to Unicode dashes or add `pymdownx.smartsymbols`.
- [ ] **LOW-8 — Folding models name schema classes `*PredictRequest` for a `fold` action.** · chai1/rf3/
  abodybuilder3/immunebuilder/esmfold schema classes · documentation (#4) · Fix: rename to `*FoldRequest`/
  `*FoldResponse`.
- [ ] **LOW-9 — mpnn "1024 residues" advisory is phrased as a hard limit.** · `mpnn/README.md:22,55` ·
  documentation (#6) · Fix: reword to "recommended up to ~1024 residues".

### Commons (simplification)
- [ ] **LOW-10 — Trim speculative `ValidationConfig`/`CacheConfig` knobs no model sets** (`min/max_size_bytes`,
  `custom_validator`, `cache_timeout_hours`, `validate_checksums`) + their dead branches. ·
  `acquisition.py:77,183,1183,1215` · commons (F4).
- [ ] **LOW-11 — `LIBRARY_MANAGED` and `CUSTOM` strategies are near-redundant** (fold into CUSTOM +
  `env_vars`). · `acquisition.py:851,1069` · commons (F5). (Defer if risk-averse.)
- [ ] **LOW-12 — "cache" names three unrelated subsystems** — add an orientation note / rename
  weight-acquisition helpers to "restore/manifest". · `storage/cache.py`, `core/caching.py`,
  `acquisition.CacheConfig` · commons (F6).
- [ ] **LOW-13 — Stale docstring in multi-entity comparator** ("using: boltz1, boltz2"; real user is
  rf3). · `testing/multientity_comparator.py:35-37` · commons (F7).

### CI/CD (follow-ups)
- [ ] **LOW-14 — `detect` job runs PR-authored `detect_models.py`;** run it from the base-branch copy. ·
  `deploy.yml:92-121` · cicd (#4).
- [ ] **LOW-15 — Core detection functions only smoke-tested;** add table-driven unit tests with synthetic
  `changed_files`. · `.github/scripts/test_detect_models.py` · cicd (#5).
- [ ] **LOW-16 — mypy `--strict` excludes `tooling/` and `docs/` despite being "enforced".** ·
  `pyproject.toml:108` · cicd (#6) · Fix: un-exclude `tooling` (add to the CI mypy run like `.github/scripts`).
- [ ] **LOW-17 — Version/deprecation hygiene:** pytest pinned `<8.0.0`; `filterwarnings` suppresses the
  Pydantic V1 `@validator` deprecation (grep to confirm no V1 validators). · `pyproject.toml:51,111,120-122`
  · cicd (#7).

### R2 / security (cosmetic hardening)
- [ ] **LOW-18 — Prune HF/xet cache cruft from the public weights mirror** (~195 objects: `.locks/`,
  `__pycache__`, `.pyc`, `.download_lock`, xet `.log`, `.gitattributes`). No secrets; regen affected
  manifests if pruning. · `models/commons/storage/r2_utils.py` (`skip_patterns`) · r2-bucket (#5).
- [ ] **LOW-19 — gitleaks allowlist whitelists whole `test_*.py`/`conftest.py` files by path.** Not
  currently hiding anything. · `.gitleaks.toml` · security (#2) · Fix: narrow to value-based
  allowlisting of the known fake placeholders.

### Testing (follow-ups)
- [ ] **LOW-20 — abodybuilder3 `pdb_rmsd_threshold=0.05A` implausibly tight (flaky-failure risk).** ·
  `abodybuilder3/test.py:21` · testing (#5) · Fix: raise to ~0.5A in line with other deterministic folders.
- [ ] **LOW-21 — Single-entity PDB RMSD pairs atoms by list order (requires equal counts).** ·
  `comparator.py:284-307` · testing (#6) · Fix: match by (residue id, atom name) like the multi-entity path.
- [ ] **LOW-22 — Deployment tests are non-empty-results smoke checks only** (numeric goldens never run at
  deploy). · `runner.py:311,263-274` · testing (#7) · Fix (optional): attach structural validators to
  deployment cases.
- [ ] **LOW-23 — Cosine unit test doesn't lock in the `diff=0` bypass; comment stale.** ·
  `test_comparator.py:137-138` · testing (#8) · Fix: add a tiny-`rel_tol` pass test + a uniform-scale
  "still passes" test.
- [ ] **LOW-24 — Length-only comparison triggers on ANY string field** (is_generated_seq / MSA). ·
  `comparator.py:93-94,128-133` · testing (#9) · Fix: scope length-only compare to the specific output key.
- [ ] **LOW-25 — Adopt `abs_tol` for near-zero-expected numeric fields** (implemented, used by no model);
  reserve huge `rel_tol` for nothing. · `comparator.py:202-204` · testing (cross-cutting rec).

### Per-model LOW nits (non-blocking)
- [ ] **LOW-26 — zymctrl perplexity can be NaN if a generated sequence starts with a stop token.** ·
  `zymctrl/app.py:138-153` · Fix: guard the masked-loss result (fall back to unmasked loss / sentinel).
- [ ] **LOW-27 — rf3 `verify_ssl=False` on weights download** (IPD serves http). · `rf3/download.py:65` ·
  Fix: add a one-line MITM caveat comment. (Also: broad `except Exception`->ServerError, unwired
  checkpoint versions — trim later.)
- [ ] **LOW-28 — Missing/absent Pydantic aliases the glossary claims exist** — temberture
  (`prediction`->`score`, `per_residue_embeddings`->`residue_embeddings`, `schema.py:120,137`); sadie
  non-snake_case passthrough (`Chain`/`Numbering`/`Insertion`) · temberture, sadie · Fix: add
  `AliasChoices` or soften the glossary comment.
- [ ] **LOW-29 — Soft length caps not enforced on input** — thermompnn/thermompnn_d `max_sequence_len=1024`;
  thermompnn_d unverifiable determinism claim in MODEL.md. · Fix: enforce a hard cap in the item
  validator or soften docs to "tested up to 1024 residues".
- [ ] **LOW-30 — omni_dna encode output fields `mean`/`last` deviate from canonical `embeddings`** (dual-
  pooling encoder). · `omni_dna` · Fix: conscious sign-off vs schema-uniformity or add a glossary note.
- [ ] **LOW-31 — ablang2 unsupported `align` on `generate`; KB/staging pending-pointers.** ablang2
  (`align` not supported); progen2 sources.yaml empty commit + `pending` snapshot + `unknown2024.pdf`
  placeholders; esm1v KB numeric inconsistency (87 vs 41 DMS datasets); deepviscosity license-notice nit;
  msa_transformer STRUCTURE_PREDICTION tag dropped + "excluding BOS/EOS" doc (no EOS); spurs README
  golden-storage wording. · respective model reports · Fix: cosmetic per-model KB/wording touch-ups.
