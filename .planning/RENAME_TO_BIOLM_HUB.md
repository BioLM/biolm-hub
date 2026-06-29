# `biolm-hub` rebrand — DEFERRED bundle (do JUST BEFORE LAUNCH, not now)

> **Decisions (2026-06-30, session `oss-w3b-wsec`).** The public OSS repo will be named **`biolm-hub`**.
> Per user: **hold ALL of the following until "just before completion"** so the focus stays on developing
> and testing the rest of the code first. Nothing here is executed now — this file is the pre-computed
> checklist so the launch sweep is mechanical, not a re-discovery. (`.planning/` is deleted at launch →
> run this BEFORE deleting `.planning/`, or copy the checklist out first.)
>
> **The bundle (all deferred together):**
> 1. **Repo identity** `biolm-models` → `biolm-hub` (Category A below).
> 2. **CLI command** `bm` → **`bh`** (user-confirmed; see CLI section).
> 3. **Modal environments** `biolm-models` → `biolm-hub` (prod) and `biolm-models-dev` → `biolm-hub-dev`
>    (dev) (Category B below). User will create these envs + copy secrets at launch.
> 4. **R2 bucket structure** — re-path weights under a `biolm-hub/` prefix mirroring the repo tree (R2 section).
> 5. **GitHub repo** — does NOT exist yet; CREATE `BioLM/biolm-hub` at launch (no "rename" needed).

**Search note:** `biolm_models` / `biolmmodels` = 0 hits — only hyphenated `biolm-models` / `biolm-models-dev`.
~78 hits / 49 files (whole repo except `.git/` + `.planning/`).

**⚠️ DO NOT blind find-replace `biolm-models` → `biolm-hub`.** The literal `prod_environment_name =
"biolm-models"` (`models/commons/util/config.py:80`) is byte-identical to the old repo name; a naive global
swap silently renames the prod Modal env. Treat Category B as its own deliberate edit.

---

## 1. Category A — Repo identity → `biolm-hub`
~34 hits / 16 files. The `models/` Python package root is NOT here (Category C — must not change).

