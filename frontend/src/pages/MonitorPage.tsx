import { useEffect, useMemo, useState, type ReactNode } from 'react';
import {
  Box,
  Card,
  CardContent,
  Chip,
  FormControl,
  InputLabel,
  MenuItem,
  Paper,
  Select,
  Typography,
} from '@mui/material';
import { WorkflowRun, api } from '../api/client';
import { usePolling, useRunMonitor } from '../hooks/useRunMonitor';

function statusColor(status?: string): 'default' | 'warning' | 'info' | 'success' | 'error' {
  switch (status) {
    case 'queued':
      return 'warning';
    case 'running':
      return 'info';
    case 'completed':
      return 'success';
    case 'failed':
      return 'error';
    default:
      return 'default';
  }
}

export default function MonitorPage() {
  const [runs, setRuns] = useState<WorkflowRun[]>([]);
  const [selectedRunId, setSelectedRunId] = useState<string | null>(null);
  const runData = usePolling(() => (selectedRunId ? api.getRun(selectedRunId) : Promise.resolve(null)), 2000, Boolean(selectedRunId));
  const { logs, messages, tokens, status } = useRunMonitor(selectedRunId);

  useEffect(() => {
    api.listRuns().then(setRuns);
  }, []);

  useEffect(() => {
    if (runs.length && !selectedRunId) setSelectedRunId(runs[0].id);
  }, [runs, selectedRunId]);

  const historicalLogs = usePolling(
    () => (selectedRunId ? api.getRunLogs(selectedRunId) : Promise.resolve([])),
    3000,
    Boolean(selectedRunId),
  );
  const historicalMessages = usePolling(
    () => (selectedRunId ? api.getRunMessages(selectedRunId) : Promise.resolve([])),
    3000,
    Boolean(selectedRunId),
  );
  const historicalTokens = usePolling(
    () => (selectedRunId ? api.getRunTokens(selectedRunId) : Promise.resolve([])),
    3000,
    Boolean(selectedRunId),
  );

  const allLogs = useMemo(
    () => [...(historicalLogs || []), ...logs.map((l) => ({ ...l }))],
    [historicalLogs, logs],
  );
  const allMessages = useMemo(
    () => [...(historicalMessages || []), ...messages.map((m) => ({ ...m }))],
    [historicalMessages, messages],
  );
  const allTokens = useMemo(
    () => [...(historicalTokens || []), ...tokens.map((t) => ({ ...t }))],
    [historicalTokens, tokens],
  );
  const currentStatus = status || runData?.status;

  return (
    <Box>
      <Box
        sx={{
          mb: 3,
          display: 'flex',
          flexDirection: { xs: 'column', sm: 'row' },
          justifyContent: 'space-between',
          alignItems: { xs: 'stretch', sm: 'center' },
          gap: 2,
        }}
      >
        <Box>
          <Typography variant="h4" gutterBottom>
            Live Monitor
          </Typography>
          <Typography variant="body2" color="text.secondary">
            Stream logs, inter-agent messages, and token usage for workflow runs.
          </Typography>
        </Box>

        <FormControl sx={{ minWidth: 280 }} size="small">
          <InputLabel>Run</InputLabel>
          <Select
            label="Run"
            value={selectedRunId || ''}
            onChange={(e) => setSelectedRunId(e.target.value)}
          >
            {runs.map((r) => (
              <MenuItem key={r.id} value={r.id}>
                {r.id.slice(0, 8)} · {r.status} · {r.input_text.slice(0, 40)}
              </MenuItem>
            ))}
          </Select>
        </FormControl>
      </Box>

      {runData && (
        <Card sx={{ mb: 3 }}>
          <CardContent>
            <StackRow
              status={currentStatus}
              tokens={runData.total_tokens}
              cost={runData.total_cost}
            />
            {runData.output_text && (
              <Paper
                variant="outlined"
                sx={{
                  mt: 2,
                  p: 2,
                  bgcolor: 'rgba(148, 163, 184, 0.06)',
                  fontFamily: 'ui-monospace, monospace',
                  fontSize: '0.9rem',
                  whiteSpace: 'pre-wrap',
                }}
              >
                {runData.output_text}
              </Paper>
            )}
            {runData.error && (
              <Typography color="error" sx={{ mt: 2 }}>
                {runData.error}
              </Typography>
            )}
          </CardContent>
        </Card>
      )}

      {!runs.length && (
        <Card sx={{ p: 6, textAlign: 'center', mb: 3 }}>
          <Typography color="text.secondary">No runs yet. Start a workflow to see live monitoring data.</Typography>
        </Card>
      )}

      <Box
        sx={{
          display: 'grid',
          gridTemplateColumns: { xs: '1fr', lg: '1fr 1fr' },
          gap: 2,
        }}
      >
        <MonitorPanel title="Logs" empty="No logs yet">
          {allLogs.map((log, i) => (
            <Box
              key={i}
              sx={{
                py: 1,
                borderBottom: '1px solid',
                borderColor: 'divider',
                fontFamily: 'ui-monospace, monospace',
                fontSize: '0.85rem',
              }}
            >
              <Chip
                label={String((log as { level?: string }).level || 'info')}
                size="small"
                sx={{ mr: 1, mb: 0.5, height: 20, fontSize: '0.7rem' }}
              />
              {String((log as { message?: string }).message || '')}
            </Box>
          ))}
        </MonitorPanel>

        <MonitorPanel title="Inter-Agent Messages" empty="No messages yet">
          {allMessages.map((msg, i) => (
            <Box key={i} sx={{ py: 1, borderBottom: '1px solid', borderColor: 'divider' }}>
              <Chip label={String((msg as { role?: string }).role || 'agent')} size="small" sx={{ mb: 0.5 }} />
              <Typography variant="body2">
                {String((msg as { content?: string }).content || '').slice(0, 400)}
              </Typography>
            </Box>
          ))}
        </MonitorPanel>

        <MonitorPanel title="Token / Cost Tracking" empty="No token data yet" wide>
          {allTokens.map((t, i) => (
            <Box
              key={i}
              sx={{
                py: 1,
                borderBottom: '1px solid',
                borderColor: 'divider',
                fontFamily: 'ui-monospace, monospace',
                fontSize: '0.85rem',
              }}
            >
              {String((t as { node_name?: string }).node_name)} · tokens={String((t as { total_tokens?: number }).total_tokens)} · $
              {Number((t as { estimated_cost?: number }).estimated_cost || 0).toFixed(6)}
            </Box>
          ))}
        </MonitorPanel>
      </Box>
    </Box>
  );
}

