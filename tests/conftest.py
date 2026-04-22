"""Shared pytest configuration and fixtures."""

from __future__ import annotations

import asyncio
import os
import shutil
from pathlib import Path

import pytest


@pytest.fixture
def api_client(monkeypatch):
    """
    FastAPI TestClient with fake job queue and DB health stubbed.
    Cleans ARQ pool / engine / event hub after each test.
    """
    monkeypatch.setenv("USE_FAKE_QUEUE", "true")
    monkeypatch.setenv("USE_FAKE_EVENT_HUB", "true")
    monkeypatch.setenv("USE_FAKE_STORAGE", "true")
    monkeypatch.setenv("USE_FAKE_OPENSEARCH", "true")
    monkeypatch.setenv("RATE_LIMIT_ENABLED", "false")

    from app.core.config import reset_settings_cache
    from app.db.session import DatabaseHealthResult, reset_engine
    from app.main import create_app
    from app.services.event_service import reset_event_hub
    from app.services.opensearch_document_index import reset_fake_opensearch_index
    from app.services.queue_backend import close_job_queue
    from app.services.storage_service import reset_object_storage

    reset_fake_opensearch_index()
    reset_settings_cache()
    reset_object_storage()

    def _stub_resolve_collections(_session, _auth_sub, settings):
        dc = settings.default_collection_id
        return [dc] if dc is not None else []

    monkeypatch.setattr(
        "app.services.search_service.resolve_accessible_collection_ids",
        _stub_resolve_collections,
    )

    monkeypatch.setattr(
        "app.api.routes.health.database_health_check",
        lambda: DatabaseHealthResult(
            ok=True,
            dsn_preview="postgresql://stub:***@127.0.0.1:5432/stub",
        ),
    )
    monkeypatch.setattr(
        "app.api.routes.health.check_opensearch_component",
        lambda _settings=None: ("up", None, None),
    )

    from app.auth.dependencies import (
        get_current_user,
        get_optional_current_user_sub,
        get_sse_subscriber_sub,
    )
    from fastapi.testclient import TestClient

    _fixed_sub = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"

    async def _test_user_id() -> str:
        return _fixed_sub

    async def _test_optional_sub() -> str | None:
        return _fixed_sub

    async def _test_sse_sub() -> str | None:
        return _fixed_sub

    application = create_app()
    application.dependency_overrides[get_current_user] = _test_user_id
    application.dependency_overrides[get_optional_current_user_sub] = _test_optional_sub
    application.dependency_overrides[get_sse_subscriber_sub] = _test_sse_sub
    with TestClient(application) as client:
        yield client
    application.dependency_overrides.pop(get_sse_subscriber_sub, None)
    application.dependency_overrides.pop(get_optional_current_user_sub, None)
    application.dependency_overrides.pop(get_current_user, None)

    asyncio.run(close_job_queue())
    reset_engine()
    reset_event_hub()
    reset_object_storage()
    reset_fake_opensearch_index()
    reset_settings_cache()


@pytest.fixture
def jwt_integration_client(monkeypatch: pytest.MonkeyPatch):
    """
    FastAPI TestClient with real Postgres, no `get_current_user` override — uses signed JWTs.

    Skips when DATABASE_URL is unset. Requires migrations applied (same as CI through 007).
    Yields (client, make_token) where make_token(sub=..., email=...) returns a Bearer string value.
    """
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        pytest.skip(
            "DATABASE_URL not set — jwt_integration_client needs Postgres with migrations applied"
        )

    monkeypatch.setenv("DATABASE_URL", database_url)
    monkeypatch.setenv("USE_FAKE_QUEUE", "true")
    monkeypatch.setenv("USE_FAKE_EVENT_HUB", "true")
    monkeypatch.setenv("USE_FAKE_STORAGE", "true")
    monkeypatch.setenv(
        "SUPABASE_JWT_SECRET",
        "jwt-integration-test-secret-must-be-long-enough-for-hs256!!",
    )
    monkeypatch.setenv("JWT_ALGORITHM", "HS256")
    monkeypatch.setenv("JWT_AUDIENCE", "authenticated")
    monkeypatch.setenv("VERIFIEDSIGNAL_AUTO_PROVISION_IDENTITY", "true")
    monkeypatch.setenv("VERIFIEDSIGNAL_ALLOW_DEFAULT_COLLECTION_FALLBACK", "true")
    monkeypatch.setenv("RATE_LIMIT_ENABLED", "false")
    monkeypatch.setenv("VERIFIEDSIGNAL_REQUIRE_AUTH_SSE", "true")

    from app.core.config import reset_settings_cache
    from app.db.session import reset_engine
    from app.main import create_app
    from app.services.event_service import reset_event_hub
    from app.services.queue_backend import close_job_queue
    from app.services.storage_service import reset_object_storage
    from fastapi.testclient import TestClient
    from jose import jwt

    reset_settings_cache()
    reset_object_storage()
    reset_engine()
    reset_event_hub()
    asyncio.run(close_job_queue())

    secret = os.environ["SUPABASE_JWT_SECRET"]

    def make_token(*, sub: str, email: str | None = None) -> str:
        payload: dict = {"sub": sub, "aud": "authenticated"}
        if email is not None:
            payload["email"] = email
        return jwt.encode(payload, secret, algorithm="HS256")

    application = create_app()
    with TestClient(application) as client:
        yield client, make_token

    asyncio.run(close_job_queue())
    reset_engine()
    reset_event_hub()
    reset_object_storage()
    reset_settings_cache()


@pytest.fixture(scope="session")
def repo_root() -> Path:
    """Repository root (contains pyproject.toml)."""
    return Path(__file__).resolve().parents[1]


@pytest.fixture(scope="session")
def docker_available() -> bool:
    return shutil.which("docker") is not None
