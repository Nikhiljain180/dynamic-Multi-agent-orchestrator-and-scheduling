import { describe, expect, it } from 'vitest';
import {
  DEFAULT_TEMPLATE_UI_CONFIG,
  getTemplateUiConfig,
  resolveTemplateType,
  templateSupportsSchedule,
} from './workflowTemplateConfig';

describe('workflowTemplateConfig', () => {
  it('enables run input and schedule for brief_summary', () => {
    const config = getTemplateUiConfig({ template_type: 'brief_summary', nodes: [], edges: [] });
    expect(config.showRunInput).toBe(true);
    expect(config.showSchedule).toBe(true);
    expect(config.showManualRun).toBe(true);
  });

  it('hides run input and schedule for telegram_triage via template_type', () => {
    const config = getTemplateUiConfig({ template_type: 'telegram_triage', nodes: [], edges: [] });
    expect(config.showRunInput).toBe(false);
    expect(config.showSchedule).toBe(false);
    expect(config.showManualRun).toBe(false);
    expect(config.channelHint).toMatch(/Telegram/i);
  });

  it('hides run input and schedule for Telegram Support Triage by workflow name', () => {
    const config = getTemplateUiConfig({ nodes: [], edges: [] }, 'Telegram Support Triage');
    expect(config.showRunInput).toBe(false);
    expect(config.showSchedule).toBe(false);
    expect(config.showManualRun).toBe(false);
  });

  it('resolves template type from workflow name when graph field is missing', () => {
    expect(resolveTemplateType({ nodes: [], edges: [] }, 'Telegram Support Triage')).toBe('telegram_triage');
    expect(resolveTemplateType({ nodes: [], edges: [] }, 'Quick Brief → Executive Summary')).toBe('brief_summary');
  });

  it('falls back to defaults for unknown or missing template_type', () => {
    expect(getTemplateUiConfig(undefined)).toEqual(DEFAULT_TEMPLATE_UI_CONFIG);
    expect(getTemplateUiConfig({ nodes: [], edges: [] })).toEqual(DEFAULT_TEMPLATE_UI_CONFIG);
    expect(getTemplateUiConfig({ template_type: 'custom', nodes: [], edges: [] })).toEqual(
      DEFAULT_TEMPLATE_UI_CONFIG,
    );
  });

  it('templateSupportsSchedule respects mapping and name fallback', () => {
    expect(templateSupportsSchedule({ template_type: 'telegram_triage', nodes: [], edges: [] })).toBe(false);
    expect(templateSupportsSchedule({ nodes: [], edges: [] }, 'Telegram Support Triage')).toBe(false);
    expect(templateSupportsSchedule({ template_type: 'brief_summary', nodes: [], edges: [] })).toBe(true);
  });
});
