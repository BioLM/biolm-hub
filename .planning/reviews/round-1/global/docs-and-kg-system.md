# Round-1 Review — Docs & knowledge-graph system

Scope: `docs/gen_pages.py`, `docs/_docgen.py`, `docs/index.md`, `docs/quickstart.md`,
`mkdocs.yml`, `tooling/check_schema_docs.py`, `tooling/field_glossary.yaml`,
`tooling/test_schema_docs.py`, plus the generated site and its CI wiring.

## Summary

The docs system is fundamentally sound and well-architected. The design — a fully virtual
`docs/models/` tree regenerated on every `mkdocs build` from each model's `config.py` + 5-file
knowledge graph, with no committed per-model copies to drift — is the right call and is correctly
implemented. `_docgen.py` is cleanly separated from the mkdocs wiring (pure, import-light), the
strict build (`mkdocs build --strict`) and the schema-doc guard both run in CI (`ci.yml`), and a
gated `docs.yml` handles Pages publishing without breaking normal pushes.

I verified the real artifacts rather than reading only the source:
- `mkdocs build --strict` succeeds offline (no Modal/network) in ~3.7s, generating 43 model pages.
- The built site is **clean of internal leakage**: no `biolm-modal`, `.planning`, `qa` env,
  internal domains, or `{Model Display Name}`/TODO template placeholders in any rendered HTML.
- The schema-doc guard passes and correctly catches the `Optional[Annotated[..., Field(...)]]`
  description-drop class of bug; the glossary is sensible and its "intentionally NOT pinned"
  comments (pLDDT, contacts) show real care.

No 🔴 must-fix issues. The findings are quality/UX defects that are **pervasive** (each affects all
43 model pages) and worth fixing before launch because they degrade the flagship deliverable — the
per-model docs page — uniformly. The two highest-impact items are both link/text-extraction
mismatches in `gen_pages.py` that unit tests on the (explicitly testable) `_docgen` helpers would
have caught.

---

## 🟠 should-fix

### 1. Every model page's tagline drops the authored one-liner
**Category:** correctness / docs quality · **Location:** `docs/gen_pages.py:74-87` (`_first_paragraph`), used at `docs/gen_pages.py:250-252`

