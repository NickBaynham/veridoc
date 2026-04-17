"""Job queue: Redis/ARQ in production, in-memory for tests and local dev."""

from __future__ import annotations

import asyncio
import uuid
from typing import Protocol

from arq.connections import ArqRedis


class JobQueue(Protocol):
    async def enqueue_process_document(self, document_id: str) -> str: ...

    async def enqueue_fetch_url_ingest(self, document_id: str) -> str: ...

    async def enqueue_score_document(self, document_id: str) -> str: ...

    async def enqueue_build_knowledge_model_version(self, model_version_id: str) -> str: ...


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

    async def enqueue_build_knowledge_model_version(self, model_version_id: str) -> str:
        job_id = str(uuid.uuid4())
        async with self._lock:
            self.jobs.append((job_id, "build_knowledge_model_version", model_version_id))
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

    async def enqueue_build_knowledge_model_version(self, model_version_id: str) -> str:
        job = await self._pool.enqueue_job("build_knowledge_model_version", model_version_id)
        if job is None:
            raise RuntimeError(
                "failed to enqueue build_knowledge_model_version (duplicate job id?)",
            )
        return job.job_id


_memory_queue: InMemoryJobQueue | None = None


def get_memory_queue() -> InMemoryJobQueue:
    global _memory_queue
    if _memory_queue is None:
        _memory_queue = InMemoryJobQueue()
    return _memory_queue


async def close_job_queue() -> None:
    """Reset in-memory test queue. Real ARQ pools are per-enqueue (see queue_service)."""
    global _memory_queue
    _memory_queue = None
