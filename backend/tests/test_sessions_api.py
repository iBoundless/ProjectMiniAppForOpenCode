"""API сессий."""

from __future__ import annotations

from pathlib import Path

from conftest import OWNER_ID
from fakes import make_session
from ocbot.permissions_profile import BOT_SESSION_PERMISSIONS


async def test_requires_auth(api, opencode, bot_store) -> None:
    client = await api(client=opencode, store=bot_store)
    assert (await client.get("/api/sessions")).status == 401
    assert (await client.post("/api/sessions", json={})).status == 401


async def test_list_and_pagination(panel, opencode, bot_store) -> None:
    client, headers = panel
    for index in range(5):
        opencode.add(make_session(f"s{index}", updated=1000 + index))
    opencode.add(make_session("busy1", busy=True, updated=500))
    opencode.add(make_session("child", parent_id="s1", updated=5000))
    await bot_store.subscribe(OWNER_ID, "s3")

    response = await client.get("/api/sessions?limit=2&page=1", headers=headers)
    assert response.status == 200
    body = await response.json()
    assert body["total"] == 6
    assert body["pages"] == 3
    assert body["busy_count"] == 1
    ids = [item["id"] for item in body["items"]]
    # Занятые первыми, дальше свежие.
    assert ids == ["busy1", "s4"]
    first = body["items"][0]
    assert first["status"] == "busy"
    assert first["project"]["title"] == "alpha"
    assert first["model"] == {"provider": "openai", "id": "gpt-x", "variant": "default"}

    page2 = await (await client.get("/api/sessions?limit=2&page=2", headers=headers)).json()
    assert [item["id"] for item in page2["items"]] == ["s3", "s2"]
    assert page2["items"][0]["subscribed"] is True
    assert page2["items"][1]["subscribed"] is False


async def test_list_limit_capped_and_filters(panel, opencode) -> None:
    client, headers = panel
    for index in range(60):
        opencode.add(make_session(f"s{index}", updated=1000 + index))
    opencode.add(make_session("run", busy=True, title="Running job"))
    body = await (await client.get("/api/sessions?limit=500", headers=headers)).json()
    assert body["limit"] == 50
    assert len(body["items"]) == 50

    busy = await (await client.get("/api/sessions?status=busy", headers=headers)).json()
    assert [item["id"] for item in busy["items"]] == ["run"]
    found = await (await client.get("/api/sessions?search=running", headers=headers)).json()
    assert [item["id"] for item in found["items"]] == ["run"]
    bad = await client.get("/api/sessions?page=x", headers=headers)
    assert bad.status == 400


async def test_get_session_card(panel, opencode) -> None:
    client, headers = panel
    opencode.add(make_session("s1", outcome="succeeded"))
    opencode.texts["s1"] = "Готово."
    response = await client.get("/api/sessions/s1", headers=headers)
    assert response.status == 200
    card = await response.json()
    assert card["id"] == "s1"
    assert card["status"] == "succeeded"
    assert card["last_text"] == "Готово."


async def test_missing_session_404(panel) -> None:
    client, headers = panel
    response = await client.get("/api/sessions/nope", headers=headers)
    assert response.status == 404
    assert (await response.json())["error"]["code"] == "not_found"
    response = await client.get("/api/sessions/bad%2F..", headers=headers)
    assert response.status == 404


async def test_opencode_unavailable_503(panel, opencode) -> None:
    client, headers = panel
    opencode.unavailable = True
    response = await client.get("/api/sessions", headers=headers)
    assert response.status == 503
    assert (await response.json())["error"]["code"] == "unavailable"


async def test_create_task(panel, opencode, bot_store, tmp_path: Path) -> None:
    client, headers = panel
    response = await client.post(
        "/api/sessions",
        json={
            "directory": str(tmp_path),
            "prompt": "Почини тесты\nподробнее",
            "model": {"provider": "anthropic", "id": "example-model"},
        },
        headers=headers,
    )
    assert response.status == 201
    body = await response.json()
    session_id = body["id"]
    assert body["subscribed"] is True
    created = opencode.created[0]
    assert created["directory"] == str(tmp_path)
    assert created["permissions"] == BOT_SESSION_PERMISSIONS
    assert created["model"].provider_id == "anthropic"
    assert created["title"] == "Почини тесты"
    assert opencode.prompts == [(session_id, "Почини тесты\nподробнее", "queue")]
    assert OWNER_ID in await bot_store.subscribers(session_id)
    assert (await bot_store.get_chat(OWNER_ID)).active_session == session_id


