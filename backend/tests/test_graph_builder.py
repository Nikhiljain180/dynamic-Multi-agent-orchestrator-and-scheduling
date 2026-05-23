import pytest

from app.models import Agent
from app.runtime.graph_builder import build_graph_from_definition
from app.runtime.graph_repair import (
    match_classifier_intent,
    match_user_intent,
    repair_misrouted_conditions,
)


def test_repair_misrouted_conditions_fixes_research_branch():
    agents_by_id = {
        "a1": Agent(
            id="a1", name="Triage Agent", role="Triage Specialist", system_prompt="triage", model="llama-3.1-8b-instant"
        ),
        "a2": Agent(
            id="a2", name="Research Agent", role="Research Specialist", system_prompt="research", model="llama-3.1-8b-instant"
        ),
        "a3": Agent(
            id="a3", name="Technical Agent", role="Technical Specialist", system_prompt="technical", model="llama-3.1-8b-instant"
        ),
    }
    graph_def = {
        "nodes": [
            {"id": "triage", "agent_id": "a1", "label": "Triage", "position": {"x": 0, "y": 0}},
            {"id": "node-research", "agent_id": "a2", "label": "Research Agent", "position": {"x": 0, "y": 0}},
            {"id": "technical", "agent_id": "a3", "label": "Technical", "position": {"x": 0, "y": 0}},
        ],
        "edges": [
            {
                "id": "e1",
                "source": "triage",
                "target": "node-research",
                "edge_type": "if_condition",
                "condition": "INTENT: technical",
            },
            {"id": "e2", "source": "triage", "target": "technical", "edge_type": "always", "condition": None},
        ],
    }
    repaired = repair_misrouted_conditions(graph_def, agents_by_id)
    research_edge = next(e for e in repaired["edges"] if e["id"] == "e1")
    assert research_edge["condition"] == "INTENT: research"
    assert match_user_intent("can you do some research on SHAP", "INTENT: research")
    assert not match_user_intent("my app keeps crashing", "INTENT: research")


def test_repair_misrouted_conditions_uses_custom_agent_metadata():
    agents_by_id = {
        "a1": Agent(
            id="a1", name="Classifier", role="Routing Specialist", system_prompt="route", model="llama-3.1-8b-instant"
        ),
        "a2": Agent(
            id="a2", name="SHAP Explorer", role="Investigation", system_prompt="explore", model="llama-3.1-8b-instant"
        ),
        "a3": Agent(
            id="a3", name="Fallback Handler", role="General Support", system_prompt="help", model="llama-3.1-8b-instant"
        ),
    }
    graph_def = {
        "nodes": [
            {"id": "router", "agent_id": "a1", "label": "Classifier", "position": {"x": 0, "y": 0}},
            {"id": "shap", "agent_id": "a2", "label": "SHAP Explorer", "position": {"x": 0, "y": 0}},
            {"id": "fallback", "agent_id": "a3", "label": "Fallback Handler", "position": {"x": 0, "y": 0}},
        ],
        "edges": [
            {
                "id": "e1",
                "source": "router",
                "target": "shap",
                "edge_type": "if_condition",
                "condition": "INTENT: technical",
            },
            {"id": "e2", "source": "router", "target": "fallback", "edge_type": "always", "condition": None},
        ],
    }
    repaired = repair_misrouted_conditions(graph_def, agents_by_id)
    shap_edge = next(e for e in repaired["edges"] if e["id"] == "e1")
    assert shap_edge["condition"] == "INTENT: shap"


def test_repair_multi_always_branches_restores_conditional_routing():
    agents_by_id = {
        "a1": Agent(
            id="a1", name="Triage Agent", role="Triage Specialist", system_prompt="triage", model="llama-3.1-8b-instant"
        ),
        "a2": Agent(
            id="a2", name="Research Agent", role="Research Specialist", system_prompt="research", model="llama-3.1-8b-instant"
        ),
        "a3": Agent(
            id="a3", name="Technical Agent", role="Technical Specialist", system_prompt="technical", model="llama-3.1-8b-instant"
        ),
    }
    graph_def = {
        "nodes": [
            {"id": "triage", "agent_id": "a1", "label": "Triage", "position": {"x": 0, "y": 0}},
            {"id": "node-research", "agent_id": "a2", "label": "Research Agent", "position": {"x": 0, "y": 0}},
            {"id": "technical", "agent_id": "a3", "label": "Technical", "position": {"x": 0, "y": 0}},
        ],
        "edges": [
            {"id": "e1", "source": "triage", "target": "node-research", "edge_type": "always", "condition": None},
            {"id": "e2", "source": "triage", "target": "technical", "edge_type": "always", "condition": None},
        ],
    }
    repaired = repair_misrouted_conditions(graph_def, agents_by_id)
    research_edge = next(e for e in repaired["edges"] if e["id"] == "e1")
    technical_edge = next(e for e in repaired["edges"] if e["id"] == "e2")
    assert research_edge["edge_type"] == "if_condition"
    assert research_edge["condition"] == "INTENT: research"
    assert technical_edge["edge_type"] == "always"
    assert technical_edge["condition"] is None


