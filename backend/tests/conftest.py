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
