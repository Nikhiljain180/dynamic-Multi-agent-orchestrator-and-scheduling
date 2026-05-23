import asyncio
import re
from collections import defaultdict
from typing import Any, Literal, TypedDict

from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.graph import END, StateGraph

from app.config import settings
from app.models import Agent, MessageRole
from app.runtime.graph_repair import (
    match_classifier_intent,
    match_user_intent,
    sanitize_graph_definition,
)
from app.runtime.llm import get_chat_model, resolve_provider
from app.runtime.tools import build_tools, prefetch_tool_context
from app.services import RunService

_TOOL_BINDING_PROVIDERS = {"openai"}


class GraphState(TypedDict):
    input_text: str
    messages: list[dict[str, Any]]
    agent_outputs: dict[str, str]
    review_passed: bool
    triage_intent: str
    final_output: str
    channel_context: dict[str, Any]


def _estimate_tokens(text: str) -> int:
    return max(1, len(text) // 4)


def _apply_guardrails(agent: Agent, content: str) -> tuple[str, bool]:
    guardrails = agent.guardrails or {}
    max_tokens = guardrails.get("max_tokens", 2000)
    blocked_patterns = guardrails.get("blocked_patterns", [])

    for pattern in blocked_patterns:
        if re.search(pattern, content, re.IGNORECASE):
            return f"[BLOCKED by guardrail: matched pattern '{pattern}']", False

    words = content.split()
    if len(words) > max_tokens:
        content = " ".join(words[:max_tokens]) + "... [truncated by guardrail]"

    return content, True


def _should_bind_tools(provider: str) -> bool:
    return provider in _TOOL_BINDING_PROVIDERS


def _is_rate_limit_error(exc: Exception) -> bool:
    err = str(exc).lower()
    return any(token in err for token in ("429", "rate limit", "tokens per minute", "too many requests"))


async def _invoke_llm(
    llm,
    messages: list,
    db,
    run_id: str,
    agent_id: str,
    max_retries: int = 2,
) -> tuple[str, int, int]:
    system_content = messages[0].content if messages else ""
    user_msg = messages[1].content if len(messages) > 1 else ""

    last_exc: Exception | None = None
    for attempt in range(max_retries + 1):
        try:
            response = await llm.ainvoke(messages)
            output = response.content if isinstance(response.content, str) else str(response.content)
            prompt_tokens = _estimate_tokens(f"{system_content}{user_msg}")
            completion_tokens = _estimate_tokens(output)
            return output, prompt_tokens, completion_tokens
        except Exception as exc:
            last_exc = exc
            if _is_rate_limit_error(exc) and attempt < max_retries:
                wait_seconds = 15 * (attempt + 1)
                await RunService.add_log(
                    db,
                    run_id,
                    f"Rate limited by LLM provider, retrying in {wait_seconds}s (attempt {attempt + 1}/{max_retries})",
                    level="warning",
                    agent_id=agent_id,
                )
                await asyncio.sleep(wait_seconds)
                continue
            raise

    raise last_exc or RuntimeError("LLM invocation failed")


async def _run_agent_node(
    agent: Agent,
    node_name: str,
    state: GraphState,
    db,
    run_id: str,
    task_instruction: str,
    display_name: str | None = None,
) -> dict[str, Any]:
    label = display_name or agent.name or node_name
    await RunService.add_log(db, run_id, f"Starting {label}", agent_id=agent.id)

    provider = resolve_provider(agent)
    allowed_tools = agent.guardrails.get("allowed_tools") if agent.guardrails else None
    tool_names = agent.tools or []
    if allowed_tools:
        tool_names = [t for t in tool_names if t in allowed_tools]

    llm = get_chat_model(agent)
    tools = build_tools(tool_names, run_id)
    if tools and _should_bind_tools(provider) and hasattr(llm, "bind_tools"):
        try:
            llm = llm.bind_tools(tools)
        except NotImplementedError:
            await RunService.add_log(db, run_id, "Tools skipped for this LLM provider", level="warning", agent_id=agent.id)
    elif tools and not _should_bind_tools(provider):
        await RunService.add_log(
            db,
            run_id,
            f"Tools pre-fetched for {provider} (no bind_tools)",
            agent_id=agent.id,
        )

    skills_text = "\n".join(f"- {s}" for s in (agent.skills or []))
    memory = agent.memory_config or {}
    memory_text = ""
    if memory.get("short_term"):
        memory_text += f"\nRecent context:\n{state.get('input_text', '')[:500]}"
    if memory.get("long_term") and state.get("agent_outputs"):
        memory_text += f"\nPrior agent outputs:\n{state['agent_outputs']}"

    system_content = agent.system_prompt
    if skills_text:
        system_content += f"\n\nSkills:\n{skills_text}"
    if agent.interaction_rules:
        system_content += f"\n\nInteraction rules:\n{agent.interaction_rules}"
    if memory_text:
        system_content += memory_text

    prior = state.get("agent_outputs", {})
    context = "\n".join(f"{k}: {v[:300]}" for k, v in prior.items()) if prior else "None"

    user_msg = f"Task: {task_instruction}\n\nOriginal input: {state['input_text']}\n\nPrior outputs:\n{context}"

    if tools and not _should_bind_tools(provider):
        prefetched = await prefetch_tool_context(tool_names, state["input_text"])
        if prefetched:
            user_msg += f"\n\n{prefetched}"

    messages = [SystemMessage(content=system_content), HumanMessage(content=user_msg)]

    try:
        output, prompt_tokens, completion_tokens = await _invoke_llm(llm, messages, db, run_id, agent.id)
    except Exception as exc:
        err = str(exc).lower()
        if "tool" in err and tools:
            await RunService.add_log(
                db,
                run_id,
                f"Tool-calling failed, retrying without tools: {exc}",
                level="warning",
                agent_id=agent.id,
            )
            plain_llm = get_chat_model(agent)
            output, prompt_tokens, completion_tokens = await _invoke_llm(
                plain_llm, messages, db, run_id, agent.id
            )
        elif settings.allow_mock_llm_fallback:
            from app.runtime.llm import MockChatModel

            mock = MockChatModel(role=agent.role.lower())
            output, prompt_tokens, completion_tokens = await _invoke_llm(mock, messages, db, run_id, agent.id)
            await RunService.add_log(db, run_id, f"LLM fallback used: {exc}", level="warning", agent_id=agent.id)
        else:
            await RunService.add_log(db, run_id, f"LLM call failed: {exc}", level="error", agent_id=agent.id)
            raise RuntimeError(f"LLM call failed for {agent.name}: {exc}") from exc

    output, passed = _apply_guardrails(agent, output)
    if not passed:
        await RunService.add_log(db, run_id, "Output blocked by guardrails", level="warning", agent_id=agent.id)

    await RunService.add_token_usage(db, run_id, node_name, prompt_tokens, completion_tokens, agent.id)
    await RunService.add_message(
        db, run_id, output, MessageRole.AGENT, from_agent_id=agent.id, channel=state.get("channel_context", {}).get("channel")
    )
    await RunService.add_log(db, run_id, f"Completed {label}", agent_id=agent.id)

    agent_outputs = dict(state.get("agent_outputs", {}))
    agent_outputs[node_name] = output

    return {"agent_outputs": agent_outputs, "messages": state.get("messages", []) + [{"node": node_name, "content": output}]}


_DEFAULT_TRIAGE_NODE_IDS = frozenset({"triage", "billing", "technical", "responder"})
_DEFAULT_TRIAGE_EDGE_KEYS = frozenset({
    ("triage", "billing", "if_condition"),
    ("triage", "technical", "if_condition"),
    ("billing", "responder", "always"),
    ("technical", "responder", "always"),
})


def _is_default_triage_template(graph_definition: dict) -> bool:
    node_ids = {n.get("id") for n in graph_definition.get("nodes", []) if n.get("id")}
    if node_ids != _DEFAULT_TRIAGE_NODE_IDS:
        return False
    edge_keys = {
        (e.get("source"), e.get("target"), e.get("edge_type", "always"))
        for e in graph_definition.get("edges", [])
    }
    return edge_keys == _DEFAULT_TRIAGE_EDGE_KEYS


def _resolve_triage_agents(
    nodes: list[dict],
    agents_by_id: dict[str, Agent],
) -> dict[str, Agent] | None:
    keyed: dict[str, Agent] = {}
    by_role: dict[str, Agent] = {}

    for node in nodes:
        agent = agents_by_id.get(node.get("agent_id"))
        if not agent:
            continue
        keyed[node["id"]] = agent
        role = agent.role.lower()
        if "triage" in role:
            by_role["triage"] = agent
        elif "billing" in role:
            by_role["billing"] = agent
        elif "technical" in role:
            by_role["technical"] = agent
        elif "respond" in role:
            by_role["responder"] = agent

    required = {"triage", "billing", "technical", "responder"}
    if required.issubset(keyed.keys()):
        return {name: keyed[name] for name in required}
    if required.issubset(by_role.keys()):
        return {name: by_role[name] for name in required}

    return None


def _wire_edges(graph: StateGraph, edges: list[dict], active_node_ids: set[str]) -> None:
    valid_edges = [
        edge
        for edge in edges
        if edge.get("source") in active_node_ids and edge.get("target") in active_node_ids
    ]

    by_source: dict[str, list[dict]] = defaultdict(list)
    for edge in valid_edges:
        by_source[edge["source"]].append(edge)

    for src, src_edges in by_source.items():
        feedback_edges = [e for e in src_edges if e.get("edge_type") == "feedback"]
        cond_edges = [e for e in src_edges if e.get("edge_type") == "if_condition"]
        always_edges = [e for e in src_edges if e.get("edge_type", "always") == "always"]

        for edge in feedback_edges:
            tgt = edge["target"]

            def route_feedback(state: GraphState, target=tgt, src_node=src):
                outputs = state.get("agent_outputs", {})
                if "FAIL" in outputs.get(src_node, "").upper():
                    return target
                return END

            graph.add_conditional_edges(src, route_feedback, {tgt: tgt, END: END})

        if cond_edges:
            if len(always_edges) == 1:
                fallback = always_edges[0]["target"]
            else:
                fallback = cond_edges[0]["target"]

            def route_conditions(
                state: GraphState,
                edges_list=tuple(cond_edges),
                source=src,
                default_target=fallback,
            ):
                output = state.get("agent_outputs", {}).get(source, "")
                input_text = state.get("input_text", "")

                for item in edges_list:
                    if match_user_intent(input_text, item.get("condition")):
                        return item["target"]

                for item in edges_list:
                    if match_classifier_intent(output, item.get("condition")):
                        return item["target"]

                return default_target

            path_map = {edge["target"]: edge["target"] for edge in cond_edges}
            if len(always_edges) == 1:
                path_map[always_edges[0]["target"]] = always_edges[0]["target"]
            graph.add_conditional_edges(src, route_conditions, path_map)
        elif len(always_edges) > 1:
            raise ValueError(
                f"Node '{src}' has multiple unconditional branches; use if_condition edges or a single always fallback"
            )
        elif always_edges:
            for edge in always_edges:
                tgt = edge["target"]
                graph.add_edge(src, tgt if tgt != "__end__" else END)

    nodes_with_outgoing = set(by_source.keys())
    for node_id in active_node_ids:
        if node_id not in nodes_with_outgoing:
            graph.add_edge(node_id, END)


def build_brief_summary_workflow_graph(agents: dict[str, Agent], db, run_id: str):
    brief_agent = agents["brief"]
    summary_agent = agents["summary"]

    async def brief_node(state: GraphState):
        return await _run_agent_node(
            brief_agent,
            "brief",
            state,
            db,
            run_id,
            "Create a concise bullet brief (max 150 words) with the most important points",
        )

    async def summary_node(state: GraphState):
        result = await _run_agent_node(
            summary_agent,
            "summary",
            state,
            db,
            run_id,
            "Write a polished executive summary (~250 words) based on the brief",
        )
        result["final_output"] = result["agent_outputs"].get("summary", "")
        return result

    graph = StateGraph(GraphState)
    graph.add_node("brief", brief_node)
    graph.add_node("summary", summary_node)
    graph.add_edge("brief", "summary")
    graph.add_edge("summary", END)
    graph.set_entry_point("brief")
    return graph.compile()


def build_triage_workflow_graph(agents: dict[str, Agent], db, run_id: str):
    triage = agents["triage"]
    billing = agents["billing"]
    technical = agents["technical"]
    responder = agents["responder"]

    async def triage_node(state: GraphState):
        result = await _run_agent_node(triage, "triage", state, db, run_id, "Classify the user intent")
        output = result["agent_outputs"].get("triage", "")
        intent = "billing" if "billing" in output.lower() else "technical"
        result["triage_intent"] = intent
        return result

    async def billing_node(state: GraphState):
        return await _run_agent_node(billing, "billing", state, db, run_id, "Handle billing inquiry")

    async def technical_node(state: GraphState):
        return await _run_agent_node(technical, "technical", state, db, run_id, "Handle technical inquiry")

    async def responder_node(state: GraphState):
        result = await _run_agent_node(responder, "responder", state, db, run_id, "Format final reply to user")
        result["final_output"] = result["agent_outputs"].get("responder", "")
        return result

    def route_after_triage(state: GraphState) -> Literal["billing", "technical"]:
        return state.get("triage_intent", "technical")

    graph = StateGraph(GraphState)
    graph.add_node("triage", triage_node)
    graph.add_node("billing", billing_node)
    graph.add_node("technical", technical_node)
    graph.add_node("responder", responder_node)
    graph.set_entry_point("triage")
    graph.add_conditional_edges("triage", route_after_triage, {"billing": "billing", "technical": "technical"})
    graph.add_edge("billing", "responder")
    graph.add_edge("technical", "responder")
    graph.add_edge("responder", END)
    return graph.compile()


def _build_brief_summary_from_keyed(keyed: dict[str, Agent], db, run_id: str):
    if {"brief", "summary"}.issubset(keyed.keys()):
        return build_brief_summary_workflow_graph({"brief": keyed["brief"], "summary": keyed["summary"]}, db, run_id)
    return None


def build_graph_from_definition(
    graph_definition: dict,
    agents_by_id: dict[str, Agent],
    db,
    run_id: str,
    workflow_name: str | None = None,
):
    graph_definition = sanitize_graph_definition(graph_definition, agents_by_id)
    template_type = graph_definition.get("template_type")
    keyed = {}
    for node in graph_definition.get("nodes", []):
        agent = agents_by_id.get(node["agent_id"])
        if agent:
            keyed[node["id"]] = agent

    if template_type in ("brief_summary", "research_pipeline"):
        graph = _build_brief_summary_from_keyed(keyed, db, run_id)
        if graph:
            return graph
        if template_type == "research_pipeline":
            legacy = {}
            if "researcher" in keyed and "writer" in keyed:
                legacy = {"brief": keyed["researcher"], "summary": keyed.get("writer", keyed["researcher"])}
            elif len(keyed) >= 2:
                ids = list(keyed.keys())
                legacy = {"brief": keyed[ids[0]], "summary": keyed[ids[1]]}
            if legacy:
                return build_brief_summary_workflow_graph(legacy, db, run_id)

    triage_agents = _resolve_triage_agents(graph_definition.get("nodes", []), agents_by_id)
    use_default_triage = template_type == "telegram_triage" and _is_default_triage_template(graph_definition)
    if triage_agents and use_default_triage:
        return build_triage_workflow_graph(triage_agents, db, run_id)

    nodes = graph_definition.get("nodes", [])
    edges = graph_definition.get("edges", [])
    if not nodes:
        raise ValueError("Workflow has no nodes")

    runnable_node_ids = {
        node["id"] for node in nodes if agents_by_id.get(node.get("agent_id"))
    }
    valid_edges = [
        edge
        for edge in edges
        if edge.get("source") in runnable_node_ids and edge.get("target") in runnable_node_ids
    ]
    nodes_with_outgoing = {edge["source"] for edge in valid_edges}
    leaf_nodes = runnable_node_ids - nodes_with_outgoing

    graph = StateGraph(GraphState)
    active_node_ids: set[str] = set()

    for node in nodes:
        agent = agents_by_id.get(node["agent_id"])
        if not agent:
            continue
        node_id = node["id"]
        active_node_ids.add(node_id)
        is_leaf = node_id in leaf_nodes
        step_label = node.get("label") or agent.name or node_id

        async def make_node(state: GraphState, n_id=node_id, ag=agent, leaf=is_leaf, step=step_label):
            result = await _run_agent_node(
                ag, n_id, state, db, run_id, f"Execute step {step}", display_name=step
            )
            if leaf:
                result["final_output"] = result["agent_outputs"].get(n_id, "")
            return result

        graph.add_node(node_id, make_node)

    if not active_node_ids:
        raise ValueError("Workflow has no runnable agent nodes")

    entry = graph_definition.get("entry_node_id")
    if entry not in active_node_ids:
        entry = next(iter(active_node_ids))
    graph.set_entry_point(entry)

    _wire_edges(graph, edges, active_node_ids)

    return graph.compile()
