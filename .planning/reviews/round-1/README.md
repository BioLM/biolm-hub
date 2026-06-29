# Round 1 Review — Executive Dashboard

First full independent review round of the `biolm-models` open-source repo. Per-target write-ups
live in `.planning/reviews/round-1/models/*.md` and `.planning/reviews/round-1/global/*.md`. The
actionable, de-duplicated fix plan is in [`FIX_PLAN.md`](./FIX_PLAN.md).

---

## 1. Totals by severity

| Severity | Raised | Refuted (dropped) | Surviving |
|----------|-------:|------------------:|----------:|
| 🔴 Launch-blocking | 36 | 5* | **31** |
| 🟠 Should-fix | 228 | 6 | **222** |
| 🟡 Nit / polish | 276 | 0 | **276** |
| **Total** | **540** | **11** | **529** |

\* 4 of the 5 dropped reds were schema-validation **test placeholders** (`dummy`, `prostt5`, `rf3`,
`gateway`), not real reviews; the 5th (`test/test`) is also a placeholder. After removing all six
test-placeholder targets (`ablang2`, `dummy`, `prostt5`, `rf3`, `gateway`, `test/test`), **every
remaining 🔴 carries a verdict of `real`** — there are no surviving unverified or uncertain reds.

**Verification confidence is high for the high-severity tier.** Of 264 red+orange findings raised,
only 10 were refuted (3.8%), 5 remain `unverified` and 2 `uncertain` (all 🟠, all in the fix plan as
"verify-then-fix"). The reds in particular held up: every refuted red was a test stub.

### Refuted high-sev findings (counted, NOT in the plan)
- 🔴 `dummy`, `prostt5`, `rf3`, `gateway`, `test/test` — schema-validation test stubs.
- 🟠 `ablang2` (stub); `esm1b` mutable-shared-default (uses correct idiom); `msa_transformer`
  sources commit-blank (was actually populated); `thermompnn` "9 pending" (not pending);
  `zymctrl` `embedding` vs `embeddings` (was already consistent); `deps-build` "properdocs"
  fabrication (justification was real).

---

## 2. Totals by theme (surviving findings)

| Theme | 🔴 | 🟠 | 🟡 | Notes |
|-------|---:|---:|---:|-------|
| Internal-reference leakage (`biolm-modal`, `qa`, "BioLM-Modal", Redis/Django/training.*) | 6 | ~12 | ~30 | The dominant launch-blocker class; systemic across 45+ files |
| Licensing / attribution | 6 | ~12 | several | 3 reds are inclusion-gate decisions (research-use / GPLv3 / no-license) |
| Correctness — schema vs. runtime contract | 6 | ~20 | many | Documented inputs/outputs that crash, are ignored, or are wrong scale |
| Error taxonomy not uniform (W7) | 0 | ~12 | ~8 | bare `raise e` → 500 + leaked text; user errors as 500; OOM as fake 200 |
| Acquisition / build-order (A.7) | 3 | ~6 | few | `huggingface_hub`/`fair-esm` in wrong image layer → cold-bucket build fails |
| Cross-model schema-field uniformity (A.3) | 0 | ~14 | many | `mean_plddt`/`plddt`, `tm`/`melting_temperature`, RequestModel-as-response |
| Knowledge-graph hygiene (A.9) | 1 | ~25 | many | TODO/pending residue + comparison.yaml dangling slugs (`nt`, `af2_nim`, …) |
| Docs accuracy (citations, versions, action names, base images) | 1 | ~30 | many | wrong arXiv/titles/vocab sizes; `predict` docs for `fold`/`encode` actions |
| Dead code / simplicity | 1 | ~10 | many | dead schemas, dup downloaders, dead billing schema, ~300 dead CLI lines |
| Tooling / CI correctness | 3 | ~7 | ~6 | CI red on clean tree; `bm kb matrix` crashes; cosine tolerance ineffective |
| Docs-site generation | 0 | 4 | 4 | tagline drop, off-site links, dup discovery, zero `_docgen` tests |
| OSS top-level docs / quickstart | 1 | ~5 | few | quickstart not reproducible; CLI command list wrong; contact placeholders |
| Logging consistency (W6) | 0 | ~4 | ~6 | emoji logs, get_logger bypass, sequence echo in errors |
| Security process | 0 | 1 | 0 | no gitleaks/trufflehog secret-scan gate |

(Category buckets are approximate — reviewers used freeform category labels; counts roll up the
freeform tags into these themes.)

---

## 3. Per-target finding counts (surviving; refuted excluded)

Test-placeholder targets (`ablang2`, `dummy`, `prostt5`, `rf3`, `gateway`, `test/test`) omitted.
`temberture` row added from its re-run (its 2🔴/6🟠/6🟡 are unverified). **DROPPED post-review** (rows kept
for the record, but no longer fix targets — see `DROPPED_MODELS.md`): `clean`, `boltz`, `rfd3`, `esmstabp`.

