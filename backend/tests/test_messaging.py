import pytest

from app.models import MessageRole
from app.services import RunService


@pytest.mark.asyncio
async def test_message_persisted_and_logged(db_session):
    from app.models import Workflow
    from app.services import WorkflowService

    workflow = await WorkflowService.create_workflow(
        db_session,
        {"name": "Msg Test", "graph_definition": {"nodes": [], "edges": []}},
    )
    run = await RunService.create_run(db_session, workflow.id, "hello")

    message = await RunService.add_message(
        db_session,
        run.id,
        "agent to agent payload",
        MessageRole.AGENT,
        from_agent_id="agent-a",
        to_agent_id="agent-b",
    )
    log = await RunService.add_log(db_session, run.id, "delivery ok", agent_id="agent-a")

    assert message.content == "agent to agent payload"
    assert log.message == "delivery ok"

    messages = await RunService.get_messages(db_session, run.id)
    assert len(messages) == 1
