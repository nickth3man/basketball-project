"""
Database utilities and table definitions for the basketball stats project.

This module centralizes:
- SQLAlchemy table definitions
- Common database operations
- Dependency injection for database sessions
- Pagination utilities
"""

from __future__ import annotations

import logging
from io import StringIO
from typing import TYPE_CHECKING, Any, Dict, List, Tuple

if TYPE_CHECKING:
    from psycopg import Connection

from sqlalchemy import (
    Boolean,
    Column,
    Integer,
    MetaData,
    String,
    Table,
    and_,
    or_,
    select,
)
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from .config import get_settings

logger = logging.getLogger(__name__)

# Database configuration
config = get_settings()

# [NOTE][PERF] Connection pool configured for moderate load.
# Tune based on actual workload and concurrent request patterns.
engine = create_async_engine(
    config.pg_dsn,
    echo=False,
    pool_size=10,  # Base pool size
    max_overflow=5,  # Additional connections when pool is full
    pool_timeout=30,  # Wait up to 30s for connection
    pool_pre_ping=True,  # Verify connections before use
)
AsyncSessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

# Metadata for table definitions
metadata = MetaData()

# Centralized table definitions using SQLAlchemy's Table object
players_table = Table(
    "players",
    metadata,
    Column("player_id", Integer, primary_key=True),
    Column("slug", String(100)),
    Column("full_name", String(200)),
    Column("first_name", String(100)),
    Column("last_name", String(100)),
    Column("is_active", Boolean),
    Column("hof_inducted", Boolean),
    Column("rookie_year", Integer),
    Column("final_year", Integer),
)

player_season_table = Table(
    "player_season",
    metadata,
    Column("seas_id", Integer, primary_key=True),
    Column("player_id", Integer),
    Column("season_end_year", Integer),
    Column("team_id", Integer),
    Column("team_abbrev", String(10)),
    Column("is_total", Boolean),
    Column("is_playoffs", Boolean),
)

player_season_pg_table = Table(
    "player_season_per_game",
    metadata,
    Column("seas_id", Integer),
    Column("g", Integer),
    Column("pts_per_g", String),
    Column("trb_per_g", String),
    Column("ast_per_g", String),
)

games_table = Table(
    "games",
    metadata,
    Column("game_id", String(20), primary_key=True),
    Column("season_end_year", Integer),
    Column("game_date_est", String(20)),
    Column("home_team_id", Integer),
    Column("away_team_id", Integer),
    Column("home_pts", Integer),
    Column("away_pts", Integer),
    Column("is_playoffs", Boolean),
)

teams_table = Table(
    "teams",
    metadata,
    Column("team_id", Integer, primary_key=True),
    Column("team_abbrev", String(10)),
    Column("team_name", String(200)),
    Column("team_city", String(200)),
    Column("is_active", Boolean),
    Column("start_season", Integer),
    Column("end_season", Integer),
)

boxscore_team_table = Table(
    "boxscore_team",
    metadata,
    Column("game_id", String(20)),
    Column("team_id", Integer),
    Column("pts", Integer),
)


