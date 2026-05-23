import type { Agent, GraphDefinition, WorkflowEdge, WorkflowNode } from '../api/client';

export const NODE_SPACING_X = 340;
export const BRANCH_GAP_Y = 120;

export type AddNodeResult = {
  graph: GraphDefinition;
  newNodeId: string;
  message: string;
};

function nodeById(graph: GraphDefinition, id: string): WorkflowNode | undefined {
  return (graph.nodes || []).find((n) => n.id === id);
}

function outgoingEdges(graph: GraphDefinition, sourceId: string): WorkflowEdge[] {
  return (graph.edges || []).filter((e) => e.source === sourceId);
}

function collectDownstreamIds(nodeId: string, edges: WorkflowEdge[]): Set<string> {
  const visited = new Set<string>([nodeId]);
  const queue = [nodeId];
  while (queue.length) {
    const current = queue.shift()!;
    for (const edge of edges) {
      if (edge.source === current && !visited.has(edge.target)) {
        visited.add(edge.target);
        queue.push(edge.target);
      }
    }
  }
  return visited;
}

function makeEdge(
  id: string,
  source: string,
  target: string,
  edgeType = 'always',
  condition: string | null = null,
): WorkflowEdge {
  return { id, source, target, edge_type: edgeType, condition };
}

function makeWorkflowNode(id: string, agent: Agent): WorkflowNode {
  return {
    id,
    agent_id: agent.id,
    label: agent.name,
    position: { x: 100, y: 120 },
  };
}

const SKIP_INTENT_TOKENS = new Set(['agent', 'specialist', 'support', 'customer', 'service', 'and', 'the']);
const RESPONDER_HINTS = ['respond', 'responder', 'reply'];

function inferIntentFromText(text: string): string | null {
  const lower = text.toLowerCase();
  if (RESPONDER_HINTS.some((hint) => lower.includes(hint))) return null;
  const tokens = lower.match(/[a-z]+/g) || [];
  for (const token of tokens) {
    if (token.length > 2 && !SKIP_INTENT_TOKENS.has(token)) return token;
  }
  return null;
}

function isRoutingHub(sourceId: string, edges: WorkflowEdge[]): boolean {
  const fromSource = edges.filter((edge) => edge.source === sourceId);
  if (fromSource.length <= 1) return false;
  return fromSource.some((edge) => edge.edge_type === 'if_condition');
}

/** UI hint when inserting a branch; backend `/workflows/repair-graph` is the source of truth. */
export function inferIntentCondition(agent: Agent): string | null {
  const intent = inferIntentFromText(`${agent.name} ${agent.role}`);
  return intent ? `INTENT: ${intent}` : null;
}

function incomingEdgeForInsert(
  sourceId: string,
  agent: Agent,
  graph: GraphDefinition,
  outEdge: WorkflowEdge,
): { edgeType: string; condition: string | null } {
  if (outEdge.edge_type === 'if_condition' && isRoutingHub(sourceId, graph.edges || [])) {
    return {
      edgeType: 'if_condition',
      condition: inferIntentCondition(agent) || outEdge.condition || null,
    };
  }
  if (outEdge.edge_type === 'if_condition') {
    return {
      edgeType: 'if_condition',
      condition: inferIntentCondition(agent) || outEdge.condition || null,
    };
  }
  return { edgeType: outEdge.edge_type, condition: outEdge.condition ?? null };
}

export function layoutBranchPosition(sourceNode: WorkflowNode, graph: GraphDefinition): { x: number; y: number } {
  const siblings = outgoingEdges(graph, sourceNode.id);
  let maxY = sourceNode.position.y;

  for (const edge of siblings) {
    const target = nodeById(graph, edge.target);
    if (target) {
      maxY = Math.max(maxY, target.position.y);
    }
  }

  return {
    x: sourceNode.position.x + NODE_SPACING_X,
    y: siblings.length ? maxY + BRANCH_GAP_Y : sourceNode.position.y,
  };
}

