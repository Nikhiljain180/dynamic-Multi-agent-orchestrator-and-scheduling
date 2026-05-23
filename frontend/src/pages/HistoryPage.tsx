import { useEffect, useState } from 'react';
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
import { AgentMessage, WorkflowRun, api } from '../api/client';

export default function HistoryPage() {
  const [messages, setMessages] = useState<AgentMessage[]>([]);
  const [runs, setRuns] = useState<WorkflowRun[]>([]);
  const [filterRunId, setFilterRunId] = useState('');

  useEffect(() => {
    Promise.all([api.getAllMessages(), api.listRuns()]).then(([msgs, runList]) => {
      setMessages(msgs);
      setRuns(runList);
    });
  }, []);

  const filtered = filterRunId ? messages.filter((m) => m.run_id === filterRunId) : messages;

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
            Message History
          </Typography>
          <Typography variant="body2" color="text.secondary">
            Persisted conversations from workflow runs and external channels.
          </Typography>
        </Box>

        <FormControl sx={{ minWidth: 280 }} size="small">
          <InputLabel>Filter by run</InputLabel>
          <Select
            label="Filter by run"
            value={filterRunId}
            onChange={(e) => setFilterRunId(e.target.value)}
          >
            <MenuItem value="">All runs</MenuItem>
            {runs.map((r) => (
              <MenuItem key={r.id} value={r.id}>
                {r.id.slice(0, 8)} · {r.input_text.slice(0, 30)}
              </MenuItem>
            ))}
          </Select>
        </FormControl>
      </Box>

      <Card>
        <CardContent sx={{ p: 0, '&:last-child': { pb: 0 } }}>
          {filtered.length === 0 && (
            <Box sx={{ py: 8, textAlign: 'center' }}>
              <Typography color="text.secondary">
                No messages yet. Run a workflow or send a Telegram message.
              </Typography>
            </Box>
          )}

          {filtered.map((msg, index) => (
            <Paper
              key={msg.id}
              variant="outlined"
              sx={{
                m: 2,
                mt: index === 0 ? 2 : 0,
                p: 2,
                bgcolor: 'rgba(148, 163, 184, 0.04)',
              }}
            >
              <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.75, mb: 1 }}>
                <Typography variant="caption" color="text.secondary">
                  {new Date(msg.created_at).toLocaleString()}
                </Typography>
                <Chip label={`run ${msg.run_id.slice(0, 8)}`} size="small" variant="outlined" />
                <Chip label={msg.role} size="small" />
                {msg.channel && <Chip label={msg.channel} size="small" color="secondary" variant="outlined" />}
              </Box>
              <Typography variant="body2" sx={{ whiteSpace: 'pre-wrap' }}>
                {msg.content}
              </Typography>
            </Paper>
          ))}
        </CardContent>
      </Card>
    </Box>
  );
}