@pytest.mark.asyncio
async def test_dual_always_triage_graph_routes_research_without_parallel_fanout(db_session):
    agents_by_id = {
        f"a{i}": Agent(
            id=f"a{i}",
            name=name,
            role=role,
            system_prompt="prompt",
            model="llama-3.1-8b-instant",
        )
        for i, (name, role) in enumerate(
            [
                ("Triage Agent", "Triage Specialist"),
                ("Research Agent", "Research Specialist"),
                ("Technical Agent", "Technical Specialist"),
                ("Responder Agent", "Responder"),
            ],
            start=1,
        )
    }
    graph_def = {
        "entry_node_id": "triage",
        "nodes": [
            {"id": "triage", "agent_id": "a1", "label": "Triage", "position": {"x": 0, "y": 0}},
            {"id": "node-research", "agent_id": "a2", "label": "Research Agent", "position": {"x": 0, "y": 0}},
            {"id": "technical", "agent_id": "a3", "label": "Technical", "position": {"x": 0, "y": 0}},
            {"id": "responder", "agent_id": "a4", "label": "Responder", "position": {"x": 0, "y": 0}},
        ],
        "edges": [
            {"id": "e1", "source": "triage", "target": "node-research", "edge_type": "always", "condition": None},
            {"id": "e2", "source": "triage", "target": "technical", "edge_type": "always", "condition": None},
            {"id": "e3", "source": "node-research", "target": "responder", "edge_type": "always", "condition": None},
            {"id": "e4", "source": "technical", "target": "responder", "edge_type": "always", "condition": None},
        ],
    }
    graph = build_graph_from_definition(graph_def, agents_by_id, db_session, "run-dual-always", "Telegram Support Triage")
    compiled_edges = [e for e in graph.get_graph().edges if e.source == "triage"]
    assert compiled_edges
    assert all(edge.conditional for edge in compiled_edges)


@pytest.mark.asyncio
async def test_brief_summary_graph_compiles(db_session):
    agents = {
        "brief": Agent(
            id="a1", name="Brief", role="Brief Specialist", system_prompt="brief", model="llama-3.1-8b-instant"
        ),
        "summary": Agent(
            id="a2", name="Summary", role="Executive Summarizer", system_prompt="summary", model="llama-3.1-8b-instant"
        ),
    }
    graph_def = {
        "template_type": "brief_summary",
        "nodes": [
            {"id": "brief", "agent_id": "a1", "label": "Quick Brief", "position": {"x": 0, "y": 0}},
            {"id": "summary", "agent_id": "a2", "label": "Executive Summary", "position": {"x": 0, "y": 0}},
        ],
        "edges": [],
    }
    agents_by_id = {a.id: a for a in agents.values()}
    graph = build_graph_from_definition(graph_def, agents_by_id, db_session, "run-1")
    assert graph is not None


@pytest.mark.asyncio
async def test_triage_graph_compiles(db_session):
    agents_by_id = {
        f"a{i}": Agent(
            id=f"a{i}",
            name=f"Agent {i}",
            role=role,
            system_prompt="prompt",
            model="llama-3.1-8b-instant",
        )
        for i, role in enumerate(["Triage", "Billing", "Technical", "Responder"], start=1)
    }
    graph_def = {
        "template_type": "telegram_triage",
        "nodes": [
            {"id": "triage", "agent_id": "a1", "label": "Triage", "position": {"x": 0, "y": 0}},
            {"id": "billing", "agent_id": "a2", "label": "Billing", "position": {"x": 0, "y": 0}},
            {"id": "technical", "agent_id": "a3", "label": "Technical", "position": {"x": 0, "y": 0}},
            {"id": "responder", "agent_id": "a4", "label": "Responder", "position": {"x": 0, "y": 0}},
        ],
        "edges": [],
    }
    graph = build_graph_from_definition(graph_def, agents_by_id, db_session, "run-2")
    assert graph is not None


