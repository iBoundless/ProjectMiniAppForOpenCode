"""SSE: /api/events и EventHub."""

from __future__ import annotations

import asyncio
import json

import pytest
from ocbot.opencode.events import Event

from conftest import OWNER_ID, login
from fakes import make_session

from ocbot_web.events import EventHub, event_session_id
from ocbot_web.keys import HUB


async def read_event(response, timeout: float = 2.0) -> str:
    """Следующий непустой блок SSE (без служебного приветствия)."""
    lines: list[str] = []
    while True:
        raw = await asyncio.wait_for(response.content.readline(), timeout)
        if not raw:
            raise EOFError
        line = raw.decode().rstrip("\n")
        if line:
            lines.append(line)
            continue
        if lines:
            block = "\n".join(lines)
            lines = []
            if ": connected" in block:
                continue
            return block


def data_of(block: str) -> dict:
    line = next(item for item in block.splitlines() if item.startswith("data: "))
    return json.loads(line[6:])


def delta(session_id: str, text: str = "hi", event_type: str = "session.text.delta") -> Event:
    return Event(id=f"e-{session_id}-{text}", type=event_type, data={"sessionID": session_id, "delta": text})


@pytest.fixture
async def sse(api, opencode, bot_store):
    async def open_stream(heartbeat: float = 5.0, user: int = OWNER_ID):
        client = await api(client=opencode, store=bot_store, heartbeat=heartbeat)
        headers = await login(client, user)
        response = await client.get("/api/events", headers=headers)
        return client, response

    return open_stream


async def wait_for(predicate, timeout: float = 2.0) -> None:
    deadline = asyncio.get_running_loop().time() + timeout
    while not predicate():
        if asyncio.get_running_loop().time() > deadline:
            raise AssertionError("condition not met")
        await asyncio.sleep(0.01)


async def test_requires_auth(api, opencode, bot_store) -> None:
    client = await api(client=opencode, store=bot_store)
    response = await client.get("/api/events")
    assert response.status == 401


async def test_subscribed_event_delivered_foreign_skipped(sse, opencode, bot_store) -> None:
    opencode.add(make_session("mine"))
    opencode.add(make_session("other"))
    await bot_store.subscribe(OWNER_ID, "mine")
    client, response = await sse()
    assert response.status == 200
    assert response.headers["Content-Type"].startswith("text/event-stream")
    hub = client.server.app[HUB]
    await wait_for(lambda: len(hub.connections) == 1)

    await opencode.event_queue.put(delta("other", "secret"))
    await opencode.event_queue.put(delta("mine", "hello"))
    block = await read_event(response)
    payload = data_of(block)
    assert payload["session_id"] == "mine"
    assert payload["type"] == "session.text.delta"
    assert payload["data"]["delta"] == "hello"
    assert "id: e-mine-hello" in block
    response.close()


async def test_child_session_event_follows_root(sse, opencode, bot_store) -> None:
    opencode.add(make_session("mine"))
    opencode.add(make_session("child", parent_id="mine"))
    await bot_store.subscribe(OWNER_ID, "mine")
    client, response = await sse()
    await wait_for(lambda: len(client.server.app[HUB].connections) == 1)
    await opencode.event_queue.put(delta("child", "sub"))
    assert data_of(await read_event(response))["session_id"] == "child"
    response.close()


async def test_notify_all_passes_everything(sse, opencode, bot_store) -> None:
    opencode.add(make_session("other"))
    await bot_store.set_notify_all(OWNER_ID, True)
    client, response = await sse()
    await wait_for(lambda: len(client.server.app[HUB].connections) == 1)
    await opencode.event_queue.put(
        Event(id="p1", type="permission.asked", data={"id": "r1", "sessionID": "other"})
    )
    payload = data_of(await read_event(response))
    assert payload["type"] == "permission.asked"
    response.close()


async def test_permission_only_for_owner(api, opencode, bot_store) -> None:
    opencode.add(make_session("mine"))
    await bot_store.subscribe(OWNER_ID, "mine")
    client = await api(client=opencode, store=bot_store)
    owner = await client.get("/api/events", headers=await login(client, OWNER_ID))
    other = await client.get("/api/events", headers=await login(client, 43))
    hub = client.server.app[HUB]
    await wait_for(lambda: len(hub.connections) == 2)
    await opencode.event_queue.put(
        Event(id="p1", type="permission.asked", data={"id": "r1", "sessionID": "mine"})
    )
    assert data_of(await read_event(owner))["type"] == "permission.asked"
    with pytest.raises(TimeoutError):
        await read_event(other, timeout=0.3)
    owner.close()
    other.close()