async def test_create_task_with_agent_and_default_model(
    panel, opencode, bot_store, tmp_path: Path
) -> None:
    client, headers = panel
    await bot_store.meta_set("default_model", "openai|gpt-y")
    response = await client.post(
        "/api/sessions",
        json={"directory": str(tmp_path), "prompt": "go", "agent": "plan"},
        headers=headers,
    )
    assert response.status == 201
    created = opencode.created[0]
    assert created["agent"] == "plan"
    assert created["model"].id == "gpt-y"
    assert created["permissions"] == BOT_SESSION_PERMISSIONS


async def test_create_task_validation(panel, opencode, tmp_path: Path) -> None:
    client, headers = panel
    for payload in (
        {"directory": "relative/path", "prompt": "x"},
        {"directory": str(tmp_path / "missing"), "prompt": "x"},
        {"directory": str(tmp_path), "prompt": "   "},
        {"directory": str(tmp_path)},
    ):
        response = await client.post("/api/sessions", json=payload, headers=headers)
        assert response.status == 400, payload
        assert (await response.json())["error"]["code"] == "validation"
    assert opencode.created == []


async def test_prompt_idle_session(panel, opencode) -> None:
    client, headers = panel
    opencode.add(make_session("s1"))
    response = await client.post(
        "/api/sessions/s1/prompt", json={"text": "еще"}, headers=headers
    )
    assert response.status == 200
    assert opencode.prompts == [("s1", "еще", "queue")]


async def test_prompt_busy_returns_draft(panel, opencode) -> None:
    client, headers = panel
    opencode.add(make_session("s1", busy=True))
    response = await client.post(
        "/api/sessions/s1/prompt", json={"text": "стоп, другое"}, headers=headers
    )
    assert response.status == 409
    error = (await response.json())["error"]
    assert error["code"] == "conflict"
    draft_id = error["draft_id"]
    assert opencode.prompts == []

    response = await client.post(
        "/api/sessions/s1/prompt",
        json={"draft_id": draft_id, "delivery": "steer"},
        headers=headers,
    )
    assert response.status == 200
    assert opencode.prompts == [("s1", "стоп, другое", "steer")]
    # Черновик одноразовый.
    again = await client.post(
        "/api/sessions/s1/prompt",
        json={"draft_id": draft_id, "delivery": "queue"},
        headers=headers,
    )
    assert again.status == 404


async def test_prompt_delivery_validation(panel, opencode) -> None:
    client, headers = panel
    opencode.add(make_session("s1", busy=True))
    bad = await client.post(
        "/api/sessions/s1/prompt",
        json={"text": "x", "delivery": "now"},
        headers=headers,
    )
    assert bad.status == 400
    ok = await client.post(
        "/api/sessions/s1/prompt",
        json={"text": "x", "delivery": "queue"},
        headers=headers,
    )
    assert ok.status == 200
    empty = await client.post("/api/sessions/s1/prompt", json={}, headers=headers)
    assert empty.status == 400


async def test_prompt_missing_session(panel) -> None:
    client, headers = panel
    response = await client.post(
        "/api/sessions/nope/prompt", json={"text": "x"}, headers=headers
    )
    assert response.status == 404


async def test_interrupt(panel, opencode) -> None:
    client, headers = panel
    opencode.add(make_session("s1", busy=True))
    response = await client.post("/api/sessions/s1/interrupt", headers=headers)
    assert response.status == 200
    assert await response.json() == {"interrupted": True}
    assert opencode.interrupted == ["s1"]


async def test_delete(panel, opencode, bot_store) -> None:
    client, headers = panel
    opencode.add(make_session("s1"))
    await bot_store.subscribe(OWNER_ID, "s1")
    await bot_store.set_active_session(OWNER_ID, "s1")

    unconfirmed = await client.delete("/api/sessions/s1", headers=headers)
    assert unconfirmed.status == 400
    assert opencode.deleted == []

    response = await client.delete("/api/sessions/s1?confirm=true", headers=headers)
    assert response.status == 200
    assert opencode.deleted == ["s1"]
    assert await bot_store.subscribers("s1") == []
    assert (await bot_store.get_chat(OWNER_ID)).active_session is None

    missing = await client.delete("/api/sessions/s1?confirm=true", headers=headers)
    assert missing.status == 404
