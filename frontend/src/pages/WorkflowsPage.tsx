import { useEffect, useMemo, useRef, useState } from 'react';
import {
  Alert,
  Box,
  Button,
  Card,
  CardActionArea,
  CardContent,
  Chip,
  FormControl,
  IconButton,
  InputLabel,
  MenuItem,
  Paper,
  Select,
  Snackbar,
  Stack,
  TextField,
  Typography,
} from '@mui/material';
import AddIcon from '@mui/icons-material/Add';
import DeleteIcon from '@mui/icons-material/Delete';
import PlayArrowIcon from '@mui/icons-material/PlayArrow';
import SaveOutlinedIcon from '@mui/icons-material/SaveOutlined';
import { Agent, PlatformLLMSettings, Workflow, api } from '../api/client';
import AddNodeDialog from '../components/AddNodeDialog';
import WorkflowCanvas, { type WorkflowCanvasHandle } from '../components/WorkflowCanvas';
import {
  agentsAvailableToAdd,
  connectOrphanAfter,
  findOrphanNodes,
  findUnreachableNodes,
  nodeLabel,
  removeEdge,
  sanitizeGraph,
  updateEdge,
} from '../lib/workflowGraphOps';
import { getTemplateUiConfig, templateSupportsSchedule } from '../lib/workflowTemplateConfig';
import { cronValidationError, normalizeCron } from '../lib/cronUtils';

const DEFAULT_RUN_INPUT = 'Benefits of multi-agent orchestration for customer support';

function loadRunSettings(graph: Workflow['graph_definition'] | undefined) {
  const schedule = graph?.schedule;
  return {
    inputText: schedule?.input_text?.trim() || DEFAULT_RUN_INPUT,
    scheduleCron: schedule?.cron?.trim() || '',
  };
}

async function prepareGraph(graph: Workflow['graph_definition']) {
  const preserved = {
    template_type: graph.template_type,
    schedule: graph.schedule,
  };
  const sanitized = sanitizeGraph(graph);
  try {
    const repaired = await api.repairWorkflowGraph(sanitized);
    return {
      ...repaired,
      ...(preserved.template_type ? { template_type: preserved.template_type } : {}),
      ...(preserved.schedule ? { schedule: preserved.schedule } : {}),
    };
  } catch {
    return sanitized;
  }
}

