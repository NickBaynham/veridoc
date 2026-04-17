"""FastAPI entrypoint: synchronous API surface, SSE, auth boundaries."""

from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, RedirectResponse
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from sqlalchemy.exc import SQLAlchemyError

from app.api.routes import (
    collections,
    documents,
    events,
    health,
    info,
    knowledge_models,
    search,
    session_auth,
    users_api,
)
from app.core.config import get_settings
from app.rate_limit import limiter, sync_limiter_from_settings
from app.services.dev_auth_bootstrap import bootstrap_dev_auth_user
from app.services.event_service import close_event_hub
from app.services.queue_backend import close_job_queue
from app.services.storage_service import reset_object_storage

logger = logging.getLogger(__name__)


def _register_exception_handlers(application: FastAPI) -> None:
    @application.exception_handler(SQLAlchemyError)
    async def sqlalchemy_error_handler(
        _request: Request,
        exc: SQLAlchemyError,
    ) -> JSONResponse:
        logger.error("SQLAlchemy error", exc_info=exc)
        if get_settings().hides_health_openapi_details():
            return JSONResponse(
                status_code=500,
                content={"detail": "Internal server error"},
            )
        orig = getattr(exc, "orig", None)
        message = str(orig) if orig is not None else str(exc)
        if len(message) > 2000:
            message = message[:2000] + "…"
        return JSONResponse(
            status_code=500,
            content={
                "detail": "database error",
                "error_type": type(exc).__name__,
                "message": message,
            },
        )


@asynccontextmanager
async def lifespan(app: FastAPI):
    _ = app
    settings = get_settings()
    await asyncio.to_thread(bootstrap_dev_auth_user, settings)
    if settings.strict_production_lifespan_warnings():
        if settings.allow_default_collection_fallback:
            logger.warning(
                "Production: VERIFIEDSIGNAL_ALLOW_DEFAULT_COLLECTION_FALLBACK is enabled; "
                "JWTs without a Postgres user may access the default collection — disable for "
                "strict multi-tenant isolation."
            )
        if settings.use_fake_queue or settings.use_fake_storage or settings.use_fake_opensearch:
            logger.warning(
                "Production: USE_FAKE_QUEUE / USE_FAKE_STORAGE / USE_FAKE_OPENSEARCH enabled — "
                "not suitable for real workloads."
            )
        if settings.use_fake_event_hub:
            logger.warning(
                "Production: USE_FAKE_EVENT_HUB enabled — SSE will not fan out across API replicas."
            )
    yield
    await close_job_queue()
    await close_event_hub()
    reset_object_storage()


def create_app() -> FastAPI:
    settings = get_settings()
    sync_limiter_from_settings(settings)
    docs_enabled = (not settings.hides_health_openapi_details()) or settings.expose_openapi_docs
    application = FastAPI(
        title=settings.app_name,
        description=(
            "VerifiedSignal HTTP API: session auth under **`/auth`** (Supabase-backed, including "
            "**`/auth/sync-identity`**); versioned resources under **`/api/v1`** "
            "(health, documents incl. signed original download, collections, users, search, "
            "SSE via Redis pub/sub). "
            "Bearer JWTs can auto-provision Postgres tenancy (users, org, inbox)."
        ),
        version="0.1.0",
        lifespan=lifespan,
        docs_url="/" if docs_enabled else None,
        redoc_url="/redoc" if docs_enabled else None,
        openapi_url="/openapi.json" if docs_enabled else None,
    )
    application.state.limiter = limiter
    application.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
    _register_exception_handlers(application)

    if docs_enabled:

        @application.get("/docs", include_in_schema=False)
        async def redirect_legacy_docs() -> RedirectResponse:
            """Old default path; interactive docs live at `/`."""
            return RedirectResponse(url="/", status_code=307)

    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["Content-Disposition"],
    )
    application.include_router(session_auth.router)
    v1 = settings.api_v1_prefix.rstrip("/") or "/api/v1"
    application.include_router(health.router, prefix=v1)
    application.include_router(info.router, prefix=v1)
    application.include_router(documents.router, prefix=v1)
    application.include_router(collections.router, prefix=v1)
    application.include_router(knowledge_models.router, prefix=v1)
    application.include_router(users_api.router, prefix=v1)
    application.include_router(search.router, prefix=v1)
    application.include_router(events.router, prefix=v1)
    return application


app = create_app()
