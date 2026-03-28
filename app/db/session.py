"""SQLAlchemy engine and session factory (Postgres system-of-record)."""

from __future__ import annotations

from collections.abc import Generator

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine, make_url
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import effective_database_url

_engine: Engine | None = None
_SessionLocal: sessionmaker[Session] | None = None


def _sqlalchemy_url_for_psycopg3(url: str) -> str:
    """Use psycopg3 for generic postgresql:// URLs (SQLAlchemy defaults to psycopg2)."""
    parsed = make_url(url)
    if parsed.drivername in ("postgresql", "postgres"):
        return str(parsed.set(drivername="postgresql+psycopg"))
    return url


def get_engine() -> Engine:
    global _engine, _SessionLocal
    if _engine is None:
        url = _sqlalchemy_url_for_psycopg3(effective_database_url())
        _engine = create_engine(url, pool_pre_ping=True)
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


def check_database_connection() -> bool:
    """Return True if SELECT 1 succeeds."""
    try:
        with get_engine().connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


def reset_engine() -> None:
    """Test hook: dispose engine and clear factories."""
    global _engine, _SessionLocal
    if _engine is not None:
        _engine.dispose()
    _engine = None
    _SessionLocal = None
