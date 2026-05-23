# Adding a New Messaging Channel

## Adapter pattern

External channels implement a simple contract:

1. **Inbound** — receive human message → find workflow → create `WorkflowRun`
2. **Execute** — call `execute_workflow_run(run_id, channel_context)`
3. **Outbound** — send `run.output_text` back to the human

See `backend/app/channels/telegram_adapter.py` as the reference implementation. Set `TELEGRAM_WORKFLOW_NAME` in `.env` to choose which workflow an adapter executes.

## Steps to add Slack

### 1. Create the adapter

```python
# backend/app/channels/slack_adapter.py

async def handle_slack_message(event: dict) -> None:
    text = event["text"]
    channel_id = event["channel"]

    async with AsyncSessionLocal() as db:
        workflow = await find_workflow_by_name(db, "Slack Support Triage")
        run = await RunService.create_run(db, workflow.id, text)

    await execute_workflow_run(run.id, {"channel": "slack", "channel_id": channel_id})

    async with AsyncSessionLocal() as db:
        run = await RunService.get_run(db, run.id)
        await send_slack_reply(channel_id, run.output_text)
```

### 2. Start the listener in `main.py`

```python
from app.channels.slack_adapter import start_slack_bot

# In lifespan:
await start_slack_bot()
```

### 3. Bind agents to the channel

Set `channels: {"slack": true}` on relevant agents in the UI.

### 4. Create a workflow template

Build a triage workflow (or reuse the Telegram template graph definition with different `template_type`).

## Steps to add WhatsApp

WhatsApp Business API requires Meta developer setup. The adapter structure is identical:

```python
# backend/app/channels/whatsapp_adapter.py

async def handle_whatsapp_webhook(payload: dict) -> None:
    text = payload["messages"][0]["text"]["body"]
    phone = payload["messages"][0]["from"]
    # Same run → execute → reply pattern
```

## Testing

Add a test in `backend/tests/test_<channel>_adapter.py`:

```python
@pytest.mark.asyncio
async def test_inbound_routes_to_workflow(client, db_session):
    await seed_templates(db_session)
    await handle_fake_message("billing question")
    # Assert run created and reply sent
```

## Environment variables

| Channel | Variable |
|---------|----------|
| Telegram | `TELEGRAM_BOT_TOKEN` |
| Slack | `SLACK_BOT_TOKEN`, `SLACK_APP_TOKEN` |
| WhatsApp | `WHATSAPP_TOKEN`, `WHATSAPP_PHONE_ID` |

Document new variables in `.env.example` and README.
