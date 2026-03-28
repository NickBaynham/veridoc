"""Shared pytest configuration and fixtures."""

from __future__ import annotations

import asyncio
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
    monkeypatch.setenv("USE_FAKE_STORAGE", "true")

    from app.core.config import reset_settings_cache
    from app.db.session import DatabaseHealthResult, reset_engine
    from app.main import create_app
    from app.services.event_service import reset_event_hub
    from app.services.queue_backend import close_job_queue
    from app.services.storage_service import reset_object_storage

    reset_settings_cache()
    reset_object_storage()
    monkeypatch.setattr(
        "app.api.routes.health.database_health_check",
        lambda: DatabaseHealthResult(
            ok=True,
            dsn_preview="postgresql://stub:***@127.0.0.1:5432/stub",
        ),
    )

    from fastapi.testclient import TestClient

    application = create_app()
    with TestClient(application) as client:
        yield client

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