| Target | 🔴 | 🟠 | 🟡 | Top issue |
|--------|---:|---:|---:|-----------|
| models/abodybuilder3 | 0 | 9 | 5 | pLDDT schema type vs runtime + plddt=True path may 500 |
| models/antifold | 0 | 4 | 7 | `nanobody_chain_id` field violates ratified naming standard |
| models/biotite | 1 | 0 | 0 | LICENSE unverified copyright + confirm-before-release note |
| models/boltz | 2 | 5 | 5 | `msa_search` depends on the EXCLUDED `msa_search_nim` |
| models/boltzgen | 0 | 7 | 7 | README params contradict schema (num_designs cap) |
| models/chai1 | 0 | 4 | 9 | ESM embeddings not pre-cached (runtime HF download) |
| models/clean | 1 | 4 | 6 | License misrepresented — upstream is research-use-only |
| models/deepviscosity | 1 | 4 | 5 | `biolm-modal` leak in fixture.py |
| models/dna_chisel | 1 | 5 | 6 | `restriction_enzymes=None` crashes endpoint (500) |
| models/dnabert2 | 0 | 6 | 6 | advertised 4–8 kbp context unreachable (2048-char cap) |
| models/dsm | 1 | 5 | 8 | generate silently ignores max_length/top_k/top_p |
| models/e1 | 0 | 2 | 10 | docs call E1 "Encrypted" — it is an Encoder |
| models/esm1b | 0 | 2 | 6 | vocab_tokens includes non-canonical codes (25 vs 20) |
| models/esm1v | 0 | 6 | 5 | predict response shape diverges from house ESM convention |
| models/esm2 | 0 | 8 | 6 | unused sentence-transformers; log_prob desc wrong |
| models/esm_if1 | 0 | 7 | 5 | caller mistakes raise bare errors → 500; OOM as empty 200 |
| models/esmc | 1 | 1 | 4 | `huggingface_hub` in runtime layer not download layer |
| models/esmfold | 1 | 4 | 3 | pLDDT returned 0–100 but schema/docs say 0–1 |
| models/esmstabp | 1 | 2 | 6 | `biolm-modal` hardcoded — leak + broken self-population |
| models/evo | 1 | 6 | 4 | comparison.yaml `nt` slug → `bm kb validate evo` exits 1 |
| models/evo2 | 1 | 4 | 6 | HF fallback build fails (huggingface_hub not in download layer) |
| models/igbert | 0 | 7 | 5 | generate() missing variant-mismatch guard |
| models/igt5 | 0 | 3 | 8 | unpaired weights link points to paired HF repo |
| models/immunebuilder | 0 | 4 | 7 | docs claim 1Å RMSD threshold; test enforces 1.5Å |
| models/immunefold | 0 | 7 | 7 | `device` config override dead (loader reads cfg.gpu) |
| models/mpnn | 1 | 5 | 2 | LICENSE wrong year (2023 vs 2024) + pre-release note |
| models/msa_transformer | 0 | 1 | 6 | internal `qa` env name in usage comment |
| models/omni_dna | 0 | 6 | 6 | from_config + strict=False → silent weight-drop risk |
| models/peptides | 1 | 2 | 6 | wrong license / attribution; possible GPLv3 copyleft dep |
| models/pro1 | 1 | 5 | 6 | LICENSE ships "NOTE TO MAINTAINERS" + unconfirmed license |
| models/prody | 1 | 5 | 9 | ~12 bare `ValueError`/`raise` → generic 500 |
| models/progen2 | 1 | 4 | 4 | shipped TODOs leak internal `qa` env |
| models/rfd3 | 1 | 5 | 6 | documented/tested params (symmetry, …) silently ignored |
| models/sadie | 0 | 4 | 5 | error message echoes full input sequence |
| models/spurs | 0 | 5 | 8 | fabricated SPURS acronym + ESM2 layer omits fair-esm |
| models/temberture | 2 | 6 | 6 | huggingface_hub build-order (cold-bucket self-pop fails) + LICENSE holder altered |
| models/tempro | 1 | 5 | 6 | upstream has NO license; MIT fabricated; weights redistributed |
| models/thermompnn | 0 | 4 | 7 | mutation positions documented PDB-numbered, code uses contiguous |
| models/thermompnn_d | 1 | 4 | 8 | LICENSE misattributes upstream copyright (MIT violation) |
| models/zymctrl | 1 | 4 | 3 | HF fallback build fails; perplexity over EOS/pad |
| commons (global) | 1 | 7 | 5 | `biolm-modal` in shipped comment; T20 print-ban silently off |
| CLI `bm` (global) | 2 | 4 | 8 | `bm kb matrix` crashes; "BioLM-Modal" in front-door help |
| Testing framework (global) | 1 | 3 | 6 | cosine_distance_threshold re-gated to rel_tol → ineffective |
| CI/CD (global) | 0 | 5 | 6 | label gate trusts GitHub *triage* role |
| Docs & KG system (global) | 0 | 4 | 4 | every page tagline drops the authored one-liner |
| Errors & logging (global) | 0 | 6 | 8 | system-error branch unused → code=null + leaked text |
| Dependencies & build (global) | 0 | 3 | 4 | HF download layer missing huggingface_hub (4 models) |
| OSS readiness & docs (global) | 1 | 5 | 3 | `biolm-modal` in dummy template (propagates to every model) |
| Security & de-internalization (global) | 3 | 5 | 2 | `R2_BUCKET="biolm-modal"` hardcoded in esmstabp/_train.py |
| DoD audit (global) | 2 | 5 | 2 | dead billing/auth schema; safe CI tier red on clean tree |

