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
- `invoke_action` — run a step of the pipeline on a deployed model variant. Fails cleanly if the
  model isn't deployed or input is invalid, so probe → schema → invoke is safe to chain.

The `biolm://` resources mirror the same data for clients that cache resources. Read
`biolm://capabilities` for the exact molecule/task/action vocabulary to filter on.
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
    _register_resources(mcp, mapper, snapshot, capabilities)
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


def _require_base(mapper: ModelMapper, slug: str) -> str:
    """Resolve a base/variant slug to its base, raising a clean error for an unknown model."""
    base = cat.resolve_base_slug(mapper, slug)
    if base is None:
        raise ValueError(
            f"Unknown model '{slug}'. Use list_models to see available slugs."
        )
    return base
