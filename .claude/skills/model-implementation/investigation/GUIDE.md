# Phase 1: Investigation

## Purpose
Gather information about the model, confirm the license is permissive, find analogous reference models, and produce a skeleton `sources.yaml`. This prevents costly rework: wrong action verbs, incompatible weights, or a license that blocks acceptance are all cheaper to catch here.

---

## 1.1 License Check — Do This First

**Permissive licenses only** — canonical policy: `CONTRIBUTING.md` → "License first". Accepted: MIT, Apache-2.0, BSD-3-Clause (and compatible permissive licenses), plus CC-BY-4.0 (common for weights). **GPL / copyleft** is accepted only after a maintainer reviews the copyleft reach — flag it and ask; don't auto-reject *or* auto-accept. CC-BY-NC, other non-commercial / "academic only", and proprietary licenses are **not accepted**.

1. Find the LICENSE file in the source repo or the model card.
2. Record the SPDX identifier (e.g., `Apache-2.0`).
3. If unclear or non-permissive, **stop and ask the user** before proceeding.

> **When upstream ships no LICENSE file** (the license exists only as a HuggingFace card `license:`
> metadata tag — very common): don't get blocked. Record the SPDX id from the tag, and when you write
> `models/<name>/LICENSE`, put that SPDX id + the canonical license text/URL (SPDX / Creative Commons /
> OSI page) + a note that upstream declares it only via metadata (link the card). The permissive-only
> gate still applies to whatever the tag says.

---

## 1.2 Scope & Resource Check — Also Before You Code

biolm-hub OSS deliberately supports a **bounded** class of models. Classify the model now, before
writing code or deploying — getting this wrong burns Modal compute on a model the catalog cannot host.

**STOP — out of scope — if the model requires ANY of:**
- a persistent **Modal Volume**, `NetworkFileSystem`, or `CloudBucketMount` (any mounted, pre-populated
  filesystem beyond the container image + weights fetched by `download.py`);
- a **reference database hosted server-side** — UniRef, BFD, MGnify, PDB70, ColabFold DBs, etc.:
  anything in the tens-of-GB→TB range that is *not the model's own weights*;
- **server-side alignment/search** — running MSA / HHblits / jackhmmer / hmmer / MMseqs2 *inside the
  endpoint* against a hosted database;
- **any asset that is neither** (a) a bounded weight artifact fetchable through the `download.py`
  `r2_then_*` wrappers, **nor** (b) supplied by the caller in the request.

If any apply, **do not write code or deploy.** These belong to the internal pipeline, not this catalog —
the Modal-Volume lifecycle, multi-TB data hosting, and per-caller cost attribution are complexity this
OSS project intentionally omits. The catalog's convention for alignment-dependent models is to take the
MSA as an **`msa`/`alignment` request input** (the caller runs the search — or uses a separate MSA
service — and passes the result in; see `models/chai1`, `models/rf3`, `models/msa_transformer`). If the
model can be adapted to that pattern, proceed on that basis. Otherwise stop and raise it with the
maintainers.

**In scope — proceed — when both hold:**
- weights are a **bounded download** that `download.py` fetches once and R2 caches (the disqualifier is
  *not* raw size — the largest shipped models pull multi-GB→tens-of-GB checkpoints via `r2_then_hf`; it
  is needing a *persistent volume/DB mount* or *server-side search*), **and**
- any MSA / template / structure the model needs is a **request input** (`msa` / `alignment` /
  `msa_content`, `pdb` / `cif`, template fields) — not searched server-side.

This boundary is enforced in CI: `tooling/check_no_modal_volumes.py` fails the build if any model's code
references `modal.Volume` / `NetworkFileSystem` / `CloudBucketMount`.

---

## 1.3 Gather Model Information

Review the available sources — paper, GitHub repo, HuggingFace model card, project website. For each:

**GitHub / source repo:**
- Architecture and inference code
- All dependencies with exact versions
- Weight-loading / download mechanism

**HuggingFace (if available):**
- Model card usage examples
- Exact commit hash for reproducibility
- Model variants and sizes
- Authentication requirements

> **Finding the pinned revision SHA + config when the card doesn't render them.** The card page often
> hides both the commit hash and the architecture dims. Get them from the HF API/hub:
> - **Latest commit SHA:** `https://huggingface.co/api/models/<org>/<model>` → the `sha` field (or
>   `huggingface_hub.model_info("<org>/<model>").sha`; `list_repo_refs(...)` lists branches/tags).
> - **A specific file's raw contents** (architecture dims, `model_type`, tokenizer class):
>   `https://huggingface.co/<org>/<model>/raw/<sha>/config.json` (also `tokenizer_config.json` /
>   `vocab.json`).
>
> Pin that 40-char `sha` as `hf_pin_revision` (never `"main"` — see `resources/common_issues.md #2`).

**Research paper:**
- Input/output specifications
- Preprocessing requirements
- Batch size and sequence length limits
- Performance benchmarks (useful for validation sanity checks)

---

## 1.4 Find a Reference Model

Browse `models/` to find the closest analogous implementation. Read its `app.py`, `config.py`, `schema.py`, `test.py`, and `download.py` (if present). Copy patterns; adapt only what is specific to the new model.

**Selection criteria:**

| Dimension | Look at |
|-----------|---------|
| Protein sequence input | `esm2/`, `esmc/`, `e1/` |
| DNA/RNA input | `evo/`, `dnabert2/`, `omni_dna/` |
| Structure (PDB/mmCIF) input | `mpnn/`, `esm_if1/`, `antifold/` |
| Structure output / folding (sequence→structure) | `esmfold/`, `chai1/`, `rf3/` |
| HuggingFace weights | `esmc/`, `prostt5/`, `dnabert2/` |
| Custom URL weights | `mpnn/`, `antifold/` |
| No external weights | `biotite/`, `dna_chisel/` |
| Single variant, one action | `dna_chisel/` |
| Multi-variant, one action | `esm1v/` |
| Multi-variant, multi-action | `esm2/` |