@pytest.mark.asyncio
async def test_generic_triage_if_edges_compile_without_duplicate_route(db_session):
    agents_by_id = {
        f"a{i}": Agent(
            id=f"a{i}",
            name=f"Agent {i}",
            role=role,
            system_prompt="prompt",
            model="llama-3.1-8b-instant",
        )
        for i, role in enumerate(["Triage", "Billing", "Technical", "Responder"], start=1)
    }
    graph_def = {
        "entry_node_id": "triage",
        "nodes": [
            {"id": "triage", "agent_id": "a1", "label": "Triage", "position": {"x": 0, "y": 0}},
            {"id": "billing", "agent_id": "a2", "label": "Billing", "position": {"x": 0, "y": 0}},
            {"id": "technical", "agent_id": "a3", "label": "Technical", "position": {"x": 0, "y": 0}},
            {"id": "responder", "agent_id": "a4", "label": "Responder", "position": {"x": 0, "y": 0}},
        ],
        "edges": [
            {"id": "e1", "source": "triage", "target": "billing", "edge_type": "if_condition", "condition": "INTENT: billing"},
            {"id": "e2", "source": "triage", "target": "technical", "edge_type": "if_condition", "condition": "INTENT: technical"},
            {"id": "e3", "source": "billing", "target": "responder", "edge_type": "always", "condition": None},
            {"id": "e4", "source": "technical", "target": "responder", "edge_type": "always", "condition": None},
        ],
    }
    graph = build_graph_from_definition(graph_def, agents_by_id, db_session, "run-3")
    assert graph is not None


@pytest.mark.asyncio
async def test_generic_graph_ignores_dangling_edges(db_session):
    agents_by_id = {
        "a1": Agent(
            id="a1",
            name="Brief",
            role="Brief Specialist",
            system_prompt="prompt",
            model="llama-3.1-8b-instant",
        ),
        "a2": Agent(
            id="a2",
            name="Summary",
            role="Executive Summarizer",
            system_prompt="prompt",
            model="llama-3.1-8b-instant",
        ),
    }
    graph_def = {
        "entry_node_id": "brief",
        "nodes": [
            {"id": "brief", "agent_id": "a1", "label": "Brief", "position": {"x": 0, "y": 0}},
            {"id": "summary", "agent_id": "a2", "label": "Summary", "position": {"x": 0, "y": 0}},
        ],
        "edges": [
            {"id": "e1", "source": "brief", "target": "summary", "edge_type": "always", "condition": None},
            {"id": "e2", "source": "node-1779559821372", "target": "summary", "edge_type": "always", "condition": None},
        ],
    }
    graph = build_graph_from_definition(graph_def, agents_by_id, db_session, "run-4")
    assert graph is not None


@pytest.mark.asyncio
async def test_default_triage_template_uses_dedicated_builder(db_session):
    agents_by_id = {
        f"a{i}": Agent(
            id=f"a{i}",
            name=f"Agent {i}",
            role=role,
            system_prompt="prompt",
            model="llama-3.1-8b-instant",
        )
        for i, role in enumerate(["Triage", "Billing", "Technical", "Responder"], start=1)
    }
    graph_def = {
        "template_type": "telegram_triage",
        "entry_node_id": "triage",
        "nodes": [
            {"id": "triage", "agent_id": "a1", "label": "Triage", "position": {"x": 0, "y": 0}},
            {"id": "billing", "agent_id": "a2", "label": "Billing", "position": {"x": 0, "y": 0}},
            {"id": "technical", "agent_id": "a3", "label": "Technical", "position": {"x": 0, "y": 0}},
            {"id": "responder", "agent_id": "a4", "label": "Responder", "position": {"x": 0, "y": 0}},
        ],
        "edges": [
            {"id": "e1", "source": "triage", "target": "billing", "edge_type": "if_condition", "condition": "INTENT: billing"},
            {"id": "e2", "source": "triage", "target": "technical", "edge_type": "if_condition", "condition": "INTENT: technical"},
            {"id": "e3", "source": "billing", "target": "responder", "edge_type": "always", "condition": None},
            {"id": "e4", "source": "technical", "target": "responder", "edge_type": "always", "condition": None},
        ],
    }
    graph = build_graph_from_definition(
        graph_def,
        agents_by_id,
        db_session,
        "run-5",
        workflow_name="Telegram Support Triage",
    )
    assert graph is not None


