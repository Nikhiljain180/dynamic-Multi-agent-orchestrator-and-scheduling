import { useCallback, useEffect, useState } from 'react';
import {
  Alert,
  Box,
  Button,
  Card,
  Chip,
  IconButton,
  Snackbar,
  Stack,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Tooltip,
  Typography,
} from '@mui/material';
import DeleteOutlinedIcon from '@mui/icons-material/DeleteOutlined';
import PauseCircleOutlinedIcon from '@mui/icons-material/PauseCircleOutlined';
import PlayCircleOutlinedIcon from '@mui/icons-material/PlayCircleOutlined';
import ScheduleOutlinedIcon from '@mui/icons-material/ScheduleOutlined';
import { Link as RouterLink } from 'react-router-dom';
import { WorkflowScheduleEntry, api } from '../api/client';

function formatUtc(value: string) {
  try {
    return new Date(value).toLocaleString(undefined, { timeZone: 'UTC' });
  } catch {
    return value;
  }
}

export default function SchedulesPage() {
  const [schedules, setSchedules] = useState<WorkflowScheduleEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [toast, setToast] = useState<string | null>(null);
  const [busyId, setBusyId] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const items = await api.listSchedules();
      setSchedules(items);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load schedules');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
    const timer = window.setInterval(load, 30000);
    return () => window.clearInterval(timer);
  }, [load]);

  const handlePause = async (entry: WorkflowScheduleEntry) => {
    setBusyId(entry.workflow_id);
    try {
      const updated = await api.updateSchedule(entry.workflow_id, { enabled: false });
      setSchedules((prev) => prev.map((item) => (item.workflow_id === updated.workflow_id ? updated : item)));
      setToast(`Paused schedule for ${entry.workflow_name}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to pause schedule');
    } finally {
      setBusyId(null);
    }
  };

  const handleResume = async (entry: WorkflowScheduleEntry) => {
    setBusyId(entry.workflow_id);
    try {
      const updated = await api.updateSchedule(entry.workflow_id, { enabled: true });
      setSchedules((prev) => prev.map((item) => (item.workflow_id === updated.workflow_id ? updated : item)));
      setToast(`Resumed schedule for ${entry.workflow_name}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to resume schedule');
    } finally {
      setBusyId(null);
    }
  };

  const handleDelete = async (entry: WorkflowScheduleEntry) => {
    if (!window.confirm(`Delete schedule for "${entry.workflow_name}"? This will not delete the workflow.`)) {
      return;
    }
    setBusyId(entry.workflow_id);
    try {
      await api.deleteSchedule(entry.workflow_id);
      setSchedules((prev) => prev.filter((item) => item.workflow_id !== entry.workflow_id));
      setToast(`Deleted schedule for ${entry.workflow_name}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to delete schedule');
    } finally {
      setBusyId(null);
    }
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
            Schedules
          </Typography>
          <Typography variant="body2" color="text.secondary">
            View and manage cron jobs for workflow templates. All times are UTC. Cron fires on UTC clock minutes.
          </Typography>
        </Box>
        <Button variant="outlined" component={RouterLink} to="/workflows">
          Open Workflows
        </Button>
      </Stack>

      {error && (
        <Alert severity="error" sx={{ mb: 2 }} onClose={() => setError(null)}>
          {error}
        </Alert>
      )}

      <Card variant="outlined">
        {loading ? (
          <Box sx={{ py: 8, textAlign: 'center' }}>
            <Typography color="text.secondary">Loading schedules…</Typography>
          </Box>
        ) : schedules.length === 0 ? (
          <Box sx={{ py: 8, textAlign: 'center' }}>
            <ScheduleOutlinedIcon sx={{ fontSize: 40, color: 'text.secondary', mb: 1 }} />
            <Typography color="text.secondary" sx={{ mb: 1 }}>
              No scheduled workflows yet.
            </Typography>
            <Typography variant="body2" color="text.secondary">
              Set a cron expression on the Workflows page and click Save Graph.
            </Typography>
          </Box>
        ) : (
          <TableContainer>
            <Table size="small">
              <TableHead>
                <TableRow>
                  <TableCell>Workflow</TableCell>
                  <TableCell>Cron (UTC)</TableCell>
                  <TableCell>Run Input</TableCell>
                  <TableCell>Status</TableCell>
                  <TableCell>Saved (UTC)</TableCell>
                  <TableCell>Last run (UTC)</TableCell>
                  <TableCell align="right">Actions</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {schedules.map((entry) => {
                  const isBusy = busyId === entry.workflow_id;
                  return (
                    <TableRow key={entry.workflow_id} hover>
                      <TableCell>
                        <Stack spacing={0.5}>
                          <Typography variant="body2" sx={{ fontWeight: 600 }}>
                            {entry.workflow_name}
                          </Typography>
                          {entry.description ? (
                            <Typography variant="caption" color="text.secondary">
                              {entry.description}
                            </Typography>
                          ) : null}
                          {entry.is_template ? (
                            <Chip label="Template" size="small" color="secondary" sx={{ alignSelf: 'flex-start' }} />
                          ) : null}
                        </Stack>
                      </TableCell>
                      <TableCell>
                        <Typography variant="body2" sx={{ fontFamily: 'monospace' }}>
                          {entry.cron}
                        </Typography>
                      </TableCell>
                      <TableCell sx={{ maxWidth: 280 }}>
                        <Typography
                          variant="body2"
                          color="text.secondary"
                          sx={{
                            display: '-webkit-box',
                            WebkitLineClamp: 2,
                            WebkitBoxOrient: 'vertical',
                            overflow: 'hidden',
                          }}
                        >
                          {entry.input_text || '—'}
                        </Typography>
                      </TableCell>
                      <TableCell>
                        <Chip
                          label={entry.enabled ? 'Active' : 'Paused'}
                          size="small"
                          color={entry.enabled ? 'success' : 'default'}
                          variant={entry.enabled ? 'filled' : 'outlined'}
                        />
                      </TableCell>
                      <TableCell>
                        <Typography variant="caption" color="text.secondary">
                          {formatUtc(entry.updated_at)}
                        </Typography>
                      </TableCell>
                      <TableCell>
                        <Typography variant="caption" color="text.secondary">
                          {entry.last_run_at ? formatUtc(entry.last_run_at) : '—'}
                        </Typography>
                      </TableCell>
                      <TableCell align="right">
                        <Stack direction="row" spacing={0.5} sx={{ justifyContent: 'flex-end' }}>
                          {entry.enabled ? (
                            <Tooltip title="Pause">
                              <span>
                                <IconButton
                                  size="small"
                                  aria-label="Pause schedule"
                                  disabled={isBusy}
                                  onClick={() => handlePause(entry)}
                                >
                                  <PauseCircleOutlinedIcon fontSize="small" />
                                </IconButton>
                              </span>
                            </Tooltip>
                          ) : (
                            <Tooltip title="Resume">
                              <span>
                                <IconButton
                                  size="small"
                                  aria-label="Resume schedule"
                                  disabled={isBusy}
                                  onClick={() => handleResume(entry)}
                                >
                                  <PlayCircleOutlinedIcon fontSize="small" />
                                </IconButton>
                              </span>
                            </Tooltip>
                          )}
                          <Tooltip title="Delete schedule">
                            <span>
                              <IconButton
                                size="small"
                                color="error"
                                aria-label="Delete schedule"
                                disabled={isBusy}
                                onClick={() => handleDelete(entry)}
                              >
                                <DeleteOutlinedIcon fontSize="small" />
                              </IconButton>
                            </span>
                          </Tooltip>
                        </Stack>
                      </TableCell>
                    </TableRow>
                  );
                })}
              </TableBody>
            </Table>
          </TableContainer>
        )}
      </Card>

      <Snackbar
        open={Boolean(toast)}
        autoHideDuration={4000}
        onClose={() => setToast(null)}
        anchorOrigin={{ vertical: 'bottom', horizontal: 'right' }}
      >
        <Alert severity="success" onClose={() => setToast(null)} sx={{ width: '100%' }}>
          {toast}
        </Alert>
      </Snackbar>
    </Box>
  );
}
