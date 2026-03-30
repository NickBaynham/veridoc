"""
Execute the scaffold document pipeline with Postgres persistence.

Called from the ARQ worker inside a thread (see `worker.pipeline.run_pipeline_job`).
"""

from __future__ import annotations

import logging
import uuid

from sqlalchemy.orm import Session

from app.db.models import Document
from app.pipeline.constants import DOCUMENT_SCAFFOLD_STAGES
from app.repositories import pipeline_repository as pipe_repo
from app.services.pipeline_extract_index import extract_body_text_stage, index_opensearch_stage
from app.services.pipeline_stage_work import (
    enrich_stage,
    ingest_verify_storage_stage,
    score_enqueue_stage,
)

log = logging.getLogger("verifiedsignal.pipeline.run")


def execute_scaffold_pipeline(session: Session, document_id: uuid.UUID, job_id: str) -> None:
    """
    Create `pipeline_runs` + `pipeline_events`, advance `documents.status`:
    queued → processing → completed (or failed on error).
    """
    if session.get(Document, document_id) is None:
        raise ValueError(f"document not found: {document_id}")

    run = pipe_repo.create_pipeline_run(session, document_id, job_id)
    pipe_repo.set_document_status(session, document_id, "processing")
    pipe_repo.append_event(
        session,
        run.id,
        0,
        "pipeline_started",
        None,
        {"job_id": job_id, "document_id": str(document_id)},
    )
    log.info("pipeline_started document_id=%s job_id=%s", document_id, job_id)

    try:
        step_seq = 1
        for stage in DOCUMENT_SCAFFOLD_STAGES:
            run.stage = stage
            pipe_repo.append_event(
                session,
                run.id,
                step_seq,
                "pipeline_stage",
                stage,
                {"job_id": job_id, "stage": stage, "document_id": str(document_id)},
            )
            log.info("pipeline_stage document_id=%s stage=%s job_id=%s", document_id, stage, job_id)
            step_seq += 1

            if stage == "ingest":
                ingest_verify_storage_stage(
                    session,
                    document_id=document_id,
                    run_id=run.id,
                    step_index=step_seq,
                    job_id=job_id,
                )
                step_seq += 1
            elif stage == "extract":
                extract_body_text_stage(
                    session,
                    document_id=document_id,
                    run_id=run.id,
                    step_index=step_seq,
                    job_id=job_id,
                )
                step_seq += 1
            elif stage == "enrich":
                enrich_stage(
                    session,
                    document_id=document_id,
                    run_id=run.id,
                    step_index=step_seq,
                    job_id=job_id,
                )
                step_seq += 1
            elif stage == "score":
                score_enqueue_stage(
                    session,
                    document_id=document_id,
                    run_id=run.id,
                    step_index=step_seq,
                    job_id=job_id,
                )
                step_seq += 1
            elif stage == "index":
                index_opensearch_stage(
                    session,
                    document_id=document_id,
                    run_id=run.id,
                    step_index=step_seq,
                    job_id=job_id,
                )
                step_seq += 1

        pipe_repo.complete_run(session, run)
        pipe_repo.set_document_status(session, document_id, "completed")
        log.info("pipeline_complete document_id=%s job_id=%s", document_id, job_id)
    except Exception as e:
        pipe_repo.fail_run(session, run, str(e))
        pipe_repo.set_document_status(session, document_id, "failed")
        log.exception("pipeline_failed document_id=%s job_id=%s", document_id, job_id)
        raise
