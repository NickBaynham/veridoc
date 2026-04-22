"""Application configuration (environment-driven)."""

from __future__ import annotations

import os
from functools import lru_cache
from urllib.parse import urlparse, urlunparse
from uuid import UUID

from pydantic import Field, field_validator, model_validator
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

    # When ENVIRONMENT is production|prod|staging, interactive OpenAPI/Swagger is off unless true.
    expose_openapi_docs: bool = Field(default=False, validation_alias="EXPOSE_OPENAPI_DOCS")

    # Per-IP limits (slowapi; in-memory — one counter set per API process).
    rate_limit_enabled: bool = Field(default=True, validation_alias="RATE_LIMIT_ENABLED")
    rate_limit_auth_signup: str = Field(
        default="5/minute",
        validation_alias="RATE_LIMIT_AUTH_SIGNUP",
    )
    rate_limit_auth_login: str = Field(
        default="10/minute",
        validation_alias="RATE_LIMIT_AUTH_LOGIN",
    )
    rate_limit_auth_refresh: str = Field(
        default="60/minute",
        validation_alias="RATE_LIMIT_AUTH_REFRESH",
    )
    rate_limit_auth_reset: str = Field(
        default="3/minute",
        validation_alias="RATE_LIMIT_AUTH_RESET",
    )
    rate_limit_auth_sync_identity: str = Field(
        default="30/minute",
        validation_alias="RATE_LIMIT_AUTH_SYNC_IDENTITY",
    )
    rate_limit_auth_logout: str = Field(
        default="30/minute",
        validation_alias="RATE_LIMIT_AUTH_LOGOUT",
    )
    rate_limit_documents_intake: str = Field(
        default="60/minute",
        validation_alias="RATE_LIMIT_DOCUMENTS_INTAKE",
    )

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

    # When true, SSE uses in-process fan-out instead of Redis pub/sub (tests; single-process dev).
    use_fake_event_hub: bool = Field(
        default=False,
        validation_alias="USE_FAKE_EVENT_HUB",
        description=(
            "In-memory EventHub for SSE. Set true in tests. When false, GET /events/stream uses "
            "Redis pub/sub at REDIS_URL (same broker as ARQ) so multiple API replicas share events."
        ),
    )

    # Redis channel for SSE JSON lines (publish/subscribe).
    event_pubsub_channel: str = Field(
        default="verifiedsignal:sse",
        validation_alias="EVENT_PUBSUB_CHANNEL",
    )

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
    # Default false (multi-tenant safe). Set true in local .env for seeded default inbox fallback.
    allow_default_collection_fallback: bool = Field(
        default=False,
        validation_alias="VERIFIEDSIGNAL_ALLOW_DEFAULT_COLLECTION_FALLBACK",
        description=(
            "If no Postgres user row matches the JWT and auto-provision is off, fall back to "
            "VERIFIEDSIGNAL_DEFAULT_COLLECTION_ID when set. Enable for local dev; keep false in "
            "production unless you accept shared default collection access."
        ),
    )

    max_upload_bytes: int = Field(default=52_428_800, validation_alias="MAX_UPLOAD_BYTES")  # 50 MiB

    # Tesseract OCR for images (image/*) and optional scanned-PDF fallback when pypdf finds no text.
    ocr_enabled: bool = Field(default=True, validation_alias="OCR_ENABLED")
    ocr_pdf_fallback: bool = Field(
        default=True,
        validation_alias="OCR_PDF_FALLBACK",
        description=(
            "When true and OCR_ENABLED, render PDF pages (poppler) and OCR if native text is empty."
        ),
    )
    ocr_max_pdf_pages: int = Field(
        default=25,
        ge=1,
        le=200,
        validation_alias="OCR_MAX_PDF_PAGES",
    )
    ocr_langs: str = Field(
        default="eng",
        validation_alias="OCR_LANGS",
        description="Tesseract language code(s), e.g. eng or eng+deu (install matching tessdata).",
    )
    tesseract_cmd: str | None = Field(
        default=None,
        validation_alias="TESSERACT_CMD",
        description="Optional path to tesseract binary; uses PATH when unset.",
    )

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

    download_presigned_ttl_seconds: int = Field(
        default=3600,
        ge=60,
        le=604_800,
        validation_alias="DOWNLOAD_PRESIGNED_TTL_SECONDS",
        description=(
            "TTL (seconds) for presigned GET URLs on GET /documents/{id}/file when redirect=true."
        ),
    )

    opensearch_url: str = Field(
        default="http://localhost:9200",
        validation_alias="OPENSEARCH_URL",
    )
    opensearch_index_name: str = Field(
        default="verifiedsignal_documents",
        validation_alias="OPENSEARCH_INDEX_NAME",
    )
    # When true, index + search use in-memory dict (tests / no OpenSearch container).
    use_fake_opensearch: bool = Field(
        default=False,
        validation_alias="USE_FAKE_OPENSEARCH",
    )

    # After scaffold pipeline, enqueue `score_document` (stub writes placeholder `document_scores`).
    enqueue_score_after_pipeline: bool = Field(
        default=False,
        validation_alias="ENQUEUE_SCORE_AFTER_PIPELINE",
    )

    require_auth_for_search: bool = Field(
        default=True,
        validation_alias="VERIFIEDSIGNAL_REQUIRE_AUTH_SEARCH",
    )
    require_auth_for_sse: bool = Field(
        default=True,
        validation_alias="VERIFIEDSIGNAL_REQUIRE_AUTH_SSE",
    )

    # Async `score_document` job: `stub` (placeholder row) or `http` (POST to SCORE_HTTP_URL).
    score_async_backend: str = Field(default="stub", validation_alias="SCORE_ASYNC_BACKEND")
    score_http_url: str = Field(default="", validation_alias="SCORE_HTTP_URL")
    score_http_bearer_token: str = Field(default="", validation_alias="SCORE_HTTP_BEARER_TOKEN")
    score_http_timeout_s: float = Field(default=120.0, validation_alias="SCORE_HTTP_TIMEOUT_S")
    score_http_max_body_chars: int = Field(
        default=12_000,
        ge=256,
        le=500_000,
        validation_alias="SCORE_HTTP_MAX_BODY_CHARS",
    )
    score_http_scorer_version: str = Field(
        default="1.0.0",
        validation_alias="SCORE_HTTP_SCORER_VERSION",
    )
    # When true, successful HTTP scorer row becomes canonical (heuristic + others demoted).
    score_api_promote_canonical: bool = Field(
        default=False,
        validation_alias="SCORE_API_PROMOTE_CANONICAL",
    )

    # Log-odds fusion row `verifiedsignal_bayes_v1` (see docs/scoring-bayesian-fusion.md).
    bayes_fusion_enabled: bool = Field(default=False, validation_alias="BAYES_FUSION_ENABLED")
    bayes_fusion_prior_ai_prob: float = Field(
        default=0.15,
        ge=0.01,
        le=0.99,
        validation_alias="BAYES_FUSION_PRIOR_AI_PROB",
    )
    bayes_fusion_promote_canonical: bool = Field(
        default=False,
        validation_alias="BAYES_FUSION_PROMOTE_CANONICAL",
    )

    # Cap JSON size for documents.analysis_metadata (worker-written sections).
    analysis_metadata_max_json_bytes: int = Field(
        default=96_384,
        ge=1024,
        le=2_000_000,
        validation_alias="ANALYSIS_METADATA_MAX_JSON_BYTES",
    )

    # When false, OpenSearch documents omit dense vectors (older indexes without knn mapping).
    opensearch_index_embeddings: bool = Field(
        default=True,
        validation_alias="OPENSEARCH_INDEX_EMBEDDINGS",
    )

    @field_validator("score_async_backend", mode="before")
    @classmethod
    def normalize_score_async_backend(cls, v: object) -> str:
        if v is None or (isinstance(v, str) and not v.strip()):
            return "stub"
        s = str(v).strip().lower()
        if s not in ("stub", "http"):
            raise ValueError("SCORE_ASYNC_BACKEND must be 'stub' or 'http'")
        return s

    # Must match worker `WorkerSettings.queue_name` / `VERIFIEDSIGNAL_ARQ_QUEUE`.
    arq_queue_name: str = Field(
        default="verifiedsignal:jobs",
        validation_alias="VERIFIEDSIGNAL_ARQ_QUEUE",
    )

    # Local dev: create a Supabase Auth user on API startup (development only; requires Supabase).
    dev_bootstrap_auth_user: bool = Field(
        default=False,
        validation_alias="VERIFIEDSIGNAL_DEV_BOOTSTRAP_AUTH_USER",
    )
    dev_bootstrap_auth_email: str = Field(
        default="dev@example.com",
        validation_alias="VERIFIEDSIGNAL_DEV_BOOTSTRAP_AUTH_EMAIL",
    )
    dev_bootstrap_auth_password: str = Field(
        default="devpassword123",
        validation_alias="VERIFIEDSIGNAL_DEV_BOOTSTRAP_AUTH_PASSWORD",
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

    @model_validator(mode="after")
    def jwt_algorithm_hmac_when_no_jwks(self) -> Settings:
        """
        When verifying with SUPABASE_JWT_SECRET, only HMAC algs are used (see jwt_verify).
        If SUPABASE_JWKS_URL is set, RS256 is enforced in code and this field is ignored for verify.
        """
        if self.supabase_jwks_url.strip():
            return self
        alg = (self.jwt_algorithm or "HS256").strip().upper()
        if alg not in ("HS256", "HS384", "HS512"):
            raise ValueError(
                "JWT_ALGORITHM must be HS256, HS384, or HS512 when SUPABASE_JWKS_URL is unset"
            )
        if alg != self.jwt_algorithm:
            return self.model_copy(update={"jwt_algorithm": alg})
        return self

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

    def hides_health_openapi_details(self) -> bool:
        """Hide /health internals and API docs (treat like production)."""
        return self.environment.strip().lower() in ("production", "prod", "staging")

    def strict_production_lifespan_warnings(self) -> bool:
        """Startup warnings for fake infra / risky tenancy (production|prod only)."""
        return self.environment.strip().lower() in ("production", "prod")


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


def running_inside_container() -> bool:
    """True when this process runs under Docker's Linux runtime (not macOS host binaries)."""
    return os.path.exists("/.dockerenv")


def effective_supabase_url_for_server(settings: Settings | None = None) -> str:
    """
    ``SUPABASE_URL`` for outbound HTTP (GoTrue, JWKS) from this API process.

    In Compose, ``http://127.0.0.1:54321`` points at the API container itself, not Supabase on the
    host. When ``/.dockerenv`` is present, loopback hosts are rewritten to ``host.docker.internal``
    so one root ``.env`` can use ``127.0.0.1`` for both ``pdm run api`` and ``docker compose``.
    Hosted ``https://….supabase.co`` URLs are left unchanged.
    """
    s = settings or get_settings()
    raw = (s.supabase_url or "").strip()
    if not raw or not running_inside_container():
        return raw
    try:
        p = urlparse(raw)
    except Exception:
        return raw
    host = (p.hostname or "").lower()
    if host not in ("127.0.0.1", "localhost", "::1"):
        return raw
    port_suffix = f":{p.port}" if p.port is not None else ""
    if p.username is not None:
        auth = p.username
        if p.password is not None:
            auth = f"{auth}:{p.password}"
        new_netloc = f"{auth}@host.docker.internal{port_suffix}"
    else:
        new_netloc = f"host.docker.internal{port_suffix}"
    return urlunparse(
        (p.scheme or "http", new_netloc, p.path, p.params, p.query, p.fragment)
    )


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
        # Defensive: never fail callers; malformed or exotic URLs should not break /health.
        return "<could not parse DATABASE_URL>"


def reset_settings_cache() -> None:
    get_settings.cache_clear()
