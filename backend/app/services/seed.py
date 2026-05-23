from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Agent, Workflow
from app.services import AgentService, WorkflowService

DEFAULT_MODEL = "llama-3.1-8b-instant"
LEGACY_MODELS = {"gpt-4o-mini", "gpt-4o", ""}

BRIEF_SUMMARY_GRAPH = {
    "template_type": "brief_summary",
    "entry_node_id": "brief",
    "nodes": [],
    "edges": [
        {"id": "e1", "source": "brief", "target": "summary", "edge_type": "always"},
    ],
}


async def _get_or_create_agent(db: AsyncSession, name: str, data: dict) -> Agent:
    result = await db.execute(select(Agent).where(Agent.name == name))
    existing = result.scalar_one_or_none()
    if existing:
        return existing
    return await AgentService.create_agent(db, data)


TRIAGE_SYSTEM_PROMPT = (
    "You classify customer support messages into billing, research, or technical intents. "
    "Respond with exactly one line starting with INTENT: billing, INTENT: research, or INTENT: technical, "
    "then a brief reason. Use INTENT: research when the user asks for investigation, learning, or background on a topic."
)


async def sync_triage_agent_prompt(db: AsyncSession) -> None:
    result = await db.execute(select(Agent).where(Agent.name == "Triage Agent"))
    agent = result.scalar_one_or_none()
    if not agent:
        return
    if "intent: research" not in agent.system_prompt.lower():
        agent.system_prompt = TRIAGE_SYSTEM_PROMPT
        await db.commit()


async def sync_legacy_agent_models(db: AsyncSession) -> None:
    result = await db.execute(select(Agent))
    changed = False
    for agent in result.scalars().all():
        if (not agent.provider or agent.provider == "openai") and (
            not agent.model or agent.model in LEGACY_MODELS
        ):
            agent.model = DEFAULT_MODEL
            changed = True
    if changed:
        await db.commit()


async def sync_brief_summary_template(db: AsyncSession) -> None:
    await sync_legacy_agent_models(db)
    await sync_triage_agent_prompt(db)
    brief = await _get_or_create_agent(
        db,
        "Quick Brief Agent",
        {
            "name": "Quick Brief Agent",
            "role": "Brief Specialist",
            "system_prompt": (
                "You create concise bullet-point briefs. Output only key points in short bullets. "
                "Stay under 150 words. No preamble."
            ),
            "model": DEFAULT_MODEL,
            "tools": [],
            "skills": ["summarization", "key point extraction"],
            "memory_config": {"short_term": True, "long_term": False},
            "guardrails": {"max_tokens": 200},
        },
    )
    summary = await _get_or_create_agent(
        db,
        "Executive Summary Agent",
        {
            "name": "Executive Summary Agent",
            "role": "Executive Summarizer",
            "system_prompt": (
                "You write polished executive summaries for business stakeholders. "
                "Use clear headings and stay around 250 words. Be direct and actionable."
            ),
            "model": DEFAULT_MODEL,
            "tools": [],
            "skills": ["executive writing", "synthesis"],
            "memory_config": {"short_term": True, "long_term": True},
            "guardrails": {"max_tokens": 350},
        },
    )

    graph = {
        **BRIEF_SUMMARY_GRAPH,
        "nodes": [
            {"id": "brief", "agent_id": brief.id, "label": "Quick Brief", "position": {"x": 100, "y": 120}},
            {"id": "summary", "agent_id": summary.id, "label": "Executive Summary", "position": {"x": 400, "y": 120}},
        ],
    }

    result = await db.execute(
        select(Workflow).where(
            Workflow.is_template.is_(True),
            Workflow.name.in_(["Research → Write → Review", "Quick Brief → Executive Summary"]),
        )
    )
    workflow = result.scalars().first()
    if workflow:
        workflow.name = "Quick Brief → Executive Summary"
        workflow.description = (
            "Two-agent linear pipeline: brief the topic, then produce a short executive summary (~250 words)."
        )
        workflow.graph_definition = graph
        await db.commit()
        return

    await WorkflowService.create_workflow(
        db,
        {
            "name": "Quick Brief → Executive Summary",
            "description": (
                "Two-agent linear pipeline: brief the topic, then produce a short executive summary (~250 words)."
            ),
            "is_template": True,
            "graph_definition": graph,
        },
    )


async def sync_template_metadata(db: AsyncSession) -> None:
    """Ensure seeded templates have template_type in graph_definition (legacy DB fix)."""
    patches = {
        "Quick Brief → Executive Summary": "brief_summary",
        "Research → Write → Review": "brief_summary",
        "Telegram Support Triage": "telegram_triage",
    }
    result = await db.execute(select(Workflow).where(Workflow.name.in_(list(patches.keys()))))
    changed = False
    for workflow in result.scalars().all():
        expected = patches.get(workflow.name)
        if not expected:
            continue
        graph = dict(workflow.graph_definition or {})
        if graph.get("template_type") != expected:
            graph["template_type"] = expected
            workflow.graph_definition = graph
            changed = True
    if changed:
        await db.commit()


