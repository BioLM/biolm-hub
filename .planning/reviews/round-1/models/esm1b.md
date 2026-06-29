# Review — `models/esm1b/` (Round 1)

## Summary

ESM-1b is a clean, well-documented single-variant port that closely tracks its sibling `models/esm2/`.
All standard files are present (`app.py`, `config.py`, `schema.py`, `test.py`, `download.py`, the 5-file
knowledge graph, `LICENSE`, `__init__.py`), the action set is the canonical `encode / predict / log_prob`,
errors use `ValidationError400`, logging uses `get_logger` with no `print`, and acquisition uses the
canonical `r2_then_hf` with `huggingface_hub` correctly listed in `setup_download_layer(extra_pip_packages=…)`
so the HF fallback can import it at build time. The MIT `LICENSE` is consistent with `sources.yaml`. No
secret / `biolm-modal` / `.planning` leakage in shipped files. Notably, esm1b makes a *better* choice than
esm2 in one place: its `LayerEmbedding` / `LayerPerTokenEmbeddings` are `ResponseModel` (esm2 mislabels these
as `RequestModel`).

No 🔴 must-fix issues found. The findings are convention/consistency and documentation-completeness items.
The most material is a real behavioral divergence from esm2 in the logits/vocab handling (esm1b emits 25
"vocab" columns including the non-canonical codes X/B/U/Z/O, where esm2 emits the 20 standard residues), which
also makes the `log_prob` normalization and several doc claims inaccurate. Beyond that: a `TODO` + approximate
benchmark numbers shipping in the public README, a mutable shared `default=` that deviates from esm2's
`default_factory`, a dead `toks_per_batch`, a dangling `verify_accuracy.py` reference, a 650M/652M
inconsistency, and `pending` placeholders in the primary section of `sources.yaml` that esm2 has filled.

---

## Findings

### 🟠 should-fix

#### 1. `vocab_tokens` includes non-canonical codes (X, B, U, Z, O) — 25 columns vs esm2's 20; contradicts the docs
- **Category:** correctness / cross-model consistency
- **Location:** `models/esm1b/app.py:112-116` (vocab construction), `:333-344` (encode logits), `:386-388`
  (predict logits), `:193-209` (log_prob normalization); docs `models/esm1b/MODEL.md:25`, `:65`,
  `models/esm1b/README.md:105-114`
- **Detail:** `self.vocab_tokens = [tok for tok in self.tokenizer.get_vocab().keys() if len(tok) == 1 and
  tok.isupper()]` selects every single-character uppercase token in the ESM-1b vocab. That set is the 20
  standard amino acids **plus the five non-standard / ambiguity codes** `X, B, U, Z, O`, i.e. 25 tokens. As a
  result `encode(include=["logits"])` and `predict` return 25 logit columns, and `log_prob` computes
  `log_softmax` over those 25 columns. By contrast, esm2 uses `self.alphabet.all_toks[4:-9]`, which is exactly
  the 20 standard residues, and its logits slice (`…[…, 4:-9]`) emits 20 columns. So the two sibling models
  disagree on the width and meaning of `logits` / `vocab_tokens`, and the `log_prob` pseudo-likelihoods are
  normalized over different denominators (25 vs 20) — they are not comparable and esm1b's are not what a
  "canonical-AA" normalization would produce. The docs compound this: `MODEL.md` says logits are "filtered to
  canonical single-letter uppercase amino acids" and the vocab is "20 standard AA", and the `README.md`
  `predict` example shows `"vocab_tokens": ["A", "R", "N", "D", …]` — both the count (20) and the order
  (ESM order actually starts `L, A, G, V, …`) are wrong relative to what the code emits.
- **Suggested fix:** Restrict `vocab_tokens` to the 20 standard residues to match esm2 (e.g. intersect the
  single-char uppercase tokens with the canonical 20, or drop `X/B/U/Z/O` explicitly), and regenerate the
  golden fixtures. If keeping X/B/U/Z/O is intentional, update `MODEL.md`/`README.md` to say the columns are
  "single-letter uppercase tokens including non-standard codes" and fix the README example's token list/order
  — but matching esm2 is strongly preferred given the repo's uniformity goal.

#### 2. README ships a `TODO` and approximate/unverified benchmark numbers
- **Category:** open-source readiness / knowledge-graph completeness
- **Location:** `models/esm1b/README.md:182-187`
- **Detail:** The "Published Results" table lists `Contact prediction L/5 ~0.50` and `SSP accuracy ~0.73`
  followed by `<!-- TODO: Replace approximate values with exact numbers from Rives et al. 2021 Table 1 and
  Figure 3 -->`. A literal `TODO` comment and self-described "approximate" numbers in a public README violate
  the knowledge-graph "no stray TODO / placeholders shipping" DoD item and risk publishing numbers the authors
  themselves flag as not yet verified.
- **Suggested fix:** Replace the `~` values with the exact figures from Rives et al. 2021 (cited), or remove
  the quantitative table and keep only the qualitative findings; delete the `TODO` comment either way.

