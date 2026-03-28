"""Health / info response models."""

from __future__ import annotations

from pydantic import BaseModel


class HealthResponse(BaseModel):
    status: str
    database: str
    # Populated outside production to troubleshoot connection failures (password never shown).
    database_dsn_preview: str | None = None
    database_error_type: str | None = None
    database_error: str | None = None


class InfoResponse(BaseModel):
    service: str
    environment: str
    api_prefix: str
    notes: str
