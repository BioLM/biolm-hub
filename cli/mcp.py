"""``bh mcp`` — run the biolm-hub MCP server.

Exposes the model catalog (knowledge graphs + per-action schemas) over the Model Context Protocol
so an agent can probe the catalog and compose a pipeline. Defaults to stdio (local, zero network);
``--http`` serves Streamable HTTP for remote/multi-client use. Guarded by the ``[mcp]`` extra,
mirroring how ``bh serve`` guards ``[serve]``.
"""

import os
from typing import Optional

import typer


def mcp_cmd(
    http: bool = typer.Option(
        False, "--http", help="Serve Streamable HTTP instead of stdio (local default)."
    ),
    host: str = typer.Option("127.0.0.1", help="Host to bind (with --http)."),
    port: int = typer.Option(9000, help="Port to bind (with --http)."),
    env: Optional[str] = typer.Option(
        None,
        "--env",
        "-e",
        help="Modal environment to target when invoke_action runs a model.",
    ),
) -> None:
    """Run the MCP server exposing the model catalog (stdio by default; --http for Streamable HTTP)."""
    try:
        from gateway.mcp.server import build_mcp_server
        from gateway.model_discovery import get_model_mapper
    except ImportError as e:
        raise typer.BadParameter(
            f"`bh mcp` needs the mcp extra ({e.name}). "
            'Install it with: pip install "biolm-hub[mcp]"'
        ) from e

    # stdio reserves stdout for the JSON-RPC protocol, so any log line on stdout corrupts the
    # stream and breaks the client. Route logging to stderr before anything logs (harmless under
    # --http). Model discovery logs during build_mcp_server, so this must come first.
    from models.commons.core.logging import route_root_logging_to_stderr

    route_root_logging_to_stderr()

    # invoke_action reads MODAL_ENVIRONMENT at call time (mirrors `bh serve`).
    if env:
        os.environ["MODAL_ENVIRONMENT"] = env

    server = build_mcp_server(get_model_mapper())
    if http:
        server.settings.host = host
        server.settings.port = port
        typer.echo(f"biolm-hub MCP (Streamable HTTP) → http://{host}:{port}/mcp")
        server.run(transport="streamable-http")
    else:
        server.run(transport="stdio")
