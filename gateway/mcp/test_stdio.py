"""End-to-end regression test: ``bh mcp`` over stdio speaks clean JSON-RPC.

Spawns the real CLI as a subprocess and drives it with a genuine MCP stdio client. This guards the
stdout-pollution bug: the framework logs to **stdout** by default (right for Modal, which captures
stdout — fatal for a stdio server, where stdout is the JSON-RPC channel), so ``bh mcp`` routes
logging to stderr. If that regresses, the log lines corrupt the stream and the client below fails to
parse them, failing this test. Modal-free (probing only), so it runs in the normal unit tier.
"""

from __future__ import annotations

import sys

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


async def test_bh_mcp_stdio_speaks_clean_jsonrpc() -> None:
    # `python -m cli.main mcp` is exactly what `bh mcp` runs, resolved to this venv's interpreter.
    params = StdioServerParameters(
        command=sys.executable, args=["-m", "cli.main", "mcp"]
    )
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()  # fails here if stdout carries non-JSON-RPC (log) lines
            tools = {t.name for t in (await session.list_tools()).tools}
            assert {"list_models", "search_models", "get_model_knowledge"} <= tools
            result = await session.call_tool(
                "list_models", {"task": "structure_prediction"}
            )
            assert result.structuredContent is not None
            assert result.structuredContent[
                "result"
            ], "a tool call round-trips cleanly over stdio"
