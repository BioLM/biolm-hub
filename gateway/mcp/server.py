"""Build the biolm-hub MCP server: curated tools mirrored by cacheable resources.

Tools guarantee reachability across MCP clients (some don't auto-read resources); resources give
clients that do a cheap, cacheable copy of the same data. The whole probe surface is static — pure
functions of the repo tree — so it needs no Modal and no credentials. ``build_mcp_server`` is used
by ``bh mcp`` (stdio) and, later, by a hosted Streamable-HTTP deployment.
"""

from __future__ import annotations

from typing import Any, Optional

from pydantic import TypeAdapter

from gateway.mcp import catalog as cat
from gateway.mcp import compose
from gateway.mcp._sdk import FastMCP
from gateway.mcp.invoke import invoke_action as run_invoke
from gateway.model_discovery import ModelMapper
from models.commons.catalog.knowledge import (
    ModelKnowledge,
    load_model_knowledge_for_slug,
)

_INSTRUCTIONS = """\
biolm-hub is a catalog of open biological ML models (protein language models, structure
prediction, inverse folding, generation, and more). Use this server to probe the catalog before
composing a pipeline:

- `list_models` / `search_models` — find candidate models by capability (molecule, task, action).
- `get_model_knowledge` — read a model's when-to-use / when-NOT-to-use, strengths, benchmarks,
  alternatives and complements. This is how you decide *which* models and in *what order*.
- `get_model_schema` — get a model's per-action request/response JSON Schema (how to call it).
- `find_alternatives` / `find_complements` — traverse the knowledge graph: swap a model for a
  competitor, or find the models it chains with (and how).
- `suggest_pipeline` — a deterministic, explainable first-draft pipeline for a free-text goal
  (a heuristic over the complements graph, not an LLM plan).
- `get_openapi` — the gateway's full OpenAPI document (optionally sliced to one model).
- `invoke_action` — run a step of the pipeline on a deployed model variant. Fails cleanly if the
  model isn't deployed or input is invalid, so probe → schema → invoke is safe to chain.

The `biolm://` resources mirror the same data for clients that cache resources. Read
`biolm://capabilities` for the exact molecule/task/action vocabulary to filter on. The
`compose_pipeline` prompt seeds a probe-then-compose plan for an open-ended goal.
"""

_CARDS_ADAPTER = TypeAdapter(list[cat.ModelCard])


def _dump_cards(cards: list[cat.ModelCard]) -> str:
    return _CARDS_ADAPTER.dump_json(cards, indent=2).decode()


def build_mcp_server(mapper: ModelMapper) -> FastMCP:
    """Construct the MCP server, precomputing the (static) catalog snapshot + capability vocab."""
    snapshot = cat.build_snapshot(mapper)
    capabilities = cat.build_capabilities()
    mcp = FastMCP("biolm-hub", instructions=_INSTRUCTIONS)
    _register_tools(mcp, mapper, snapshot)
    _register_compose_tools(mcp, mapper, snapshot)
    _register_resources(mcp, mapper, snapshot, capabilities)
    _register_prompts(mcp, snapshot, capabilities)
    return mcp


def _register_tools(
    mcp: FastMCP, mapper: ModelMapper, snapshot: cat.CatalogSnapshot
) -> None:
    @mcp.tool(
        description="List catalog models, optionally filtered by molecule / task / action capability."
    )
    def list_models(
        molecule: Optional[str] = None,
        task: Optional[str] = None,
        action: Optional[str] = None,
    ) -> list[cat.ModelCard]:
        return cat.search_cards(snapshot, None, molecule, task, action)

    @mcp.tool(
        description="Search models by free-text query plus optional capability filters; ranked by match."
    )
    def search_models(
        query: str,
        molecule: Optional[str] = None,
        task: Optional[str] = None,
        action: Optional[str] = None,
    ) -> list[cat.ModelCard]:
        return cat.search_cards(snapshot, query, molecule, task, action)

    @mcp.tool(
        description=(
            "Get a model's knowledge graph: when to use it, when NOT to, strengths, weaknesses, "
            "alternatives, complements, benchmarks and citations. `format` is 'json' (default) or 'md'."
        )
    )
    def get_model_knowledge(slug: str, format: str = "json") -> ModelKnowledge | str:
        base = _require_base(mapper, slug)
        knowledge = load_model_knowledge_for_slug(base)
        return knowledge.to_markdown() if format == "md" else knowledge

    @mcp.tool(
        description="Get request + response JSON Schemas for a model's actions (all, or one via `action`)."
    )
    def get_model_schema(slug: str, action: Optional[str] = None) -> cat.ModelSchemas:
        base = _require_base(mapper, slug)
        return cat.build_model_schemas(mapper, base, action)

    @mcp.tool(
        description=(
            "Invoke a model action on a DEPLOYED variant — e.g. slug='esm2-650m', action='encode', "
            "items=[{'sequence': 'MKT...'}]. Returns the model's response. Fails cleanly (not a stack "
            "trace) if the model isn't deployed, Modal auth is missing, or the input is invalid. Pass "
            "gateway_url to route through a deployed gateway instead of local Modal. Use "
            "get_model_schema first to see the exact request shape."
        )
    )
    async def invoke_action(
        slug: str,
        action: str,
        items: list[dict[str, Any]],
        params: Optional[dict[str, Any]] = None,
        gateway_url: Optional[str] = None,
    ) -> dict[str, Any]:
        return await run_invoke(mapper, slug, action, items, params, gateway_url)


