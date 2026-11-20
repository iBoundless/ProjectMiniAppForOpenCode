"""Ключи зависимостей в web.Application."""

from __future__ import annotations

import asyncio
from typing import Any

from aiohttp import web

from .config import WebSettings

SETTINGS = web.AppKey("settings", WebSettings)
# Клиент OpenCode и хранилища типизированы как Any: в тестах подставляются
# фейки с тем же интерфейсом.
CLIENT = web.AppKey("client", Any)
STORE = web.AppKey("store", Any)
AUTH = web.AppKey("auth", Any)
SERVICE = web.AppKey("service", Any)
HUB = web.AppKey("hub", Any)
DRAFTS = web.AppKey("drafts", Any)
RESTART_LOCK = web.AppKey("restart_lock", asyncio.Lock)
HEARTBEAT = web.AppKey("heartbeat", float)

# Сессия авторизации текущего запроса (auth.AuthSession).
AUTH_SESSION = web.RequestKey("auth_session", Any)
