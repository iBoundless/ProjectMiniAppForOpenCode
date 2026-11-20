"""Фейковый OpenCode-клиент с интерфейсом ocbot.opencode.client.OpencodeClient."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from typing import Any

from ocbot.opencode import ApiError, OpencodeUnavailable, SessionNotFound
from ocbot.opencode.events import Event
from ocbot.opencode.models import (
    AgentInfo,
    ModelInfo,
    ModelRef,
    PermissionRequest,
    Project,
    Rule,
    SessionInfo,
)


def make_session(
    session_id: str,
    *,
    title: str = "",
    busy: bool = False,
    parent_id: str | None = None,
    project_id: str | None = "p1",
    directory: str = "/work/alpha",
    updated: int = 1000,
    outcome: str | None = None,
    cost: float = 0.0,
) -> SessionInfo:
    return SessionInfo.model_validate(
        {
            "id": session_id,
            "parentID": parent_id,
            "title": title or f"Session {session_id}",
            "agent": "build",
            "model": {"id": "gpt-x", "providerID": "openai"},
            "projectID": project_id,
            "cost": cost,
            "outcome": outcome,
            "time": {
                "created": updated - 10,
                "updated": updated,
                "busy": updated if busy else updated - 5,
                "idle": None if busy else updated,
            },
            "location": {"directory": directory},
        }
    )


class FakeOpencode:
    def __init__(self) -> None:
        self.sessions: dict[str, SessionInfo] = {}
        self.projects: list[Project] = [
            Project.model_validate(
                {"id": "p1", "canonical": "/work/alpha", "time": {"active": 10}}
            ),
            Project.model_validate(
                {"id": "p2", "canonical": "/work/beta", "name": "Beta", "time": {"active": 30}}
            ),
            Project.model_validate(
                {"id": "p3", "canonical": "/work/gamma", "time": {"active": 20}}
            ),
        ]
        self.models: list[ModelInfo] = []
        self.agents: list[AgentInfo] = []
        self.permissions: list[PermissionRequest] = []
        self.texts: dict[str, str] = {}
        self.prompts: list[tuple[str, str, str]] = []
        self.created: list[dict[str, Any]] = []
        self.deleted: list[str] = []
        self.interrupted: list[str] = []
        self.replies: list[tuple[str, str, str]] = []
        self.unavailable = False
        self.version = "1.2.3"
        self.event_queue: asyncio.Queue[Event | None] = asyncio.Queue()
        self.event_connects = 0
        self._counter = 0

    def _check(self) -> None:
        if self.unavailable:
            raise OpencodeUnavailable("connection refused")

    def add(self, session: SessionInfo) -> SessionInfo:
        self.sessions[session.id] = session
        return session

    async def aclose(self) -> None:
        return None

    async def info(self) -> dict[str, Any]:
        self._check()
        return {"version": self.version}

    async def list_sessions(
        self,
        limit: int = 50,
        search: str | None = None,
        roots_only: bool = True,
        directory: str | None = None,
    ) -> list[SessionInfo]:
        self._check()
        items = list(self.sessions.values())
        if roots_only:
            items = [s for s in items if not s.parent_id]
        if search:
            items = [s for s in items if search.lower() in s.title.lower()]
        items.sort(key=lambda s: -s.time.updated)
        return items[:limit]

    async def get_session(self, session_id: str) -> SessionInfo:
        self._check()
        if session_id not in self.sessions:
            raise SessionNotFound(session_id)
        return self.sessions[session_id]

    async def create_session(
        self,
        directory: str,
        model: ModelRef | None = None,
        agent: str | None = None,
        permissions: list[Rule] | None = None,
        title: str | None = None,
    ) -> SessionInfo:
        self._check()
        self._counter += 1
        session_id = f"new{self._counter}"
        self.created.append(
            {
                "directory": directory,
                "model": model,
                "agent": agent,
                "permissions": permissions,
                "title": title,
            }
        )
        session = make_session(session_id, title=title or "", directory=directory)
        return self.add(session)

    async def prompt(self, session_id: str, text: str, delivery: str = "queue") -> None:
        self._check()
        if session_id not in self.sessions:
            raise SessionNotFound(session_id)
        self.prompts.append((session_id, text, delivery))

    async def interrupt(self, session_id: str) -> bool:
        self._check()
        if session_id not in self.sessions:
            raise SessionNotFound(session_id)
        self.interrupted.append(session_id)
        return True

    async def delete_session(self, session_id: str) -> None:
        self._check()
        if session_id not in self.sessions:
            raise SessionNotFound(session_id)
        del self.sessions[session_id]
        self.deleted.append(session_id)

    async def list_projects(self) -> list[Project]:
        self._check()
        return list(self.projects)

    async def list_models(self, directory: str | None = None) -> list[ModelInfo]:
        self._check()
        return list(self.models)

    async def list_agents(self, directory: str | None = None) -> list[AgentInfo]:
        self._check()
        return list(self.agents)

    async def list_permissions(self) -> list[PermissionRequest]:
        self._check()
        return list(self.permissions)

    async def reply_permission(self, session_id: str, request_id: str, decision: str) -> None:
        self._check()
        pending = [p for p in self.permissions if p.id == request_id]
        if not pending:
            raise ApiError(404, "not found")
        self.permissions = [p for p in self.permissions if p.id != request_id]
        self.replies.append((session_id, request_id, decision))

    async def last_assistant_text(self, session_id: str) -> str | None:
        self._check()
        return self.texts.get(session_id)

    async def events(self) -> AsyncIterator[Event]:
        self.event_connects += 1
        while True:
            event = await self.event_queue.get()
            if event is None:
                return
            yield event


def permission(request_id: str, session_id: str, action: str = "shell") -> PermissionRequest:
    return PermissionRequest.model_validate(
        {
            "id": request_id,
            "sessionID": session_id,
            "action": action,
            "resources": ["ls -la"],
            "message": "run ls",
        }
    )


class FakeService:
    """Интерфейс ocbot.opencode.service.ServiceController."""

    def __init__(self, opencode: FakeOpencode) -> None:
        self.opencode = opencode
        self.restarts = 0
        self.restart_ok = True
        self.url = "http://127.0.0.1:49374"

    async def status(self):
        from ocbot.opencode.service import ServiceStatus

        try:
            info = await self.opencode.info()
        except OpencodeUnavailable:
            return ServiceStatus(url=self.url, running=False)
        busy = sum(1 for s in self.opencode.sessions.values() if s.time.is_busy())
        return ServiceStatus(
            url=self.url, running=True, version=info["version"], busy_count=busy
        )

    async def restart(self) -> bool:
        self.restarts += 1
        return self.restart_ok
