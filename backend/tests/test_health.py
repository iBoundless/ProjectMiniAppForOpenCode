"""Каркас приложения: /health и middleware."""

from __future__ import annotations

from aiohttp.test_utils import TestClient, TestServer

from ocbot_web.app import create_app
from ocbot_web.config import WebSettings


async def _client(settings: WebSettings, **kwargs) -> TestClient:
    client = TestClient(TestServer(create_app(settings, **kwargs)))
    await client.start_server()
    return client


async def test_health(settings: WebSettings) -> None:
    client = await _client(settings)
    try:
        response = await client.get("/health")
        assert response.status == 200
        assert response.content_type == "application/json"
        assert await response.json() == {
            "status": "ok",
            "service": "opencode-miniapp",
            "version": "0.1.0",
        }
    finally:
        await client.close()


async def test_unknown_route_404_json(settings: WebSettings) -> None:
    client = await _client(settings)
    try:
        response = await client.get("/api/nope")
        assert response.status == 404
        body = await response.json()
        assert body["error"]["code"] == "not_found"
        assert body["error"]["message"]
    finally:
        await client.close()


async def test_body_too_large_413(settings: WebSettings) -> None:
    client = await _client(settings, max_body=1024)
    try:
        response = await client.post("/health", data=b"x" * 4096)
        assert response.status == 413
        body = await response.json()
        assert body["error"]["code"] == "validation"
    finally:
        await client.close()


async def test_method_not_allowed_json(settings: WebSettings) -> None:
    client = await _client(settings)
    try:
        response = await client.post("/health", data=b"{}")
        assert response.status == 405
        assert (await response.json())["error"]["code"] == "validation"
    finally:
        await client.close()


async def test_foreign_origin_rejected(settings: WebSettings) -> None:
    client = await _client(settings)
    try:
        response = await client.post(
            "/health", data=b"{}", headers={"Origin": "https://evil.example"}
        )
        assert response.status == 403
        assert (await response.json())["error"]["code"] == "forbidden"
    finally:
        await client.close()


async def test_configured_origin_allowed(settings: WebSettings) -> None:
    client = await _client(settings)
    try:
        response = await client.post(
            "/health", data=b"{}", headers={"Origin": "https://panel.example.com"}
        )
        # Origin прошел, дальше роутер: метода POST у /health нет.
        assert response.status == 405
    finally:
        await client.close()


async def test_access_log_has_no_query(settings: WebSettings, caplog) -> None:
    client = await _client(settings)
    caplog.set_level("INFO", logger="ocbot_web.app")
    try:
        await client.get("/health?t=very-secret-token")
    finally:
        await client.close()
    assert "/health" in caplog.text
    assert "very-secret-token" not in caplog.text
