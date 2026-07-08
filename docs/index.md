# biolm-hub

A standardized, **agent-first** catalog of open biological ML models that deploy on
[Modal](https://modal.com) in a couple of commands.

Running an open biological ML model shouldn't mean re-solving the same plumbing every time —
dependencies, an undocumented interface, a one-off deployment — before you get a single prediction,
for every model and every person or agent who tries. What's still missing is a **clean, uniform,
documented, deploy-anywhere** substrate so nobody has to reinvent the wheel. That's what this repo is:
ready-to-run bio-models anyone — human or agent — can pull off the shelf and run, growing as the
community adds more.

📦 **Source:** this site documents the open-source
[**biolm-hub** repository on GitHub](https://github.com/BioLM/biolm-hub) — browse the code, file an
issue, or contribute a model there. (The repo link is also in the top bar of every page.)

## Five-minute success

```bash
git clone https://github.com/BioLM/biolm-hub
cd biolm-hub
make install                               # venv + the `bh` CLI (all extras)

bh setup                                   # checks your Modal config
bh deploy esm2                             # deploy to your Modal workspace

bh serve                                   # local catalog UI + HTTP API → http://127.0.0.1:8000
# then, in another terminal, call it:
curl -X POST http://127.0.0.1:8000/api/v1/esm2-8m/encode \
  -H 'Content-Type: application/json' \
  -d '{"items": [{"sequence": "MKTAYIAKQR"}]}'
```

No R2 / Hugging Face secrets on your Modal workspace? Prefix deploys with
`BIOLM_SKIP_MODAL_SECRETS=1` so the build reads public weights anonymously. See
the [HTTP API](api.md) for the full calling contract.

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
- **For agents** — the machine-readable API is at `/openapi.json` (via `bh serve` or a deployed
  gateway); each model's `comparison.yaml` / `sources.yaml` drives model selection.
