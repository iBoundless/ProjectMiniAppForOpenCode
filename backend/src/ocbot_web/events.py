"""Один потребитель SSE OpenCode и раздача событий подключенным панелям."""

from __future__ import annotations

import asyncio
import contextlib
import json
import logging
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any

from ocbot.opencode.events import Event, backoff_delay

from .sessions import Visibility

log = logging.getLogger(__name__)

HEARTBEAT_SECONDS = 20.0
QUEUE_SIZE = 500
# Как часто перечитывать подписки и notify_all пользователя из базы бота.
VISIBILITY_TTL = 5.0
CLOSE = ""

FORWARDED_TYPES = frozenset(
    {
        "session.execution.started",
        "session.text.delta",
        "session.reasoning.delta",
        "session.tool.input.started",
        "session.tool.success",
        "session.tool.failed",
        "session.execution.succeeded",
        "session.execution.failed",
        "session.execution.interrupted",
        "session.idle",
        "session.updated",
        "session.deleted",
        "permission.asked",
        "permission.replied",
    }
)


def event_session_id(event: Event) -> str | None:
    data = event.data if isinstance(event.data, dict) else {}
    for source in (data, data.get("properties"), data.get("info"), data.get("session")):
        if not isinstance(source, dict):
            continue
        for key in ("sessionID", "session_id"):
            value = source.get(key)
            if isinstance(value, str) and value:
                return value
    if event.type.startswith("session.") and isinstance(data.get("id"), str):
        return data["id"]
    return None


def format_event(event: Event, session_id: str | None) -> str:
    payload = {
        "type": event.type,
        "session_id": session_id,
        "data": event.data,
        "created": event.created,
    }
    lines = []
    if event.id:
        lines.append(f"id: {event.id}")
    lines.append("data: " + json.dumps(payload, ensure_ascii=False, separators=(",", ":")))
    return "\n".join(lines) + "\n\n"


@dataclass(eq=False)
class Connection:
    user_id: int
    visibility: Visibility
    queue: asyncio.Queue[str] = field(default_factory=lambda: asyncio.Queue(QUEUE_SIZE))
    refreshed: float = 0.0
    dropped: int = 0

    def push(self, chunk: str) -> None:
        if self.queue.full():
            # Медленный клиент: теряем самое старое, а не блокируем остальных.
            with contextlib.suppress(asyncio.QueueEmpty):
                self.queue.get_nowait()
            self.dropped += 1
        self.queue.put_nowait(chunk)


class EventHub:
    def __init__(
        self,
        client: Any,
        store: Any,
        *,
        sleep: Callable[[float], Awaitable[None]] | None = None,
        now: Callable[[], float] | None = None,
    ) -> None:
        self.client = client
        self.store = store
        self._sleep = sleep or asyncio.sleep
        self._now = now or time.monotonic
        self.connections: set[Connection] = set()
        self._task: asyncio.Task[None] | None = None
        self.reconnects = 0

    def connect(self, user_id: int) -> Connection:
        connection = Connection(user_id, Visibility(self.client, self.store, user_id))
        self.connections.add(connection)
        return connection

    def disconnect(self, connection: Connection) -> None:
        self.connections.discard(connection)

    def remember(self, user_id: int, session_id: str) -> None:
        """Новая сессия пользователя видна его подключениям сразу."""
        for connection in self.connections:
            if connection.user_id == user_id:
                connection.visibility.remember(session_id)

    async def _visible(self, connection: Connection, session_id: str) -> bool:
        now = self._now()
        if now - connection.refreshed > VISIBILITY_TTL:
            connection.visibility.refresh()
            connection.refreshed = now
        try:
            return await connection.visibility.can_see(session_id)
        except Exception:  # noqa: BLE001
            log.warning("visibility check failed", exc_info=True)
            return False

    async def dispatch(self, event: Event) -> None:
        if event.type not in FORWARDED_TYPES:
            return
        session_id = event_session_id(event)
        if session_id is None:
            return
        chunk = format_event(event, session_id)
        for connection in list(self.connections):
            if await self._visible(connection, session_id):
                connection.push(chunk)

    async def run(self) -> None:
        """Читать OpenCode SSE бесконечно, переподключаясь с backoff."""
        failures = 0
        while True:
            try:
                async for event in self.client.events():
                    failures = 0
                    await self.dispatch(event)
                log.info("opencode event stream ended")
            except asyncio.CancelledError:
                raise
            except Exception as exc:  # noqa: BLE001
                log.warning("opencode event stream failed: %s", type(exc).__name__)
            self.reconnects += 1
            delay = backoff_delay(failures)
            failures += 1
            await self._sleep(delay)

    def start(self) -> None:
        if self._task is None or self._task.done():
            self._task = asyncio.create_task(self.run(), name="opencode-events")

    def close_all(self) -> None:
        """Попросить все подключения завершиться (пустая строка - сигнал)."""
        for connection in list(self.connections):
            connection.push(CLOSE)

    async def stop(self) -> None:
        if self._task is not None:
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError, Exception):
                await self._task
            self._task = None
        self.connections.clear()
