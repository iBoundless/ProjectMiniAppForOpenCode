"""Запросы прав OpenCode: список и решение.

Строки `permission_messages` принадлежат боту, панель их только читает.
"""

from __future__ import annotations

import logging
import re
from typing import Any, Literal

from aiohttp import web
from ocbot.opencode.models import PermissionRequest
from pydantic import BaseModel

from ..auth import login_required, user_id
from ..errors import ApiError, json_response, read_model
from ..keys import CLIENT, STORE
from ..sessions import Visibility

log = logging.getLogger(__name__)
routes = web.RouteTableDef()

ID_RE = re.compile(r"^[A-Za-z0-9_.\-]{1,128}$")


class ReplyBody(BaseModel):
    decision: Literal["once", "always", "reject"]


def serialize_permission(item: PermissionRequest) -> dict[str, Any]:
    return {
        "id": item.id,
        "session_id": item.session_id,
        "action": item.action,
        "resources": item.resources,
        "message": item.message,
        "directory": item.source.directory if item.source else None,
        "save": item.save,
    }


async def addressed_to(store: Any, user: int) -> set[str]:
    """ID запросов, которые бот отправил этому пользователю."""
    try:
        messages = await store.list_permission_messages()
    except Exception:  # noqa: BLE001 - таблицы может не быть у старого бота
        return set()
    return {m.request_id for m in messages if m.chat_id == user}


async def visible_permissions(request: web.Request) -> list[PermissionRequest]:
    client = request.app[CLIENT]
    store = request.app[STORE]
    uid = user_id(request)
    pending = await client.list_permissions()
    if not pending:
        return []
    visibility = Visibility(client, store, uid)
    mine = await addressed_to(store, uid)
    return [
        item
        for item in pending
        if item.id in mine or await visibility.can_see(item.session_id)
    ]


@routes.get("/api/permissions")
@login_required
async def list_permissions(request: web.Request) -> web.Response:
    items = await visible_permissions(request)
    return json_response({"items": [serialize_permission(item) for item in items]})


@routes.post("/api/permissions/{request_id}/reply")
@login_required
async def reply(request: web.Request) -> web.Response:
    request_id = request.match_info["request_id"]
    if not ID_RE.match(request_id):
        raise ApiError(404, "Запрос прав не найден")
    body = await read_model(request, ReplyBody)
    match = next((p for p in await visible_permissions(request) if p.id == request_id), None)
    if match is None:
        raise ApiError(404, "Запрос прав не найден или уже решен")
    await request.app[CLIENT].reply_permission(match.session_id, match.id, body.decision)
    log.info(
        "permission %s answered %s by user %s", match.id, body.decision, user_id(request)
    )
    return json_response({"ok": True, "decision": body.decision})