# Database dependency
async def get_db() -> AsyncSession:
    """Get async database session."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()


# Pagination dependency
def get_pagination():
    """Get pagination parameters."""

    def pagination_dependency(page: int = 1, page_size: int = 50):
        if page < 1:
            page = 1
        if page_size < 1 or page_size > 1000:
            page_size = 50
        return (page, page_size)

    return pagination_dependency


# Utility functions
def parse_bool(value: str | None) -> bool | None:
    """Parse boolean string to Python bool."""
    if value is None:
        return None
    return value.lower() in {"true", "1", "yes", "on"}


def parse_comma_ints(value: str | None) -> List[int]:
    """Parse comma-separated integers."""
    if not value:
        return []
    return [int(x.strip()) for x in value.split(",") if x.strip().isdigit()]


# Bulk operations
async def bulk_insert(
    table: Table, data: List[Dict[str, Any]], conn: Connection
) -> None:
    """
    Insert data in bulk using COPY operation.

    [NOTE] This function uses psycopg (sync) Connection, not asyncpg.
    Intended for ETL use, not API layer. API should use asyncpg bulk operations.

    Preconditions: table exists; data is non-empty list of dicts with consistent keys.
    Postconditions: All rows inserted via COPY.
    Side effects: Database write.
    """
    # [TODO][SECURITY][P2] @api/db
    # What: Validate table.name against allowlist to prevent SQL injection.
    # Why (root cause): Table name comes from Table object, but should validate anyway.
    # Risk/Impact: Low (Table objects are code-defined), but defense-in-depth.
    # Next step: Add table name validation if this is ever called with user input.
    # Evidence: Line 166; f-string with table.name (safe if Table objects are trusted).

    if not data:
        return

    # Convert to list of lists for COPY
    columns = list(data[0].keys())
    values = [
        [str(row[col]) if row[col] is not None else None for col in columns]
        for row in data
    ]

    # [NOTE][PERF] COPY is efficient for bulk inserts (faster than INSERT).
    # Trade-off: Less flexible than parameterized INSERT (no RETURNING, etc.).
    # Use COPY for efficient bulk insert
    copy_query = f"COPY {table.name} ({','.join(columns)}) FROM STDIN WITH CSV"
    curr = conn.cursor()
    curr.copy_expert(copy_query, StringIO("\n".join([",".join(row) for row in values])))
    curr.close()  # psycopg cursors are sync, not async


# Allowlist of tables that can be truncated (ETL use only)
ALLOWED_TRUNCATE_TABLES = {
    "players",
    "teams",
    "seasons",
    "games",
    "boxscore_team",
    "player_season",
    "player_season_per_game",
    "player_season_totals",
    "player_season_per36",
    "player_season_per100",
    "player_season_advanced",
    "team_season",
    "team_season_per_game",
    "team_season_totals",
    "pbp_events",
}


def truncate_table(conn: Connection, table_name: str, cascade: bool = False) -> None:
    """
    Truncate table with optional cascade.

    [SECURITY] Validates table_name against allowlist before execution.

    Preconditions: table_name is in ALLOWED_TRUNCATE_TABLES.
    Postconditions: Table truncated (all rows deleted).
    Side effects: Irreversible data deletion.
    """
    if table_name not in ALLOWED_TRUNCATE_TABLES:
        raise ValueError(
            f"Table '{table_name}' not in allowlist. "
            f"Allowed tables: {sorted(ALLOWED_TRUNCATE_TABLES)}"
        )

    cascade_clause = " CASCADE" if cascade else ""
    curr = conn.cursor()
    curr.execute(f"TRUNCATE TABLE {table_name}{cascade_clause}")
    curr.close()


# Common query builders
def build_players_query(
    filters: List[Dict[str, Any]] = None,
    season_filter: Tuple[int, int] = None,
    search_term: str = None,
    active_only: bool = None,
    hof_only: bool = None,
) -> select:
    """Build optimized players query with filters."""
    query = select(players_table)

    # Apply filters
    filter_clauses = []
    if season_filter:
        start_year, end_year = season_filter
        filter_clauses.append(players_table.c.final_year >= start_year)
        filter_clauses.append(players_table.c.rookie_year <= end_year)

    if active_only is not None:
        filter_clauses.append(players_table.c.is_active == active_only)

    if hof_only is not None:
        filter_clauses.append(players_table.c.hof_inducted == hof_only)

    if search_term:
        search_pattern = f"%{search_term.lower()}%"
        filter_clauses.append(
            or_(
                players_table.c.full_name.ilike(search_pattern),
                players_table.c.first_name.ilike(search_pattern),
                players_table.c.last_name.ilike(search_pattern),
                players_table.c.slug.ilike(search_pattern),
            )
        )

    if filter_clauses:
        query = query.where(and_(*filter_clauses))

    return query.order_by(
        players_table.c.full_name.nulls_last(), players_table.c.player_id
    )


def build_pagination_query(query: select, page: int, page_size: int) -> select:
    """
    Add pagination to query.

    Returns only the paginated query. Callers must compute count separately
    by executing count_query via their async session.

    Preconditions: query is a valid SQLAlchemy select statement.
    Postconditions: Returns paginated query (no execution).
    Side effects: None (query building only, no execution).
    """
    offset = (page - 1) * page_size
    paginated_query = query.limit(page_size).offset(offset)

    return paginated_query
