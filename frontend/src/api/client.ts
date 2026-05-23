const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${API_URL}${path}`, {
    headers: { 'Content-Type': 'application/json', ...options?.headers },
    ...options,
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(text || res.statusText);
  }
  if (res.status === 204) return undefined as T;
  return res.json();
}

export interface Agent {
  id: string;
  name: string;
  role: string;
  system_prompt: string;
  model: string;
  provider?: string | null;
  use_platform_api_key: boolean;
  api_key_hint?: string | null;
  tools: string[];
  channels: Record<string, unknown>;
  schedule?: string | null;
  memory_config: Record<string, unknown>;
  skills: string[];
  interaction_rules?: string | null;
  guardrails: Record<string, unknown>;
  created_at: string;
  updated_at: string;
}

export interface AgentPayload extends Partial<Agent> {
  api_key?: string | null;
}

export interface PlatformLLMSettings {
  provider: string;
  model: string;
  api_key_configured: boolean;
  api_key_hint?: string | null;
  groq_models: string[];
  openai_models: string[];
  ollama_models: string[];
  opencode_models: string[];
  providers: string[];
}

export interface Workflow {
  id: string;
  name: string;
  description?: string | null;
  is_template: boolean;
  graph_definition: GraphDefinition;
  created_at: string;
  updated_at: string;
}

export interface WorkflowSchedule {
  cron?: string | null;
  input_text?: string | null;
  enabled?: boolean;
}

export interface WorkflowScheduleEntry {
  workflow_id: string;
  workflow_name: string;
  description?: string | null;
  is_template: boolean;
  cron: string;
  input_text: string;
  enabled: boolean;
  updated_at: string;
  last_run_at?: string | null;
}

export interface GraphDefinition {
  template_type?: string;
  entry_node_id?: string;
  nodes: WorkflowNode[];
  edges: WorkflowEdge[];
  schedule?: WorkflowSchedule;
}

export interface WorkflowNode {
  id: string;
  agent_id: string;
  label: string;
  position: { x: number; y: number };
}

export interface WorkflowEdge {
  id: string;
  source: string;
  target: string;
  edge_type: string;
  condition?: string | null;
}

export interface WorkflowRun {
  id: string;
  workflow_id: string;
  status: 'queued' | 'running' | 'completed' | 'failed';
  input_text: string;
  output_text?: string | null;
  error?: string | null;
  total_tokens: number;
  total_cost: number;
  started_at?: string | null;
  completed_at?: string | null;
  created_at: string;
}

export interface AgentMessage {
  id: string;
  run_id: string;
  from_agent_id?: string | null;
  to_agent_id?: string | null;
  role: string;
  content: string;
  channel?: string | null;
  created_at: string;
}

export interface RunLog {
  id: string;
  run_id: string;
  agent_id?: string | null;
  level: string;
  message: string;
  created_at: string;
}

export interface TokenUsage {
  id: string;
  run_id: string;
  agent_id?: string | null;
  node_name: string;
  prompt_tokens: number;
  completion_tokens: number;
  total_tokens: number;
  estimated_cost: number;
  created_at: string;
}

export interface ToolInfo {
  name: string;
  description: string;
}

export const api = {
  getPlatformLLMSettings: () => request<PlatformLLMSettings>('/api/platform/llm-settings'),
  listAgents: () => request<Agent[]>('/api/agents'),
  getAgent: (id: string) => request<Agent>(`/api/agents/${id}`),
  createAgent: (data: AgentPayload) => request<Agent>('/api/agents', { method: 'POST', body: JSON.stringify(data) }),
  updateAgent: (id: string, data: AgentPayload) => request<Agent>(`/api/agents/${id}`, { method: 'PUT', body: JSON.stringify(data) }),
  deleteAgent: (id: string) => request<void>(`/api/agents/${id}`, { method: 'DELETE' }),
  listTools: () => request<ToolInfo[]>('/api/tools'),
  repairWorkflowGraph: (graph_definition: GraphDefinition) =>
    request<{ graph_definition: GraphDefinition }>('/api/workflows/repair-graph', {
      method: 'POST',
      body: JSON.stringify({ graph_definition }),
    }).then((response) => response.graph_definition),
  listWorkflows: () => request<Workflow[]>('/api/workflows'),
  getWorkflow: (id: string) => request<Workflow>(`/api/workflows/${id}`),
  createWorkflow: (data: Partial<Workflow>) => request<Workflow>('/api/workflows', { method: 'POST', body: JSON.stringify(data) }),
  updateWorkflow: (id: string, data: Partial<Workflow>) => request<Workflow>(`/api/workflows/${id}`, { method: 'PUT', body: JSON.stringify(data) }),
  deleteWorkflow: (id: string) => request<void>(`/api/workflows/${id}`, { method: 'DELETE' }),
  startRun: (workflowId: string, input_text: string) =>
    request<WorkflowRun>(`/api/workflows/${workflowId}/runs`, {
      method: 'POST',
      body: JSON.stringify({ input_text }),
    }),
  listRuns: (workflowId?: string) =>
    request<WorkflowRun[]>(`/api/runs${workflowId ? `?workflow_id=${workflowId}` : ''}`),
  getRun: (id: string) => request<WorkflowRun>(`/api/runs/${id}`),
  getRunMessages: (id: string) => request<AgentMessage[]>(`/api/runs/${id}/messages`),
  getRunLogs: (id: string) => request<RunLog[]>(`/api/runs/${id}/logs`),
  getRunTokens: (id: string) => request<TokenUsage[]>(`/api/runs/${id}/tokens`),
  getAllMessages: (runId?: string) =>
    request<AgentMessage[]>(`/api/messages${runId ? `?run_id=${runId}` : ''}`),
  listSchedules: () => request<WorkflowScheduleEntry[]>('/api/schedules'),
  getSchedule: (workflowId: string) => request<WorkflowScheduleEntry>(`/api/schedules/${workflowId}`),
  updateSchedule: (workflowId: string, data: Partial<Pick<WorkflowScheduleEntry, 'enabled' | 'cron' | 'input_text'>>) =>
    request<WorkflowScheduleEntry>(`/api/schedules/${workflowId}`, {
      method: 'PATCH',
      body: JSON.stringify(data),
    }),
  deleteSchedule: (workflowId: string) =>
    request<void>(`/api/schedules/${workflowId}`, { method: 'DELETE' }),
};

export function wsUrl(runId: string) {
  const base = API_URL.replace('http', 'ws');
  return `${base}/api/ws/runs/${runId}`;
}

export function modelsForProvider(settings: PlatformLLMSettings, provider: string | null | undefined): string[] {
  switch (provider || settings.provider) {
    case 'groq':
      return settings.groq_models;
    case 'openai':
      return settings.openai_models;
    case 'ollama':
      return settings.ollama_models;
    case 'opencode':
      return settings.opencode_models;
    default:
      return settings.groq_models;
  }
}

const LEGACY_DEFAULT_MODELS = new Set(['gpt-4o-mini', '']);

export function effectiveProvider(agent: Agent, platform: PlatformLLMSettings | null): string {
  return agent.provider || platform?.provider || 'groq';
}

export function effectiveModel(agent: Agent, platform: PlatformLLMSettings | null): string {
  const provider = effectiveProvider(agent, platform);
  const platformProvider = platform?.provider || 'groq';

  if (agent.provider && agent.provider !== platformProvider && agent.model) {
    return agent.model;
  }

  if (platform?.model) {
    return platform.model;
  }

  if (agent.model && !LEGACY_DEFAULT_MODELS.has(agent.model)) {
    return agent.model;
  }

  if (platform) {
    const options = modelsForProvider(platform, provider);
    if (options.length) return options[0];
  }

  return agent.model || 'llama-3.1-8b-instant';
}

export function displayAgentLLM(agent: Agent, platform: PlatformLLMSettings | null): string {
  return `${effectiveProvider(agent, platform)} · ${effectiveModel(agent, platform)}`;
}

export function agentNodeSubtitle(agent: Agent, platform: PlatformLLMSettings | null): string {
  return `${agent.role} · ${displayAgentLLM(agent, platform)}`;
}
