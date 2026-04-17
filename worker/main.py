"""
ARQ worker process entry.

Run locally:
  pdm run arq worker.main.WorkerSettings

Docker Compose provides a `worker` service with the same command.
"""

from __future__ import annotations

from typing import ClassVar

from worker.config import QUEUE_NAME, redis_settings
from worker.logging import configure_logging
from worker.tasks import (
    build_knowledge_model_version,
    fetch_url_and_ingest,
    process_document,
    score_document,
)

configure_logging()


class WorkerSettings:
    # ClassVar: list must not be treated as a per-instance default (RUF012).
    functions: ClassVar[list] = [
        process_document,
        fetch_url_and_ingest,
        score_document,
        build_knowledge_model_version,
    ]
    redis_settings = redis_settings
    queue_name = QUEUE_NAME
