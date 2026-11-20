"""Сквозная проверка: в логах нет initData, cookie, токенов и паролей."""

from __future__ import annotations

import asyncio

from conftest import BOT_TOKEN, make_init_data
from fakes import make_session, permission

from ocbot_web.auth import COOKIE_NAME


async def test_full_flow_logs_have_no_secrets(api, opencode, bot_store, tmp_path, caplog) -> None:
    caplog.set_level("DEBUG")
    client = await api(client=opencode, store=bot_store)
    init_data = make_init_data()
    response = await client.post("/api/auth/telegram", json={"init_data": init_data})
    assert response.status == 200
    cookie = response.cookies[COOKIE_NAME].value
    headers = {"Cookie": f"{COOKIE_NAME}={cookie}"}

    link = await (await client.post("/api/auth/login-token", headers=headers)).json()
    await client.get(f"/login?t={link['token']}", allow_redirects=False)

    opencode.add(make_session("s1"))
    await bot_store.subscribe(42, "s1")
    opencode.permissions = [permission("r1", "s1")]
    await client.get("/api/sessions", headers=headers)
    await client.post(
        "/api/sessions",
        json={"directory": str(tmp_path), "prompt": "secret prompt text"},
        headers=headers,
    )
    await client.post("/api/permissions/r1/reply", json={"decision": "once"}, headers=headers)
    stream = await client.get("/api/events", headers=headers)
    stream.close()
    await asyncio.sleep(0)
    await client.post("/api/auth/logout", headers=headers)

    text = caplog.text
    for secret in (
        cookie,
        link["token"],
        BOT_TOKEN,
        "opencode-secret",
        "hash=",
        "secret prompt text",
    ):
        assert secret not in text, secret
