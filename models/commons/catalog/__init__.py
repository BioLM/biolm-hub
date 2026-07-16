"""Catalog-level, config-free readers for per-model metadata.

Currently exposes the shared knowledge-graph loader (:mod:`models.commons.catalog.knowledge`),
which turns a model's ``sources.yaml`` / ``comparison.yaml`` / ``README.md`` /
``MODEL.md`` / ``BIOLOGY.md`` into one typed :class:`~models.commons.catalog.knowledge.ModelKnowledge`
object. It is the single source consumed by the gateway ``/knowledge`` route, the
per-model ``knowledge_graph()`` container method, and the MCP server.
"""
