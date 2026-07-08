# Gateway — unified endpoint + catalog web app

The gateway is a FastAPI app that fronts the catalog: it serves a browseable **catalog UI** and routes
inference requests to the right per-model Modal class, so callers hit one surface instead of N
per-model endpoints. The same app powers the local `bh serve` and the optional deployed gateway.

## Layout

| File | Role |
|------|------|
| `routing.py` | The core: builds the FastAPI app and, using each model's `config.py` (`modal_class_name`), routes `/{model}/{action}` to the deployed Modal container class — no AST discovery. |
| `model_discovery.py` | Discovers which models/variants are deployed in the target Modal environment. |
| `config.py` | Gateway configuration. |
| `server.py` | The **bare** deployed gateway (no response cache). |
| `server_with_cache.py` | The **cached** deployed gateway (response caching via `BIOLM_CACHE_ENABLED`). |
| `deploy_gateway.py` | Deploys the gateway to Modal (`python -m gateway.deploy_gateway [--cache]`). |
| `catalog/` | The web UI — templates + static assets (served by the app). |

## Local vs deployed

- **Local** (`bh serve`): builds the gateway app in-process (`use_cache=False`) and serves the catalog
  UI + HTTP API at `http://127.0.0.1:8000`. Best for browsing schemas and calling your deployed
  models from a form. Needs the `serve` extra (`pip install "biolm-hub[serve]"`). Either way the app
  also serves auto-generated interactive docs at `/docs` (Swagger UI) and the machine-readable
  contract at `/openapi.json`.
- **Deployed** (`gateway/server*.py` via `deploy_gateway.py`): an optional always-on gateway in your
  Modal workspace. Pick `server.py` (bare) or `server_with_cache.py` (response caching).

## Caution

A deployed gateway — and `bh serve --host 0.0.0.0` — is **unauthenticated** and bills **your** Modal
account. Don't put one on a public network without your own access control in front.

See the top-level [`README.md`](../README.md) for the catalog overview, and the
[docs site](https://biolm.github.io/biolm-hub/) for the rendered schemas and per-model knowledge graph.
