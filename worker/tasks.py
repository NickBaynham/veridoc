"""ARQ task entrypoints."""

from __future__ import annotations

import asyncio
from typing import Any

from app.services.url_ingest_worker import run_fetch_url_and_ingest_sync
from arq.worker import func as arq_job

from worker.logging import get_logger
from worker.pipeline import run_document_pipeline

log = get_logger("verifiedsignal.worker.tasks")


async def build_knowledge_model_version(ctx: dict[str, Any], model_version_id: str) -> str:
    """Background: materialize summary_json for a knowledge_model_versions row."""
    from app.services.models.model_build_worker import run_build_knowledge_model_version_sync

    log.info("task_build_knowledge_model_version version_id=%s", model_version_id)
    await asyncio.to_thread(run_build_knowledge_model_version_sync, model_version_id)
    return model_version_id


async def fetch_url_and_ingest(ctx: dict[str, Any], document_id: str) -> str:
    """Fetch remote URL for a `created` document, upload raw bytes, enqueue `process_document`."""
    log.info("task_fetch_url_and_ingest document_id=%s", document_id)
    await asyncio.to_thread(run_fetch_url_and_ingest_sync, document_id)
    return document_id


async def _score_document(ctx: dict[str, Any], document_id: str) -> str:
    """
    Scoring job: stub or HTTP remote scorer (`SCORE_ASYNC_BACKEND`, `SCORE_HTTP_URL`).

    Transient remote failures raise after DB rollback so ARQ retries (see `max_tries`).
    """
    from app.services.score_document_worker import (
        ScoringRetryableError,
        run_score_document_sync,
    )

    log.info("task_score_document document_id=%s", document_id)
    try:
        await asyncio.to_thread(run_score_document_sync, document_id)
    except ScoringRetryableError:
        log.warning("task_score_document_retryable document_id=%s", document_id)
        raise
    return document_id


# Registered as `score_document` for enqueue_job; retries transient HTTP/network failures.
score_document = arq_job(_score_document, name="score_document", max_tries=5)


async def process_document(ctx: dict[str, Any], document_id: str) -> str:
    """
    Background job: process a single document through the scaffold pipeline.

    Name must match API enqueue: `enqueue_job("process_document", document_id)`.
    """
    log.info("task_process_document document_id=%s", document_id)
    await run_document_pipeline(ctx, document_id)
    return document_id
