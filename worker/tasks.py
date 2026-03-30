"""ARQ task entrypoints."""

from __future__ import annotations

import asyncio
from typing import Any

from app.services.url_ingest_worker import run_fetch_url_and_ingest_sync

from worker.logging import get_logger
from worker.pipeline import run_document_pipeline

log = get_logger("verifiedsignal.worker.tasks")


async def fetch_url_and_ingest(ctx: dict[str, Any], document_id: str) -> str:
    """Fetch remote URL for a `created` document, upload raw bytes, enqueue `process_document`."""
    log.info("task_fetch_url_and_ingest document_id=%s", document_id)
    await asyncio.to_thread(run_fetch_url_and_ingest_sync, document_id)
    return document_id


async def score_document(ctx: dict[str, Any], document_id: str) -> str:
    """Stub scoring job: placeholder row in `document_scores` (real models TBD)."""
    from app.services.score_document_worker import run_score_document_sync

    log.info("task_score_document document_id=%s", document_id)
    await asyncio.to_thread(run_score_document_sync, document_id)
    return document_id


async def process_document(ctx: dict[str, Any], document_id: str) -> str:
    """
    Background job: process a single document through the scaffold pipeline.

    Name must match API enqueue: `enqueue_job("process_document", document_id)`.
    """
    log.info("task_process_document document_id=%s", document_id)
    await run_document_pipeline(ctx, document_id)
    return document_id
