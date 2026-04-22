"""Integration: search and SSE require authentication by default (no dependency overrides)."""

from __future__ import annotations

from unittest.mock import MagicMock
from urllib.parse import quote

import pytest
from app.api.deps import get_db
from app.core.config import reset_settings_cache
from app.main import create_app
from fastapi.testclient import TestClient


@pytest.fixture
def unauth_api_client(monkeypatch: pytest.MonkeyPatch):
    """TestClient with real auth dependencies; DB session stubbed to avoid Postgres."""
    monkeypatch.setenv("USE_FAKE_QUEUE", "true")
    monkeypatch.setenv("USE_FAKE_STORAGE", "true")
    monkeypatch.setenv("USE_FAKE_OPENSEARCH", "true")
    monkeypatch.setenv("RATE_LIMIT_ENABLED", "false")
    # CI or a developer .env may set legacy anonymous SSE; plain GET on /events/stream then never ends.
    monkeypatch.setenv("VERIFIEDSIGNAL_REQUIRE_AUTH_SSE", "true")
    monkeypatch.setenv("VERIFIEDSIGNAL_REQUIRE_AUTH_SEARCH", "true")
    reset_settings_cache()

    def fake_db():
        yield MagicMock()

    application = create_app()
    application.dependency_overrides[get_db] = fake_db
    with TestClient(application) as client:
        yield client
    application.dependency_overrides.pop(get_db, None)
    reset_settings_cache()


@pytest.mark.integration
def test_search_returns_401_without_bearer(unauth_api_client: TestClient) -> None:
    r = unauth_api_client.get("/api/v1/search", params={"q": "x", "limit": 5})
    assert r.status_code == 401


@pytest.mark.integration
def test_sse_stream_returns_401_without_token(unauth_api_client: TestClient) -> None:
    # Same as authenticated case: never use .get() on SSE — it waits for an unbounded body.
    with unauth_api_client.stream("GET", "/api/v1/events/stream", timeout=5.0) as r:
        assert r.status_code == 401


@pytest.mark.integration
def test_search_allows_anonymous_when_flag_disabled(
    unauth_api_client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("VERIFIEDSIGNAL_REQUIRE_AUTH_SEARCH", "false")
    reset_settings_cache()
    r = unauth_api_client.get("/api/v1/search", params={"q": "x", "limit": 5})
    assert r.status_code == 200
    assert r.json()["index_status"] == "fake"


@pytest.mark.integration
def test_search_requires_bearer_jwt(jwt_integration_client) -> None:
    client, make_token = jwt_integration_client
    r = client.get("/api/v1/search", params={"q": "jwt-search", "limit": 5})
    assert r.status_code == 401

    sub = "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb"
    headers = {"Authorization": f"Bearer {make_token(sub=sub, email='s@example.com')}"}
    r2 = client.get("/api/v1/search", params={"q": "jwt-search", "limit": 5}, headers=headers)
    assert r2.status_code == 200
    assert r2.json()["index_status"] == "fake"


@pytest.mark.integration
def test_sse_accepts_access_token_query(jwt_integration_client) -> None:
    client, make_token = jwt_integration_client
    sub = "cccccccc-cccc-4ccc-8ccc-cccccccccccc"
    tok = make_token(sub=sub, email="sse@example.com")
    # SSE never finishes; plain client.get() waits for the full body and hangs.
    with client.stream(
        "GET",
        f"/api/v1/events/stream?access_token={quote(tok, safe='')}",
        timeout=5.0,
    ) as r:
        assert r.status_code == 200
