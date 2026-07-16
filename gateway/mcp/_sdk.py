"""Single import site for the MCP SDK — a firewall against SDK churn.

Everything in ``gateway.mcp`` imports the server class from here rather than from ``mcp`` directly,
so a future SDK bump (v2 renames ``FastMCP`` → ``MCPServer`` and reworks internals) touches exactly
one file. ``bh mcp`` guards the import with a friendly "install the ``[mcp]`` extra" message, so the
raw ``ModuleNotFoundError`` never reaches a user.
"""

from mcp.server.fastmcp import FastMCP

__all__ = ["FastMCP"]
