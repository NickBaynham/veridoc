"""Reachability checks for Redis, object storage, and OpenSearch (health endpoint)."""

from __future__ import annotations

import logging

import boto3
import httpx
from botocore.config import Config
from botocore.exceptions import BotoCoreError, ClientError

from app.core.config import Settings, get_settings

log = logging.getLogger(__name__)

# (status, error_type, error_message) — error_* None when status is up or stub
ComponentResult = tuple[str, str | None, str | None]


def _truncate(msg: str, max_len: int = 500) -> str:
    if len(msg) <= max_len:
        return msg
    return msg[: max_len - 1] + "…"


def check_redis_component(settings: Settings | None = None) -> ComponentResult:
    """PING Redis when ARQ queue is enabled; otherwise stub."""
    s = settings or get_settings()
    if s.use_fake_queue:
        return "stub", None, None
    try:
        import redis as redis_lib

        client = redis_lib.from_url(
            s.redis_url,
            socket_connect_timeout=2.0,
            socket_timeout=2.0,
            decode_responses=True,
        )
        try:
            client.ping()
            return "up", None, None
        finally:
            client.close()
    except Exception as e:
        log.debug("redis health failed", exc_info=True)
        return "down", type(e).__name__, _truncate(str(e))


def check_object_storage_component(settings: Settings | None = None) -> ComponentResult:
    """HEAD bucket when S3/MinIO is enabled; otherwise stub."""
    s = settings or get_settings()
    if s.use_fake_storage:
        return "stub", None, None
    try:
        cfg = Config(
            connect_timeout=2,
            read_timeout=2,
            signature_version="s3v4",
            s3={"addressing_style": "path" if s.s3_use_path_style else "auto"},
        )
        client = boto3.client(
            "s3",
            endpoint_url=s.s3_endpoint_url or None,
            aws_access_key_id=s.s3_access_key_id,
            aws_secret_access_key=s.s3_secret_access_key,
            region_name=s.s3_region,
            config=cfg,
        )
        client.head_bucket(Bucket=s.s3_bucket)
        return "up", None, None
    except (ClientError, BotoCoreError) as e:
        log.debug("object storage health failed", exc_info=True)
        return "down", type(e).__name__, _truncate(str(e))
    except Exception as e:
        log.debug("object storage health failed", exc_info=True)
        return "down", type(e).__name__, _truncate(str(e))


def check_opensearch_component(settings: Settings | None = None) -> ComponentResult:
    """
    GET cluster root (OpenSearch / Elasticsearch compatible).
    Treats HTTP 5xx as down; connection errors as down; 2xx–4xx as up (service answered).
    """
    s = settings or get_settings()
    base = s.opensearch_url.rstrip("/")
    url = f"{base}/"
    try:
        with httpx.Client(timeout=2.0, follow_redirects=True) as client:
            response = client.get(url)
        if response.status_code >= 500:
            return (
                "down",
                "HTTPStatusError",
                _truncate(f"HTTP {response.status_code} from OpenSearch root"),
            )
        return "up", None, None
    except httpx.RequestException as e:
        log.debug("opensearch health failed", exc_info=True)
        return "down", type(e).__name__, _truncate(str(e))
    except Exception as e:
        log.debug("opensearch health failed", exc_info=True)
        return "down", type(e).__name__, _truncate(str(e))


def overall_status_from_components(
    *,
    database_ok: bool,
    redis_status: str,
    object_storage_status: str,
    opensearch_status: str,
) -> str:
    """ok if Postgres is up and every non-stub dependency is up."""
    if not database_ok:
        return "degraded"
    for part in (redis_status, object_storage_status, opensearch_status):
        if part == "down":
            return "degraded"
    return "ok"
