"""Подписки и настройки уведомлений."""

from __future__ import annotations

from conftest import OWNER_ID
from fakes import make_session


async def test_subscribe_and_unsubscribe(panel, opencode, bot_store) -> None:
    client, headers = panel
    opencode.add(make_session("s1"))

    response = await client.post("/api/sessions/s1/subscribe", headers=headers)
    assert response.status == 200
    assert await response.json() == {"subscribed": True}
    assert OWNER_ID in await bot_store.subscribers("s1")

    card = await (await client.get("/api/sessions/s1", headers=headers)).json()
    assert card["subscribed"] is True

    response = await client.delete("/api/sessions/s1/subscribe", headers=headers)
    assert await response.json() == {"subscribed": False}
    assert OWNER_ID not in await bot_store.subscribers("s1")


async def test_subscribe_missing_session_404(panel) -> None:
    client, headers = panel
    response = await client.post("/api/sessions/nope/subscribe", headers=headers)
    assert response.status == 404


async def test_notifications_settings(panel, opencode, bot_store) -> None:
    client, headers = panel
    await bot_store.subscribe(OWNER_ID, "a")
    await bot_store.subscribe(OWNER_ID, "b")
    await bot_store.subscribe(43, "c")

    body = await (await client.get("/api/settings/notifications", headers=headers)).json()
    assert body == {"notify_all": False, "subscribed_sessions": ["a", "b"]}

    response = await client.post(
        "/api/settings/notifications", json={"notify_all": True}, headers=headers
    )
    assert response.status == 200
    assert (await response.json())["notify_all"] is True
    assert (await bot_store.get_chat(OWNER_ID)).notify_all is True
    assert OWNER_ID in await bot_store.chats_with_notify_all()


async def test_notifications_validation(panel) -> None:
    client, headers = panel
    response = await client.post(
        "/api/settings/notifications", json={"notify_all": "maybe"}, headers=headers
    )
    assert response.status == 400


async def test_requires_auth(api, opencode, bot_store) -> None:
    client = await api(client=opencode, store=bot_store)
    assert (await client.get("/api/settings/notifications")).status == 401
    assert (await client.post("/api/sessions/s1/subscribe")).status == 401
