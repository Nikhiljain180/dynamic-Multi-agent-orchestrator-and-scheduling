"""Per-template capabilities (keep in sync with frontend workflowTemplateConfig.ts)."""

TEMPLATE_SUPPORTS_SCHEDULE: dict[str, bool] = {
    "brief_summary": True,
    "research_pipeline": True,
    "telegram_triage": False,
}

WORKFLOW_NAME_TEMPLATE_TYPE: dict[str, str] = {
    "Quick Brief → Executive Summary": "brief_summary",
    "Research → Write → Review": "brief_summary",
    "Telegram Support Triage": "telegram_triage",
}


def resolve_template_type(graph_definition: dict | None, workflow_name: str | None = None) -> str:
    template_type = str((graph_definition or {}).get("template_type") or "").strip()
    if template_type:
        return template_type
    name = str(workflow_name or "").strip()
    return WORKFLOW_NAME_TEMPLATE_TYPE.get(name, "")


def template_supports_schedule(graph_definition: dict | None, workflow_name: str | None = None) -> bool:
    template_type = resolve_template_type(graph_definition, workflow_name)
    if template_type in TEMPLATE_SUPPORTS_SCHEDULE:
        return TEMPLATE_SUPPORTS_SCHEDULE[template_type]
    return True
