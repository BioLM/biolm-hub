# Review — `models/dnabert2/`

**Reviewer:** independent launch-gating review (round 1)
**Verdict:** Solid, conventional implementation. Plumbing matches the house pattern (esm2/omni_dna)
closely — config/schema/download/test wiring is correct, actions are canonical (`encode`, `log_prob`),
acquisition is the canonical `r2_then_hf` with the build-time imports declared in
`setup_download_layer(extra_pip_packages=...)`, and there is **no secret or `biolm-modal`/`.planning`
leakage**. No 🔴 launch-blockers found. The issues are documentation accuracy and knowledge-graph
consistency: an advertised context window the API can't accept, a GUE benchmark figure that disagrees
across the four knowledge files, a dangling `nt` model reference, a BIOLOGY/sources mismatch, a bare
`ValueError`, and an unresolved reviewer note left in the LICENSE.

Cross-checked against `models/esm2/` (reference) and `models/omni_dna/` (sibling DNA model), the
template `models/dummy/`, the error taxonomy in `models/commons/core/error.py`, and
`tooling/field_glossary.yaml`.

---

## 🔴 must-fix
_None found._

---

## 🟠 should-fix

### 1. Advertised 4–8 kbp context window is unreachable — schema caps input at 2048 **nucleotides**
- **Category:** Correctness / docs-vs-code
- **Location:** `schema.py:20` & `:31` (`max_length=DNABERT2Params.max_sequence_len`) vs
  `comparison.yaml:25,34,43`, `MODEL.md:63`, `BIOLOGY.md:16`, `README.md:48`
- **Detail:** The single constant `max_sequence_len = 2048` is used for two different units. In the
  schema it is the `max_length` of the input **string** (`DNABERT2EncodeRequestItem.sequence`), i.e. a
  cap of 2048 **characters = nucleotides** (~2 kbp). In `app.py` (`tokenizer(..., max_length=2048)`) the
  same value is a **token** truncation limit. Because BPE always yields fewer tokens than characters,
  the token limit never binds and the real, enforced ceiling is **2048 nt (~2 kbp)**. Yet
  `comparison.yaml`, `MODEL.md`, and `BIOLOGY.md` repeatedly sell an "effective context window of
  approximately 4–8 kbp." A user who picks DNABERT-2 for a 5 kbp regulatory region (as the docs invite)
  gets a validation rejection at 2049 nt. The docs describe the model's *theoretical* capacity, not what
  the deployed API accepts.
- **Fix:** Decide which is intended and make them agree. Either (a) raise the request `max_length` to the
  intended nucleotide span (e.g. ~8000) and keep the tokenizer's separate 2048-**token** truncation, so
  the advertised window is actually reachable; or (b) keep the 2048-nt cap and correct every doc claim to
  state the real input limit (~2 kbp). Do not reuse one constant for both a character cap and a token
  cap — give them distinct names.

### 2. GUE benchmark size is inconsistent across the four knowledge files
- **Category:** Knowledge graph / accuracy
- **Location:** `README.md:162` ("28 datasets, 7 task categories") vs `MODEL.md:79`,
  `BIOLOGY.md:128`, `comparison.yaml:17` (all "36 datasets across 9 task categories")
- **Detail:** The same benchmark is described with two different sizes within one model's docs. The
  DNABERT-2 paper's GUE is 28 datasets / 7 tasks; "36 / 9" appears to be a different (later/expanded)
  figure. Regardless of the true number, shipping two contradictory values is a credibility problem and
  exactly the kind of cross-file inconsistency the knowledge-graph review is meant to catch.
- **Fix:** Verify against Zhou et al. 2306.15006 and use the same number in all four files.

