# Review — `models/evo/` (Round 1)

**Reviewer verdict:** Strong, clean implementation that faithfully wraps the upstream `evo-model`
library and follows the house plumbing (commons decorators, `ModelMixinSnap`, `r2_then_library`
acquisition, `setup_download_layer`/`setup_source_layer`, typed Pydantic schemas with rendering
`Field(description=...)`). Actions (`log_prob`, `generate`) are from the closed set and match intent.

However, there is **one launch-gating (🔴) defect**: the model **fails the repo's own
`bm kb validate evo`** (exit 1) because `comparison.yaml` references a model slug (`nt`) that does
not exist under `models/`. There are also several should-fix doc/accuracy issues, the most important
being a **`generated` output field whose description is factually wrong** (claims it includes the
prompt; the Evo library returns continuation-only — verified against the library source and
contradicting sibling `evo2`).

Cross-checks performed: schema field descriptions vs. `app.py` runtime; `app.py` vs. upstream
`/Users/qamar/dev/evo/evo/generation.py`; license vs. upstream `evo` LICENSE & citation; KG slug
references vs. `models/` directory (+ ran `cli.kb.validate_cmd`); conventions vs. `models/esm2` and
`models/dummy`; `prompt`/`generated` naming vs. `evo2`/`progen2`/`zymctrl`.

---

## 🔴 Must-fix before launch

### 1. `comparison.yaml` references a non-existent model slug `nt` — fails `bm kb validate`
- **Category:** Knowledge graph / cross-model consistency / DoD
- **Location:** `models/evo/comparison.yaml:55` (alternatives) and `:66` (complements)
- **Detail:** `comparison.yaml` lists `- model: "nt"` under both `alternatives` and `complements`,
  but there is no `models/nt/` directory (DNA models present are `dnabert2`, `omni_dna`, `evo2`,
  `dna_chisel`). The file's own header states "All referenced model slugs must exist in models/",
  and the repo validator enforces this. I ran it:
  ```
  $ python -c "from cli.kb import validate_cmd; validate_cmd(model='evo')"
  evo
    ERROR: comparison.yaml alternative 'nt' not in models/
    ERROR: comparison.yaml complement 'nt' not in models/
  2 errors → typer.Exit(1)
  ```
  `cli/kb.py:275-287` appends these as **errors** (not warnings) and `:322-323` raises
  `typer.Exit(1)`. So `bm kb validate evo` is red, which is a Definition-of-Done blocker for W14.
- **Fix:** Replace the `nt` entries with an existing DNA model slug (`dnabert2` or `omni_dna`) in
  both the `alternatives` and `complements` blocks, or add the `nt` model. Also update the prose in
  `weaknesses`/`dont_use_when` that says "use nt, dnabert2, or evo2" / "use NT" to match. Re-run
  `bm kb validate evo` until green.

---

## 🟠 Should-fix

### 2. `generate` → `generated` field description is wrong (claims it includes the prompt)
- **Category:** Correctness / schema-vs-runtime mismatch / docs
- **Location:** `models/evo/schema.py:137-139`; mirrored in `README.md:113` (JSON example) and
  `README.md:120` ("full output sequence (prompt + newly generated tokens)").
- **Detail:** The field says *"Full generated DNA sequence, including the prompt and newly generated
  nucleotides."* The Evo library returns **only the newly generated continuation, not the prompt**.
  Verified in `/Users/qamar/dev/evo/evo/generation.py`: `Generator.generate` writes only new tokens
  into the `generation` tensor (the prompt lives in `x`/`input` and is never concatenated), returns
  `generation[:, :i+1]`, and `generate(...)` detokenizes exactly those into `generated_seqs`.
  `app.py:205` assigns `generated_seq = seqs[0]` directly. The sibling model `evo2` documents this
  correctly (`models/evo2/schema.py:224`: *"Autoregressive continuation of the input prompt"*), so
  Evo is both wrong and inconsistent with its closest peer. A caller trusting the description would
  mis-handle outputs (e.g., try to strip a prompt prefix that isn't there).
- **Fix:** Change the description to e.g. *"Newly generated DNA continuation (does NOT include the
  prompt), in A/C/G/T."* and update `README.md:113-120` (example comment + prose) to match.

