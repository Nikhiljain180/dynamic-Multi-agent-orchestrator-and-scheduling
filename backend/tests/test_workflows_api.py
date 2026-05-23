import pytest


@pytest.mark.asyncio
async def test_create_update_delete_workflow(client):
    agent_resp = await client.post(
        "/api/agents",
        json={
            "name": "Workflow Agent",
            "role": "Worker",
            "system_prompt": "Do work",
            "model": "llama-3.1-8b-instant",
        },
    )
    agent_id = agent_resp.json()["id"]

    create_resp = await client.post(
        "/api/workflows",
        json={
            "name": "Custom Pipeline",
            "description": "Two-step test workflow",
            "graph_definition": {
                "entry_node_id": "step1",
                "nodes": [
                    {"id": "step1", "agent_id": agent_id, "label": "Step 1", "position": {"x": 0, "y": 0}},
                ],
                "edges": [],
            },
        },
    )
    assert create_resp.status_code == 201
    workflow = create_resp.json()
    workflow_id = workflow["id"]
    assert workflow["name"] == "Custom Pipeline"

    update_resp = await client.put(
        f"/api/workflows/{workflow_id}",
        json={"description": "Updated description"},
    )
    assert update_resp.status_code == 200
    assert update_resp.json()["description"] == "Updated description"

    list_resp = await client.get("/api/workflows")
    assert any(item["id"] == workflow_id for item in list_resp.json())

    delete_resp = await client.delete(f"/api/workflows/{workflow_id}")
    assert delete_resp.status_code == 204

    get_resp = await client.get(f"/api/workflows/{workflow_id}")
    assert get_resp.status_code == 404


@pytest.mark.asyncio
async def test_start_workflow_run_returns_accepted(client, monkeypatch):
    agent_resp = await client.post(
        "/api/agents",
        json={
            "name": "Runner Agent",
            "role": "Worker",
            "system_prompt": "Run",
            "model": "llama-3.1-8b-instant",
        },
    )
    agent_id = agent_resp.json()["id"]

    workflow_resp = await client.post(
        "/api/workflows",
        json={
            "name": "Runnable Workflow",
            "graph_definition": {
                "entry_node_id": "only",
                "nodes": [
                    {"id": "only", "agent_id": agent_id, "label": "Only", "position": {"x": 0, "y": 0}},
                ],
                "edges": [],
            },
        },
    )
    workflow_id = workflow_resp.json()["id"]

    started = []

    async def fake_execute(run_id, channel_context=None):
        started.append((run_id, channel_context))

    monkeypatch.setattr("app.api.routes.execute_workflow_run", fake_execute)

    run_resp = await client.post(
        f"/api/workflows/{workflow_id}/runs",
        json={"input_text": "hello from api test", "channel_context": {"channel": "web"}},
    )
    assert run_resp.status_code == 202
    run = run_resp.json()
    assert run["status"] == "queued"
    assert run["input_text"] == "hello from api test"
    assert len(started) == 1
    assert started[0][1] == {"channel": "web"}


@pytest.mark.asyncio
async def test_repair_graph_endpoint_fixes_dual_always_branches(client):
    triage_resp = await client.post(
        "/api/agents",
        json={
            "name": "Triage Agent",
            "role": "Triage Specialist",
            "system_prompt": "Classify",
            "model": "llama-3.1-8b-instant",
        },
    )
    research_resp = await client.post(
        "/api/agents",
        json={
            "name": "Research Agent",
            "role": "Research Specialist",
            "system_prompt": "Research",
            "model": "llama-3.1-8b-instant",
        },
    )
    technical_resp = await client.post(
        "/api/agents",
        json={
            "name": "Technical Agent",
            "role": "Technical Specialist",
            "system_prompt": "Technical",
            "model": "llama-3.1-8b-instant",
        },
    )

    repair_resp = await client.post(
        "/api/workflows/repair-graph",
        json={
            "graph_definition": {
                "entry_node_id": "triage",
                "nodes": [
                    {"id": "triage", "agent_id": triage_resp.json()["id"], "label": "Triage", "position": {"x": 0, "y": 0}},
                    {"id": "research", "agent_id": research_resp.json()["id"], "label": "Research Agent", "position": {"x": 0, "y": 0}},
                    {"id": "technical", "agent_id": technical_resp.json()["id"], "label": "Technical", "position": {"x": 0, "y": 0}},
                ],
                "edges": [
                    {"id": "e1", "source": "triage", "target": "research", "edge_type": "always", "condition": None},
                    {"id": "e2", "source": "triage", "target": "technical", "edge_type": "always", "condition": None},
                ],
            }
        },
    )
    assert repair_resp.status_code == 200
    repaired = repair_resp.json()["graph_definition"]
    research_edge = next(edge for edge in repaired["edges"] if edge["id"] == "e1")
    technical_edge = next(edge for edge in repaired["edges"] if edge["id"] == "e2")
    assert research_edge["edge_type"] == "if_condition"
    assert research_edge["condition"] == "INTENT: research"
    assert technical_edge["edge_type"] == "always"


@pytest.mark.asyncio
async def test_repair_graph_preserves_schedule_and_template_type(client):
    agent_resp = await client.post(
        "/api/agents",
        json={
            "name": "Schedule Agent",
            "role": "Worker",
            "system_prompt": "Work",
            "model": "llama-3.1-8b-instant",
        },
    )
    agent_id = agent_resp.json()["id"]

    repair_resp = await client.post(
        "/api/workflows/repair-graph",
        json={
            "graph_definition": {
                "template_type": "brief_summary",
                "entry_node_id": "n1",
                "nodes": [
                    {"id": "n1", "agent_id": agent_id, "label": "Step", "position": {"x": 0, "y": 0}},
                ],
                "edges": [],
                "schedule": {
                    "cron": "*/2 * * * *",
                    "input_text": "scheduled input",
                    "enabled": True,
                },
            },
        },
    )
    assert repair_resp.status_code == 200
    repaired = repair_resp.json()["graph_definition"]
    assert repaired["template_type"] == "brief_summary"
    assert repaired["schedule"]["cron"] == "*/2 * * * *"
    assert repaired["schedule"]["input_text"] == "scheduled input"
