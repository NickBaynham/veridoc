"""Application configuration (environment-driven)."""

from __future__ import annotations

import os
from functools import lru_cache
from urllib.parse import urlparse, urlunparse
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

    # Map Supabase JWT to Postgres: create users + personal org + inbox on first Bearer request.
    auto_provision_identity: bool = Field(
        default=True,
        validation_alias="VERIFIEDSIGNAL_AUTO_PROVISION_IDENTITY",
    )
    # When false, JWTs without a users row do not get the seeded default inbox (prod multi-tenant).
    allow_default_collection_fallback: bool = Field(
        default=True,
        validation_alias="VERIFIEDSIGNAL_ALLOW_DEFAULT_COLLECTION_FALLBACK",
        description=(
            "If no Postgres user row matches the JWT and auto-provision is off, fall back to "
            "VERIFIEDSIGNAL_DEFAULT_COLLECTION_ID when set (local dev). Disable in production."
        ),
    )

    max_upload_bytes: int = Field(default=52_428_800, validation_alias="MAX_UPLOAD_BYTES")  # 50 MiB

    # URL-based document intake (worker fetches remote bytes → same S3 + pipeline as multipart).
    url_ingest_enabled: bool = Field(default=True, validation_alias="URL_INGEST_ENABLED")
    url_fetch_max_bytes: int = Field(
        default=52_428_800,
        validation_alias="URL_FETCH_MAX_BYTES",
        description="Max response body size when fetching a URL (defaults to MAX_UPLOAD_BYTES).",
    )
    url_fetch_timeout_s: float = Field(default=60.0, validation_alias="URL_FETCH_TIMEOUT_S")
    url_fetch_max_redirects: int = Field(default=5, validation_alias="URL_FETCH_MAX_REDIRECTS")
    url_fetch_follow_redirects: bool = Field(
        default=True,
        validation_alias="URL_FETCH_FOLLOW_REDIRECTS",
    )
    allow_http_url_ingest: bool = Field(
        default=False,
        validation_alias="ALLOW_HTTP_URL_INGEST",
        description="Allow http:// URLs (dev only; use https in production).",
    )
    url_fetch_block_private_networks: bool = Field(
        default=True,
        validation_alias="URL_FETCH_BLOCK_PRIVATE_NETWORKS",
        description="Reject URLs whose hostnames resolve to private/link-local/loopback IPs.",
    )

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

    # --- Supabase Auth (leave empty to disable auth HTTP routes / use test overrides) ---
    supabase_url: str = Field(default="", validation_alias="SUPABASE_URL")
    supabase_anon_key: str = Field(default="", validation_alias="SUPABASE_ANON_KEY")
    supabase_service_role_key: str = Field(
        default="",
        validation_alias="SUPABASE_SERVICE_ROLE_KEY",
    )
    supabase_jwt_secret: str = Field(default="", validation_alias="SUPABASE_JWT_SECRET")
    supabase_jwks_url: str = Field(default="", validation_alias="SUPABASE_JWKS_URL")
    jwt_algorithm: str = Field(default="HS256", validation_alias="JWT_ALGORITHM")
    jwt_audience: str = Field(default="authenticated", validation_alias="JWT_AUDIENCE")

    # Comma-separated browser origins for credentialed requests (refresh cookie).
    cors_origins: str = Field(
        default="http://localhost:5173,http://127.0.0.1:5173,http://localhost:3000,http://127.0.0.1:3000",
        validation_alias="CORS_ORIGINS",
    )
    # Set true behind HTTPS in production so refresh cookies are not sent over plain HTTP.
    auth_cookie_secure: bool = Field(default=False, validation_alias="AUTH_COOKIE_SECURE")

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def supabase_auth_configured(self) -> bool:
        return bool(
            self.supabase_url.strip()
            and self.supabase_service_role_key.strip()
            and self.supabase_anon_key.strip()
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


def preview_database_url(url: str) -> str:
    """Redact password from a Postgres URL for logs / non-production health responses."""
    try:
        parsed = urlparse(url)
        netloc = parsed.netloc
        if "@" in netloc:
            userinfo, hostport = netloc.rsplit("@", 1)
            user = userinfo.split(":", 1)[0] if ":" in userinfo else userinfo
            netloc = f"{user}:***@{hostport}"
        path = parsed.path if parsed.path else "/"
        return urlunparse((parsed.scheme, netloc, path, parsed.params, "", ""))
    except Exception:
        return "<could not parse DATABASE_URL>"


def reset_settings_cache() -> None:
    get_settings.cache_clear()