**Packaging / metadata**
- `pyproject.toml:2` — `name = "biolm-models"`
- `pyproject.toml:25` — `pip install "biolm-models[serve]"` (comment)
- `pyproject.toml:36` — `pip install "biolm-models[docs]"` (comment)
- `pyproject.toml:68-70` — `Homepage`/`Documentation`/`Repository` = `https://github.com/BioLM/biolm-models`
- `uv.lock:194` — `name = "biolm-models"` (regenerate via `uv lock` after editing pyproject; don't hand-edit)

**Docs site / config**
- `mkdocs.yml:1` — `site_name: biolm-models`
- `mkdocs.yml:3` — `repo_url: https://github.com/BioLM/biolm-models`
- `mkdocs.yml:4` — `repo_name: BioLM/biolm-models`
- `docs/index.md:1` — `# biolm-models`
- `docs/index.md:14-15` — `git clone …/biolm-models` + `cd biolm-models`
- `docs/quickstart.md:8-9` — `git clone …/biolm-models` + `cd biolm-models`
- `docs/_docgen.py:12` — `GITHUB_BLOB = "https://github.com/BioLM/biolm-models/blob/main"` (builds "view source" links on every generated page)

**README / root docs**
- `README.md:1` — `<h1 align="center">biolm-models</h1>`
- `README.md:14` — name in prose
- `README.md:21-22` — clone URL + `cd biolm-models`
- `SECURITY.md:7` — `https://github.com/BioLM/biolm-models/security/advisories/new`
- `CONTRIBUTING.md:3` — name in prose
- `CLAUDE.md:3` — name in prose (public CLAUDE.md)
- `PHILOSOPHY.md:3` — name in prose

**License attribution** — every per-model `LICENSE:1` header reads `biolm-models — "<model>" model`. Sweep ALL
remaining models/*/LICENSE.

**CLI runtime text (tracks pyproject `name`)**
- `cli/serve.py:45` — `'Install them with: pip install "biolm-models[serve]"'`

**`.claude/skills/` docs that hardcode the GitHub repo path (404 after rename)**
- `pr-management/SKILL.md:1,3,120,124` (incl. two `gh api repos/BioLM/biolm-models/...`)
- `model-implementation/SKILL.md:3,10`
- `model-knowledge-base/SKILL.md:3,10`

## 2. CLI `bm` → `bh`
User-confirmed: the CLI command should be **`bh`** (biolm-hub), not `bm`. At launch, change the console-script
entrypoint in `pyproject.toml` (`[project.scripts]`), every `bm <subcmd>` in docs/README/CONTRIBUTING/quickstart/
skills, and CLI help text. (The Python package/module under `cli/` need not be renamed — only the command name
+ user-facing references.) NOTE: the current grep inventory above counted `biolm-models`, NOT `bm` — do a
separate `\bbm\b` sweep at launch (careful: avoid matching unrelated "bm" substrings).

## 3. Category B — Modal envs → `biolm-hub` / `biolm-hub-dev`
~43 hits / 33 files. **Source of truth:**
- `models/commons/util/config.py:79` — `dev_environment_name = "biolm-models-dev"` → `"biolm-hub-dev"`
- `models/commons/util/config.py:80` — `prod_environment_name = "biolm-models"` → `"biolm-hub"`

Echoes: `.github/workflows/deploy.yml:37,60`; `gateway/deploy_gateway.py:5-6`;
`models/commons/util/environment.py:115,141` (docstrings); per-model `app.py` deploy comments
(ablang2:357, antifold:448, biotite:375, boltzgen:467, deepviscosity:235, esm1b:417, esm2:485, esm_if1:206,
esmc:348, esmfold:212, evo:218, igt5:210, immunefold:405, mpnn:309, progen2:224, prody:120, prostt5:412,
rf3:446, sadie:143, spurs:315, temberture:433, tempro:231); skill docs
(`pr-management/SKILL.md:29,32,48,167,182,190,195,227`, `model-implementation/resources/quick_reference.md:27-29`,
`model-implementation/validation/GUIDE.md:90,93`).

**Infra (user, at launch):** create Modal envs `biolm-hub` + `biolm-hub-dev`, copy `cloudflare-r2` +
`hf-api-token` secrets into them, update the GitHub `modal-dev` Environment secrets / `MODAL_ENVIRONMENT`,
stop old apps on `biolm-models-dev`.

## 4. R2 bucket structure — mirror the repo tree under a `biolm-hub/` prefix
`biolm-public` is a general BioLM public bucket, so the OSS repo's artifacts should live under a namespaced
prefix that mirrors the repo's file/folder structure, e.g. `r2://biolm-public/biolm-hub/models/esm2/…`.
**Today** (`models/commons/util/config.py:9-12`): `r2_bucket_name="biolm-public"`, prefixes
`r2_model_store_dir="model-store"`, `r2_model_cache_dir="model-cache"`, `r2_test_data_dir="test-data"` — so keys
are `model-store/<slug>/<version>/…`. **At launch:** re-namespace these prefixes under `biolm-hub/` (e.g.
`biolm-hub/models`/`biolm-hub/model-cache`/`biolm-hub/test-data`, or a structure mirroring the repo). This is a
single-point change in `config.py` (everything derives the key prefix from these constants) — but it MUST happen
**before** any real Milestone-B weight writes populate the bucket, otherwise weights land under the old prefix
and need migration. The unauthenticated r2.dev read path (added this session) reads `{public_url}/{key}` and
follows whatever key these constants produce — so it needs no change when the prefix moves. **Coordinate timing:
if Milestone B writes weights before this re-path, plan an R2 move/migration.**

---

## Category C — Python `models/` package root (MUST NOT change)
Import root is the directory `models/` (`from models.commons…`), used by 272 files — independent of repo name.

## Not a hit (FYI)
- R2 bucket default is `biolm-public` (`config.py:9`), NOT `biolm-models`.

## Cautions
- Category A URLs only resolve after `BioLM/biolm-hub` exists on GitHub.
- `docs/_docgen.py:12` + `SECURITY.md:7` build user-facing links from the repo URL.
- `uv.lock:194` + `cli/serve.py:45` track pyproject `name` — edit `pyproject.toml:2`, then `uv lock`.
</content>
</invoke>
