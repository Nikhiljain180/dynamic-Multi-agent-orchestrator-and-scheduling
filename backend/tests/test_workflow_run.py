import pytest

from app.workers.executor import execute_workflow_run


@pytest.mark.asyncio
async def test_brief_summary_workflow_executes(session_factory, monkeypatch):
    from app.config import settings
    from app.models import Agent
    from app.services import RunService, WorkflowService

    monkeypatch.setattr(settings, "llm_provider", "mock")

    async with session_factory() as db_session:
        brief = Agent(
            id="b1",
            name="Brief",
            role="Brief Specialist",
            system_prompt="brief",
            model="llama-3.1-8b-instant",
            tools=[],
        )
        summary = Agent(
            id="s1",
            name="Summary",
            role="Executive Summarizer",
            system_prompt="summary",
            model="llama-3.1-8b-instant",
            tools=[],
        )
        db_session.add_all([brief, summary])
        await db_session.commit()

        workflow = await WorkflowService.create_workflow(
            db_session,
            {
                "name": "Test Brief Summary",
                "graph_definition": {
                    "template_type": "brief_summary",
                    "nodes": [
                        {"id": "brief", "agent_id": "b1", "label": "Quick Brief", "position": {"x": 0, "y": 0}},
                        {"id": "summary", "agent_id": "s1", "label": "Executive Summary", "position": {"x": 0, "y": 0}},
                    ],
                    "edges": [],
                },
            },
        )

        run = await RunService.create_run(db_session, workflow.id, "Customer support automation")
        run_id = run.id

    await execute_workflow_run(run_id)

    async with session_factory() as db_session:
        completed = await RunService.get_run(db_session, run_id)
        assert completed is not None
        assert completed.status.value == "completed"
        assert completed.output_text

        messages = await RunService.get_messages(db_session, run_id)
        assert messages
        logs = await RunService.get_logs(db_session, run_id)
        assert any("Starting" in log.message for log in logs)
