"""Авторизация: подпись Telegram initData, серверные сессии, одноразовые ссылки."""

from __future__ import annotations

import functools
import hashlib
import hmac
import json
import secrets
import time
from collections.abc import Awaitable, Callable, Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import parse_qsl

import aiosqlite
from aiohttp import web
from pydantic import BaseModel, ConfigDict, ValidationError

from .errors import ApiError
from .keys import AUTH, AUTH_SESSION, SETTINGS

COOKIE_NAME = "oc_panel_session"
TOKEN_BYTES = 32
LOGIN_TOKEN_TTL = 300
# Допуск на расхождение часов клиента Telegram и сервера.
CLOCK_SKEW = 60

SCHEMA = """
CREATE TABLE IF NOT EXISTS auth_sessions (
    id_hash TEXT PRIMARY KEY,
    user_id INTEGER NOT NULL,
    user_json TEXT NOT NULL DEFAULT '{}',
    created_at INTEGER NOT NULL,
    expires_at INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS auth_sessions_expires ON auth_sessions(expires_at);
CREATE TABLE IF NOT EXISTS login_tokens (
    token_hash TEXT PRIMARY KEY,
    user_id INTEGER NOT NULL,
    created_at INTEGER NOT NULL,
    expires_at INTEGER NOT NULL,
    used_at INTEGER
);
"""


class AuthError(Exception):
    """Отказ в авторизации; status 401 или 403."""

    def __init__(self, status: int, message: str) -> None:
        super().__init__(message)
        self.status = status
        self.message = message


