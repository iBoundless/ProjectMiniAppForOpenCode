"""Статус и перезапуск сервиса OpenCode (не хоста)."""

from __future__ import annotations

import asyncio
import logging

from aiohttp import web
from pydantic import BaseModel

from ..auth import login_required, user_id
from ..errors import ApiError, json_response, read_model, validation
from ..keys import RESTART_LOCK, SERVICE

log = logging.getLogger(__name__)
routes = web.RouteTableDef()

class RestartBody(BaseModel):
    confirm: bool = False


def restart_lock(app: web.Application) -> asyncio.Lock:
    return app[RESTART_LOCK]


@routes.get("/api/service/status")
@login_required
async def status(request: web.Request) -> web.Response:
    current = await request.app[SERVICE].status()
    return json_response(
        {
            "running": current.running,
            "version": current.version,
            "url": current.url,
            "busy_count": current.busy_count,
            "restarting": restart_lock(request.app).locked(),
        }
    )


@routes.post("/api/service/restart")
@login_required
async def restart(request: web.Request) -> web.Response:
    body = await read_model(request, RestartBody)
    if not body.confirm:
        raise validation("Перезапуск требует подтверждения: confirm=true")
    lock = restart_lock(request.app)
    if lock.locked():
        raise ApiError(409, "Перезапуск уже идет")
    async with lock:
        service = request.app[SERVICE]
        before = await service.status()
        log.info(
            "opencode restart requested by user %s, busy=%s",
            user_id(request),
            before.busy_count,
        )
        if not await service.restart():
            raise ApiError(
                503, "OpenCode не поднялся после перезапуска", busy_count=before.busy_count
            )
    return json_response({"restarted": True, "busy_count": before.busy_count})
