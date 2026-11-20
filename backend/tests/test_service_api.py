"""API сервиса OpenCode."""

from __future__ import annotations

import pytest
from fakes import FakeService, make_session

from conftest import login


@pytest.fixture
async def svc(api, opencode, bot_store):
    service = FakeService(opencode)
    client = await api(client=opencode, store=bot_store, service=service)
    return client, await login(client), service


async def test_status(svc, opencode) -> None:
    client, headers, _ = svc
    opencode.add(make_session("b", busy=True))
    opencode.add(make_session("i"))
    body = await (await client.get("/api/service/status", headers=headers)).json()
    assert body == {
        "running": True,
        "version": "1.2.3",
        "url": "http://127.0.0.1:49374",
        "busy_count": 1,
        "restarting": False,
    }


async def test_status_down(svc, opencode) -> None:
    client, headers, _ = svc
    opencode.unavailable = True
    body = await (await client.get("/api/service/status", headers=headers)).json()
    assert body["running"] is False


async def test_restart_requires_confirm(svc) -> None:
    client, headers, service = svc
    for payload in ({}, {"confirm": False}):
        response = await client.post("/api/service/restart", json=payload, headers=headers)
        assert response.status == 400
    assert service.restarts == 0


async def test_restart_with_confirm(svc, opencode) -> None:
    client, headers, service = svc
    opencode.add(make_session("b", busy=True))
    response = await client.post(
        "/api/service/restart", json={"confirm": True}, headers=headers
    )
    assert response.status == 200
    assert await response.json() == {"restarted": True, "busy_count": 1}
    assert service.restarts == 1


async def test_restart_timeout_503(svc) -> None:
    client, headers, service = svc
    service.restart_ok = False
    response = await client.post(
        "/api/service/restart", json={"confirm": True}, headers=headers
    )
    assert response.status == 503
    assert (await response.json())["error"]["code"] == "unavailable"


async def test_requires_auth(svc) -> None:
    client, _, _ = svc
    assert (await client.get("/api/service/status")).status == 401
    assert (await client.post("/api/service/restart", json={"confirm": True})).status == 401


async def test_default_service_controller(api, opencode, bot_store) -> None:
    from ocbot.opencode.service import ServiceController

    from ocbot_web.keys import SERVICE

    client = await api(client=opencode, store=bot_store)
    assert isinstance(client.server.app[SERVICE], ServiceController)
