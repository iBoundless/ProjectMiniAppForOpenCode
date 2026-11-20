"""Справочники для формы новой задачи: проекты, модели, агенты."""

from __future__ import annotations

from typing import Any

from aiohttp import web
from ocbot.opencode.models import AgentInfo, ModelInfo, Project

from ..auth import login_required
from ..errors import json_response, validation
from ..keys import CLIENT

routes = web.RouteTableDef()


def directory_query(request: web.Request) -> str | None:
    value = (request.query.get("directory") or "").strip()
    if not value:
        return None
    if len(value) > 4096 or not value.startswith("/"):
        raise validation("directory: ожидается абсолютный путь")
    return value


def serialize_projects(projects: list[Project]) -> list[dict[str, Any]]:
    ordered = sorted(projects, key=lambda p: (-p.time.active, p.title.lower()))
    return [
        {"id": p.id, "canonical": p.canonical, "title": p.title, "active": p.time.active}
        for p in ordered
    ]


def serialize_models(models: list[ModelInfo]) -> list[dict[str, Any]]:
    """Одна запись на пару provider/model, по алфавиту."""
    seen: dict[tuple[str, str], dict[str, Any]] = {}
    for item in models:
        if not item.enabled:
            continue
        key = (item.provider_id, item.model_id)
        if key in seen:
            continue
        variants = [
            str(v.get("id") or v.get("name"))
            for v in item.variants
            if isinstance(v, dict) and (v.get("id") or v.get("name"))
        ]
        seen[key] = {
            "provider": item.provider_id,
            "model": item.model_id,
            "label": item.label,
            "variants": variants,
        }
    return sorted(
        seen.values(), key=lambda m: (m["provider"].lower(), m["label"].lower(), m["model"])
    )


def serialize_agents(agents: list[AgentInfo]) -> list[dict[str, Any]]:
    visible = [a for a in agents if not a.hidden]
    visible.sort(key=lambda a: a.label.lower())
    return [{"id": a.id, "label": a.label, "mode": a.mode} for a in visible]


@routes.get("/api/projects")
@login_required
async def projects(request: web.Request) -> web.Response:
    items = await request.app[CLIENT].list_projects()
    return json_response({"items": serialize_projects(items)})


@routes.get("/api/models")
@login_required
async def models(request: web.Request) -> web.Response:
    items = await request.app[CLIENT].list_models(directory_query(request))
    return json_response({"items": serialize_models(items)})


@routes.get("/api/agents")
@login_required
async def agents(request: web.Request) -> web.Response:
    items = await request.app[CLIENT].list_agents(directory_query(request))
    return json_response({"items": serialize_agents(items)})
