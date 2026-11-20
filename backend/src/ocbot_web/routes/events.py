"""GET /api/events: поток событий OpenCode для панели."""

from __future__ import annotations

import asyncio
import contextlib
import logging

from aiohttp import web

from ..auth import current_session, login_required, user_id
from ..errors import ApiError
from ..events import CLOSE
from ..keys import AUTH_SESSION, HEARTBEAT, HUB

log = logging.getLogger(__name__)
routes = web.RouteTableDef()


@routes.get("/api/events")
@login_required
async def events(request: web.Request) -> web.StreamResponse:
    hub = request.app[HUB]
    heartbeat = request.app[HEARTBEAT]
    response = web.StreamResponse(
        headers={
            "Content-Type": "text/event-stream; charset=utf-8",
            "Cache-Control": "no-cache, no-store",
            "X-Accel-Buffering": "no",
        }
    )
    await response.prepare(request)
    connection = hub.connect(user_id(request))
    try:
        await response.write(b"retry: 3000\n: connected\n\n")
        while True:
            try:
                chunk = await asyncio.wait_for(connection.queue.get(), heartbeat)
            except TimeoutError:
                # Сессию могли закрыть (logout) или убрать пользователя из allowlist.
                if AUTH_SESSION in request:
                    del request[AUTH_SESSION]
                try:
                    await current_session(request)
                except ApiError:
                    break
                chunk = ": ping\n\n"
            if chunk == CLOSE:
                break
            await response.write(chunk.encode())
    except ConnectionResetError:
        pass
    finally:
        hub.disconnect(connection)
    with contextlib.suppress(Exception):
        await response.write_eof()
    return response
