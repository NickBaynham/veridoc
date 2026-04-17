"""SSE fan-out: Redis pub/sub in production, in-memory when USE_FAKE_EVENT_HUB=true."""

from __future__ import annotations

import asyncio
import json
import logging
import threading
from abc import ABC, abstractmethod
from contextlib import suppress
from datetime import UTC, datetime
from typing import Any

import redis.asyncio as redis_async

from app.core.config import get_settings

log = logging.getLogger(__name__)


def _build_message(event_type: str, payload: dict[str, Any]) -> str:
    return json.dumps(
        {
            "type": event_type,
            "payload": payload,
            "ts": datetime.now(tz=UTC).isoformat(),
            "environment": get_settings().environment,
        }
    )


class EventHubBackend(ABC):
    """Shared contract for SSE event delivery."""

    @abstractmethod
    async def subscribe(self) -> asyncio.Queue[str]:
        raise NotImplementedError

    @abstractmethod
    async def unsubscribe(self, q: asyncio.Queue[str]) -> None:
        raise NotImplementedError

    @abstractmethod
    async def publish(self, event_type: str, payload: dict[str, Any]) -> None:
        raise NotImplementedError

    async def aclose(self) -> None:
        """Release external resources; Redis hub overrides."""
        return


class InMemoryEventHub(EventHubBackend):
    """Fan-out to SSE clients on a single process (tests / dev without Redis)."""

    def __init__(self) -> None:
        # (loop, queue): publish may use a different asyncio.run() than the SSE handler.
        self._subscribers: list[tuple[asyncio.AbstractEventLoop, asyncio.Queue[str]]] = []
        self._lock = threading.Lock()

    async def subscribe(self) -> asyncio.Queue[str]:
        q: asyncio.Queue[str] = asyncio.Queue(maxsize=256)
        loop = asyncio.get_running_loop()
        with self._lock:
            self._subscribers.append((loop, q))
        return q

    async def unsubscribe(self, q: asyncio.Queue[str]) -> None:
        with self._lock:
            self._subscribers = [(lp, qq) for lp, qq in self._subscribers if qq is not q]

    async def publish(self, event_type: str, payload: dict[str, Any]) -> None:
        msg = _build_message(event_type, payload)
        with self._lock:
            targets = list(self._subscribers)

        def _safe_put(qq: asyncio.Queue[str], data: str) -> None:
            with suppress(asyncio.QueueFull):
                qq.put_nowait(data)

        for loop, q in targets:
            loop.call_soon_threadsafe(_safe_put, q, msg)


class RedisEventHub(EventHubBackend):
    """
    Redis pub/sub so every API replica subscribed to the channel receives publishes.

    One Redis connection + pubsub per active SSE subscriber. Each ``publish`` uses a short-lived
    async client so callers can safely use ``asyncio.run(hub.publish(...))`` from sync routes
    (each run gets a new event loop; a cached publisher would be bound to a closed loop).
    """

    def __init__(self, redis_url: str, channel: str) -> None:
        self._url = redis_url
        self._channel = channel
        self._listener_tasks: dict[asyncio.Queue[str], asyncio.Task[None]] = {}
        self._listener_lock = asyncio.Lock()

    async def subscribe(self) -> asyncio.Queue[str]:
        q: asyncio.Queue[str] = asyncio.Queue(maxsize=256)
        client = redis_async.from_url(self._url, decode_responses=True)
        pubsub = client.pubsub()
        await pubsub.subscribe(self._channel)

        async def pump() -> None:
            try:
                async for message in pubsub.listen():
                    if message["type"] != "message":
                        continue
                    data = message.get("data")
                    if data is None:
                        continue
                    if not isinstance(data, str):
                        data = str(data)
                    with suppress(asyncio.QueueFull):
                        q.put_nowait(data)
            except asyncio.CancelledError:
                raise
            except Exception:
                log.exception("redis_sse_listener_failed channel=%s", self._channel)
            finally:
                with suppress(Exception):
                    await pubsub.unsubscribe(self._channel)
                with suppress(Exception):
                    await pubsub.aclose()
                with suppress(Exception):
                    await client.aclose()

        task = asyncio.create_task(pump())
        async with self._listener_lock:
            self._listener_tasks[q] = task
        return q

    async def unsubscribe(self, q: asyncio.Queue[str]) -> None:
        async with self._listener_lock:
            task = self._listener_tasks.pop(q, None)
        if task is not None and not task.done():
            task.cancel()
            with suppress(asyncio.CancelledError):
                await task

    async def publish(self, event_type: str, payload: dict[str, Any]) -> None:
        msg = _build_message(event_type, payload)
        client = redis_async.from_url(self._url, decode_responses=True)
        try:
            await client.publish(self._channel, msg)
        finally:
            with suppress(Exception):
                await client.aclose()

    async def aclose(self) -> None:
        async with self._listener_lock:
            tasks = list(self._listener_tasks.items())
            self._listener_tasks.clear()
        for _q, task in tasks:
            if not task.done():
                task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
            except Exception:
                pass


_hub: EventHubBackend | None = None


def get_event_hub() -> EventHubBackend:
    global _hub
    if _hub is None:
        s = get_settings()
        if s.use_fake_event_hub:
            _hub = InMemoryEventHub()
        else:
            _hub = RedisEventHub(s.redis_url, s.event_pubsub_channel)
    return _hub


def reset_event_hub() -> None:
    """Clear singleton; closes Redis hub when no asyncio loop conflict."""
    global _hub
    if _hub is None:
        return
    hub = _hub
    _hub = None
    with suppress(RuntimeError):
        # Nested event loop (e.g. test setup): aclose may not run; reference is dropped anyway.
        asyncio.run(hub.aclose())


async def close_event_hub() -> None:
    """Application shutdown: close hub and clear singleton."""
    global _hub
    if _hub is None:
        return
    hub = _hub
    _hub = None
    await hub.aclose()
