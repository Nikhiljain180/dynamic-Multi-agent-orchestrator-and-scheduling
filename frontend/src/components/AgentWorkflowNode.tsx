import { memo, useState, type CSSProperties, type MouseEvent, type PointerEvent } from 'react';
import { Handle, Position, type NodeProps } from '@xyflow/react';
import { ListItemText, Menu, MenuItem, Paper, Typography } from '@mui/material';
import AddIcon from '@mui/icons-material/Add';
import SmartToyOutlinedIcon from '@mui/icons-material/SmartToyOutlined';
import AccountTreeOutlinedIcon from '@mui/icons-material/AccountTreeOutlined';
import SupportAgentOutlinedIcon from '@mui/icons-material/SupportAgentOutlined';
import SummarizeOutlinedIcon from '@mui/icons-material/SummarizeOutlined';
import ReplyOutlinedIcon from '@mui/icons-material/ReplyOutlined';
import { useWorkflowEditor } from './WorkflowEditorContext';
import { agentNodeSubtitle } from '../api/client';
import './workflow-canvas.css';

export type AgentNodeData = {
  label: string;
  agentId?: string;
  subtitle?: string;
};

function nodeTheme(id: string, label: string) {
  const key = `${id} ${label}`.toLowerCase();
  if (key.includes('triage')) {
    return { accent: '#6366f1', icon: AccountTreeOutlinedIcon, badge: 'Router' };
  }
  if (key.includes('billing')) {
    return { accent: '#f59e0b', icon: SupportAgentOutlinedIcon, badge: 'Specialist' };
  }
  if (key.includes('technical') || key.includes('tech')) {
    return { accent: '#a855f7', icon: SupportAgentOutlinedIcon, badge: 'Specialist' };
  }
  if (key.includes('respond')) {
    return { accent: '#22c55e', icon: ReplyOutlinedIcon, badge: 'Output' };
  }
  if (key.includes('brief') || key.includes('research')) {
    return { accent: '#0ea5e9', icon: SummarizeOutlinedIcon, badge: 'Agent' };
  }
  if (key.includes('summary') || key.includes('writer')) {
    return { accent: '#14b8a6', icon: SummarizeOutlinedIcon, badge: 'Agent' };
  }
  if (key.includes('review')) {
    return { accent: '#f97316', icon: SmartToyOutlinedIcon, badge: 'Review' };
  }
  return { accent: '#38bdf8', icon: SmartToyOutlinedIcon, badge: 'Agent' };
}

function stopFlowDrag(event: PointerEvent | MouseEvent) {
  event.stopPropagation();
  event.preventDefault();
}

function AgentWorkflowNodeComponent({ id, data, selected }: NodeProps) {
  const nodeData = data as AgentNodeData;
  const label = nodeData.label || id;
  const theme = nodeTheme(id, label);
  const Icon = theme.icon;
  const { availableAgents, platform, readOnly, onAddConnectedNode } = useWorkflowEditor();
  const [menuAnchor, setMenuAnchor] = useState<HTMLElement | null>(null);

  const openAgentMenu = (event: MouseEvent<HTMLElement>) => {
    stopFlowDrag(event);
    if (readOnly || !availableAgents.length) return;
    setMenuAnchor(event.currentTarget);
  };

  const pickAgent = (agentId: string) => {
    const agent = availableAgents.find((a) => a.id === agentId);
    if (agent) onAddConnectedNode(id, agent);
    setMenuAnchor(null);
  };

  return (
    <div
      className={`wf-node-shell ${selected ? 'wf-node-shell--selected' : ''}`}
      style={{ '--wf-accent': theme.accent } as CSSProperties}
    >
      <Handle
        type="target"
        position={Position.Left}
        id="in"
        className="wf-handle wf-handle--target"
        isConnectable={!readOnly}
      />

      <div className="wf-node">
        <div className="wf-node__header">
          <span className="wf-node__icon">
            <Icon fontSize="small" />
          </span>
          <div className="wf-node__titles">
            <div className="wf-node__label">{label}</div>
            <div className="wf-node__badge">{theme.badge}</div>
          </div>
        </div>
        <div className="wf-node__body">
          <div className="wf-node__meta">Agent node</div>
          {nodeData.subtitle && <div className="wf-node__subtitle">{nodeData.subtitle}</div>}
        </div>
      </div>

      <div className="wf-node__output nodrag nopan nowheel">
        <span className="wf-node__stem" aria-hidden />
      </div>

      <Handle
        type="source"
        position={Position.Right}
        className="wf-handle wf-handle--source"
        id="out"
        isConnectable={!readOnly}
      />

      {!readOnly && (
        <button
          type="button"
          className="wf-node__add-btn nodrag nopan nowheel"
          aria-label="Add next node"
          title="Add next node (creates new connected step)"
          onClick={openAgentMenu}
        >
          <AddIcon sx={{ fontSize: 18 }} />
        </button>
      )}

      <Menu
        anchorEl={menuAnchor}
        open={Boolean(menuAnchor)}
        onClose={() => setMenuAnchor(null)}
        anchorOrigin={{ vertical: 'center', horizontal: 'right' }}
        transformOrigin={{ vertical: 'center', horizontal: 'left' }}
        slotProps={{ paper: { sx: { minWidth: 260, ml: 1.5 } } }}
      >
        <Paper elevation={0} sx={{ px: 2, py: 1, bgcolor: 'transparent' }}>
          <Typography variant="caption" color="text.secondary">
            Creates a new connected step after this node
          </Typography>
        </Paper>
        {availableAgents.length ? (
          availableAgents.map((agent) => (
            <MenuItem key={agent.id} onClick={() => pickAgent(agent.id)}>
              <ListItemText primary={agent.name} secondary={agentNodeSubtitle(agent, platform)} />
            </MenuItem>
          ))
        ) : (
          <Paper elevation={0} sx={{ px: 2, py: 1.5, bgcolor: 'transparent' }}>
            <Typography variant="body2" color="text.secondary">
              All agents are already on this workflow.
            </Typography>
          </Paper>
        )}
      </Menu>
    </div>
  );
}

export default memo(AgentWorkflowNodeComponent);
