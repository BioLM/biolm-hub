# Phase 1: Discovery

## Purpose

Mine the codebase and public sources to populate `sources.yaml` -- the machine-readable index of
all primary sources and applied literature for this model. This file is the foundation every
downstream documentation phase builds from.

## Prerequisites

- The model directory exists under `models/` with at least `config.py` and `app.py`.
- Access to web search (arXiv, bioRxiv, Google Scholar, GitHub, HuggingFace).
- Template: `models/dummy/sources.yaml`.

---

## Step 1: Mine the Codebase

Extract every reference already present before searching externally.

1. **`config.py`** -- `model_slug`, `display_name`, `ModelTags` (molecule types, tasks),
   HuggingFace repo mappings (e.g., `facebook/esm2_t33_650M_UR50D`)
2. **`app.py`** -- `pip_install()` calls hint at source repos; inline paper comments
3. **`download.py`** (if present) -- source URLs: HuggingFace, GitHub releases, direct downloads
4. **`schema.py`** -- paper references in docstrings; domain-specific terminology for searches
5. **Existing `README.md`** (if present) -- paper links, arXiv/DOI, GitHub URLs, BibTeX blocks

---

## Step 2: Search External Sources

### Find the primary paper

- Search arXiv (`arxiv.org/search/`) and bioRxiv (`biorxiv.org`) for the model name
- Search Google Scholar and Semantic Scholar for author + model name
- If the name is generic, add qualifiers: "protein language model", "genomic foundation model"
- Check the paper for "Code availability" or "Data availability" sections

### Find the source repo

- Check the paper or HuggingFace model card for a GitHub link
- Search GitHub directly for the model name; check the research lab's GitHub organization

### Find the HuggingFace page

- Search HuggingFace Hub for the model name
- Cross-check any `config.py` HF repo mappings against what is actually on the Hub

---

## Step 3: Determine License (CRITICAL)

**Do not accept "Unknown" without exhausting all sources below.** Only permissive licenses
(MIT / Apache-2.0 / BSD / CC-BY-4.0 and compatible) are accepted. The accepted-license policy is
canonical in `CONTRIBUTING.md` → "License first"; this step implements it (GPL/copyleft →
maintainer review, not an automatic reject).

Check in this order -- stop when found:

1. **GitHub/GitLab LICENSE file** -- read the actual file (`LICENSE`, `LICENSE.md`, `LICENSE.txt`,
   `COPYING`). Do not trust the GitHub API `license` field; it can be wrong.
2. **HuggingFace model card YAML frontmatter** -- `license:` field. Cross-check against the
   actual repo LICENSE file; the two sometimes disagree.
3. **Zenodo / archive deposits** -- weights may have a separate license from the code (e.g.,
   code=MIT, weights=CC-BY-NC-SA-4.0).
4. **PyPI package metadata** -- `https://pypi.org/pypi/<package>/json`
5. **Paper "Data and Code Availability" section**
6. **Project page or web server** -- check for terms of use or commercial licensing contacts

**Dual-license awareness**: Code and weights often have different licenses. Record the more
restrictive one as `license.type` and document both in `license.notes`. The `sources.yaml`
`license` field is the source of truth; the `README.md` License section must match it.

**License declared only in metadata (no LICENSE file)**: common on HuggingFace — the repo has no
`LICENSE`/`COPYING` file, only a `license:` tag in the card frontmatter. Record the SPDX id from the
tag as `license.type`, set `license.url` to the model card and/or the canonical license text
(SPDX / Creative Commons / OSI page), and note in `license.notes` that upstream declares the license
only via metadata. Don't block on the missing file — but the permissive-only gate still applies to
whatever the tag says.

Common types:
- `MIT`, `Apache-2.0`, `BSD-3-Clause` -- permissive, accepted
- `CC-BY-4.0` -- permissive with attribution, accepted
- `CC-BY-NC-4.0` / `CC-BY-NC-SA-4.0` -- non-commercial only, **not accepted**
- `GPL-3.0` -- copyleft, review with a maintainer before accepting
- `Custom non-commercial` -- not accepted; document the URL and restrictions and stop

If the license is non-permissive, do not continue. Note it in the PR and ask a maintainer.

---

## Step 4: Find Applied Literature

