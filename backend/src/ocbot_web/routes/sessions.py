"""API сессий: список, карточка, создание, текст, остановка, удаление."""

from __future__ import annotations

import logging
import re
from typing import Literal

from aiohttp import web
from ocbot.opencode.models import ModelRef
from pydantic import BaseModel, Field, field_validator

from ..auth import login_required, user_id
from ..errors import ApiError, json_response, read_model, validation
from ..keys import CLIENT, DRAFTS, HUB, STORE
from ..sessions import (
    MAX_LIMIT,
    check_directory,
    create_task,
    serialize_session,
    session_card,
    session_status,
)
from ..sessions import list_page as list_sessions_page

log = logging.getLogger(__name__)
routes = web.RouteTableDef()

ID_RE = re.compile(r"^[A-Za-z0-9_.\-]{1,128}$")
TEXT_LIMIT = 20000


def session_id_param(request: web.Request) -> str:
    """ID сессии подставляется в путь OpenCode API, поэтому строгий формат."""
    value = request.match_info["session_id"]
    if not ID_RE.match(value) or value in (".", ".."):
        raise ApiError(404, "Сессия не найдена")
    return value


def int_query(request: web.Request, name: str, default: int, low: int, high: int) -> int:
    raw = request.query.get(name)
    if raw is None or raw == "":
        return default
    try:
        value = int(raw)
    except ValueError as exc:
        raise validation(f"{name}: ожидается целое число") from exc
    return min(max(value, low), high)


class ModelChoice(BaseModel):
    provider: str = Field(min_length=1, max_length=200)
    id: str = Field(min_length=1, max_length=200)
    variant: str = Field(default="default", max_length=100)

    def ref(self) -> ModelRef:
        return ModelRef(id=self.id, provider_id=self.provider, variant=self.variant)


class CreateSession(BaseModel):
    directory: str = Field(min_length=1, max_length=4096)
    prompt: str = Field(min_length=1, max_length=TEXT_LIMIT)
    model: ModelChoice | None = None
    agent: str | None = Field(default=None, max_length=200)
    title: str | None = Field(default=None, max_length=200)

    @field_validator("prompt")
    @classmethod
    def _not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Текст задачи пустой")
        return value

    @field_validator("agent", "title")
    @classmethod
    def _empty_to_none(cls, value: str | None) -> str | None:
        return value.strip() or None if value is not None else None


class PromptBody(BaseModel):
    text: str | None = Field(default=None, max_length=TEXT_LIMIT)
    draft_id: str | None = Field(default=None, max_length=64)
    delivery: Literal["queue", "steer"] | None = None


@routes.get("/api/sessions")
@login_required
async def list_sessions(request: web.Request) -> web.Response:
    search = (request.query.get("search") or "").strip()[:200] or None
    status = (request.query.get("status") or "").strip()[:32] or None
    payload = await list_sessions_page(
        request.app[CLIENT],
        request.app[STORE],
        user_id(request),
        page=int_query(request, "page", 1, 1, 10_000),
        limit=int_query(request, "limit", 20, 1, MAX_LIMIT),
        search=search,
        status=status,
    )
    return json_response(payload)


@routes.get("/api/sessions/{session_id}")
@login_required
async def get_session(request: web.Request) -> web.Response:
    card = await session_card(
        request.app[CLIENT], request.app[STORE], user_id(request), session_id_param(request)
    )
    return json_response(card)


@routes.post("/api/sessions")
@login_required
async def create_session(request: web.Request) -> web.Response:
    body = await read_model(request, CreateSession)
    try:
        directory = check_directory(body.directory)
    except ValueError as exc:
        raise validation(str(exc)) from exc
    client = request.app[CLIENT]
    store = request.app[STORE]
    uid = user_id(request)
    session = await create_task(
        client,
        store,
        chat_id=uid,
        directory=directory,
        model=body.model.ref() if body.model else None,
        agent=body.agent,
        text=body.prompt,
        title=body.title,
    )
    log.info("session %s created by user %s", session.id, uid)
    hub = request.app.get(HUB)
    if hub is not None:
        hub.remember(uid, session.id)
    projects = {project.id: project for project in await client.list_projects()}
    return json_response(
        serialize_session(session, projects, subscribed=True, active=True), status=201
    )


@routes.post("/api/sessions/{session_id}/prompt")
@login_required
async def prompt(request: web.Request) -> web.Response:
    session_id = session_id_param(request)
    body = await read_model(request, PromptBody)
    client = request.app[CLIENT]
    drafts = request.app[DRAFTS]
    uid = user_id(request)

    text = body.text
    if body.draft_id:
        if body.delivery is None:
            raise validation("Для черновика нужен delivery: queue или steer")
        text = drafts.pop(body.draft_id, session_id, uid)
        if text is None:
            raise ApiError(404, "Черновик не найден или устарел")
    if not text or not text.strip():
        raise validation("Текст пустой")

    if body.delivery is None:
        session = await client.get_session(session_id)
        if session.time.is_busy():
            draft_id = drafts.put(session_id, uid, text)
            raise ApiError(
                409,
                "Сессия занята: поставить в очередь или вмешаться?",
                draft_id=draft_id,
                session_status=session_status(session),
            )
        delivery = "queue"
    else:
        await client.get_session(session_id)
        delivery = body.delivery

    await client.prompt(session_id, text, delivery=delivery)
    return json_response({"ok": True, "delivery": delivery})


@routes.post("/api/sessions/{session_id}/interrupt")
@login_required
async def interrupt(request: web.Request) -> web.Response:
    session_id = session_id_param(request)
    interrupted = await request.app[CLIENT].interrupt(session_id)
    return json_response({"interrupted": interrupted})


@routes.delete("/api/sessions/{session_id}")
@login_required
async def delete_session(request: web.Request) -> web.Response:
    session_id = session_id_param(request)
    if request.query.get("confirm") not in ("1", "true"):
        raise validation("Удаление требует подтверждения: confirm=true")
    client = request.app[CLIENT]
    await client.delete_session(session_id)
    await request.app[STORE].remove_session(session_id)
    log.info("session %s deleted by user %s", session_id, user_id(request))
    return json_response({"deleted": True})
