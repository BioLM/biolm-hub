# biolm-hub MCP server

> One more way to reach the catalog — a **Model Context Protocol** server that lets an agent *probe*
> every model (what it does, when to use it, its exact request schema) and *invoke* the ones it picks.
> Richer in metadata than the raw HTTP API, so an agent can figure out **which models to chain, in what
> order** to solve a problem — then run them.

## Quickstart

*From zero to an agent probing the catalog in about two minutes. Probing needs **no** Modal account —
it reads the repo. Only `invoke_action` touches Modal.*

```bash
# 1 — Install (the MCP server is an opt-in extra; `make install` already includes it)
pip install "biolm-hub[mcp]"

# 2 — Run it (stdio: local, zero network, the everyday path)
bh mcp
#   …or serve Streamable HTTP for a remote/multi-client agent:
bh mcp --http --port 9000        # → http://127.0.0.1:9000/mcp
```

Point an agent at it. For a client that reads an `mcpServers` config (Claude Desktop, Claude Code, an
SDK agent):

```jsonc
// stdio (local) — the client spawns `bh mcp`
{ "mcpServers": { "biolm-hub": { "command": "bh", "args": ["mcp"] } } }

// or Streamable HTTP (a running `bh mcp --http`)
{ "mcpServers": { "biolm-hub": { "url": "http://127.0.0.1:9000/mcp" } } }
```

That's it — the agent can now probe the whole catalog.

### Host it on Modal (opt-in)

`gateway/mcp/deploy_mcp.py` hosts the MCP server on Modal over **stateless** Streamable HTTP, mirroring
the gateway deployment:

```bash
modal deploy gateway/mcp/deploy_mcp.py    # → https://<workspace>--biolm-mcp-web.modal.run/mcp
```

Point a client at the deployed `/mcp` URL. Bind a custom domain with `BIOLM_MCP_DOMAIN`. Like the
gateway, the hosted surface is **unauthenticated and bills your Modal account** — don't expose it
publicly without your own access control. It stays metadata-only until a client calls `invoke_action`.

## What the agent gets

**Tools** (work in every MCP client):

| Tool | Does |
|------|------|
| `list_models` | List models, optionally filtered by `molecule` / `task` / `action`. |
| `search_models` | Free-text search + capability filters, ranked — the "which models?" step. |
| `get_model_knowledge` | When to use / when **not** to, strengths, benchmarks, alternatives, complements. `format` = `json` (default) or `md`. |
| `get_model_schema` | A model's per-action request/response JSON Schema — the "how do I call it?" step. |
| `find_alternatives` | A model's **alternatives** (competitors + when each is better/worse) — swap one model for another. |
| `find_complements` | A model's **complements** (the models it chains with, and the workflow for how). |
| `suggest_pipeline` | A deterministic, explainable first-draft pipeline for a free-text `goal` — a heuristic over the complements graph, **not** an LLM plan. |
| `get_openapi` | The gateway's full OpenAPI (JSON), generated in-process; optional `slug` slices to one model. Needs the `[serve]` extra. |
| `invoke_action` | Run an action on a **deployed** variant and get the model's response. |

**Resources** (a cacheable mirror, for clients that read resources):
`biolm://catalog` · `biolm://capabilities` · `biolm://openapi` · `biolm://model/{slug}` ·
`biolm://model/{slug}/knowledge` · `biolm://model/{slug}/schema`.

**Prompt:** `compose_pipeline(goal)` seeds an agent with the capability vocab + catalog summary and
asks it to draft a probe-then-compose plan.

Read `biolm://capabilities` first for the exact `molecule` / `task` / `action` vocabulary to filter on.

## The flow it's built for — probe, then compose

> *"Design a protein that binds target X, then check the designs are plausible."*

1. **Which models?** `search_models(task="inverse_folding")` → ProteinMPNN + friends, each with a
   one-liner and capability tags.
2. **Right fit?** `get_model_knowledge("mpnn")` → when to use / when NOT, benchmarks, and its
   **complements** point at ESM-2 for scoring.
3. **How to call them?** `get_model_schema("mpnn", "generate")` + `get_model_schema("esm2-650m",
   "log_prob")` → exact request/response JSON Schemas.
4. **Run the chain.** `invoke_action("mpnn", "generate", …)` designs → `invoke_action("esm2-650m",
   "log_prob", …)` scores them. All from metadata the MCP already had.

The narrative version of this — the "why it exists" pitch — is the [For agents (MCP)](../../docs/mcp.md)
docs page.

## Invoking models — and what happens when things go wrong

`invoke_action` dispatches to your deployed models via the Modal SDK using the credentials of the
process running `bh mcp` (the same way `bh serve` calls models). Target a specific Modal environment
with `bh mcp --env biolm-hub-dev`, or pass `gateway_url=` to route through a deployed gateway instead.

Every failure comes back as a **short, actionable error** (an MCP `isError` result — never a stack
trace):

| Situation | What the agent sees |
|-----------|---------------------|
| Model isn't deployed | `Model 'esm2-650m' isn't deployed to Modal. Deploy it with: bh deploy esm2` |
| Modal auth/token missing | `Modal authentication failed. Set up credentials with: modal token new` |
| Timed out / can't reach Modal | `'esm2-650m/encode' timed out on Modal.` / `Couldn't reach Modal…` |
| Invalid input | `Invalid input for esm2-650m/encode: items.0.sequence: field required` (before any call) |
| The model rejects the request | The model's own `detail` + error `code`, surfaced verbatim |

> [!WARNING]
> **`invoke_action` bills your Modal account** and hits unauthenticated endpoints, exactly like the
> gateway. Everything else (`list_models`, `search_models`, `get_model_knowledge`, `get_model_schema`
> and all resources) is **static and offline** — no Modal, no credentials, no billing.

## How it stays in sync

The server is a thin consumer of the same config-driven catalog the gateway, docs, and README already
share (`gateway.model_discovery.get_model_mapper`) plus the shared knowledge loader
(`models/commons/catalog/knowledge.py`). **Adding a model under `models/<name>/` needs zero MCP code** —
it just appears — and a uniformity test fails CI if it ever wouldn't.
