"""Modal-free tests for the gateway ``GET /api/v1/{model}/knowledge`` route.

Uses FastAPI's TestClient against an in-process gateway app (no Modal, no network): the route
reads knowledge-graph files from the repo tree, so it is fully offline-testable.
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from gateway.model_discovery import get_model_mapper
from gateway.routing import build_gateway_app


def _client() -> TestClient:
    mapper = get_model_mapper()
    return TestClient(build_gateway_app(mapper, use_cache=False))


def test_knowledge_json_is_the_default() -> None:
    resp = _client().get("/api/v1/esm2/knowledge")
    assert resp.status_code == 200
    body = resp.json()
    assert body["slug"] == "esm2"
    assert body["display_name"] == "ESM2"
    assert body["strengths"]
    assert body["dont_use_when"]
    assert set(body["documents"]) == {"README", "MODEL", "BIOLOGY"}


def test_knowledge_markdown_on_request() -> None:
    resp = _client().get("/api/v1/esm2/knowledge", params={"format": "md"})
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/markdown")
    assert resp.text.startswith("# ESM2")


def test_knowledge_accepts_a_variant_slug() -> None:
    resp = _client().get("/api/v1/esm2-650m/knowledge")
    assert resp.status_code == 200
    assert resp.json()["slug"] == "esm2"


def test_unknown_model_returns_404() -> None:
    resp = _client().get("/api/v1/not-a-real-model/knowledge")
    assert resp.status_code == 404
