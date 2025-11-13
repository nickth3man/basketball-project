from __future__ import annotations

from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from .config import get_settings

_settings = get_settings()

# Single shared async engine / sessionmaker for the process.
engine: AsyncEngine = create_async_engine(
    _settings.pg_dsn,
    future=True,
    echo=False,
)

AsyncSessionMaker = async_sessionmaker(
    bind=engine,
    expire_on_commit=False,
    autoflush=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    FastAPI dependency that yields an AsyncSession.

    Does NOT create or modify schema; it only connects to the existing DB.
    """
    async with AsyncSessionMaker() as session:
        try:
            yield session
        finally:
            # session context handles close; explicit for clarity
            await session.close()


__all__ = ["engine", "AsyncSessionMaker", "get_db"]