"""Сборка aiohttp-приложения: middleware, зависимости, маршруты."""

from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import AsyncIterator, Awaitable, Callable
from typing import Any
from urllib.parse import urlsplit

from aiohttp import web
from ocbot.opencode import ApiError as OpencodeApiError
from ocbot.opencode import OpencodeUnavailable, SessionNotFound

from . import __version__
from .auth import AuthStore
from .config import WebSettings
from .errors import (
    DEFAULT_MESSAGES,
    ApiError,
    code_for_status,
    error_response,
    json_response,
)
from .keys import AUTH, SETTINGS
from .routes import setup_routes

log = logging.getLogger(__name__)

SERVICE_NAME = "opencode-miniapp"
MAX_BODY_BYTES = 64 * 1024
SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}

Handler = Callable[[web.Request], Awaitable[web.StreamResponse]]


@web.middleware
async def access_log_middleware(
    request: web.Request, handler: Handler
) -> web.StreamResponse:
    """Метод, путь без query string, статус и время. Тела и cookie не пишем."""
    started = time.monotonic()
    status = 500
    try:
        response = await handler(request)
        status = response.status
        return response
    except web.HTTPException as exc:
        status = exc.status
        raise
    finally:
        elapsed = (time.monotonic() - started) * 1000
        log.info("%s %s %s %.0fms", request.method, request.path, status, elapsed)


@web.middleware
async def error_middleware(
    request: web.Request, handler: Handler
) -> web.StreamResponse:
    try:
        return await handler(request)
    except ApiError as exc:
        return error_response(exc.status, exc.code, exc.message, **exc.extra)
    except web.HTTPException as exc:
        if exc.status < 400:
            raise
        message = DEFAULT_MESSAGES.get(exc.status, exc.reason)
        return error_response(exc.status, code_for_status(exc.status), message)
    except SessionNotFound:
        return error_response(404, "not_found", "Сессия не найдена")
    except OpencodeUnavailable:
        return error_response(503, "unavailable", "Сервер OpenCode недоступен")
    except OpencodeApiError as exc:
        if exc.status == 404:
            return error_response(404, "not_found", "Не найдено")
        log.warning("OpenCode API error %s", exc.status)
        return error_response(502, "unavailable", "Ошибка сервера OpenCode")
    except asyncio.CancelledError:
        raise
    except Exception:
        log.exception("unhandled error on %s %s", request.method, request.path)
        return error_response(500, "internal", "Внутренняя ошибка")


def body_limit_middleware(limit: int) -> Callable[..., Awaitable[web.StreamResponse]]:
    @web.middleware
    async def middleware(
        request: web.Request, handler: Handler
    ) -> web.StreamResponse:
        length = request.content_length
        if length is not None and length > limit:
            raise ApiError(413)
        return await handler(request)

    return middleware


def origin_allowed(request: web.Request, settings: WebSettings) -> bool:
    origin = request.headers.get("Origin")
    if origin is None:
        # Не браузер (curl, служебный вызов): защищает cookie SameSite.
        return True
    if origin in settings.allowed_origins:
        return True
    parts = urlsplit(origin)
    return bool(parts.scheme in ("http", "https") and parts.netloc == request.host)


@web.middleware
async def origin_middleware(
    request: web.Request, handler: Handler
) -> web.StreamResponse:
    """CSRF: изменяющие запросы только со своего Origin."""
    if request.method not in SAFE_METHODS:
        if not origin_allowed(request, request.app[SETTINGS]):
            raise ApiError(403, "Запрос с чужого источника")
    return await handler(request)


async def health(request: web.Request) -> web.Response:
    return json_response(
        {"status": "ok", "service": SERVICE_NAME, "version": __version__}
    )


def _resources(
    auth: Any | None,
) -> Callable[[web.Application], AsyncIterator[None]]:
    """Создать недостающие зависимости при старте и закрыть свои при остановке."""

    async def context(app: web.Application) -> AsyncIterator[None]:
        settings = app[SETTINGS]
        owned: list[Any] = []
        if auth is None:
            store = AuthStore(settings.mini_app_db_path)
            await store.init()
            owned.append(store)
            app[AUTH] = store
        try:
            yield
        finally:
            for item in reversed(owned):
                close = getattr(item, "close", None) or getattr(item, "aclose")
                await close()

    return context


def create_app(
    settings: WebSettings,
    *,
    auth: Any | None = None,
    max_body: int = MAX_BODY_BYTES,
) -> web.Application:
    app = web.Application(
        middlewares=[
            access_log_middleware,
            error_middleware,
            body_limit_middleware(max_body),
            origin_middleware,
        ],
        client_max_size=max_body,
    )
    app[SETTINGS] = settings
    if auth is not None:
        app[AUTH] = auth
    app.cleanup_ctx.append(_resources(auth))
    app.router.add_get("/health", health)
    app.router.add_get("/api/health", health)
    setup_routes(app)
    return app
