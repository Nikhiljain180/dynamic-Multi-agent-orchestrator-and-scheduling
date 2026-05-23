import type { GraphDefinition } from '../api/client';

export interface TemplateUiConfig {
  showRunInput: boolean;
  showSchedule: boolean;
  showManualRun: boolean;
  channelHint?: string;
}

/** Fallback when graph_definition.template_type is missing (legacy DB rows). */
export const WORKFLOW_NAME_TEMPLATE_TYPE: Record<string, string> = {
  'Quick Brief → Executive Summary': 'brief_summary',
  'Research → Write → Review': 'brief_summary',
  'Telegram Support Triage': 'telegram_triage',
};

/** Per-template Workflows page field visibility. Extend when adding new templates. */
export const TEMPLATE_UI_CONFIG: Record<string, TemplateUiConfig> = {
  brief_summary: {
    showRunInput: true,
    showSchedule: true,
    showManualRun: true,
  },
  research_pipeline: {
    showRunInput: true,
    showSchedule: true,
    showManualRun: true,
  },
  telegram_triage: {
    showRunInput: false,
    showSchedule: false,
    showManualRun: false,
    channelHint: 'Triggered by Telegram messages. Set TELEGRAM_BOT_TOKEN and send a message to your bot.',
  },
};

export const DEFAULT_TEMPLATE_UI_CONFIG: TemplateUiConfig = {
  showRunInput: true,
  showSchedule: true,
  showManualRun: true,
};

export function resolveTemplateType(
  graph: GraphDefinition | undefined,
  workflowName?: string | null,
): string | undefined {
  const fromGraph = graph?.template_type?.trim();
  if (fromGraph) return fromGraph;
  const name = workflowName?.trim();
  if (name && WORKFLOW_NAME_TEMPLATE_TYPE[name]) {
    return WORKFLOW_NAME_TEMPLATE_TYPE[name];
  }
  return undefined;
}

export function getTemplateUiConfig(
  graph: GraphDefinition | undefined,
  workflowName?: string | null,
): TemplateUiConfig {
  const templateType = resolveTemplateType(graph, workflowName);
  if (templateType && TEMPLATE_UI_CONFIG[templateType]) {
    return TEMPLATE_UI_CONFIG[templateType];
  }
  return DEFAULT_TEMPLATE_UI_CONFIG;
}

export function templateSupportsSchedule(
  graph: GraphDefinition | undefined,
  workflowName?: string | null,
): boolean {
  return getTemplateUiConfig(graph, workflowName).showSchedule;
}
