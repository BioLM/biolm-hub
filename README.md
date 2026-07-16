<h1 align="center">biolm-hub</h1>

<p align="center">
  <b>Pull an open biological ML model off the shelf and have it serving in minutes — human or agent.</b>
</p>

<p align="center">
  A standardized, <b>agent-first</b> catalog of open biological ML models that deploy to your own
  <a href="https://modal.com">Modal</a> account in a couple of commands. Same layout, same verbs,
  same schemas — learn one model, use all <b>37</b>.
</p>

<p align="center">
  <a href="https://github.com/BioLM/biolm-hub/actions/workflows/ci.yml"><img alt="CI" src="https://github.com/BioLM/biolm-hub/actions/workflows/ci.yml/badge.svg"></a>
  <a href="https://biolm.github.io/biolm-hub/"><img alt="Docs" src="https://img.shields.io/badge/docs-live-14b8a6.svg"></a>
  <a href="LICENSE"><img alt="License: Apache-2.0" src="https://img.shields.io/badge/license-Apache--2.0-blue.svg"></a>
  <img alt="Python 3.12+" src="https://img.shields.io/badge/python-3.12%2B-blue.svg">
  <img alt="37 models" src="https://img.shields.io/badge/models-37-6d28d9.svg">
  <a href="https://github.com/BioLM/biolm-hub/discussions"><img alt="Discussions" src="https://img.shields.io/badge/discussions-join-ff8a00.svg"></a>
</p>

<p align="center">
  <a href="#quickstart">Quickstart</a> ·
  <a href="https://biolm.github.io/biolm-hub/">Docs</a> ·
  <a href="PHILOSOPHY.md">Philosophy</a> ·
  <a href="CONTRIBUTING.md">Contributing</a> ·
  <a href="https://github.com/BioLM/biolm-hub/discussions">Discussions</a>
</p>

---

Running an open biological ML model usually means re-solving the same plumbing every time: chase
dependencies, reverse-engineer an undocumented interface, wire up a deployment — all before your first
prediction. Everyone who touches that model, human or agent, pays the tax again.

**biolm-hub is the missing substrate.** Every model has the same layout, the same action verbs, the
same schemas, and a machine-readable knowledge graph — so anyone can pull a model off the shelf and
have it running in **minutes, not days**. **37 models today**, one uniform interface, built to grow as
the community adds more.

## Quickstart

