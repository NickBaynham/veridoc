"""Persistence for pipeline_runs / pipeline_events."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Document, PipelineEvent, PipelineRun
from app.pipeline.constants import PIPELINE_NAME, PIPELINE_VERSION


def create_pipeline_run(session: Session, document_id: uuid.UUID, job_id: str) -> PipelineRun:
    now = datetime.now(UTC)
    run = PipelineRun(
        document_id=document_id,
        pipeline_name=PIPELINE_NAME,
        pipeline_version=PIPELINE_VERSION,
        definition_schema_version=1,
        status="running",
        stage="queued",
        started_at=now,
        run_metadata={"job_id": job_id},
    )
    session.add(run)
    session.flush()
    return run


def append_event(
    session: Session,
    run_id: uuid.UUID,
    step_index: int,
    event_type: str,
    stage: str | None,
    payload: dict,
) -> None:
    ev = PipelineEvent(
        pipeline_run_id=run_id,
        step_index=step_index,
        event_type=event_type,
        stage=stage,
        payload=payload,
        event_schema_version=1,
    )
    session.add(ev)


def set_document_status(session: Session, document_id: uuid.UUID, status: str) -> None:
    doc = session.get(Document, document_id)
    if doc is None:
        raise ValueError(f"document not found: {document_id}")
    doc.status = status


def complete_run(session: Session, run: PipelineRun) -> None:
    run.status = "succeeded"
    run.completed_at = datetime.now(UTC)


def fail_run(session: Session, run: PipelineRun, message: str) -> None:
    run.status = "failed"
    run.error_detail = {"message": message[:4000]}
    run.completed_at = datetime.now(UTC)


def get_latest_run_for_document(session: Session, document_id: uuid.UUID) -> PipelineRun | None:
    return session.scalar(
        select(PipelineRun)
        .where(PipelineRun.document_id == document_id)
        .order_by(PipelineRun.started_at.desc().nullslast(), PipelineRun.created_at.desc())
        .limit(1)
    )


def list_events_for_run(session: Session, run_id: uuid.UUID) -> list[PipelineEvent]:
    rows = session.scalars(
        select(PipelineEvent)
        .where(PipelineEvent.pipeline_run_id == run_id)
        .order_by(PipelineEvent.step_index.asc(), PipelineEvent.created_at.asc())
    ).all()
    return list(rows)


def list_recent_events_for_collection(
    session: Session,
    collection_id: uuid.UUID,
    *,
    limit: int = 100,
) -> list[tuple[PipelineEvent, PipelineRun, Document]]:
    """Newest pipeline events for documents in this collection (cross-run feed)."""
    stmt = (
        select(PipelineEvent, PipelineRun, Document)
        .join(PipelineRun, PipelineRun.id == PipelineEvent.pipeline_run_id)
        .join(Document, Document.id == PipelineRun.document_id)
        .where(Document.collection_id == collection_id)
        .order_by(PipelineEvent.created_at.desc())
        .limit(limit)
    )
    return list(session.execute(stmt).all())
