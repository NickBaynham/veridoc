"""
Background scoring entrypoint (stub): records a placeholder `document_scores` row.

Replace with real model inference and canonical promotion when scoring ships.
"""

from __future__ import annotations

import logging
import uuid

from sqlalchemy.orm import Session

from app.db.models import Document, DocumentScore
from app.db.session import get_session_factory

log = logging.getLogger("verifiedsignal.score_document")


def run_score_document_sync(document_id: str) -> None:
    SessionLocal = get_session_factory()
    session: Session = SessionLocal()
    try:
        _run_score_document(session, uuid.UUID(document_id))
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def _run_score_document(session: Session, document_id: uuid.UUID) -> None:
    doc = session.get(Document, document_id)
    if doc is None:
        log.warning("score_document_missing document_id=%s", document_id)
        return
    row = DocumentScore(
        document_id=doc.id,
        pipeline_run_id=None,
        scorer_name="verifiedsignal_stub",
        scorer_version="0.1.0",
        score_schema_version=1,
        is_canonical=False,
        score_payload={"status": "stub", "note": "Real scoring not yet implemented"},
    )
    session.add(row)
    log.info("score_document_stub_insert document_id=%s", document_id)
