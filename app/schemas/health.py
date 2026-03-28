"""Health / info response models."""

from __future__ import annotations

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    status: str
    database: str
    redis: str = Field(description="Redis (real) or stub when USE_FAKE_QUEUE=true.")
    object_storage: str = Field(description="S3/MinIO (real) or stub when USE_FAKE_STORAGE=true.")
    opensearch: str = Field(description="OpenSearch/Elasticsearch-compatible HTTP GET / check.")
    # Populated outside production to troubleshoot connection failures (password never shown).
    database_dsn_preview: str | None = None
    database_error_type: str | None = None
    database_error: str | None = None
    redis_error_type: str | None = None
    redis_error: str | None = None
    object_storage_error_type: str | None = None
    object_storage_error: str | None = None
    opensearch_error_type: str | None = None
    opensearch_error: str | None = None


class InfoResponse(BaseModel):
    service: str
    environment: str
    api_prefix: str
    notes: str
