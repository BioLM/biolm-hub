<h1 align="center">biolm-models</h1>

<p align="center">
  A standardized, <b>agent-first</b> catalog of open biological ML models that deploy on
  <a href="https://modal.com">Modal</a> in a couple of commands.
</p>

---

Implementing a bio-ML model used to be a moat — research code is dependency hell, undocumented, and
fragile. Coding agents have commoditized that work. What's still missing is a **clean, uniform,
documented, deploy-anywhere** substrate so nobody has to reinvent the wheel.

`biolm-models` is that substrate: every model has the same layout, the same action verbs, the same
schemas, and a machine-readable knowledge graph — so an agent (or a human) can pull any model off the
shelf and run it.

## Quickstart — five-minute success

```bash
git clone https://github.com/BioLM/biolm-models
cd biolm-models
make install      # creates the venv and installs everything (uv)

bm setup          # checks your Modal + R2 config and tells you exactly what to fix
bm deploy esm2    # deploys ESM-2 to your Modal workspace
# → run inference against your endpoint
```

`bm setup` walks you through configuring [Modal](https://modal.com) (`modal token new`) and, if you
want to cache weights/responses in your own bucket, your Cloudflare R2 credentials. Public model
weights are pulled from a read-only bucket by default, so the happy path needs no credentials beyond
Modal.

## What's inside

| Path | What |
|------|------|
| `models/<name>/` | One model, uniform layout — `app.py`, `config.py`, `schema.py`, `test.py` — plus a **knowledge graph**: `sources.yaml` (license, papers, source repos), `comparison.yaml` (when to use / alternatives), `README.md`, `MODEL.md`, `BIOLOGY.md`. |
| `models/commons/` | The shared framework: config, decorators, Modal image helpers, R2 storage/download, testing. |
| `cli/` | The `bm` tool — `setup`, `deploy`, `serve`, `r2`. |
| `gateway/` | A unified inference endpoint and a catalog web app (run inference from the browser). |

## Why it's "agent-first"

Every design choice optimizes for an LLM/agent consumer:

- **Uniform action verbs** — `predict`, `fold`, `encode`, `generate`, `score`, `log_prob`. Learn one
  model and you know them all.
- **Uniform schemas** — consistent field names across families (`heavy_chain`/`light_chain`,
  `sequence`, `pdb`/`cif`, `embeddings`, …).
- **A machine-readable knowledge graph** per model — so an agent can decide *which* model to use, not
  just how to call it.
- **One obvious way to do a thing** — structured logging, a consistent error taxonomy, pinned deps.

See [`PHILOSOPHY.md`](PHILOSOPHY.md) for the full design center.

## Adding a model

The catalog is meant to be **self-extending**: a contributor's agent can add a new model that matches
house style end-to-end. Start from `models/dummy/` (the template) and follow
[`CONTRIBUTING.md`](CONTRIBUTING.md). Each model's license is declared in its `sources.yaml`; only
permissively-licensed (MIT / Apache-2.0 / BSD and compatible) models are included.

## License

[Apache-2.0](LICENSE) for the framework and catalog code. **Each model carries its own upstream
license** in its directory (`sources.yaml` + a per-model `LICENSE`/attribution) — check it before use.
