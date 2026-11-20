"""Общие фикстуры тестов backend."""

from __future__ import annotations

from pathlib import Path

import pytest

from ocbot_web.config import WebSettings

BOT_TOKEN = "123456:test-bot-token"
OWNER_ID = 42
OTHER_ID = 777


@pytest.fixture
def settings(tmp_path: Path) -> WebSettings:
    return WebSettings(
        telegram_bot_token=BOT_TOKEN,
        allowed_user_ids=[OWNER_ID, 43],
        opencode_password="opencode-secret",
        opencode_service_json=tmp_path / "service.json",
        ocbot_db_path=tmp_path / "bot.db",
        mini_app_db_path=tmp_path / "mini_app.db",
        mini_app_url="https://panel.example.com",
    )


def make_init_data(
    user_id: int = OWNER_ID,
    *,
    auth_date: int | None = None,
    bot_token: str = BOT_TOKEN,
    tamper: bool = False,
) -> str:
    """initData, подписанные как в Telegram."""
    import json
    import time
    from urllib.parse import urlencode

    from ocbot_web.auth import sign_init_data

    fields = {
        "auth_date": str(int(time.time()) if auth_date is None else auth_date),
        "query_id": "AAH-test",
        "user": json.dumps({"id": user_id, "first_name": "Test", "username": "tester"}),
    }
    fields["hash"] = sign_init_data(fields, bot_token)
    if tamper:
        fields["query_id"] = "AAH-other"
    return urlencode(fields)


def cookie_header(token: str) -> dict[str, str]:
    from ocbot_web.auth import COOKIE_NAME

    return {"Cookie": f"{COOKIE_NAME}={token}"}


@pytest.fixture
async def api(settings: WebSettings):
    """Фабрика тестового клиента: api(**deps) -> TestClient."""
    from aiohttp.test_utils import TestClient, TestServer

    from ocbot_web.app import create_app

    clients: list[TestClient] = []

    async def factory(**kwargs) -> TestClient:
        client = TestClient(TestServer(create_app(settings, **kwargs)))
        await client.start_server()
        clients.append(client)
        return client

    yield factory
    for client in clients:
        await client.close()


async def login(client, user_id: int = OWNER_ID) -> dict[str, str]:
    """Создать сессию напрямую и вернуть заголовок Cookie."""
    from ocbot_web.keys import AUTH, SETTINGS

    app = client.server.app
    token = await app[AUTH].create_session(
        {"id": user_id, "first_name": "Test"}, app[SETTINGS].session_ttl
    )
    return cookie_header(token)
