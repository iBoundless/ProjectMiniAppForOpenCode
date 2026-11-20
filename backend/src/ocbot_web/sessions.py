"""Сессии OpenCode для панели: сериализация, список, создание, черновики."""

from __future__ import annotations

import secrets
import time
from collections import OrderedDict
from collections.abc import Callable
from dataclasses import dataclass
from math import ceil
from pathlib import Path
from typing import Any

from ocbot.opencode.models import ModelRef, Project, SessionInfo
from ocbot.permissions_profile import BOT_SESSION_PERMISSIONS
from ocbot.store import Store
from ocbot.taskflow import create_bot_session, parse_default_model

MAX_LIMIT = 50
# Сколько корневых сессий запрашивать у OpenCode для фильтра и пагинации.
FETCH_LIMIT = 200
DRAFT_TTL = 600
MAX_DRAFTS = 100
DEFAULT_MODEL_KEY = "default_model"


def session_status(session: SessionInfo) -> str:
    """busy, если идет выполнение; иначе итог (succeeded, failed, ...) или idle."""
    if session.time.is_busy():
        return "busy"
    return session.outcome or "idle"


def matches_status(session: SessionInfo, status: str | None) -> bool:
    if not status or status == "all":
        return True
    current = session_status(session)
    if status in ("busy", "active"):
        return current == "busy"
    if status == "idle":
        return current != "busy"
    return current == status


def project_title(
    session: SessionInfo, projects: dict[str, Project]
) -> str | None:
    if session.project_id and session.project_id in projects:
        return projects[session.project_id].title
    if session.directory:
        return session.directory.rstrip("/").rsplit("/", 1)[-1] or session.directory
    return None


def serialize_session(
    session: SessionInfo,
    projects: dict[str, Project],
    *,
    subscribed: bool,
    active: bool = False,
) -> dict[str, Any]:
    model = None
    if session.model is not None:
        model = {
            "provider": session.model.provider_id,
            "id": session.model.id,
            "variant": session.model.variant,
        }
    return {
        "id": session.id,
        "parent_id": session.parent_id,
        "title": session.title or "",
        "project": {
            "id": session.project_id,
            "title": project_title(session, projects),
        },
        "directory": session.directory,
        "model": model,
        "agent": session.agent,
        "status": session_status(session),
        "busy": session.time.is_busy(),
        "outcome": session.outcome,
        "cost": session.cost,
        "time": {
            "created": session.time.created,
            "updated": session.time.updated,
            "busy": session.time.busy,
            "idle": session.time.idle,
        },
        "subscribed": subscribed,
        "active": active,
    }


async def subscribed_ids(store: Store, user_id: int, session_ids: list[str]) -> set[str]:
    result = set()
    for session_id in session_ids:
        if user_id in await store.subscribers(session_id):
            result.add(session_id)
    return result


async def list_page(
    client: Any,
    store: Store,
    user_id: int,
    *,
    page: int,
    limit: int,
    search: str | None,
    status: str | None,
) -> dict[str, Any]:
    sessions = await client.list_sessions(limit=FETCH_LIMIT, search=search or None)
    projects = {project.id: project for project in await client.list_projects()}
    roots = [
        session
        for session in sessions
        if not session.parent_id and matches_status(session, status)
    ]
    # Активные сверху, дальше по времени обновления.
    roots.sort(key=lambda s: (not s.time.is_busy(), -(s.time.updated or s.time.created)))
    total = len(roots)
    pages = max(1, ceil(total / limit))
    page = min(max(1, page), pages)
    chunk = roots[(page - 1) * limit : page * limit]
    subscribed = await subscribed_ids(store, user_id, [s.id for s in chunk])
    chat = await store.get_chat(user_id)
    return {
        "items": [
            serialize_session(
                session,
                projects,
                subscribed=session.id in subscribed,
                active=session.id == chat.active_session,
            )
            for session in chunk
        ],
        "page": page,
        "pages": pages,
        "limit": limit,
        "total": total,
        "busy_count": sum(1 for s in roots if s.time.is_busy()),
    }


async def session_card(client: Any, store: Store, user_id: int, session_id: str) -> dict[str, Any]:
    session = await client.get_session(session_id)
    projects = {project.id: project for project in await client.list_projects()}
    subscribed = user_id in await store.subscribers(session.id)
    chat = await store.get_chat(user_id)
    card = serialize_session(
        session, projects, subscribed=subscribed, active=chat.active_session == session.id
    )
    card["last_text"] = await client.last_assistant_text(session.id)
    return card


def check_directory(value: str) -> str:
    """Абсолютный путь к существующему каталогу на этой машине."""
    path = Path(value)
    if not path.is_absolute():
        raise ValueError("Путь к проекту должен быть абсолютным")
    if ".." in path.parts:
        raise ValueError("Путь не должен содержать ..")
    if not path.is_dir():
        raise ValueError("Каталог проекта не найден")
    return str(path)


