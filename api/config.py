from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings


class ApiSettings(BaseSettings):
    """
    Runtime configuration for the API layer.

    - Uses env vars for flexibility.
    - Defaults mirror ETL-style DSN expectations (local Postgres).
    """

    # Async SQLAlchemy-style PostgreSQL DSN.
    # Default matches local development; override via API_PG_DSN.
    pg_dsn: str = Field(
        default="postgresql+asyncpg://basketball:basketball@localhost:5433/basketball",
        description="Database connection string for async SQLAlchemy engine.",
    )

    page_size_default: int = Field(50, ge=1, le=500)
    page_size_max: int = Field(200, ge=1, le=1000)

    class Config:
        env_prefix = "API_"
        case_sensitive = False


@lru_cache(maxsize=1)
def get_settings() -> ApiSettings:
    """Cached accessor so settings are constructed once per process."""
    return ApiSettings()


__all__ = ["ApiSettings", "get_settings"]
