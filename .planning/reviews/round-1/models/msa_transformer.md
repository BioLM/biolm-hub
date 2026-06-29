# Review — `models/msa_transformer/`

**Reviewer pass:** Round-1 independent, launch-gating.
**Verdict:** Solid, faithfully follows the ESM-family house pattern (it is effectively an MSA-shaped sibling of
`esm2`). Schema is clean, every field description renders, errors are typed, logging is structured, weights
self-populate via `r2_then_library`, and the 5-file knowledge graph is present and internally consistent
(slug `msa-transformer` / display `MSA Transformer` match across config, schema, sources, comparison). No
correctness bug found in the inference path. The findings are: one systemic internal-env leak (shared with
~35 other models), one knowledge-graph completeness gap (source-repo commit/snapshot left blank though the
code pins the exact commit), and a handful of nits (misleading token-layout comments, one over-stated doc
phrase, minor cross-model inconsistencies).

Cross-checked against `models/esm2/` (sibling reference) and `models/dummy/` (template), the rubric, and
`tooling/field_glossary.yaml`.

---

## 🔴 must-fix
_None specific to this model._ (The `qa`-env reference below is rubric-🔴 by the letter, but it is template-wide
and only fixable globally — reported at 🟠 with that caveat so it can be de-duplicated.)

---

## 🟠 should-fix

### 1. Internal Modal env name `qa` leaks in shipped usage comment
- **category:** internal leakage
- **location:** `models/msa_transformer/app.py:261` (`# Force deploy to "qa" or "main" environment:`)
- **detail:** `qa` is a real internal BioLM Modal environment name — `models/commons/modal/deployment.py:41`
  treats `current_env in ("qa", "main")` as production. The rubric explicitly lists "internal `qa` env" in a
  shipped file as a 🔴 leak. I am reporting it at 🟠 only because it is **template-wide**: the identical comment
  appears in ~35 `models/*/app.py` files plus `commons/modal/deployment.py`, so it must be fixed once,
  globally (a W14 / global-reviewer item), not in this model alone. Flagging here for completeness.
