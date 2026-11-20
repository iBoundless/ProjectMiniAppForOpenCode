"""Одноразовые ссылки для входа из Safari (PWA)."""

from __future__ import annotations

import time

from conftest import OTHER_ID, OWNER_ID, cookie_header, login
from ocbot_web.auth import COOKIE_NAME
from ocbot_web.keys import AUTH

REMOTE = {"X-Forwarded-For": "203.0.113.5"}


async def test_token_is_one_time(api) -> None:
    client = await api()
    token = await client.server.app[AUTH].create_login_token(OWNER_ID)
    first = await client.get(f"/login?t={token}", allow_redirects=False)
    assert first.status == 302
    second = await client.get(f"/login?t={token}", allow_redirects=False)
    assert second.status == 401


async def test_redirect_and_cookie(api) -> None:
    client = await api()
    token = await client.server.app[AUTH].create_login_token(OWNER_ID)
    response = await client.get(f"/login?t={token}", allow_redirects=False)
    assert response.status == 302
    assert response.headers["Location"] == "/"
    assert "httponly" in response.headers["Set-Cookie"].lower()
    session = response.cookies[COOKIE_NAME].value
    me = await client.get("/api/auth/me", headers=cookie_header(session))
    assert (await me.json())["user"]["id"] == OWNER_ID


async def test_expired_token_rejected(api) -> None:
    client = await api()
    store = client.server.app[AUTH]
    token = await store.create_login_token(OWNER_ID, ttl=60)
    store._now = lambda: time.time() + 120
    response = await client.get(f"/login?t={token}", allow_redirects=False)
    assert response.status == 401


async def test_unknown_or_missing_token(api) -> None:
    client = await api()
    assert (await client.get("/login", allow_redirects=False)).status == 401
    assert (await client.get("/login?t=nope", allow_redirects=False)).status == 401


async def test_plain_token_not_stored(api) -> None:
    client = await api()
    store = client.server.app[AUTH]
    token = await store.create_login_token(OWNER_ID)
    rows = await store.dump("login_tokens")
    assert len(rows) == 1
    assert all(token not in str(value) for value in rows[0])


async def test_create_token_for_logged_in_user(api, settings) -> None:
    client = await api()
    headers = await login(client)
    response = await client.post("/api/auth/login-token", headers={**headers, **REMOTE})
    assert response.status == 200
    body = await response.json()
    assert body["url"] == f"{settings.mini_app_url}/login?t={body['token']}"
    redirect = await client.get(f"/login?t={body['token']}", allow_redirects=False)
    assert redirect.status == 302


async def test_create_token_requires_auth_when_remote(api) -> None:
    client = await api()
    response = await client.post("/api/auth/login-token", headers=REMOTE)
    assert response.status == 401
    response = await client.post(
        "/api/auth/login-token", json={"user_id": OWNER_ID}, headers=REMOTE
    )
    assert response.status == 401


async def test_local_service_call(api) -> None:
    client = await api()
    response = await client.post("/api/auth/login-token", json={"user_id": OWNER_ID})
    assert response.status == 200
    response = await client.post("/api/auth/login-token", json={"user_id": OTHER_ID})
    assert response.status == 403


async def test_user_cannot_mint_for_other(api) -> None:
    client = await api()
    headers = await login(client)
    response = await client.post(
        "/api/auth/login-token", json={"user_id": 43}, headers={**headers, **REMOTE}
    )
    assert response.status == 403


async def test_login_link_not_logged(api, caplog) -> None:
    caplog.set_level("DEBUG")
    client = await api()
    token = await client.server.app[AUTH].create_login_token(OWNER_ID)
    await client.get(f"/login?t={token}", allow_redirects=False)
    assert token not in caplog.text
