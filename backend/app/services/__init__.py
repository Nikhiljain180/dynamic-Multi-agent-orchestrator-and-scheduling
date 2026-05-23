import json
from typing import Any

import redis.asyncio as redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models import Agent, AgentMessage, RunLog, RunStatus, TokenUsage, Workflow, WorkflowRun
from app.services.crypto import encrypt_api_key, mask_api_key


_redis_client: redis.Redis | None = None


async def get_redis() -> redis.Redis:
    global _redis_client
    if _redis_client is None:
        _redis_client = redis.from_url(settings.redis_url, decode_responses=True)
    return _redis_client


async def publish_event(channel: str, payload: dict[str, Any]) -> None:
    client = await get_redis()
    await client.publish(channel, json.dumps(payload))


class AgentService:
    @staticmethod
    def _apply_api_key_fields(data: dict[str, Any]) -> dict[str, Any]:
        data = dict(data)
        api_key = data.pop("api_key", None)
        use_platform = data.get("use_platform_api_key", True)

        if use_platform:
            data["use_platform_api_key"] = True
            data["api_key_encrypted"] = None
            data["api_key_hint"] = None
            return data

        if api_key:
            encrypted = encrypt_api_key(api_key)
            if not encrypted:
                raise ValueError("ENCRYPTION_KEY is not configured; cannot store per-agent API keys")
            data["api_key_encrypted"] = encrypted
            data["api_key_hint"] = mask_api_key(api_key)
            data["use_platform_api_key"] = False

        return data

    @staticmethod
    async def list_agents(db: AsyncSession) -> list[Agent]:
        result = await db.execute(select(Agent).order_by(Agent.created_at.desc()))
        return list(result.scalars().all())

    @staticmethod
    async def get_agent(db: AsyncSession, agent_id: str) -> Agent | None:
        return await db.get(Agent, agent_id)

    @staticmethod
    async def create_agent(db: AsyncSession, data: dict[str, Any]) -> Agent:
        data = AgentService._apply_api_key_fields(data)
        agent = Agent(**data)
        db.add(agent)
        await db.commit()
        await db.refresh(agent)
        return agent

    @staticmethod
    async def update_agent(db: AsyncSession, agent: Agent, data: dict[str, Any]) -> Agent:
        data = dict(data)
        if "api_key" in data or "use_platform_api_key" in data:
            merged = {
                "use_platform_api_key": data.get("use_platform_api_key", agent.use_platform_api_key),
                "api_key": data.pop("api_key", None),
            }
            key_data = AgentService._apply_api_key_fields(merged)
            data.update(key_data)
        for key, value in data.items():
            setattr(agent, key, value)
        await db.commit()
        await db.refresh(agent)
        return agent

    @staticmethod
    async def delete_agent(db: AsyncSession, agent: Agent) -> None:
        await db.delete(agent)
        await db.commit()


class WorkflowService:
    @staticmethod
    async def list_workflows(db: AsyncSession) -> list[Workflow]:
        result = await db.execute(select(Workflow).order_by(Workflow.created_at.desc()))
        return list(result.scalars().all())

    @staticmethod
    async def get_workflow(db: AsyncSession, workflow_id: str) -> Workflow | None:
        return await db.get(Workflow, workflow_id)

    @staticmethod
    async def create_workflow(db: AsyncSession, data: dict[str, Any]) -> Workflow:
        if isinstance(data.get("graph_definition"), dict):
            data["graph_definition"] = data["graph_definition"]
        workflow = Workflow(**data)
        db.add(workflow)
        await db.commit()
        await db.refresh(workflow)
        return workflow

    @staticmethod
    async def update_workflow(db: AsyncSession, workflow: Workflow, data: dict[str, Any]) -> Workflow:
        for key, value in data.items():
            setattr(workflow, key, value)
        await db.commit()
        await db.refresh(workflow)
        return workflow

    @staticmethod
    async def delete_workflow(db: AsyncSession, workflow: Workflow) -> None:
        await db.delete(workflow)
        await db.commit()


