"""Application configuration (environment-driven)."""

from __future__ import annotations

import os
from functools import lru_cache
from uuid import UUID

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "verifiedsignal-api"
    api_v1_prefix: str = "/api/v1"
    environment: str = "development"

    database_url: str = Field(
        default="postgresql://verifiedsignal:verifiedsignal@localhost:5432/verifiedsignal",
        validation_alias="DATABASE_URL",
    )

    @field_validator("database_url", mode="before")
    @classmethod
    def database_url_from_process_environ(cls, v: object) -> object:
        """Prefer live os.environ so CI / make ci-local match psycopg (tests use getenv)."""
        env_url = os.environ.get("DATABASE_URL")
        if env_url is not None and env_url.strip() != "":
            return env_url
        return v

    redis_url: str = Field(
        default="redis://localhost:6379/0",
        validation_alias="REDIS_URL",
    )

    # When true, skip Redis/ARQ and use in-process fake queue (tests + local without Redis).
    use_fake_queue: bool = Field(default=False, validation_alias="USE_FAKE_QUEUE")

    # When true, store objects in memory instead of MinIO/S3.
    use_fake_storage: bool = Field(default=False, validation_alias="USE_FAKE_STORAGE")

    # Intake: default collection when multipart form omits collection_id (seeded by migration 002).
    default_collection_id: UUID | None = Field(
        default=UUID("00000000-0000-4000-8000-000000000002"),
        validation_alias="VERIFIEDSIGNAL_DEFAULT_COLLECTION_ID",
    )

    max_upload_bytes: int = Field(default=52_428_800, validation_alias="MAX_UPLOAD_BYTES")  # 50 MiB

    s3_endpoint_url: str | None = Field(default=None, validation_alias="S3_ENDPOINT_URL")
    s3_access_key_id: str = Field(default="minioadmin", validation_alias="AWS_ACCESS_KEY_ID")
    s3_secret_access_key: str = Field(
        default="minioadmin",
        validation_alias="AWS_SECRET_ACCESS_KEY",
    )
    s3_region: str = Field(default="us-east-1", validation_alias="AWS_DEFAULT_REGION")
    s3_bucket: str = Field(default="verifiedsignal", validation_alias="S3_BUCKET")
    s3_use_path_style: bool = Field(default=True, validation_alias="S3_USE_PATH_STYLE")

    opensearch_url: str = Field(
        default="http://localhost:9200",
        validation_alias="OPENSEARCH_URL",
    )

    # Must match worker `WorkerSettings.queue_name` / `VERIFIEDSIGNAL_ARQ_QUEUE`.
    arq_queue_name: str = Field(
        default="verifiedsignal:jobs",
        validation_alias="VERIFIEDSIGNAL_ARQ_QUEUE",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()


def effective_database_url() -> str:
    """
    URL used for DB connections. Prefer live os.environ so pytest / make ci-local match
    integration helpers that use getenv (Settings + field_validator alone can still diverge
    from process env with pydantic-settings merge order).
    """
    direct = os.environ.get("DATABASE_URL")
    if direct is not None and direct.strip() != "":
        return direct.strip()
    return get_settings().database_url


def reset_settings_cache() -> None:
    get_settings.cache_clear()
