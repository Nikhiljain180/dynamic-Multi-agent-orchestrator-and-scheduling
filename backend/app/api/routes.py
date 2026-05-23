import asyncio
import json

from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.runtime.graph_repair import sanitize_graph_definition
from app.runtime.tools import list_available_tools
from app.schemas import (
    AgentCreate,
    AgentMessageResponse,
    AgentResponse,
    AgentUpdate,
    GraphRepairRequest,
    GraphRepairResponse,
    PlatformLLMSettings,
    RunLogResponse,
    TokenUsageResponse,
    ToolInfo,
    WorkflowCreate,
    WorkflowResponse,
    WorkflowRunCreate,
    WorkflowRunResponse,
    WorkflowScheduleResponse,
    WorkflowScheduleUpdate,
    WorkflowUpdate,
)
from app.services import AgentService, RunService, WorkflowService, get_redis
from app.services.schedule_service import ScheduleService
from app.runtime.llm import (
    GROQ_MODELS,
    OLLAMA_MODELS,
    OPENAI_MODELS,
    OPENCODE_MODELS,
    get_platform_api_key,
    get_platform_api_key_hint,
)
from app.config import settings
from app.workers.executor import execute_workflow_run

router = APIRouter()


@router.get("/tools", response_model=list[ToolInfo])
async def list_tools():
    return list_available_tools()


@router.get("/platform/llm-settings", response_model=PlatformLLMSettings)
async def get_platform_llm_settings():
    provider = settings.llm_provider
    model = settings.llm_model or ""
    platform_key = get_platform_api_key(provider)
    return PlatformLLMSettings(
        provider=provider,
        model=model,
        api_key_configured=bool(platform_key and not platform_key.startswith("sk-your")),
        api_key_hint=get_platform_api_key_hint(provider),
        groq_models=GROQ_MODELS,
        openai_models=OPENAI_MODELS,
        ollama_models=OLLAMA_MODELS,
        opencode_models=OPENCODE_MODELS,
        providers=["groq", "openai", "ollama", "opencode", "mock"],
    )


@router.get("/agents", response_model=list[AgentResponse])
async def list_agents(db: AsyncSession = Depends(get_db)):
    return await AgentService.list_agents(db)