### 3. Bare `ValueError` in `log_prob` violates the error taxonomy
- **Category:** Errors
- **Location:** `app.py:234` — `raise ValueError("Tokenizer has no [MASK] token.")`
- **Detail:** Rubric A.5 and the `BioLMError` taxonomy (`models/commons/core/error.py`) require typed
  errors. A bare `ValueError` carries no stable `code` and is not classified by the `modal_endpoint`
  decorator as user vs system, so it surfaces as a generic uncoded 500. This is a system/config fault
  (a misconfigured tokenizer, effectively unreachable for DNABERT-2), so it should be a `ServerError`
  subclass.
- **Fix:** `from models.commons.core.error import ModelExecutionError` and
  `raise ModelExecutionError("Tokenizer has no [MASK] token.")`.

### 4. `comparison.yaml` references a model slug that does not exist (`nt`)
- **Category:** Knowledge graph / cross-model consistency
- **Location:** `comparison.yaml:52` (`alternatives: - model: "nt"`) and `:75`
  (`complements: - model: "nt"`)
- **Detail:** The file header states "All referenced model slugs must exist in `models/`," but there is
  no `models/nt/` directory (confirmed; the DNA models present are `evo`, `evo2`, `omni_dna`,
  `dna_chisel`). The structured `model:` keys are the strict ones — a tool consuming this YAML to build a
  selection graph would get a dangling edge. (`nt-v2-500m`/`nt-v2-250m`/`omni_dna-1b` also appear in
  prose at `:45,53` but prose is looser.)
- **Fix:** Either add the `nt` model, or drop the two structured `nt` entries (and fix the prose) until
  it exists. Confirm the other referenced slugs (`evo`, `evo2`, `omni_dna`, `esm2`, `dna_chisel`) — they
  all exist.

### 5. `BIOLOGY.md` says applied literature is "pending" while `sources.yaml` already lists 5 entries
- **Category:** Knowledge graph / internal consistency
- **Location:** `BIOLOGY.md:69` ("Applied literature entries for DNABERT-2 are pending curation.") and
  `:75` (`<!-- TODO: Add specific applied literature entries... -->`) vs `sources.yaml:42-92`
- **Detail:** `sources.yaml` has a fully populated `applied_literature:` block (Nature Comms 2025
  benchmark, enhancer classification 2509.25274, Gene-LLMs survey, DeepVRegulome, TFBS-Finder), but
  BIOLOGY.md's "Applied Use Cases" section claims they are still pending and carries a TODO. The two
  knowledge files disagree.
- **Fix:** Populate BIOLOGY.md's Applied Use Cases from the curated `sources.yaml` entries and remove the
  "pending"/TODO text.

### 6. LICENSE ships an unresolved reviewer note and no concrete copyright line
- **Category:** Licensing
- **Location:** `LICENSE:180-183` (NOTICE) — "...if not explicitly stated there, attribution is to
  'The DNABERT-2 Authors' **(flag for reviewer to verify)**."
- **Detail:** The license type (Apache-2.0) is correct and consistent with `sources.yaml:3-5`, and the
  NOTICE attribution to the authors is good practice. But the parenthetical "(flag for reviewer to
  verify)" is launch-residue that should not ship in a public legal file, and there is no concrete
  `Copyright [year] [holder]` line. Rubric A.8 flags inferred holders; this one is flagged but the flag
  itself is the residue.
- **Fix:** Resolve the holder (upstream `MAGICS-LAB/DNABERT_2` is Apache-2.0 — confirm the copyright
  line there) and either add a concrete `Copyright <year> <holder>` line or settle on "The DNABERT-2
  Authors" cleanly, deleting the reviewer parenthetical.

---

## 🟡 nits

### 7. Wrong memory comment in `config.py`
- **Category:** Correctness (comment)
- **Location:** `config.py:28` — `memory=4 * 1024,  # 8 GB`
- **Detail:** `4 * 1024` MB = 4 GB, not 8 GB. `README.md:199` and `MODEL.md:170` both correctly say 4 GB,
  so the comment is a copy-paste slip from esm2 (whose `8 * 1024  # 8GB RAM` is correct).
