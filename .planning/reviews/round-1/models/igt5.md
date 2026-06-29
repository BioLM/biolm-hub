# Review — `models/igt5/`

**Reviewer:** independent launch-gating review (round 1)
**Verdict:** Good shape, no 🔴 blockers. IgT5 is a faithful clone of its validated sibling `igbert`,
so plumbing is uniform with the house pattern. The findings below are documentation accuracy issues
(a wrong HF link, a wrong citation/year spread across 3 files), a couple of shared quality warts
(residue-embedding padding semantics, dead validation branch, no-op ConfigDict keys), and some forward-
compat polish. None block launch on their own, but the doc errors are user-facing and should be fixed.

## What's correct (verified)
- **Layout / config**: all standard files + the 5-file knowledge graph present; `ModelFamily` defines
  `modal_class_name="IgT5Model"`, `action_schemas`, variant axis `MODEL_TYPE`, tags. ✓
- **Action verb**: single `encode` action for an embedding model — correct, from the closed set. ✓
- **Schema field names**: canonical `items`/`params`/`sequence`/`heavy_chain`/`light_chain` with
  `heavy`/`light` aliases preserved; outputs `embeddings`/`residue_embeddings`/`results`. Biology lives
  in tags (`InputMolecule.ANTIBODY`), not field names. ✓
- **Field descriptions render**: `python -m tooling.check_schema_docs --model igt5` → `✓ schema docs OK`.
  All `Field(description=...)` are at field level (not buried in `Optional[Annotated[...]]`). ✓
- **Errors / logging**: caller mistakes raise `ValidationError400` (a `UserError`/`BioLMError`
  subclass); `get_logger`, no `print` (T20 clean); validators raise `ValueError` which Pydantic converts
  to a 422 — idiomatic, not a bare-exception violation. ✓
- **Acquisition**: canonical `r2_then_hf` with `required_files=["config.json"]`, self-populating; pinned
  HF revisions per variant; `huggingface_hub==0.26.0` listed in `setup_download_layer(extra_pip_packages=)`
  for the empty-cache fallback (build-order rule honored). ✓
- **License**: per-model `LICENSE` is CC-BY-4.0 ("Attribution 4.0 International"), consistent with
  `sources.yaml` (`type: CC-BY-4.0`); the HF-says-MIT-but-Zenodo-is-canonical discrepancy is explicitly
  flagged in sources/README/MODEL — good practice. ✓
- **No internal leakage**: grep for `biolm-modal` / `.planning` / internal paths is clean. The
  `"qa"`/`"main"` mention in the `__main__` docstring is NOT a leak — `qa`/`main` are first-class Modal
  deployment environments in the *public* `models/commons/modal/deployment.py` and the same docstring
  ships in 30 models. ✓

---

## 🟠 should-fix

### 1. Wrong HuggingFace URL for the unpaired weights (dead/incorrect link)
**Category:** docs / dead link — **`models/igt5/README.md:189`**
The link text says `huggingface.co/Exscientia/IgT5_unpaired` but the URL points at the **paired** repo:
```
- **Model weights (unpaired)**: [huggingface.co/Exscientia/IgT5_unpaired](https://huggingface.co/Exscientia/IgT5)
```
`config.py` (`IGT5_HF_REPO_MAP["IgT5_unpaired"] = "Exscientia/IgT5_unpaired"`) confirms the correct repo.
**Fix:** change the URL to `https://huggingface.co/Exscientia/IgT5_unpaired`.

### 2. Wrong citation year + arXiv id, contradicting the rest of the knowledge graph
**Category:** docs / cross-file consistency — **`models/igt5/MODEL.md:59`, `comparison.yaml:8`, `comparison.yaml:26`**
The primary paper is Kenlay et al. **2024**, arXiv **2403.17889** (correct in `sources.yaml:20`,
`README.md:9,172,177,187`). But:
- `MODEL.md:59` references `Kenlay et al. 2023 -- ... (arXiv: 2310.16645)` — both the year and the arXiv
  id are wrong (2310.16645 is not this paper).
