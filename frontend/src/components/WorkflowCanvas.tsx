import {
  Background,
  BackgroundVariant,
  Controls,
  MiniMap,
  ReactFlow,
  ReactFlowProvider,
  addEdge,
  applyEdgeChanges,
  applyNodeChanges,
  useEdgesState,
  useNodesState,
  useReactFlow,
  type Connection,
  type Edge,
  type EdgeChange,
  type Node,
  type NodeChange,
} from '@xyflow/react';
import '@xyflow/react/dist/style.css';
import {
  forwardRef,
  useCallback,
  useEffect,
  useImperativeHandle,
  useMemo,
  useRef,
  useState,
} from 'react';
import { Chip, Stack } from '@mui/material';
import type { Agent, GraphDefinition, PlatformLLMSettings, WorkflowEdge, WorkflowNode } from '../api/client';
import { agentNodeSubtitle } from '../api/client';
import { addNodeAfter, agentsAvailableToAdd, sanitizeGraph, type AddNodeResult } from '../lib/workflowGraphOps';
import AgentWorkflowNode from './AgentWorkflowNode';
import { WorkflowEditorContext } from './WorkflowEditorContext';
import './workflow-canvas.css';

interface Props {
  graph: GraphDefinition;
  workflowId: string;
  onChange: (graph: GraphDefinition) => void;
  onAction?: (message: string) => void;
  readOnly?: boolean;
  agents?: Agent[];
  platform?: PlatformLLMSettings | null;
}

export type WorkflowCanvasHandle = {
  applyGraphResult: (result: AddNodeResult) => void;
  syncGraph: (graph: GraphDefinition) => void;
};

const nodeTypes = { agent: AgentWorkflowNode };
const MAX_HISTORY = 50;
const SOURCE_HANDLE = 'out';

type Snapshot = { nodes: Node[]; edges: Edge[] };

function edgeStyle(edgeType?: string) {
  if (edgeType === 'feedback') {
    return { stroke: '#f97316', strokeWidth: 2, strokeDasharray: '6 4' };
  }
  if (edgeType === 'if_condition') {
    return { stroke: '#a855f7', strokeWidth: 2 };
  }
  return { stroke: '#64748b', strokeWidth: 2 };
}

function makeFlowEdge(
  id: string,
  source: string,
  target: string,
  edgeType = 'always',
  condition: string | null = null,
): Edge {
  return {
    id,
    source,
    target,
    sourceHandle: SOURCE_HANDLE,
    type: 'smoothstep',
    animated: edgeType === 'feedback',
    data: { edgeType, condition },
    label: condition || (edgeType !== 'always' ? edgeType.replace(/_/g, ' ') : undefined),
    style: edgeStyle(edgeType),
    labelStyle: { fill: '#e2e8f0', fontWeight: 600, fontSize: 11 },
    labelBgStyle: { fill: '#111827', fillOpacity: 0.95 },
    labelBgPadding: [6, 4] as [number, number],
    labelBgBorderRadius: 6,
  };
}

function toFlowNodes(nodes: WorkflowNode[], agents?: Agent[], platform?: PlatformLLMSettings | null): Node[] {
  return nodes.map((n) => {
    const agent = agents?.find((a) => a.id === n.agent_id);
    return {
      id: n.id,
      position: n.position,
      data: {
        label: n.label,
        agentId: n.agent_id,
        subtitle: agent ? agentNodeSubtitle(agent, platform ?? null) : undefined,
      },
      type: 'agent',
    };
  });
}

function toFlowEdges(edges: WorkflowEdge[]): Edge[] {
  return edges.map((e) => makeFlowEdge(e.id, e.source, e.target, e.edge_type, e.condition));
}

function graphFromFlow(nodes: Node[], edges: Edge[], graph: GraphDefinition): GraphDefinition {
  return sanitizeGraph({
    ...graph,
    nodes: nodes.map((n) => ({
      id: n.id,
      agent_id: (n.data as { agentId?: string }).agentId || '',
      label: String((n.data as { label?: string }).label || n.id),
      position: n.position,
    })),
    edges: edges.map((e) => ({
      id: e.id,
      source: e.source,
      target: e.target,
      edge_type: String((e.data as { edgeType?: string })?.edgeType || 'always'),
      condition: ((e.data as { condition?: string | null })?.condition ?? null) || null,
    })),
  });
}