export function findOrphanNodes(graph: GraphDefinition): WorkflowNode[] {
  const nodes = graph.nodes || [];
  const edges = graph.edges || [];
  if (!nodes.length) return [];

  const connected = new Set<string>();
  for (const edge of edges) {
    connected.add(edge.source);
    connected.add(edge.target);
  }

  if (!edges.length && nodes.length === 1) {
    return [];
  }

  return nodes.filter((n) => !connected.has(n.id));
}

export function findUnreachableNodes(graph: GraphDefinition): WorkflowNode[] {
  const nodes = graph.nodes || [];
  const edges = graph.edges || [];
  if (!nodes.length) return [];

  const entry = graph.entry_node_id || nodes[0]?.id;
  if (!entry) return nodes;

  const reachable = new Set<string>([entry]);
  const queue = [entry];
  while (queue.length) {
    const current = queue.shift()!;
    for (const edge of edges) {
      if (edge.source === current && !reachable.has(edge.target)) {
        reachable.add(edge.target);
        queue.push(edge.target);
      }
    }
  }

  return nodes.filter((n) => !reachable.has(n.id));
}

export function describeAddAction(sourceId: string | null, graph: GraphDefinition): string {
  const nodes = graph.nodes || [];
  if (!nodes.length || !sourceId) {
    return 'Creates the first workflow step (entry node).';
  }

  const source = nodeById(graph, sourceId);
  if (!source) return 'Adds a new connected agent step.';

  const outgoing = outgoingEdges(graph, sourceId);
  if (outgoing.length === 0) {
    return `Appends a new step after "${source.label}".`;
  }
  if (outgoing.length === 1) {
    const target = nodeById(graph, outgoing[0].target);
    return `Inserts a new step between "${source.label}" and "${target?.label || outgoing[0].target}".`;
  }
  return `Adds a new parallel branch from "${source.label}".`;
}

export function addFirstNode(agent: Agent, graph: GraphDefinition): AddNodeResult {
  const id = `node-${Date.now()}`;
  const newNode = makeWorkflowNode(id, agent);
  newNode.position = { x: 100, y: 120 };

  return {
    graph: {
      ...graph,
      entry_node_id: id,
      nodes: [newNode],
      edges: graph.edges || [],
    },
    newNodeId: id,
    message: `Added ${agent.name} as the first step`,
  };
}

export function addNodeAfter(sourceId: string, agent: Agent, graph: GraphDefinition): AddNodeResult {
  const source = nodeById(graph, sourceId);
  if (!source) {
    throw new Error(`Source node "${sourceId}" not found`);
  }

  const id = `node-${Date.now()}`;
  const ts = Date.now();
  const outgoing = outgoingEdges(graph, sourceId);
  const newNode = makeWorkflowNode(id, agent);
  const edges = [...(graph.edges || [])];
  let nodes = [...(graph.nodes || [])];

  if (outgoing.length === 0) {
    newNode.position = {
      x: source.position.x + NODE_SPACING_X,
      y: source.position.y,
    };
    nodes.push(newNode);
    edges.push(makeEdge(`e-${ts}`, sourceId, id));

    return {
      graph: { ...graph, nodes, edges },
      newNodeId: id,
      message: `Added ${agent.name} after ${source.label}`,
    };
  }

  if (outgoing.length === 1) {
    const outEdge = outgoing[0];
    const target = nodeById(graph, outEdge.target);
    if (!target) {
      newNode.position = layoutBranchPosition(source, graph);
      nodes.push(newNode);
      edges.push(makeEdge(`e-${ts}`, sourceId, id));
      return {
        graph: { ...graph, nodes, edges },
        newNodeId: id,
        message: `Added ${agent.name} after ${source.label}`,
      };
    }

    const downstream = collectDownstreamIds(outEdge.target, graph.edges || []);
    nodes = nodes.map((n) =>
      downstream.has(n.id)
        ? { ...n, position: { x: n.position.x + NODE_SPACING_X, y: n.position.y } }
        : n,
    );
    newNode.position = { ...target.position };
    nodes.push(newNode);

    const filtered = edges.filter((e) => e.id !== outEdge.id);
    const incoming = incomingEdgeForInsert(sourceId, agent, graph, outEdge);
    filtered.push(
      makeEdge(`e-${ts}-a`, sourceId, id, incoming.edgeType, incoming.condition),
      makeEdge(`e-${ts}-b`, id, outEdge.target, 'always', null),
    );

    return {
      graph: { ...graph, nodes, edges: filtered },
      newNodeId: id,
      message: `Inserted ${agent.name} between ${source.label} and ${target.label}`,
    };
  }

  newNode.position = layoutBranchPosition(source, graph);
  nodes.push(newNode);
  const intent = inferIntentCondition(agent);
  edges.push(
    makeEdge(
      `e-${ts}`,
      sourceId,
      id,
      intent ? 'if_condition' : 'always',
      intent,
    ),
  );

  return {
    graph: { ...graph, nodes, edges },
    newNodeId: id,
    message: `Added branch ${agent.name} from ${source.label}`,
  };
}

