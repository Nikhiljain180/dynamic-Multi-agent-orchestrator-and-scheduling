"""Graph definition sanitization and routing repair (single source of truth)."""

import re
from collections import defaultdict
from typing import Any

from app.models import Agent


def intent_from_condition(condition: str | None) -> str | None:
    if not condition or ":" not in condition:
        return None
    intent = condition.split(":", 1)[1].strip().lower()
    return intent or None


def match_user_intent(input_text: str, condition: str | None) -> bool:
    intent = intent_from_condition(condition)
    if not intent:
        return False
    return intent in input_text.lower()


def match_classifier_intent(output: str, condition: str | None) -> bool:
    if not condition:
        return False
    text = output.lower()
    cond = condition.lower()
    if cond in text:
        return True
    intent = intent_from_condition(condition)
    if intent and intent in text:
        return True
    return False


def match_edge_condition(output: str, condition: str | None, input_text: str = "") -> bool:
    if not condition:
        return False
    text = f"{output}\n{input_text}".lower()
    cond = condition.lower()
    if cond in text:
        return True
    intent = intent_from_condition(condition)
    if intent and intent in text:
        return True
    return False


_SKIP_INTENT_TOKENS = frozenset({"agent", "specialist", "support", "customer", "service", "and", "the"})
_RESPONDER_HINTS = frozenset({"respond", "responder", "reply"})
_FALLBACK_HINTS = ("technical", "general", "support", "fallback", "default", "billing")


def infer_intent_from_text(text: str) -> str | None:
    lower = text.lower()
    if any(hint in lower for hint in _RESPONDER_HINTS):
        return None
    for token in re.findall(r"[a-z]+", lower):
        if len(token) > 2 and token not in _SKIP_INTENT_TOKENS:
            return token
    return None


def infer_intent_from_agent(agent: Agent) -> str | None:
    return infer_intent_from_text(f"{agent.name} {agent.role}")


def infer_intent_from_node(node: dict, agent: Agent | None = None) -> str | None:
    if agent:
        return infer_intent_from_agent(agent)
    return infer_intent_from_text(node.get("label", ""))


def is_classifier_node(node: dict, agent: Agent | None = None) -> bool:
    text = f"{node.get('label', '')} {agent.name if agent else ''} {agent.role if agent else ''}".lower()
    return any(hint in text for hint in ("triage", "classif", "router", "routing", "intent"))


def is_routing_hub(source_id: str, edges: list[dict]) -> bool:
    from_source = [edge for edge in edges if edge.get("source") == source_id]
    if len(from_source) <= 1:
        return False
    return any(edge.get("edge_type") == "if_condition" for edge in from_source)


def _pick_fallback_always_edge(
    always_edges: list[dict],
    node_by_id: dict[str, dict],
    agents_by_id: dict[str, Agent],
) -> dict:
    if len(always_edges) == 1:
        return always_edges[0]

    best_edge = always_edges[-1]
    best_score = -1
    for edge in always_edges:
        target_node = node_by_id.get(edge.get("target", ""))
        if not target_node:
            continue
        target_agent = agents_by_id.get(target_node.get("agent_id"))
        if infer_intent_from_node(target_node, target_agent) is None:
            return edge
        text = (
            f"{target_node.get('label', '')} {target_agent.name if target_agent else ''} "
            f"{target_agent.role if target_agent else ''}"
        ).lower()
        score = 0
        for idx, hint in enumerate(_FALLBACK_HINTS):
            if hint in text:
                score = len(_FALLBACK_HINTS) - idx
                break
        if score > best_score:
            best_score = score
            best_edge = edge
    return best_edge


