"""In-process (no network, no Modal) tests for the MCP server.

Drives the server with a real MCP client over in-memory streams, so tools and resources are
exercised exactly as a client would. The server is built once and reused across sessions.
"""

from __future__ import annotations

import json
from typing import Any

from mcp.shared.memory import create_connected_server_and_client_session as connect
from mcp.types import TextContent, TextResourceContents
from pydantic import AnyUrl

from gateway.mcp.server import build_mcp_server
from gateway.model_discovery import get_model_mapper

SERVER = build_mcp_server(get_model_mapper())


def _structured(result: Any) -> dict[str, Any]:
    """The tool call's structured payload (asserting it is present)."""
    assert result.structuredContent is not None
    return dict(result.structuredContent)


def _content_text(result: Any) -> str:
    """The first text block of a tool call's unstructured content."""
    block = result.content[0]
    assert isinstance(block, TextContent)
    return block.text


def _resource_text(read_result: Any) -> str:
    """The text body of a read resource (asserting it is text, not a blob)."""
    block = read_result.contents[0]
    assert isinstance(block, TextResourceContents)
    return block.text


async def test_lists_expected_tools_and_resources() -> None:
    async with connect(SERVER) as client:
        await client.initialize()
        tools = {t.name for t in (await client.list_tools()).tools}
        assert {
            "list_models",
            "search_models",
            "get_model_knowledge",
            "get_model_schema",
        } <= tools
        resources = {str(r.uri) for r in (await client.list_resources()).resources}
        assert {"biolm://catalog", "biolm://capabilities"} <= resources
        templates = {
            t.uriTemplate
            for t in (await client.list_resource_templates()).resourceTemplates
        }
        assert "biolm://model/{slug}/knowledge" in templates
        assert "biolm://model/{slug}/schema" in templates


async def test_search_models_filters_by_molecule_and_ranks() -> None:
    async with connect(SERVER) as client:
        await client.initialize()
        result = await client.call_tool(
            "search_models", {"query": "protein embedding", "molecule": "protein"}
        )
        assert not result.isError
        cards = _structured(result)["result"]
        assert "esm2" in [c["slug"] for c in cards]
        assert all("protein" in c["molecules"] for c in cards)


async def test_list_models_action_filter_actually_filters() -> None:
    async with connect(SERVER) as client:
        await client.initialize()
        everything = _structured(await client.call_tool("list_models", {}))["result"]
        encoders = _structured(
            await client.call_tool("list_models", {"action": "encode"})
        )["result"]
        assert 0 < len(encoders) < len(everything)
        assert all("encode" in c["actions"] for c in encoders)


async def test_get_model_knowledge_json_and_markdown() -> None:
    async with connect(SERVER) as client:
        await client.initialize()
        kg = _structured(
            await client.call_tool("get_model_knowledge", {"slug": "esm2"})
        )["result"]
        assert kg["slug"] == "esm2"
        assert kg["strengths"] and kg["dont_use_when"]

        as_md = await client.call_tool(
            "get_model_knowledge", {"slug": "esm2", "format": "md"}
        )
        assert _content_text(as_md).startswith("# ESM2")


async def test_get_model_schema_accepts_variant_slug() -> None:
    async with connect(SERVER) as client:
        await client.initialize()
        data = _structured(
            await client.call_tool(
                "get_model_schema", {"slug": "esm2-650m", "action": "encode"}
            )
        )
        assert data["slug"] == "esm2"
        assert [a["action"] for a in data["actions"]] == ["encode"]
        assert "properties" in data["actions"][0]["request_schema"]


async def test_unknown_model_is_reported_as_error() -> None:
    async with connect(SERVER) as client:
        await client.initialize()
        result = await client.call_tool(
            "get_model_knowledge", {"slug": "not-a-real-model"}
        )
        assert result.isError


async def test_capabilities_resource_exposes_the_vocabulary() -> None:
    async with connect(SERVER) as client:
        await client.initialize()
        caps = json.loads(
            _resource_text(await client.read_resource(AnyUrl("biolm://capabilities")))
        )
        assert "protein" in caps["molecules"]
        assert "encode" in caps["actions"]
        assert "structure_prediction" in caps["tasks"]


async def test_catalog_resource_and_model_templates_resolve() -> None:
    async with connect(SERVER) as client:
        await client.initialize()
        catalog = json.loads(
            _resource_text(await client.read_resource(AnyUrl("biolm://catalog")))
        )
        assert any(c["slug"] == "esm2" for c in catalog)
        kg = json.loads(
            _resource_text(
                await client.read_resource(AnyUrl("biolm://model/esm2/knowledge"))
            )
        )
        assert kg["slug"] == "esm2"
