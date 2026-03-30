"""Worker enqueue with structured logging (ARQ / in-memory)."""

from __future__ import annotations

import asyncio
import logging

from app.services.queue_backend import get_job_queue

log = logging.getLogger("verifiedsignal.queue")


async def enqueue_process_document(document_id: str) -> str:
    log.info("enqueue_attempt document_id=%s", document_id)
    try:
        queue = await get_job_queue()
        job_id = await queue.enqueue_process_document(document_id)
        log.info("enqueue_success document_id=%s job_id=%s", document_id, job_id)
        return job_id
    except Exception:
        log.exception("enqueue_failure document_id=%s", document_id)
        raise


def enqueue_process_document_sync(document_id: str) -> str:
    """Use from synchronous FastAPI routes (sync def) without a running event loop."""
    return asyncio.run(enqueue_process_document(document_id))


async def enqueue_fetch_url_ingest(document_id: str) -> str:
    log.info("enqueue_fetch_url_attempt document_id=%s", document_id)
    try:
        queue = await get_job_queue()
        job_id = await queue.enqueue_fetch_url_ingest(document_id)
        log.info("enqueue_fetch_url_success document_id=%s job_id=%s", document_id, job_id)
        return job_id
    except Exception:
        log.exception("enqueue_fetch_url_failure document_id=%s", document_id)
        raise


def enqueue_fetch_url_ingest_sync(document_id: str) -> str:
    return asyncio.run(enqueue_fetch_url_ingest(document_id))


async def enqueue_score_document(document_id: str) -> str:
    log.info("enqueue_score_attempt document_id=%s", document_id)
    try:
        queue = await get_job_queue()
        job_id = await queue.enqueue_score_document(document_id)
        log.info("enqueue_score_success document_id=%s job_id=%s", document_id, job_id)
        return job_id
    except Exception:
        log.exception("enqueue_score_failure document_id=%s", document_id)
        raise


def enqueue_score_document_sync(document_id: str) -> str:
    return asyncio.run(enqueue_score_document(document_id))