@router.post("/agents", response_model=AgentResponse, status_code=201)
async def create_agent(payload: AgentCreate, db: AsyncSession = Depends(get_db)):
    try:
        return await AgentService.create_agent(db, payload.model_dump())
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/agents/{agent_id}", response_model=AgentResponse)
async def get_agent(agent_id: str, db: AsyncSession = Depends(get_db)):
    agent = await AgentService.get_agent(db, agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    return agent


@router.put("/agents/{agent_id}", response_model=AgentResponse)
async def update_agent(agent_id: str, payload: AgentUpdate, db: AsyncSession = Depends(get_db)):
    agent = await AgentService.get_agent(db, agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    try:
        return await AgentService.update_agent(db, agent, payload.model_dump(exclude_unset=True))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.delete("/agents/{agent_id}", status_code=204)
async def delete_agent(agent_id: str, db: AsyncSession = Depends(get_db)):
    agent = await AgentService.get_agent(db, agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    await AgentService.delete_agent(db, agent)


@router.get("/workflows", response_model=list[WorkflowResponse])
async def list_workflows(db: AsyncSession = Depends(get_db)):
    return await WorkflowService.list_workflows(db)


@router.post("/workflows/repair-graph", response_model=GraphRepairResponse)
async def repair_workflow_graph(payload: GraphRepairRequest, db: AsyncSession = Depends(get_db)):
    graph_definition = payload.graph_definition
    if hasattr(graph_definition, "model_dump"):
        graph_definition = graph_definition.model_dump()
    agents = await AgentService.list_agents(db)
    agents_by_id = {agent.id: agent for agent in agents}
    repaired = sanitize_graph_definition(graph_definition, agents_by_id)
    return GraphRepairResponse(graph_definition=repaired)


@router.post("/workflows", response_model=WorkflowResponse, status_code=201)
async def create_workflow(payload: WorkflowCreate, db: AsyncSession = Depends(get_db)):
    data = payload.model_dump()
    if hasattr(payload.graph_definition, "model_dump"):
        data["graph_definition"] = payload.graph_definition.model_dump()
    return await WorkflowService.create_workflow(db, data)


@router.get("/workflows/{workflow_id}", response_model=WorkflowResponse)
async def get_workflow(workflow_id: str, db: AsyncSession = Depends(get_db)):
    workflow = await WorkflowService.get_workflow(db, workflow_id)
    if not workflow:
        raise HTTPException(status_code=404, detail="Workflow not found")
    return workflow


@router.put("/workflows/{workflow_id}", response_model=WorkflowResponse)
async def update_workflow(workflow_id: str, payload: WorkflowUpdate, db: AsyncSession = Depends(get_db)):
    workflow = await WorkflowService.get_workflow(db, workflow_id)
    if not workflow:
        raise HTTPException(status_code=404, detail="Workflow not found")
    data = payload.model_dump(exclude_unset=True)
    if "graph_definition" in data and hasattr(payload.graph_definition, "model_dump"):
        data["graph_definition"] = payload.graph_definition.model_dump()
    return await WorkflowService.update_workflow(db, workflow, data)


@router.delete("/workflows/{workflow_id}", status_code=204)
async def delete_workflow(workflow_id: str, db: AsyncSession = Depends(get_db)):
    workflow = await WorkflowService.get_workflow(db, workflow_id)
    if not workflow:
        raise HTTPException(status_code=404, detail="Workflow not found")
    await WorkflowService.delete_workflow(db, workflow)


@router.get("/schedules", response_model=list[WorkflowScheduleResponse])
async def list_schedules(db: AsyncSession = Depends(get_db)):
    return await ScheduleService.list_schedules(db)


@router.get("/schedules/{workflow_id}", response_model=WorkflowScheduleResponse)
async def get_schedule(workflow_id: str, db: AsyncSession = Depends(get_db)):
    entry = await ScheduleService.get_schedule(db, workflow_id)
    if not entry:
        raise HTTPException(status_code=404, detail="Schedule not found")
    return entry


@router.patch("/schedules/{workflow_id}", response_model=WorkflowScheduleResponse)
async def update_schedule(
    workflow_id: str,
    payload: WorkflowScheduleUpdate,
    db: AsyncSession = Depends(get_db),
):
    workflow = await WorkflowService.get_workflow(db, workflow_id)
    if not workflow:
        raise HTTPException(status_code=404, detail="Workflow not found")
    try:
        return await ScheduleService.update_schedule(db, workflow, payload.model_dump(exclude_unset=True))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.delete("/schedules/{workflow_id}", status_code=204)
async def delete_schedule(workflow_id: str, db: AsyncSession = Depends(get_db)):
    workflow = await WorkflowService.get_workflow(db, workflow_id)
    if not workflow:
        raise HTTPException(status_code=404, detail="Workflow not found")
    await ScheduleService.delete_schedule(db, workflow)


@router.post("/workflows/{workflow_id}/runs", response_model=WorkflowRunResponse, status_code=202)
async def start_workflow_run(workflow_id: str, payload: WorkflowRunCreate, db: AsyncSession = Depends(get_db)):
    workflow = await WorkflowService.get_workflow(db, workflow_id)
    if not workflow:
        raise HTTPException(status_code=404, detail="Workflow not found")
    run = await RunService.create_run(db, workflow_id, payload.input_text)
    asyncio.create_task(execute_workflow_run(run.id, payload.channel_context))
    return run


@router.get("/runs", response_model=list[WorkflowRunResponse])
async def list_runs(workflow_id: str | None = None, db: AsyncSession = Depends(get_db)):
    return await RunService.list_runs(db, workflow_id)


@router.get("/runs/{run_id}", response_model=WorkflowRunResponse)
async def get_run(run_id: str, db: AsyncSession = Depends(get_db)):
    run = await RunService.get_run(db, run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    return run


@router.get("/runs/{run_id}/messages", response_model=list[AgentMessageResponse])
async def get_run_messages(run_id: str, db: AsyncSession = Depends(get_db)):
    return await RunService.get_messages(db, run_id)


@router.get("/runs/{run_id}/logs", response_model=list[RunLogResponse])
async def get_run_logs(run_id: str, db: AsyncSession = Depends(get_db)):
    return await RunService.get_logs(db, run_id)


@router.get("/runs/{run_id}/tokens", response_model=list[TokenUsageResponse])
async def get_run_tokens(run_id: str, db: AsyncSession = Depends(get_db)):
    return await RunService.get_token_usages(db, run_id)


@router.get("/messages", response_model=list[AgentMessageResponse])
async def get_all_messages(run_id: str | None = None, db: AsyncSession = Depends(get_db)):
    return await RunService.get_messages(db, run_id, newest_first=True)


@router.websocket("/ws/runs/{run_id}")
async def websocket_run_monitor(websocket: WebSocket, run_id: str):
    await websocket.accept()
    redis = await get_redis()
    pubsub = redis.pubsub()
    await pubsub.subscribe(f"run:{run_id}")
    try:
        while True:
            message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
            if message and message.get("data"):
                await websocket.send_text(message["data"])
            try:
                await asyncio.wait_for(websocket.receive_text(), timeout=0.01)
            except asyncio.TimeoutError:
                pass
    except WebSocketDisconnect:
        pass
    finally:
        await pubsub.unsubscribe(f"run:{run_id}")
        await pubsub.close()
