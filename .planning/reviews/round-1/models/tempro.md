# Review — `models/tempro/`

**Reviewer:** independent round-1 (Opus)
**Date:** 2026-06-29

## Summary

TEMPRO is a nanobody melting-temperature (Tm) predictor: it calls the deployed ESM2 endpoint for
mean-pooled embeddings, then runs a small Keras head on CPU. The plumbing is largely sound and
mirrors its closest sibling `esmstabp` (same ESM2-cross-call shape, same `predict` action, CPU-only
head): config/schema/download/test all follow the house abstractions, field descriptions render,
fixtures use the shared runner, and there is **no internal-repo / `.planning` / path leakage and no
`print`**.

The **one launch-gating problem is licensing**: the upstream TEMPRO repository has **no license at
all** (GitHub API: `license: null`, no `LICENSE` file in the repo, license endpoint 404), yet this
model ships a fabricated MIT `LICENSE` and asserts MIT in `sources.yaml`, `README.md`, and
`comparison.yaml` — and it self-populates weights by downloading `user.zip` from that unlicensed
repo. Beyond that, the knowledge-graph files are internally inconsistent and stale (applied
literature present in `sources.yaml` but denied in `BIOLOGY.md`/`comparison.yaml`), four `TODO`
comments ship in the docs, the citation in `README.md`/`MODEL.md` is wrong, the melting-temperature
output field name (`tm`) is inconsistent with its two sibling Tm models, and the logging is an
emoji-heavy outlier vs every other model.

Findings below grouped by severity.

---

## 🔴 Must-fix

### 1. Upstream repo has NO license — the MIT claim is fabricated (and weights are redistributed)
- **Category:** Licensing
- **Location:** `models/tempro/LICENSE`; `models/tempro/sources.yaml:3-6`; `models/tempro/README.md:140-142`; `models/tempro/comparison.yaml:11`; weight source `models/tempro/config.py:23-25`
- **Detail:** The GitHub API is authoritative and reports for `Jerome-Alvarez/TEMPRO`:
  `license: null`, `GET .../license` → `404 Not Found`, and the repo root contains **no LICENSE
  file** (only `README.md`, `embedding_generator.zip`, `paper_results.zip`, `requirements.txt`,
  `tm_predictors.rar`, `user.zip`). Under default copyright this means **all rights reserved** — the
  code and weights are *not* MIT and *not* open-source. Yet `LICENSE` is a full MIT text with
  "Copyright (c) 2024 Jerome Anthony E. Alvarez", `sources.yaml` declares `type: MIT`, `README.md`
  says "Code: MIT", and `comparison.yaml` even advertises "MIT license enables unrestricted
  commercial use." Compounding this, `config.py` makes the container download `user.zip` from this
  unlicensed repo at a pinned commit and re-serves the extracted Keras weights — i.e. we
  redistribute third-party weights that carry no grant of rights. This is the strongest launch
  gate: rubric A.8 requires the per-model LICENSE to be permissive, consistent with `sources.yaml`,
  and free of inferred/unflagged holders. The published *paper* (Sci. Reports, CC-BY) does not
  license the code/weights.
- **Fix:** Do not ship a fabricated MIT file. Contact the authors to obtain an explicit license for
  the code+weights, OR drop the MIT claims everywhere and mark the license as **unknown / all
  rights reserved** in `sources.yaml`/`README.md`/`comparison.yaml`, and have the inclusion-matrix
  owner decide whether TEMPRO can ship at all given that its weights are unlicensed. If a license is
  secured, set `LICENSE`, `sources.yaml`, README, and comparison.yaml to match it exactly.

---

## 🟠 Should-fix

### 2. Knowledge-graph internal inconsistency: applied literature present vs "none catalogued"
- **Category:** Knowledge graph
- **Location:** `models/tempro/sources.yaml:31-92` vs `models/tempro/BIOLOGY.md:34-36` and `models/tempro/comparison.yaml:16`
- **Detail:** `sources.yaml` lists **four** `applied_literature` entries that explicitly benchmark
  TEMPRO (NanoMelt, the mechanistic-interpretability bioRxiv, NBsTem, NbBench). But `BIOLOGY.md`
  states "No applied literature entries have been catalogued yet" and `comparison.yaml` lists as a
  weakness "limited external validation -- no independent benchmarking studies or applied literature
  citations yet." These three files directly contradict each other; `sources.yaml` was clearly
  updated later (it cites 2025/2026 papers) while the prose files were not. Rubric A.9 requires the
  five files to be internally consistent.
