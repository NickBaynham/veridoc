"""Unit tests: score_document job enqueue on fake queue."""

from __future__ import annotations

import asyncio
import os
import uuid

import pytest
from app.core.config import reset_settings_cache
from app.services.queue_backend import close_job_queue, get_memory_queue
from app.services.queue_service import enqueue_score_document


@pytest.mark.unit
def test_enqueue_score_document_records_on_fake_queue():
    os.environ["USE_FAKE_QUEUE"] = "true"
    reset_settings_cache()

    async def _run():
        await close_job_queue()
        did = str(uuid.uuid4())
        jid = await enqueue_score_document(did)
        assert jid
        q = get_memory_queue()
        assert q.jobs == [(jid, "score_document", did)]
        await close_job_queue()

    asyncio.run(_run())
    reset_settings_cache()
    os.environ.pop("USE_FAKE_QUEUE", None)