> **Rule:** Never invent import organization, decorator usage, or class structure. Copy from the reference model.

> **Caveat — copy the plumbing, NOT the science.** The reference gives you import organization,
> decorators, class structure, and the `download.py`/`config.py`/`test.py` shape. It does **not**
> license copying its *field names* or its *tokenization*:
> - **Field names follow the uniform rules, not the reference.** e.g. `igbert` uses `sequence` for an
>   unpaired chain, but a **nanobody/VHH is a lone `heavy_chain`** (never `vhh`, never `sequence`).
>   Apply the schema-field rules in `CONTRIBUTING.md` / the SKILL Global Rules; don't inherit the
>   reference's choice just because you copied the file.
> - **Verify the tokenizer family from the UPSTREAM model, not the reference (MUST-VERIFY).** Read the
>   `tokenizer_class` in the upstream `tokenizer_config.json` and the `model_type` in `config.json`,
>   then match it to how you feed input — there are (at least) three buckets, not two:
>   - **BERT/WordPiece** (e.g. `igbert`): space-join residues (`" ".join(seq)`).
>   - **RoBERTa char-level byte-BPE**: pass the **raw** sequence (no spaces).
>   - **Subword / k-mer / custom-vocabulary tokenizers** (BPE, k-mer, and the custom tokenizers common
>     in DNA/genomics models — `dnabert2` uses a BPE tokenizer, the Nucleotide Transformer (upstream) a fixed
>     k-mer vocabulary): pass the **raw** string and let the HF tokenizer segment it — do **not**
>     space-join. Here **character length ≠ token count** (a k-mer/BPE tokenizer packs many characters
>     into one token), which changes how you set the length cap — see the `max_sequence_len` note in
>     `implementation/GUIDE.md §2.1`. These custom tokenizers usually load via `trust_remote_code=True`
>     (as `dnabert2` does), which has its own dependency footgun — see `implementation/GUIDE.md §2.4`.
>   Assuming the reference's scheme when the family differs silently produces wrong tokenization and
>   wrong inference, and it's hard to catch without running the model.

---

## 1.5 Determine Specifications

Work through these before writing a line of code:

**Variants:** Are there size variants (`8m`, `35m`, `650m`)? Type variants (`protein`, `ligand`)? Single variant?

**Actions:** Which of the six canonical verbs applies?
- `predict` — scalar/label property
- `fold` — 3D structure (returns `pdb`/`cif`)
- `encode` — embeddings / representations
- `generate` — new sequences or structures
- `score` — model-defined fitness scalar
- `log_prob` — per-sequence log-likelihood

Map each action to its input/output schema fields (using the standard field names from `CONTRIBUTING.md`).

> **Get user approval on actions and schemas before proceeding** — or, if you are running
> autonomously with no interactive user, record the decision (which verbs, which schema fields, and
> why) in the PR description or `sources.yaml` notes so a reviewer can check it.

**Resources:** For each variant, estimate GPU, memory, CPU, and timeout. See `resources/quick_reference.md` for the GPU tier table.

**Dependencies:** List all pip packages with exact versions. Note any system packages or conda requirements.

**Weight acquisition:** Where do weights come from (HuggingFace, URL, GitHub, none)? Authentication required? Total size per variant?

---

## 1.6 Create a Skeleton `sources.yaml`

Create `models/<name>/sources.yaml` now — a skeleton is better than none, and the license field is required before any code is merged.

Minimum required fields:

```yaml
model_slug: "your-model-slug"    # must match directory name and config.py base_model_slug
display_name: "Your Model Name"

license:
  type: "Apache-2.0"             # SPDX identifier
  url: "https://github.com/org/repo/blob/main/LICENSE"
  notes: ""                      # add context if needed, e.g. "weights are CC-BY-4.0"

molecule_types:
  - "protein"                    # from InputMolecule enum

tasks:
  - "embedding"                  # from Task enum

primary_papers:
  - title: "Full paper title"
    arxiv: ""                    # arXiv ID or bioRxiv DOI suffix
    doi: ""
    venue: ""
    year: 2024
    authors:
      - "Author A et al."

source_repos:
  - type: "github"               # github / huggingface / other
    url: "https://github.com/org/repo"
    commit: ""                   # pin this during implementation
```

See `models/dummy/sources.yaml` for the complete schema including `applied_literature`, `comparison`, and R2 knowledge-base paths. The full knowledge graph is authored by the `model-knowledge-base` skill — fill in what you know now and leave the rest for that phase.

---

## 1.7 Evaluate Endpoint Reuse

If the new model calls an existing hosted model (e.g., ESM-2 for embeddings), verify compatibility before assuming you can reuse the endpoint:

- Read the candidate's `schema.py` — exact field names and types
- Read the candidate's `app.py` — layer index, dimensions, pooling
- Confirm the extraction logic matches the paper

If compatible, use `modal.Cls.lookup()`. Document the decision (which endpoint, which params, and why).

---

## Gate

Before moving to Phase 2, confirm:

- [ ] License confirmed permissive and recorded in `sources.yaml`
- [ ] Scope check passed: no Modal Volume, no server-side reference DB, no server-side MSA/template search (any alignment is a request input)
- [ ] Reference model(s) identified; key files read
- [ ] Variants, actions, and schemas approved by user (or, running autonomously, recorded in the PR / `sources.yaml`)
- [ ] Resource requirements estimated
- [ ] `sources.yaml` skeleton committed (or ready to commit with Phase 2)
