"""Liveness and dependency health."""

from __future__ import annotations

from fastapi import APIRouter

from app.core.config import get_settings
from app.db.session import database_health_check
from app.schemas.health import HealthResponse
from app.services.dependency_health import (
    check_object_storage_component,
    check_opensearch_component,
    check_redis_component,
    overall_status_from_components,
)

router = APIRouter(tags=["health"])


def _include_dependency_health_details() -> bool:
    """Omit DSN preview and errors in production responses."""
    return get_settings().environment.lower() not in ("production", "prod")


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    settings = get_settings()
    h = database_health_check()
    redis_st, redis_et, redis_em = check_redis_component(settings)
    storage_st, storage_et, storage_em = check_object_storage_component(settings)
    os_st, os_et, os_em = check_opensearch_component(settings)

    include = _include_dependency_health_details()
    overall = overall_status_from_components(
        database_ok=h.ok,
        redis_status=redis_st,
        object_storage_status=storage_st,
        opensearch_status=os_st,
    )

    return HealthResponse(
        status=overall,
        database="up" if h.ok else "down",
        redis=redis_st,
        object_storage=storage_st,
        opensearch=os_st,
        database_dsn_preview=h.dsn_preview if include else None,
        database_error_type=h.error_type if include and not h.ok else None,
        database_error=h.error_message if include and not h.ok else None,
        redis_error_type=redis_et if include and redis_st == "down" else None,
        redis_error=redis_em if include and redis_st == "down" else None,
        object_storage_error_type=storage_et if include and storage_st == "down" else None,
        object_storage_error=storage_em if include and storage_st == "down" else None,
        opensearch_error_type=os_et if include and os_st == "down" else None,
        opensearch_error=os_em if include and os_st == "down" else None,
    )
