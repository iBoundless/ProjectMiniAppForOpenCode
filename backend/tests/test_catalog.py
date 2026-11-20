"""API справочников."""

from __future__ import annotations

from ocbot.opencode.models import AgentInfo, ModelInfo


def model(provider: str, model_id: str, name: str = "", enabled: bool = True) -> ModelInfo:
    return ModelInfo.model_validate(
        {
            "id": f"{provider}/{model_id}",
            "modelID": model_id,
            "providerID": provider,
            "name": name,
            "enabled": enabled,
        }
    )


async def test_requires_auth(api, opencode, bot_store) -> None:
    client = await api(client=opencode, store=bot_store)
    for path in ("/api/projects", "/api/models", "/api/agents"):
        assert (await client.get(path)).status == 401


async def test_projects_sorted_by_activity(panel) -> None:
    client, headers = panel
    response = await client.get("/api/projects", headers=headers)
    assert response.status == 200
    items = (await response.json())["items"]
    assert [p["id"] for p in items] == ["p2", "p3", "p1"]
    assert items[0] == {"id": "p2", "canonical": "/work/beta", "title": "Beta", "active": 30}
    assert items[2]["title"] == "alpha"


async def test_models_deduplicated_and_sorted(panel, opencode) -> None:
    client, headers = panel
    opencode.models = [
        model("openai", "gpt-b", "GPT B"),
        model("anthropic", "example-model", "Example Model"),
        model("openai", "gpt-a", "GPT A"),
        model("openai", "gpt-a", "GPT A dup"),
        model("openai", "off", "Off", enabled=False),
    ]
    response = await client.get("/api/models?directory=/work/alpha", headers=headers)
    assert response.status == 200
    items = (await response.json())["items"]
    assert [(m["provider"], m["model"]) for m in items] == [
        ("anthropic", "example-model"),
        ("openai", "gpt-a"),
        ("openai", "gpt-b"),
    ]
    assert items[1]["label"] == "GPT A"


async def test_models_directory_must_be_absolute(panel) -> None:
    client, headers = panel
    response = await client.get("/api/models?directory=relative", headers=headers)
    assert response.status == 400


async def test_agents(panel, opencode) -> None:
    client, headers = panel
    opencode.agents = [
        AgentInfo.model_validate({"id": "plan", "name": "Plan", "mode": "primary"}),
        AgentInfo.model_validate({"id": "build", "mode": "primary"}),
        AgentInfo.model_validate({"id": "secret", "hidden": True}),
    ]
    response = await client.get("/api/agents", headers=headers)
    items = (await response.json())["items"]
    assert items == [
        {"id": "build", "label": "build", "mode": "primary"},
        {"id": "plan", "label": "Plan", "mode": "primary"},
    ]


async def test_unavailable_503(panel, opencode) -> None:
    client, headers = panel
    opencode.unavailable = True
    for path in ("/api/projects", "/api/models", "/api/agents"):
        response = await client.get(path, headers=headers)
        assert response.status == 503
        assert (await response.json())["error"]["code"] == "unavailable"
