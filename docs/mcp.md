# For agents: the catalog over MCP

The whole catalog, exposed to an agent over the **Model Context Protocol** — so an agent can *reason
about* the models (what each does, when to use it, its exact request shape) before it *runs* them.
Richer than the raw HTTP API: instead of you hand-wiring calls, the agent probes the catalog and
composes its own pipeline.

## Why this exists — probe, then compose

Give an agent an open-ended goal and it can solve it from metadata it already has:

> **"Design a protein that binds target X, then check the designs are plausible."**
>
> 1. **Which models?** `list_models(task="inverse_folding")` → ProteinMPNN, and friends, each with a
>    one-line summary and its capability tags.
> 2. **Is it the right fit?** `get_model_knowledge("mpnn")` → when to use it, when *not* to, its
>    benchmarks — and its **complements**, which point at **ESM-2** for scoring designed sequences.
> 3. **How do I call them?** `get_model_schema("mpnn", "generate")` and
>    `get_model_schema("esm2-650m", "log_prob")` → the exact request/response JSON Schemas.
> 4. **Run the chain.** `invoke_action("protein-mpnn", "generate", …)` produces designs →
>    `invoke_action("esm2-650m", "log_prob", …)` scores them. Keep the plausible ones.

`invoke_action` needs a deployable **variant** slug (`protein-mpnn`, `esm2-650m`); the probe tools
(`get_model_knowledge`, `get_model_schema`, `find_complements`) also accept the **family** slug
(`mpnn`, `esm2`).

No glue code, no reading docs by hand — the agent discovered the models, learned how to combine them,
and executed the pipeline through one interface. That's the point: **the knowledge graph and schemas
are the API.**

## Connect in 30 seconds

```bash
pip install "biolm-hub[mcp]"     # the MCP server is an opt-in extra
```

A stdio MCP server is **spawned by the client, not run by hand.** You don't start `bh mcp` yourself and
leave it running — the client (Claude Code, Claude Desktop, the Inspector) launches it, talks JSON-RPC
over stdin/stdout, and shuts it down. Run bare in a terminal, `bh mcp` just blocks waiting for a client
and looks hung; that's expected. To *see* it yourself, use the Inspector below.

Probing the catalog needs **no Modal account** — it reads the repo. Only `invoke_action` runs a model
(and bills your Modal account, like any deployed endpoint).

### See it now — the MCP Inspector (zero config, no agent)

One command opens a browser UI with every tool and resource (needs Node). Use the **absolute path** to
the `bh` in your repo venv — a bare `bh` won't be on the spawned process's PATH:

```bash
npx @modelcontextprotocol/inspector "$(pwd)/.venv/bin/bh" mcp
```

Click `search_models`, read a model's knowledge graph, inspect a schema — all without an agent.
(Headless one-shot: `npx @modelcontextprotocol/inspector --cli "$(pwd)/.venv/bin/bh" mcp --method tools/list`.)

### Add it to Claude Code (the "wow")

Claude Code spawns the server against **its own** PATH, where the repo venv usually isn't active — so a
bare `bh` silently fails to resolve. Point it at the **absolute** path to the venv's `bh`, and use
`--scope user` so it's available in every session (the default `local` scope only works inside this repo
directory):

```bash
# from the repo root — $(pwd) bakes in the absolute path
claude mcp add --scope user biolm-hub -- "$(pwd)/.venv/bin/bh" mcp
```

Verify, then reload:

```bash
claude mcp list        # expect:  biolm-hub … ✔ Connected
```

A **running** Claude Code session won't see the new server until you restart it (or start a new
session). Then ask it something open-ended:

> *"With the biolm-hub tools: I have an antibody heavy + light chain and want to (a) check it's
> plausible, (b) get a 3D structure, and (c) propose a few CDR variants that stay structurally
> compatible. Which catalog models should I chain, in what order? For each step name the model and its
> action, tell me when NOT to use it, and show its request schema — don't run anything yet."*

Watch it call `search_models` → `get_model_knowledge` → `find_complements` → `get_model_schema` and
plan the whole pipeline from metadata alone. (To clean up later: `claude mcp remove biolm-hub`.)

### Other clients

Any client that reads an `mcpServers` config (Claude Desktop, an SDK agent) takes the same **absolute**
path — replace `/ABS/PATH/TO` with your checkout:

```json
{ "mcpServers": { "biolm-hub": { "command": "/ABS/PATH/TO/biolm-hub/.venv/bin/bh", "args": ["mcp"] } } }
```

Drop that into `claude_desktop_config.json` and **restart** Claude Desktop. To serve a
remote/multi-client agent instead, run `bh mcp --http` (Streamable HTTP at `http://127.0.0.1:9000/mcp`)
and give the client the URL — for Claude Code, with the server running:
`claude mcp add --transport http --scope user biolm-hub http://127.0.0.1:9000/mcp`.

## What the agent gets

| Tool | Does |
|------|------|
| `list_models` | List models, filter by molecule / task / action. |
| `search_models` | Free-text + capability search, ranked — the "which models?" step. |
| `get_model_knowledge` | When to use / when **not**, strengths, alternatives, complements, benchmarks, citations (`format` = `json` or `md`). |
| `get_model_schema` | A model's per-action request/response JSON Schema. |
| `find_alternatives` | A model's alternatives — competitors with when-each-is-better/worse notes, to swap one out. |
| `find_complements` | A model's complements — the models it chains with, and the workflow for how. |
| `suggest_pipeline` | A deterministic, explainable first-draft pipeline for a free-text goal — a heuristic over the complements graph, **not** an LLM plan. |
| `get_openapi` | The gateway's full OpenAPI (JSON), generated in-process; optional `slug` slices to one model (needs the `[serve]` extra). |
| `invoke_action` | Run an action on a deployed model — with clean, actionable errors if it isn't deployed, auth fails, or the input is invalid. |

The same data is mirrored as cacheable **resources** (`biolm://catalog`, `biolm://capabilities`,
`biolm://openapi`, `biolm://model/{slug}[/knowledge|/schema]`) for clients that read them, and the
`compose_pipeline(goal)` **prompt** seeds a probe-then-compose plan. Start from
`biolm://capabilities` for the exact molecule/task/action vocabulary to filter on.

Host the whole thing on Modal (stateless Streamable HTTP) with `modal deploy gateway/mcp/deploy_mcp.py`
— an opt-in, unauthenticated surface with the same stance as the gateway.

## The property that makes it scale

Every tool and resource is **generated from the catalog** — the same config + knowledge-graph files
that drive the docs and the gateway. So **adding a model to `models/` gives every agent a new
capability with zero glue code**: it simply appears in `search_models`, gets its own
`biolm://model/<name>/…` resources, and becomes invokable. A uniformity test fails CI if it ever
wouldn't.

See [`gateway/mcp/README.md`](https://github.com/BioLM/biolm-hub/blob/main/gateway/mcp/README.md) in
the repo for the full runbook (hosting, edge-case behavior, dev loop).