#### 3. Mutable shared `default=ESM1bEncodeRequestParams()` deviates from esm2's `default_factory`
- **Category:** convention / latent correctness
- **Location:** `models/esm1b/schema.py:65-68`
- **Detail:** `params: ESM1bEncodeRequestParams = Field(default=ESM1bEncodeRequestParams(), …)` instantiates a
  single shared params object reused by every request that omits `params`. esm2 (and most other families —
  evo, igbert, igt5, msa_transformer, chai1, prody) use `default_factory=…RequestParams`, which yields a fresh
  instance per request. There is no live bug today (the app reads `payload.params.repr_layers` and rebuilds a
  new list rather than mutating it), but this is a latent mutable-default footgun and a needless plumbing
  difference from the sibling model.
- **Suggested fix:** `params: ESM1bEncodeRequestParams = Field(default_factory=ESM1bEncodeRequestParams, …)`.

---

### 🟡 nits

#### 4. Dead code: `self.toks_per_batch = 4096` is set but never used
- **Category:** simplicity / leftover scaffolding
- **Location:** `models/esm1b/app.py:107-108`
- **Detail:** Unlike esm2 (which passes `toks_per_batch` to `FastaBatchedDataset.get_batch_indices`), esm1b
  runs a single forward pass over the whole batch and never reads `self.toks_per_batch`. The attribute and its
  "Tokens per batch for batching" comment are copy-paste residue from esm2 and are misleading (there is no
  token-based batching here). `MODEL.md:168` also lists `tokens_per_batch | 4096` as if it were operative.
- **Suggested fix:** Remove the assignment and comment (and the `MODEL.md` row), or wire it in if batching is
  ever intended.

#### 5. `sources.yaml` primary-section placeholders lag esm2
- **Category:** knowledge-graph completeness / consistency
- **Location:** `models/esm1b/sources.yaml:37` (`md_r2: pending`), `:42` (`commit: ''`), `:43`
  (`snapshot_r2: pending`), `:20` (`arxiv: ''`)
- **Detail:** For the primary paper and GitHub source repo, esm2 fills `md_r2`, `commit`, and `snapshot_r2`;
  esm1b leaves them `pending`/empty. (The `pdf_r2: pending` / `md_r2: pending` entries under
  `applied_literature` match esm2's convention and are fine.) The PNAS paper legitimately has no arXiv id (it
  has a DOI), so `arxiv: ''` there is acceptable, but the `commit`/`snapshot_r2` for `facebookresearch/esm`
  could be pinned the way esm2 does.
- **Suggested fix:** Populate `commit`, `snapshot_r2`, and the primary `md_r2` (or confirm these R2 assets are
  intentionally deferred), to match esm2's completeness.

#### 6. `MODEL.md` references a non-existent `verify_accuracy.py`
- **Category:** docs / dead reference
- **Location:** `models/esm1b/MODEL.md:91` — "Additional biological verification (from `verify_accuracy.py`)"
- **Detail:** No `verify_accuracy.py` exists anywhere in the repo (esm1b is the only file that references it).
  This points an outside reader at a script that does not ship.
- **Suggested fix:** Drop the "(from `verify_accuracy.py`)" parenthetical; the verification table reads fine
  standalone.

#### 7. Parameter count stated inconsistently (652M vs 650M)
- **Category:** consistency
- **Location:** `models/esm1b/README.md:3`, `:18`, `:32` and `MODEL.md:20` say **652M**; `comparison.yaml:11`,
  `:16` and `sources.yaml:47` (and the HF repo name `esm1b_t33_650M_UR50S`) say **650M**
- **Detail:** The model's own size is given as 652M in README/MODEL but 650M in the YAML knowledge-graph files.
  (The other "650M" mentions referring to ESM-2-650M are correct.)
- **Suggested fix:** Standardize on one — e.g. "650M (≈652M exact)" — across all five files.

#### 8. `fixture.py` hardcodes input sequences rather than sourcing them (esm2 reads inputs from R2)
- **Category:** consistency / test hygiene
- **Location:** `models/esm1b/fixture.py:24-27`
- **Detail:** `TEST_SEQUENCE_SHORT` and `TEST_SEQUENCE_MASKED` are hardcoded in the generator (the medium one
  correctly reuses `STANDARD_PROTEIN`). esm2's `fixture.py` instead pulls its canonical inputs from R2. This
  is a dev-only generation script (no module-scope R2/network, so the lazy-load rule is satisfied) and there is
  no shared "masked" asset to reuse, so impact is low — but it is a plumbing divergence from the sibling.
- **Suggested fix:** Optionally align with esm2 (source inputs from R2 / shared assets) for uniformity.

