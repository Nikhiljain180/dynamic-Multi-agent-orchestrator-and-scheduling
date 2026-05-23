from datetime import datetime, timezone

from sqlalchemy import select

from app.database import AsyncSessionLocal
from app.models import Agent, MessageRole, RunStatus, Workflow
from app.runtime.graph_builder import build_graph_from_definition
from app.services import RunService, publish_event


async def execute_workflow_run(run_id: str, channel_context: dict | None = None) -> None:
    async with AsyncSessionLocal() as db:
        run = await RunService.get_run(db, run_id)
        if not run:
            return

        workflow = await db.get(Workflow, run.workflow_id)
        if not workflow:
            run.status = RunStatus.FAILED
            run.error = "Workflow not found"
            await db.commit()
            return

        run.status = RunStatus.RUNNING
        run.started_at = datetime.now(timezone.utc)
        await db.commit()

        await publish_event(
            f"run:{run_id}",
            {"type": "status", "data": {"run_id": run_id, "status": RunStatus.RUNNING.value}},
        )
        await RunService.add_log(db, run_id, f"Workflow '{workflow.name}' started")

        if channel_context:
            await RunService.add_message(
                db,
                run_id,
                run.input_text,
                MessageRole.HUMAN,
                channel=channel_context.get("channel", "telegram"),
            )

        result = await db.execute(select(Agent))
        agents = {a.id: a for a in result.scalars().all()}

        graph_def = workflow.graph_definition or {}
        try:
            graph = build_graph_from_definition(graph_def, agents, db, run_id, workflow.name)
            initial_state = {
                "input_text": run.input_text,
                "messages": [],
                "agent_outputs": {},
                "review_passed": False,
                "triage_intent": "",
                "final_output": "",
                "channel_context": channel_context or {},
            }
            final_state = await graph.ainvoke(initial_state)
            run.output_text = final_state.get("final_output") or _collect_output(final_state)
            run.status = RunStatus.COMPLETED
            run.completed_at = datetime.now(timezone.utc)
            await RunService.add_log(db, run_id, "Workflow completed successfully")
        except Exception as exc:
            run.status = RunStatus.FAILED
            run.error = str(exc)
            run.completed_at = datetime.now(timezone.utc)
            await RunService.add_log(db, run_id, f"Workflow failed: {exc}", level="error")

        await db.commit()
        await publish_event(
            f"run:{run_id}",
            {"type": "status", "data": {"run_id": run_id, "status": run.status.value, "output": run.output_text}},
        )


def _collect_output(state: dict) -> str:
    outputs = state.get("agent_outputs", {})
    if not outputs:
        return "No output generated."
    return "\n\n".join(f"## {k}\n{v}" for k, v in outputs.items())
