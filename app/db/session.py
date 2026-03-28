"""SQLAlchemy engine and session factory (Postgres system-of-record)."""

from __future__ import annotations

from collections.abc import Generator
from dataclasses import dataclass

import psycopg
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import effective_database_url, preview_database_url

_engine: Engine | None = None
_SessionLocal: sessionmaker[Session] | None = None


@dataclass(frozen=True, slots=True)
class DatabaseHealthResult:
    ok: bool
    dsn_preview: str
    error_type: str | None = None
    error_message: str | None = None


def get_engine() -> Engine:
    global _engine, _SessionLocal
    if _engine is None:

        def _connect() -> psycopg.Connection:
            return psycopg.connect(effective_database_url())

        _engine = create_engine(
            "postgresql+psycopg://",
            creator=_connect,
            pool_pre_ping=True,
        )
        _SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=_engine)
    return _engine


def get_session_factory() -> sessionmaker[Session]:
    get_engine()
    assert _SessionLocal is not None
    return _SessionLocal


def get_db() -> Generator[Session, None, None]:
    SessionLocal = get_session_factory()
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def database_health_check() -> DatabaseHealthResult:
    """Run SELECT 1; include redacted DSN and error details for non-production /health."""
    dsn = effective_database_url()
    preview = preview_database_url(dsn)
    try:
        with get_engine().connect() as conn:
            conn.execute(text("SELECT 1"))
        return DatabaseHealthResult(ok=True, dsn_preview=preview)
    except Exception as e:
        msg = str(e)
        if len(msg) > 800:
            msg = msg[:800] + "…"
        return DatabaseHealthResult(
            ok=False,
            dsn_preview=preview,
            error_type=type(e).__name__,
            error_message=msg,
        )


def check_database_connection() -> bool:
    """Return True if SELECT 1 succeeds."""
    return database_health_check().ok


def reset_engine() -> None:
    """Test hook: dispose engine and clear factories."""
    global _engine, _SessionLocal
    if _engine is not None:
        _engine.dispose()
    _engine = None
    _SessionLocal = None