async def test_disconnect_removes_connection(sse, opencode) -> None:
    client, response = await sse()
    hub = client.server.app[HUB]
    await wait_for(lambda: len(hub.connections) == 1)
    response.close()
    # Сервер замечает разрыв при следующей записи (heartbeat или событие).
    opencode.add(make_session("x"))
    await opencode.event_queue.put(delta("x"))
    await wait_for(lambda: len(hub.connections) == 0, timeout=5)


async def test_heartbeat(sse) -> None:
    client, response = await sse(heartbeat=0.05)
    raw = b""
    while b": ping" not in raw:
        raw += await asyncio.wait_for(response.content.readline(), 2)
    response.close()


async def test_logout_closes_stream(api, opencode, bot_store) -> None:
    client = await api(client=opencode, store=bot_store, heartbeat=0.05)
    headers = await login(client)
    response = await client.get("/api/events", headers=headers)
    await client.post("/api/auth/logout", headers=headers)
    body = await asyncio.wait_for(response.content.read(), 3)
    assert body.startswith(b"retry:")
    await wait_for(lambda: len(client.server.app[HUB].connections) == 0)


async def test_created_session_visible_immediately(sse, opencode, bot_store) -> None:
    client, response = await sse()
    hub = client.server.app[HUB]
    await wait_for(lambda: len(hub.connections) == 1)
    connection = next(iter(hub.connections))
    opencode.add(make_session("fresh"))
    hub.remember(OWNER_ID, "fresh")
    assert await connection.visibility.can_see("fresh")
    response.close()


class FlakyClient:
    def __init__(self, events: list[Event]) -> None:
        self.calls = 0
        self.events_list = events

    async def get_session(self, session_id: str):
        return make_session(session_id)

    async def _gen(self):
        self.calls += 1
        if self.calls == 1:
            raise ConnectionError("boom")
        for event in self.events_list:
            yield event
        await asyncio.Event().wait()

    def events(self):
        return self._gen()


async def test_hub_backoff_and_reconnect(bot_store) -> None:
    sleeps: list[float] = []

    async def fake_sleep(delay: float) -> None:
        sleeps.append(delay)

    await bot_store.set_notify_all(OWNER_ID, True)
    client = FlakyClient([delta("s1")])
    hub = EventHub(client, bot_store, sleep=fake_sleep)
    connection = hub.connect(OWNER_ID)
    hub.start()
    chunk = await asyncio.wait_for(connection.queue.get(), 2)
    assert '"session_id":"s1"' in chunk
    assert sleeps == [1.0]
    assert hub.reconnects == 1
    await hub.stop()


async def test_slow_client_drops_oldest(bot_store) -> None:
    from ocbot_web import events as events_module

    await bot_store.set_notify_all(OWNER_ID, True)
    hub = EventHub(FlakyClient([]), bot_store)
    connection = hub.connect(OWNER_ID)
    for index in range(events_module.QUEUE_SIZE + 3):
        await hub.dispatch(delta("s", str(index)))
    assert connection.queue.qsize() == events_module.QUEUE_SIZE
    assert connection.dropped == 3


def test_event_session_id_variants() -> None:
    assert event_session_id(Event(None, "session.idle", {"sessionID": "a"})) == "a"
    assert event_session_id(Event(None, "session.updated", {"info": {"sessionID": "b"}})) == "b"
    assert event_session_id(Event(None, "session.updated", {"id": "c"})) == "c"
    assert event_session_id(Event(None, "permission.asked", {"id": "r"})) is None


async def test_unknown_types_ignored(bot_store) -> None:
    await bot_store.set_notify_all(OWNER_ID, True)
    hub = EventHub(FlakyClient([]), bot_store)
    connection = hub.connect(OWNER_ID)
    await hub.dispatch(Event(None, "server.heartbeat", {"sessionID": "s"}))
    assert connection.queue.empty()
