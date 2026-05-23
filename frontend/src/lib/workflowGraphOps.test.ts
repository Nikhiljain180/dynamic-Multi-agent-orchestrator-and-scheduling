import { describe, expect, it } from 'vitest';
import type { Agent, GraphDefinition } from '../api/client';
import {
  BRANCH_GAP_Y,
  NODE_SPACING_X,
  agentsAvailableToAdd,
  addFirstNode,
  addNodeAfter,
  addNodeToGraph,
  findOrphanNodes,
  findUnreachableNodes,
  inferIntentCondition,
  layoutBranchPosition,
  sanitizeGraph,
} from './workflowGraphOps';

const agent = (id: string, name: string): Agent => ({
  id,
  name,
  role: 'Agent',
  system_prompt: 'test',
  model: 'llama-3.1-8b-instant',
  use_platform_api_key: true,
  tools: [],
  channels: {},
  memory_config: {},
  skills: [],
  guardrails: {},
  created_at: '',
  updated_at: '',
});

const emptyGraph = (): GraphDefinition => ({ nodes: [], edges: [] });

const linearGraph = (): GraphDefinition => ({
  entry_node_id: 'a',
  nodes: [
    { id: 'a', agent_id: 'ag1', label: 'A', position: { x: 100, y: 120 } },
    { id: 'b', agent_id: 'ag2', label: 'B', position: { x: 440, y: 120 } },
  ],
  edges: [{ id: 'e1', source: 'a', target: 'b', edge_type: 'always', condition: null }],
});

const triageGraph = (): GraphDefinition => ({
  entry_node_id: 'triage',
  nodes: [
    { id: 'triage', agent_id: 't1', label: 'Triage', position: { x: 100, y: 150 } },
    { id: 'billing', agent_id: 'b1', label: 'Billing', position: { x: 440, y: 50 } },
    { id: 'technical', agent_id: 't2', label: 'Technical', position: { x: 440, y: 250 } },
  ],
  edges: [
    { id: 'e1', source: 'triage', target: 'billing', edge_type: 'if_condition', condition: 'INTENT: billing' },
    { id: 'e2', source: 'triage', target: 'technical', edge_type: 'if_condition', condition: 'INTENT: technical' },
  ],
});