class TelegramUser(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: int
    first_name: str = ""
    last_name: str | None = None
    username: str | None = None
    language_code: str | None = None
    photo_url: str | None = None

    def public(self) -> dict[str, Any]:
        return self.model_dump(exclude_none=True)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def new_token() -> str:
    return secrets.token_urlsafe(TOKEN_BYTES)


def _secret_key(bot_token: str) -> bytes:
    return hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()


def sign_init_data(fields: dict[str, str], bot_token: str) -> str:
    """Подпись initData так, как ее считает Telegram. Нужна тестам и dev."""
    check = "\n".join(f"{key}={fields[key]}" for key in sorted(fields))
    return hmac.new(_secret_key(bot_token), check.encode(), hashlib.sha256).hexdigest()


def validate_init_data(
    init_data: str,
    bot_token: str,
    max_age: int,
    *,
    allowed_ids: Iterable[int] | None = None,
    now: float | None = None,
) -> TelegramUser:
    """Проверить подпись, срок и allowlist. Значения в ошибках не раскрываются."""
    if not init_data or len(init_data) > 8192:
        raise AuthError(401, "Нет данных авторизации Telegram")
    pairs = parse_qsl(init_data, keep_blank_values=True, strict_parsing=False)
    fields: dict[str, str] = {}
    for key, value in pairs:
        if key in fields:
            raise AuthError(401, "Некорректные данные авторизации")
        fields[key] = value

    received = fields.pop("hash", "")
    if not received or "auth_date" not in fields or "user" not in fields:
        raise AuthError(401, "Некорректные данные авторизации")
    # signature (Ed25519 для третьих сторон) входит в data_check_string.
    expected = sign_init_data(fields, bot_token)
    if not hmac.compare_digest(expected, received.lower()):
        raise AuthError(401, "Неверная подпись Telegram")

    try:
        auth_date = int(fields["auth_date"])
    except ValueError as exc:
        raise AuthError(401, "Некорректные данные авторизации") from exc
    current = time.time() if now is None else now
    if current - auth_date > max_age or auth_date - current > CLOCK_SKEW:
        raise AuthError(401, "Данные авторизации устарели, откройте панель заново")

    try:
        user = TelegramUser.model_validate(json.loads(fields["user"]))
    except (ValueError, ValidationError) as exc:
        raise AuthError(401, "Некорректные данные пользователя") from exc

    if allowed_ids is not None and user.id not in set(allowed_ids):
        raise AuthError(403, "Доступ запрещен")
    return user


@dataclass(slots=True)
class AuthSession:
    user_id: int
    user: dict[str, Any]
    created_at: int
    expires_at: int


class AuthStore:
    """Хранилище mini_app.db. В базе только SHA-256 хеши токенов."""

    def __init__(
        self, db_path: str | Path, *, now: Callable[[], float] | None = None
    ) -> None:
        self._db_path = Path(db_path)
        self._now = now or time.time
        self._conn: aiosqlite.Connection | None = None

    @property
    def _db(self) -> aiosqlite.Connection:
        if self._conn is None:
            raise RuntimeError("auth store is not initialized")
        return self._conn

    def now(self) -> int:
        return int(self._now())

    async def init(self) -> None:
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = await aiosqlite.connect(self._db_path)
        await self._conn.execute("PRAGMA journal_mode=WAL")
        await self._conn.executescript(SCHEMA)
        await self._conn.commit()
        try:
            self._db_path.chmod(0o600)
        except OSError:
            pass

    async def close(self) -> None:
        if self._conn is not None:
            await self._conn.close()
            self._conn = None

    async def create_session(self, user: dict[str, Any], ttl: int) -> str:
        token = new_token()
        now = self.now()
        await self._db.execute(
            "INSERT INTO auth_sessions(id_hash, user_id, user_json, created_at, expires_at)"
            " VALUES(?, ?, ?, ?, ?)",
            (hash_token(token), int(user["id"]), json.dumps(user), now, now + ttl),
        )
        await self._db.commit()
        await self.purge_expired()
        return token

    async def get_session(self, token: str | None) -> AuthSession | None:
        if not token or len(token) > 256:
            return None
        cursor = await self._db.execute(
            "SELECT user_id, user_json, created_at, expires_at FROM auth_sessions"
            " WHERE id_hash = ?",
            (hash_token(token),),
        )
        row = await cursor.fetchone()
        await cursor.close()
        if row is None:
            return None
        if row[3] <= self.now():
            await self.delete_session(token)
            return None
        try:
            user = json.loads(row[1])
        except ValueError:
            user = {"id": row[0]}
        return AuthSession(user_id=row[0], user=user, created_at=row[2], expires_at=row[3])

    async def delete_session(self, token: str) -> None:
        await self._db.execute(
            "DELETE FROM auth_sessions WHERE id_hash = ?", (hash_token(token),)
        )
        await self._db.commit()

    async def purge_expired(self) -> None:
        now = self.now()
        await self._db.execute("DELETE FROM auth_sessions WHERE expires_at <= ?", (now,))
        await self._db.execute("DELETE FROM login_tokens WHERE expires_at <= ?", (now,))
        await self._db.commit()

    async def create_login_token(self, user_id: int, ttl: int = LOGIN_TOKEN_TTL) -> str:
        """Одноразовый токен для входа из Safari: в базе только хеш."""
        token = new_token()
        now = self.now()
        await self._db.execute(
            "INSERT INTO login_tokens(token_hash, user_id, created_at, expires_at)"
            " VALUES(?, ?, ?, ?)",
            (hash_token(token), int(user_id), now, now + ttl),
        )
        await self._db.commit()
        return token

    async def consume_login_token(self, token: str | None) -> int | None:
        """Погасить токен и вернуть user_id; None, если токен неизвестен,
        просрочен или уже использован."""
        if not token or len(token) > 256:
            return None
        now = self.now()
        digest = hash_token(token)
        cursor = await self._db.execute(
            "UPDATE login_tokens SET used_at = ?"
            " WHERE token_hash = ? AND used_at IS NULL AND expires_at > ?",
            (now, digest, now),
        )
        changed = cursor.rowcount
        await cursor.close()
        await self._db.commit()
        if changed != 1:
            return None
        cursor = await self._db.execute(
            "SELECT user_id FROM login_tokens WHERE token_hash = ?", (digest,)
        )
        row = await cursor.fetchone()
        await cursor.close()
        return int(row[0]) if row else None

    async def count(self, table: str) -> int:
        if table not in ("auth_sessions", "login_tokens"):
            raise ValueError(table)
        cursor = await self._db.execute(f"SELECT COUNT(*) FROM {table}")
        row = await cursor.fetchone()
        await cursor.close()
        return int(row[0]) if row else 0

    async def dump(self, table: str) -> list[tuple[Any, ...]]:
        """Все строки таблицы. Для тестов: проверить, что открытых токенов нет."""
        if table not in ("auth_sessions", "login_tokens"):
            raise ValueError(table)
        cursor = await self._db.execute(f"SELECT * FROM {table}")
        rows = await cursor.fetchall()
        await cursor.close()
        return [tuple(row) for row in rows]


def set_session_cookie(response: web.StreamResponse, token: str, ttl: int) -> None:
    response.set_cookie(
        COOKIE_NAME,
        token,
        max_age=ttl,
        path="/",
        httponly=True,
        secure=True,
        samesite="Lax",
    )


def clear_session_cookie(response: web.StreamResponse) -> None:
    response.del_cookie(COOKIE_NAME, path="/", secure=True, httponly=True, samesite="Lax")


async def current_session(request: web.Request) -> AuthSession:
    """Сессия из cookie; 401 без нее, 403 если пользователя убрали из allowlist."""
    cached = request.get(AUTH_SESSION)
    if isinstance(cached, AuthSession):
        return cached
    auth: AuthStore = request.app[AUTH]
    token = request.cookies.get(COOKIE_NAME)
    session = await auth.get_session(token)
    if session is None:
        raise ApiError(401)
    if session.user_id not in request.app[SETTINGS].allowed_user_ids:
        if token:
            await auth.delete_session(token)
        raise ApiError(403)
    request[AUTH_SESSION] = session
    return session


def user_id(request: web.Request) -> int:
    session = request.get(AUTH_SESSION)
    if not isinstance(session, AuthSession):
        raise ApiError(401)
    return session.user_id


Handler = Callable[[web.Request], Awaitable[web.StreamResponse]]


def login_required(handler: Handler) -> Handler:
    @functools.wraps(handler)
    async def wrapper(request: web.Request) -> web.StreamResponse:
        await current_session(request)
        return await handler(request)

    return wrapper