@pytest.mark.asyncio
async def test_customized_triage_graph_uses_generic_builder(db_session):
    agents_by_id = {
        f"a{i}": Agent(
            id=f"a{i}",
            name=f"Agent {i}",
            role=role,
            system_prompt="prompt",
            model="llama-3.1-8b-instant",
        )
        for i, role in enumerate(["Triage", "Billing", "Technical", "Responder", "Research"], start=1)
    }
    graph_def = {
        "template_type": "telegram_triage",
        "entry_node_id": "triage",
        "nodes": [
            {"id": "triage", "agent_id": "a1", "label": "Triage", "position": {"x": 0, "y": 0}},
            {"id": "technical", "agent_id": "a3", "label": "Technical", "position": {"x": 0, "y": 0}},
            {"id": "responder", "agent_id": "a4", "label": "Responder", "position": {"x": 0, "y": 0}},
            {"id": "research", "agent_id": "a5", "label": "Research Agent", "position": {"x": 0, "y": 0}},
        ],
        "edges": [
            {"id": "e1", "source": "triage", "target": "research", "edge_type": "if_condition", "condition": "INTENT: research"},
            {"id": "e2", "source": "triage", "target": "technical", "edge_type": "always", "condition": None},
            {"id": "e3", "source": "technical", "target": "responder", "edge_type": "always", "condition": None},
            {"id": "e4", "source": "research", "target": "responder", "edge_type": "always", "condition": None},
        ],
    }
    graph = build_graph_from_definition(
        graph_def,
        agents_by_id,
        db_session,
        "run-5b",
        workflow_name="Telegram Support Triage",
    )
    assert graph is not None


@pytest.mark.asyncio
async def test_telegram_workflow_with_stale_edges_uses_generic_builder(db_session):
    agents_by_id = {
        f"a{i}": Agent(
            id=f"a{i}",
            name=f"Agent {i}",
            role=role,
            system_prompt="prompt",
            model="llama-3.1-8b-instant",
        )
        for i, role in enumerate(["Triage", "Billing", "Technical", "Responder"], start=1)
    }
    graph_def = {
        "entry_node_id": "triage",
        "nodes": [
            {"id": "triage", "agent_id": "a1", "label": "Triage", "position": {"x": 0, "y": 0}},
            {"id": "billing", "agent_id": "a2", "label": "Billing", "position": {"x": 0, "y": 0}},
            {"id": "technical", "agent_id": "a3", "label": "Technical", "position": {"x": 0, "y": 0}},
            {"id": "responder", "agent_id": "a4", "label": "Responder", "position": {"x": 0, "y": 0}},
        ],
        "edges": [
            {"id": "e-stale", "source": "node-1779559821372", "target": "billing", "edge_type": "always", "condition": None},
        ],
    }
    graph = build_graph_from_definition(
        graph_def,
        agents_by_id,
        db_session,
        "run-5",
        workflow_name="Telegram Support Triage",
    )
    assert graph is not None


@pytest.mark.asyncio
async def test_telegram_workflow_with_missing_billing_node_uses_generic_builder(db_session):
    agents_by_id = {
        f"a{i}": Agent(
            id=f"a{i}",
            name=f"Agent {i}",
            role=role,
            system_prompt="prompt",
            model="llama-3.1-8b-instant",
        )
        for i, role in enumerate(["Triage", "Billing", "Technical", "Responder"], start=1)
    }
    graph_def = {
        "entry_node_id": "triage",
        "nodes": [
            {"id": "triage", "agent_id": "a1", "label": "Triage", "position": {"x": 0, "y": 0}},
            {"id": "technical", "agent_id": "a3", "label": "Technical", "position": {"x": 0, "y": 0}},
            {"id": "responder", "agent_id": "a4", "label": "Responder", "position": {"x": 0, "y": 0}},
        ],
        "edges": [
            {"id": "e2", "source": "triage", "target": "technical", "edge_type": "if_condition", "condition": "INTENT: technical"},
        ],
    }
    graph = build_graph_from_definition(
        graph_def,
        agents_by_id,
        db_session,
        "run-6",
        workflow_name="Telegram Support Triage",
    )
    assert graph is not None
