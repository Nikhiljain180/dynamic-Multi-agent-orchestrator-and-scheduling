import pytest


@pytest.mark.asyncio
async def test_create_and_list_agents(client):
    payload = {
        "name": "Test Agent",
        "role": "Tester",
        "system_prompt": "You are a test agent.",
        "model": "gpt-4o-mini",
        "tools": ["web_search"],
        "guardrails": {"max_tokens": 1000},
    }
    create_resp = await client.post("/api/agents", json=payload)
    assert create_resp.status_code == 201
    agent = create_resp.json()
    assert agent["name"] == "Test Agent"

    list_resp = await client.get("/api/agents")
    assert list_resp.status_code == 200
    assert any(a["id"] == agent["id"] for a in list_resp.json())


@pytest.mark.asyncio
async def test_update_and_delete_agent(client):
    create_resp = await client.post(
        "/api/agents",
        json={
            "name": "Updatable",
            "role": "Worker",
            "system_prompt": "Original",
            "model": "gpt-4o-mini",
        },
    )
    agent_id = create_resp.json()["id"]

    update_resp = await client.put(f"/api/agents/{agent_id}", json={"system_prompt": "Updated"})
    assert update_resp.status_code == 200
    assert update_resp.json()["system_prompt"] == "Updated"

    delete_resp = await client.delete(f"/api/agents/{agent_id}")
    assert delete_resp.status_code == 204

    get_resp = await client.get(f"/api/agents/{agent_id}")
    assert get_resp.status_code == 404
