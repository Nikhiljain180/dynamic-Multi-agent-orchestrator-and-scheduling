import pytest


@pytest.mark.asyncio
async def test_list_schedules_returns_workflows_with_cron(client):
    create_resp = await client.post(
        "/api/workflows",
        json={
            "name": "Scheduled Template",
            "description": "Daily brief",
            "is_template": True,
            "graph_definition": {
                "entry_node_id": "entry",
                "nodes": [],
                "edges": [],
                "schedule": {
                    "cron": "0 9 * * *",
                    "input_text": "Morning brief",
                    "enabled": True,
                },
            },
        },
    )
    workflow_id = create_resp.json()["id"]

    list_resp = await client.get("/api/schedules")
    assert list_resp.status_code == 200
    items = list_resp.json()
    match = next(item for item in items if item["workflow_id"] == workflow_id)
    assert match["workflow_name"] == "Scheduled Template"
    assert match["cron"] == "0 9 * * *"
    assert match["input_text"] == "Morning brief"
    assert match["enabled"] is True
    assert match["is_template"] is True


@pytest.mark.asyncio
async def test_pause_and_resume_schedule(client):
    create_resp = await client.post(
        "/api/workflows",
        json={
            "name": "Pausable Workflow",
            "graph_definition": {
                "entry_node_id": "entry",
                "nodes": [],
                "edges": [],
                "schedule": {"cron": "*/5 * * * *", "input_text": "tick"},
            },
        },
    )
    workflow_id = create_resp.json()["id"]

    pause_resp = await client.patch(f"/api/schedules/{workflow_id}", json={"enabled": False})
    assert pause_resp.status_code == 200
    assert pause_resp.json()["enabled"] is False

    resume_resp = await client.patch(f"/api/schedules/{workflow_id}", json={"enabled": True})
    assert resume_resp.status_code == 200
    assert resume_resp.json()["enabled"] is True


@pytest.mark.asyncio
async def test_delete_schedule_clears_cron(client):
    create_resp = await client.post(
        "/api/workflows",
        json={
            "name": "Deletable Schedule",
            "graph_definition": {
                "entry_node_id": "entry",
                "nodes": [],
                "edges": [],
                "schedule": {"cron": "0 12 * * *", "input_text": "noon"},
            },
        },
    )
    workflow_id = create_resp.json()["id"]

    delete_resp = await client.delete(f"/api/schedules/{workflow_id}")
    assert delete_resp.status_code == 204

    list_resp = await client.get("/api/schedules")
    assert not any(item["workflow_id"] == workflow_id for item in list_resp.json())

    workflow_resp = await client.get(f"/api/workflows/{workflow_id}")
    assert workflow_resp.status_code == 200
    assert "schedule" not in workflow_resp.json()["graph_definition"]


@pytest.mark.asyncio
async def test_get_schedule_not_found(client):
    resp = await client.get("/api/schedules/missing-id")
    assert resp.status_code == 404
