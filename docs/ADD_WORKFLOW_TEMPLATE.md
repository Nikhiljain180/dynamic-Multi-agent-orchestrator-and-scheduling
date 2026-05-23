# Adding a New Workflow Template

## Overview

Workflow templates are `Workflow` records with `is_template=True` and a `graph_definition` JSON blob. The runtime compiles them into LangGraph graphs via `build_graph_from_definition()`.

## Steps

### 1. Create agents

Use the Agents UI or API to create agents with appropriate roles, tools, and guardrails.

```bash
curl -X POST http://localhost:8000/api/agents \
  -H 'Content-Type: application/json' \
  -d '{
    "name": "My Agent",
    "role": "Specialist",
    "system_prompt": "You are a specialist...",
    "model": "gpt-4o-mini",
    "tools": ["web_search"]
  }'
```

### 2. Define the graph

```json
{
  "template_type": "my_custom_template",
  "entry_node_id": "step1",
  "nodes": [
    {"id": "step1", "agent_id": "<agent-uuid>", "label": "Step 1", "position": {"x": 100, "y": 100}},
    {"id": "step2", "agent_id": "<agent-uuid>", "label": "Step 2", "position": {"x": 350, "y": 100}}
  ],
  "edges": [
    {"id": "e1", "source": "step1", "target": "step2", "edge_type": "always"},
    {"id": "e2", "source": "step2", "target": "step1", "edge_type": "feedback", "condition": "needs_retry"}
  ]
}
```

### 3. (Optional) Add a dedicated graph builder

For complex routing, add a builder function in `backend/app/runtime/graph_builder.py`:

```python
def build_my_template_graph(agents: dict[str, Agent], db, run_id: str):
    # Define nodes and conditional edges
    ...
    return graph.compile()
```

Register it in `build_graph_from_definition()` when `template_type == "my_custom_template"`.

### 4. Seed or create via API

```bash
curl -X POST http://localhost:8000/api/workflows \
  -H 'Content-Type: application/json' \
  -d '{
    "name": "My Template",
    "description": "Description for UI",
    "is_template": true,
    "graph_definition": { ... }
  }'
```

### 5. Test

```bash
curl -X POST http://localhost:8000/api/workflows/<workflow-id>/runs \
  -H 'Content-Type: application/json' \
  -d '{"input_text": "Test input"}'
```

Monitor at `/monitor` or via `GET /api/runs/<run-id>/logs`.

## Template UI mapping

Some templates are channel-driven and should not expose manual run input or cron scheduling in the Workflows sidebar. Field visibility is controlled in `frontend/src/lib/workflowTemplateConfig.ts`:

| `template_type` | Run Input | Schedule | Manual Run |
|-----------------|-----------|----------|------------|
| `brief_summary` | yes | yes | yes |
| `research_pipeline` | yes | yes | yes |
| `telegram_triage` | no | no | no (Telegram channel) |
| *(custom / unset)* | yes | yes | yes |

When adding a channel-only template, register it in `TEMPLATE_UI_CONFIG` with `showRunInput: false`, `showSchedule: false`, and a `channelHint` message.

Saving a graph for a template without schedule support clears any existing `graph_definition.schedule` block.

## Graph repair

Routing repair is centralized in `backend/app/runtime/graph_repair.py` and applied automatically when graphs compile. Preview or normalize a graph via:

```bash
curl -X POST http://localhost:8000/api/workflows/repair-graph \
  -H 'Content-Type: application/json' \
  -d '{"graph_definition": { ... }}'
```

## Edge types

| Type | Behavior |
|------|----------|
| `always` | Unconditional transition |
| `if_condition` | Route based on node output content |
| `on_failure` | Route when node fails guardrails |
| `feedback` | Loop back for retry/revision |
