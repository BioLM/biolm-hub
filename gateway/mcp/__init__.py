"""Model Context Protocol (MCP) server for the biolm-hub catalog.

A lightweight, metadata-rich surface over the same config-driven catalog the gateway, docs, and
README already share. It lets a consuming agent probe every model's knowledge graph and per-action
JSON Schema, decide which models to chain and in what order, then (later) invoke them.

The server is a thin consumer of :func:`gateway.model_discovery.get_model_mapper` plus the shared
knowledge loader in :mod:`models.commons.catalog.knowledge` — it never re-enumerates models, so
adding a model under ``models/<name>/`` requires zero MCP code. Launch it with ``bh mcp``.
"""
