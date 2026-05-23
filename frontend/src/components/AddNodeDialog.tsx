import { useEffect, useMemo, useState } from 'react';
import {
  Button,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  FormControl,
  FormControlLabel,
  InputLabel,
  MenuItem,
  Radio,
  RadioGroup,
  Select,
  Typography,
} from '@mui/material';
import type { Agent, GraphDefinition } from '../api/client';
import { addNodeToGraph, agentsAvailableToAdd, describeAddAction } from '../lib/workflowGraphOps';

interface Props {
  open: boolean;
  onClose: () => void;
  agents: Agent[];
  graph: GraphDefinition;
  defaultSourceId?: string | null;
  onConfirm: (graph: GraphDefinition, message: string, newNodeId: string) => void;
}

export default function AddNodeDialog({
  open,
  onClose,
  agents,
  graph,
  defaultSourceId = null,
  onConfirm,
}: Props) {
  const nodes = graph.nodes || [];
  const isEmpty = nodes.length === 0;
  const availableAgents = useMemo(() => agentsAvailableToAdd(graph, agents), [graph, agents]);

  const [agentId, setAgentId] = useState('');
  const [placement, setPlacement] = useState<'first' | 'after'>('first');
  const [sourceId, setSourceId] = useState<string>('');

  useEffect(() => {
    if (!open) return;
    setAgentId(availableAgents[0]?.id || '');
    if (isEmpty) {
      setPlacement('first');
      setSourceId('');
    } else {
      setPlacement('after');
      const preferred = defaultSourceId && nodes.some((n) => n.id === defaultSourceId)
        ? defaultSourceId
        : nodes[0]?.id || '';
      setSourceId(preferred);
    }
  }, [open, availableAgents, isEmpty, nodes, defaultSourceId]);

  const preview = useMemo(() => {
    if (placement === 'first' || isEmpty) {
      return describeAddAction(null, graph);
    }
    return describeAddAction(sourceId, graph);
  }, [placement, isEmpty, sourceId, graph]);

  const handleConfirm = () => {
    const agent = availableAgents.find((a) => a.id === agentId);
    if (!agent) return;

    const effectiveSource = placement === 'first' || isEmpty ? null : sourceId;
    const result = addNodeToGraph(agent, graph, effectiveSource);
    onConfirm(result.graph, result.message, result.newNodeId);
    onClose();
  };

  return (
    <Dialog open={open} onClose={onClose} fullWidth maxWidth="sm">
      <DialogTitle>Add Agent Node</DialogTitle>
      <DialogContent sx={{ display: 'flex', flexDirection: 'column', gap: 2, pt: 1 }}>
        {availableAgents.length ? (
          <FormControl fullWidth>
            <InputLabel id="add-node-agent-label">Agent</InputLabel>
            <Select
              labelId="add-node-agent-label"
              label="Agent"
              value={agentId}
              onChange={(e) => setAgentId(e.target.value)}
            >
              {availableAgents.map((agent) => (
                <MenuItem key={agent.id} value={agent.id}>
                  {agent.name}
                </MenuItem>
              ))}
            </Select>
          </FormControl>
        ) : (
          <Typography variant="body2" color="text.secondary">
            Every agent is already on this workflow. Remove a step or create a new agent on the Agents page.
          </Typography>
        )}

        {availableAgents.length > 0 && (
          <>
            <FormControl>
              <Typography variant="subtitle2" gutterBottom>
                Placement
              </Typography>
              <RadioGroup
                value={placement}
                onChange={(e) => setPlacement(e.target.value as 'first' | 'after')}
              >
                <FormControlLabel
                  value="first"
                  control={<Radio />}
                  label="First node (empty workflow)"
                  disabled={!isEmpty}
                />
                <FormControlLabel
                  value="after"
                  control={<Radio />}
                  label="After an existing step"
                  disabled={isEmpty}
                />
              </RadioGroup>
            </FormControl>

            {placement === 'after' && !isEmpty && (
              <FormControl fullWidth>
                <InputLabel id="add-node-source-label">Add after</InputLabel>
                <Select
                  labelId="add-node-source-label"
                  label="Add after"
                  value={sourceId}
                  onChange={(e) => setSourceId(e.target.value)}
                >
                  {nodes.map((node) => (
                    <MenuItem key={node.id} value={node.id}>
                      {node.label}
                    </MenuItem>
                  ))}
                </Select>
              </FormControl>
            )}

            <Typography variant="body2" color="text.secondary">
              {preview}
            </Typography>
          </>
        )}
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose}>Cancel</Button>
        <Button
          variant="contained"
          onClick={handleConfirm}
          disabled={!agentId || !availableAgents.length || (placement === 'after' && !sourceId)}
        >
          Add connected step
        </Button>
      </DialogActions>
    </Dialog>
  );
}
