"""Единый формат ошибок API: {"error": {"code": ..., "message": ...}}."""

from __future__ import annotations

import json
from typing import Any

from aiohttp import web
from pydantic import BaseModel, ValidationError

STATUS_CODES = {
    400: "validation",
    401: "unauthorized",
    403: "forbidden",
    404: "not_found",
    405: "validation",
    409: "conflict",
    413: "validation",
    415: "validation",
    422: "validation",
    503: "unavailable",
    502: "unavailable",
    504: "unavailable",
}

DEFAULT_MESSAGES = {
    400: "Некорректный запрос",
    401: "Требуется вход",
    403: "Доступ запрещен",
    404: "Не найдено",
    405: "Метод не поддерживается",
    409: "Конфликт",
    413: "Слишком большой запрос",
    500: "Внутренняя ошибка",
    503: "Сервис недоступен",
}


class ApiError(Exception):
    """Ошибка, которую middleware превращает в JSON-ответ."""

    def __init__(
        self,
        status: int,
        message: str | None = None,
        *,
        code: str | None = None,
        **extra: Any,
    ) -> None:
        super().__init__(message or DEFAULT_MESSAGES.get(status, ""))
        self.status = status
        self.code = code or code_for_status(status)
        self.message = message or DEFAULT_MESSAGES.get(status, "Ошибка")
        self.extra = extra


def dumps(value: Any) -> str:
    """JSON без экранирования кириллицы."""
    return json.dumps(value, ensure_ascii=False)


def json_response(data: Any, *, status: int = 200) -> web.Response:
    return web.json_response(data, status=status, dumps=dumps)


def code_for_status(status: int) -> str:
    return STATUS_CODES.get(status, "internal")


def error_response(
    status: int, code: str, message: str, **extra: Any
) -> web.Response:
    payload: dict[str, Any] = {"code": code, "message": message}
    payload.update(extra)
    return json_response({"error": payload}, status=status)


def unauthorized(message: str = "Требуется вход") -> ApiError:
    return ApiError(401, message)


def forbidden(message: str = "Доступ запрещен") -> ApiError:
    return ApiError(403, message)


def not_found(message: str = "Не найдено") -> ApiError:
    return ApiError(404, message)


def unavailable(message: str = "Сервер OpenCode недоступен") -> ApiError:
    return ApiError(503, message)


def validation(message: str = "Некорректный запрос") -> ApiError:
    return ApiError(400, message)


def validation_message(exc: ValidationError) -> str:
    """Короткое описание ошибки схемы без значений полей."""
    parts = []
    for item in exc.errors()[:3]:
        location = ".".join(str(piece) for piece in item.get("loc", ())) or "body"
        parts.append(f"{location}: {item.get('msg', 'invalid')}")
    return "; ".join(parts) or "Некорректный запрос"


async def read_model[T: BaseModel](request: web.Request, model: type[T]) -> T:
    """Разобрать JSON-тело запроса по схеме; ошибки превращаются в 400."""
    raw = await request.read()
    if not raw.strip():
        payload: Any = {}
    else:
        try:
            payload = json.loads(raw)
        except ValueError as exc:
            raise validation("Тело запроса должно быть JSON") from exc
    if not isinstance(payload, dict):
        raise validation("Тело запроса должно быть JSON-объектом")
    try:
        return model.model_validate(payload)
    except ValidationError as exc:
        raise validation(validation_message(exc)) from exc
