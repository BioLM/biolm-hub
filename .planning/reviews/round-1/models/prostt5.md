# Review — `models/prostt5/`

**Reviewer:** independent round-1 · **Target:** `models/prostt5/` · **Reference:** `models/esm2/`, `models/dummy/`

## Summary

ProstT5 is a four-deployment family (two axes: `MODEL_ACTION` ∈ {encode, generate} × `MODEL_DIRECTION` ∈
{AA2fold, fold2AA}). The plumbing mostly follows the house pattern (ModelFamily config, `r2_then_hf`
download self-population, snapshot class, structured logging, no `print`, MIT LICENSE consistent with
`sources.yaml`). The knowledge-graph prose is rich and largely accurate.

However there are **two launch-gating defects**: (1) a silent numerical-correctness bug in batched
`encode` (mean-pooling averages over padding for every non-longest sequence in a mixed-length batch),
and (2) the per-variant schema gap — the gateway action registry and the generated docs publish the
**AA** request schema for *all four* variants, so the two `fold2AA` deployments advertise an
amino-acid input contract that rejects the lowercase-3Di input they actually require. This is exactly
the deferred W5 schema work. Beyond those, there is leftover scaffolding (dead schema classes, a
copy-pasted "Nucleotides" error message, a TODO in `BIOLOGY.md`, a redundant-and-crash-prone runtime
`os.environ` re-read, a dead length-padding branch), a non-canonical output field name
(`mean_representation` vs `embeddings`), and a few doc/code drifts (image tag, author name).

---

## 🔴 Must-fix before launch

### 1. Batched `encode` mean-pools over padding → wrong embeddings for short sequences
- **category:** Correctness
- **location:** `models/prostt5/app.py:247,276-283`
- **detail:** `max_seq_len = len(max(sequences, key=len)) + 1` is a single batch-wide length. After
  `padding="longest"`, the slice `embs = embedding_repr.last_hidden_state[:, 1:max_seq_len]` keeps
  `max_len` positions for **every** sequence, then `embs.mean(dim=1)` averages over all of them. For
  any sequence shorter than the longest in the batch, those trailing positions are `<eos>`/pad tokens,
  so the per-protein mean is computed over real residues **plus** padding embeddings (and divided by
  `max_len`, not the true length `L`). With `batch_size=16` and mixed lengths this silently corrupts
  the primary output — e.g. a length-50 sequence batched with a length-500 one averages ~50 real and
  ~450 pad vectors. The upstream ProstT5 snippet trims per sequence
  (`last_hidden_state[i, 1:len_i+1]`); `esm2/app.py` does the same with a per-sequence `truncate_len`.
  The single-sequence test fixtures never exercise this.
- **suggested fix:** Mean-pool per sequence using real lengths / the attention mask, e.g.
  `mask = ids.attention_mask[:, 1:].unsqueeze(-1)` then
  `(embs * mask).sum(1) / mask.sum(1)`, or loop per sequence over `len(seq_i)` like ESM2. Add a
  mixed-length-batch encode fixture so the regression is caught.

### 2. `fold2AA` variants publish the wrong (AA) request schema — broken public contract
- **category:** Schema / Public contract / DoD (schema accuracy)
- **location:** `models/prostt5/config.py:65-78` → consumed by `gateway/model_discovery.py:112-123`
  (registry keyed by `(base_slug, action)`, **not** by variant) and `docs/gen_pages.py:177-182`.