The canonical README template (`models/dummy/README.md:23`) and **all 43 production READMEs** put the
model's summary in a Markdown blockquote: `> **One-line summary**: ...`. The page generator builds the
italic tagline under the H1 from `_first_paragraph(readme)`, but `_first_paragraph` explicitly skips
any line starting with `>` (blockquote). So the authored one-liner is **never** used. Instead the
generator falls through to the first body paragraph (the Overview's opening sentence).

Verified on the built site — esm2's tagline renders as the verbose Overview paragraph
("ESM-2 (Evolutionary Scale Modeling 2) is a protein language model developed by Meta AI's
Fundamental AI Research (FAIR) team. It is trained with a masked language modeling objective on
UniRef50…") instead of the crisp authored summary ("Masked protein language model (BERT-style) from
Meta AI/FAIR that produces sequence embeddings, masked-token predictions, and per-sequence
log-probabilities…"). This happens on 100% of model pages.

**Fix:** Extract the blockquote one-liner as the tagline. E.g., add a `_one_liner(md)` helper that
finds the first `>`-prefixed line, strips the `> **One-line summary**:` lead-in, and use it; fall
back to `_first_paragraph` only if absent. (See also #5 — `_first_paragraph` is not
HTML-comment-aware, so fixing the tagline path closes that latent hole too.)

### 2. Intra-model "See also" links bounce off-site to GitHub instead of the same page
**Category:** docs quality / dead-ish links · **Location:** `docs/gen_pages.py:45-47` (`MODEL_PAGE_MAP`), `docs/gen_pages.py:186-189` + `docs/_docgen.py:183-213` (`rewrite_links`)

Each model page concatenates README + MODEL.md + BIOLOGY.md into one page with anchors `#usage`,
`#architecture-training`, `#biology` (verified present in the HTML). But every README ends with
`*See also: [MODEL.md](MODEL.md) … [BIOLOGY.md](BIOLOGY.md)*` (140 such cross-links across the
catalog), and `MODEL_PAGE_MAP` only maps the top-level prose pages (Philosophy/Contributing/
Future-work). So a model's own `MODEL.md`/`BIOLOGY.md` references are rewritten to **GitHub blob
URLs** — verified: all 43 model pages link `…/blob/main/models/<m>/MODEL.md`. The reader is sent off
the docs site to raw source even though that exact content is the next section down on the same page.

**Fix:** When embedding a model's prose, pass `embed()` a page_map that also maps that model's own KG
files to in-page anchors: `MODEL.md → #architecture-training`, `BIOLOGY.md → #biology`,
`README.md → #usage`. `embed`/`rewrite_links` already accept a `page_map`, so this is a per-model
merged dict in `_prose`/`_model_page`.

### 3. Duplicated `_discover()` with silently divergent SKIP sets (43 vs 44 models)
**Category:** modularity / consistency · **Location:** `docs/gen_pages.py:32` + `:281-286` vs `tooling/check_schema_docs.py:31` + `:34-39`

The two tools each carry a near-identical copy of model discovery, but with different SKIP sets:
gen_pages `{"commons","dummy","__pycache__"}` (43 models) vs check_schema_docs
`{"commons","__pycache__"}` (44 — it includes `dummy`). Confirmed at runtime: the build reports
"generated docs for 43 models", the checker reports "schema docs OK (44 models)". A third copy with
its own skip rule lives in `gateway/model_discovery.py:53`. Each behavior is individually defensible
(render-skip the template, but schema-check it so it stays valid), but the divergence is undocumented
copy-paste drift: a contributor reasonably expects "the model list" to mean one thing.

**Fix:** Factor a single `discover_models(skip=...)` helper (e.g. in `tooling/` or `models/commons`)
that both tools import, and add a one-line comment at each call site explaining the dummy choice.

### 4. `_docgen.py` ships with zero unit tests despite being built for testability
**Category:** testing gap · **Location:** `docs/_docgen.py:1-5` (docstring) — no test file exists

The module docstring states it is "Kept free of any `mkdocs_gen_files` import so the logic is
unit-testable on its own," yet there is no test for it anywhere (`grep` for `_docgen`/`render_schema_md`/
`rewrite_links`/`demote_headings` finds no test). These helpers carry the non-trivial, edge-case-heavy
logic that gates the public site (link rewriting, `..` path resolution, heading demotion, fenced-block
awareness, JSON-schema→Markdown). Findings #1 and #2 are exactly the kind of regressions a small unit
suite would have caught.

**Fix:** Add `docs/test_docgen.py` (Modal-free, unit tier) covering `rewrite_links` (page_map hit,
relative→GitHub, `..` resolution, http/anchor pass-through), `demote_headings` (fence-aware, h1 strip,
level-6 cap), `strip_html_comments`, and `render_schema_md` on a tiny Pydantic model.

---

## 🟡 nits

### 5. `_first_paragraph` is not HTML-comment-aware (latent tagline corruption)
**Category:** robustness · **Location:** `docs/gen_pages.py:74-87`

`embed()` runs `strip_html_comments` before rendering prose, but `_first_paragraph` runs on the raw
README. It only skips a comment's *first* line (starts with `<`); the inner lines of a multi-line
`<!-- … -->` block start with plain text and would be captured as the tagline. No production README
currently triggers this (all start with the blockquote one-liner), so it's latent — but if a
contributor forgets to delete the template's leading comment block, the tagline becomes TODO text.
Fixing #1 (extract the blockquote) sidesteps this; otherwise run `strip_html_comments` first.

### 6. Stray `/models/SUMMARY/` page published to the site
**Category:** polish · **Location:** `mkdocs.yml:43-44` (literate-nav)

The generated `models/SUMMARY.md` is consumed by literate-nav for the Models nav, but is **also**
rendered as a standalone content page (`site/models/SUMMARY/index.html`, 30 KB, title "SUMMARY"). It
is not in the nav and not in the search index (verified), but is reachable by direct URL. Minor, but
it's a stray nav-artifact on a public site. **Fix:** add `models/SUMMARY.md` to `exclude_docs`
(after literate-nav reads it) or `validation`/`not_in_nav`, or emit the summary under a name
literate-nav drops.

### 7. Broken in-page anchors never fail the build, even under `--strict`
**Category:** validation tradeoff · **Location:** `mkdocs.yml:63-69` (`validation.links.anchors: info`)

`anchors: info` is a deliberate, commented escape hatch (embedded KG prose carries intra-doc anchors
that may not survive section nesting), and page-level `not_found: warn` still fails the strict build —
a good split. The downside: a genuinely broken `#anchor` in authored prose ships silently. Acceptable
for now; consider periodically flipping anchors to `warn` locally to audit, or fixing #2 so most
intra-doc links become validated in-page anchors.

### 8. `docs/index.md` duplicates README "what's inside"/actions content (drift risk)
**Category:** consistency · **Location:** `docs/index.md:22-30`

The site home is a hand-maintained static page that restates the action-verb list and "what's inside"
already in the root `README.md`. The verbs currently match the canonical set
(`predict/fold/encode/generate/score/log_prob`) in both `index.md` and `quickstart.md`, so no live
drift — but two hand-kept copies of the same list will diverge eventually. Low priority; a tailored
site home is a reasonable choice. Keep an eye on it, or generate the action list from the catalog.

---

## Definition-of-Done audit (docs dimension)

- **Strict build wired in CI:** MET — `ci.yml` runs `mkdocs build --strict`; `docs.yml` gates Pages.
- **No committed generated docs / no drift:** MET — only `_docgen.py`, `gen_pages.py`, `index.md`,
  `quickstart.md` are tracked; models tree is fully virtual.
- **No internal leakage in the site:** MET — verified clean in built HTML.
- **Schema-doc guard (renders + glossary) enforced in CI:** MET — `tooling/check_schema_docs.py` +
  `test_schema_docs.py`, run in `ci.yml`; catches the `Optional[Annotated]` drop class.
- **Docs examples correct:** MET — `make install`, `bm setup/deploy/serve`, `pip install '.[serve]'`,
  `make docs` all exist and match.
- **Public CLAUDE.md authored / bootstrap deleted (W14):** NOT in scope of this dimension's files, but
  note the temporary bootstrap `CLAUDE.md` is still present (tracked separately under W14).

## Verification

Adversarial re-check of the four high-severity findings (tried to refute each by re-reading the cited code).

1. **Tagline drops the authored one-liner (blockquote skipped) — REAL.** `_first_paragraph` (gen_pages.py:78) `continue`s on any line starting with `>`, and the authored summary is a blockquote (`> **One-line summary**: …` — dummy/README.md:23, esm2/README.md:3). Used at gen_pages.py:250-252, so the tagline falls through to the Overview opening paragraph for all 43 rendered model pages.
2. **Intra-model See-also links bounce to GitHub — REAL.** The page concatenates README/MODEL.md/BIOLOGY.md into sections "Usage"/"Architecture & training"/"Biology" (gen_pages.py:257-259). `MODEL_PAGE_MAP` (gen_pages.py:45-47) excludes MODEL.md/BIOLOGY.md, so `rewrite_links` (_docgen.py:206-211) falls through to a GitHub blob URL for the footer links `[MODEL.md](MODEL.md)`/`[BIOLOGY.md](BIOLOGY.md)` (README:361) — 143 such cross-links across the catalog — sending readers off-site to content that is the next section on the same page.
3. **Duplicated `_discover()` with divergent SKIP sets (43 vs 44) — REAL (facts), but the divergence is intentional/defensible.** gen_pages.py:32 `{commons,dummy,__pycache__}` vs check_schema_docs.py:31 `{commons,__pycache__}`; 44 dirs have config.py (incl. dummy), so build logs "generated docs for 43" (gen_pages.py:339) and checker prints "schema docs OK (44 models)" (check_schema_docs.py:108-109). A third discovery with its own rule lives at gateway/model_discovery.py:50-55. All claims demonstrable; this is a maintainability/copy-paste concern (render-skip the template, schema-check it), not a correctness defect.
4. **`_docgen.py` has zero unit tests despite the testability docstring — REAL.** Docstring claims "unit-testable on its own" (_docgen.py:3-4), but no test references `render_schema_md`/`rewrite_links`/`demote_headings`/`strip_html_comments`/`_docgen` (grep: none outside docs/). The only adjacent test, tooling/test_schema_docs.py:9-17, exercises `check_schema_docs` (`_discover`/`_load_verbatim`/`check_model`), not the _docgen render/link/heading helpers.
