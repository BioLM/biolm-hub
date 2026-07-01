# Quickstart

Get from a clean clone to a running model in a few commands.

## 1. Install

```bash
git clone https://github.com/BioLM/biolm-hub
cd biolm-hub
make install      # creates the venv and installs everything via uv
```

`make install` builds a virtualenv, installs the framework and the `bh` CLI, and sets up the
pre-commit hooks.

## 2. Configure your accounts

```bash
bh setup
```

`bh setup` checks your environment and tells you exactly what to fix:

- **[Modal](https://modal.com)** is required — it's where models deploy and run. If you're not
  authenticated, `bh setup` points you at `modal token new`.
- **Cloudflare R2** is optional. Public model weights are pulled from a read-only bucket by default,
  so the happy path needs no credentials beyond Modal. Configure R2 only if you want to cache weights
  or responses in your own bucket.

## 3. Deploy a model

```bash
bh deploy esm2
```

This deploys [ESM-2](models/esm2.md) to *your* Modal workspace. The first deploy pulls the weights
from the public bucket (or the original source) and caches them; subsequent deploys are fast.

Browse the [model catalog](models/index.md) for everything you can deploy, and each model's page for
its actions and request/response schema.

## 4. Run inference

Every model exposes the same uniform action verbs (`predict`, `fold`, `encode`, `generate`, `score`,
`log_prob`) over an HTTP endpoint. See a model's page (e.g. [ESM-2](models/esm2.md)) for its exact
request and response schema, then POST to your deployed endpoint.

## Run the catalog in your browser

```bash
pip install '.[serve]'
bh serve
```

`bh serve` runs a local catalog web app that lists every model and lets you fill in a form and run
inference against your deployed endpoints — no gateway deployment required.

!!! warning "Deployed endpoints are unauthenticated"
    A deployed model, a deployed gateway, or `bh serve --host 0.0.0.0` exposes inference **without
    authentication**, and every call bills *your* Modal account. Don't expose them on a public
    network without putting your own access control in front.

## Next steps

- [Model catalog](models/index.md) — what's available and when to use it.
- [Philosophy](philosophy.md) — why the catalog is built the way it is.
- [Contributing](contributing.md) — add a model, the house rules, how CI works.
