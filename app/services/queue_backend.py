"""Job queue: Redis/ARQ in production, in-memory for tests and local dev."""

from __future__ import annotations

import asyncio
import uuid
from typing import Protocol

from arq import create_pool
from arq.connections import ArqRedis, RedisSettings

from app.core.config import get_settings


class JobQueue(Protocol):
    async def enqueue_process_document(self, document_id: str) -> str: ...

    async def enqueue_fetch_url_ingest(self, document_id: str) -> str: ...

    async def enqueue_score_document(self, document_id: str) -> str: ...


class InMemoryJobQueue:
    """Test-safe queue: records jobs; worker is not consuming these."""

    def __init__(self) -> None:
        # (job_id, function_name, document_id)
        self.jobs: list[tuple[str, str, str]] = []
        self._lock = asyncio.Lock()

    async def enqueue_process_document(self, document_id: str) -> str:
        job_id = str(uuid.uuid4())
        async with self._lock:
            self.jobs.append((job_id, "process_document", document_id))
        return job_id

    async def enqueue_fetch_url_ingest(self, document_id: str) -> str:
        job_id = str(uuid.uuid4())
        async with self._lock:
            self.jobs.append((job_id, "fetch_url_and_ingest", document_id))
        return job_id

    async def enqueue_score_document(self, document_id: str) -> str:
        job_id = str(uuid.uuid4())
        async with self._lock:
            self.jobs.append((job_id, "score_document", document_id))
        return job_id


class ArqJobQueue:
    """Enqueue ARQ jobs on Redis."""

    def __init__(self, pool: ArqRedis) -> None:
        self._pool = pool

    async def enqueue_process_document(self, document_id: str) -> str:
        job = await self._pool.enqueue_job("process_document", document_id)
        if job is None:
            raise RuntimeError("failed to enqueue process_document (duplicate job id?)")
        return job.job_id

    async def enqueue_fetch_url_ingest(self, document_id: str) -> str:
        job = await self._pool.enqueue_job("fetch_url_and_ingest", document_id)
        if job is None:
            raise RuntimeError("failed to enqueue fetch_url_and_ingest (duplicate job id?)")
        return job.job_id

    async def enqueue_score_document(self, document_id: str) -> str:
        job = await self._pool.enqueue_job("score_document", document_id)
        if job is None:
            raise RuntimeError("failed to enqueue score_document (duplicate job id?)")
        return job.job_id


_memory_queue: InMemoryJobQueue | None = None
_arq_pool: ArqRedis | None = None
_arq_lock = asyncio.Lock()


def get_memory_queue() -> InMemoryJobQueue:
    global _memory_queue
    if _memory_queue is None:
        _memory_queue = InMemoryJobQueue()
    return _memory_queue


async def get_job_queue() -> JobQueue:
    settings = get_settings()
    if settings.use_fake_queue:
        return get_memory_queue()

    global _arq_pool
    async with _arq_lock:
        if _arq_pool is None:
            redis_settings = RedisSettings.from_dsn(settings.redis_url)
            _arq_pool = await create_pool(
                redis_settings,
                default_queue_name=settings.arq_queue_name,
            )
    return ArqJobQueue(_arq_pool)


async def close_job_queue() -> None:
    global _arq_pool, _memory_queue
    if _arq_pool is not None:
        await _arq_pool.close()
        _arq_pool = None
    _memory_queue = None