### 3. `EvoModel` class docstring advertises `encode()` and `predict()` methods that don't exist
- **Category:** Readability / correctness (misleading docs)
- **Location:** `models/evo/app.py:85-91`
- **Detail:** The docstring says the class "implements: encode(); predict() => per-position logits;
  log_prob() => total log-prob; generate() => sequence sampling." Only `log_prob` and `generate` are
  defined (and `config.py` declares only those two actions). `encode`/`predict` are leftovers and are
  misleading to a contributor.
- **Fix:** Remove the `encode()` and `predict()` lines so the docstring lists only `log_prob()` and
  `generate()`.

### 4. `LICENSE` ships an unresolved reviewer note + speculative copyright holder
- **Category:** Licensing / open-source readiness
- **Location:** `models/evo/LICENSE:180-183`
- **Detail:** The NOTICE block contains: *"The exact upstream copyright holder is listed in the
  upstream repository; if not explicitly stated there, attribution is to 'The Evo Authors' (flag for
  reviewer to verify)."* This "(flag for reviewer to verify)" review-note placeholder must not ship
  publicly. The upstream `/Users/qamar/dev/evo/LICENSE` is the bare Apache-2.0 template with **no**
  copyright line, so the correct course is to attribute to the named authors/institutions (the NOTICE
  already names "Arc Institute, Stanford University, and Together Computer") and drop the speculative
  sentence.
