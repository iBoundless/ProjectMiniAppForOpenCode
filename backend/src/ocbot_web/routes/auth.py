"""POST /api/auth/telegram, GET /api/auth/me, POST /api/auth/logout."""

from __future__ import annotations

import logging

from aiohttp import web
from pydantic import BaseModel, Field

from ..auth import (
    COOKIE_NAME,
    AuthError,
    clear_session_cookie,
    current_session,
    login_required,
    set_session_cookie,
    validate_init_data,
)
from ..errors import ApiError, json_response, read_model
from ..keys import AUTH, SETTINGS

log = logging.getLogger(__name__)
routes = web.RouteTableDef()


class TelegramLogin(BaseModel):
    init_data: str = Field(min_length=1, max_length=8192)


@routes.post("/api/auth/telegram")
async def telegram_login(request: web.Request) -> web.Response:
    settings = request.app[SETTINGS]
    body = await read_model(request, TelegramLogin)
    try:
        user = validate_init_data(
            body.init_data,
            settings.telegram_bot_token,
            settings.init_data_max_age,
            allowed_ids=settings.allowed_user_ids,
        )
    except AuthError as exc:
        # Только причина; сами initData в лог не попадают.
        log.warning("telegram login rejected: %s", exc.status)
        raise ApiError(exc.status, exc.message) from exc
    token = await request.app[AUTH].create_session(user.public(), settings.session_ttl)
    log.info("telegram login for user %s", user.id)
    response = json_response({"user": user.public()})
    set_session_cookie(response, token, settings.session_ttl)
    return response


@routes.get("/api/auth/me")
@login_required
async def me(request: web.Request) -> web.Response:
    session = await current_session(request)
    return json_response({"user": session.user, "expires_at": session.expires_at})


@routes.post("/api/auth/logout")
async def logout(request: web.Request) -> web.Response:
    token = request.cookies.get(COOKIE_NAME)
    if token:
        await request.app[AUTH].delete_session(token)
    response = json_response({"ok": True})
    clear_session_cookie(response)
    return response