Applied literature = papers that **use** the model (not the model's own papers).

Search by molecule type using these query templates (replace `{MODEL}` with the model name):

**Protein models:**
- `"{MODEL}" antibody engineering OR antibody design`
- `"{MODEL}" enzyme engineering OR fitness landscape OR directed evolution`
- `"{MODEL}" variant effect prediction OR DMS`
- `"{MODEL}" protein stability prediction thermostability`
- `"{MODEL}" embeddings downstream prediction`

**DNA/genomics models:**
- `"{MODEL}" promoter prediction OR enhancer prediction`
- `"{MODEL}" variant effect non-coding OR regulatory variant`
- `"{MODEL}" CRISPR guide design OR guide RNA efficiency`

**RNA models:**
- `"{MODEL}" RNA structure prediction secondary structure`
- `"{MODEL}" mRNA design OR codon optimization`

**Antibody models:**
- `"{MODEL}" CDR design OR affinity maturation`
- `"{MODEL}" developability prediction OR humanization`
- `"{MODEL}" paratope prediction OR epitope prediction`

**Where to search:** Google Scholar, PubMed, bioRxiv, Semantic Scholar, arXiv.
Google Scholar's "Cited by" link on the primary paper is the single most productive strategy.

**Quality filters (apply to all):**
- Peer-reviewed or reputable preprint (bioRxiv, arXiv, medRxiv)
- Contains quantitative results using this model
- Published within the last 3 years preferred; older accepted if seminal

**When fewer than 3 papers are found:** Try all capitalization variants of the model name, the
parent model family, and the closest competitor's benchmark papers. For models published less than
6 months ago, focus on bioRxiv preprints.

**If an honest, exhaustive search still yields fewer than 3, document the gap — never fabricate.** A
short or empty `applied_literature` with a one-line note (niche/new model; N papers found; search
performed) is correct and passes the gate below. Inventing a DOI, title, author, or number to reach
"3" is a hard failure. When in doubt, document the gap — the "≥3 papers" target never overrides the
anti-fabrication rule.

For each qualifying paper, add an entry to `applied_literature` in `sources.yaml` with `title`,
`doi`/`arxiv`, `year`, `relevance` (1-2 sentences), `molecule_focus`, and `task_focus`. Leave
`pdf_r2` and `md_r2` as `""` -- populating those fields is a maintainer operation.

---

## Step 5: Populate sources.yaml

Copy `models/dummy/sources.yaml` as your template. Fill in:

1. `model_slug` and `display_name` -- from `config.py` `ModelFamily` (must match exactly)
2. `primary_papers` -- `title`, `arxiv`/`doi`, `venue`, `year`, `authors`. Set `pdf_r2` and
   `md_r2` to `""`
3. `source_repos` -- GitHub, HuggingFace, etc. Set `snapshot_r2` / `page_md_r2` to `""`
4. `license` -- `type` (SPDX identifier), `url` (link to the LICENSE file), `notes` (any
   restrictions or dual-license context)
5. `molecule_types`, `applicable_to`, `tasks` -- pull directly from `config.py` `ModelTags`
6. `applied_literature` -- entries found in Step 4

---

## Gate Criteria

Phase 1 is complete when **all** of the following are true:

- [ ] `sources.yaml` exists in the model directory
- [ ] `model_slug` matches `config.py` and the directory name under `models/`
- [ ] `display_name` matches `config.py`
- [ ] `license.type` is populated (not "Unknown" unless all sources above are exhausted and the
      gap is documented in `license.notes`)
- [ ] At least one entry in `primary_papers` with title, identifier (arxiv or doi), and year
- [ ] `molecule_types`, `applicable_to`, and `tasks` each have at least one entry
- [ ] `applied_literature` has at least 3 entries, or the gap is documented (e.g., model
      published < 6 months ago -- preprint-only search yielded N papers)

---

## Common Issues

- **Model name differs from slug in the paper**: Document both in `display_name` or `license.notes`.
- **Unpublished models**: Use the HuggingFace model card or GitHub README as primary reference;
  set `venue: "Unpublished"`.
- **Multiple papers**: Include all in `primary_papers`, ordered by relevance (foundational first).
- **Preprint later published**: Prefer the published version but include both arXiv and DOI.
- **Non-permissive license discovered**: Do not continue. Flag in PR.
