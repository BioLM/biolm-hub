"""In-process (no network, no Modal) tests for the compose + OpenAPI MCP surface.

Drives the server with a real MCP client over in-memory streams, exactly as a client would. Covers
the knowledge-graph traversal tools (find_alternatives / find_complements / suggest_pipeline), the
get_openapi tool + biolm://openapi resource, and the compose_pipeline prompt. All offline: FastAPI
(the [serve] extra) is present in this repo's venv, so the OpenAPI path is exercised for real.
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
    assert result.structuredContent is not None
    return dict(result.structuredContent)


def _content_text(result: Any) -> str:
    block = result.content[0]
    assert isinstance(block, TextContent)
    return block.text


def _resource_text(read_result: Any) -> str:
    block = read_result.contents[0]
    assert isinstance(block, TextResourceContents)
    return block.text


async def test_find_alternatives_returns_shaped_edges() -> None:
    async with connect(SERVER) as client:
        await client.initialize()
        result = await client.call_tool("find_alternatives", {"slug": "esm2"})
        assert not result.isError
        data = _structured(result)
        assert data["slug"] == "esm2"
        alts = data["alternatives"]
        assert alts, "esm2 should have alternatives"
        assert all("model" in a for a in alts)
        assert any(a.get("when_better") for a in alts)


async def test_find_complements_returns_shaped_edges() -> None:
    async with connect(SERVER) as client:
        await client.initialize()
        # A variant slug must resolve to the base family's complements.
        result = await client.call_tool("find_complements", {"slug": "esm2-650m"})
        assert not result.isError
        data = _structured(result)
        assert data["slug"] == "esm2"
        comps = data["complements"]
        assert comps, "esm2 should have complements"
        assert all("model" in c for c in comps)
        assert any(c.get("workflow") for c in comps)


async def test_find_alternatives_unknown_slug_is_error() -> None:
    async with connect(SERVER) as client:
        await client.initialize()
        result = await client.call_tool(
            "find_alternatives", {"slug": "not-a-real-model"}
        )
        assert result.isError


async def test_suggest_pipeline_is_ordered_and_deterministic() -> None:
    async with connect(SERVER) as client:
        await client.initialize()
        first = _structured(
            await client.call_tool("suggest_pipeline", {"goal": "design a protein"})
        )
        steps = first["steps"]
        assert steps, "a design goal should yield at least one step"
        assert steps[0]["role"] == "primary"
        assert all({"slug", "role", "why"} <= set(s) for s in steps)
        # No repeated model in the chain (the traversal tracks visited slugs).
        slugs = [s["slug"] for s in steps]
        assert len(slugs) == len(set(slugs))
        assert first["rationale"]

        # Deterministic: same goal → identical suggestion.
        second = _structured(
            await client.call_tool("suggest_pipeline", {"goal": "design a protein"})
        )
        assert second == first


async def test_get_openapi_returns_a_document_with_paths() -> None:
    async with connect(SERVER) as client:
        await client.initialize()
        result = await client.call_tool("get_openapi", {})
        assert not result.isError
        spec = json.loads(_content_text(result))
        assert "paths" in spec and spec["paths"]
        assert any(p.startswith("/api/v1/") for p in spec["paths"])


async def test_get_openapi_slice_filters_to_one_model() -> None:
    async with connect(SERVER) as client:
        await client.initialize()
        result = await client.call_tool("get_openapi", {"slug": "esm2"})
        assert not result.isError
        spec = json.loads(_content_text(result))
        paths = spec["paths"]
        assert paths, "sliced spec should still have esm2 paths"
        assert all(p.startswith("/api/v1/esm2") for p in paths)


async def test_openapi_resource_resolves() -> None:
    async with connect(SERVER) as client:
        await client.initialize()
        spec = json.loads(
            _resource_text(await client.read_resource(AnyUrl("biolm://openapi")))
        )
        assert "paths" in spec and spec["paths"]


async def test_compose_prompt_is_listed_and_renders_the_goal() -> None:
    async with connect(SERVER) as client:
        await client.initialize()
        names = {p.name for p in (await client.list_prompts()).prompts}
        assert "compose_pipeline" in names

        rendered = await client.get_prompt(
            "compose_pipeline", {"goal": "design a protein binder"}
        )
        text = " ".join(
            block.text
            for message in rendered.messages
            if isinstance(block := message.content, TextContent)
        )
        assert "design a protein binder" in text
        assert "complements" in text
