"""Запросы прав."""

from __future__ import annotations

from conftest import OWNER_ID
from fakes import make_session, permission


async def test_list_only_visible(panel, opencode, bot_store) -> None:
    client, headers = panel
    opencode.add(make_session("mine"))
    opencode.add(make_session("child", parent_id="mine"))
    opencode.add(make_session("other"))
    await bot_store.subscribe(OWNER_ID, "mine")
    opencode.permissions = [
        permission("r1", "mine"),
        permission("r2", "child"),
        permission("r3", "other"),
    ]
    response = await client.get("/api/permissions", headers=headers)
    assert response.status == 200
    items = (await response.json())["items"]
    assert [p["id"] for p in items] == ["r1", "r2"]
    assert items[0]["action"] == "shell"
    assert items[0]["resources"] == ["ls -la"]


async def test_notify_all_sees_everything(panel, opencode, bot_store) -> None:
    client, headers = panel
    opencode.add(make_session("other"))
    opencode.permissions = [permission("r3", "other")]
    await bot_store.set_notify_all(OWNER_ID, True)
    items = (await (await client.get("/api/permissions", headers=headers)).json())["items"]
    assert [p["id"] for p in items] == ["r3"]


async def test_addressed_by_bot_visible(panel, opencode, bot_store) -> None:
    client, headers = panel
    opencode.add(make_session("other"))
    opencode.permissions = [permission("r3", "other")]
    await bot_store.set_permission_message("r3", OWNER_ID, 555, 1000, session_id="other")
    items = (await (await client.get("/api/permissions", headers=headers)).json())["items"]
    assert [p["id"] for p in items] == ["r3"]


async def test_reply_and_repeat_404(panel, opencode, bot_store) -> None:
    client, headers = panel
    opencode.add(make_session("mine"))
    await bot_store.subscribe(OWNER_ID, "mine")
    opencode.permissions = [permission("r1", "mine")]

    response = await client.post(
        "/api/permissions/r1/reply", json={"decision": "once"}, headers=headers
    )
    assert response.status == 200
    assert opencode.replies == [("mine", "r1", "once")]

    response = await client.post(
        "/api/permissions/r1/reply", json={"decision": "once"}, headers=headers
    )
    assert response.status == 404


async def test_reply_foreign_session_404(panel, opencode) -> None:
    client, headers = panel
    opencode.add(make_session("other"))
    opencode.permissions = [permission("r3", "other")]
    response = await client.post(
        "/api/permissions/r3/reply", json={"decision": "always"}, headers=headers
    )
    assert response.status == 404
    assert opencode.replies == []


async def test_reply_validation(panel, opencode, bot_store) -> None:
    client, headers = panel
    response = await client.post(
        "/api/permissions/r1/reply", json={"decision": "yes"}, headers=headers
    )
    assert response.status == 400


async def test_bot_rows_untouched(panel, opencode, bot_store) -> None:
    client, headers = panel
    opencode.add(make_session("mine"))
    await bot_store.subscribe(OWNER_ID, "mine")
    opencode.permissions = [permission("r1", "mine")]
    await bot_store.set_permission_message("r1", OWNER_ID, 10, 1000, session_id="mine")
    await client.post("/api/permissions/r1/reply", json={"decision": "reject"}, headers=headers)
    assert await bot_store.get_permission_message("r1") is not None


async def test_unavailable_503(panel, opencode) -> None:
    client, headers = panel
    opencode.unavailable = True
    assert (await client.get("/api/permissions", headers=headers)).status == 503
