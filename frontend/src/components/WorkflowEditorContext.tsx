import { createContext, useContext } from 'react';
import type { Agent, PlatformLLMSettings } from '../api/client';

export type WorkflowEditorContextValue = {
  agents: Agent[];
  availableAgents: Agent[];
  platform: PlatformLLMSettings | null;
  readOnly: boolean;
  onAddConnectedNode: (sourceNodeId: string, agent: Agent) => void;
};

export const WorkflowEditorContext = createContext<WorkflowEditorContextValue>({
  agents: [],
  availableAgents: [],
  platform: null,
  readOnly: true,
  onAddConnectedNode: () => undefined,
});

export function useWorkflowEditor() {
  return useContext(WorkflowEditorContext);
}
