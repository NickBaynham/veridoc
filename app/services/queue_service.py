"""Worker enqueue with structured logging (ARQ / in-memory)."""

from __future__ import annotations

import asyncio
import logging

from arq import create_pool
from arq.connections import RedisSettings

from app.core.config import get_settings
from app.services.queue_backend import ArqJobQueue, get_memory_queue

log = logging.getLogger("verifiedsignal.queue")


async def _enqueue_with_ephemeral_arq(enqueue) -> str:
    """
    Create a dedicated ARQ Redis pool for this operation and close it afterward.

    Sync API routes call ``asyncio.run(enqueue_...)`` from thread-pool workers; each run uses a
    fresh event loop. A process-global pool would be bound to the first (now-closed) loop and
    breaks subsequent enqueues — e.g. second document stays ``queued`` with no worker pickup.
    """
    settings = get_settings()
    redis_settings = RedisSettings.from_dsn(settings.redis_url)
    pool = await create_pool(
        redis_settings,
        default_queue_name=settings.arq_queue_name,
    )
    try:
        return await enqueue(ArqJobQueue(pool))
    finally:
        await pool.close()


async def enqueue_process_document(document_id: str) -> str:
    log.info("enqueue_attempt document_id=%s", document_id)
    try:
        settings = get_settings()
        if settings.use_fake_queue:
            queue = get_memory_queue()
            job_id = await queue.enqueue_process_document(document_id)
        else:
            job_id = await _enqueue_with_ephemeral_arq(
                lambda q: q.enqueue_process_document(document_id),
            )
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
        settings = get_settings()
        if settings.use_fake_queue:
            queue = get_memory_queue()
            job_id = await queue.enqueue_fetch_url_ingest(document_id)
        else:
            job_id = await _enqueue_with_ephemeral_arq(
                lambda q: q.enqueue_fetch_url_ingest(document_id),
            )
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
        settings = get_settings()
        if settings.use_fake_queue:
            queue = get_memory_queue()
            job_id = await queue.enqueue_score_document(document_id)
        else:
            job_id = await _enqueue_with_ephemeral_arq(
                lambda q: q.enqueue_score_document(document_id),
            )
        log.info("enqueue_score_success document_id=%s job_id=%s", document_id, job_id)
        return job_id
    except Exception:
        log.exception("enqueue_score_failure document_id=%s", document_id)
        raise


def enqueue_score_document_sync(document_id: str) -> str:
    return asyncio.run(enqueue_score_document(document_id))


async def enqueue_build_knowledge_model_version(model_version_id: str) -> str:
    log.info("enqueue_knowledge_model_build_attempt version_id=%s", model_version_id)
    try:
        settings = get_settings()
        if settings.use_fake_queue:
            queue = get_memory_queue()
            job_id = await queue.enqueue_build_knowledge_model_version(model_version_id)
        else:
            job_id = await _enqueue_with_ephemeral_arq(
                lambda q: q.enqueue_build_knowledge_model_version(model_version_id),
            )
        log.info(
            "enqueue_knowledge_model_build_success version_id=%s job_id=%s",
            model_version_id,
            job_id,
        )
        return job_id
    except Exception:
        log.exception("enqueue_knowledge_model_build_failure version_id=%s", model_version_id)
        raise


def enqueue_build_knowledge_model_version_sync(model_version_id: str) -> str:
    return asyncio.run(enqueue_build_knowledge_model_version(model_version_id))