class RunService:
    @staticmethod
    async def create_run(db: AsyncSession, workflow_id: str, input_text: str) -> WorkflowRun:
        run = WorkflowRun(workflow_id=workflow_id, input_text=input_text, status=RunStatus.QUEUED)
        db.add(run)
        await db.commit()
        await db.refresh(run)
        return run

    @staticmethod
    async def get_run(db: AsyncSession, run_id: str) -> WorkflowRun | None:
        return await db.get(WorkflowRun, run_id)

    @staticmethod
    async def list_runs(db: AsyncSession, workflow_id: str | None = None) -> list[WorkflowRun]:
        query = select(WorkflowRun).order_by(WorkflowRun.created_at.desc())
        if workflow_id:
            query = query.where(WorkflowRun.workflow_id == workflow_id)
        result = await db.execute(query)
        return list(result.scalars().all())

    @staticmethod
    async def add_message(
        db: AsyncSession,
        run_id: str,
        content: str,
        role: str,
        from_agent_id: str | None = None,
        to_agent_id: str | None = None,
        channel: str | None = None,
    ) -> AgentMessage:
        message = AgentMessage(
            run_id=run_id,
            content=content,
            role=role,
            from_agent_id=from_agent_id,
            to_agent_id=to_agent_id,
            channel=channel,
        )
        db.add(message)
        await db.commit()
        await db.refresh(message)
        await publish_event(
            f"run:{run_id}",
            {
                "type": "message",
                "data": {
                    "id": message.id,
                    "run_id": run_id,
                    "from_agent_id": from_agent_id,
                    "to_agent_id": to_agent_id,
                    "role": role,
                    "content": content,
                    "channel": channel,
                    "created_at": message.created_at.isoformat(),
                },
            },
        )
        return message

    @staticmethod
    async def add_log(
        db: AsyncSession,
        run_id: str,
        message: str,
        level: str = "info",
        agent_id: str | None = None,
    ) -> RunLog:
        log = RunLog(run_id=run_id, message=message, level=level, agent_id=agent_id)
        db.add(log)
        await db.commit()
        await db.refresh(log)
        await publish_event(
            f"run:{run_id}",
            {
                "type": "log",
                "data": {
                    "id": log.id,
                    "run_id": run_id,
                    "agent_id": agent_id,
                    "level": level,
                    "message": message,
                    "created_at": log.created_at.isoformat(),
                },
            },
        )
        return log

    @staticmethod
    async def add_token_usage(
        db: AsyncSession,
        run_id: str,
        node_name: str,
        prompt_tokens: int,
        completion_tokens: int,
        agent_id: str | None = None,
    ) -> TokenUsage:
        total = prompt_tokens + completion_tokens
        cost = (prompt_tokens * 0.00000015) + (completion_tokens * 0.0000006)
        usage = TokenUsage(
            run_id=run_id,
            node_name=node_name,
            agent_id=agent_id,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total,
            estimated_cost=cost,
        )
        db.add(usage)
        run = await db.get(WorkflowRun, run_id)
        if run:
            run.total_tokens += total
            run.total_cost += cost
        await db.commit()
        await db.refresh(usage)
        await publish_event(
            f"run:{run_id}",
            {
                "type": "token_usage",
                "data": {
                    "id": usage.id,
                    "run_id": run_id,
                    "agent_id": agent_id,
                    "node_name": node_name,
                    "prompt_tokens": prompt_tokens,
                    "completion_tokens": completion_tokens,
                    "total_tokens": total,
                    "estimated_cost": cost,
                    "created_at": usage.created_at.isoformat(),
                },
            },
        )
        return usage

    @staticmethod
    async def get_messages(
        db: AsyncSession,
        run_id: str | None = None,
        *,
        newest_first: bool = False,
    ) -> list[AgentMessage]:
        order = AgentMessage.created_at.desc() if newest_first else AgentMessage.created_at.asc()
        query = select(AgentMessage).order_by(order)
        if run_id:
            query = query.where(AgentMessage.run_id == run_id)
        result = await db.execute(query)
        return list(result.scalars().all())

    @staticmethod
    async def get_logs(db: AsyncSession, run_id: str) -> list[RunLog]:
        result = await db.execute(
            select(RunLog).where(RunLog.run_id == run_id).order_by(RunLog.created_at.asc())
        )
        return list(result.scalars().all())

    @staticmethod
    async def get_token_usages(db: AsyncSession, run_id: str) -> list[TokenUsage]:
        result = await db.execute(
            select(TokenUsage).where(TokenUsage.run_id == run_id).order_by(TokenUsage.created_at.asc())
        )
        return list(result.scalars().all())
