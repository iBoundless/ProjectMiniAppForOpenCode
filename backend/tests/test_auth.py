"""Авторизация Telegram Mini App и серверные сессии."""

from __future__ import annotations

import time

import pytest

from conftest import BOT_TOKEN, OTHER_ID, OWNER_ID, cookie_header, login, make_init_data
from ocbot_web.auth import COOKIE_NAME, AuthError, validate_init_data
from ocbot_web.keys import AUTH


def test_valid_signature() -> None:
    user = validate_init_data(make_init_data(), BOT_TOKEN, 3600, allowed_ids=[OWNER_ID])
    assert user.id == OWNER_ID
    assert user.username == "tester"


@pytest.mark.parametrize(
    "init_data",
    [
        "",
        "user=%7B%7D&auth_date=1",
        make_init_data(tamper=True),
        make_init_data(bot_token="999:other"),
    ],
)
def test_invalid_init_data(init_data: str) -> None:
    with pytest.raises(AuthError) as info:
        validate_init_data(init_data, BOT_TOKEN, 3600)
    assert info.value.status == 401


def test_expired_auth_date() -> None:
    old = int(time.time()) - 7200
    with pytest.raises(AuthError) as info:
        validate_init_data(make_init_data(auth_date=old), BOT_TOKEN, 3600)
    assert info.value.status == 401


def test_foreign_user() -> None:
    with pytest.raises(AuthError) as info:
        validate_init_data(
            make_init_data(OTHER_ID), BOT_TOKEN, 3600, allowed_ids=[OWNER_ID]
        )
    assert info.value.status == 403


async def test_login_sets_http_only_cookie(api) -> None:
    client = await api()
    response = await client.post(
        "/api/auth/telegram", json={"init_data": make_init_data()}
    )
    assert response.status == 200
    assert (await response.json())["user"]["id"] == OWNER_ID
    raw = response.headers.getall("Set-Cookie")[0]
    assert raw.startswith(f"{COOKIE_NAME}=")
    lowered = raw.lower()
    assert "httponly" in lowered
    assert "secure" in lowered
    assert "samesite=lax" in lowered

    token = response.cookies[COOKIE_NAME].value
    me = await client.get("/api/auth/me", headers=cookie_header(token))
    assert me.status == 200
    assert (await me.json())["user"]["id"] == OWNER_ID
    # В базе только хеш.
    rows = await client.server.app[AUTH].dump("auth_sessions")
    assert all(token not in str(row) for row in rows)


async def test_login_bad_signature_401(api) -> None:
    client = await api()
    response = await client.post(
        "/api/auth/telegram", json={"init_data": make_init_data(tamper=True)}
    )
    assert response.status == 401
    assert (await response.json())["error"]["code"] == "unauthorized"


async def test_login_expired_401(api) -> None:
    client = await api()
    old = int(time.time()) - 200000
    response = await client.post(
        "/api/auth/telegram", json={"init_data": make_init_data(auth_date=old)}
    )
    assert response.status == 401


async def test_login_foreign_user_403(api) -> None:
    client = await api()
    response = await client.post(
        "/api/auth/telegram", json={"init_data": make_init_data(OTHER_ID)}
    )
    assert response.status == 403
    assert (await response.json())["error"]["code"] == "forbidden"


async def test_login_ignores_body_user_id(api) -> None:
    client = await api()
    response = await client.post(
        "/api/auth/telegram",
        json={"init_data": make_init_data(OTHER_ID), "user_id": OWNER_ID},
    )
    assert response.status == 403


async def test_login_validation_error(api) -> None:
    client = await api()
    response = await client.post("/api/auth/telegram", data=b"not json")
    assert response.status == 400
    response = await client.post("/api/auth/telegram", json={})
    assert response.status == 400


async def test_me_without_cookie_401(api) -> None:
    client = await api()
    response = await client.get("/api/auth/me")
    assert response.status == 401
    response = await client.get("/api/auth/me", headers=cookie_header("bogus"))
    assert response.status == 401


async def test_logout_deletes_session(api) -> None:
    client = await api()
    headers = await login(client)
    assert (await client.get("/api/auth/me", headers=headers)).status == 200
    response = await client.post("/api/auth/logout", headers=headers)
    assert response.status == 200
    assert (await client.get("/api/auth/me", headers=headers)).status == 401
    assert await client.server.app[AUTH].count("auth_sessions") == 0


async def test_session_expires(api, settings) -> None:
    client = await api()
    store = client.server.app[AUTH]
    token = await store.create_session({"id": OWNER_ID}, 1)
    store._now = lambda: time.time() + 10
    response = await client.get("/api/auth/me", headers=cookie_header(token))
    assert response.status == 401


async def test_removed_from_allowlist_403(api) -> None:
    client = await api()
    headers = await login(client, OTHER_ID)
    response = await client.get("/api/auth/me", headers=headers)
    assert response.status == 403


async def test_init_data_not_logged(api, caplog) -> None:
    caplog.set_level("DEBUG")
    client = await api()
    init_data = make_init_data(tamper=True)
    await client.post("/api/auth/telegram", json={"init_data": init_data})
    await client.post("/api/auth/telegram", json={"init_data": make_init_data()})
    assert "AAH-" not in caplog.text
    assert "hash=" not in caplog.text
