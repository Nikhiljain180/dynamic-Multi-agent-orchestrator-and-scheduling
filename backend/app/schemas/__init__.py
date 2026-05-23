from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.models import MessageRole, RunStatus


class AgentBase(BaseModel):
    name: str
    role: str
    system_prompt: str
    model: str = "llama-3.1-8b-instant"
    provider: str | None = None
    use_platform_api_key: bool = True
    tools: list[str] = Field(default_factory=list)
    channels: dict[str, Any] = Field(default_factory=dict)
    schedule: str | None = None
    memory_config: dict[str, Any] = Field(default_factory=dict)
    skills: list[str] = Field(default_factory=list)
    interaction_rules: str | None = None
    guardrails: dict[str, Any] = Field(default_factory=dict)


class AgentCreate(AgentBase):
    api_key: str | None = None


class AgentUpdate(BaseModel):
    name: str | None = None
    role: str | None = None
    system_prompt: str | None = None
    model: str | None = None
    provider: str | None = None
    use_platform_api_key: bool | None = None
    api_key: str | None = None
    tools: list[str] | None = None
    channels: dict[str, Any] | None = None
    schedule: str | None = None
    memory_config: dict[str, Any] | None = None
    skills: list[str] | None = None
    interaction_rules: str | None = None
    guardrails: dict[str, Any] | None = None


class AgentResponse(AgentBase):
    id: str
    api_key_hint: str | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class PlatformLLMSettings(BaseModel):
    provider: str
    model: str
    api_key_configured: bool
    api_key_hint: str | None = None
    groq_models: list[str] = Field(default_factory=list)
    openai_models: list[str] = Field(default_factory=list)
    ollama_models: list[str] = Field(default_factory=list)
    opencode_models: list[str] = Field(default_factory=list)
    providers: list[str] = Field(default_factory=list)


class WorkflowNode(BaseModel):
    id: str
    agent_id: str
    label: str
    position: dict[str, float] = Field(default_factory=dict)


class WorkflowEdge(BaseModel):
    id: str
    source: str
    target: str
    edge_type: str = "always"
    condition: str | None = None


class WorkflowScheduleDef(BaseModel):
    cron: str | None = None
    input_text: str | None = None
    enabled: bool | None = True


class WorkflowGraphDefinition(BaseModel):
    model_config = ConfigDict(extra="allow")

    template_type: str | None = None
    schedule: WorkflowScheduleDef | dict[str, Any] | None = None
    nodes: list[WorkflowNode] = Field(default_factory=list)
    edges: list[WorkflowEdge] = Field(default_factory=list)
    entry_node_id: str | None = None


class GraphRepairRequest(BaseModel):
    graph_definition: WorkflowGraphDefinition | dict[str, Any]


class GraphRepairResponse(BaseModel):
    graph_definition: dict[str, Any]


class WorkflowBase(BaseModel):
    name: str
    description: str | None = None
    is_template: bool = False
    graph_definition: WorkflowGraphDefinition | dict[str, Any] = Field(default_factory=dict)


class WorkflowCreate(WorkflowBase):
    pass


class WorkflowUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    graph_definition: WorkflowGraphDefinition | dict[str, Any] | None = None


class WorkflowResponse(WorkflowBase):
    id: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class WorkflowRunCreate(BaseModel):
    input_text: str
    channel_context: dict[str, Any] = Field(default_factory=dict)


class WorkflowRunResponse(BaseModel):
    id: str
    workflow_id: str
    status: RunStatus
    input_text: str
    output_text: str | None = None
    error: str | None = None
    total_tokens: int
    total_cost: float
    started_at: datetime | None = None
    completed_at: datetime | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class AgentMessageResponse(BaseModel):
    id: str
    run_id: str
    from_agent_id: str | None
    to_agent_id: str | None
    role: MessageRole
    content: str
    channel: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class RunLogResponse(BaseModel):
    id: str
    run_id: str
    agent_id: str | None
    level: str
    message: str
    created_at: datetime

    model_config = {"from_attributes": True}


class TokenUsageResponse(BaseModel):
    id: str
    run_id: str
    agent_id: str | None
    node_name: str
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    estimated_cost: float
    created_at: datetime

    model_config = {"from_attributes": True}


class ToolInfo(BaseModel):
    name: str
    description: str


class WorkflowScheduleResponse(BaseModel):
    workflow_id: str
    workflow_name: str
    description: str | None = None
    is_template: bool = False
    cron: str
    input_text: str = ""
    enabled: bool = True
    updated_at: datetime
    last_run_at: datetime | None = None


class WorkflowScheduleUpdate(BaseModel):
    enabled: bool | None = None
    cron: str | None = None
    input_text: str | None = None
