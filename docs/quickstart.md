# Quickstart

Get from a clean clone to a running model in a few commands.

## 1. Install

```bash
git clone https://github.com/BioLM/biolm-hub
cd biolm-hub
make install                # creates the venv and installs everything via uv
source .venv/bin/activate   # puts the `bh` CLI on your PATH
```

`make install` builds a virtualenv, installs the framework and the `bh` CLI, and sets up the
pre-commit hooks. Activating the venv puts `bh` on your `PATH`; without activating, run
`.venv/bin/bh …` or `uv run bh …` instead.

## 2. Configure your accounts

```bash
bh setup
```

`bh setup` checks your environment and tells you exactly what to fix:

- **[Modal](https://modal.com)** is required — it's where models deploy and run. If you're not
  authenticated, `bh setup` points you at `modal token new`.
- **Cloudflare R2** is optional. Public model weights are pulled from a read-only bucket by default.
  If your Modal workspace doesn't have the `cloudflare-r2` / `hf-api-token` secrets provisioned, a
  deploy can't mount them — `bh deploy` detects this and reads the public weights anonymously (no flag
  needed). Configure R2 only if you want to cache weights or responses into your own bucket.

## 3. Deploy a model

```bash
bh deploy esm2

# bh deploy auto-detects a workspace with no cloudflare-r2 / hf-api-token secrets and
# reads the public weights anonymously. Set BIOLM_SKIP_MODAL_SECRETS=1 to force it.
```

This deploys ESM-2's **default variant** — the smallest size (`esm2-8m`, CPU-only) — to *your* Modal
workspace. Pass `--all-variants` to deploy all five ESM-2 sizes (including a 3B-parameter model on an
L40S GPU), or `--variant MODEL_SIZE=650m` to pick a specific one. The first deploy pulls the weights
from the public bucket (or the original source) and caches them; subsequent deploys are fast.

Browse the [model catalog](models/index.md) for everything you can deploy, and each model's page for
its actions and request/response schema.

## 4. Run inference

A bare `bh deploy` deploys the model's Modal class — it isn't a public HTTP endpoint on its own.
Expose it over HTTP one of two ways: run `bh serve` locally (next section), or deploy the unified
gateway. Both serve the same contract — `POST /api/v1/{slug}/{action}` with a
`{"items": [...], "params": {...}}` body:

```bash
bh serve   # in one terminal → http://127.0.0.1:8000

# in another terminal:
curl -X POST http://127.0.0.1:8000/api/v1/esm2-8m/encode \
  -H 'Content-Type: application/json' \
  -d '{"items": [{"sequence": "MKTAYIAKQR"}]}'
```

Every model uses the same uniform action verbs (`predict`, `fold`, `encode`, `generate`, `score`,
`log_prob`). See a model's page (e.g. [ESM-2](models/esm2.md)) for the exact request/response schema
of each action, and the [HTTP API](api.md) page for the full calling contract and error shape.

## Run the catalog in your browser

```bash
bh serve
```

`make install` already installed the `[serve]` extra (it runs `uv sync --all-extras`), so there's
nothing more to install. `bh serve` runs a local catalog web app that lists every model and lets you
fill in a form and run inference against your deployed endpoints — no gateway deployment required.

!!! warning "Deployed endpoints are unauthenticated"
    A deployed model, a deployed gateway, or `bh serve --host 0.0.0.0` exposes inference **without
    authentication**, and every call bills *your* Modal account. Don't expose them on a public
    network without putting your own access control in front.

## Next steps

- [Model catalog](models/index.md) — what's available and when to use it.
- [Philosophy](philosophy.md) — why the catalog is built the way it is.
- [Contributing](contributing.md) — add a model, the house rules, how CI works.