export function addNodeToGraph(
  agent: Agent,
  graph: GraphDefinition,
  sourceId: string | null,
): AddNodeResult {
  const nodes = graph.nodes || [];
  let result: AddNodeResult;
  if (!nodes.length || !sourceId) {
    result = addFirstNode(agent, graph);
  } else {
    result = addNodeAfter(sourceId, agent, graph);
  }
  return { ...result, graph: sanitizeGraph(result.graph) };
}

export function sanitizeGraph(graph: GraphDefinition): GraphDefinition {
  const nodes = graph.nodes || [];
  const nodeIds = new Set(nodes.map((n) => n.id));
  const edges = (graph.edges || []).filter(
    (edge) => nodeIds.has(edge.source) && nodeIds.has(edge.target),
  );
  let entry = graph.entry_node_id;
  if (!entry || !nodeIds.has(entry)) {
    entry = nodes[0]?.id;
  }
  return { ...graph, nodes, edges, entry_node_id: entry };
}

export function removeEdge(edgeId: string, graph: GraphDefinition): GraphDefinition {
  return sanitizeGraph({
    ...graph,
    edges: (graph.edges || []).filter((e) => e.id !== edgeId),
  });
}

export function updateEdge(
  edgeId: string,
  graph: GraphDefinition,
  patch: Partial<Pick<WorkflowEdge, 'edge_type' | 'condition'>>,
): GraphDefinition {
  return sanitizeGraph({
    ...graph,
    edges: (graph.edges || []).map((edge) => {
      if (edge.id !== edgeId) return edge;
      const edgeType = patch.edge_type ?? edge.edge_type;
      const condition =
        edgeType === 'always'
          ? null
          : patch.condition !== undefined
            ? patch.condition
            : edge.condition ?? null;
      return { ...edge, edge_type: edgeType, condition };
    }),
  });
}

export function connectOrphanAfter(orphanId: string, sourceId: string, graph: GraphDefinition): GraphDefinition {
  const orphan = nodeById(graph, orphanId);
  const source = nodeById(graph, sourceId);
  if (!orphan || !source) return graph;

  const ts = Date.now();
  return sanitizeGraph({
    ...graph,
    edges: [...(graph.edges || []), makeEdge(`e-${ts}`, sourceId, orphanId)],
  });
}

export function nodeLabel(graph: GraphDefinition, nodeId: string): string {
  return nodeById(graph, nodeId)?.label || nodeId;
}

export function usedAgentIds(graph: GraphDefinition): Set<string> {
  return new Set((graph.nodes || []).map((n) => n.agent_id).filter(Boolean));
}

export function agentsAvailableToAdd(graph: GraphDefinition, agents: Agent[]): Agent[] {
  const used = usedAgentIds(graph);
  return agents.filter((agent) => !used.has(agent.id));
}
