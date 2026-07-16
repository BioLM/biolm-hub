# For agents: the catalog over MCP

The whole catalog, exposed to an agent over the **Model Context Protocol** — so an agent can *reason
about* the models (what each does, when to use it, its exact request shape) before it *runs* them.
Richer than the raw HTTP API: instead of you hand-wiring calls, the agent probes the catalog and
composes its own pipeline.

## Why this exists — probe, then compose

Give an agent an open-ended goal and it can solve it from metadata it already has:

> **"Design a protein that binds target X, then check the designs are plausible."**
>
> 1. **Which models?** `search_models(task="inverse_folding")` → ProteinMPNN, and friends, each with a
>    one-line summary and its capability tags.
> 2. **Is it the right fit?** `get_model_knowledge("mpnn")` → when to use it, when *not* to, its
>    benchmarks — and its **complements**, which point at **ESM-2** for scoring designed sequences.
> 3. **How do I call them?** `get_model_schema("mpnn", "generate")` and
>    `get_model_schema("esm2-650m", "log_prob")` → the exact request/response JSON Schemas.
> 4. **Run the chain.** `invoke_action("mpnn", "generate", …)` produces designs →
>    `invoke_action("esm2-650m", "log_prob", …)` scores them. Keep the plausible ones.

No glue code, no reading docs by hand — the agent discovered the models, learned how to combine them,
and executed the pipeline through one interface. That's the point: **the knowledge graph and schemas
are the API.**

## Connect in 30 seconds

```bash
pip install "biolm-hub[mcp]"     # the MCP server is an opt-in extra
bh mcp                           # stdio (local, zero network) — the everyday path
# or serve it for a remote/multi-client agent:
bh mcp --http --port 9000        # Streamable HTTP → http://127.0.0.1:9000/mcp
```

Point an agent at it. For any client that reads an `mcpServers` config (Claude Desktop, Claude Code,
an SDK agent):

```json
{ "mcpServers": { "biolm-hub": { "command": "bh", "args": ["mcp"] } } }
```

Probing the catalog needs **no Modal account** — it reads the repo. Only `invoke_action` runs a model
(and bills your Modal account, like any deployed endpoint).

## What the agent gets

| Tool | Does |
|------|------|
| `list_models` | List models, filter by molecule / task / action. |
| `search_models` | Free-text + capability search, ranked — the "which models?" step. |
| `get_model_knowledge` | When to use / when **not**, strengths, alternatives, complements, benchmarks, citations (`format` = `json` or `md`). |
| `get_model_schema` | A model's per-action request/response JSON Schema. |
| `invoke_action` | Run an action on a deployed model — with clean, actionable errors if it isn't deployed, auth fails, or the input is invalid. |

The same data is mirrored as cacheable **resources** (`biolm://catalog`, `biolm://capabilities`,
`biolm://model/{slug}[/knowledge|/schema]`) for clients that read them. Start from
`biolm://capabilities` for the exact molecule/task/action vocabulary to filter on.

## The property that makes it scale

Every tool and resource is **generated from the catalog** — the same config + knowledge-graph files
that drive the docs and the gateway. So **adding a model to `models/` gives every agent a new
capability with zero glue code**: it simply appears in `search_models`, gets its own
`biolm://model/<name>/…` resources, and becomes invokable. A uniformity test fails CI if it ever
wouldn't.

See [`gateway/mcp/README.md`](https://github.com/BioLM/biolm-hub/blob/main/gateway/mcp/README.md) in
the repo for the full runbook (hosting, edge-case behavior, dev loop).
