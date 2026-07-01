# biolm-hub

A standardized, **agent-first** catalog of open biological ML models that deploy on
[Modal](https://modal.com) in a couple of commands.

The per-model implementation is no longer the hard part — coding agents have commoditized it.
What's still missing is a **clean, uniform, documented, deploy-anywhere** substrate so nobody has to
reinvent the wheel. That's what this repo is: ready-to-run bio-models an agent (or human) can pull
off the shelf and run.

## Five-minute success

```bash
git clone https://github.com/BioLM/biolm-hub
cd biolm-hub
bh setup          # checks your Modal + R2 config and tells you what to do
bh deploy esm2    # deploys the model to your Modal workspace
# → run inference
```

## What's inside

- **`models/`** — each model with a uniform layout (`app.py`, `config.py`, `schema.py`, `test.py`)
  plus a machine-readable **knowledge graph** (`sources.yaml`, `comparison.yaml`, `README.md`,
  `MODEL.md`, `BIOLOGY.md`): when to use it, training data, benchmarks, license, alternatives.
- **`cli/`** — the `bh` tool: `setup`, `deploy`, `serve`, `r2`.
- **`gateway/`** — a unified inference endpoint + a catalog web app.
- Uniform **action verbs** (`predict`, `fold`, `encode`, `generate`, `score`, `log_prob`), uniform
  schemas, structured logging, and a consistent error taxonomy — so an agent that learns one model
  knows them all.

## Start here

- [Quickstart](quickstart.md) — clone to a running model in a few commands.
- [Model catalog](models/index.md) — every model, with API schema, when-to-use guidance, and license.
- [Philosophy](philosophy.md) — the design center.
- [Contributing](contributing.md) — add a model and the house rules.
