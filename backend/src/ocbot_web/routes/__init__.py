"""Маршруты API."""

from __future__ import annotations

from aiohttp import web

from . import auth, catalog, sessions


def setup_routes(app: web.Application) -> None:
    for module in (auth, sessions, catalog):
        app.router.add_routes(module.routes)
