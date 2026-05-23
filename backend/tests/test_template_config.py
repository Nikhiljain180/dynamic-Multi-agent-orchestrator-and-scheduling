from app.runtime.template_config import resolve_template_type, template_supports_schedule


def test_telegram_triage_does_not_support_schedule_by_type():
    assert template_supports_schedule({"template_type": "telegram_triage"}) is False


def test_telegram_triage_does_not_support_schedule_by_name():
    assert template_supports_schedule({}, "Telegram Support Triage") is False


def test_brief_summary_supports_schedule():
    assert template_supports_schedule({"template_type": "brief_summary"}) is True
    assert template_supports_schedule({}, "Quick Brief → Executive Summary") is True


def test_resolve_template_type_from_name():
    assert resolve_template_type({}, "Telegram Support Triage") == "telegram_triage"


def test_unknown_template_defaults_to_schedule_allowed():
    assert template_supports_schedule({}) is True
    assert template_supports_schedule({"template_type": "custom"}) is True