- **Fix:** Finalize attribution (e.g., "Copyright the Evo authors — Arc Institute, Stanford
  University, and Together Computer") and delete the "(flag for reviewer to verify)" parenthetical
  and the conditional sentence.

### 5. `TODO` placeholders shipping in the knowledge-graph docs
- **Category:** Knowledge graph completeness / open-source readiness
- **Location:** `models/evo/README.md:186` and `models/evo/MODEL.md:72` (identical
  `<!-- TODO: Extract exact numerical values from Nguyen et al. Science 2024 Figures 2-4 ... -->`)
- **Detail:** Rubric A.9/C requires "no stray TODO/pending/template placeholders shipping." These are
  HTML comments (not rendered) but are clearly unfinished-work markers in files meant to be public.
- **Fix:** Either extract the numbers from the paper and fill the adjacent tables, or remove the TODO
  comments (and soften the surrounding "Approximate Performance" tables to stand on their own).

### 6. `sources.yaml` primary `source_repos` left as `pending` / empty `commit`
- **Category:** Knowledge graph completeness / provenance
- **Location:** `models/evo/sources.yaml:48-56` (`commit: ''` and `snapshot_r2: pending` for both the
  `evo-design/evo` and `togethercomputer/stripedhyena` repos)
- **Detail:** The reference model `esm2/sources.yaml:46-50` pins a concrete `commit`
  (`2b369911…`) and a real `snapshot_r2` tarball. Evo leaves both repos unpinned and snapshots
  `pending`, weakening reproducibility/provenance. (Note: `bm kb validate` does not check
  `snapshot_r2`, so this is not caught by tooling — but it diverges from the house standard.)
- **Fix:** Pin both `commit` SHAs and upload + reference the repo snapshots (or set a deliberate
  policy and remove the `pending` markers).

### 7. `README` "Paper" link points to an arXiv ID the Evo paper doesn't have
- **Category:** Docs / dead-or-wrong link
- **Location:** `models/evo/README.md:264` (`Paper: [arXiv:2403.19444](https://arxiv.org/abs/2403.19444)`)
- **Detail:** Every other reference in evo's own docs (and the upstream `evo` README) cites the paper
  via the Science DOI `10.1126/science.ado9336` and bioRxiv `10.1101/2024.02.27.582234`; the upstream
  README has **no** arXiv version. The `arXiv:2403.19444` link is inconsistent and almost certainly
  not the Evo paper. (Confidence: moderate-high — I could not fetch the URL, but the safe fix applies
  regardless.)
- **Fix:** Replace with the Science DOI (`https://doi.org/10.1126/science.ado9336`) and/or the bioRxiv
  link, matching the BibTeX/`sources.yaml`.

---

## 🟡 Nits

### 8. Citation author typo: "Durber" should be "Durrant"
- **Category:** Docs / attribution accuracy
- **Location:** `models/evo/README.md:248` ("Durber MG") and `:255` (BibTeX `Durber, Matthew G`)
- **Detail:** Upstream and `sources.yaml:25` correctly use "Matthew G. Durrant". The README misspells
  the author in both the reference list and BibTeX. (Also minor: BibTeX drops the accent in
  "Christopher Ré" → "Re"; upstream uses "Ré".)
- **Fix:** Correct "Durber" → "Durrant" in both places.

### 9. `comparison.yaml` overstates usable context (8 kbp) vs the 4,096-nt API cap
- **Category:** Docs / cross-file consistency
- **Location:** `models/evo/comparison.yaml:18` (strength: "8 kbp context window covers most
  prokaryotic genes … in a single inference pass")
- **Detail:** `EvoParams.max_sequence_len = 4096` (`schema.py:20`) caps inputs at 4 kbp — half the
  claimed 8 kbp. README/MODEL correctly note the 4,096-nt API cap, so `comparison.yaml` is the
  outlier. Mild overstatement of what the deployed endpoint actually accepts.
- **Fix:** Either raise the cap to 8192 (the 8k variant's native context) or qualify the strength to
  "up to 4 kbp per request (8k native context)".

### 10. Dead defensive branch in `generate`
- **Category:** Simplicity / dead code
- **Location:** `models/evo/app.py:200-203`
- **Detail:** `evo.generation.generate()` always returns a 2-tuple `(seqs, scores)` (see library
  signature `-> Tuple[List[str], List[float]]`); the `else: seqs, scores, _ = generate_result`
  branch is unreachable for the pinned `evo-model==0.4`.
- **Fix:** Simplify to `seqs, scores = self.generate_fn(...)` (keep a comment if you want to hedge
  against future library versions).

### 11. Cross-model schema-class naming inconsistency for `log_prob`
- **Category:** Consistency (repo-wide; evo follows the DNA-model convention)
- **Location:** `models/evo/schema.py:36,44,79,83` (`EvoPredictLogProb*`)
- **Detail:** Evo names its `log_prob` schemas `EvoPredictLogProb…`, matching `dnabert2`
  (`DNABERT2PredictLogProb…`) but **not** `esm2` (`ESM2LogProb…`). The action is `log_prob` (no
  `predict`), so the `Predict` prefix is vestigial. This is a repo-wide split (DNA vs protein
  families) rather than an evo-only defect; flagging for a consistency pass. Field names themselves
  (`log_prob`, `items`, `results`, `score`) are correct and match `tooling/field_glossary.yaml`.
- **Fix:** Pick one convention repo-wide (preferably `<Model>LogProb…`) and align; keep a Pydantic
  alias if any external title is depended upon.

---

## Notes / things checked that are OK
- Acquisition: `download.py` uses canonical `r2_then_library` with an `init_fn` that points the HF
  cache at the R2-managed dir (`setup_hf_cache_env`), self-populating the bucket — correct pattern.
- Build order: unlike esm2 (which passes `extra_pip_packages` to `setup_download_layer`), evo
  installs `evo-model`/torch/flash-attn into the image **before** calling `setup_download_layer`, so
  the layer's build-time `from evo import Evo` resolves. Valid (and arguably required given the
  flash-attn `--no-build-isolation` toolchain). Not a defect, just a different-but-correct ordering.
- Field rendering: all request/response `Field(description=...)` render in `model_json_schema()`
  (top-level `Annotated[..., Field]`; `seed` uses `Optional[int] = Field(...)`, not the
  `Optional[Annotated[..., Field]]` foot-gun) — no silently-dropped descriptions.
- Errors/logging: input validation goes through `validate_dna_unambiguous` (raises in-schema);
  `get_logger` used, no `print` in runtime code; no full-sequence/secret logging.
- `score` (generate) description "Average log-probability per token" matches the library
  (`np.mean(logprobs)` over generated tokens) — accurate.
- `log_prob` uses `reduce_method="sum"`; description "Log-likelihood of the sequence under the model"
  matches the glossary's autoregressive variant.
- No `biolm-modal` / `.planning` / local-path / internal-domain leakage in shipped files. (`app.py:223`
  "QA/prod" mirrors esm2's "qa" comment — a repo-wide cleanup item, not evo-specific.)
- Hardcoded tiny DNA fixtures (`ACGTAC`, `ACGT`) are consistent with the other DNA models
  (`dnabert2`, `evo2`); there is no `STANDARD_DNA` in `commons/testing/shared_assets.py` to reuse
  (only protein assets), so this is a repo-wide gap, not an evo defect.

## Verification

Adversarial re-check of the 7 HIGH-severity findings (attempted to refute each against the actual code).

1. **comparison.yaml references non-existent slug `nt` — fails `bm kb validate evo`** — **REAL.** `models/` has no `nt/` dir (DNA models: dnabert2, omni_dna, evo2, dna_chisel); `comparison.yaml:55` (alternatives) and `:66` (complements) list `model: "nt"`. Replicating the validator slug-check (`cli/kb.py:264-287`, SKIP_DIRS at `:25`) yields exactly `alternative 'nt' not in models/` + `complement 'nt' not in models/`; `total_errors>0` → `typer.Exit(1)` (`cli/kb.py:322-323`). (Full `bm` CLI can't run in this env due to an unrelated missing `requests` dep, but the slug logic is reproduced directly.)
2. **`generated` description wrongly claims output includes the prompt** — **REAL.** Upstream `/Users/qamar/dev/evo/evo/generation.py`: `Generator.generate` writes only sampled `new_idx` into the `generation` tensor (prompt lives in `x`/`input`, never concatenated) and returns `generation[:, :i+1]`; module `generate()` detokenizes only `output_ids` → continuation-only `generated_seqs`. `app.py:205` assigns `seqs[0]` directly. So `schema.py:137-139` ("including the prompt and newly generated nucleotides") and README `:120` are wrong; evo2 documents it correctly. Value returned is correct; the contract text is not.
3. **Class docstring lists encode()/predict() that don't exist** — **REAL.** `app.py:85-91` docstring claims `encode()` and `predict() => per-position logits`, but only `log_prob()` (`:132`) and `generate()` (`:157`) are defined, and `config.py:80-91` registers only `LOG_PROB` + `GENERATE`. Leftover template text.
4. **LICENSE ships an unresolved reviewer note** — **REAL.** `LICENSE:181-183` contains "...if not explicitly stated there, attribution is to \"The Evo Authors\" (flag for reviewer to verify)." A review placeholder; must not ship publicly.
5. **TODO placeholders in README.md and MODEL.md** — **REAL.** Identical `<!-- TODO: Extract exact numerical values from Nguyen et al. Science 2024 Figures 2-4 ... -->` at `README.md:186` and `MODEL.md:72`. Unfinished-work markers in public-facing files (HTML comments, not rendered).
6. **sources.yaml primary source_repos unpinned** — **REAL (factual claim accurate).** `sources.yaml:46-56`: both repos (evo-design/evo, togethercomputer/stripedhyena) have `commit: ''` and `snapshot_r2: pending`; reference `esm2/sources.yaml:48-49` pins `2b369911...` + a real tarball. Provenance/standard divergence. As the finding itself notes, `bm kb validate` does not check this, so it is not a tooling-red blocker (unlike #1).
7. **README 'Paper' link uses an arXiv ID Evo does not have** — **REAL.** `README.md:264` links `arXiv:2403.19444`. WebFetch of https://arxiv.org/abs/2403.19444 resolves to "Leveraging Expert Input for Robust and Explainable AI-Assisted Lung Cancer Detection in Chest X-rays" (Rafferty, Ramaesh, Rajan; cs.LG/cs.CV) — unrelated to Evo. Correct citation is Science DOI 10.1126/science.ado9336 / bioRxiv 10.1101/2024.02.27.582234 (both already in sources.yaml/README).

**Summary: 7/7 REAL.** All confirmed against the cited code/files; none refuted. Severity nuance: #1 is the only one that turns `bm kb validate evo` red (W14 DoD blocker); #2 and #4 are wrong public-contract/placeholder text; #3/#5/#7 are doc/template defects; #6 is a provenance gap not caught by tooling.
