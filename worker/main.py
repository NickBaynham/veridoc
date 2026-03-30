"""
ARQ worker process entry.

Run locally:
  pdm run arq worker.main.WorkerSettings

Docker Compose provides a `worker` service with the same command.
"""

from __future__ import annotations

from worker.config import QUEUE_NAME, redis_settings
from worker.logging import configure_logging
from worker.tasks import fetch_url_and_ingest, process_document, score_document

configure_logging()


class WorkerSettings:
    functions = [process_document, fetch_url_and_ingest, score_document]
    redis_settings = redis_settings
    queue_name = QUEUE_NAME