describe('workflowGraphOps', () => {
  it('agentsAvailableToAdd excludes agents already on the graph', () => {
    const graph = linearGraph();
    const pool = [
      agent('ag1', 'A Agent'),
      agent('ag2', 'B Agent'),
      agent('ag3', 'Extra'),
    ];
    const available = agentsAvailableToAdd(graph, pool);
    expect(available.map((a) => a.id)).toEqual(['ag3']);
  });

  it('E1: addFirstNode on empty graph sets entry and one node', () => {
    const result = addFirstNode(agent('ag1', 'Quick Brief'), emptyGraph());
    expect(result.graph.nodes).toHaveLength(1);
    expect(result.graph.entry_node_id).toBe(result.newNodeId);
    expect(result.graph.edges).toHaveLength(0);
    expect(findOrphanNodes(result.graph)).toHaveLength(0);
  });

  it('E2: insert between on linear chain rewires A→new→B and shifts B', () => {
    const result = addNodeAfter('a', agent('ag3', 'Middle'), linearGraph());
    const newNode = result.graph.nodes.find((n) => n.id === result.newNodeId)!;
    const b = result.graph.nodes.find((n) => n.id === 'b')!;

    expect(result.graph.edges).toHaveLength(2);
    expect(result.graph.edges.some((e) => e.source === 'a' && e.target === result.newNodeId)).toBe(true);
    expect(result.graph.edges.some((e) => e.source === result.newNodeId && e.target === 'b')).toBe(true);
    expect(newNode.position).toEqual({ x: 440, y: 120 });
    expect(b.position.x).toBe(440 + NODE_SPACING_X);
  });

  it('E3: append after leaf node with zero outgoing edges', () => {
    const result = addNodeAfter('b', agent('ag4', 'Tail'), linearGraph());
    const newNode = result.graph.nodes.find((n) => n.id === result.newNodeId)!;

    expect(result.graph.edges.some((e) => e.source === 'b' && e.target === result.newNodeId)).toBe(true);
    expect(newNode.position.x).toBe(440 + NODE_SPACING_X);
    expect(newNode.position.y).toBe(120);
  });

  it('E4: router node adds parallel branch below existing branches', () => {
    const result = addNodeAfter('triage', agent('ag5', 'Research'), triageGraph());
    const newNode = result.graph.nodes.find((n) => n.id === result.newNodeId)!;

    expect(result.graph.edges.some((e) => e.source === 'triage' && e.target === result.newNodeId)).toBe(true);
    expect(newNode.position.x).toBe(100 + NODE_SPACING_X);
    expect(newNode.position.y).toBe(250 + BRANCH_GAP_Y);
  });

  it('E5: addNodeToGraph after billing appends connected step', () => {
    const graph = triageGraph();
    graph.nodes.push({ id: 'responder', agent_id: 'r1', label: 'Responder', position: { x: 780, y: 150 } });
    graph.edges.push({ id: 'e3', source: 'billing', target: 'responder', edge_type: 'always', condition: null });

    const result = addNodeToGraph(agent('ag6', 'Extra'), graph, 'billing');
    expect(result.graph.edges.some((e) => e.source === 'billing' && e.target === result.newNodeId)).toBe(true);
  });

  it('E6: two sequential adds keep both edges', () => {
    let graph = linearGraph();
    const first = addNodeAfter('b', agent('ag7', 'One'), graph);
    graph = first.graph;
    const second = addNodeAfter('b', agent('ag8', 'Two'), graph);

    const fromB = second.graph.edges.filter((e) => e.source === 'b');
    expect(fromB.length).toBeGreaterThanOrEqual(1);
    expect(second.graph.nodes.length).toBe(4);
  });

  it('findOrphanNodes detects disconnected nodes', () => {
    const graph = linearGraph();
    graph.nodes.push({ id: 'lonely', agent_id: 'x', label: 'Lonely', position: { x: 0, y: 0 } });
    expect(findOrphanNodes(graph)).toHaveLength(1);
    expect(findOrphanNodes(graph)[0].id).toBe('lonely');
  });

  it('findUnreachableNodes detects nodes not reachable from entry', () => {
    const graph = linearGraph();
    graph.nodes.push({ id: 'island', agent_id: 'x', label: 'Island', position: { x: 900, y: 900 } });
    graph.edges.push({ id: 'e2', source: 'island', target: 'b', edge_type: 'always', condition: null });
    const unreachable = findUnreachableNodes(graph);
    expect(unreachable.some((n) => n.id === 'island')).toBe(true);
  });

  it('layoutBranchPosition places branch below lowest sibling', () => {
    const graph = triageGraph();
    const source = graph.nodes.find((n) => n.id === 'triage')!;
    const pos = layoutBranchPosition(source, graph);
    expect(pos.y).toBe(250 + BRANCH_GAP_Y);
  });

  it('sanitizeGraph removes edges whose endpoints are missing nodes', () => {
    const graph = linearGraph();
    graph.nodes = graph.nodes.filter((n) => n.id !== 'b');
    graph.edges = [
      { id: 'e1', source: 'a', target: 'b', edge_type: 'always', condition: null },
      { id: 'e2', source: 'a', target: 'missing', edge_type: 'always', condition: null },
    ];
    const clean = sanitizeGraph(graph);
    expect(clean.edges).toHaveLength(0);
    expect(clean.nodes.map((n) => n.id)).toEqual(['a']);
  });

  it('insert between triage and technical sets research intent on incoming edge', () => {
    const graph: GraphDefinition = {
      entry_node_id: 'triage',
      nodes: [
        { id: 'triage', agent_id: 't1', label: 'Triage', position: { x: 100, y: 150 } },
        { id: 'technical', agent_id: 't2', label: 'Technical', position: { x: 440, y: 150 } },
      ],
      edges: [
        {
          id: 'e1',
          source: 'triage',
          target: 'technical',
          edge_type: 'if_condition',
          condition: 'INTENT: technical',
        },
      ],
    };
    const researchAgent = agent('ag-research', 'Research Agent');
    const result = addNodeAfter('triage', researchAgent, graph);
    const fromTriage = result.graph.edges.find((e) => e.source === 'triage' && e.target === result.newNodeId);
    const toTechnical = result.graph.edges.find((e) => e.source === result.newNodeId && e.target === 'technical');

    expect(fromTriage?.edge_type).toBe('if_condition');
    expect(fromTriage?.condition).toBe('INTENT: research');
    expect(toTechnical?.edge_type).toBe('always');
    expect(toTechnical?.condition).toBeNull();
  });

  it('inferIntentCondition maps agent names to intent labels', () => {
    expect(inferIntentCondition(agent('a1', 'Research Agent'))).toBe('INTENT: research');
    expect(inferIntentCondition(agent('a2', 'Technical Agent'))).toBe('INTENT: technical');
  });
});