def _repair_multi_always_branches(
    edges: list[dict],
    node_by_id: dict[str, dict],
    agents_by_id: dict[str, Agent],
) -> list[dict]:
    by_source: dict[str, list[dict]] = defaultdict(list)
    for edge in edges:
        by_source[edge.get("source", "")].append(edge)

    for source_id, from_source in by_source.items():
        always_edges = [edge for edge in from_source if edge.get("edge_type", "always") == "always"]
        if len(always_edges) < 2:
            continue

        fallback = _pick_fallback_always_edge(always_edges, node_by_id, agents_by_id)
        fallback_target = fallback.get("target")

        for idx, edge in enumerate(edges):
            if edge.get("source") != source_id or edge.get("edge_type", "always") != "always":
                continue
            if edge.get("target") == fallback_target:
                continue

            target_node = node_by_id.get(edge.get("target", ""))
            if not target_node:
                continue
            target_agent = agents_by_id.get(target_node.get("agent_id"))
            expected_intent = infer_intent_from_node(target_node, target_agent)
            if expected_intent:
                edges[idx] = {
                    **edge,
                    "edge_type": "if_condition",
                    "condition": f"INTENT: {expected_intent}",
                }

    return edges


def repair_misrouted_conditions(
    graph_definition: dict,
    agents_by_id: dict[str, Agent] | None = None,
) -> dict:
    agents_by_id = agents_by_id or {}
    nodes = graph_definition.get("nodes", [])
    node_by_id = {node["id"]: node for node in nodes if node.get("id")}
    edges = [dict(edge) for edge in graph_definition.get("edges", [])]

    for idx, edge in enumerate(edges):
        source_id = edge.get("source", "")
        target_node = node_by_id.get(edge.get("target", ""))
        if not target_node:
            continue

        target_agent = agents_by_id.get(target_node.get("agent_id"))
        expected_intent = infer_intent_from_node(target_node, target_agent)

        if (
            edge.get("edge_type") == "if_condition"
            and is_routing_hub(source_id, edges)
            and expected_intent
        ):
            current_intent = intent_from_condition(edge.get("condition"))
            if current_intent and current_intent != expected_intent:
                edges[idx] = {**edge, "condition": f"INTENT: {expected_intent}"}

        if edge.get("edge_type") == "if_condition" and not is_routing_hub(source_id, edges):
            source_node = node_by_id.get(source_id)
            source_agent = agents_by_id.get((source_node or {}).get("agent_id"))
            if not is_classifier_node(source_node or {}, source_agent):
                edges[idx] = {**edge, "edge_type": "always", "condition": None}

    edges = _repair_multi_always_branches(edges, node_by_id, agents_by_id)

    for source_id in {edge.get("source") for edge in edges}:
        from_source = [edge for edge in edges if edge.get("source") == source_id]
        always_targets = {
            edge.get("target")
            for edge in from_source
            if edge.get("edge_type", "always") == "always"
        }
        if not always_targets:
            continue
        edges = [
            edge
            for edge in edges
            if not (
                edge.get("source") == source_id
                and edge.get("edge_type") == "if_condition"
                and edge.get("target") in always_targets
            )
        ]

    return {**graph_definition, "nodes": nodes, "edges": edges}


def _graph_metadata(graph_definition: dict) -> dict[str, Any]:
    """Fields outside nodes/edges that must survive sanitization."""
    meta: dict[str, Any] = {}
    if graph_definition.get("template_type"):
        meta["template_type"] = graph_definition["template_type"]
    schedule = graph_definition.get("schedule")
    if isinstance(schedule, dict) and schedule:
        meta["schedule"] = schedule
    return meta


def sanitize_graph_definition(graph_definition: dict, agents_by_id: dict[str, Agent]) -> dict:
    nodes = [
        node
        for node in graph_definition.get("nodes", [])
        if node.get("id") and agents_by_id.get(node.get("agent_id"))
    ]
    node_ids = {node["id"] for node in nodes}
    edges = [
        edge
        for edge in graph_definition.get("edges", [])
        if edge.get("source") in node_ids and edge.get("target") in node_ids
    ]
    entry = graph_definition.get("entry_node_id")
    if entry not in node_ids:
        entry = nodes[0]["id"] if nodes else None
    cleaned = {**graph_definition, "nodes": nodes, "edges": edges, "entry_node_id": entry}
    repaired = repair_misrouted_conditions(cleaned, agents_by_id)
    return {**repaired, **_graph_metadata(graph_definition)}
