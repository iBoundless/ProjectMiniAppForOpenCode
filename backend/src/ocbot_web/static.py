"""Раздача собранного frontend (`frontend/dist`) с fallback на index.html."""

from __future__ import annotations

import logging
import mimetypes
from pathlib import Path

from aiohttp import web

from .errors import ApiError

log = logging.getLogger(__name__)

# src/ocbot_web/static.py -> корень репозитория.
DEFAULT_STATIC_DIR = Path(__file__).resolve().parents[3] / "frontend" / "dist"
IMMUTABLE = "public, max-age=31536000, immutable"
NO_CACHE = "no-cache"
# Пути backend: статика их не подменяет даже при отсутствии маршрута.
RESERVED = ("/api/", "/api", "/login", "/health")
SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "same-origin",
}

mimetypes.add_type("application/manifest+json", ".webmanifest")
mimetypes.add_type("text/javascript", ".js")


def resolve_file(root: Path, path: str) -> Path | None:
    """Файл внутри root или None (в том числе при попытке выйти за root)."""
    relative = path.lstrip("/")
    if not relative:
        return None
    try:
        candidate = (root / relative).resolve()
    except (OSError, ValueError):
        return None
    if not candidate.is_relative_to(root) or not candidate.is_file():
        return None
    return candidate


def cache_control(root: Path, file: Path) -> str:
    if file.parent == root / "assets" or file.parent.parent == root / "assets":
        return IMMUTABLE
    if file.parent == root / "icons":
        return "public, max-age=86400"
    # index.html, sw.js, manifest: всегда проверять новую версию.
    return NO_CACHE


def file_response(root: Path, file: Path) -> web.FileResponse:
    headers = {"Cache-Control": cache_control(root, file), **SECURITY_HEADERS}
    if file.name == "sw.js":
        headers["Service-Worker-Allowed"] = "/"
    return web.FileResponse(file, headers=headers)


def setup_static(app: web.Application, static_dir: Path | None) -> None:
    root = (static_dir or DEFAULT_STATIC_DIR).resolve()

    async def handler(request: web.Request) -> web.StreamResponse:
        path = request.path
        if path == "/api" or path.startswith(RESERVED):
            raise ApiError(404)
        file = resolve_file(root, path)
        if file is not None:
            return file_response(root, file)
        if path.startswith("/assets/") or path.startswith("/icons/"):
            raise ApiError(404, "Файл не найден")
        index = root / "index.html"
        if not index.is_file():
            raise ApiError(404, "Frontend не собран: выполните scripts/build.sh")
        return file_response(root, index)

    if not (root / "index.html").is_file():
        log.warning("frontend build not found, only API is served")
    app.router.add_get("/{tail:.*}", handler, name="static")
