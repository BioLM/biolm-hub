<h1 align="center">biolm-hub</h1>

<p align="center">
  A standardized, <b>agent-first</b> catalog of open biological ML models that deploy on
  <a href="https://modal.com">Modal</a> in a couple of commands.
</p>

<p align="center">
  <a href="LICENSE"><img alt="License: Apache-2.0" src="https://img.shields.io/badge/license-Apache--2.0-blue.svg"></a>
  <img alt="Python 3.12+" src="https://img.shields.io/badge/python-3.12%2B-blue.svg">
  <img alt="36 models" src="https://img.shields.io/badge/models-36-14b8a6.svg">
  <img alt="agent-first" src="https://img.shields.io/badge/design-agent--first-6d28d9.svg">
</p>

<p align="center">
  <a href="#quickstart--five-minute-success">Quickstart</a> ·
  <a href="PHILOSOPHY.md">Philosophy</a> ·
  <a href="CONTRIBUTING.md">Contributing</a>
</p>

---

Implementing a bio-ML model used to be a moat — research code is dependency hell, undocumented, and
fragile. Coding agents have commoditized that work. What's still missing is a **clean, uniform,
documented, deploy-anywhere** substrate so nobody has to reinvent the wheel.

`biolm-hub` is that substrate: every model has the same layout, the same action verbs, the same
schemas, and a machine-readable knowledge graph — so an agent (or a human) can pull any model off the
shelf and run it. The catalog ships **36 models** today, each with an identical interface.

## Quickstart — five-minute success

```bash
git clone https://github.com/BioLM/biolm-hub
cd biolm-hub
make install                              # venv + all deps via uv, plus pre-commit hooks
source .venv/bin/activate                 # puts the `bh` CLI on your PATH

bh setup                                            # verify your Modal auth; it tells you exactly what to fix
BIOLM_SKIP_MODAL_SECRETS=1 bh deploy esm2 --variant MODEL_SIZE=8m   # deploy the small 8M-param ESM-2
```

Skipping the `source .venv/bin/activate` step? Run `.venv/bin/bh …` or `uv run bh …` instead — either
puts you on the same CLI without activating.

The only account you need is [Modal](https://modal.com) — `bh setup` points you at `modal token new`
if you're not authenticated. `BIOLM_SKIP_MODAL_SECRETS=1` tells the deploy not to mount the optional
weight-cache secrets (Cloudflare R2 / Hugging Face) that a fresh workspace doesn't have; public model
weights are then read anonymously over HTTPS from a read-only bucket. Drop the flag once you've
configured your own R2 credentials (via `bh setup`) and want deploys to self-populate your bucket.
`--variant MODEL_SIZE=8m` deploys just the smallest, CPU-only size; a bare `bh deploy esm2` (no
`--variant`) deploys **all five** ESM-2 sizes, including a 3B-parameter model on an L40S GPU.

Deploy prints your endpoint URL. Every model speaks the same verbs — `predict`, `fold`, `encode`,
`generate`, `score`, `log_prob` — over HTTP, so once you know one you know them all. See the
[ESM-2 model page](models/esm2/) for its exact request/response schema, then POST to your endpoint —
or run `bh serve` for a local web app that lets you fill in a form and call your deployed models from
the browser.

> **Deployed endpoints are unauthenticated.** A deployed model, a deployed gateway, or
> `bh serve --host 0.0.0.0` exposes inference **without authentication**, and every call bills *your*
> Modal account. Don't put one on a public network without your own access control in front.

## What's inside

| Path | What |
|------|------|
| `models/<name>/` | One model, uniform layout — `app.py`, `config.py`, `schema.py`, `test.py` — plus a **knowledge graph**: `sources.yaml` (license, papers, source repos), `comparison.yaml` (when to use / alternatives), `README.md`, `MODEL.md`, `BIOLOGY.md`. |
| `models/commons/` | The shared framework: config, decorators, Modal image helpers, R2 storage/download, the error taxonomy, structured logging, and the testing harness. |
| `models/dummy/` | The template — copy it to start a new model. |
| `cli/` | The `bh` tool — `setup`, `deploy`, `serve`, `cache`, `r2`, `kb`. |
| `gateway/` | A unified inference endpoint and a catalog web app (run inference from the browser). |
| `docs/` | The mkdocs site; per-model pages are generated from each model's config + knowledge graph. Build it with `make docs`. |

## Why it's "agent-first"

Every design choice optimizes for an LLM/agent consumer:

- **Uniform action verbs** — `predict`, `fold`, `encode`, `generate`, `score`, `log_prob`. Learn one
  model and you know them all.
- **Uniform schemas** — consistent field names across families (`heavy_chain`/`light_chain`,
  `sequence`, `pdb`/`cif`, `embeddings`, …); the biology lives in metadata, not ad-hoc field names.
- **A machine-readable knowledge graph** per model — so an agent can decide *which* model to use, not
  just how to call it.
- **One obvious way to do a thing** — structured logging, a consistent typed error taxonomy, pinned
  dependencies.

See [`PHILOSOPHY.md`](PHILOSOPHY.md) for the full design center.

## Adding a model

The catalog is meant to be **self-extending**: a contributor's agent can add a new model that matches
house style end-to-end. Start from `models/dummy/` (the template) and follow
[`CONTRIBUTING.md`](CONTRIBUTING.md). Each model's license is declared in its `sources.yaml`; only
permissively-licensed (MIT / Apache-2.0 / BSD and compatible) models are included.

## License

[Apache-2.0](LICENSE) for the framework and catalog code. **Each model carries its own upstream
license** in its directory (`sources.yaml` + a per-model `LICENSE`/attribution) — check it before use.
