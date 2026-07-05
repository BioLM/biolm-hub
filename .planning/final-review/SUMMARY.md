# biolm-hub — Final Pre-Launch Review: Executive Summary

**Date:** 2026-07-06 · **Inputs:** 9 cross-cutting dimension reports + `readme-section-curation.md`
+ 36 per-model reports (all under `.planning/final-review/`). Actionable ledger: [`ISSUES.md`](ISSUES.md).

---

## Overall verdict: **GO — with a short pre-launch fix pass**

The repo is in genuinely good shape and safe to flip public after a focused polish pass. Every
dimension landed at **`minor-gaps`** or **`READY`** — there is **no open engineering launch-blocker**.
License hygiene, de-internalization of the *working tree*, R2 public-readiness, CI trust-split, mypy
`--strict`, and cross-model uniformity are all strong and largely CI-enforced.

### The two apparent "critical blockers" — both correctly retired

1. **esmc license (was flagged HIGH / "launch-blocking")** -> **RESOLVED — not a blocker.**
   The MIT relicense with "Copyright 2026 Chan Zuckerberg Biohub, Inc." was **verified against the
   LIVE upstream** `github.com/evolutionaryscale/esm/blob/main/LICENSE.md`, which reads exactly that —
   a real relicense that postdates model knowledge cutoffs; the copyright holder **matches upstream**.
   Public-bucket redistribution is therefore legitimate. The esmc reviewer's `lossy-or-wrong` fidelity
   and `significant-gaps` quality verdicts were driven *entirely* by this now-resolved concern.
   **Residual (LOW):** stale in-repo doc attribution still contradicts the MIT reality —
   `config.py:48,84` say "600m excluded — non-commercial license", `comparison.yaml` still advises
   "use ESM2 for MIT", `MODEL.md` lists MIT as a "Con" and uses the retired `predict_log_prob` verb.
   Cleanup only.

2. **Internal billing/redis/pubsub/analytics code in git HISTORY** -> **PLANNED LAUNCH STEP, not an
   engineering issue.** The working tree is clean; the material survives only in prior commits. This
   is the known, staged, human-only **history nuke** (squash-to-root / orphan commit) already written
   up in `.planning/W_LAUNCH_STAGING.md` Step D. Tracked under Launch Prerequisites, not engineering.

---

## Per-dimension verdicts

| Dimension | Verdict | Findings (by severity) |
|---|---|---|
| oss-readiness | minor-gaps | MED x3, LOW x2 |
| commons-architecture | minor-gaps | MED x3, LOW x4 |
| cross-model-consistency | minor-gaps | MED x1, LOW x3, INFO x1 |
| code-cleanliness | minor-gaps | MED x2, LOW x4 |
| documentation | minor-gaps | **HIGH x1** (evo2), MED x1, LOW x2, INFO x2 |
| cicd-repo-architecture | minor-gaps | MED x3, LOW x3, nit x1 |
| r2-bucket | **READY** | LOW x1 (HF-cache cruft) |
| testing-goldens | minor-gaps | **HIGH x1** (prody), MED x3, LOW x5 |
| security-deinternalization | **READY** | LOW x1, INFO x2 (1 = planned history nuke) |
| readme-section-curation | advisory | structural recs (P0/P1/P2) — dedupes with documentation MED |

Deduplicated engineering severity totals (after retiring the two "criticals"):
**HIGH x3 · MEDIUM x22 · LOW x~25**, plus 6 human Launch Prerequisites. See `ISSUES.md`.

---

## Per-model roll-up (36 models)

- **Fidelity vs internal reference:** 33 **preserved**, 2 **divergent-ok**, 1 **lossy-or-wrong**.
- **Quality:** majority **ready**, several **minor-gaps**, 1 **significant-gaps**.

Models worth calling out by name:

