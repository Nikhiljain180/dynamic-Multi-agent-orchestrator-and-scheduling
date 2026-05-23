import pytest

from app.channels.telegram_adapter import handle_telegram_message


class FakeMessage:
    def __init__(self, text: str):
        self.text = text
        self.replies: list[str] = []

    async def reply_text(self, text: str):
        self.replies.append(text)


class FakeChat:
    def __init__(self, chat_id: int):
        self.id = chat_id


class FakeUpdate:
    def __init__(self, text: str, chat_id: int = 123):
        self.message = FakeMessage(text)
        self.effective_chat = FakeChat(chat_id)


@pytest.mark.asyncio
async def test_telegram_routes_to_triage_workflow(client, db_session, monkeypatch):
    from app.services.seed import seed_templates

    await seed_templates(db_session)

    update = FakeUpdate("I have a billing question about my invoice")
    await handle_telegram_message(update, None)

    assert any("Processing" in r for r in update.message.replies)
    assert len(update.message.replies) >= 2