- **detail:** `action_schemas` is static: `encode → ProstT5EncodeRequestAA`,
  `generate → ProstT5GenerateRequestAA`. The action registry and the docs generator therefore use the
  **AA** schema for all four public slugs, including `prostt5-fold2aa-encode` and
  `prostt5-fold2aa-generate`. Those deployments actually require lowercase-3Di input
  (`app.py:166-170,191-195` select `…RequestFold`; `validate_prostt5_3di` requires the lowercase
  20-letter alphabet). So the generated documentation tells a `fold2AA` user to send uppercase amino
  acids, and any gateway-side validation against the registry schema would reject the only valid
  (lowercase-3Di) input — `validate_aa_extended` rejects lowercase. The `fold2AA` contract
  (3Di input, and for generate the absence of `num_beams`) is published nowhere except the container's
  own type hint and the hand-written README tables. The config comments admit this is unresolved
  ("a union type that gets resolved at runtime … a limitation we'll need to address in the next
  stage"). This is the deferred W5 schema-FIELD work.
- **suggested fix:** Make `action_schemas` direction-aware so each public variant advertises its true
  schema (e.g. resolve `request_schema` from `MODEL_DIRECTION` in `config.py`, or register
  per-variant action schemas in the gateway/docs path), and remove the scaffolding comments. At
  minimum, the four public slugs must each render the correct request schema in the generated docs.

---

## 🟠 Should-fix

### 3. `validate_prostt5_3di` error says "Nucleotides" — 3Di are structural tokens
- **category:** Errors / Correctness
- **location:** `models/prostt5/schema.py:55-60`
- **detail:** The message is `"Nucleotides can only be represented with '{prostt5_3di}' characters"`,
  copy-pasted from the DNA validator. 3Di tokens are a Foldseek **structural** alphabet, not
  nucleotides; a `fold2AA` user who sends bad input gets a misleading error.
- **suggested fix:** `f"3Di structural tokens can only use the lowercase characters '{prostt5_3di}'"`.

### 4. Dead, mislabeled schema classes (leftover scaffolding)
- **category:** Simplicity / Schema
- **location:** `models/prostt5/schema.py:117-128`
- **detail:** `ProstT5EncodeResponseLabel` and `ProstT5NEncodeResponseResult` are never imported or
  used (encode actually returns `ProstT5EncodeResponseResult.mean_representation`). They subclass
  `RequestModel`, and their field descriptions ("score assigned to this token", "Decoded sequence
  string for this generation candidate") describe a generation/logits output that this model does not
  produce in encode. Pure residue.
- **suggested fix:** Delete both classes.

### 5. Non-canonical output field name `mean_representation`
- **category:** Schema field names / Consistency
- **location:** `models/prostt5/schema.py:131-134`
- **detail:** Rubric A.3 lists `embeddings` as the canonical embedding output; `esm2` returns its
  mean embedding under `embeddings`. ProstT5 uses `mean_representation`, breaking cross-model
  uniformity (the diff between models should be the science, not the field name).
- **suggested fix:** Rename to `embeddings` (or `mean_embedding`) and keep a Pydantic
  `alias="mean_representation"` with `populate_by_name=True` per the rename rule. Update README/MODEL
  JSON examples accordingly.

### 6. Runtime `os.environ["MODEL_DIRECTION"]` re-read is redundant and crash-prone
- **category:** Correctness / Simplicity
- **location:** `models/prostt5/app.py:173-177, 216-220`
- **detail:** Both endpoints re-read `current_direction = os.environ["MODEL_DIRECTION"]` and compare
  it to the module constant `model_direction`. `parse_variant` applies the default **without** writing
  it back to `os.environ` (`environment.py:42-43`), so when a variant relies on the default (env var
  unset) this raises `KeyError` on every request. The check also compares an env var to a constant
  already derived from that same env var, so it can never meaningfully differ. `esm2` simply uses its
  `model_size` constant. (Same line raises a bare `ValueError` for an internal invariant — see also
  rubric A.5.)
- **suggested fix:** Delete the re-read and the mismatch check; pass `self.model_direction` (the class
  attribute already set from `model_direction`) into `prostt5_compute_embeddings` / `prostt5_translate`.

### 7. Dead length-padding branch in `generate` (wrong condition)
- **category:** Correctness
- **location:** `models/prostt5/app.py:403-410`
- **detail:** `if t_len > s_len: truncate; elif s_len < t_len: pad with "d"`. The `elif` condition
  `s_len < t_len` is identical to the first `if` (`t_len > s_len`), so it is unreachable — when the
  generated sequence is **shorter** than the source it is never padded, and the documented
  "padded with 'd' to match length" behavior (README:268, MODEL.md:147) does not happen. Also padding
  a `fold2AA` AA output with the 3Di character `'d'` would be alphabet-wrong anyway.
- **suggested fix:** Change to `elif s_len > t_len:` and pad with an alphabet-appropriate token (or
  drop the pad and just log), so the test's `len(seq) == len(input)` assertion is actually upheld for
  the rare `L>512` case.

### 8. README image tag does not match `app.py`
- **category:** Docs (drift)
- **location:** `models/prostt5/README.md:264` (and `MODEL.md` deps list) vs `models/prostt5/app.py:60`
- **detail:** README says the container is "Based on `pytorch/pytorch:2.0.1-cuda11.7-cudnn8-runtime`",
  but `app.py` builds from `pytorch/pytorch:2.6.0-cuda12.4-cudnn9-runtime`.
- **suggested fix:** Update README to the actual `2.6.0-cuda12.4-cudnn9-runtime` tag.

### 9. Author name wrong/inconsistent: "Maria" vs "Martin" Steinegger
- **category:** Knowledge graph (accuracy / consistency)
- **location:** `models/prostt5/sources.yaml:26`, `models/prostt5/README.md:287` vs
  `models/prostt5/LICENSE:27`
- **detail:** The co-author is **Martin** Steinegger (Steinegger lab / Foldseek). `sources.yaml`
  author list and the README BibTeX both say "Maria Steinegger"; the LICENSE attribution correctly
  says "Martin Steinegger". Factual error plus internal inconsistency.
- **suggested fix:** Change to "Martin Steinegger" in `sources.yaml` and the README BibTeX.

### 10. `sources.yaml` source repo not pinned/snapshotted (unlike esm2)
- **category:** Knowledge graph (completeness)
- **location:** `models/prostt5/sources.yaml:33-37`
- **detail:** `source_repos[github].commit: ''` is empty and `snapshot_r2: pending`, whereas the
  reference `esm2/sources.yaml:46-50` pins a real commit and `snapshot_r2` path — and `config.py`
  *does* pin `PROSTT5_HF_REVISION`. (Note: `pending` on `applied_literature` `pdf_r2`/`md_r2` matches
  the esm2 convention and is not flagged here.)
- **suggested fix:** Fill the GitHub `commit` and populate `snapshot_r2`, or remove the keys if no
  snapshot is intended.

### 11. `BIOLOGY.md` ships a TODO placeholder
- **category:** Knowledge graph (no template residue)
- **location:** `models/prostt5/BIOLOGY.md:70`
- **detail:** `<!-- TODO: Add citations for applied studies using ProstT5 embeddings for specific
  tasks -->` ships in a public doc; rubric A.9 forbids stray TODO/pending residue.
- **suggested fix:** Resolve the citations (several are already in `sources.yaml` applied_literature)
  or delete the comment.

---

## 🟡 Nits

### 12. config.py scaffolding comments admit unresolved design
- **location:** `models/prostt5/config.py:68-78`
- **detail:** "we'll use a union type that gets resolved at runtime", "This is a limitation we'll need
  to address in the next stage", "Default to AA, runtime will handle direction" read as porting-phase
  notes. Tie-off with finding #2.
- **suggested fix:** Remove once #2 is resolved.

### 13. Confusing `is_aa` naming + wrong assertion messages in the generate validator
- **location:** `models/prostt5/test.py:30-52`
- **detail:** `is_aa = sample_seq.islower()` is `True` when the **output** is lowercase 3Di (i.e. the
  `AA2fold` direction, input AA); the messages "AA sequences should be lowercase" / "FOLD sequences
  should be uppercase" describe the output by the opposite alphabet. The control flow is functionally
  correct but the naming/messages are misleading.
- **suggested fix:** Rename to `direction_is_aa2fold` and fix the assert messages to name the output
  alphabet (3Di vs amino acid).

### 14. `half_precision = True` set but deliberately unused
- **location:** `models/prostt5/schema.py:19` vs `models/prostt5/app.py:152-156`
- **detail:** `ProstT5Params.half_precision = True` while `setup_model` explicitly skips half precision
  ("Skipping half precision with memory snapshots"). The flag is dead/contradictory config.
- **suggested fix:** Remove the flag (or honor it) to avoid implying fp16 is active.

### 15. Stale TODO comment on `early_stopping`
- **location:** `models/prostt5/app.py:344-347`
- **detail:** The TODO quotes a `num_beams=1` warning, but the code only sets `early_stopping` inside
  `if num_beams > 1`, so the warning can't trigger. Comment is misleading.
- **suggested fix:** Delete the TODO.

### 16. `top_k` default typed `float` in helper signature
- **location:** `models/prostt5/app.py:293`
- **detail:** `top_k: float = 6` while the schema (`schema.py:159`) and HF expect `int`.
- **suggested fix:** `top_k: int = 6`.

### 17. Peer-reviewed ProstT5 paper filed under `applied_literature`
- **location:** `models/prostt5/sources.yaml:63-77`
- **detail:** "Bilingual language model for protein sequence and structure" (NAR Genomics &
  Bioinformatics, 2024, same author list) is the journal version of the **primary** paper, listed
  under `applied_literature` rather than `primary_papers`.
- **suggested fix:** Move it to `primary_papers` (or note it as the peer-reviewed version of the
  bioRxiv entry).

### 18. Internal env name `qa` in the `__main__` docstring (systemic)
- **location:** `models/prostt5/app.py:422`
- **detail:** `# Force deploy to "qa" or "main" environment:` references the internal `qa` Modal
  environment (rubric flags `qa` as internal). Not prostt5-specific — `esm2/app.py:484` carries the
  identical line — so this should be fixed repo-wide rather than counted against prostt5 alone.
- **suggested fix:** Address in the W-launch internal-reference sweep across all model `__main__`
  docstrings / the deployment helper.

---

## D. Definition-of-Done audit (model-scoped)

- **Canonical actions** — MET. `encode`/`generate` are in the closed set; direction is a deployment
  axis, not an invented verb.
- **Schema fields / accuracy** — NOT MET. Output field `mean_representation` is non-canonical (#5),
  and the `fold2AA` variants publish the AA schema (#2).
- **Errors** — PARTIAL. Validators use the commons `ValueError` pattern (acceptable), but the 3Di
  validator message is wrong (#3) and a bare `ValueError` is used for a runtime invariant (#6).
- **Logging** — MET. `get_logger` only, no `print`, no full-sequence/secret logging.
- **Acquisition** — MET. `r2_then_hf` with `huggingface_hub` listed in
  `setup_download_layer(extra_pip_packages=...)` for self-population; HF revision pinned.
- **Licensing** — MET (with caveat). MIT LICENSE present, permissive, consistent with `sources.yaml`;
  attribution is hand-asserted and flagged as such in the LICENSE footer.
- **Knowledge graph** — PARTIAL. All five files present and substantive, but with a TODO (#11), an
  author-name error (#9), an unpinned source repo (#10), and a doc/code image drift (#8).
- **Tests** — MET (mostly). `TestSuite` with integration + deployment cases, lazy R2 reads in the
  validator; but no mixed-length-batch encode case (would have caught #1), and fixtures are
  prostt5-local rather than shared assets (consistent with the direction-specific 3Di inputs).
- **No internal leakage** — MET except the systemic `qa` docstring (#18).

---

## Verification

Adversarial re-review of externally-supplied findings (refute unless concretely demonstrable):

- **"test finding" (`app.py:1`, "test detail")** — **REFUTED.** `models/prostt5/app.py:1` is `import os`; the finding carries no substantive claim ("test detail" placeholder) and no defect is demonstrable at or around that line. This is a synthetic placeholder, not a real defect.
