"""Настройки backend из окружения."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from ocbot_web.config import WebSettings, read_service_password

BASE_ENV = {
    "TELEGRAM_BOT_TOKEN": "123:secret-token",
    "ALLOWED_USER_IDS": "42",
}


def _env(tmp_path: Path, **extra: str) -> dict[str, str]:
    env = dict(BASE_ENV)
    env["OPENCODE_SERVICE_JSON"] = str(tmp_path / "missing.json")
    env.update(extra)
    return env


def test_defaults(tmp_path: Path) -> None:
    settings = WebSettings.from_env(_env(tmp_path))
    assert settings.allowed_user_ids == [42]
    assert settings.opencode_url == "http://127.0.0.1:49374"
    assert settings.opencode_password == ""
    assert settings.mini_app_host == "127.0.0.1"
    assert settings.mini_app_port == 8080
    assert settings.mini_app_url == ""
    assert settings.init_data_max_age == 86400
    assert settings.session_ttl == 86400
    assert settings.mini_app_db_path.name == "mini_app.db"
    assert settings.allowed_origins == set()


def test_env_overrides(tmp_path: Path) -> None:
    settings = WebSettings.from_env(
        _env(
            tmp_path,
            ALLOWED_USER_IDS="1, 2;3",
            OPENCODE_URL="http://localhost:5000/",
            OPENCODE_PASSWORD="pw",
            OCBOT_DB_PATH=str(tmp_path / "bot.db"),
            MINI_APP_DB_PATH=str(tmp_path / "web.db"),
            MINI_APP_HOST="0.0.0.0",
            MINI_APP_PORT="9090",
            MINI_APP_URL="https://panel.example.com/",
            MINI_APP_INIT_DATA_MAX_AGE="60",
            MINI_APP_SESSION_TTL="120",
        )
    )
    assert settings.allowed_user_ids == [1, 2, 3]
    assert settings.opencode_url == "http://localhost:5000"
    assert settings.opencode_password == "pw"
    assert settings.ocbot_db_path == tmp_path / "bot.db"
    assert settings.mini_app_db_path == tmp_path / "web.db"
    assert settings.mini_app_host == "0.0.0.0"
    assert settings.mini_app_port == 9090
    assert settings.mini_app_url == "https://panel.example.com"
    assert settings.allowed_origins == {"https://panel.example.com"}
    assert settings.init_data_max_age == 60
    assert settings.session_ttl == 120


def test_password_from_service_json(tmp_path: Path) -> None:
    service = tmp_path / "service.json"
    service.write_text(json.dumps({"password": "from-file"}))
    settings = WebSettings.from_env(
        _env(tmp_path, OPENCODE_SERVICE_JSON=str(service))
    )
    assert settings.opencode_password == "from-file"


def test_env_password_wins(tmp_path: Path) -> None:
    service = tmp_path / "service.json"
    service.write_text(json.dumps({"password": "from-file"}))
    settings = WebSettings.from_env(
        _env(tmp_path, OPENCODE_SERVICE_JSON=str(service), OPENCODE_PASSWORD="env")
    )
    assert settings.opencode_password == "env"


def test_broken_service_json(tmp_path: Path) -> None:
    service = tmp_path / "service.json"
    service.write_text("not json")
    assert read_service_password(service) == ""
    service.write_text("[1, 2]")
    assert read_service_password(service) == ""


def test_empty_allowlist_rejected(tmp_path: Path) -> None:
    with pytest.raises(ValidationError):
        WebSettings.from_env(_env(tmp_path, ALLOWED_USER_IDS=""))


def test_missing_token_rejected(tmp_path: Path) -> None:
    env = _env(tmp_path)
    env["TELEGRAM_BOT_TOKEN"] = ""
    with pytest.raises(ValidationError):
        WebSettings.from_env(env)


@pytest.mark.parametrize(
    "name", ["MINI_APP_SESSION_TTL", "MINI_APP_INIT_DATA_MAX_AGE"]
)
@pytest.mark.parametrize("value", ["-1", "0"])
def test_non_positive_ttl_rejected(tmp_path: Path, name: str, value: str) -> None:
    with pytest.raises(ValidationError):
        WebSettings.from_env(_env(tmp_path, **{name: value}))


@pytest.mark.parametrize("port", ["0", "65536"])
def test_port_range(tmp_path: Path, port: str) -> None:
    with pytest.raises(ValidationError):
        WebSettings.from_env(_env(tmp_path, MINI_APP_PORT=port))


def test_remote_opencode_rejected(tmp_path: Path) -> None:
    with pytest.raises(ValidationError):
        WebSettings.from_env(_env(tmp_path, OPENCODE_URL="http://192.0.2.5:49374"))


def test_secrets_not_in_repr(tmp_path: Path) -> None:
    settings = WebSettings.from_env(_env(tmp_path, OPENCODE_PASSWORD="pw-secret"))
    text = repr(settings) + str(settings)
    assert "secret-token" not in text
    assert "pw-secret" not in text
