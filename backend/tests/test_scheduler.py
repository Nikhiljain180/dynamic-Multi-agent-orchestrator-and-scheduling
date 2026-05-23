from datetime import datetime, timezone

import pytest

from app.workers.scheduler import cron_slot_due, get_workflow_schedule, tick_schedules


def test_cron_slot_due_matches_within_poll_window():
    now = datetime(2026, 5, 22, 9, 0, 30, tzinfo=timezone.utc)
    slot = cron_slot_due("0 9 * * *", now, window_seconds=60)
    assert slot == datetime(2026, 5, 22, 9, 0, tzinfo=timezone.utc)


def test_cron_slot_due_every_two_minutes_caught_on_next_poll():
    """*/2 cron must still fire when the poll tick lands ~60s after the slot."""
    now = datetime(2026, 5, 24, 4, 3, 0, tzinfo=timezone.utc)
    slot = cron_slot_due("*/2 * * * *", now, window_seconds=60)
    assert slot == datetime(2026, 5, 24, 4, 2, tzinfo=timezone.utc)


def test_cron_slot_due_daily_not_fired_hours_later():
    now = datetime(2026, 5, 24, 11, 0, 0, tzinfo=timezone.utc)
    slot = cron_slot_due("0 4 * * *", now, window_seconds=60)
    assert slot is None


def test_get_workflow_schedule():
    assert get_workflow_schedule({"schedule": {"cron": "*/5 * * * *", "input_text": "hello"}}) == {
        "cron": "*/5 * * * *",
        "input_text": "hello",
    }
    assert get_workflow_schedule({}) == {}


@pytest.mark.asyncio
async def test_tick_schedules_skips_channel_only_template(db_session, monkeypatch):
    from app.services import WorkflowService
    from app.workers import scheduler as scheduler_module

    started: list[str] = []

    async def fake_execute(run_id, channel_context=None):
        started.append(run_id)

    monkeypatch.setattr(scheduler_module, "execute_workflow_run", fake_execute)
    monkeypatch.setattr(
        scheduler_module,
        "cron_slot_due",
        lambda _expr, _now, _window: datetime(2026, 5, 22, 12, 0, tzinfo=timezone.utc),
    )
    scheduler_module._last_fired.clear()

    await WorkflowService.create_workflow(
        db_session,
        {
            "name": "Telegram With Stale Cron",
            "graph_definition": {
                "template_type": "telegram_triage",
                "entry_node_id": "entry",
                "nodes": [],
                "edges": [],
                "schedule": {"cron": "*/5 * * * *", "input_text": "should not run"},
            },
        },
    )

    await tick_schedules()

    assert not started


@pytest.mark.asyncio
async def test_tick_schedules_skips_paused_workflow(db_session, monkeypatch):
    from app.services import WorkflowService
    from app.workers import scheduler as scheduler_module

    started: list[str] = []

    async def fake_execute(run_id, channel_context=None):
        started.append(run_id)

    monkeypatch.setattr(scheduler_module, "execute_workflow_run", fake_execute)
    monkeypatch.setattr(
        scheduler_module,
        "cron_slot_due",
        lambda _expr, _now, _window: datetime(2026, 5, 22, 12, 0, tzinfo=timezone.utc),
    )
    scheduler_module._last_fired.clear()

    await WorkflowService.create_workflow(
        db_session,
        {
            "name": "Paused Workflow",
            "graph_definition": {
                "entry_node_id": "entry",
                "nodes": [],
                "edges": [],
                "schedule": {
                    "cron": "*/5 * * * *",
                    "input_text": "should not run",
                    "enabled": False,
                },
            },
        },
    )

    await tick_schedules()

    assert not started


@pytest.mark.asyncio
async def test_tick_schedules_starts_workflow_run(db_session, monkeypatch):
    from app.services import WorkflowService
    from app.workers import scheduler as scheduler_module

    started: list[str] = []

    async def fake_execute(run_id, channel_context=None):
        started.append(run_id)

    monkeypatch.setattr(scheduler_module, "execute_workflow_run", fake_execute)
    monkeypatch.setattr(
        scheduler_module,
        "cron_slot_due",
        lambda _expr, _now, _window: datetime(2026, 5, 22, 12, 0, tzinfo=timezone.utc),
    )
    scheduler_module._last_fired.clear()

    await WorkflowService.create_workflow(
        db_session,
        {
            "name": "Scheduled Workflow",
            "graph_definition": {
                "entry_node_id": "entry",
                "nodes": [],
                "edges": [],
                "schedule": {
                    "cron": "*/5 * * * *",
                    "input_text": "scheduled hello",
                },
            },
        },
    )

    await tick_schedules()

    assert started