- `comparison.yaml:8` and `comparison.yaml:26` both say `Kenlay et al. 2023`.
This makes the same paper appear as two different works across the knowledge graph.
**Fix:** change all three to `Kenlay et al. 2024` / `arXiv: 2403.17889`.

### 3. `residue_embeddings` includes zeroed special-token and padding rows (batch-dependent length)
**Category:** correctness / API contract — **`models/igt5/app.py:187-207`, schema `models/igt5/schema.py:156-159`**
`residue_embeddings[idx]` is returned at the **batch-padded** length `[L_padded, H]`: special tokens and
padding are zeroed (`residue_embeddings[special_tokens_mask == 1] = 0`) but still emitted as rows, and the
matrix is padded to the longest item in the request. Consequences:
- the same single sequence returns a *different-length* `residue_embeddings` depending on what else is in
  the batch (trailing zero rows), and
- the row count does not equal the residue count.
The schema description is the glossary-pinned `"Per-residue embedding vectors."`, which does not convey
this; only `MODEL.md:161` mentions padding. This is shared verbatim with `igbert` (same code), so it's a
family-level wart rather than an igt5 regression — worth fixing in both. **Fix (preferred):** trim each
result to its real residues using `attention_mask`/`special_tokens_mask` before `.tolist()` (as `esm2`
does with `1:truncate_len+1`); at minimum, document the padding/zeroing in the field description.

---

## 🟡 nits / polish

### 4. Dead branch in the variant-mismatch check
**`models/igt5/app.py:136-148`** (shared with `igbert/app.py:142-151`).
`request_kind = payload.items[0]._kind`, so `any(item._kind != self.model_type for item in payload.items)`
already covers item 0. The trailing
```
or ((request_kind == PAIRED and self.model_type != PAIRED) or (request_kind == UNPAIRED and self.model_type != UNPAIRED))
```
is fully subsumed by the `any(...)` and never changes the result. **Fix:** reduce to
`if any(item._kind != self.model_type for item in payload.items):`.

### 5. No-op `ConfigDict` keys on the response model
**`models/igt5/schema.py:145-150`**. `exclude_unset`/`exclude_none` are **not** `ConfigDict` keys (they
are `model_dump()` args); they are silently ignored (verified: `model_dump()` still emits the `None`
field). None-stripping actually happens in `commons/data/serializer.py:187` (`model_dump(exclude_none=True)`),
so behavior is correct but the config is misleading dead metadata. (`esm2` hides the same two keys under
`json_schema_extra`; `igbert` repeats this exact mistake.) **Fix:** drop both keys from the ConfigDict.

