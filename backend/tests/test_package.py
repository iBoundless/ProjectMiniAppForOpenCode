"""Проверка зависимости от пакета ocbot."""

import ocbot_web


def test_version() -> None:
    assert ocbot_web.__version__ == "0.1.0"


def test_ocbot_modules_importable() -> None:
    from ocbot.config import Settings
    from ocbot.opencode.client import OpencodeClient
    from ocbot.permissions_profile import BOT_SESSION_PERMISSIONS
    from ocbot.store import Store
    from ocbot.taskflow import create_bot_session

    assert Settings is not None
    assert OpencodeClient is not None
    assert Store is not None
    assert callable(create_bot_session)
    assert BOT_SESSION_PERMISSIONS
