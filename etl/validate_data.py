from __future__ import annotations

"""
Lightweight DB-level validation harness.

Usage (non-interactive):

    python -m etl.validate_data

Behavior:

- Uses the same configuration mechanism as other ETL modules.
- Connects via etl.db.get_connection / etl.db.release_connection.
- Runs structural, referential, and basic summary checks.
- Prints human-readable messages.
- Exits with code 0 on success, non-zero on fatal issues.

This module is intentionally conservative:
- It does not import API or frontend modules.
- It does not mutate data.
"""

from typing import Iterable, List

from psycopg import Connection

from .config import get_config
from .db import get_connection, release_connection
from .logging_utils import get_logger, log_structured

logger = get_logger(__name__)


# -----------------------
# Helper query primitives
# -----------------------


def check_table_exists(conn: Connection, table_name: str) -> bool:
    """
    Return True if the given table or view exists in the current schema.

    Uses information_schema; matches both BASE TABLE and VIEW.
    """
    sql = """
        SELECT 1
        FROM information_schema.tables
        WHERE table_name = %s
        UNION ALL
        SELECT 1
        FROM information_schema.views
        WHERE table_name = %s
        LIMIT 1
    """
    with conn.cursor() as cur:
        cur.execute(sql, (table_name, table_name))
        exists = cur.fetchone() is not None

    # Pylance's complaint about **fields types is conservative; this is fine at runtime.
    log_structured(
        logger,
        logger.level,
        "Checked table existence",
        table=table_name,
        exists=exists,
    )
    return exists


def count_orphans(
    conn: Connection,
    child_table: str,
    child_column: str,
    parent_table: str,
    parent_column: str,
) -> int:
    """
    Count rows in child_table where child_column is not null
    and missing in parent_table.
    """
    sql = f"""
        SELECT COUNT(*)
        FROM {child_table} c
        LEFT JOIN {parent_table} p
          ON c.{child_column} = p.{parent_column}
        WHERE c.{child_column} IS NOT NULL
          AND p.{parent_column} IS NULL
    """
    with conn.cursor() as cur:
        cur.execute(sql)
        row = cur.fetchone()
        cnt = int(row[0]) if row and row[0] is not None else 0

    log_structured(
        logger,
        logger.level,
        "Checked orphan references",
        child_table=child_table,
        child_column=child_column,
        parent_table=parent_table,
        parent_column=parent_column,
        orphans=cnt,
    )
    return cnt


def _table_must_exist(
    conn: Connection, table_name: str, fatal_errors: List[str]
) -> None:
    if not check_table_exists(conn, table_name):
        msg = f"Missing required table/view: {table_name}"
        logger.error(msg)
        fatal_errors.append(msg)


def _count_rows(conn: Connection, table_name: str) -> int:
    sql = f"SELECT COUNT(*) FROM {table_name}"
    with conn.cursor() as cur:
        cur.execute(sql)
        row = cur.fetchone()
        return int(row[0]) if row and row[0] is not None else 0


# -------------
# Validations
# -------------


def run_structural_checks(conn: Connection) -> List[str]:
    """
    Ensure that core tables and advanced views exist.

    Returns a list of fatal error messages (empty if all ok).
    """
    fatal_errors: List[str] = []

    required_tables: Iterable[str] = [
        "players",
        "teams",
        "games",
        "player_season",
        "team_season",
        "boxscore_team",
        "pbp_events",
    ]

    # Advanced views referenced in 002_advanced_views.sql
    required_views: Iterable[str] = [
        "vw_player_season_advanced",
        "vw_team_season_advanced",
        "vw_player_career_aggregates",
    ]

    for name in required_tables:
        _table_must_exist(conn, name, fatal_errors)

    for name in required_views:
        _table_must_exist(conn, name, fatal_errors)

    return fatal_errors


def run_referential_checks(conn: Connection) -> List[str]:
    """
    Check key relationships for orphans.

    Returns a list of fatal error messages (empty if all ok).
    """
    fatal_errors: List[str] = []

    # player_season.player_id -> players.player_id
    cnt = count_orphans(conn, "player_season", "player_id", "players", "player_id")
    if cnt:
        fatal_errors.append(
            (
                "Found {count} orphan "
                "player_season.player_id not in players.player_id"
            ).format(count=cnt),
        )

    # team_season.team_id -> teams.team_id
    cnt = count_orphans(conn, "team_season", "team_id", "teams", "team_id")
    if cnt:
        fatal_errors.append(
            "Found {count} orphan team_season.team_id not in teams.team_id".format(
                count=cnt,
            ),
        )

    # boxscore_team.game_id -> games.game_id
    cnt = count_orphans(conn, "boxscore_team", "game_id", "games", "game_id")
    if cnt:
        fatal_errors.append(
            "Found {count} orphan boxscore_team.game_id not in games.game_id".format(
                count=cnt,
            ),
        )

    # pbp_events.game_id -> games.game_id
    cnt = count_orphans(conn, "pbp_events", "game_id", "games", "game_id")
    if cnt:
        fatal_errors.append(
            "Found {count} orphan pbp_events.game_id not in games.game_id".format(
                count=cnt,
            ),
        )

    return fatal_errors


def run_summary_checks(conn: Connection) -> List[str]:
    """
    Basic sanity checks on core table row counts.

    Returns a list of non-fatal warning messages.
    """
    warnings: List[str] = []

    for table in ("players", "teams", "games"):
        if not check_table_exists(conn, table):
            # Structural check handles missing tables; don't duplicate here.
            continue
        count = _count_rows(conn, table)
        if count <= 0:
            msg = f"Warning: table {table} has no rows (count={count})"
            logger.warning(msg)
            warnings.append(msg)
        else:
            log_structured(
                logger,
                logger.level,
                "Row count check passed",
                table=table,
                count=count,
            )

    return warnings


# -------------
# Entrypoint
# -------------


def main() -> None:
    """
    Run all validation checks and exit with appropriate status code.

    Exit codes:
    - 0: all checks passed (possibly with warnings).
    - 1: structural or referential integrity failures detected.
    - 2: unexpected runtime error (e.g., connection issues).
    """
    config = get_config()
    conn: Connection | None = None
    try:
        conn = get_connection(config)

        fatal_errors: List[str] = []
        warnings: List[str] = []

        fatal_errors.extend(run_structural_checks(conn))
        fatal_errors.extend(run_referential_checks(conn))
        warnings.extend(run_summary_checks(conn))

        if fatal_errors:
            for msg in fatal_errors:
                logger.error("VALIDATION FATAL: %s", msg)
            log_structured(
                logger,
                logger.level,
                "Data validation failed",
                fatal_count=len(fatal_errors),
                warning_count=len(warnings),
            )
            raise SystemExit(1)

        for msg in warnings:
            logger.warning("VALIDATION WARNING: %s", msg)

        log_structured(
            logger,
            logger.level,
            "Data validation passed",
            fatal_count=0,
            warning_count=len(warnings),
        )
        raise SystemExit(0)
    except SystemExit:
        # Re-raise SystemExit without logging as error again.
        raise
    except Exception as exc:  # pragma: no cover - defensive
        logger.exception("Unexpected error during data validation: %s", exc)
        raise SystemExit(2)
    finally:
        if conn is not None:
            release_connection(conn)


if __name__ == "__main__":
    main()
