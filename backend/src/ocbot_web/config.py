"""Настройки backend Mini App из переменных окружения."""

from __future__ import annotations

import json
import os
from collections.abc import Mapping
from pathlib import Path
from urllib.parse import urlsplit

from ocbot.config import DEFAULT_DB_PATH, DEFAULT_SERVICE_JSON, _default_bin
from pydantic import BaseModel, Field, field_validator

DEFAULT_OPENCODE_URL = "http://127.0.0.1:49374"
DEFAULT_MINI_APP_DB_PATH = DEFAULT_DB_PATH.parent / "mini_app.db"
LOCAL_HOSTS = {"127.0.0.1", "localhost", "::1"}


class WebSettings(BaseModel):
    """Секреты помечены repr=False: они не попадают в repr и логи."""

    telegram_bot_token: str = Field(min_length=1, repr=False)
    allowed_user_ids: list[int] = Field(min_length=1)
    opencode_url: str = DEFAULT_OPENCODE_URL
    opencode_password: str = Field(default="", repr=False)
    opencode_service_json: Path = DEFAULT_SERVICE_JSON
    opencode_bin: str = Field(default_factory=_default_bin)
    ocbot_db_path: Path = DEFAULT_DB_PATH
    mini_app_db_path: Path = DEFAULT_MINI_APP_DB_PATH
    mini_app_host: str = "127.0.0.1"
    mini_app_port: int = Field(default=8080, ge=1, le=65535)
    mini_app_url: str = ""
    init_data_max_age: int = Field(default=86400, gt=0)
    session_ttl: int = Field(default=86400, gt=0)
    static_dir: Path | None = None

    @field_validator("allowed_user_ids", mode="before")
    @classmethod
    def _parse_ids(cls, value: object) -> object:
        if isinstance(value, str):
            return [
                int(part)
                for part in value.replace(";", ",").split(",")
                if part.strip()
            ]
        return value

    @field_validator("opencode_url")
    @classmethod
    def _local_opencode(cls, value: str) -> str:
        host = urlsplit(value).hostname or ""
        if host not in LOCAL_HOSTS:
            raise ValueError("OpenCode должен быть локальным (127.0.0.1)")
        return value.rstrip("/")

    @field_validator("opencode_service_json", "ocbot_db_path", "mini_app_db_path", "static_dir")
    @classmethod
    def _expand(cls, value: Path | None) -> Path | None:
        return Path(value).expanduser() if value is not None else None

    @field_validator("mini_app_url")
    @classmethod
    def _strip_url(cls, value: str) -> str:
        return value.strip().rstrip("/")

    @property
    def allowed_origins(self) -> set[str]:
        """Origin публичного адреса панели, если он задан."""
        if not self.mini_app_url:
            return set()
        parts = urlsplit(self.mini_app_url)
        return {f"{parts.scheme}://{parts.netloc}"}

    @classmethod
    def from_env(cls, environ: Mapping[str, str] | None = None) -> WebSettings:
        env = os.environ if environ is None else environ
        service_json = Path(
            env.get("OPENCODE_SERVICE_JSON") or str(DEFAULT_SERVICE_JSON)
        ).expanduser()
        values: dict[str, object] = {
            "telegram_bot_token": env.get("TELEGRAM_BOT_TOKEN", ""),
            "allowed_user_ids": env.get("ALLOWED_USER_IDS", ""),
            "opencode_url": env.get("OPENCODE_URL") or DEFAULT_OPENCODE_URL,
            "opencode_password": env.get("OPENCODE_PASSWORD")
            or read_service_password(service_json),
            "opencode_service_json": service_json,
        }
        optional = {
            "opencode_bin": "OPENCODE_BIN",
            "ocbot_db_path": "OCBOT_DB_PATH",
            "mini_app_db_path": "MINI_APP_DB_PATH",
            "mini_app_host": "MINI_APP_HOST",
            "mini_app_port": "MINI_APP_PORT",
            "mini_app_url": "MINI_APP_URL",
            "init_data_max_age": "MINI_APP_INIT_DATA_MAX_AGE",
            "session_ttl": "MINI_APP_SESSION_TTL",
            "static_dir": "MINI_APP_STATIC_DIR",
        }
        for field, name in optional.items():
            raw = env.get(name)
            if raw:
                values[field] = raw
        return cls.model_validate(values)


def read_service_password(path: Path) -> str:
    """Пароль OpenCode из service.json; при любой ошибке пустая строка."""
    try:
        data = json.loads(path.read_text())
    except (OSError, ValueError):
        return ""
    if not isinstance(data, dict):
        return ""
    return str(data.get("password") or "")
