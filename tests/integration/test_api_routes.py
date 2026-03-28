"""Integration tests: FastAPI routes with stubbed infra (fake queue, DB health OK)."""

from __future__ import annotations

import pytest


@pytest.mark.integration
def test_health_ok(api_client):
    r = api_client.get("/api/v1/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["database"] == "up"
    assert body["redis"] == "stub"
    assert body["object_storage"] == "stub"
    assert body["opensearch"] == "up"


@pytest.mark.integration
def test_info(api_client):
    r = api_client.get("/api/v1/info")
    assert r.status_code == 200
    data = r.json()
    assert data["service"] == "verifiedsignal-api"
    assert "/api/v1" in data["api_prefix"]


@pytest.mark.integration
def test_search_stub(api_client):
    r = api_client.get("/api/v1/search", params={"q": "truth", "limit": 5})
    assert r.status_code == 200
    data = r.json()
    assert data["hits"] == []
    assert data["index_status"] == "stub"