def _register_compose_tools(
    mcp: FastMCP, mapper: ModelMapper, snapshot: cat.CatalogSnapshot
) -> None:
    """Register the graph-traversal / composition tools (kept separate so each stays under the
    complexity cap and the probe tools above read cleanly)."""

    @mcp.tool(
        description=(
            "Get a model's alternatives — competing models with when-each-is-better/worse notes, "
            "so you can swap it out. Accepts a base or variant slug."
        )
    )
    def find_alternatives(slug: str) -> compose.AlternativesResult:
        return compose.alternatives_for(_require_base(mapper, slug))

    @mcp.tool(
        description=(
            "Get a model's complements — the models it chains with in a pipeline, each with the "
            "workflow (and example protocol) for how they compose. Accepts a base or variant slug."
        )
    )
    def find_complements(slug: str) -> compose.ComplementsResult:
        return compose.complements_for(_require_base(mapper, slug))

    @mcp.tool(
        description=(
            "Suggest a deterministic, explainable pipeline for a free-text goal (e.g. 'design a "
            "protein binder, then check it's plausible'). A transparent heuristic — NOT an LLM "
            "plan: it seeds from the best keyword match and follows the knowledge graph's "
            "`complements` edges into an ordered chain of {slug, role, why}. A starting point to "
            "refine — verify each step with get_model_schema before invoking."
        )
    )
    def suggest_pipeline(goal: str) -> compose.PipelineSuggestion:
        return compose.suggest_pipeline(mapper, snapshot, goal)

    @mcp.tool(
        description=(
            "Get the gateway's full OpenAPI (JSON) document — every model's HTTP route + schema. "
            "Generated in-process (no running gateway). Pass `slug` to slice to one model's paths. "
            "Needs the [serve] extra installed; returns a clean error if it isn't."
        )
    )
    def get_openapi(slug: Optional[str] = None) -> dict[str, Any]:
        base = _require_base(mapper, slug) if slug else None
        return compose.build_openapi_spec(mapper, base)


def _register_resources(
    mcp: FastMCP,
    mapper: ModelMapper,
    snapshot: cat.CatalogSnapshot,
    capabilities: cat.Capabilities,
) -> None:
    @mcp.resource(
        "biolm://catalog",
        mime_type="application/json",
        description="Whole catalog: every model with tags, actions, variants and one-liner.",
    )
    def catalog_resource() -> str:
        return _dump_cards(snapshot.cards)

    @mcp.resource(
        "biolm://capabilities",
        mime_type="application/json",
        description="Controlled vocabulary: molecules, tasks, modalities, architectures, actions.",
    )
    def capabilities_resource() -> str:
        return capabilities.model_dump_json(indent=2)

    @mcp.resource(
        "biolm://openapi",
        mime_type="application/json",
        description="The gateway's full OpenAPI document (needs the [serve] extra).",
    )
    def openapi_resource() -> str:
        import json

        return json.dumps(compose.build_openapi_spec(mapper), indent=2)

    @mcp.resource(
        "biolm://model/{slug}",
        mime_type="application/json",
        description="One model's compact catalog card.",
    )
    def model_card_resource(slug: str) -> str:
        base = _require_base(mapper, slug)
        card = next((c for c in snapshot.cards if c.slug == base), None)
        return card.model_dump_json(indent=2) if card else "{}"

    @mcp.resource(
        "biolm://model/{slug}/knowledge",
        mime_type="application/json",
        description="One model's full knowledge graph.",
    )
    def model_knowledge_resource(slug: str) -> str:
        base = _require_base(mapper, slug)
        return load_model_knowledge_for_slug(base).model_dump_json(indent=2)

    @mcp.resource(
        "biolm://model/{slug}/schema",
        mime_type="application/json",
        description="One model's action request/response JSON Schemas.",
    )
    def model_schema_resource(slug: str) -> str:
        base = _require_base(mapper, slug)
        return cat.build_model_schemas(mapper, base).model_dump_json(indent=2)


def _register_prompts(
    mcp: FastMCP, snapshot: cat.CatalogSnapshot, capabilities: cat.Capabilities
) -> None:
    """Register the composition prompt that seeds an agent's probe-then-compose plan."""

    @mcp.prompt(
        description="Seed a probe-then-compose plan over the catalog for an open-ended goal."
    )
    def compose_pipeline(goal: str) -> str:
        return compose.build_compose_prompt(snapshot, capabilities, goal)


def _require_base(mapper: ModelMapper, slug: str) -> str:
    """Resolve a base/variant slug to its base, raising a clean error for an unknown model."""
    base = cat.resolve_base_slug(mapper, slug)
    if base is None:
        raise ValueError(
            f"Unknown model '{slug}'. Use list_models to see available slugs."
        )
    return base