- **Fix:** Reconcile: populate `BIOLOGY.md` "Applied Use Cases" from the `sources.yaml` entries and
  remove the TODO; update the `comparison.yaml` weakness to reflect that independent benchmarks now
  exist (and that they report TEMPRO underperforming newer models — useful for `dont_use_when`).

### 3. `TODO` placeholders ship in knowledge-graph docs
- **Category:** Docs / knowledge graph
- **Location:** `models/tempro/README.md:91`; `models/tempro/MODEL.md:24`; `models/tempro/MODEL.md:41`; `models/tempro/BIOLOGY.md:36`
- **Detail:** Four `<!-- TODO: ... -->` comments remain (extract benchmarks / training data / search
  for citing papers). They are HTML comments so they don't render, but they ship in source, and
  rubric A.9 explicitly forbids stray `TODO` residue in shipped knowledge-graph files. The paper
  (DOI in `sources.yaml`) is open-access CC-BY, so the "requires PDF access" TODOs are resolvable.
- **Fix:** Resolve the TODOs (the Sci. Reports paper is freely available) or delete the comments and
  state plainly what is known.

### 4. Citation in README/MODEL.md is wrong (mislabeled "Preprint", wrong title, missing co-author, no DOI)
- **Category:** Docs
- **Location:** `models/tempro/README.md:144-158`; `models/tempro/MODEL.md` (paper references)
- **Detail:** `sources.yaml:13-24` correctly records the published article: *"TEMPRO: nanobody
  melting temperature estimation model using protein embeddings"*, Scientific Reports 14:19074
  (2024), DOI `10.1038/s41598-024-70101-6`, authors **Jerome Anthony E. Alvarez and Scott N. Dean**.
  But `README.md` cites it as a *"Preprint (2024)"* with a different title ("...protein **language
  model** embeddings"), **only Alvarez** (drops Scott N. Dean), and the BibTeX has no DOI/journal.
  This is verifiably inaccurate.
- **Fix:** Replace the README/MODEL.md citation + BibTeX with the published Sci. Reports record from
  `sources.yaml` (both authors, journal, volume, year, DOI).

### 5. Melting-temperature output field name is inconsistent across sibling Tm models
- **Category:** Schema / cross-model consistency
- **Location:** `models/tempro/schema.py:62-65` (`tm`) vs `models/esmstabp/app.py:148-149` (`melting_temperature`) vs `models/temberture/schema.py:136-138` (`prediction`)
- **Detail:** Three sibling thermostability models each name the *same* output concept differently:
  TEMPRO `tm`, ESMStabP `melting_temperature`, TemBERTure `prediction`. None of them appears in
  `tooling/field_glossary.yaml`. The repo's north star is uniformity ("the diff between two models
  should be the science, not the plumbing"); a Tm scalar is the same field regardless of model, so
  it should have one canonical name. This is a cross-model decision, but TEMPRO's terse `tm` is the
  outlier worth aligning.
- **Fix:** Pick one canonical name (e.g. `melting_temperature`, matching ESMStabP), add it to
  `field_glossary.yaml`, and align TEMPRO (keep a Pydantic alias `tm` if needed for back-compat per
  rubric A.3). Coordinate with the esmstabp/temberture reviewers.

### 6. Emoji-heavy logging is a uniformity outlier
- **Category:** Logging / consistency
- **Location:** `models/tempro/app.py` lines 109, 118, 124, 130, 132, 144, 157, 174, 193, 205, 215, 218, 238, 242
- **Detail:** TEMPRO emits **14** emoji-decorated log lines (🔧📂✅🎯🔗📞❌🌡️📊🧠). A scan of all 44
  `app.py` files shows this is by far the highest — the next is `mpnn` at 4, and the direct sibling
  `esmstabp` (same ESM2-cross-call flow) uses zero. esm2/dummy (the reference + template) use none.
  This is plumbing noise that makes TEMPRO's logs diverge from the rest for no functional reason.
- **Fix:** Drop the emoji and match the plain `logger.info("...", ...)` style used by `esm2`,
  `esmstabp`, and `dummy`.

---

## 🟡 Nits

### 7. Dead commented-out code in the ESM2 call path
- **Category:** Simplicity
- **Location:** `models/tempro/app.py:168-171`
- **Detail:** A commented-out `model_dump()` block with the note "Everything is now a dict." The
  decorator does serialize the response to a dict (confirmed: `modal_endpoint` returns
  `serialize_model(...)`), so the dict access is correct — but the commented block is leftover
  scaffolding.
- **Fix:** Delete lines 168-171.

### 8. `get_esm2_modal_class` lru_cache is needless indirection vs the sibling pattern
- **Category:** Simplicity / consistency
- **Location:** `models/tempro/app.py:77-85, 162` vs `models/esmstabp/app.py:98-100`
- **Detail:** TEMPRO wraps the ESM2 `Cls.from_name(...)` in a module-level `@lru_cache(maxsize=128)`
  keyed on `(esm_app_name, app_username)`. Within a container both args are fixed, so the cache only
  ever holds one entry — the 128 slots and the helper add complexity for nothing. ESMStabP simply
  does `self.esm2_model = Cls.from_name("esm2-650m","ESM2Model")(app_username=self.app_username)`
  once in `setup_model`. Relatedly, TEMPRO passes the Pydantic request object to `.remote()` while
  ESMStabP passes `request.model_dump()` — pick one across the ESM2-dependent models.
- **Fix:** Initialize the ESM2 class reference once in an `@modal.enter` method like ESMStabP and
  drop the lru_cache helper; align the `.remote()` payload form (dict vs object) with the siblings.

### 9. Error typing / double-logging on the ESM2 path
- **Category:** Errors
- **Location:** `models/tempro/app.py:182, 192-194, 241-243`
- **Detail:** Line 182 raises a bare `ValueError` for an *internal* fault (ESM2 returned no
  embeddings); it is then caught and re-wrapped as `RuntimeError` (192) and logged with
  `exc_info=True`, then the outer `predict` catch (242) logs the same exception **again** before
  `raise e`. Net effect: the same failure is logged twice and never carries a stable BioLM `code`.
  (The `RuntimeError` for cross-call failure itself matches the esmstabp/boltz/spurs sibling
  convention, so that part is consistent.) Per W7, an internal fault is better expressed as
  `ServerError`/`ModelExecutionError`.
- **Fix:** Raise `ModelExecutionError` (from `commons.core.error`) for the empty-embeddings case,
  and log the failure in one place (drop the duplicate `logger.error` in either
  `get_esm2_embeddings` or `predict`).

### 10. Minor style: f-string + degree symbol in a log call
- **Category:** Readability / consistency
- **Location:** `models/tempro/app.py:236`
- **Detail:** `logger.debug(f"  Sequence {i+1}: Tm = {tm_value:.2f}°C")` uses an f-string (eager
  formatting) while the rest of the file uses lazy `%`-style logging; it also embeds a non-ASCII `°`.
- **Fix:** `logger.debug("Sequence %s: Tm = %.2f C", i + 1, tm_value)`.

### 11. fixture.py comment claims His-tags removed, but GSHM remnants remain
- **Category:** Docs / fixtures
- **Location:** `models/tempro/fixture.py:19, 26, 30, 34`
- **Detail:** The comment says sequences were "cleaned from experimentals.fasta (His tags and extra
  residues removed)", yet 4TYU/4U05/4W68 still carry the `GSHM` expression-tag remnant. This may be
  intentional (matching the paper's validation inputs) but contradicts the comment.
- **Fix:** Either finish the cleanup or correct the comment to say sequences are kept verbatim from
  the paper's external-validation set.

### 12. `sources.yaml` primary-paper `md_r2: pending` + empty `arxiv`
- **Category:** Knowledge graph
- **Location:** `models/tempro/sources.yaml:16, 23`
- **Detail:** The primary paper has `arxiv: ''` and `md_r2: pending`, whereas the reference `esm2`
  ships a real `md_r2` for its primary papers. (`pending` on `applied_literature` `pdf_r2` matches
  esm2's accepted convention, so those are fine.) Minor completeness gap for the primary entry.
- **Fix:** Generate/upload the markdown for the primary paper and set `md_r2`, or leave `pending`
  only if the global convention permits it for primaries too.

---

## Notes (not tempro-specific; for the global reviewer)

- `app.py:252` `# Force deploy to QA or production:` references the internal `qa` Modal env. This is
  **repo-wide** — all ~35 `app.py` files (including the reference `esm2:484`) carry the same
  `qa`/`main` deploy comment, and `commons/modal/deployment.py` literally checks
  `current_env in ("qa","main")`. Rubric C lists `qa` as an internal-env leak; resolving it is a
  global/commons cleanup, not a TEMPRO-only fix, so flagging here rather than as a TEMPRO finding.

## DoD spot-check (this model)
- Standard layout, `ModelFamily`, closed-set `predict` action, rendering field descriptions,
  shared-runner tests, no `print`, no internal-repo/.planning leakage: **met**.
- Per-model permissive LICENSE consistent with sources: **NOT met** (finding #1).
- Knowledge graph complete + internally consistent, free of TODO/pending residue: **NOT met**
  (findings #2, #3, #12).
- Acquisition self-populates the public bucket via canonical wrappers (`download_with_fallback`,
  R2-primary + custom GitHub-zip fallback, caches back to R2): **met** — though see #1 re: the
  legality of redistributing the unlicensed weights.

---

## Verification

Adversarial re-check of the six HIGH-severity findings against current source (2026-06-29). Each
was re-read in the cited files and tested against the live GitHub API.

1. **License fabrication / unlicensed weight redistribution — REAL.** GitHub API is authoritative
   and confirms the finding exactly: `gh api repos/Jerome-Alvarez/TEMPRO/license` → 404,
   `repos/Jerome-Alvarez/TEMPRO` → `license: None`, and the repo root (at HEAD **and** at the pinned
   commit `d2752834…` that `config.py:23-25` pulls `user.zip` from) contains no LICENSE
   (`README.md, embedding_generator.zip, paper_results.zip, requirements.txt, tm_predictors.rar,
   user.zip`). Yet `models/tempro/LICENSE:1-3` is full MIT text ("Copyright (c) 2024 Jerome Anthony
   E. Alvarez"), `sources.yaml:4` declares `type: MIT`, `README.md:142` says "Code: MIT", and
   `comparison.yaml:11` advertises "MIT license enables unrestricted commercial use." Could not refute.

2. **Applied-literature inconsistency — REAL.** `sources.yaml:31-92` holds four `applied_literature`
   entries (NanoMelt :32, mech-interp bioRxiv :51, NBsTem :65, NbBench :78), but `BIOLOGY.md:34`
   says "No applied literature entries have been catalogued yet" and `comparison.yaml:16` lists
   "no independent benchmarking studies or applied literature citations yet" as a weakness. Three
   files contradict; could not refute.

3. **Four shipped TODO placeholders — REAL.** Confirmed literal `<!-- TODO: ... -->` at
   `README.md:91`, `MODEL.md:24`, `MODEL.md:41`, `BIOLOGY.md:36`. Could not refute.

4. **Wrong README/MODEL.md citation — REAL.** `README.md:148` mislabels the published Sci. Reports
   article (DOI `10.1038/s41598-024-70101-6`, two authors per `sources.yaml:14-21`) as a "Preprint
   (2024)", uses a divergent title ("…protein language model embeddings" vs sources' "…protein
   embeddings"), drops co-author Scott N. Dean (only "Alvarez J."), and the BibTeX :153-157 carries
   no DOI/journal; MODEL.md:24,41 likewise call it a "preprint". Could not refute.

5. **Tm output field-name inconsistency — REAL.** Verified `tempro/schema.py:63` = `tm`,
   `esmstabp/app.py:149` = `melting_temperature`, `temberture/schema.py:137` = `prediction`, and
   `tooling/field_glossary.yaml` contains only `temperature`/`ptm` (none of the three). The
   inconsistency is concrete and in code; the "TEMPRO's terse `tm` is the outlier" framing is a
   judgment (all three names differ, so it is equally a cross-model harmonization gap), but the
   factual claim holds. Could not refute.

6. **Emoji-heavy logging outlier — REAL.** `grep` confirms exactly 14 emoji log lines at the cited
   numbers (109,118,124,130,132,144,157,174,193,205,215,218,238,242). Siblings `esmstabp`, `esm2`
   = 0; `mpnn` = 3 (finding said 4 — trivial off-by-one, immaterial). TEMPRO at 14 is by far the
   highest. Could not refute.