function StackRow({ status, tokens, cost }: { status?: string; tokens: number; cost: number }) {
  return (
    <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1, alignItems: 'center' }}>
      <Typography variant="body2" color="text.secondary">
        Status
      </Typography>
      <Chip label={status || 'unknown'} color={statusColor(status)} size="small" />
      <Typography variant="body2" color="text.secondary" sx={{ ml: { sm: 2 } }}>
        Tokens: {tokens}
      </Typography>
      <Typography variant="body2" color="text.secondary">
        Cost: ${cost.toFixed(6)}
      </Typography>
    </Box>
  );
}

function MonitorPanel({
  title,
  empty,
  wide,
  children,
}: {
  title: string;
  empty: string;
  wide?: boolean;
  children: ReactNode;
}) {
  const hasContent = Array.isArray(children) ? children.length > 0 : Boolean(children);

  return (
    <Card sx={{ gridColumn: wide ? { lg: '1 / -1' } : undefined, display: 'flex', flexDirection: 'column' }}>
      <CardContent sx={{ pb: 1 }}>
        <Typography variant="h6">{title}</Typography>
      </CardContent>
      <Box sx={{ px: 2, pb: 2, maxHeight: 400, overflow: 'auto', flexGrow: 1 }}>
        {!hasContent ? (
          <Typography variant="body2" color="text.secondary" sx={{ py: 4, textAlign: 'center' }}>
            {empty}
          </Typography>
        ) : (
          children
        )}
      </Box>
    </Card>
  );
}
