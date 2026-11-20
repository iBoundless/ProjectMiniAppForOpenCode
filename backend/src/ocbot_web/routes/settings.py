"""Подписки на сессии и настройки уведомлений (общие строки с ботом)."""

from __future__ import annotations

from aiohttp import web
from pydantic import BaseModel

from ..auth import login_required, user_id
from ..errors import json_response, read_model
from ..keys import CLIENT, STORE
from ..sessions import user_subscriptions
from .sessions import session_id_param

routes = web.RouteTableDef()


class NotificationSettings(BaseModel):
    notify_all: bool


@routes.post("/api/sessions/{session_id}/subscribe")
@login_required
async def subscribe(request: web.Request) -> web.Response:
    session_id = session_id_param(request)
    await request.app[CLIENT].get_session(session_id)
    await request.app[STORE].subscribe(user_id(request), session_id)
    return json_response({"subscribed": True})


@routes.delete("/api/sessions/{session_id}/subscribe")
@login_required
async def unsubscribe(request: web.Request) -> web.Response:
    session_id = session_id_param(request)
    await request.app[STORE].unsubscribe(user_id(request), session_id)
    return json_response({"subscribed": False})


async def notifications_payload(request: web.Request) -> dict[str, object]:
    store = request.app[STORE]
    uid = user_id(request)
    chat = await store.get_chat(uid)
    return {
        "notify_all": chat.notify_all,
        "subscribed_sessions": await user_subscriptions(store, uid),
    }


@routes.get("/api/settings/notifications")
@login_required
async def get_notifications(request: web.Request) -> web.Response:
    return json_response(await notifications_payload(request))


@routes.post("/api/settings/notifications")
@login_required
async def set_notifications(request: web.Request) -> web.Response:
    body = await read_model(request, NotificationSettings)
    await request.app[STORE].set_notify_all(user_id(request), body.notify_all)
    return json_response(await notifications_payload(request))
