"""POST /api/auth/telegram, GET /api/auth/me, POST /api/auth/logout."""

from __future__ import annotations

import logging

from aiohttp import web
from pydantic import BaseModel, Field

from ..app_helpers import is_local_request

from ..auth import (
    COOKIE_NAME,
    LOGIN_TOKEN_TTL,
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


class LoginTokenRequest(BaseModel):
    # Только для служебного вызова с локального адреса (бот на этой машине).
    user_id: int | None = None


LOGIN_FAILED_PAGE = """<!doctype html>
<html lang="ru"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Ссылка недействительна</title></head>
<body style="font-family: -apple-system, sans-serif; padding: 2rem">
<h1>Ссылка недействительна</h1>
<p>Одноразовая ссылка уже использована или устарела.
Запросите новую в Telegram-боте.</p>
</body></html>
"""


@routes.post("/api/auth/login-token")
async def create_login_token(request: web.Request) -> web.Response:
    settings = request.app[SETTINGS]
    body = await read_model(request, LoginTokenRequest)
    if body.user_id is not None and is_local_request(request):
        target = body.user_id
        if target not in settings.allowed_user_ids:
            raise ApiError(403)
    else:
        session = await current_session(request)
        if body.user_id is not None and body.user_id != session.user_id:
            raise ApiError(403)
        target = session.user_id
    auth = request.app[AUTH]
    token = await auth.create_login_token(target, LOGIN_TOKEN_TTL)
    path = f"/login?t={token}"
    return json_response(
        {
            "token": token,
            "url": f"{settings.mini_app_url}{path}" if settings.mini_app_url else path,
            "expires_at": auth.now() + LOGIN_TOKEN_TTL,
        }
    )


@routes.get("/login")
async def login_by_token(request: web.Request) -> web.Response:
    settings = request.app[SETTINGS]
    auth = request.app[AUTH]
    user_id = await auth.consume_login_token(request.query.get("t"))
    if user_id is None or user_id not in settings.allowed_user_ids:
        log.warning("login link rejected")
        return web.Response(
            status=401, text=LOGIN_FAILED_PAGE, content_type="text/html"
        )
    token = await auth.create_session({"id": user_id}, settings.session_ttl)
    log.info("login link used by user %s", user_id)
    response = web.Response(
        status=302,
        headers={
            "Location": "/",
            "Cache-Control": "no-store",
            "Referrer-Policy": "no-referrer",
        },
    )
    set_session_cookie(response, token, settings.session_ttl)
    return response