async def resolve_model(store: Store, model: ModelRef | None) -> ModelRef | None:
    """Явная модель или модель по умолчанию, выбранная в боте."""
    if model is not None:
        return model
    return parse_default_model(await store.meta_get(DEFAULT_MODEL_KEY))


async def create_task(
    client: Any,
    store: Store,
    *,
    chat_id: int,
    directory: str,
    model: ModelRef | None,
    agent: str | None,
    text: str,
    title: str | None = None,
) -> SessionInfo:
    """Создать сессию со строгим профилем прав бота и отправить первый текст.

    Без агента используется `create_bot_session` бота как есть. Агента
    `create_bot_session` не принимает, поэтому для него те же шаги
    повторены с передачей `agent`.
    """
    model = await resolve_model(store, model)
    if agent is None:
        return await create_bot_session(
            client,
            store,
            chat_id=chat_id,
            directory=directory,
            model=model,
            text=text,
            title=title,
        )
    session = await client.create_session(
        directory,
        model=model,
        agent=agent,
        permissions=BOT_SESSION_PERMISSIONS,
        title=title or text.strip().splitlines()[0][:60] or None,
    )
    await store.subscribe(chat_id, session.id)
    await store.set_active_session(chat_id, session.id)
    await client.prompt(session.id, text, delivery="queue")
    return session


@dataclass(slots=True)
class Draft:
    session_id: str
    user_id: int
    text: str
    expires_at: float


class DraftStore:
    """Текст, не отправленный в занятую сессию, ждет решения queue/steer."""

    def __init__(self, *, ttl: float = DRAFT_TTL, now: Callable[[], float] | None = None) -> None:
        self._ttl = ttl
        self._now = now or time.monotonic
        self._items: OrderedDict[str, Draft] = OrderedDict()

    def _purge(self) -> None:
        now = self._now()
        for key in [key for key, draft in self._items.items() if draft.expires_at <= now]:
            del self._items[key]
        while len(self._items) > MAX_DRAFTS:
            self._items.popitem(last=False)

    def put(self, session_id: str, user_id: int, text: str) -> str:
        self._purge()
        draft_id = secrets.token_urlsafe(12)
        self._items[draft_id] = Draft(session_id, user_id, text, self._now() + self._ttl)
        self._purge()
        return draft_id

    def pop(self, draft_id: str, session_id: str, user_id: int) -> str | None:
        self._purge()
        draft = self._items.get(draft_id)
        if draft is None or draft.session_id != session_id or draft.user_id != user_id:
            return None
        del self._items[draft_id]
        return draft.text

    def __len__(self) -> int:
        self._purge()
        return len(self._items)


async def user_subscriptions(store: Store, user_id: int) -> list[str]:
    """ID сессий, на которые подписан чат пользователя.

    В `Store` бота нет такого метода, поэтому читаем таблицу `subscriptions`
    напрямую, только SELECT.
    """
    cursor = await store._connection.execute(
        "SELECT session_id FROM subscriptions WHERE chat_id = ? ORDER BY session_id",
        (user_id,),
    )
    rows = await cursor.fetchall()
    await cursor.close()
    return [row[0] for row in rows]


MAX_ANCESTORS = 8


class Visibility:
    """Какие сессии видит пользователь: подписка на сессию или ее корень,
    активная сессия или `notify_all`. Результаты кэшируются на объект."""

    def __init__(self, client: Any, store: Store, user_id: int) -> None:
        self.client = client
        self.store = store
        self.user_id = user_id
        self._chain: dict[str, list[str]] = {}
        self._own: set[str] | None = None
        self._all: bool | None = None

    async def _load(self) -> None:
        if self._own is not None:
            return
        chat = await self.store.get_chat(self.user_id)
        self._all = chat.notify_all
        own = set(await user_subscriptions(self.store, self.user_id))
        if chat.active_session:
            own.add(chat.active_session)
        self._own = own

    async def chain(self, session_id: str) -> list[str]:
        """Сессия и ее предки до корня (без сетевых ошибок наружу)."""
        if session_id in self._chain:
            return self._chain[session_id]
        result = [session_id]
        current = session_id
        for _ in range(MAX_ANCESTORS):
            try:
                info = await self.client.get_session(current)
            except Exception:  # noqa: BLE001 - нет данных, значит без предков
                break
            if not info.parent_id or info.parent_id in result:
                break
            current = info.parent_id
            result.append(current)
        self._chain[session_id] = result
        return result

    async def can_see(self, session_id: str) -> bool:
        await self._load()
        if self._all:
            return True
        assert self._own is not None
        if session_id in self._own:
            return True
        return any(item in self._own for item in await self.chain(session_id))

    def remember(self, session_id: str) -> None:
        """Сессия, созданная пользователем, видна сразу."""
        if self._own is not None:
            self._own.add(session_id)
