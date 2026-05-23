import asyncio
import logging
from datetime import datetime, timezone

from croniter import croniter

from app.config import settings
from app.database import AsyncSessionLocal
from app.runtime.template_config import template_supports_schedule
from app.services import RunService, WorkflowService
from app.workers.executor import execute_workflow_run

logger = logging.getLogger(__name__)

_scheduler_task: asyncio.Task | None = None
_last_fired: dict[str, datetime] = {}


def cron_slot_due(cron_expr: str, now: datetime, window_seconds: int) -> datetime | None:
    """Return the previous cron slot when it falls inside the polling catch-up window."""
    try:
        current = now.astimezone(timezone.utc)
        itr = croniter(cron_expr.strip(), current)
        prev_time = itr.get_prev(datetime)
        if prev_time.tzinfo is None:
            prev_time = prev_time.replace(tzinfo=timezone.utc)
        prev_time = prev_time.replace(second=0, microsecond=0)
        delta = (current - prev_time).total_seconds()
        # Allow up to 2× poll interval so */N minute crons are not skipped between ticks.
        grace = max(window_seconds * 2, 120)
        if 0 <= delta < grace:
            return prev_time
    except (ValueError, KeyError) as exc:
        logger.warning("Invalid cron expression %r: %s", cron_expr, exc)
    return None


def _fire_key(workflow_id: str, slot: datetime) -> str:
    return f"workflow:{workflow_id}:{slot.isoformat()}"


def get_workflow_schedule(graph_definition: dict | None) -> dict:
    schedule = (graph_definition or {}).get("schedule") or {}
    return schedule if isinstance(schedule, dict) else {}


async def tick_schedules() -> None:
    now = datetime.now(timezone.utc)
    window = settings.schedule_poll_seconds

    async with AsyncSessionLocal() as db:
        workflows = await WorkflowService.list_workflows(db)
        for workflow in workflows:
            if not template_supports_schedule(workflow.graph_definition, workflow.name):
                continue
            schedule = get_workflow_schedule(workflow.graph_definition)
            cron = str(schedule.get("cron") or "").strip()
            if not cron:
                continue
            if schedule.get("enabled", True) is False:
                continue

            slot = cron_slot_due(cron, now, window)
            if slot is None:
                continue

            key = _fire_key(workflow.id, slot)
            if key in _last_fired:
                continue

            input_text = schedule.get("input_text") or f"Scheduled run for {workflow.name}"
            run = await RunService.create_run(db, workflow.id, input_text)
            await RunService.add_log(
                db,
                run.id,
                f"Scheduled run for workflow '{workflow.name}' ({cron})",
                level="info",
            )
            _last_fired[key] = now
            asyncio.create_task(
                execute_workflow_run(
                    run.id,
                    {"channel": "schedule", "workflow_id": workflow.id},
                )
            )
            logger.info("Started scheduled workflow %s", workflow.name)


async def _scheduler_loop() -> None:
    while True:
        try:
            await tick_schedules()
        except Exception:
            logger.exception("Scheduler tick failed")
        await asyncio.sleep(settings.schedule_poll_seconds)


async def start_scheduler() -> None:
    global _scheduler_task
    if not settings.schedule_enabled:
        logger.info("Workflow scheduler disabled (SCHEDULE_ENABLED=false)")
        return
    if _scheduler_task and not _scheduler_task.done():
        return
    _scheduler_task = asyncio.create_task(_scheduler_loop())
    logger.info("Workflow scheduler started (poll every %ss)", settings.schedule_poll_seconds)


async def stop_scheduler() -> None:
    global _scheduler_task
    if _scheduler_task:
        _scheduler_task.cancel()
        try:
            await _scheduler_task
        except asyncio.CancelledError:
            pass
        _scheduler_task = None
