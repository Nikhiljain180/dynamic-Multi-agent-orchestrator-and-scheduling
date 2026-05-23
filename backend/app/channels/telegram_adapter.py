import asyncio
import logging

from sqlalchemy import select
from telegram import Update
from telegram.ext import Application, ContextTypes, MessageHandler, filters

from app.config import settings
from app.database import AsyncSessionLocal
from app.models import Workflow
from app.services import RunService
from app.workers.executor import execute_workflow_run

logger = logging.getLogger(__name__)

_telegram_app: Application | None = None


async def handle_telegram_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message or not update.message.text:
        return

    text = update.message.text
    chat_id = str(update.effective_chat.id if update.effective_chat else "")

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Workflow).where(Workflow.name == settings.telegram_workflow_name).limit(1)
        )
        workflow = result.scalar_one_or_none()
        if not workflow:
            await update.message.reply_text("Support workflow not configured yet.")
            return

        run = await RunService.create_run(db, workflow.id, text)
        await update.message.reply_text("Processing your request...")

    channel_context = {"channel": "telegram", "chat_id": chat_id}
    await execute_workflow_run(run.id, channel_context)

    async with AsyncSessionLocal() as db:
        completed = await RunService.get_run(db, run.id)
        reply = completed.output_text if completed and completed.output_text else "Done processing your request."
        await update.message.reply_text(reply[:4000])


async def start_telegram_bot() -> None:
    global _telegram_app
    if not settings.telegram_bot_token or settings.telegram_bot_token == "your-telegram-bot-token":
        logger.warning("Telegram bot token not configured — skipping Telegram integration")
        return

    _telegram_app = Application.builder().token(settings.telegram_bot_token).build()
    _telegram_app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_telegram_message))
    await _telegram_app.initialize()
    await _telegram_app.start()
    await _telegram_app.updater.start_polling(drop_pending_updates=True)
    logger.info("Telegram bot started (polling mode)")


async def stop_telegram_bot() -> None:
    global _telegram_app
    if _telegram_app:
        await _telegram_app.updater.stop()
        await _telegram_app.stop()
        await _telegram_app.shutdown()
        _telegram_app = None
