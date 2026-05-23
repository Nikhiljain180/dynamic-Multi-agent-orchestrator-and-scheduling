from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import RunLog, Workflow, WorkflowRun
from app.runtime.template_config import template_supports_schedule
from app.services import WorkflowService
from app.workers.scheduler import get_workflow_schedule


async def latest_scheduled_run_at(db: AsyncSession, workflow_id: str):
    result = await db.execute(
        select(WorkflowRun.created_at)
        .join(RunLog, RunLog.run_id == WorkflowRun.id)
        .where(WorkflowRun.workflow_id == workflow_id)
        .where(RunLog.message.like("Scheduled run for workflow%"))
        .order_by(WorkflowRun.created_at.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


def is_schedule_enabled(schedule: dict[str, Any]) -> bool:
    return schedule.get("enabled", True) is not False


def workflow_has_schedule(graph_definition: dict[str, Any] | None) -> bool:
    schedule = get_workflow_schedule(graph_definition)
    return bool(str(schedule.get("cron") or "").strip())


def build_schedule_entry(workflow: Workflow, last_run_at=None) -> dict[str, Any] | None:
    if not template_supports_schedule(workflow.graph_definition, workflow.name):
        return None
    schedule = get_workflow_schedule(workflow.graph_definition)
    cron = str(schedule.get("cron") or "").strip()
    if not cron:
        return None
    return {
        "workflow_id": workflow.id,
        "workflow_name": workflow.name,
        "description": workflow.description,
        "is_template": workflow.is_template,
        "cron": cron,
        "input_text": schedule.get("input_text") or "",
        "enabled": is_schedule_enabled(schedule),
        "updated_at": workflow.updated_at,
        "last_run_at": last_run_at,
    }


def patch_workflow_schedule(graph_definition: dict[str, Any] | None, patch: dict[str, Any]) -> dict[str, Any]:
    graph = dict(graph_definition or {})
    schedule = dict(get_workflow_schedule(graph))
    if "enabled" in patch and patch["enabled"] is not None:
        schedule["enabled"] = bool(patch["enabled"])
    if "cron" in patch and patch["cron"] is not None:
        schedule["cron"] = str(patch["cron"]).strip() or None
    if "input_text" in patch and patch["input_text"] is not None:
        schedule["input_text"] = str(patch["input_text"])
    graph["schedule"] = schedule
    return graph


def clear_workflow_schedule(graph_definition: dict[str, Any] | None) -> dict[str, Any]:
    graph = dict(graph_definition or {})
    graph.pop("schedule", None)
    return graph


class ScheduleService:
    @staticmethod
    async def list_schedules(db: AsyncSession) -> list[dict[str, Any]]:
        workflows = await WorkflowService.list_workflows(db)
        entries: list[dict[str, Any]] = []
        for workflow in workflows:
            last_run_at = await latest_scheduled_run_at(db, workflow.id)
            entry = build_schedule_entry(workflow, last_run_at=last_run_at)
            if entry:
                entries.append(entry)
        return entries

    @staticmethod
    async def get_schedule(db: AsyncSession, workflow_id: str) -> dict[str, Any] | None:
        workflow = await WorkflowService.get_workflow(db, workflow_id)
        if not workflow:
            return None
        last_run_at = await latest_scheduled_run_at(db, workflow_id)
        return build_schedule_entry(workflow, last_run_at=last_run_at)

    @staticmethod
    async def update_schedule(
        db: AsyncSession,
        workflow: Workflow,
        patch: dict[str, Any],
    ) -> dict[str, Any]:
        graph = patch_workflow_schedule(workflow.graph_definition, patch)
        await WorkflowService.update_workflow(db, workflow, {"graph_definition": graph})
        last_run_at = await latest_scheduled_run_at(db, workflow.id)
        entry = build_schedule_entry(workflow, last_run_at=last_run_at)
        if not entry:
            raise ValueError("Workflow has no schedule to update")
        return entry

    @staticmethod
    async def delete_schedule(db: AsyncSession, workflow: Workflow) -> None:
        graph = clear_workflow_schedule(workflow.graph_definition)
        await WorkflowService.update_workflow(db, workflow, {"graph_definition": graph})