- **suggested fix:** Decide globally how to phrase the deploy comment for the public repo (e.g. "Force deploy
  even when the active Modal environment is a protected one"), then apply across all models; remove the literal
  internal env name from public-facing comments/help.

### 2. `sources.yaml` source-repo `commit`/`snapshot_r2` left blank though the code pins the exact commit
- **category:** knowledge graph (completeness/consistency)
- **location:** `models/msa_transformer/sources.yaml:36-42` (`commit: ''`, `snapshot_r2: pending`)
- **detail:** `app.py:39/48` and `download.py` both pin fair-esm at commit
  `2b369911bb5b4b0dda914521b9475cad1656b2ac`, and the sibling `esm2/sources.yaml:48-49` already records that
  same repo as `commit: 2b369911bb5b4b0dda914521b9475cad1656b2ac` with a real
  `snapshot_r2: knowledge-base/models/esm2/primary/repos/esm-2b369911.tar.gz`. Here both fields are empty /
  `pending` for the **primary** source repo, so the knowledge graph is incomplete and inconsistent with the
  code and with esm2 (same library, same commit). (Note: the `pending` values under `applied_literature`
  pdf_r2/md_r2 are a sanctioned pattern — esm2 uses them and `dummy/sources.yaml` documents them — so those are
  *not* flagged.)
- **suggested fix:** Set `commit: 2b369911bb5b4b0dda914521b9475cad1656b2ac` and point `snapshot_r2` at the
  existing esm snapshot tarball (or this model's own archived copy) instead of `pending`.

---

## 🟡 nits

### 3. Misleading BOS/EOS token-layout comments (code is correct, comments are not)
- **category:** readability / correctness-of-comments
- **location:** `models/msa_transformer/app.py:207, 218, 237, 244`
- **detail:** The MSA Transformer alphabet (`esm_msa1b_t12_100M_UR50S`) prepends BOS but does **not** append
  EOS, so a tokenized row is length `L+1` and the row-attention map is `[L+1, L+1]`. The comments claim
  "`seq_len+2` ... The +2 accounts for BOS and EOS tokens" (line 237) and "Remove BOS/EOS tokens (first and
  last positions)" (line 244); the representation-shape comments (207, 218) likewise omit the BOS dimension.
  The slicing `[..., 1:seq_len+1, ...]` is anchored from the front, so it yields the correct `[L,L]` / `[L,d]`
  result regardless — there is **no functional bug** — but the comments will mislead a future maintainer into
  thinking a trailing special token is being stripped. (Confidence: high on the no-EOS fact; the only impact is
  comment accuracy.)
- **suggested fix:** Correct the comments to "BOS only (no EOS for MSA Transformer); tokens are `seq_len+1`,
  slice removes the leading BOS."

### 4. README calls the 256-depth cap "recommended" but it is a hard, enforced limit
- **category:** docs accuracy
- **location:** `models/msa_transformer/README.md:54` ("Maximum MSA depth: 256 sequences (recommended)")
- **detail:** `schema.py:100` enforces `max_length=MSATransformerParams.max_msa_depth` (256) on `msa`, so an MSA
  of >256 rows is **rejected** with a validation error, not merely discouraged. "(recommended)" understates the
  behavior. (The Actions table at README:72 correctly says "2--256 sequences".)
- **suggested fix:** Drop "(recommended)" — state it as a hard maximum, matching the Actions table and MODEL.md.

### 5. `comparison.yaml` references models not present in this repo
- **category:** consistency (cross-model)
- **location:** `models/msa_transformer/comparison.yaml:49-55, 70-72` (`model: poet`, `model: saprot`)
- **detail:** `poet` and `saprot` have no directory under `models/`. They are referenced as `alternatives` /
  `complements` here (and in several other models' comparison.yaml: esm2, esm1v, esmc, prostt5, ...), so this is
  likely an intentional reference to the broader BioLM catalog rather than this OSS subset — but in a catalog UI
  (`bm serve`) these become dead cross-links. Low confidence that it is a defect vs. intended.
- **suggested fix:** Confirm the policy for referencing not-shipped models in `comparison.yaml`; if cross-links
  must resolve, gate the referenced slugs to shipped models (or mark external ones explicitly).

### 6. `Task.STRUCTURE_PREDICTION` tag is inconsistent with esm2's treatment of contacts
- **category:** consistency (tags)
- **location:** `models/msa_transformer/config.py:37`
- **detail:** This model tags `task=[EMBEDDING, STRUCTURE_PREDICTION]` for its unsupervised contact output, but
  `esm2` — which also produces a contact map — does **not** claim `STRUCTURE_PREDICTION` (`esm2/config.py:62`).
  Neither model declares an `OutputModality.STRUCTURE`, which is correct (both emit 2-D contact maps, not 3-D
  coordinates). The inconsistency is only in the `task` tag. Pick one convention for "predicts contacts" so the
  two siblings tag the same capability the same way. Low confidence on direction.
- **suggested fix:** Either add `STRUCTURE_PREDICTION` to esm2, or drop it here and rely on `EMBEDDING` +
  documentation — whichever the tag taxonomy intends for contact-only models.

### 7. Nested response sub-models subclass `ResponseModel` here but `RequestModel` in esm2
- **category:** consistency (schema plumbing)
- **location:** `models/msa_transformer/schema.py:123, 132` (`LayerEmbedding(ResponseModel)`,
  `LayerPerTokenEmbeddings(ResponseModel)`)
- **detail:** esm2's identically-named sub-models subclass `RequestModel` (`esm2/schema.py:129, 136`). Both
  render descriptions fine (verified via `model_json_schema()`), so there is no functional effect, but it is a
  "plumbing differs, not the science" divergence. If anything msa_transformer's choice (`ResponseModel` for
  response sub-models) is the more correct one; esm2 is the outlier.
- **suggested fix:** Standardize the base class for response sub-models across the ESM family (prefer
  `ResponseModel`), and update whichever side is the outlier.

### 8. Fixture query row duplicates a shared asset instead of importing it
- **category:** tests (shared-asset reuse)
- **location:** `models/msa_transformer/fixture.py:37` (and the 25-mer used at 83/99)
- **detail:** The single/batch query row
  `MKTVRQERLKSIVRILERSKEPVSGAQLAEELSVSRQVIVQDIAYLRSLGYNIVATPRGYVL` is the first 61 residues of the shared
  `STANDARD_PROTEIN_STABILITY` (65-mer) in `models/commons/testing/shared_assets.py:29`. The homolog rows must
  be synthetic (no shared *MSA* asset exists, so hard-coding the alignment is justified), but the query row
  could import the shared constant to avoid silent drift. Very minor.
- **suggested fix:** Optionally build the query row from `STANDARD_PROTEIN_STABILITY[:61]` (import from
  `shared_assets`) and keep the synthetic homologs local.

---

## Definition-of-Done audit (per-model items)
- **Standard layout (W2/W3):** MET — `app.py`, `config.py`, `schema.py`, `test.py`, `download.py`, `fixture.py`,
  `__init__.py`, plus all 5 KG files + `LICENSE`.
- **Canonical actions (W7):** MET — single `encode` (correct verb for an embedding/encoder model).
- **Typed errors (W7):** MET — `ValidationError400` (a `UserError`→`BioLMError` subclass) for out-of-range
  `repr_layers`; request-shape validation via Pydantic validators (idiomatic `ValueError`→422, matches commons).
- **Schema field descriptions (W5):** MET — all request/response fields render in `model_json_schema()`;
  glossary-pinned fields (`sequence_index`, `layer`, `per_token_embeddings`) use the verbatim strings.
- **Structured logging (W6):** MET — `get_logger`, no `print`, indices not sequences logged.
- **Acquisition (W-acq):** MET — `r2_then_library` self-populates R2; build-order honored (fair-esm passed via
  `setup_download_layer(extra_pip_packages=...)` so the fallback can `import esm` at build time).
- **Licensing (W2):** MET — per-model `LICENSE` (MIT, Meta copyright + attribution note) consistent with
  `sources.yaml` (`type: MIT`).
- **Knowledge graph (W-kg):** PARTIAL — present and consistent, but the source-repo `commit`/`snapshot_r2` are
  unfilled (finding #2).
- **Tests (W17/W12):** MET — `TestSuite` with integration + deployment cases, lazy R2 fixtures, no module-scope
  network; shared-asset reuse only partially leveraged (finding #8).

## Verification

Adversarial re-check of the two HIGH-severity findings flagged on `msa_transformer`.

- **Finding 1 — `qa` env name in shipped usage comment → REAL.**
  Confirmed verbatim at `models/msa_transformer/app.py:261` (`# Force deploy to "qa" or "main" environment:`).
  `qa` is genuinely a real internal env name: `models/commons/modal/deployment.py:41` hardcodes
  `if current_env in ("qa", "main"):` as the production check (and the `--force-deploy` help string at
  `deployment.py:35` repeats `'qa' or 'main'`). It is template-wide — 31 `models/*/app.py` files carry the
  identical comment (`grep 'qa" or "main"'`) plus `deployment.py`. The reviewer's own ORANGE / fix-once-globally
  caveat stands; the factual leak is demonstrable.

- **Finding 2 — blank source-repo `commit`/`snapshot_r2` → REFUTED.**
  The factual sub-claims are true (`sources.yaml:39 commit: ''`, `:40 snapshot_r2: pending`; the commit
  `2b369911…` is pinned in `app.py:39,48`; `esm2/sources.yaml:48-49` fills both), BUT the *same* authority the
  reviewer cites for the applied_literature carve-out — `models/dummy/sources.yaml` — explicitly sanctions both
  states for `source_repos`: line 132 documents `commit` as "Pinned commit hash … **Optional**", and line 137
  documents `snapshot_r2` as "Set to '' or 'pending' if not yet captured." This is a phase-wide placeholder
  pattern, not a per-model defect (21 models have `commit: ''`, 24 have `snapshot_r2: pending`). The only true
  kernel is that the commit is trivially recoverable from the code — a nice-to-have completeness fill of an
  Optional field, not the claimed knowledge-graph inconsistency defect. The finding overstates a schema-sanctioned
  placeholder as a defect.