#### 9. `log_prob` is labelled "Pseudo-log-likelihood" but computes a single unmasked forward pass (wt-marginal) — family-wide
- **Category:** field-description accuracy (low confidence; not esm1b-specific)
- **Location:** `models/esm1b/schema.py:206-208`, `BIOLOGY.md:43` ("computes the pseudo-log-likelihood")
- **Detail:** The implementation does one forward pass on the unmasked sequence and sums `log P(x_i | full
  context)` — the "wt-marginal" score — not a true pseudo-log-likelihood (which masks each position in turn).
  The app docstring, README, and MODEL.md describe the actual single-pass computation correctly; only the
  schema field and BIOLOGY.md use the term "pseudo-log-likelihood". esm2 uses the identical wording and
  implementation, so this is a family-wide naming imprecision — flagged here only so the aggregating reviewer
  can decide whether to fix it consistently across the ESM family.
- **Suggested fix:** Either reword to "Summed log-likelihood of the sequence under the model (single
  unmasked forward pass)" family-wide, or leave as-is for uniformity.

---

## Definition-of-Done quick audit
- Standard layout / `ModelFamily` with `modal_class_name`, `action_schemas`, tags — **met**.
- Canonical actions (`encode`/`predict`/`log_prob`), no invented verbs — **met**.
- Uniform schema field names (`items`, `params`, `sequence`, `embeddings`/`logits`/`log_prob`, batch under
  `results`); descriptions render (no `Optional[Annotated[Field]]` drops) — **met**.
- Typed errors (`ValidationError400`), structured logging, no `print` — **met**.
- Canonical acquisition (`r2_then_hf`), self-populates R2, build-order rule (`huggingface_hub` in
  `extra_pip_packages`) — **met**.
- Per-model MIT `LICENSE` consistent with `sources.yaml` — **met**.
- Tests: `TestSuite` with integration + deployment, lazy fixtures, shared `STANDARD_PROTEIN` + shared
  `_validate_log_prob` — **met**.
- Knowledge graph 5 files present, slug/display_name consistent with config — **met**, but **partially** on
  "no placeholders / fully accurate": README `TODO` + approximate benchmarks (#2), `sources.yaml` `pending`
  primary entries (#5), `verify_accuracy.py` dangling ref (#6), 650M/652M inconsistency (#7), and the
  vocab/logits doc mismatch (#1).

---

## Verification

Adversarial re-check of the three HIGH-severity findings flagged for `esm1b` (re-read of
`app.py`, `schema.py`, `README.md`, `MODEL.md`, plus cross-check against `models/esm2/` and an
empirical Pydantic v2.11.7 default-copy test).

### Finding 1 — vocab_tokens includes non-canonical codes (X,B,U,Z,O), 25 cols vs esm2's 20 → **REAL**
- `app.py:112-116` selects every single-char uppercase vocab token (`len==1 and tok.isupper()`),
  which is the 20 standard AAs **plus** X,B,U,Z,O = 25 (the code comment line 110 even claims
  "standard 20 amino acids", a code/comment mismatch). `app.py:336-344` (encode) and `:386-398`
  (predict) emit those 25 columns; `log_prob` log_softmax (`:193-209`) normalizes over 25.
- esm2 uses `self.alphabet.all_toks[4:-9]` = 20 (`models/esm2/app.py:134`, slices `…,4:-9` at
  `:363,:417`; log_prob comment "[L, 20]" `models/esm2/app.py:455-460`). Denominators genuinely
  differ (25 vs 20) → pseudo-likelihoods not comparable across the siblings.
- Docs inaccurate: README `:114` "number of canonical amino acid tokens", `:244` "filtered to
  canonical single-letter uppercase amino acids", MODEL.md `:153` "slice to canonical AA vocab" all
  imply 20 canonical, but code returns 25 (incl. non-canonical). Predict example `README:110`
  `vocab_tokens: ["A","R","N","D",...]` is wrong count (should be 25) and wrong order (actual ESM
  order starts L,A,G,V,...). Confirmed in code.

### Finding 2 — README ships a TODO comment + approximate/unverified benchmarks → **REAL**
- `README.md:184` "Contact prediction L/5 (long-range) | ~0.50" and `:185` "SSP accuracy (3-state)
  | ~0.73", followed by literal `:187` `<!-- TODO: Replace approximate values with exact numbers
  from Rives et al. 2021 Table 1 and Figure 3 -->`. The TODO and self-described approximate (`~`)
  numbers are demonstrably present in a file slated to ship publicly.

### Finding 3 — "mutable shared default=ESM1bEncodeRequestParams() footgun" → **REFUTED**
- The load-bearing claim ("instantiates a single shared params object reused by every request") is
  false under Pydantic v2. Pydantic smart-deepcopies non-factory mutable defaults per instance:
  empirical test on pydantic 2.11.7 with the same nested-model + list-default shape gives
  `a.params is b.params == False` and mutating one instance's nested list does NOT leak into another.
  `RequestModel` config is only `ConfigDict(strict=True, extra="forbid")`
  (`models/commons/model/pydantic.py:30`), nothing that disables default copying. The finding itself
  concedes "No live bug today." What remains is a cosmetic `default=` vs `default_factory=`
  (`schema.py:65-68` vs `models/esm2/schema.py:77`) consistency nit — not a mutable-shared-state
  footgun and not HIGH severity. Refuted on the substantive mechanism.