export default function WorkflowsPage() {
  const canvasRef = useRef<WorkflowCanvasHandle>(null);
  const [workflows, setWorkflows] = useState<Workflow[]>([]);
  const [agents, setAgents] = useState<Agent[]>([]);
  const [selected, setSelected] = useState<Workflow | null>(null);
  const [graph, setGraph] = useState<Workflow['graph_definition'] | undefined>();
  const [inputText, setInputText] = useState(DEFAULT_RUN_INPUT);
  const [scheduleCron, setScheduleCron] = useState('');
  const [lastRunId, setLastRunId] = useState<string | null>(null);
  const [toast, setToast] = useState<string | null>(null);
  const [platform, setPlatform] = useState<PlatformLLMSettings | null>(null);
  const [addDialogOpen, setAddDialogOpen] = useState(false);
  const [repairOrphanId, setRepairOrphanId] = useState<string>('');
  const [repairSourceId, setRepairSourceId] = useState<string>('');

  const load = async (keepWorkflowId?: string | null) => {
    const [wf, ag, platformSettings] = await Promise.all([
      api.listWorkflows(),
      api.listAgents(),
      api.getPlatformLLMSettings(),
    ]);
    setWorkflows(wf);
    setAgents(ag);
    setPlatform(platformSettings);
    const next = (keepWorkflowId ? wf.find((item) => item.id === keepWorkflowId) : null) ?? wf[0] ?? null;
    if (next) {
      const repaired = await prepareGraph(next.graph_definition);
      setSelected({ ...next, graph_definition: repaired });
      setGraph(repaired);
      const runSettings = loadRunSettings(repaired);
      setInputText(runSettings.inputText);
      setScheduleCron(runSettings.scheduleCron);
    } else {
      setSelected(null);
      setGraph(undefined);
    }
  };

  useEffect(() => {
    load();
  }, []);

  useEffect(() => {
    if (!selected?.graph_definition) {
      setGraph(undefined);
      return;
    }
    const runSettings = loadRunSettings(selected.graph_definition);
    setInputText(runSettings.inputText);
    setScheduleCron(runSettings.scheduleCron);
    let cancelled = false;
    prepareGraph(selected.graph_definition).then((repaired) => {
      if (cancelled) return;
      setGraph(repaired);
      if (JSON.stringify(repaired) !== JSON.stringify(selected.graph_definition)) {
        setSelected((prev) => (prev ? { ...prev, graph_definition: repaired } : prev));
      }
    });
    return () => {
      cancelled = true;
    };
  }, [selected?.id]);

  const orphans = useMemo(() => (graph ? findOrphanNodes(graph) : []), [graph]);
  const unreachable = useMemo(() => (graph ? findUnreachableNodes(graph) : []), [graph]);
  const addableAgents = useMemo(
    () => (graph ? agentsAvailableToAdd(graph, agents) : agents),
    [graph, agents],
  );
  const templateUi = useMemo(
    () => getTemplateUiConfig(graph, selected?.name),
    [graph, selected?.name],
  );

  const saveGraph = async () => {
    if (!selected || !graph) return;
    const ui = getTemplateUiConfig(graph, selected.name);
    const cron = normalizeCron(scheduleCron);
    if (ui.showSchedule && cron) {
      const cronError = cronValidationError(cron);
      if (cronError) {
        setToast(cronError);
        return;
      }
    }
    const base: Workflow['graph_definition'] = { ...graph };
    if (ui.showSchedule && cron) {
      base.schedule = {
        cron,
        input_text: inputText.trim() || null,
        enabled: graph.schedule?.enabled ?? true,
      };
    } else {
      delete base.schedule;
    }
    const repaired = await prepareGraph(base);
    await api.updateWorkflow(selected.id, { graph_definition: repaired });
    setSelected((prev) => (prev ? { ...prev, graph_definition: repaired } : prev));
    setGraph(repaired);
    setToast('Workflow graph saved');
    await load(selected.id);
  };

  const runWorkflow = async () => {
    if (!selected) return;
    const run = await api.startRun(selected.id, inputText);
    setLastRunId(run.id);
    setToast(`Run started · ${run.id.slice(0, 8)}`);
  };

  const handleGraphChange = (nextGraph: typeof graph) => {
    if (!nextGraph) return;
    const clean = sanitizeGraph(nextGraph);
    setSelected((prev) => (prev ? { ...prev, graph_definition: clean } : prev));
  };

  const handleDialogConfirm = (nextGraph: NonNullable<typeof graph>, message: string, newNodeId: string) => {
    const clean = sanitizeGraph(nextGraph);
    setSelected((prev) => (prev ? { ...prev, graph_definition: clean } : prev));
    canvasRef.current?.applyGraphResult({ graph: clean, newNodeId, message });
  };

  const handleDeleteEdge = (edgeId: string) => {
    if (!graph) return;
    const nextGraph = removeEdge(edgeId, graph);
    canvasRef.current?.syncGraph(nextGraph);
    setSelected((prev) => (prev ? { ...prev, graph_definition: nextGraph } : prev));
    setToast('Edge removed');
  };

  const handleUpdateEdge = (
    edgeId: string,
    patch: Partial<{ edge_type: string; condition: string | null }>,
  ) => {
    if (!graph) return;
    const nextGraph = updateEdge(edgeId, graph, patch);
    canvasRef.current?.syncGraph(nextGraph);
    setSelected((prev) => (prev ? { ...prev, graph_definition: nextGraph } : prev));
  };

  const handleRepairRouting = async () => {
    if (!graph) return;
    const nextGraph = await prepareGraph(graph);
    canvasRef.current?.syncGraph(nextGraph);
    setSelected((prev) => (prev ? { ...prev, graph_definition: nextGraph } : prev));
    setGraph(nextGraph);
    setToast('Routing conditions repaired — click Save Graph');
  };

  const effectiveRepairOrphanId = repairOrphanId || orphans[0]?.id || '';

  const handleRepairOrphan = () => {
    if (!effectiveRepairOrphanId || !repairSourceId || !graph) return;
    const nextGraph = connectOrphanAfter(effectiveRepairOrphanId, repairSourceId, graph);
    canvasRef.current?.syncGraph(nextGraph);
    setSelected((prev) => (prev ? { ...prev, graph_definition: nextGraph } : prev));
    const orphanLabel = graph?.nodes?.find((n) => n.id === effectiveRepairOrphanId)?.label || effectiveRepairOrphanId;
    const sourceLabel = graph?.nodes?.find((n) => n.id === repairSourceId)?.label || repairSourceId;
    setToast(`Connected ${orphanLabel} after ${sourceLabel}`);
    setRepairOrphanId('');
    setRepairSourceId('');
  };

  return (
    <Box>
      <Stack
        spacing={2}
        sx={{
          mb: 3,
          flexDirection: { xs: 'column', sm: 'row' },
          justifyContent: 'space-between',
          alignItems: { xs: 'flex-start', sm: 'center' },
        }}
      >
        <Box>
          <Typography variant="h4" gutterBottom>
            Workflows
          </Typography>
          <Typography variant="body2" color="text.secondary">
            Compose multi-agent pipelines visually and run them from the canvas.
          </Typography>
        </Box>
        {lastRunId && (
          <Chip label={`Last run: ${lastRunId.slice(0, 8)}`} color="primary" variant="outlined" />
        )}
      </Stack>

      <Box
        sx={{
          display: 'grid',
          gridTemplateColumns: { xs: '1fr', md: '1fr 1fr', lg: 'repeat(3, 1fr)' },
          gap: 2,
          mb: 3,
        }}
      >
        {workflows.map((wf) => {
          const isSelected = selected?.id === wf.id;
          const cron = wf.graph_definition?.schedule?.cron?.trim();
          const showScheduleChip = cron && templateSupportsSchedule(wf.graph_definition, wf.name);
          return (
            <Card
              key={wf.id}
              variant="outlined"
              sx={{
                borderColor: isSelected ? 'primary.main' : 'divider',
                boxShadow: isSelected ? '0 0 0 1px rgba(56, 189, 248, 0.35)' : 'none',
              }}
            >
              <CardActionArea
                onClick={async () => {
                  const clean = await prepareGraph(wf.graph_definition);
                  setSelected({ ...wf, graph_definition: clean });
                  setGraph(clean);
                  const runSettings = loadRunSettings(clean);
                  setInputText(runSettings.inputText);
                  setScheduleCron(runSettings.scheduleCron);
                }}
              >
                <CardContent>
                  <Stack
                    direction="row"
                    spacing={1}
                    sx={{ justifyContent: 'space-between', alignItems: 'flex-start' }}
                  >
                    <Typography variant="h6" component="h3">
                      {wf.name}
                    </Typography>
                    {wf.is_template && <Chip label="Template" size="small" color="secondary" />}
                  </Stack>
                  <Typography variant="body2" color="text.secondary" sx={{ mt: 1 }}>
                    {wf.description}
                  </Typography>
                  {showScheduleChip ? (
                    <Chip
                      label={`Scheduled: ${cron}`}
                      size="small"
                      color="info"
                      variant="outlined"
                      sx={{ mt: 1.5 }}
                    />
                  ) : null}
                </CardContent>
              </CardActionArea>
            </Card>
          );
        })}
      </Box>

      {selected && graph && (
        <Box
          sx={{
            display: 'grid',
            gridTemplateColumns: { xs: '1fr', lg: '1fr 340px' },
            gap: 2,
            alignItems: 'stretch',
            minHeight: { xs: 560, lg: 'calc(100vh - 100px)' },
          }}
        >
          <Paper
            variant="outlined"
            sx={{
              overflow: 'hidden',
              minHeight: { xs: 560, lg: 'calc(100vh - 100px)' },
              height: { lg: 'calc(100vh - 100px)' },
              display: 'flex',
              flexDirection: 'column',
              bgcolor: '#0b1220',
            }}
          >
            <WorkflowCanvas
              ref={canvasRef}
              graph={graph}
              workflowId={selected.id}
              agents={agents}
              platform={platform}
              onChange={handleGraphChange}
              onAction={setToast}
            />
          </Paper>

          <Paper
            variant="outlined"
            sx={{
              p: 2.5,
              minHeight: { xs: 'auto', lg: 'calc(100vh - 100px)' },
            }}
          >
            <Typography variant="h6" gutterBottom>
              {selected.name}
            </Typography>
            <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
              {selected.description}
            </Typography>

            {orphans.length > 0 && (
              <Alert severity="warning" sx={{ mb: 2 }}>
                <Typography variant="body2" sx={{ mb: 1 }}>
                  Disconnected nodes: {orphans.map((n) => n.label).join(', ')}
                </Typography>
                <Stack spacing={1} sx={{ mt: 1 }}>
                  {orphans.length > 1 && (
                    <FormControl size="small" fullWidth>
                      <InputLabel id="repair-orphan-label">Node to connect</InputLabel>
                      <Select
                        labelId="repair-orphan-label"
                        label="Node to connect"
                        value={repairOrphanId}
                        onChange={(e) => setRepairOrphanId(e.target.value)}
                      >
                        {orphans.map((n) => (
                          <MenuItem key={n.id} value={n.id}>
                            {n.label}
                          </MenuItem>
                        ))}
                      </Select>
                    </FormControl>
                  )}
                  <FormControl size="small" fullWidth>
                    <InputLabel id="repair-source-label">Connect after</InputLabel>
                    <Select
                      labelId="repair-source-label"
                      label="Connect after"
                      value={repairSourceId}
                      onChange={(e) => setRepairSourceId(e.target.value)}
                    >
                      {(graph.nodes || [])
                        .filter((n) => n.id !== effectiveRepairOrphanId)
                        .map((n) => (
                          <MenuItem key={n.id} value={n.id}>
                            {n.label}
                          </MenuItem>
                        ))}
                    </Select>
                  </FormControl>
                  <Button
                    size="small"
                    variant="outlined"
                    onClick={handleRepairOrphan}
                    disabled={!effectiveRepairOrphanId || !repairSourceId}
                  >
                    Connect
                  </Button>
                </Stack>
              </Alert>
            )}

            {unreachable.length > 0 && (
              <Alert severity="info" sx={{ mb: 2 }}>
                Unreachable from entry: {unreachable.map((n) => n.label).join(', ')}
              </Alert>
            )}

            {templateUi.channelHint ? (
              <Alert severity="info" sx={{ mb: 2 }}>
                {templateUi.channelHint}
              </Alert>
            ) : null}

            {templateUi.showRunInput ? (
              <TextField
                label="Run Input"
                fullWidth
                multiline
                minRows={2}
                maxRows={6}
                value={inputText}
                onChange={(e) => setInputText(e.target.value)}
                helperText="Used for manual runs and scheduled runs."
                sx={{ mb: 2, '& textarea': { resize: 'none', overflow: 'hidden !important' } }}
              />
            ) : null}

            {templateUi.showSchedule ? (
              <TextField
                label="Schedule (cron, UTC)"
                fullWidth
                placeholder="*/5 * * * *"
                value={scheduleCron}
                onChange={(e) => setScheduleCron(e.target.value)}
                helperText="UTC. Use spaces: */2 * * * * (every 2 min). Manage jobs in Schedules."
                sx={{ mb: 2 }}
              />
            ) : null}

            <Stack spacing={1}>
              {templateUi.showManualRun ? (
                <Button
                  variant="contained"
                  startIcon={<PlayArrowIcon />}
                  onClick={runWorkflow}
                  fullWidth
                  disabled={orphans.length > 0}
                >
                  Run Workflow
                </Button>
              ) : null}
              {templateUi.showManualRun && orphans.length > 0 && (
                <Typography variant="caption" color="text.secondary">
                  Fix disconnected nodes before running.
                </Typography>
              )}
              <Button variant="outlined" startIcon={<SaveOutlinedIcon />} onClick={saveGraph} fullWidth>
                Save Graph
              </Button>
              <Button
                variant="outlined"
                startIcon={<AddIcon />}
                onClick={() => setAddDialogOpen(true)}
                fullWidth
                disabled={!addableAgents.length}
              >
                Add Agent Node
              </Button>
              {!addableAgents.length && (
                <Typography variant="caption" color="text.secondary">
                  All agents are already on this workflow.
                </Typography>
              )}
            </Stack>

            <Typography variant="subtitle2" sx={{ mt: 3, mb: 1 }}>
              Edges
            </Typography>
            <Button size="small" variant="text" onClick={handleRepairRouting} sx={{ mb: 1 }}>
              Repair routing conditions
            </Button>
            <Stack spacing={1}>
              {(graph.edges || []).length ? (
                graph.edges.map((e) => (
                  <Paper key={e.id} variant="outlined" sx={{ p: 1 }}>
                    <Stack direction="row" spacing={0.5} sx={{ alignItems: 'center', mb: 0.75 }}>
                      <Typography variant="caption" sx={{ flex: 1, fontWeight: 600 }}>
                        {nodeLabel(graph, e.source)} → {nodeLabel(graph, e.target)}
                      </Typography>
                      <IconButton size="small" aria-label="Delete edge" onClick={() => handleDeleteEdge(e.id)}>
                        <DeleteIcon fontSize="small" />
                      </IconButton>
                    </Stack>
                    <Stack spacing={0.75}>
                      <FormControl size="small" fullWidth>
                        <InputLabel id={`edge-type-${e.id}`}>Type</InputLabel>
                        <Select
                          labelId={`edge-type-${e.id}`}
                          label="Type"
                          value={e.edge_type}
                          onChange={(ev) =>
                            handleUpdateEdge(e.id, {
                              edge_type: ev.target.value,
                              condition: ev.target.value === 'always' ? null : e.condition ?? '',
                            })
                          }
                        >
                          <MenuItem value="always">always</MenuItem>
                          <MenuItem value="if_condition">if_condition</MenuItem>
                          <MenuItem value="feedback">feedback</MenuItem>
                        </Select>
                      </FormControl>
                      {e.edge_type !== 'always' && (
                        <TextField
                          size="small"
                          fullWidth
                          label="Condition"
                          placeholder="INTENT: research"
                          value={e.condition ?? ''}
                          onChange={(ev) => handleUpdateEdge(e.id, { condition: ev.target.value })}
                          helperText="Matches triage output or user message (e.g. INTENT: research)"
                        />
                      )}
                    </Stack>
                  </Paper>
                ))
              ) : (
                <Typography variant="caption" color="text.secondary">
                  No edges defined
                </Typography>
              )}
            </Stack>
          </Paper>

          <AddNodeDialog
            open={addDialogOpen}
            onClose={() => setAddDialogOpen(false)}
            agents={agents}
            graph={graph}
            onConfirm={handleDialogConfirm}
          />
        </Box>
      )}

      {!workflows.length && (
        <Card sx={{ p: 6, textAlign: 'center' }}>
          <Typography color="text.secondary">No workflows yet.</Typography>
        </Card>
      )}

      <Snackbar open={Boolean(toast)} autoHideDuration={4000} onClose={() => setToast(null)} anchorOrigin={{ vertical: 'bottom', horizontal: 'right' }}>
        <Alert severity="success" onClose={() => setToast(null)} sx={{ width: '100%' }}>
          {toast}
        </Alert>
      </Snackbar>
    </Box>
  );
}
