"""Modal-free tests for the W9 catalog web app.

Covers catalog data generation (route scanning) and the deployment-status
mapping. The Modal query is monkeypatched, so these run with no Modal/R2.
"""

from gateway.catalog import deployment_status as ds
from gateway.catalog.deployment_status import get_deployment_status
from gateway.catalog.generator import generate_catalog_data
from gateway.model_discovery import get_model_mapper
from gateway.routing import build_gateway_app


def test_catalog_generation_produces_endpoints():
    mapper = get_model_mapper()
    app = build_gateway_app(mapper, use_cache=False)
    catalog = generate_catalog_data(app)

    assert catalog, "catalog should not be empty"
    # peptides is a known single-variant model with an encode endpoint.
    assert "peptides" in catalog
    endpoints = catalog["peptides"]["endpoints"]
    assert endpoints
    assert all("path" in e and "method" in e for e in endpoints)
    assert any(e["path"].startswith("/api/v3/peptides/") for e in endpoints)


def test_deployment_status_maps_deployed_and_undeployed(monkeypatch):
    mapper = get_model_mapper()
    peptides_app = mapper.get_variant_info("peptides")["modal_app_name"]
    # Pretend only the peptides app is deployed.
    monkeypatch.setattr(
        ds, "get_deployed_app_names", lambda environment=None: {peptides_app}
    )

    status = get_deployment_status(mapper)
    assert status["peptides"] is True
    assert any(v is False for slug, v in status.items() if slug != "peptides")


def test_deployment_status_unknown_when_query_fails(monkeypatch):
    mapper = get_model_mapper()
    # Query failure → None for every slug (status unknown, never wrongly "undeployed").
    monkeypatch.setattr(ds, "get_deployed_app_names", lambda environment=None: None)

    status = get_deployment_status(mapper)
    assert status
    assert all(v is None for v in status.values())


# --- Route-level rendering (FastAPI TestClient; no Modal — status monkeypatched) ---


def _catalog_client(monkeypatch, deployed_app_names):
    from fastapi.testclient import TestClient

    from gateway.catalog.mount import mount_catalog

    mapper = get_model_mapper()
    app = build_gateway_app(mapper, use_cache=False)
    monkeypatch.setattr(
        ds, "get_deployed_app_names", lambda environment=None: deployed_app_names
    )
    mount_catalog(app, mapper)
    return TestClient(app)


def test_catalog_page_renders_status_badges(monkeypatch):
    mapper = get_model_mapper()
    peptides_app = mapper.get_variant_info("peptides")["modal_app_name"]
    client = _catalog_client(monkeypatch, {peptides_app})

    resp = client.get("/catalog")
    assert resp.status_code == 200
    assert "BioLM API Catalog" in resp.text
    assert "● deployed" in resp.text  # peptides
    assert "● not deployed" in resp.text  # the rest


def test_model_page_deployed_vs_undeployed(monkeypatch):
    mapper = get_model_mapper()
    peptides_app = mapper.get_variant_info("peptides")["modal_app_name"]

    deployed = _catalog_client(monkeypatch, {peptides_app})
    r1 = deployed.get("/catalog/peptides")
    assert r1.status_code == 200
    assert "deploy-notice" not in r1.text
    assert "disabled title" not in r1.text

    undeployed = _catalog_client(monkeypatch, set())
    r2 = undeployed.get("/catalog/peptides")
    assert r2.status_code == 200
    assert "deploy-notice" in r2.text
    assert "disabled title" in r2.text

    assert undeployed.get("/catalog/does-not-exist").status_code == 404
