from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

_MIGRATIONS = (
    "ALTER TABLE agents ADD COLUMN IF NOT EXISTS provider VARCHAR(50)",
    "ALTER TABLE agents ADD COLUMN IF NOT EXISTS api_key_encrypted TEXT",
    "ALTER TABLE agents ADD COLUMN IF NOT EXISTS api_key_hint VARCHAR(50)",
    "ALTER TABLE agents ADD COLUMN IF NOT EXISTS use_platform_api_key BOOLEAN DEFAULT TRUE",
)


async def run_migrations(engine: AsyncEngine) -> None:
    async with engine.begin() as conn:
        for statement in _MIGRATIONS:
            await conn.execute(text(statement))