*From zero to a live model in about five minutes. The only account you need is [Modal](https://modal.com).*

```bash
# 1 — Install
git clone https://github.com/BioLM/biolm-hub && cd biolm-hub
make install                 # venv + all deps via uv, plus pre-commit hooks
source .venv/bin/activate    # puts the `bh` CLI on your PATH
                             # (or install direnv — see below — to skip this step)

# 2 — Point bh at Modal
bh setup                     # verifies your Modal auth; tells you exactly what to fix

# 3 — Deploy a model and serve it
bh deploy esm2               # ESM-2's default variant: the small, CPU-only 8M model
bh serve &                   # the biolm-hub gateway: HTTP endpoint + browser UI on :8000
```

Then call it — every model speaks the same verbs (`predict`, `fold`, `encode`, `generate`, `score`,
`log_prob`), so once you know one you know them all:

```bash
curl -s http://127.0.0.1:8000/api/v1/esm2-8m/encode \
  -H "Content-Type: application/json" \
  -d '{
    "items": [
      { "sequence": "MKTVRQERLKSIVRILERSKEPVSGAQLAEELSVSRQVIVQDIAYLRSLGYNIVATPRGYVLAGG" }
    ]
  }'
```

> [!WARNING]
> **Deployed endpoints are unauthenticated.** A deployed model, a deployed gateway, or
> `bh serve --host 0.0.0.0` exposes inference **without authentication**, and every call bills *your*
> Modal account. Never put one on a public network without your own access control in front.

**Good to know:**

- **Routes are per *variant slug*, not family name.** `bh deploy esm2` deploys the `esm2-8m` variant,
  so it answers at `POST /api/v1/esm2-8m/encode`. Browse the exact slugs at
  `http://127.0.0.1:8000/catalog` (a browser form to run inference by hand) or in the deploy output.
- **The response** is `{"results": [{"sequence_index": 0, "embeddings": [{"layer": <n>, "embedding": [...]}]}]}`
  — one entry per input sequence; by default the final layer's mean-pooled vector. Pass `params.include`
  for per-residue embeddings, contacts, logits, or attentions. Each
  [model's page](https://biolm.github.io/biolm-hub/models/esm2/) documents its own schema.
- **No secrets? It just works.** A fresh workspace with no Cloudflare R2 / Hugging Face secrets deploys
  credential-less: public weights are read anonymously over HTTPS from a read-only bucket. Add your own
  R2 via `bh setup` and deploys self-populate your bucket instead. (`BIOLM_SKIP_MODAL_SECRETS` forces
  either mode.)
- **Prefer not to activate the venv?** Use `uv run bh …` or `.venv/bin/bh …`.
- **Want it fully automatic?** Install [direnv](https://direnv.net) (`brew install direnv`, then add its
  shell hook) and run `direnv allow` once. The committed `.envrc` then activates the venv — so `bh` is
  on your PATH — the moment you `cd` in, and loads a local `.env` if you have one
  (`cp .env.example .env`). Nothing here is required; the repo works without direnv or a `.env`.

## Docs & interfaces

Four ways in — one hop each:

- **Docs site** (schemas, per-model knowledge graph, when-to-use): <https://biolm.github.io/biolm-hub/>
  — browse every model at <https://biolm.github.io/biolm-hub/models/>.
- **Browser catalog + live API** (`bh serve`): `http://127.0.0.1:8000/catalog`, with Swagger UI at
  `/docs`, the machine-readable spec at `/openapi.json`, and each model's knowledge graph at
  `GET /api/v1/{model}/knowledge` (append `?format=md` for Markdown).
- **MCP server** (`bh mcp`): expose the catalog to an agent over the Model Context Protocol — it can
  probe every model's knowledge graph and per-action schema to decide which models to chain, then
  invoke them. Install the `[mcp]` extra; see [`gateway/mcp/README.md`](gateway/mcp/README.md).
- **For agents:** each model's machine-readable knowledge graph is `models/<name>/comparison.yaml`
  (when-to-use / alternatives) + `sources.yaml` (license / papers) — the same data rendered on each
  docs page.

### Deploy more than the default

| Command | Deploys |
|---------|---------|
| `bh deploy esm2` | The **default variant** — `esm2-8m`, CPU-only, small and cheap. |
| `bh deploy esm2 --variant MODEL_SIZE=650m` | One specific size. |
| `bh deploy esm2 --all-variants` | The whole family — all five sizes, up to a 3B model on an L40S GPU. |

## Why "agent-first"

Every design choice optimizes for an LLM/agent consumer — and humans get the same clean, predictable
surface for free:

- **Uniform action verbs** — `predict`, `fold`, `encode`, `generate`, `score`, `log_prob`. Learn one
  model, know them all.
- **Uniform schemas** — consistent field names across families (`sequence`, `heavy_chain`/`light_chain`,
  `pdb`/`cif`, `embeddings`, …). The biology lives in metadata, not ad-hoc field names.
- **A machine-readable knowledge graph** per model — so an agent can decide *which* model to use, not
  just how to call it.
- **One obvious way to do a thing** — structured logging, a typed error taxonomy, pinned dependencies.

See [`PHILOSOPHY.md`](PHILOSOPHY.md) for the full design center.

## What's inside

| Path | What |
|------|------|
| `models/<name>/` | One model, uniform layout — `app.py`, `config.py`, `schema.py`, `test.py` — plus a **knowledge graph**: `sources.yaml` (license, papers, source repos), `comparison.yaml` (when to use / alternatives), `README.md`, `MODEL.md`, `BIOLOGY.md`. |
| `models/commons/` | The shared framework: config, decorators, Modal image helpers, R2 storage/download, the error taxonomy, structured logging, and the testing harness. |
| `models/dummy/` | The template — copy it to start a new model. |
| `cli/` | The `bh` tool — `setup`, `deploy`, `serve`, `cache`, `r2`, `kb`. |
| `gateway/` | The **biolm-hub gateway**: a unified inference endpoint and a catalog web app (run inference from the browser). |
| `docs/` | The [docs site](https://biolm.github.io/biolm-hub/); per-model pages are generated from each model's config + knowledge graph. Build locally with `make docs`. |

CI runs `make check` on every PR (style + mypy + schema-doc check + tests) — keep it green locally
before pushing.

## Add a model

The catalog grows with its community, and adding a model is meant to be approachable for you and your
agent alike — the uniform layout means a new model follows a well-worn path, not a research project.

1. Have one in mind? Propose it in a
   [discussion](https://github.com/BioLM/biolm-hub/discussions) or an issue.
2. Copy `models/dummy/` and follow [`CONTRIBUTING.md`](CONTRIBUTING.md) — or, if you're building with
   an agent, point it at the `model-implementation` and `model-knowledge-base` skills in `.claude/skills/`.
3. `make check` and `make docs` go green; your model's docs page is generated automatically.

Each model declares its license in `sources.yaml`; only permissively-licensed models are included —
see [`CONTRIBUTING.md`](CONTRIBUTING.md) for the accepted-license policy (permissive + CC-BY-4.0; GPL
by maintainer review).

## Security

Found a vulnerability? Report it privately to **support+security@biolm.ai** — please don't open a
public issue. We'll acknowledge, keep you posted, and credit you if you'd like. (Note the
unauthenticated-endpoint warning under [Quickstart](#quickstart) — guarding a deployed endpoint is on
you.)

## License

[Apache-2.0](LICENSE) for the framework and catalog code. **Each model carries its own upstream
license** in its directory (`sources.yaml` + a per-model `LICENSE`/attribution) — check it before use.
