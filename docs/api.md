# HTTP API

Every model in the catalog is called the same way: one `POST` per action, a
uniform request envelope, and a uniform response and error shape. Learn it once
and it applies to all models — the differences between models live in each
action's request/response schema (on the model's own page), not in the plumbing.

## Where the API lives

The `/api/v1/...` routes are served in two places — pick whichever fits:

- **`bh serve` (local, recommended for trying things).** Runs the catalog web
  app *and* the API in-process on your machine, calling your deployed Modal
  models directly. No gateway deployment needed.

  ```bash
  pip install 'biolm-hub[serve]'   # already included if you ran `make install`
  bh serve            # → http://127.0.0.1:8000/catalog  (API at the same origin)
  ```

  The API base URL is then `http://127.0.0.1:8000`.

- **A deployed gateway (hosted, shareable).** `python -m gateway.deploy_gateway`
  deploys the unified gateway to *your* Modal workspace; Modal serves it at a
  generated `https://<...>.modal.run` URL (or your custom domain). The base URL
  is that gateway URL.

A bare `bh deploy <model>` on its own is **not** directly HTTP-addressable — it
deploys the model's Modal class. Reach it through `bh serve` or the gateway,
both of which route to it.

!!! warning "These endpoints are unauthenticated"
    A deployed model, a deployed gateway, and `bh serve --host 0.0.0.0` expose
    inference **without authentication**, and every call bills *your* Modal
    account. Don't expose them on a public network without your own access
    control in front.

## The calling contract

```
POST {base_url}/api/v1/{slug}/{action}
Content-Type: application/json
```

- **`{slug}`** — a variant's endpoint slug, listed in the **Variants** table on
  each model's page (e.g. `esm2-650m`, `protein-mpnn`, `esmfold`).
- **`{action}`** — one of the model's actions, from the closed set `predict`,
  `fold`, `encode`, `generate`, `score`, `log_prob`. A model's page lists the
  actions it supports.

### Request envelope

Requests are batched and share one envelope across all models:

```json
{
  "items": [ { "...": "one input" }, { "...": "another input" } ],
  "params": { "...": "optional action parameters" }
}
```

- **`items`** (required) — the batch of inputs. Each item's fields (e.g.
  `sequence`, `pdb`, `smiles`) and the batch size limit are defined by the
  action's request schema on the model page.
- **`params`** (optional for most actions) — parameters controlling the action;
  defaults are used when omitted.

### Success response

A successful call returns the per-item results in the same order as `items`:

```json
{
  "results": [ { "...": "result for item 0" }, { "...": "result for item 1" } ]
}
```

### Errors

A failure returns a structured error body and the matching HTTP status:

```json
{
  "detail": "A human-readable message.",
  "errors": [],
  "status_code": 400,
  "code": "user.validation"
}
```

The HTTP status equals `status_code`, and the stable, machine-readable `code`
is what an agent should branch on. See the [Errors](errors.md) page for the full
list of codes and their meanings.

## Worked example

Encoding two protein sequences with ESM-2 (the `650m` variant), against a local
`bh serve`:

```bash
curl -X POST http://127.0.0.1:8000/api/v1/esm2-650m/encode \
  -H "Content-Type: application/json" \
  -d '{
    "items": [
      { "sequence": "MKTAYIAKQRQISFVKSHFSRQLEERLGLIE" },
      { "sequence": "MVLSPADKTNVKAAWGKVGAHAGEYGAEALE" }
    ],
    "params": { "include": ["mean"] }
  }'
```

The response carries one entry per input under `results`, in request order.
Every model page shows a ready-to-run `curl` and the exact request/response
schema for each of its actions.

## Utility endpoints

- **`GET /`** — health check; also lists the models the gateway supports.
- **`GET /resource-specs`** — the GPU/CPU/memory spec for every model variant.
