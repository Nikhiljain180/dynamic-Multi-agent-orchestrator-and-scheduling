import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import router
from app.channels.telegram_adapter import start_telegram_bot, stop_telegram_bot
from app.database import AsyncSessionLocal, Base, engine
from app.services.seed import seed_templates
from app.services.migrate import run_migrations
from app.workers.scheduler import start_scheduler, stop_scheduler

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    await run_migrations(engine)

    async with AsyncSessionLocal() as db:
        await seed_templates(db)

    try:
        await start_telegram_bot()
    except Exception as exc:
        logger.warning("Telegram bot failed to start: %s", exc)

    try:
        await start_scheduler()
    except Exception as exc:
        logger.warning("Workflow scheduler failed to start: %s", exc)
    yield
    await stop_scheduler()
    await stop_telegram_bot()
    await engine.dispose()


app = FastAPI(
    title="Yuno AI Agent Orchestration Platform",
    description="Create, configure, and orchestrate multi-agent workflows with LangGraph",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router, prefix="/api")


@app.get("/health")
async def health():
    return {"status": "ok"}
