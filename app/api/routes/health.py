"""Liveness and dependency health."""

from __future__ import annotations

from fastapi import APIRouter

from app.core.config import get_settings
from app.db.session import database_health_check
from app.schemas.health import HealthResponse

router = APIRouter(tags=["health"])


def _include_database_health_details() -> bool:
    """Omit DSN preview and errors in production responses."""
    return get_settings().environment.lower() not in ("production", "prod")


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    h = database_health_check()
    include = _include_database_health_details()
    return HealthResponse(
        status="ok" if h.ok else "degraded",
        database="up" if h.ok else "down",
        database_dsn_preview=h.dsn_preview if include else None,
        database_error_type=h.error_type if include and not h.ok else None,
        database_error=h.error_message if include and not h.ok else None,
    )
