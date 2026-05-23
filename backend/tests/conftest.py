import json

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from fastapi import FastAPI
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.api.routes import router
from app.database import Base, get_db

TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

test_app = FastAPI()
test_app.include_router(router, prefix="/api")


@pytest_asyncio.fixture
async def engine():
    eng = create_async_engine(
        TEST_DATABASE_URL,
        echo=False,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield eng
    await eng.dispose()


@pytest_asyncio.fixture
async def session_factory(engine):
    return async_sessionmaker(engine, expire_on_commit=False)


@pytest_asyncio.fixture
async def db_session(session_factory):
    async with session_factory() as session:
        yield session


@pytest_asyncio.fixture(autouse=True)
def patch_session_local(session_factory, monkeypatch):
    monkeypatch.setattr("app.database.AsyncSessionLocal", session_factory)
    monkeypatch.setattr("app.workers.executor.AsyncSessionLocal", session_factory)
    monkeypatch.setattr("app.channels.telegram_adapter.AsyncSessionLocal", session_factory)
    monkeypatch.setattr("app.workers.scheduler.AsyncSessionLocal", session_factory)


@pytest_asyncio.fixture
async def client(session_factory):
    async def override_get_db():
        async with session_factory() as session:
            yield session

    test_app.dependency_overrides[get_db] = override_get_db

    async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test") as ac:
        yield ac

    test_app.dependency_overrides.clear()


@pytest_asyncio.fixture(autouse=True)
def patch_settings(monkeypatch):
    from app.config import settings

    monkeypatch.setattr(settings, "llm_provider", "mock")
    monkeypatch.setattr(settings, "allow_mock_llm_fallback", False)


@pytest.fixture
def published_events():
    return []


@pytest_asyncio.fixture(autouse=True)
async def mock_redis(monkeypatch, published_events):
    class FakeRedis:
        async def publish(self, channel, payload):
            published_events.append({"channel": channel, "payload": json.loads(payload) if isinstance(payload, str) else payload})
            return 1

        def pubsub(self):
            return FakePubSub(published_events)

    class FakePubSub:
        def __init__(self, events):
            self.events = events
            self.channel = None
            self._delivered = 0

        async def subscribe(self, channel):
            self.channel = channel

        async def get_message(self, ignore_subscribe_messages=True, timeout=1.0):
            for idx, event in enumerate(self.events):
                if event["channel"] == self.channel:
                    return {"data": json.dumps(event["payload"])}
            raise TimeoutError

        async def unsubscribe(self, channel):
            return None

        async def close(self):
            return None

    async def fake_get_redis():
        return FakeRedis()

    monkeypatch.setattr("app.services.get_redis", fake_get_redis)
    monkeypatch.setattr("app.api.routes.get_redis", fake_get_redis)

    async def capture_publish(channel, payload):
        published_events.append({"channel": channel, "payload": payload})

    monkeypatch.setattr("app.services.publish_event", capture_publish)
