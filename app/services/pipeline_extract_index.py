"""Extract text from storage bytes, persist artifact, index into OpenSearch (worker pipeline)."""

from __future__ import annotations

import logging
import uuid

from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.db.models import Document
from app.repositories import pipeline_repository as pipe_repo
from app.services.document_content_extract import extract_document_text
from app.services.document_text_extract import truncate_for_body
from app.services.opensearch_document_index import index_document_sync
from app.services.storage_service import (
    ObjectStorage,
    build_extract_artifact_key,
    get_object_storage,
)

log = logging.getLogger("verifiedsignal.pipeline.extract_index")


def _extract_failure_reason(note: str | None, kind: str) -> bool:
    if not note:
        return False
    if note == "pdf_encrypted":
        return True
    if kind == "pdf" and note.startswith("pdf_error:"):
        return True
    if kind == "docx" and note.startswith("docx_error:"):
        return True
    return False


def extract_body_text_stage(
    session: Session,
    *,
    document_id: uuid.UUID,
    run_id: uuid.UUID,
    step_index: int,
    job_id: str,
    storage: ObjectStorage | None = None,
    settings: Settings | None = None,
) -> None:
    _ = settings or get_settings()
    storage = storage or get_object_storage()
    doc = session.get(Document, document_id)
    if doc is None:
        return
    doc.extract_artifact_key = None
    if not doc.storage_key:
        pipe_repo.append_event(
            session,
            run_id,
            step_index,
            "extract_skipped",
            "extract",
            {"reason": "no_storage_key", "job_id": job_id},
        )
        return
    try:
        raw = storage.get_bytes(doc.storage_key)
    except KeyError:
        pipe_repo.append_event(
            session,
            run_id,
            step_index,
            "extract_failed",
            "extract",
            {"reason": "object_missing", "job_id": job_id},
        )
        return
    except Exception as e:
        log.warning("extract_read_failed document_id=%s err=%s", document_id, e)
        pipe_repo.append_event(
            session,
            run_id,
            step_index,
            "extract_failed",
            "extract",
            {"reason": type(e).__name__, "job_id": job_id},
        )
        return

    text, note, kind = extract_document_text(raw, doc.content_type, doc.original_filename)
    if _extract_failure_reason(note, kind):
        doc.body_text = None
        pipe_repo.append_event(
            session,
            run_id,
            step_index,
            "extract_failed",
            "extract",
            {"reason": note, "kind": kind, "job_id": job_id, "bytes": len(raw)},
        )
        return

    body = truncate_for_body(text) if text else ""
    doc.body_text = body if body else None

    if text:
        artifact_key = build_extract_artifact_key(document_id)
        try:
            storage.upload_bytes(artifact_key, text.encode("utf-8"), "text/plain; charset=utf-8")
            doc.extract_artifact_key = artifact_key
        except Exception as e:
            log.warning("extract_artifact_upload_failed document_id=%s err=%s", document_id, e)
            pipe_repo.append_event(
                session,
                run_id,
                step_index,
                "extract_artifact_failed",
                "extract",
                {"reason": type(e).__name__, "job_id": job_id},
            )

    pipe_repo.append_event(
        session,
        run_id,
        step_index,
        "extract_complete",
        "extract",
        {
            "job_id": job_id,
            "bytes": len(raw),
            "chars": len(text or ""),
            "body_chars": len(doc.body_text or ""),
            "note": note,
            "kind": kind,
            "artifact_key": doc.extract_artifact_key,
        },
    )


def index_opensearch_stage(
    session: Session,
    *,
    document_id: uuid.UUID,
    run_id: uuid.UUID,
    step_index: int,
    job_id: str,
    settings: Settings | None = None,
) -> None:
    settings = settings or get_settings()
    doc = session.get(Document, document_id)
    if doc is None:
        return
    try:
        index_document_sync(
            document_id=doc.id,
            collection_id=doc.collection_id,
            title=doc.title,
            body_text=doc.body_text,
            status=doc.status,
            settings=settings,
        )
    except Exception as e:
        log.warning("index_failed document_id=%s err=%s", document_id, e)
        pipe_repo.append_event(
            session,
            run_id,
            step_index,
            "index_failed",
            "index",
            {"reason": str(e)[:500], "job_id": job_id},
        )
        return

    pipe_repo.append_event(
        session,
        run_id,
        step_index,
        "index_complete",
        "index",
        {"job_id": job_id},
    )