| Model | Fidelity | Quality | Why flagged |
|---|---|---|---|
| **esmc** | lossy-or-wrong | significant-gaps | **Both verdicts were license-driven and are now RESOLVED** (MIT verified vs live upstream). Real residual = LOW stale-doc cleanup only. Inference science, weights source, action semantics all preserved. |
| **omni_dna** | preserved | minor-gaps | **Open HIGH:** declares Apache-2.0 but upstream weights are **MIT** — real accuracy/license bug to fix pre-launch (`sources.yaml`, `LICENSE`, `README`, `comparison.yaml`). |
| **evo2** | preserved | ready | **Open HIGH (docs):** README advertises `evo2-7b-base` as "Enabled" but only `evo2-1b-base` ships -> an agent trusting it gets a 404. Self-contradicts line 37. |
| **prody** | preserved | minor-gaps | **Open HIGH (testing):** `rel_tol=2.0` defeats the near-zero self-alignment RMSD goldens (masking). **Plus MED:** OpenBabel GPL-2.0 baked into the image + fixture default — needs the maintainer license sign-off. |
| **esm1b / esm1v** | divergent-ok | minor-gaps | Divergences are **deliberate and documented** (vocab restriction / max-length 512->1022), **not regressions**. Low-severity KG wording nits only. |
| **dna_chisel** | preserved | minor-gaps | **Inherited correctness bug (MED):** `kozak_sequence_strength` can never return 1.0 — a dead feature faithfully carried over from internal. |

Everything else is `preserved` fidelity with `ready`/`minor-gaps` quality — findings are LOW nits
(KB pending-pointers, output-field aliases, doc wording, soft length caps). No model besides the six
above needs attention before launch beyond the systemic sweeps below.

---

## Top themes (systemic, cut across many models)

1. **Vestigial internal plumbing in every model.** `app_username` Modal param re-declared and never
   read in all 37 `app.py`; internal workstream codenames (`W2`/`W8`/...) in 19 shipped files. Pure
   noise that works against the "diff is the science, not the plumbing" thesis. One mechanical sweep.

2. **README <-> generated-docs duplication + internal QA leaking to the public site.** The generator
   embeds each full README under "Usage", re-printing tables the site already generates
   authoritatively (Variants/Actions/License) *and* contributor-only sections (Implementation
   Verification with golden tolerances, stale `python models/.../app.py` shell commands). This is the
   same double-authoring that produced the evo2 drift. Flagged independently by `documentation` and
   `readme-section-curation` — the single highest-leverage docs fix.

3. **Output/input field-name uniformity has residual outliers.** Output side largely converged (with
   aliases), but the **encode `include` option VALUE** still differs per model
   (`per_token`/`per_residue`/`residue`/`rescoding`), and a few output fields diverge
   (prostt5 `mean_representation`, antifold `vocab`, omni_dna `mean`/`last`). Back-compat alias +
   `tooling/` check is the pattern.

4. **Golden-test calibration.** One real masking hole (prody `rel_tol=2.0`), magnitude-blind embedding
   goldens, over-loose stochastic-model tolerances (chai1/esm_if1 `rel_tol=0.5`), one over-tight one
   (abodybuilder3 `0.05A`), and non-self-contained regen for 7 models (RCSB/GitHub fetch). `abs_tol`
   exists but is unused — adopting it fixes the masking hole.

5. **Storage subsystem carries dead/duplicated surface.** ~4,850 lines; dead public helpers (0
   callers, some in `__all__`), two parallel R2-restore implementations, dual hand-maintained commons
   file lists. Not a blocker, but the one place the uniformity promise frays for a contributor.

6. **CI/CD hygiene (not correctness).** Coverage gate declared (`fail_under=85`) but never run
   (`--no-cov` everywhere); deploy security depends on comment-only, unenforceable repo config;
   third-party actions on the secrets-bearing workflow are tag-pinned not SHA-pinned; no dependabot.

7. **License provenance is mostly excellent but needs targeted sign-offs.** 37/37 per-model LICENSE
   files, all permissive, tricky cases documented. Items needing a human: omni_dna Apache->MIT
   correction (HIGH), prody OpenBabel GPL-2.0 accept, esmc stale-doc cleanup, and a spot-confirm of
   inferred copyright holders.
