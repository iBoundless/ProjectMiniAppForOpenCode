"""Мелкие помощники для обработчиков."""

from __future__ import annotations

from aiohttp import web

LOCAL_ADDRESSES = {"127.0.0.1", "::1"}


def is_local_request(request: web.Request) -> bool:
    """Запрос с этой машины напрямую, а не через прокси и не из браузера."""
    if request.headers.get("Origin") or request.headers.get("X-Forwarded-For"):
        return False
    return request.remote in LOCAL_ADDRESSES