- **Fix:** Change the comment to `# 4 GB`.

### 8. Stray TODO markers shipping in knowledge-graph files
- **Category:** Knowledge graph (A.9 "no stray TODO")
- **Location:** `README.md:171`, `MODEL.md:90` (both "Extract exact GUE numerical scores..."),
  `BIOLOGY.md:75`, plus a code TODO at `schema.py:18` ("test how long sequences can be...").
- **Detail:** Rubric A.9 calls for no stray TODO placeholders in shipped docs. Note this is **systemic**
  across the repo (esm2, evo, omni_dna READMEs all carry TODOs; the `schema.py` TODO is verbatim shared
  with `omni_dna`), so it likely belongs to the global W14 docs cleanup rather than being a
  dnabert2-specific defect — flagging for completeness.
- **Fix:** Resolve or remove the TODOs (the GUE one is moot once finding #2 fills in the numbers).

### 9. Dead tokenizer kwargs at load time
- **Category:** Readability / simplicity
- **Location:** `app.py:126-133` — `AutoTokenizer.from_pretrained(..., padding=True, truncation=True, max_length=..., return_tensors="pt")`
- **Detail:** `padding`/`truncation`/`max_length`/`return_tensors` are call-time tokenization arguments,
  not `from_pretrained` arguments; they are no-ops here. The actual tokenization in `encode`/`log_prob`
  already passes them explicitly. Cargo-culted config that reads as if it configures truncation but does
  not.
- **Fix:** Drop the extra kwargs from the `from_pretrained` call.

### 10. `DNABERT2PredictLogProb*` class names retain a "Predict" prefix for the `log_prob` action
- **Category:** Naming / cross-model uniformity
- **Location:** `schema.py:50-72,90-99` (and imports in `app.py`, `config.py`, `fixture.py`)
- **Detail:** The action is `log_prob`, but the request/response classes are named
  `DNABERT2PredictLogProbRequest/Response`. The cleaner reference (`esm2`) uses `ESM2LogProbRequest`.
  Low priority because this "PredictLogProb" naming is shared by several models (`e1`, `esmc`, `evo`,
  `evo2`, `omni_dna`) — it's a repo-wide drift, not a dnabert2-only defect — but it is the kind of
  plumbing difference the uniformity north-star wants ironed out.
- **Fix:** Repo-wide, standardize on `…LogProbRequest/Response`; if renamed, keep a Pydantic alias.

### 11. Internal env name in `__main__` docstring
- **Category:** Open-source readiness / internal reference
- **Location:** `app.py:274` — `# Force deploy in QA/prod:`
- **Detail:** "QA" is an internal deployment environment name. Minor and systemic (esm2's docstring is
  worse: "Force deploy to 'qa' or 'main' environment"). Worth a sweep before public launch.
- **Fix:** Reword generically, e.g. `# Force deploy:`.

### 12. `log_prob` builds an L×L×vocab logits tensor in a single forward pass (no sub-batching)
- **Category:** Correctness / robustness (low confidence)
- **Location:** `app.py:237-249`
- **Detail:** For each sequence it stacks one masked copy per valid token (`num_valid ≈ L`) and runs a
  single forward producing `logits` of shape `[num_valid, L, vocab]`. At the 2048-nt input cap (~400-680
  BPE tokens, vocab ~4096) that is roughly 2.5-3 GB just for the logits, plus 12 layers of activations
  for an L×L batch. Probably fits a T4's 16 GB, but it scales as O(L²·vocab) and there is no chunking
  guard, so a future raise of the length cap (see finding #1) could OOM. Marked low-confidence — verify
  on a T4 at max length before relying on it.
- **Fix:** Chunk `valid_positions` into fixed-size sub-batches and accumulate, decoupling peak memory
  from sequence length.

---

## Definition-of-Done notes
- Standard layout, canonical actions, canonical `r2_then_hf` acquisition (with `huggingface_hub`/
  `transformers`/`einops` correctly declared in `setup_download_layer(extra_pip_packages=...)` for the
  build-time fallback import), typed `TestSuite` with integration + deployment cases and lazy fixtures —
  all **met**.
- Every request/response field carries a field-level `Field(description=...)` (no `Optional[Annotated]`
  description-drop trap); `log_prob` description matches the `field_glossary.yaml` verbatim entry — **met**.
- Knowledge-graph completeness/consistency — **partially met**: findings #2, #4, #5, #8 above.
- Licensing — **partially met**: correct type/attribution but reviewer-note residue (#6).
- No secret / `biolm-modal` / `.planning` leakage — **met** (only the minor "QA" docstring, #11).

## Verification

Adversarial re-verification of the six HIGH-severity findings (attempted to refute each; all
confirmed against concrete file:line evidence):

1. **Advertised 4-8 kbp context unreachable — schema caps at 2048 nt** — **REAL**.
   `schema.py:32,57` apply `max_length=DNABERT2Params.max_sequence_len` (=`2048`, `schema.py:19`)
   to the `sequence` *string* field, which Pydantic enforces as a 2048-*character* (= nucleotide,
   ~2 kbp) cap; `app.py:131,170,205` reuse the same `2048` as a tokenizer *token* truncation limit
   that never binds (BPE yields fewer tokens than chars). Yet `comparison.yaml:25,34,43`,
   `MODEL.md:63`, `BIOLOGY.md:16`, `README.md:48` sell "~4-8 kbp"; a >2048 nt input is rejected.
   README is internally contradictory too (`README.md:41` "2,048 nucleotides" vs `:48` "2,048 tokens").

2. **GUE size inconsistent across knowledge files** — **REAL**. `README.md:162` "28 datasets, 7 task
   categories" contradicts `MODEL.md:79`, `BIOLOGY.md:128`, `comparison.yaml:17`, all "36 datasets
   across 9 task categories". Confirmed verbatim.

3. **Bare `ValueError` in `log_prob` violates BioLMError taxonomy** — **REAL**. `app.py:234`
   `raise ValueError("Tokenizer has no [MASK] token.")` is an untyped builtin; `commons/core/error.py`
   defines the `BioLMError`/`ServerError`/`ModelExecutionError` taxonomy this should use. (Note: the
   branch is effectively unreachable for DNABERT-2's MLM tokenizer, so it is a defensive/config guard
   — best classified as a `ServerError` subclass, as the finding states.)

4. **`comparison.yaml` references non-existent slug `nt`** — **REAL**. `comparison.yaml:52`
   (alternatives) and `:75` (complements) use `model: "nt"`; `ls models/` confirms no `models/nt/`
   exists (DNA models present: `evo`, `evo2`, `omni_dna`, `dna_chisel`, `dnabert2`). Header
   `comparison.yaml:8` requires all referenced slugs to exist — dangling structured edge.

5. **BIOLOGY.md "pending" vs sources.yaml 5 entries** — **REAL**. `BIOLOGY.md:69` "Applied literature
   entries for DNABERT-2 are pending curation." + TODO `:75`, while `sources.yaml:42-92` lists a fully
   populated `applied_literature` block of 5 entries (Nature Comms 2025, 2509.25274, Gene-LLMs survey,
   DeepVRegulome 2511.09026, TFBS-Finder 2502.01311). Direct contradiction.

6. **LICENSE reviewer-note residue + no copyright line** — **REAL**. `LICENSE:182-183` ships
   "...attribution is to \"The DNABERT-2 Authors\" (flag for reviewer to verify)." in the NOTICE; the
   NOTICE (`:171-183`) carries no concrete `Copyright [year] [holder]` line. License type Apache-2.0
   is correct/consistent with `sources.yaml:3-5`, but the parenthetical is launch-residue.

**Summary: 6/6 confirmed REAL.**