### 6. Unused `kind` property
**`models/igt5/schema.py:124-126`** defines `def kind(self)` returning `self._kind`; nothing references it
(`igbert` doesn't have it). **Fix:** delete the property.

### 7. `@model_validator(mode="after")` declared as `(cls, instance)` — non-idiomatic, future break
**`models/igt5/schema.py:90-91`** (shared with `igbert`). Pydantic is pinned to `2.11.7`, where this still
works (treated as a classmethod), so no warning fires today. On 2.12+ it emits
`PydanticDeprecatedSince212` ("on a classmethod is deprecated … removed in V3.0"). **Fix:** make it an
instance method — `def validate_and_infer_type(self) -> "IgT5EncodeRequestItem":` using `self.*`.

### 8. Redundant `.cpu()` calls
**`models/igt5/app.py:196-197`** already do `.detach().cpu()`, then **lines 204/207** call `.cpu()` again
on the already-CPU tensors. Harmless but redundant. **Fix:** drop the second `.cpu()`.

### 9. Stray `TODO` HTML comments in shipped docs
**`README.md:124`, `MODEL.md:27`, `MODEL.md:59`** ship `<!-- TODO: ... -->` placeholders. This is a
repo-wide condition (most models, including the `esm2` reference and the `dummy` template, carry similar
TODOs — presumably a tracked global docs deliverable), so low severity, but they are incomplete public
docs. **Fix:** resolve the parameter-count / benchmark TODOs or remove the comments before launch.

### 10. Self-contradicting license phrasing
**`MODEL.md:103`** lists "License terms not fully specified for original weights" under Cons, which
contradicts the otherwise-confident CC-BY-4.0 stance in `README.md:20`, `MODEL.md:18-22`, `sources.yaml`,
and `comparison.yaml:11`. **Fix:** align with the CC-BY-4.0 + "HF says MIT, Zenodo canonical" wording used
elsewhere.

### 11. (low confidence — verify) Paired mean-pool may include the in-text `</s>` separator
**`models/igt5/app.py:150-154, 187-194`**. The paired input is the literal string
`"<heavy> </s> <light>"`. HF's `return_special_tokens_mask` typically marks only the *template-added*
special tokens, not special-token strings embedded in the user text — so the mid-sequence `</s>` would get
`special_tokens_mask == 0`, meaning its embedding is **not** zeroed and **is** counted in the mean and the
residue output. If the reference IgT5 pooling excludes the separator, paired means would be slightly off.
This is identical to `igbert`'s `[SEP]` handling and there are golden R2 fixtures at `rel_tol=1e-4`, so it
may already match the reference (or the fixtures may be self-generated). **Action:** confirm against the
Exscientia reference whether the separator should be excluded from pooling; if so, mask it in both models.

---

## D. Definition-of-Done (igt5 scope)
- Standard layout, canonical action, uniform schema field names, rendering descriptions, typed errors,
  structured logging, canonical self-populating acquisition, permissive per-model LICENSE consistent with
  sources, full 5-file knowledge graph, `TestSuite` with integration + deployment cases and lazy fixtures
  — **all met**.
- "Knowledge graph accurate / no stray placeholders" — **partially met**: wrong unpaired HF link (#1),
  wrong citation year/arXiv across 3 files (#2), and TODO residue (#9).
- Cross-model uniformity — **met**: igt5 mirrors the validated `igbert` plumbing; findings #3/#4/#5/#7 are
  inherited from that shared pattern, not igt5-specific divergences.

---

## Verification

Adversarial re-check of the three HIGH-severity findings (attempted refutation; cited concrete evidence).

- **#1 Unpaired weights link points at the paired HF repo — REAL.**
  `README.md:189` link text `huggingface.co/Exscientia/IgT5_unpaired` wraps URL
  `https://huggingface.co/Exscientia/IgT5`; `config.py:29` (`IGT5_HF_REPO_MAP["IgT5_unpaired"] =
  "Exscientia/IgT5_unpaired"`) confirms the URL is the wrong (paired) repo.

- **#2 Wrong citation year + arXiv id for the primary paper — REAL.**
  Canonical `sources.yaml:20-23` = arXiv 2403.17889 / 2024, matching `README.md:172,180-181,187`; but
  `MODEL.md:59` cites "Kenlay et al. 2023 ... (arXiv: 2310.16645)" (wrong year AND a different arXiv id)
  and `comparison.yaml:8,26` say "Kenlay et al. 2023" — a genuine intra-KG contradiction.

- **#3 residue_embeddings returned at batch-padded length with zeroed special/pad rows — REAL.**
  `app.py:187-189` zeroes special-token/pad rows in-place but `app.py:207` emits
  `residue_embeddings[idx]` (full `[L_padded, H]` from `padding="longest"`) with no slice to residue
  count, so row count != residues and length varies with batch composition; `schema.py:158` description
  "Per-residue embedding vectors." does not convey this (MODEL.md only lists `<pad>` as a special token
  at line 48, no padding-shape note). Inherited verbatim from igbert (family-level), still demonstrable here.
