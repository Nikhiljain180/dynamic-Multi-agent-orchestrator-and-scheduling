import asyncio
import json

import pytest
from starlette.websockets import WebSocketDisconnect

from app.models import MessageRole
from app.services import RunService


@pytest.mark.asyncio
async def test_add_message_publishes_event(published_events, db_session):
    from app.services import WorkflowService

    workflow = await WorkflowService.create_workflow(
        db_session,
        {"name": "Event Test", "graph_definition": {"nodes": [], "edges": []}},
    )
    run = await RunService.create_run(db_session, workflow.id, "hello")

    await RunService.add_message(
        db_session,
        run.id,
        "agent payload",
        MessageRole.AGENT,
        from_agent_id="agent-a",
    )

    assert len(published_events) == 1
    assert published_events[0]["channel"] == f"run:{run.id}"
    payload = published_events[0]["payload"]
    assert payload["type"] == "message"
    assert payload["data"]["content"] == "agent payload"


@pytest.mark.asyncio
async def test_add_log_publishes_event(published_events, db_session):
    from app.services import WorkflowService

    workflow = await WorkflowService.create_workflow(
        db_session,
        {"name": "Log Event Test", "graph_definition": {"nodes": [], "edges": []}},
    )
    run = await RunService.create_run(db_session, workflow.id, "hello")

    await RunService.add_log(db_session, run.id, "delivery ok", agent_id="agent-a")

    assert published_events[-1]["payload"]["type"] == "log"
    assert published_events[-1]["payload"]["data"]["message"] == "delivery ok"


@pytest.mark.asyncio
async def test_websocket_forwards_pubsub_payload(monkeypatch):
    from app.api.routes import websocket_run_monitor

    payload = {"type": "log", "data": {"message": "hello websocket"}}

    class FakePubSub:
        def __init__(self):
            self.calls = 0

        async def subscribe(self, channel):
            return None

        async def get_message(self, ignore_subscribe_messages=True, timeout=1.0):
            self.calls += 1
            if self.calls == 1:
                return {"data": json.dumps(payload)}
            await asyncio.sleep(0)
            return None

        async def unsubscribe(self, channel):
            return None

        async def close(self):
            return None

    class FakeRedis:
        def pubsub(self):
            return FakePubSub()

    async def fake_get_redis():
        return FakeRedis()

    class FakeWebSocket:
        def __init__(self):
            self.sent: list[str] = []

        async def accept(self):
            return None

        async def send_text(self, data: str):
            self.sent.append(data)
            raise WebSocketDisconnect()

        async def receive_text(self):
            await asyncio.sleep(0.02)
            raise asyncio.TimeoutError

    monkeypatch.setattr("app.api.routes.get_redis", fake_get_redis)

    websocket = FakeWebSocket()
    await websocket_run_monitor(websocket, "run-1")

    assert websocket.sent
    assert json.loads(websocket.sent[0]) == payload
