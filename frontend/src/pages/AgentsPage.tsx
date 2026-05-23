import { useEffect, useState } from 'react';
import {
  Alert,
  Box,
  Button,
  Card,
  CardActions,
  CardContent,
  Checkbox,
  Chip,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  FormControl,
  FormControlLabel,
  FormHelperText,
  InputLabel,
  MenuItem,
  Select,
  Stack,
  TextField,
  Typography,
} from '@mui/material';
import AddIcon from '@mui/icons-material/Add';
import DeleteIcon from '@mui/icons-material/Delete';
import EditOutlinedIcon from '@mui/icons-material/EditOutlined';
import { Agent, PlatformLLMSettings, ToolInfo, api, displayAgentLLM, modelsForProvider } from '../api/client';

const emptyAgent: Partial<Agent> & { api_key?: string } = {
  name: '',
  role: '',
  system_prompt: '',
  model: 'llama-3.1-8b-instant',
  provider: null,
  use_platform_api_key: true,
  tools: [],
  channels: {},
  memory_config: { short_term: true, long_term: false },
  skills: [],
  interaction_rules: '',
  guardrails: { max_tokens: 2000, allowed_tools: [], blocked_patterns: [] },
};

export default function AgentsPage() {
  const [agents, setAgents] = useState<Agent[]>([]);
  const [tools, setTools] = useState<ToolInfo[]>([]);
  const [platform, setPlatform] = useState<PlatformLLMSettings | null>(null);
  const [form, setForm] = useState<Partial<Agent> & { api_key?: string }>(emptyAgent);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [modalOpen, setModalOpen] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);

  const load = async () => {
    const [agentList, toolList, platformSettings] = await Promise.all([
      api.listAgents(),
      api.listTools(),
      api.getPlatformLLMSettings(),
    ]);
    setAgents(agentList);
    setTools(toolList);
    setPlatform(platformSettings);
  };

  useEffect(() => {
    load();
  }, []);

  const selectedProvider = form.provider || platform?.provider || 'groq';
  const modelOptions = platform ? modelsForProvider(platform, selectedProvider) : ['llama-3.1-8b-instant'];
  const isEditing = Boolean(editingId);

  const openCreate = () => {
    setEditingId(null);
    setForm(emptyAgent);
    setFormError(null);
    setModalOpen(true);
  };

  const openEdit = (agent: Agent) => {
    setEditingId(agent.id);
    setForm({ ...agent, api_key: '' });
    setFormError(null);
    setModalOpen(true);
  };

  const closeModal = () => {
    setModalOpen(false);
    setEditingId(null);
    setForm(emptyAgent);
    setFormError(null);
  };

  const save = async () => {
    if (!form.name?.trim() || !form.role?.trim() || !form.system_prompt?.trim()) {
      setFormError('Name, role, and system prompt are required.');
      return;
    }

    if (!form.use_platform_api_key && !form.api_key?.trim()) {
      setFormError('API key is required when not using the platform default.');
      return;
    }

    const payload: Record<string, unknown> = {
      ...form,
      skills: typeof form.skills === 'string'
        ? String(form.skills).split(',').map((s) => s.trim()).filter(Boolean)
        : form.skills,
      guardrails: {
        ...emptyAgent.guardrails,
        ...(form.guardrails || {}),
      },
    };

    if (form.use_platform_api_key) {
      payload.use_platform_api_key = true;
      delete payload.api_key;
    } else {
      payload.use_platform_api_key = false;
      payload.api_key = form.api_key?.trim();
    }

    try {
      if (editingId) {
        await api.updateAgent(editingId, payload);
      } else {
        await api.createAgent(payload);
      }
      closeModal();
      await load();
    } catch (err) {
      setFormError(err instanceof Error ? err.message : 'Failed to save agent');
    }
  };

  const remove = async (id: string) => {
    await api.deleteAgent(id);
    await load();
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
            Agents
          </Typography>
          <Typography variant="body2" color="text.secondary">
            Configure specialist agents with prompts, models, tools, and guardrails.
          </Typography>
        </Box>
        <Button variant="contained" startIcon={<AddIcon />} onClick={openCreate}>
          Create Agent
        </Button>
      </Stack>

      {platform && (
        <Alert severity="info" sx={{ mb: 3, bgcolor: 'rgba(56, 189, 248, 0.08)', border: '1px solid rgba(56, 189, 248, 0.2)' }}>
          Platform defaults:{' '}
          <Chip label={platform.provider} size="small" sx={{ mx: 0.5 }} />
          <Chip label={platform.model || 'provider default'} size="small" />
          <Typography variant="caption" component="div" sx={{ mt: 1, color: 'text.secondary' }}>
            Agents inherit these unless you override provider or model in the edit dialog.
          </Typography>
        </Alert>
      )}

      <Box
        sx={{
          display: 'grid',
          gridTemplateColumns: { xs: '1fr', sm: '1fr 1fr', lg: 'repeat(3, 1fr)' },
          gap: 2.5,
        }}
      >
        {agents.map((agent) => (
          <Card key={agent.id} sx={{ height: '100%', display: 'flex', flexDirection: 'column' }}>
              <CardContent sx={{ flexGrow: 1 }}>
                <Typography variant="h6" gutterBottom>
                  {agent.name}
                </Typography>
                <Typography variant="body2" color="text.secondary" sx={{ mb: 1.5 }}>
                  {agent.role} · {displayAgentLLM(agent, platform)}
                </Typography>
                <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.75, mb: 1.5 }}>
                  {agent.tools.length ? (
                    agent.tools.map((t) => <Chip key={t} label={t} size="small" variant="outlined" />)
                  ) : (
                    <Chip label="No tools" size="small" variant="outlined" />
                  )}
                </Box>
                <Typography
                  variant="body2"
                  color="text.secondary"
                  sx={{ display: '-webkit-box', WebkitLineClamp: 3, WebkitBoxOrient: 'vertical', overflow: 'hidden' }}
                >
                  {agent.system_prompt}
                </Typography>
              </CardContent>
              <CardActions sx={{ px: 2, pb: 2 }}>
                <Button size="small" startIcon={<EditOutlinedIcon />} onClick={() => openEdit(agent)}>
                  Edit
                </Button>
                <Button size="small" color="error" startIcon={<DeleteIcon />} onClick={() => remove(agent.id)}>
                  Delete
                </Button>
              </CardActions>
            </Card>
        ))}
      </Box>

      {!agents.length && (
        <Card sx={{ p: 6, textAlign: 'center' }}>
          <Typography color="text.secondary">No agents yet. Create your first agent to get started.</Typography>
        </Card>
      )}

      <Dialog open={modalOpen} onClose={closeModal} maxWidth="md" fullWidth scroll="paper">
        <DialogTitle>{isEditing ? 'Edit Agent' : 'Create Agent'}</DialogTitle>
        <DialogContent dividers>
          <Stack spacing={2.5} sx={{ pt: 0.5 }}>
            {formError && <Alert severity="error">{formError}</Alert>}

            <Box sx={{ display: 'grid', gridTemplateColumns: { xs: '1fr', sm: '1fr 1fr' }, gap: 2 }}>
              <TextField
                label="Name"
                fullWidth
                required
                value={form.name || ''}
                onChange={(e) => setForm({ ...form, name: e.target.value })}
              />
              <TextField
                label="Role"
                fullWidth
                required
                value={form.role || ''}
                onChange={(e) => setForm({ ...form, role: e.target.value })}
              />
              <FormControl fullWidth>
                <InputLabel>Provider</InputLabel>
                <Select
                  label="Provider"
                  value={form.provider || ''}
                  onChange={(e) => setForm({
                    ...form,
                    provider: e.target.value || null,
                    model: modelsForProvider(platform!, e.target.value || platform?.provider)[0],
                  })}
                >
                  <MenuItem value="">Platform default ({platform?.provider})</MenuItem>
                  {(platform?.providers || []).filter((p) => p !== 'mock').map((p) => (
                    <MenuItem key={p} value={p}>{p}</MenuItem>
                  ))}
                </Select>
              </FormControl>
              <FormControl fullWidth required>
                <InputLabel>Model</InputLabel>
                <Select
                  label="Model"
                  value={form.model || ''}
                  onChange={(e) => setForm({ ...form, model: e.target.value })}
                >
                  {modelOptions.map((m) => (
                    <MenuItem key={m} value={m}>{m}</MenuItem>
                  ))}
                </Select>
              </FormControl>
            </Box>

            <TextField
              label="System Prompt"
              fullWidth
              required
              multiline
              minRows={2}
              maxRows={8}
              value={form.system_prompt || ''}
              onChange={(e) => setForm({ ...form, system_prompt: e.target.value })}
              sx={{
                '& textarea': {
                  resize: 'none',
                  overflow: 'hidden !important',
                },
              }}
            />

            <TextField
              label="Skills (comma-separated)"
              fullWidth
              value={(form.skills || []).join(', ')}
              onChange={(e) => setForm({ ...form, skills: e.target.value.split(',').map((s) => s.trim()) })}
            />

            <TextField
              label="Interaction Rules"
              fullWidth
              multiline
              minRows={2}
              value={form.interaction_rules || ''}
              onChange={(e) => setForm({ ...form, interaction_rules: e.target.value })}
            />

            <TextField
              label="Max Tokens (guardrail)"
              type="number"
              fullWidth
              value={Number(form.guardrails?.max_tokens || 2000)}
              onChange={(e) => setForm({ ...form, guardrails: { ...form.guardrails, max_tokens: Number(e.target.value) } })}
            />

            <FormControl fullWidth>
              <InputLabel>Tools</InputLabel>
              <Select
                multiple
                label="Tools"
                value={form.tools || []}
                onChange={(e) => setForm({ ...form, tools: e.target.value as string[] })}
                renderValue={(selected) => (
                  <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.5 }}>
                    {selected.map((value) => <Chip key={value} label={value} size="small" />)}
                  </Box>
                )}
              >
                {tools.map((t) => (
                  <MenuItem key={t.name} value={t.name}>{t.name}</MenuItem>
                ))}
              </Select>
            </FormControl>

            <Stack direction="row" spacing={3} sx={{ flexWrap: 'wrap' }}>
              <FormControlLabel
                control={
                  <Checkbox
                    checked={Boolean(form.memory_config?.short_term)}
                    onChange={(e) => setForm({ ...form, memory_config: { ...form.memory_config, short_term: e.target.checked } })}
                  />
                }
                label="Short-term memory"
              />
              <FormControlLabel
                control={
                  <Checkbox
                    checked={Boolean(form.memory_config?.long_term)}
                    onChange={(e) => setForm({ ...form, memory_config: { ...form.memory_config, long_term: e.target.checked } })}
                  />
                }
                label="Long-term memory"
              />
              <FormControlLabel
                control={
                  <Checkbox
                    checked={Boolean(form.channels?.telegram)}
                    onChange={(e) => setForm({ ...form, channels: { ...form.channels, telegram: e.target.checked } })}
                  />
                }
                label="Telegram channel"
              />
            </Stack>

            <Box sx={{ p: 2, borderRadius: 2, bgcolor: 'rgba(148, 163, 184, 0.06)', border: '1px solid', borderColor: 'divider' }}>
              <FormControlLabel
                control={
                  <Checkbox
                    checked={Boolean(form.use_platform_api_key)}
                    onChange={(e) => setForm({ ...form, use_platform_api_key: e.target.checked, api_key: '' })}
                  />
                }
                label="Use platform default API key"
              />
              {!form.use_platform_api_key && (
                <TextField
                  label="API Key"
                  type="password"
                  fullWidth
                  required
                  value={form.api_key || ''}
                  onChange={(e) => setForm({ ...form, api_key: e.target.value })}
                  helperText={isEditing ? 'Required when using a custom key for this agent.' : 'Required when not using the platform default key.'}
                  sx={{ mt: 1.5 }}
                />
              )}
              {form.use_platform_api_key && (
                <FormHelperText sx={{ ml: 0 }}>
                  This agent will use the API key configured in your server `.env` file.
                </FormHelperText>
              )}
            </Box>
          </Stack>
        </DialogContent>
        <DialogActions sx={{ px: 3, py: 2 }}>
          <Button onClick={closeModal}>Cancel</Button>
          <Button variant="contained" onClick={save}>
            {isEditing ? 'Save Changes' : 'Create Agent'}
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
}