---

## 4. The 🔴 launch-blockers (31, grouped)

All 🔴 verdicts are `real`. They collapse into seven causes:

1. **Internal-name leakage (DoD #11).** `biolm-modal` in shipped code/docs/template; `qa` Modal
   env across commons + ~30 model `app.py` (now also *functionally stale* — CI moved to
   `biolm-models-dev`, code didn't); "BioLM-Modal" in the `bm` CLI front-door help.
   *(security ×3, oss-readiness, dod-audit ×1, commons, cli ×1, deepviscosity, esmstabp, boltz, progen2)*
2. **Licensing inclusion-gate decisions.** `clean` (research-use-only mislabeled BSD-3),
   `peptides` (possible GPLv3 copyleft + wrong attribution), `tempro` (upstream unlicensed; MIT
   fabricated; weights redistributed). Plus `mpnn`/`thermompnn_d`/`biotite` copyright-correctness.
3. **Acquisition build-order (A.7).** `esmc`, `zymctrl`, `evo2` (and latently `temberture`) put
   `huggingface_hub` in the runtime layer → cold/empty-R2 self-population build fails — the OSS
   deploy path.
4. **Broken public contracts.** `dna_chisel` (`restriction_enzymes=None` → 500), `dsm` (generate
   ignores 3 params), `esmfold` (pLDDT wrong scale), `rfd3` (documented params silently dropped),
   `boltz` (`msa_search` → excluded NIM).
5. **CI / tooling red on a clean tree.** 14 `cli/test_kb.py` tests fail (typer vs click Exit);
   `bm kb matrix` imports a non-existent module; testing-framework cosine tolerance is inert.
6. **Dead billing/auth schema** still shipped in the gateway (`introspection.py`) — contradicts the
   W8 "auth/billing stripped" claim.
7. **Misc per-model correctness/errors** rolled into the themed plan.

---

## 5. The 🟠 should-fix landscape (222)

The bulk are **uniformity & accuracy debt**, fixable Modal-free and mostly batchable:
- **Error taxonomy** (W7) is structurally done but not applied: the system-error branch is
  effectively dead (~21 `raise e` sites), `UnsupportedOptionError`/`ResourceNotFoundError` are
  wired but never raised, `ServerError` is missing from `ERROR_MAP`, and caller mistakes surface as
  500 across ≥10 models.
- **Knowledge-graph hygiene**: TODO/pending residue and dangling `comparison.yaml` slugs (`nt`,
  `af2_nim`, `propermab`, `gemme`, `camsol`, `poet`, `saprot`, …) recur in 20+ models; one (`evo`)
  fails the repo's own `bm kb validate`.
- **Docs accuracy**: wrong citations/arXiv IDs/paper titles/vocab sizes, wrong base-image/version
  claims, and the repo-wide habit of documenting the action as `predict` when it is `fold`/`encode`.
- **Cross-model schema-field divergence**: `mean_plddt` vs `plddt` vs `full_plddt`; `tm` vs
  `melting_temperature` vs `prediction`; response DTOs inheriting `RequestModel`.
- **LICENSE reviewer notes** ("flag for reviewer to verify" / "NOTE TO MAINTAINERS") shipping in
  ~10 models.

---

## 6. The 🟡 nits (276)

Polish only — dead attributes, misleading comments, f-string vs lazy logging, changelog ordering,
naming drift, systemic `qa`-env mentions reported at low severity by per-model reviewers. Sweep
opportunistically alongside the themed 🟠 work; do not gate launch on these.

---

## 7. Cross-cutting takeaways

- **The single highest-leverage launch task is the de-internalization sweep.** It is the
  most-reported issue, spans 45+ files, includes a *functional* bug (`esmstabp` writes to the wrong
  bucket; `qa` no longer matches the real deploy env), and propagates from the `dummy` template into
  every new model. Fix the template + commons first, then sweep models.
- **The framework is sound; the debt is application-level.** commons (taxonomy, acquisition engine,
  ModelFamily), the testing harness, CI/CD gating, and the docs system are all architecturally
  praised. Most findings are inconsistent *application* of good primitives, not design flaws.
- **Three licensing reds need a human decision before any code work** — they may remove models from
  the catalog entirely.
- **Verification paid off**: only ~4% of high-sev findings were refuted, and the refutations were
  almost entirely test stubs — the reviewers' real reds are trustworthy.
