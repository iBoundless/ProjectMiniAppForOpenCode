"""Раздача собранного frontend."""

from __future__ import annotations

from pathlib import Path

import pytest

from ocbot_web.config import WebSettings


@pytest.fixture
def dist(tmp_path: Path) -> Path:
    root = tmp_path / "dist"
    (root / "assets").mkdir(parents=True)
    (root / "icons").mkdir()
    (root / "index.html").write_text("<!doctype html><title>panel</title>")
    (root / "assets" / "app.js").write_text("console.log('app')")
    (root / "sw.js").write_text("self.addEventListener('fetch', () => {})")
    (root / "manifest.webmanifest").write_text("{}")
    (root / "icons" / "icon-192.png").write_bytes(b"\x89PNG")
    (tmp_path / "secret.txt").write_text("nope")
    return root


@pytest.fixture
async def web_client(api, settings: WebSettings, dist: Path, opencode, bot_store):
    settings.static_dir = dist
    return await api(client=opencode, store=bot_store)


async def test_root_serves_index(web_client) -> None:
    response = await web_client.get("/")
    assert response.status == 200
    assert "panel" in await response.text()
    assert response.headers["Cache-Control"] == "no-cache"
    assert response.headers["Content-Type"].startswith("text/html")
    assert response.headers["X-Content-Type-Options"] == "nosniff"


async def test_asset_served_with_long_cache(web_client) -> None:
    response = await web_client.get("/assets/app.js")
    assert response.status == 200
    assert await response.text() == "console.log('app')"
    assert "immutable" in response.headers["Cache-Control"]
    assert "javascript" in response.headers["Content-Type"]


async def test_missing_asset_404(web_client) -> None:
    response = await web_client.get("/assets/missing.js")
    assert response.status == 404
    assert (await response.json())["error"]["code"] == "not_found"


async def test_spa_fallback(web_client) -> None:
    response = await web_client.get("/session/abc")
    assert response.status == 200
    assert "panel" in await response.text()


async def test_api_not_intercepted(web_client) -> None:
    response = await web_client.get("/api/health")
    assert (await response.json())["status"] == "ok"
    response = await web_client.get("/api/unknown")
    assert response.status == 404
    assert response.headers["Content-Type"].startswith("application/json")
    response = await web_client.get("/health")
    assert (await response.json())["status"] == "ok"


async def test_sw_and_manifest(web_client) -> None:
    response = await web_client.get("/sw.js")
    assert response.headers["Cache-Control"] == "no-cache"
    assert response.headers["Service-Worker-Allowed"] == "/"
    response = await web_client.get("/manifest.webmanifest")
    assert response.headers["Content-Type"].startswith("application/manifest+json")


async def test_no_path_traversal(web_client) -> None:
    for path in ("/../secret.txt", "/%2e%2e/secret.txt", "/assets/..%2f..%2fsecret.txt"):
        response = await web_client.get(path)
        assert "nope" not in await response.text()


async def test_without_build(api, settings: WebSettings, tmp_path: Path, opencode, bot_store) -> None:
    settings.static_dir = tmp_path / "missing"
    client = await api(client=opencode, store=bot_store)
    response = await client.get("/")
    assert response.status == 404
    assert (await client.get("/health")).status == 200