async def seed_templates(db: AsyncSession) -> None:
    await sync_legacy_agent_models(db)
    existing = await db.execute(select(Workflow).where(Workflow.is_template.is_(True)))
    if existing.scalars().first():
        await sync_brief_summary_template(db)
        await sync_template_metadata(db)
        return

    agents_data = [
        {
            "name": "Quick Brief Agent",
            "role": "Brief Specialist",
            "system_prompt": (
                "You create concise bullet-point briefs. Output only key points in short bullets. "
                "Stay under 150 words. No preamble."
            ),
            "model": DEFAULT_MODEL,
            "tools": [],
            "skills": ["summarization", "key point extraction"],
            "memory_config": {"short_term": True, "long_term": False},
            "guardrails": {"max_tokens": 200},
        },
        {
            "name": "Executive Summary Agent",
            "role": "Executive Summarizer",
            "system_prompt": (
                "You write polished executive summaries for business stakeholders. "
                "Use clear headings and stay around 250 words. Be direct and actionable."
            ),
            "model": DEFAULT_MODEL,
            "tools": [],
            "skills": ["executive writing", "synthesis"],
            "memory_config": {"short_term": True, "long_term": True},
            "guardrails": {"max_tokens": 350},
        },
        {
            "name": "Triage Agent",
            "role": "Triage Specialist",
            "system_prompt": TRIAGE_SYSTEM_PROMPT,
            "model": DEFAULT_MODEL,
            "tools": [],
            "channels": {"telegram": True},
            "skills": ["intent classification", "customer support"],
            "guardrails": {"max_tokens": 200},
        },
        {
            "name": "Billing Agent",
            "role": "Billing Specialist",
            "system_prompt": "You handle billing inquiries including invoices, payments, and charges.",
            "model": DEFAULT_MODEL,
            "tools": [],
            "skills": ["billing support", "invoice lookup"],
            "guardrails": {"max_tokens": 500},
        },
        {
            "name": "Technical Agent",
            "role": "Technical Specialist",
            "system_prompt": "You handle technical support inquiries including bugs, errors, and configuration issues.",
            "model": DEFAULT_MODEL,
            "tools": [],
            "skills": ["troubleshooting", "technical support"],
            "guardrails": {"max_tokens": 500},
        },
        {
            "name": "Responder Agent",
            "role": "Responder",
            "system_prompt": "You format specialist responses into friendly customer-facing replies.",
            "model": DEFAULT_MODEL,
            "tools": ["notify_human"],
            "channels": {"telegram": True},
            "skills": ["customer communication"],
            "guardrails": {"max_tokens": 400, "allowed_tools": ["notify_human"]},
        },
    ]

    created_agents: dict[str, Agent] = {}
    for data in agents_data:
        agent = await AgentService.create_agent(db, data)
        role = data["role"].lower()
        if "brief" in role:
            key = "brief"
        elif "executive" in role or "summar" in role:
            key = "summary"
        elif "triage" in role:
            key = "triage"
        elif "billing" in role:
            key = "billing"
        elif "technical" in role:
            key = "technical"
        elif "respond" in role:
            key = "responder"
        else:
            key = data["name"].lower().replace(" ", "_")
        created_agents[key] = agent

    brief_graph = {
        **BRIEF_SUMMARY_GRAPH,
        "nodes": [
            {"id": "brief", "agent_id": created_agents["brief"].id, "label": "Quick Brief", "position": {"x": 100, "y": 120}},
            {"id": "summary", "agent_id": created_agents["summary"].id, "label": "Executive Summary", "position": {"x": 400, "y": 120}},
        ],
    }

    triage_graph = {
        "template_type": "telegram_triage",
        "entry_node_id": "triage",
        "nodes": [
            {"id": "triage", "agent_id": created_agents["triage"].id, "label": "Triage", "position": {"x": 100, "y": 150}},
            {"id": "billing", "agent_id": created_agents["billing"].id, "label": "Billing", "position": {"x": 350, "y": 50}},
            {"id": "technical", "agent_id": created_agents["technical"].id, "label": "Technical", "position": {"x": 350, "y": 250}},
            {"id": "responder", "agent_id": created_agents["responder"].id, "label": "Responder", "position": {"x": 600, "y": 150}},
        ],
        "edges": [
            {"id": "e1", "source": "triage", "target": "billing", "edge_type": "if_condition", "condition": "INTENT: billing"},
            {"id": "e2", "source": "triage", "target": "technical", "edge_type": "if_condition", "condition": "INTENT: technical"},
            {"id": "e3", "source": "billing", "target": "responder", "edge_type": "always"},
            {"id": "e4", "source": "technical", "target": "responder", "edge_type": "always"},
        ],
    }

    await WorkflowService.create_workflow(
        db,
        {
            "name": "Quick Brief → Executive Summary",
            "description": (
                "Two-agent linear pipeline: brief the topic, then produce a short executive summary (~250 words)."
            ),
            "is_template": True,
            "graph_definition": brief_graph,
        },
    )

    await WorkflowService.create_workflow(
        db,
        {
            "name": "Telegram Support Triage",
            "description": "Routes Telegram messages through triage to billing or technical specialists, then responds to the user.",
            "is_template": True,
            "graph_definition": triage_graph,
        },
    )