function WorkflowCanvasInner(
  {
    graph,
    workflowId,
    onChange,
    onAction,
    readOnly = false,
    agents = [],
    platform = null,
  }: Props,
  ref: React.Ref<WorkflowCanvasHandle>,
) {
  const [nodes, setNodes, onNodesChange] = useNodesState(toFlowNodes(graph.nodes || [], agents, platform));
  const [edges, setEdges, onEdgesChange] = useEdgesState(toFlowEdges(graph.edges || []));
  const [past, setPast] = useState<Snapshot[]>([]);
  const [future, setFuture] = useState<Snapshot[]>([]);

  const internalUpdate = useRef(false);
  const externalSync = useRef(false);
  const dragSnapshotTaken = useRef(false);
  const prevWorkflowId = useRef(workflowId);
  const didInitialFit = useRef(false);
  const graphRef = useRef(graph);
  graphRef.current = graph;

  const { fitView } = useReactFlow();

  const defaultEdgeOptions = useMemo(
    () => ({
      type: 'smoothstep',
      sourceHandle: SOURCE_HANDLE,
      style: { stroke: '#64748b', strokeWidth: 2 },
    }),
    [],
  );

  const pushHistory = useCallback((currentNodes: Node[], currentEdges: Edge[]) => {
    setPast((p) => [...p.slice(-MAX_HISTORY + 1), { nodes: currentNodes, edges: currentEdges }]);
    setFuture([]);
  }, []);

  const emitChange = useCallback(
    (nextNodes: Node[], nextEdges: Edge[]) => {
      internalUpdate.current = true;
      const nextGraph = graphFromFlow(nextNodes, nextEdges, graphRef.current);
      onChange(nextGraph);
    },
    [onChange],
  );

  const applyFlowState = useCallback(
    (nextNodes: Node[], nextEdges: Edge[], recordHistory = true) => {
      if (recordHistory) pushHistory(nodes, edges);
      setNodes(nextNodes);
      setEdges(nextEdges);
      emitChange(nextNodes, nextEdges);
    },
    [nodes, edges, pushHistory, setNodes, setEdges, emitChange],
  );

  const applySnapshot = useCallback(
    (snapshot: Snapshot) => {
      setNodes(snapshot.nodes);
      setEdges(snapshot.edges);
      emitChange(snapshot.nodes, snapshot.edges);
    },
    [setNodes, setEdges, emitChange],
  );

  const syncGraph = useCallback(
    (nextGraph: GraphDefinition) => {
      const clean = sanitizeGraph(nextGraph);
      externalSync.current = true;
      setNodes(toFlowNodes(clean.nodes || [], agents, platform));
      setEdges(toFlowEdges(clean.edges || []));
    },
    [agents, platform, setNodes, setEdges],
  );

  const applyGraphResult = useCallback(
    (result: AddNodeResult) => {
      const nextNodes = toFlowNodes(result.graph.nodes || [], agents, platform);
      const nextEdges = toFlowEdges(result.graph.edges || []);
      applyFlowState(nextNodes, nextEdges);
      onAction?.(result.message);
    },
    [agents, platform, applyFlowState, onAction],
  );

  useImperativeHandle(ref, () => ({ applyGraphResult, syncGraph }), [applyGraphResult, syncGraph]);

  const undo = useCallback(() => {
    if (!past.length) return;
    const previous = past[past.length - 1];
    setPast((p) => p.slice(0, -1));
    setFuture((f) => [{ nodes, edges }, ...f]);
    applySnapshot(previous);
  }, [past, nodes, edges, applySnapshot]);

  const redo = useCallback(() => {
    if (!future.length) return;
    const next = future[0];
    setFuture((f) => f.slice(1));
    setPast((p) => [...p, { nodes, edges }]);
    applySnapshot(next);
  }, [future, nodes, edges, applySnapshot]);

  useEffect(() => {
    if (prevWorkflowId.current !== workflowId) {
      prevWorkflowId.current = workflowId;
      didInitialFit.current = false;
      setPast([]);
      setFuture([]);
      setNodes(toFlowNodes(graph.nodes || [], agents, platform));
      setEdges(toFlowEdges(graph.edges || []));
      return;
    }
    if (internalUpdate.current) {
      internalUpdate.current = false;
      return;
    }
    if (externalSync.current) {
      externalSync.current = false;
      return;
    }
    setNodes(toFlowNodes(graph.nodes || [], agents, platform));
    setEdges(toFlowEdges(graph.edges || []));
  }, [graph, agents, platform, workflowId, setNodes, setEdges]);

  useEffect(() => {
    if (!nodes.length || didInitialFit.current) return;
    requestAnimationFrame(() => {
      fitView({ padding: 0.2, duration: 0 });
      didInitialFit.current = true;
    });
  }, [nodes.length, workflowId, fitView]);

  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      if (readOnly) return;
      const target = event.target as HTMLElement | null;
      if (target?.closest('input, textarea, select, [contenteditable="true"]')) return;

      const mod = event.metaKey || event.ctrlKey;
      if (!mod || event.key.toLowerCase() !== 'z') return;

      event.preventDefault();
      if (event.shiftKey) redo();
      else undo();
    };

    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  }, [readOnly, undo, redo]);

  const handleNodesChange = useCallback(
    (changes: NodeChange[]) => {
      if (readOnly) return;

      if (changes.some((c) => c.type === 'remove')) {
        pushHistory(nodes, edges);
      }

      if (changes.some((c) => c.type === 'position' && c.dragging) && !dragSnapshotTaken.current) {
        pushHistory(nodes, edges);
        dragSnapshotTaken.current = true;
      }

      if (changes.every((c) => c.type !== 'position' || !c.dragging)) {
        dragSnapshotTaken.current = false;
      }

      const removedIds = new Set(
        changes.filter((c): c is NodeChange & { type: 'remove'; id: string } => c.type === 'remove').map((c) => c.id),
      );

      const nextNodes = applyNodeChanges(changes, nodes);
      setNodes(nextNodes);

      let nextEdges = edges;
      if (removedIds.size > 0) {
        nextEdges = edges.filter((edge) => !removedIds.has(edge.source) && !removedIds.has(edge.target));
        setEdges(nextEdges);
      }

      if (changes.some((c) => c.type === 'remove' || (c.type === 'position' && !c.dragging))) {
        emitChange(nextNodes, nextEdges);
      }
    },
    [readOnly, nodes, edges, pushHistory, setNodes, emitChange],
  );

  const handleEdgesChange = useCallback(
    (changes: EdgeChange[]) => {
      if (readOnly) return;

      if (changes.some((c) => c.type === 'remove')) {
        pushHistory(nodes, edges);
      }

      const nextEdges = applyEdgeChanges(changes, edges);
      setEdges(nextEdges);

      if (changes.some((c) => c.type === 'remove')) {
        emitChange(nodes, nextEdges);
      }
    },
    [readOnly, nodes, edges, pushHistory, setEdges, emitChange],
  );

  const onConnect = useCallback(
    (connection: Connection) => {
      if (readOnly) return;
      const nextEdges = addEdge(
        {
          ...connection,
          sourceHandle: SOURCE_HANDLE,
          id: `e-${Date.now()}`,
          type: 'smoothstep',
          data: { edgeType: 'always', condition: null },
          style: edgeStyle('always'),
        },
        edges,
      );
      applyFlowState(nodes, nextEdges);
      onAction?.('Connected nodes manually');
    },
    [readOnly, edges, nodes, applyFlowState, onAction],
  );

  const addConnectedNode = useCallback(
    (sourceNodeId: string, agent: Agent) => {
      if (readOnly) return;
      const currentGraph = graphFromFlow(nodes, edges, graphRef.current);
      try {
        const result = addNodeAfter(sourceNodeId, agent, currentGraph);
        const nextNodes = toFlowNodes(result.graph.nodes || [], agents, platform);
        const nextEdges = toFlowEdges(result.graph.edges || []);
        applyFlowState(nextNodes, nextEdges);
        onAction?.(result.message);
      } catch {
        onAction?.('Could not add node');
      }
    },
    [readOnly, nodes, edges, agents, platform, applyFlowState, onAction],
  );

  const availableAgents = useMemo(
    () => agentsAvailableToAdd(graphFromFlow(nodes, edges, graphRef.current), agents),
    [nodes, edges, agents],
  );

  const editorContext = useMemo(
    () => ({
      agents,
      availableAgents,
      platform,
      readOnly,
      onAddConnectedNode: addConnectedNode,
    }),
    [agents, availableAgents, platform, readOnly, addConnectedNode],
  );

  return (
    <WorkflowEditorContext.Provider value={editorContext}>
      <div className="workflow-flow">
        {!readOnly && (
          <Stack direction="row" spacing={1} className="workflow-flow__toolbar">
            <Chip
              size="small"
              label="Drag blue dot → blue dot to connect · + adds new step · click output then input also works"
              variant="outlined"
            />
          </Stack>
        )}

        <ReactFlow
          nodes={nodes}
          edges={edges}
          nodeTypes={nodeTypes}
          defaultEdgeOptions={defaultEdgeOptions}
          onNodesChange={readOnly ? undefined : handleNodesChange}
          onEdgesChange={readOnly ? undefined : handleEdgesChange}
          onConnect={onConnect}
          connectOnClick={!readOnly}
          connectionRadius={32}
          fitViewOptions={{ padding: 0.2 }}
          colorMode="dark"
          proOptions={{ hideAttribution: true }}
          nodesDraggable={!readOnly}
          nodesConnectable={!readOnly}
          elementsSelectable={!readOnly}
          deleteKeyCode={readOnly ? null : ['Backspace', 'Delete']}
          snapToGrid
          snapGrid={[16, 16]}
        >
          <Background variant={BackgroundVariant.Dots} gap={18} size={1.2} color="rgba(148, 163, 184, 0.22)" />
          <Controls showInteractive={!readOnly} position="bottom-left" />
          <MiniMap
            position="bottom-right"
            nodeColor={(node) => {
              const label = String((node.data as { label?: string })?.label || node.id).toLowerCase();
              if (label.includes('triage')) return '#6366f1';
              if (label.includes('billing')) return '#f59e0b';
              if (label.includes('technical')) return '#a855f7';
              if (label.includes('respond')) return '#22c55e';
              return '#38bdf8';
            }}
            maskColor="rgba(11, 18, 32, 0.75)"
          />
        </ReactFlow>
      </div>
    </WorkflowEditorContext.Provider>
  );
}

const WorkflowCanvasInnerForwarded = forwardRef<WorkflowCanvasHandle, Props>(WorkflowCanvasInner);

const WorkflowCanvas = forwardRef<WorkflowCanvasHandle, Props>(function WorkflowCanvas(props, ref) {
  return (
    <ReactFlowProvider>
      <WorkflowCanvasInnerForwarded {...props} ref={ref} />
    </ReactFlowProvider>
  );
});

export default WorkflowCanvas;
